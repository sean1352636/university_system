"""Destinations confirmed by the university itself.

Until now every KS5 destination was what the college was *told* — by the
learner, a parent, a survey, UCAS Track. When a leaver goes to the home
university, the university knows for certain, and publishes it on the
cross-system bus:

* ``university.student.enrolled`` — the learner enrolled (course, start
  date). Applied to the learner's **LEAVING** destination.
* ``university.student.progressed`` — the learner progressed from one year
  to the next ("Sustained into Year 2").
* ``university.student.withdrawn`` — the learner withdrew ("Withdrew in
  Year 1"). Only a reason *category* is ever sent, never the reason.

Each event is stored once in ``dest_university_confirmations`` (keyed on
what it says, not on the bus event id, so a redelivery or a re-publish is
a no-op) and applied through the destinations module's own functions:

* **LEAVING record** — created if there is none; filled in if it is blank
  or ``Unknown``. A destination staff entered by hand is **never
  overwritten**: a matching one is marked confirmed (blank fields filled,
  a note added), a different one gets a note asking for review and the
  confirmation is flagged as a conflict.
* **Monthly activity** (``sustained``) — Higher Education months from the
  course start up to the month the university recorded the event, so the
  DfE sustained measure counts what the university confirmed. Months staff
  already recorded are left as they are. For a withdrawal the withdrawal
  month itself is not counted (the learner was not in HE for all of it).

Handlers never raise for a learner this college does not know — the bus
may deliver another college's learners, or a learner since erased.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_DESTINATIONS_DB

EVENT_ENROLLED = "university.student.enrolled"
EVENT_PROGRESSED = "university.student.progressed"
EVENT_WITHDRAWN = "university.student.withdrawn"

#: The confirmed-via / activity-source value written for these records.
SOURCE = "University (confirmed by institution)"

#: Bus consumer identity (one receipt per event per handler).
CONSUMER_SYSTEM = "sixth_form"
HANDLER_PREFIX = "sixth_form.destinations.university_confirmations"

#: The reason categories the university may send (anything else is shown
#: as "not disclosed").
REASON_LABELS = {"academic": "Academic", "not_disclosed": "Not disclosed"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dest_university_confirmations (
    confirmation_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key              TEXT NOT NULL UNIQUE,
    event_type             TEXT NOT NULL
                           CHECK (event_type IN ('enrolled', 'progressed', 'withdrawn')),
    student_id             TEXT NOT NULL,
    journey_id             TEXT,
    university_student_id  TEXT,
    institution            TEXT,
    course                 TEXT,
    course_code            TEXT,
    start_date             TEXT,
    from_year              INTEGER,
    to_year                INTEGER,
    event_date             TEXT,
    reason_category        TEXT,
    outcome                TEXT NOT NULL,
    applied                TEXT,
    conflict               INTEGER NOT NULL DEFAULT 0,
    months_recorded        INTEGER NOT NULL DEFAULT 0,
    bus_event_id           TEXT,
    received_at            TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_dest_uniconf_student
    ON dest_university_confirmations(student_id, event_type);
CREATE INDEX IF NOT EXISTS idx_dest_uniconf_unisid
    ON dest_university_confirmations(university_student_id);
"""


def _connect() -> _sql.Connection:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.progression.destinations import (
        sustained as _sustained,
    )
    _sustained.init_db()          # destinations + students + activity tables
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _DB_READY = True


# ── helpers ─────────────────────────────────────────────────────────


def _clean(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _iso_date(value: Any) -> str | None:
    text = (_clean(value) or "")[:10]
    try:
        return _dt.date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _norm(value: Any) -> str:
    return " ".join(str(value or "").casefold().replace("&", " and ").split())


def _payload(envelope: dict) -> dict:
    payload = dict(envelope.get("payload") or {})
    payload.setdefault("journey_id", envelope.get("journey_id"))
    return payload


def _student_exists(student_id: str | None) -> bool:
    if not student_id:
        return False
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    return _students.get_student(student_id) is not None


def _student_for_journey(journey_id: str | None) -> str | None:
    """This college's student id on *journey_id*, via the platform identity
    registry (the ``college`` slot); None when unknown."""
    if not journey_id:
        return None
    try:
        from education_system.platform.cross_system import identity_service
        live = identity_service.resolve_journey_id(str(journey_id))
        row = identity_service.get(live) if live else None
    except Exception:
        logger.debug("journey lookup failed for %s", journey_id, exc_info=True)
        return None
    return _clean((row or {}).get("college_student_id"))


def _resolve_student(payload: dict) -> str | None:
    """The sixth form student an event is about, or None."""
    sid = _clean(payload.get("sf_student_id"))
    if sid and _student_exists(sid):
        return sid
    uni = _clean(payload.get("university_student_id"))
    if uni:
        init_db()
        with _connect() as conn:
            row = conn.execute(
                "SELECT student_id FROM dest_university_confirmations "
                "WHERE university_student_id = ? ORDER BY confirmation_id LIMIT 1",
                (uni,)).fetchone()
        if row and _student_exists(row["student_id"]):
            return row["student_id"]
    sid = _student_for_journey(payload.get("journey_id"))
    return sid if sid and _student_exists(sid) else None


def _enrolment(student_id: str, university_student_id: str | None) -> dict | None:
    """The stored enrolment confirmation for this learner, if any."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM dest_university_confirmations WHERE event_type = 'enrolled' "
            "AND student_id = ? AND (? IS NULL OR university_student_id = ?) "
            "ORDER BY confirmation_id DESC LIMIT 1",
            (student_id, university_student_id, university_student_id)).fetchone()
    return dict(row) if row else None


def _already(event_key: str) -> bool:
    init_db()
    with _connect() as conn:
        return conn.execute(
            "SELECT 1 FROM dest_university_confirmations WHERE event_key = ?",
            (event_key,)).fetchone() is not None


def _store(row: dict[str, Any]) -> bool:
    """Insert the confirmation; False if this event_key is already held."""
    init_db()
    cols = list(row)
    with _connect() as conn:
        cur = conn.execute(
            f"INSERT OR IGNORE INTO dest_university_confirmations ({', '.join(cols)}) "  # nosec B608 - keys are this module's literals
            f"VALUES ({', '.join('?' for _ in cols)})",
            [row[c] for c in cols])
        conn.commit()
        return bool(cur.rowcount)


def _institution_for(payload: dict, student_id: str) -> str | None:
    """The university's name, from this college's own UCAS choice."""
    named = _clean(payload.get("institution") or payload.get("university"))
    if named:
        return named
    choice_id = _int(payload.get("sf_choice_id"))
    try:
        from education_system.systems.sixth_form.domain.progression.university import ucas
        if choice_id:
            choice = ucas.get_choice(choice_id)
            if choice is not None and _clean(choice.university):
                return _clean(choice.university)
    except Exception:
        logger.debug("UCAS choice %s unavailable", choice_id, exc_info=True)
    try:
        from education_system.systems.sixth_form.domain.progression.destinations import (
            destinations_links as _links,
        )
        prefill = _links.ucas_prefill(student_id) or {}
        return _clean(prefill.get("institution"))
    except Exception:
        return None


# ── monthly activity (sustained measure) ────────────────────────────


def _month(value: str | None) -> str | None:
    return value[:7] if value and len(value) >= 7 else None


def _record_he_months(student_id: str, start: str | None, end: str | None,
                      provider: str | None, note: str) -> int:
    """HE activity for every month start..end (YYYY-MM) that staff have not
    already recorded as HE. Returns the months added."""
    if not start or not end or end < start:
        return 0
    from education_system.systems.sixth_form.domain.progression.destinations import (
        sustained as _sustained,
    )
    have = {a["month"] for a in _sustained.list_activity(student_id)
            if a["activity_type"] == "Higher Education"}
    added, month, guard = 0, start, 0
    while month <= end and guard < 72:
        if month not in have:
            _sustained.record_activity(student_id, month, "Higher Education",
                                       provider=provider, source=SOURCE, notes=note)
            added += 1
        month = _sustained._month_add(month, 1)
        guard += 1
    return added


def _start_month(enrolment: dict | None, payload: dict) -> str | None:
    start = _iso_date((enrolment or {}).get("start_date")) or _iso_date(payload.get("start_date"))
    if start:
        return start[:7]
    year = _int((enrolment or {}).get("from_year")) or _int(payload.get("entry_year"))
    return f"{year:04d}-09" if year else None


# ── the LEAVING destination ─────────────────────────────────────────


def _append_note(existing: str | None, line: str) -> str:
    existing = (existing or "").strip()
    if line in existing:
        return existing
    return f"{existing}\n{line}".strip()


def _apply_leaving(student_id: str, *, institution: str | None, course: str | None,
                   start_date: str | None, confirmed_on: str | None,
                   university_student_id: str | None) -> tuple[str, bool]:
    """Apply an enrolment to the LEAVING record. Returns (what was done,
    conflict?)."""
    from education_system.systems.sixth_form.domain.progression.destinations import (
        destinations as _dest,
    )
    note = (f"Enrolment confirmed by {institution or 'the university'}"
            f"{' on ' + confirmed_on if confirmed_on else ''}"
            f"{' (university student ' + university_student_id + ')' if university_student_id else ''}.")
    current = _dest.get_record_for(student_id, "LEAVING")
    base = {"student_id": student_id, "checkpoint": "LEAVING"}
    if current is None or (current.destination_type == "Unknown"
                           and not (current.institution or current.employer)):
        payload = dict(base, destination_type="Higher Education",
                       institution=institution, course=course, start_date=start_date,
                       confirmed_via=SOURCE, confirmed_date=confirmed_on,
                       study_level=current.study_level if current else None,
                       notes=_append_note(current.notes if current else None, note))
        _dest.save_record(payload)
        return ("created destination" if current is None else "filled blank destination"), False

    # A destination someone entered by hand: never overwrite it.
    keep = {f: getattr(current, f) for f in (
        "destination_type", "institution", "course", "study_level", "employer", "role",
        "salary_band", "start_date", "confirmed_via", "confirmed_date", "notes")}
    same_place = (current.destination_type == "Higher Education"
                  and (not current.institution or not institution
                       or _norm(current.institution) == _norm(institution)))
    if same_place:
        keep["institution"] = keep["institution"] or institution
        keep["course"] = keep["course"] or course
        keep["start_date"] = keep["start_date"] or start_date
        if not keep["confirmed_via"]:
            keep["confirmed_via"] = SOURCE
            keep["confirmed_date"] = keep["confirmed_date"] or confirmed_on
        keep["notes"] = _append_note(keep["notes"], note)
        _dest.save_record(dict(base, **keep))
        return "confirmed existing destination", False
    review = (f"{note} This differs from the recorded destination "
              f"({current.destination_type}: {current.display_target()}) — please review.")
    keep["notes"] = _append_note(keep["notes"], review)
    _dest.save_record(dict(base, **keep))
    return "noted on differing destination", True


# ── handlers ────────────────────────────────────────────────────────


def apply_enrolled(payload: dict, *, bus_event_id: str | None = None) -> dict | None:
    """Apply a ``university.student.enrolled`` payload. Idempotent; returns
    the stored confirmation, or None for an unknown learner / repeat."""
    student_id = _resolve_student(payload)
    if not student_id:
        logger.info("University enrolment for unknown learner (journey %s) ignored",
                    payload.get("journey_id"))
        return None
    uni_sid = _clean(payload.get("university_student_id"))
    key = f"enrolled:{student_id}:{uni_sid or payload.get('sf_choice_id') or ''}"
    if _already(key):
        return None
    institution = _institution_for(payload, student_id)
    course = _clean(payload.get("course_name")) or _clean(payload.get("course_code"))
    start_date = _iso_date(payload.get("start_date"))
    confirmed_on = _iso_date(payload.get("enrolled_on")) or _dt.date.today().isoformat()
    applied, conflict = _apply_leaving(
        student_id, institution=institution, course=course, start_date=start_date,
        confirmed_on=confirmed_on, university_student_id=uni_sid)
    # The months from the course start to the confirmation count as HE.
    start_m, confirmed_m = _start_month(None, payload), confirmed_on[:7]
    months = (_record_he_months(student_id, start_m, confirmed_m, institution,
                                "Enrolment confirmed by the university")
              if start_m and start_m <= confirmed_m else 0)
    row = {
        "event_key": key, "event_type": "enrolled", "student_id": student_id,
        "journey_id": _clean(payload.get("journey_id")), "university_student_id": uni_sid,
        "institution": institution, "course": course,
        "course_code": _clean(payload.get("course_code")), "start_date": start_date,
        "from_year": _int(payload.get("entry_year")), "to_year": None,
        "event_date": confirmed_on, "reason_category": None, "outcome": "Enrolled",
        "applied": applied, "conflict": int(conflict), "months_recorded": months,
        "bus_event_id": bus_event_id,
    }
    _store(row)
    _backfill_months(student_id, row)
    logger.info("University enrolment applied to %s: %s", student_id, applied)
    return row


def _backfill_months(student_id: str, enrolment: dict[str, Any]) -> None:
    """A progression or withdrawal that arrived before the enrolment (the
    bus does not promise order) could not know when the course started, so
    recorded no months. Now that the start is known, record them."""
    from education_system.systems.sixth_form.domain.progression.destinations import (
        sustained as _sustained,
    )
    start = _start_month(enrolment, {})
    if not start:
        return
    with _connect() as conn:
        waiting = [dict(r) for r in conn.execute(
            "SELECT * FROM dest_university_confirmations WHERE student_id = ? "
            "AND event_type IN ('progressed', 'withdrawn') AND months_recorded = 0 "
            "AND (university_student_id IS NULL OR ? IS NULL OR university_student_id = ?)",
            (student_id, enrolment.get("university_student_id"),
             enrolment.get("university_student_id")))]
    for c in waiting:
        when = _iso_date(c["event_date"])
        if not when:
            continue
        if c["event_type"] == "withdrawn":
            end, note = _sustained._month_add(when[:7], -1), "Enrolled until withdrawal (university)"
        else:
            end, note = when[:7], f"Progressed to Year {c['to_year']} (university)"
        added = _record_he_months(student_id, start, end, enrolment.get("institution"), note)
        if added:
            with _connect() as conn:
                conn.execute(
                    "UPDATE dest_university_confirmations SET months_recorded = ?, "
                    "institution = COALESCE(institution, ?), course = COALESCE(course, ?), "
                    "start_date = COALESCE(start_date, ?) WHERE confirmation_id = ?",
                    (added, enrolment.get("institution"), enrolment.get("course"),
                     enrolment.get("start_date"), c["confirmation_id"]))
                conn.commit()


def apply_progressed(payload: dict, *, bus_event_id: str | None = None) -> dict | None:
    """Apply ``university.student.progressed``: "Sustained into Year N"."""
    student_id = _resolve_student(payload)
    if not student_id:
        logger.info("University progression for unknown learner (journey %s) ignored",
                    payload.get("journey_id"))
        return None
    uni_sid = _clean(payload.get("university_student_id"))
    from_year, to_year = _int(payload.get("from_year")), _int(payload.get("to_year"))
    if to_year is None and from_year is not None:
        to_year = from_year + 1
    key = f"progressed:{student_id}:{uni_sid or ''}:{from_year}:{to_year}"
    if _already(key):
        return None
    enrolment = _enrolment(student_id, uni_sid)
    recorded = _iso_date(payload.get("recorded_on")) or _dt.date.today().isoformat()
    institution = (enrolment or {}).get("institution") or _institution_for(payload, student_id)
    months = _record_he_months(student_id, _start_month(enrolment, payload), recorded[:7],
                               institution, f"Progressed to Year {to_year} (university)")
    row = {
        "event_key": key, "event_type": "progressed", "student_id": student_id,
        "journey_id": _clean(payload.get("journey_id")), "university_student_id": uni_sid,
        "institution": institution, "course": (enrolment or {}).get("course"),
        "course_code": (enrolment or {}).get("course_code"),
        "start_date": (enrolment or {}).get("start_date"),
        "from_year": from_year, "to_year": to_year, "event_date": recorded,
        "reason_category": None,
        "outcome": f"Sustained into Year {to_year}" if to_year else "Progressed",
        "applied": "sustained activity recorded", "conflict": 0, "months_recorded": months,
        "bus_event_id": bus_event_id,
    }
    _store(row)
    return row


def apply_withdrawn(payload: dict, *, bus_event_id: str | None = None) -> dict | None:
    """Apply ``university.student.withdrawn``: "Withdrew in Year N"."""
    student_id = _resolve_student(payload)
    if not student_id:
        logger.info("University withdrawal for unknown learner (journey %s) ignored",
                    payload.get("journey_id"))
        return None
    uni_sid = _clean(payload.get("university_student_id"))
    withdrawn_on = (_iso_date(payload.get("withdrawn_on"))
                    or _iso_date(payload.get("recorded_on")) or _dt.date.today().isoformat())
    key = f"withdrawn:{student_id}:{uni_sid or ''}:{withdrawn_on}"
    if _already(key):
        return None
    year = _int(payload.get("from_year"))
    enrolment = _enrolment(student_id, uni_sid)
    institution = (enrolment or {}).get("institution") or _institution_for(payload, student_id)
    from education_system.systems.sixth_form.domain.progression.destinations import (
        sustained as _sustained,
    )
    last_full = _sustained._month_add(withdrawn_on[:7], -1)
    months = _record_he_months(student_id, _start_month(enrolment, payload), last_full,
                               institution, "Enrolled until withdrawal (university)")
    category = _clean(payload.get("reason_category"))
    row = {
        "event_key": key, "event_type": "withdrawn", "student_id": student_id,
        "journey_id": _clean(payload.get("journey_id")), "university_student_id": uni_sid,
        "institution": institution, "course": (enrolment or {}).get("course"),
        "course_code": (enrolment or {}).get("course_code"),
        "start_date": (enrolment or {}).get("start_date"),
        "from_year": year, "to_year": None, "event_date": withdrawn_on,
        # Only a known category is kept; anything else is not stored.
        "reason_category": category if category in REASON_LABELS else "not_disclosed",
        "outcome": f"Withdrew in Year {year}" if year else "Withdrew",
        "applied": "withdrawal recorded", "conflict": 0, "months_recorded": months,
        "bus_event_id": bus_event_id,
    }
    _store(row)
    return row


def _handler(apply):
    def handle(envelope: dict) -> None:
        try:
            apply(_payload(envelope), bus_event_id=envelope.get("event_id"))
        except Exception:
            # A malformed payload or a validation refusal for one learner
            # must not wedge the bus; it is logged and the event acked.
            logger.exception("University feedback event %s could not be applied",
                             envelope.get("event_id"))
    return handle


handle_enrolled = _handler(apply_enrolled)
handle_progressed = _handler(apply_progressed)
handle_withdrawn = _handler(apply_withdrawn)

_registered = False


def register_consumers() -> None:
    """Idempotently subscribe the three handlers to the cross-system bus."""
    global _registered
    if _registered:
        return
    from education_system.platform.integrations.external import cross_system_bus
    for event, handler, suffix in (
            (EVENT_ENROLLED, handle_enrolled, "enrolled"),
            (EVENT_PROGRESSED, handle_progressed, "progressed"),
            (EVENT_WITHDRAWN, handle_withdrawn, "withdrawn")):
        cross_system_bus.subscribe(event, handler, handler_name=f"{HANDLER_PREFIX}.{suffix}")
    _registered = True


# ── reading ─────────────────────────────────────────────────────────


def confirmations_for(student_id: str) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM dest_university_confirmations WHERE student_id = ? "
            "ORDER BY COALESCE(event_date, received_at), confirmation_id", (student_id,))]


def latest_status(student_id: str) -> str | None:
    """The newest outcome the university reported ("Enrolled",
    "Sustained into Year 2", "Withdrew in Year 1"), or None."""
    rows = confirmations_for(student_id)
    return rows[-1]["outcome"] if rows else None


@dataclass
class CohortRow:
    student_id: str
    student_name: str
    destination_type: str
    destination: str
    recorded_via: str
    basis: str              # Confirmed by institution / Self-reported / Not recorded
    university_status: str
    conflict: bool

    def as_row(self) -> dict[str, Any]:
        return {"student_id": self.student_id, "student_name": self.student_name,
                "destination_type": self.destination_type, "destination": self.destination,
                "recorded_via": self.recorded_via, "basis": self.basis,
                "university_status": self.university_status,
                "conflict": "Review" if self.conflict else ""}


BASIS_CONFIRMED = "Confirmed by institution"
BASIS_SELF = "Self-reported"
BASIS_NONE = "Not recorded"


def cohort(year_left: int) -> list[CohortRow]:
    """The leavers of *year_left* with how their LEAVING destination is
    known: confirmed by the institution (a university enrolment event is
    held) or self-reported (any other source)."""
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    from education_system.systems.sixth_form.domain.progression.destinations import (
        destinations as _dest,
        sustained as _sustained,
    )
    ids = _sustained.leavers(year_left)
    names = {s.student_id: s.full_name for s in _students.list_students()}
    leaving = {r.student_id: r for r in _dest.list_records(checkpoint="LEAVING")}
    by_student: dict[str, list[dict]] = {}
    with _connect() as conn:
        for r in conn.execute("SELECT * FROM dest_university_confirmations "
                              "ORDER BY COALESCE(event_date, received_at), confirmation_id"):
            by_student.setdefault(r["student_id"], []).append(dict(r))
    out = []
    for sid in ids:
        rec = leaving.get(sid)
        confs = by_student.get(sid, [])
        enrolled = [c for c in confs if c["event_type"] == "enrolled"]
        conflict = any(c["conflict"] for c in enrolled)
        if rec is None:
            basis = BASIS_NONE
        elif enrolled and not conflict:
            basis = BASIS_CONFIRMED
        else:
            # Includes a hand-entered destination the university's report
            # contradicts: what is recorded is still the self-reported one.
            basis = BASIS_SELF
        out.append(CohortRow(
            student_id=sid, student_name=names.get(sid, "(unknown)"),
            destination_type=rec.destination_type if rec else "—",
            destination=rec.display_target() if rec else "—",
            recorded_via=(rec.confirmed_via or "—") if rec else "—",
            basis=basis,
            university_status=confs[-1]["outcome"] if confs else "—",
            conflict=conflict))
    return out


def cohort_summary(year_left: int) -> dict[str, int]:
    rows = cohort(year_left)
    counts = {BASIS_CONFIRMED: 0, BASIS_SELF: 0, BASIS_NONE: 0}
    for r in rows:
        counts[r.basis] += 1
    counts["Leavers"] = len(rows)
    counts["Needs review (differs from university)"] = sum(1 for r in rows if r.conflict)
    counts["Sustained (university reports progression)"] = sum(
        1 for r in rows if r.university_status.startswith("Sustained"))
    counts["Withdrew (university reports)"] = sum(
        1 for r in rows if r.university_status.startswith("Withdrew"))
    return counts


def list_confirmations(*, student_id: str | None = None,
                       event_type: str | None = None) -> list[dict[str, Any]]:
    init_db()
    clauses, args = [], []
    if student_id:
        clauses.append("c.student_id = ?")
        args.append(student_id)
    if event_type:
        clauses.append("c.event_type = ?")
        args.append(event_type)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT c.*, TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) "
            "AS student_name FROM dest_university_confirmations c "
            "LEFT JOIN students s ON s.student_id = c.student_id "
            f"{where} ORDER BY c.received_at DESC, c.confirmation_id DESC", args)]  # nosec B608 - fixed clauses
    for r in rows:
        r["reason"] = REASON_LABELS.get(r.get("reason_category") or "", "") \
            if r["event_type"] == "withdrawn" else ""
    return rows


__all__ = [
    "BASIS_CONFIRMED", "BASIS_NONE", "BASIS_SELF", "CohortRow", "EVENT_ENROLLED",
    "EVENT_PROGRESSED", "EVENT_WITHDRAWN", "REASON_LABELS", "SOURCE",
    "apply_enrolled", "apply_progressed", "apply_withdrawn", "cohort", "cohort_summary",
    "confirmations_for", "handle_enrolled", "handle_progressed", "handle_withdrawn",
    "init_db", "latest_status", "list_confirmations", "register_consumers",
]
