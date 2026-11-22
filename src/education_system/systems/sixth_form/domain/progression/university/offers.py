"""University-offer tracking for the Sixth Form System.

This module is a *focused view* over the existing ``ucas_choices`` data:
the offer state, terms, and final decision live on the UCAS choice
itself, but staff need a few additional offer-management fields that
don't sit naturally on the choice (reply deadline, scholarship,
accommodation, optional alternative-grade pathway). Those live in a
small companion table here keyed 1:1 to a choice.

**Except for choices at this platform's own university.** Those fields
are things an institution *issues*, and for the one institution that is
on this platform, it now issues them for real — see
``university...admissions.domain.ucas.offer_terms``. For those choices
this module reads the university's row and refuses to write its own, so
there is one answer to "what did they offer?" rather than a college's
hand-copy sitting next to the university's record. Everything for the
other four choices is unchanged: the college is the only party that knows
those terms, and it goes on entering them.

Operations:

* List offers (every UCAS choice that has actually had an offer).
* Filter by student / university / decision status / deadline window.
* Edit offer details for a choice (creates the companion row on
  demand).
* Set the final decision on the underlying choice (Firm / Insurance /
  Declined) — this is the workflow staff use during offer week.
* Per-student comparison: every offer side-by-side with predicted
  grades for the relevant subject.
* Structured conditions on an offer (``offer_conditions`` table — the
  platform's shape, ``platform/cross_system/offer_conditions``) and a
  met / not met / review check of the learner's *released* results
  against them (:func:`check_offer`). For a choice at this platform's own
  university the conditions are that university's, read-only here.

Cascade: deleting a UCAS choice (or its application, or the student)
removes the offer details row.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from education_system import paths
from education_system.platform.cross_system import offer_conditions as _oc

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_OFFERS_DB

# Decision statuses that count as "has an offer" for filtering.
OFFER_DECISION_STATUSES: tuple[str, ...] = (
    "Unconditional Offer", "Conditional Offer",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS offer_details (
    offer_id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    choice_id                 INTEGER NOT NULL UNIQUE,
    grade_requirement         TEXT,
    grade_alternative         TEXT,
    reply_deadline            TEXT,
    expiry_date               TEXT,
    scholarship               TEXT,
    accommodation_guaranteed  INTEGER NOT NULL DEFAULT 0,
    notes                     TEXT,
    created_at                TEXT DEFAULT (datetime('now')),
    updated_at                TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (choice_id) REFERENCES ucas_choices(choice_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_offers_choice   ON offer_details(choice_id);
CREATE INDEX IF NOT EXISTS idx_offers_deadline ON offer_details(reply_deadline);

-- What an external university's offer asks for, row by row, so the
-- learner's released results can be checked against it.
CREATE TABLE IF NOT EXISTS offer_conditions (
    condition_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    choice_id           INTEGER NOT NULL,
    position            INTEGER NOT NULL DEFAULT 0,
    kind                TEXT NOT NULL CHECK (kind IN (
                            'grade_profile', 'subject_grade', 'tariff_points',
                            'qualification_grade', 'gcse_requirement',
                            'other_text')),
    qualification_type  TEXT,
    subject             TEXT,
    min_grade           TEXT,
    min_points          INTEGER,
    count               INTEGER,
    text                TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (choice_id) REFERENCES ucas_choices(choice_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_offer_conditions_choice
    ON offer_conditions(choice_id, position);
"""

#: Structured condition kinds (the platform's).
CONDITION_KINDS: tuple[str, ...] = _oc.CONDITION_KINDS
_COND_FIELDS = ("kind", "qualification_type", "subject", "min_grade",
                "min_points", "count", "text")


@dataclass
class OfferDetails:
    offer_id: int
    choice_id: int
    grade_requirement: str | None
    grade_alternative: str | None
    reply_deadline: str | None
    expiry_date: str | None
    scholarship: str | None
    accommodation_guaranteed: bool
    notes: str | None
    created_at: str
    updated_at: str
    #: True when these terms were issued by this platform's university
    #: rather than entered here. Such a row is read-only — ``save_details``
    #: refuses it — and carries the officer who issued it.
    issued_by_university: bool = False
    issued_by: str | None = None
    #: Structured conditions, in the platform's shape, in order.
    conditions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_editable_here(self) -> bool:
        """Whether the sixth form may edit these terms."""
        return not self.issued_by_university


@dataclass
class OfferRow:
    """A UCAS choice joined to its student, application, and (optional)
    offer details — the canonical "one row per offer" record used by
    the directory and per-student comparison views."""
    # From ucas_choices
    choice_id: int
    application_id: int
    choice_order: int
    university: str
    course_code: str | None
    course_name: str
    entry_year: int | None
    decision_status: str
    offer_terms: str | None
    final_decision: str | None
    # From ucas_applications
    cycle_year: int
    application_status: str
    # From students
    student_id: str
    student_name: str
    # From predicted_grades
    predicted_grade: str | None
    # From offer_details (optional — None if no companion row yet)
    details: OfferDetails | None


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    # FKs target ucas_choices which targets ucas_applications/students.
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    _ucas.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Offers schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_details(r: sqlite3.Row) -> OfferDetails:
    return OfferDetails(
        offer_id=r["offer_id"], choice_id=r["choice_id"],
        grade_requirement=r["grade_requirement"],
        grade_alternative=r["grade_alternative"],
        reply_deadline=r["reply_deadline"],
        expiry_date=r["expiry_date"],
        scholarship=r["scholarship"],
        accommodation_guaranteed=bool(r["accommodation_guaranteed"]),
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid offer-detail input."""


class UniversityIssuedError(ValidationError):
    """Raised when the sixth form tries to author terms that the
    university named on the choice issues for itself.

    A subclass of :class:`ValidationError` so existing callers still catch
    it and show the message, and distinct so a caller that wants to hide
    an edit button rather than pop an error can tell the two apart.
    """


def _validate_date(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["grade_requirement"] = (data.get("grade_requirement") or "").strip() or None
    out["grade_alternative"] = (data.get("grade_alternative") or "").strip() or None
    out["reply_deadline"] = _validate_date(
        data.get("reply_deadline"), "Reply deadline")
    out["expiry_date"] = _validate_date(
        data.get("expiry_date"), "Expiry date")
    out["scholarship"] = (data.get("scholarship") or "").strip() or None
    accom = data.get("accommodation_guaranteed")
    if isinstance(accom, str):
        accom = accom.strip().lower() in ("1", "true", "yes", "y", "on")
    out["accommodation_guaranteed"] = 1 if bool(accom) else 0
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


# ── Terms issued by this platform's university ─────────────────────

def _university_terms(choice_ids: list[int]) -> dict[int, OfferDetails]:
    """``{choice_id: OfferDetails}`` for the terms our university issued.

    Lazily imported and guarded, like every other reach across this
    boundary: a sixth form running standalone gets an empty mapping and
    keeps showing whatever it entered itself.
    """
    if not choice_ids:
        return {}
    try:
        from education_system.platform.cross_system.adapters import route_support
        issued = route_support.adapter_for("university").offer_terms_for_choices(
            list(choice_ids))
    except Exception:
        logger.debug("University offer terms unavailable", exc_info=True)
        return {}
    return {
        cid: OfferDetails(
            offer_id=t.get("terms_id"),
            choice_id=cid,
            grade_requirement=t.get("grade_requirement"),
            grade_alternative=t.get("grade_alternative"),
            reply_deadline=t.get("reply_deadline"),
            expiry_date=t.get("expiry_date"),
            scholarship=t.get("scholarship"),
            accommodation_guaranteed=t.get("accommodation_guaranteed"),
            notes=t.get("notes"),
            created_at=t.get("issued_at"),
            updated_at=t.get("updated_at"),
            issued_by_university=True,
            issued_by=t.get("issued_by"),
            conditions=list(t.get("conditions") or []),
        )
        for cid, t in issued.items()
    }


def is_university_issued(university: str | None) -> bool:
    """Are a choice's offer terms that institution's to issue rather than
    ours to enter?

    True only for the one university that runs on this platform: it is the
    only institution here that can publish its own terms. A UI asks this
    to show the fields read-only instead of prompting for seven answers
    and then having the save refused.
    """
    try:
        from education_system.systems.sixth_form.domain.progression import (
            university_handover,
        )
        return university_handover.is_home_university(university)
    except Exception:
        logger.debug("Could not resolve the home university", exc_info=True)
        return False


#: Internal alias — the same question, asked from inside this module.
_is_ours = is_university_issued


# ── Details CRUD (upsert keyed on choice_id) ───────────────────────

def get_details_for_choice(choice_id: int) -> OfferDetails | None:
    """The terms on a choice — ours if we entered them, the university's
    if it issued them."""
    init_db()
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    choice = _ucas.get_choice(choice_id)
    if choice is not None and _is_ours(choice.university):
        return _university_terms([choice_id]).get(choice_id)
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM offer_details WHERE choice_id = ?", (choice_id,),
        ).fetchone()
        if not r:
            return None
        out = _row_details(r)
        out.conditions = _load_conditions(conn, [choice_id]).get(choice_id, [])
        return out


def save_details(choice_id: int, data: dict[str, Any]) -> OfferDetails:
    """Upsert offer details for a UCAS choice.

    Refused for a choice at this platform's own university: those terms
    are that university's to issue, through ``record_decision``.
    """
    init_db()
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    choice = _ucas.get_choice(choice_id)
    if choice is None:
        raise ValidationError(f"No UCAS choice with id {choice_id}")
    if _is_ours(choice.university):
        raise UniversityIssuedError(
            f"The terms of an offer from {choice.university} are issued by "
            "its admissions team. They appear here once published; they "
            "cannot be entered here."
        )
    try:
        p = _validate_payload(data)
        conditions = None
        if data.get("conditions") is not None:
            try:
                conditions = _oc.validate_conditions(data.get("conditions"))
            except ValueError as e:
                raise ValidationError(str(e)) from None
            _validate_against_scales(conditions)
    except ValidationError as e:
        logger.warning("save_details validation failed for choice #%d: %s",
                       choice_id, e)
        raise

    with _connect() as conn:
        conn.execute(
            """INSERT INTO offer_details
                   (choice_id, grade_requirement, grade_alternative,
                    reply_deadline, expiry_date, scholarship,
                    accommodation_guaranteed, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))
               ON CONFLICT(choice_id) DO UPDATE SET
                   grade_requirement = excluded.grade_requirement,
                   grade_alternative = excluded.grade_alternative,
                   reply_deadline    = excluded.reply_deadline,
                   expiry_date       = excluded.expiry_date,
                   scholarship       = excluded.scholarship,
                   accommodation_guaranteed = excluded.accommodation_guaranteed,
                   notes             = excluded.notes,
                   updated_at        = datetime('now')""",
            (choice_id, p["grade_requirement"], p["grade_alternative"],
             p["reply_deadline"], p["expiry_date"], p["scholarship"],
             p["accommodation_guaranteed"], p["notes"]),
        )
        if conditions is not None:
            _replace_conditions(conn, choice_id, conditions)
        conn.commit()
    out = get_details_for_choice(choice_id)
    assert out is not None
    logger.info(
        "Saved offer details for choice #%d "
        "(deadline=%s, scholarship=%s, accom=%s)",
        choice_id, out.reply_deadline, out.scholarship,
        out.accommodation_guaranteed,
    )
    return out


def delete_details(choice_id: int) -> bool:
    """Clear the terms we entered for a choice.

    Refused for a choice at this platform's own university for the same
    reason ``save_details`` is: those terms are that university's record,
    and there is nothing of ours here to clear. Withdrawing them is done
    on their side.
    """
    init_db()
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    choice = _ucas.get_choice(choice_id)
    if choice is not None and _is_ours(choice.university):
        raise UniversityIssuedError(
            f"The terms of an offer from {choice.university} are held by "
            "its admissions team and cannot be cleared here."
        )
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM offer_details WHERE choice_id = ?", (choice_id,),
        )
        conn.execute(
            "DELETE FROM offer_conditions WHERE choice_id = ?", (choice_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted offer details for choice #%d", choice_id)
            return True
        return False


# ── Final-decision shortcut ───────────────────────────────────────

def set_final_decision(choice_id: int, final: str | None) -> None:
    """Convenience: update the UCAS choice's ``final_decision`` field
    without forcing the caller to import the ucas module. Enforces the
    one-Firm / one-Insurance rule via the UCAS data layer."""
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    _ucas.update_choice(choice_id, {"final_decision": (final or "")})


# ── Joined directory & filters ────────────────────────────────────

def _predicted_grades_map() -> dict[tuple[str, str], str]:
    """Return ``{(student_id, subject): grade}`` from the predicted-grades
    module if it's available; otherwise empty."""
    try:
        from education_system.systems.sixth_form.domain.assessment.predicted_grades import predicted_grades as _pg
        return {(p.student_id, p.subject): p.grade
                for p in _pg.list_predictions()}
    except Exception:
        logger.exception("Could not load predicted grades")
        return {}


def _subject_for_course(course_name: str) -> str:
    """Heuristic: take the first word of the course name as the subject
    key. UCAS course names are messy but most "Mathematics", "Physics
    with Astrophysics", "Computer Science" etc. start with the subject."""
    if not course_name:
        return ""
    first = course_name.split()[0]
    # Normalise a few common variants
    return first.rstrip(",.")


def list_offer_rows(
    *,
    student_id: str | None = None,
    university_like: str | None = None,
    decision_status: str | None = None,
    final_decision: str | None = None,
    offers_only: bool = False,
    deadline_before: str | None = None,
) -> list[OfferRow]:
    """Joined view of UCAS choices + applications + students + offer
    details. ``offers_only=True`` restricts to choices with a decision
    status that indicates an offer (Unconditional / Conditional).
    """
    init_db()
    from education_system.systems.sixth_form.domain.progression.university import ucas
    from education_system.systems.sixth_form.domain.learners.students import students as _ucas
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("a.student_id = ?")
        args.append(student_id.strip())
    if university_like:
        clauses.append("c.university LIKE ?")
        args.append(f"%{university_like.strip()}%")
    if decision_status:
        clauses.append("c.decision_status = ?")
        args.append(decision_status)
    if final_decision:
        clauses.append("c.final_decision = ?")
        args.append(final_decision)
    if offers_only:
        placeholders = ",".join("?" * len(OFFER_DECISION_STATUSES))
        clauses.append(f"c.decision_status IN ({placeholders})")
        args.extend(OFFER_DECISION_STATUSES)
    # The deadline filter is applied after the join rather than inside it:
    # for a choice at our own university the reply deadline lives in that
    # university's table, so an ``od.reply_deadline`` clause would filter
    # out exactly the rows that have one.
    deadline_before_s = (_validate_date(deadline_before, "Deadline before")
                         if deadline_before else None)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT "
        "  c.choice_id, c.application_id, c.choice_order, "
        "  c.university, c.course_code, c.course_name, c.entry_year, "
        "  c.decision_status, c.offer_terms, c.final_decision, "
        "  a.cycle_year, a.status AS app_status, a.student_id, "
        "  od.* "
        "FROM ucas_choices c "
        "JOIN ucas_applications a ON a.application_id = c.application_id "
        "LEFT JOIN offer_details od ON od.choice_id = c.choice_id "
        f"{where} "
        "ORDER BY a.student_id, c.choice_order"
    )
    with _connect() as conn:
        rows = conn.execute(sql, args).fetchall()

    name_index = {s.student_id: s.full_name for s in _students.list_students()}
    grade_map = _predicted_grades_map()

    # Terms our own university issued, fetched once for the whole page
    # rather than per row. Only choices that name us can have any, so only
    # those ids are asked for. "Is this us?" is resolved per distinct
    # institution rather than per row — a cohort's five choices each name
    # a handful of universities between them, and the answer needs the
    # university's own settings to work it out.
    ours_by_name = {name: _is_ours(name)
                    for name in {r["university"] for r in rows}}
    ours = {r["choice_id"] for r in rows if ours_by_name.get(r["university"])}
    issued = _university_terms(sorted(ours))
    local_conditions = _load_conditions(
        conn=None, choice_ids=[r["choice_id"] for r in rows
                               if r["choice_id"] not in ours])

    out: list[OfferRow] = []
    for r in rows:
        details = None
        if r["choice_id"] in ours:
            # The university's record wins outright for its own choices:
            # any local row is a stale hand-copy from before it owned them.
            details = issued.get(r["choice_id"])
        elif r["offer_id"] is not None:
            details = OfferDetails(
                offer_id=r["offer_id"], choice_id=r["choice_id"],
                grade_requirement=r["grade_requirement"],
                grade_alternative=r["grade_alternative"],
                reply_deadline=r["reply_deadline"],
                expiry_date=r["expiry_date"],
                scholarship=r["scholarship"],
                accommodation_guaranteed=bool(r["accommodation_guaranteed"]),
                notes=r["notes"],
                created_at=r["created_at"], updated_at=r["updated_at"],
                conditions=local_conditions.get(r["choice_id"], []),
            )
        subj_key = _subject_for_course(r["course_name"])
        pred = grade_map.get((r["student_id"], subj_key))
        out.append(OfferRow(
            choice_id=r["choice_id"],
            application_id=r["application_id"],
            choice_order=r["choice_order"],
            university=r["university"],
            course_code=r["course_code"],
            course_name=r["course_name"],
            entry_year=r["entry_year"],
            decision_status=r["decision_status"],
            offer_terms=r["offer_terms"],
            final_decision=r["final_decision"],
            cycle_year=r["cycle_year"],
            application_status=r["app_status"],
            student_id=r["student_id"],
            student_name=name_index.get(r["student_id"], "(unknown)"),
            predicted_grade=pred,
            details=details,
        ))
    if deadline_before_s is not None:
        out = [r for r in out
               if r.details is not None
               and r.details.reply_deadline is not None
               and r.details.reply_deadline <= deadline_before_s]
    return out


def get_offer_row(choice_id: int) -> OfferRow | None:
    """Single joined row for one UCAS choice."""
    for r in list_offer_rows():
        if r.choice_id == choice_id:
            return r
    return None


def offers_for_student(student_id: str) -> list[OfferRow]:
    return list_offer_rows(student_id=student_id)


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class OfferSummary:
    total_choices: int
    total_offers: int
    by_decision: dict[str, int]
    by_final: dict[str, int]
    with_scholarship: int
    with_accommodation: int
    upcoming_deadlines: int  # within 30 days


def summary(*, deadline_window_days: int = 30) -> OfferSummary:
    """Counts across all offer rows. ``upcoming_deadlines`` counts
    rows whose reply_deadline is within ``deadline_window_days`` of
    today and hasn't been actioned yet (final_decision is null)."""
    import datetime as _dt
    rows = list_offer_rows()
    today = _dt.date.today()
    cutoff = today + _dt.timedelta(days=deadline_window_days)
    by_decision: dict[str, int] = {}
    by_final: dict[str, int] = {}
    n_offers = 0
    n_scholarship = 0
    n_accom = 0
    upcoming = 0
    for r in rows:
        by_decision[r.decision_status] = by_decision.get(
            r.decision_status, 0) + 1
        if r.decision_status in OFFER_DECISION_STATUSES:
            n_offers += 1
        key = r.final_decision or "(none)"
        by_final[key] = by_final.get(key, 0) + 1
        if r.details and r.details.scholarship:
            n_scholarship += 1
        if r.details and r.details.accommodation_guaranteed:
            n_accom += 1
        if (r.details and r.details.reply_deadline
                and r.final_decision is None):
            try:
                d = _dt.date.fromisoformat(r.details.reply_deadline)
            except ValueError:
                continue
            if today <= d <= cutoff:
                upcoming += 1
    return OfferSummary(
        total_choices=len(rows), total_offers=n_offers,
        by_decision=by_decision, by_final=by_final,
        with_scholarship=n_scholarship,
        with_accommodation=n_accom,
        upcoming_deadlines=upcoming,
    )


# ── Structured conditions ─────────────────────────────────────────

def _load_conditions(conn: sqlite3.Connection | None,
                     choice_ids) -> dict[int, list[dict[str, Any]]]:
    """``{choice_id: [condition, ...]}`` for the choices we entered."""
    ids = sorted({int(i) for i in choice_ids})
    out: dict[int, list[dict[str, Any]]] = {}
    if not ids:
        return out
    own = conn is None
    if own:
        init_db()
        conn = _connect()
    try:
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            marks = ",".join("?" * len(chunk))
            # db-audit: ignore[DBW001] - join of placeholders
            rows = conn.execute(
                f"SELECT * FROM offer_conditions WHERE choice_id IN ({marks}) "  # nosec B608
                "ORDER BY choice_id, position, condition_id", chunk).fetchall()
            for r in rows:
                out.setdefault(r["choice_id"], []).append(
                    {f: r[f] for f in _COND_FIELDS})
    finally:
        if own:
            conn.close()
    return out


def _replace_conditions(conn: sqlite3.Connection, choice_id: int,
                        rows: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM offer_conditions WHERE choice_id = ?",
                 (choice_id,))
    for pos, c in enumerate(rows):
        conn.execute(
            """INSERT INTO offer_conditions
                   (choice_id, position, kind, qualification_type, subject,
                    min_grade, min_points, count, text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (choice_id, pos, c["kind"], c.get("qualification_type"),
             c.get("subject"), c.get("min_grade"), c.get("min_points"),
             c.get("count"), c.get("text")))


def _validate_against_scales(rows: list[dict[str, Any]]) -> None:
    """Grades on a qualification the college teaches must be on its scale."""
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        grade_scales as _gs,
    )
    for i, c in enumerate(rows, 1):
        if c["kind"] not in ("subject_grade", "qualification_grade"):
            continue
        qtype = c.get("qualification_type")
        if qtype and _gs.canonical_type(qtype):
            try:
                _gs.validate_grade(c["min_grade"], qtype)
            except ValueError as e:
                raise ValidationError(f"Condition {i}: {e}") from None


def set_conditions(choice_id: int, rows) -> list[dict[str, Any]]:
    """Replace the structured conditions on an external university's offer.

    Refused for a choice at this platform's own university — those are
    that university's conditions, published with its offer.
    """
    init_db()
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    choice = _ucas.get_choice(choice_id)
    if choice is None:
        raise ValidationError(f"No UCAS choice with id {choice_id}")
    if _is_ours(choice.university):
        raise UniversityIssuedError(
            f"The conditions of an offer from {choice.university} are set by "
            "its admissions team and cannot be entered here.")
    try:
        clean = _oc.validate_conditions(rows)
    except ValueError as e:
        raise ValidationError(str(e)) from None
    _validate_against_scales(clean)
    with _connect() as conn:
        # The conditions hang off the offer, so make sure there is one to
        # show them on (an otherwise-empty details row).
        conn.execute("INSERT OR IGNORE INTO offer_details (choice_id) VALUES (?)",
                     (choice_id,))
        _replace_conditions(conn, choice_id, clean)
        conn.commit()
    logger.info("Saved %d offer condition(s) for choice #%d",
                len(clean), choice_id)
    return clean


def conditions_from_text(text: str | None) -> list[dict[str, Any]]:
    """Read a typed grade requirement as structured conditions."""
    return _oc.conditions_from_text(text)


def describe_condition(c: dict[str, Any]) -> str:
    return _oc.describe(c)


# ── Met / not met against released results ────────────────────────

@dataclass
class OfferCheck:
    choice_id: int
    verdict: str            # Met / Missed / Review / Pending
    reason: str
    conditions: list[dict[str, Any]]
    from_text: bool         # conditions read from the typed requirement

    @property
    def label(self) -> str:
        return {_oc.MET: "Met", _oc.MISSED: "Not met",
                _oc.REVIEW: "Review", _oc.PENDING: "Awaiting results"
                }.get(self.verdict, self.verdict)


def released_results_for(student_id: str) -> list[dict[str, Any]]:
    """The learner's released exam results in the platform's result shape.

    Embargoed results are left out — this check is shown to staff advising
    the learner, and before release it would give the results away.
    """
    from education_system.systems.sixth_form.domain.assessment.exam_results import (
        exam_results as _results,
    )
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        learning_aims as _aims,
    )
    out: list[dict[str, Any]] = []
    for row in _results.results_for_student(student_id, released_only=True):
        qtype = None
        try:
            qtype = _aims.qualification_type_for(student_id, row.subject)
        except Exception:
            logger.debug("No qualification type for %s / %s", student_id,
                         row.subject, exc_info=True)
        out.append({"subject": row.subject, "grade": row.result.grade,
                    "qualification_type": qtype, "released": True,
                    "release_at": None, "season": row.season,
                    "year": row.year})
    return out


def check_offer(row: OfferRow | int, *,
                results: list[dict[str, Any]] | None = None) -> OfferCheck | None:
    """Met / not met / review for one offer against released results.

    ``None`` for a choice with no offer. Uses the structured conditions
    when there are any, otherwise reads the typed requirement.
    """
    if isinstance(row, int):
        row = get_offer_row(row)
        if row is None:
            return None
    if row.decision_status not in OFFER_DECISION_STATUSES:
        return None
    d = row.details
    if row.decision_status == "Unconditional Offer":
        return OfferCheck(row.choice_id, _oc.MET, "Unconditional offer.", [], False)
    conditions = list(d.conditions) if d and d.conditions else []
    from_text = False
    if not conditions:
        text = (d.grade_requirement if d and d.grade_requirement
                else row.offer_terms)
        conditions = _oc.conditions_from_text(text)
        from_text = True
    if not conditions:
        return OfferCheck(row.choice_id, _oc.REVIEW,
                          "No condition recorded on this offer.", [], from_text)
    if results is None:
        try:
            results = released_results_for(row.student_id)
        except Exception as e:
            logger.exception("Could not read results for %s", row.student_id)
            return OfferCheck(row.choice_id, _oc.PENDING,
                              f"Results could not be read: {e}", conditions,
                              from_text)
    ev = _oc.evaluate(conditions, results)
    return OfferCheck(row.choice_id, ev.verdict, ev.reason, conditions, from_text)


def checks_for_student(student_id: str) -> dict[int, OfferCheck]:
    """``{choice_id: OfferCheck}`` for every offer the learner holds."""
    rows = offers_for_student(student_id)
    if not rows:
        return {}
    try:
        results = released_results_for(student_id)
    except Exception:
        logger.exception("Could not read results for %s", student_id)
        results = None
    out: dict[int, OfferCheck] = {}
    for r in rows:
        chk = check_offer(r, results=results)
        if chk is not None:
            out[r.choice_id] = chk
    return out
