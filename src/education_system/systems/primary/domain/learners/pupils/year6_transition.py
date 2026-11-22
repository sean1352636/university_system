"""Year 6 → Year 7 transition: the primary school's side.

For each Year 6 cohort (one academic year) the school records:

* **destination** — the platform's Secondary School System, or an external
  secondary school by name;
* **application / offer** against the national timetable: applications by
  31 October of Year 6, national offer day on 1 March (or the next working
  day), then the parent accepts or declines;
* **parental consent** per sensitive handover field (``CONSENT_FIELDS``);
* the **transition report** (strengths, interests, worries, friendships,
  keep-apart, all about me, enhanced transition...), which crosses to the
  secondary as the routine ``transition_report`` handover field;
* **visits** to the secondary school (open evenings, induction days...);
* the DSL's **safeguarding-file transfer record** — when the file went, to
  whom, by what means. A pointer only: the file itself goes DSL-to-DSL and
  never through this module;
* a derived **checklist**.

Platform destination
--------------------
The secondary is reached only through the platform
(``platform.cross_system.transitions`` / ``route_support``), in stages, so
the pupil sits in the secondary's queue through the summer term::

    set_destination(platform)  → start_transition      (expected)
    record_application         → record_application    (applied)
    record_offer               → applicant + offer_place (offered)
    record_acceptance          → accept_place          (accepted)
    approve_handover           → approve_handover      (handover_approved)

On the last day, ``secondary_transfer.move_to_secondary_school`` resumes the
same open transition (``route_support.transfer`` reuses it) to admit and
complete. The secondary's acknowledgement, rejection or admission is read
back from the transition row and its events — never from the secondary
system itself.

Re-approving the handover after edits is **not possible**: the platform
workflow only moves forward, and ``approve_handover`` is a step, so a second
call on a transition already at ``handover_approved`` is refused. Edit the
report and consent before approving; later changes stay in the primary
record and must be passed on directly (the GUI says so).

External destinations are recorded here only; nothing crosses the platform.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.primary.domain.learners.pupils import pupils as pupils_data
from education_system.systems.primary.infrastructure import year6_transition_store as store
from education_system.systems.primary.domain.learners.pupils.pupils import (
    Pupil,
    ValidationError,
)

logger = logging.getLogger(__name__)

SOURCE = "primary"
DESTINATION = "secondary"
SECONDARY_ENTRY_YEAR = "7"
PLATFORM_DESTINATION_NAME = "Secondary School System"

#: The sensitive handover fields a parent may consent to share. Kept equal
#: to ``secondary_transfer.CONSENT_FIELDS`` (that module re-exports it).
CONSENT_FIELDS: tuple[str, ...] = ("send_provision", "support_indicators",
                                   "current_interventions", "medical_requirements")
CONSENT_LABELS: dict[str, str] = {
    "send_provision": "SEND provision, EHCP and access arrangements",
    "support_indicators": "Pupil Premium / FSM / LAC / EAL indicators",
    "current_interventions": "Interventions in progress",
    "medical_requirements": "Medical needs and care plans",
}
CONSENT_METHODS: tuple[str, ...] = (
    "Signed form", "Email", "Parent portal", "In person", "Telephone (noted)")

DESTINATION_PLATFORM = "platform"
DESTINATION_EXTERNAL = "external"
DESTINATION_TYPES: dict[str, str] = {
    DESTINATION_PLATFORM: "Secondary School System (this platform)",
    DESTINATION_EXTERNAL: "Another secondary school",
}

APPLICATION_STATUSES: dict[str, str] = {
    "not_applied": "Not applied yet",
    "applied": "Applied",
    "offered": "Place offered",
    "accepted": "Place accepted",
    "declined": "Offer declined",
    "moved": "Moved to secondary",
}

VISIT_TYPES: tuple[str, ...] = (
    "Open evening", "Induction day", "Enhanced transition visit",
    "Secondary staff visit to primary", "Taster lesson", "Other")

SAFEGUARDING_METHODS: tuple[str, ...] = (
    "Secure electronic transfer (CPOMS / MyConcern)", "Hand delivered",
    "Recorded delivery", "Other secure method")

#: Platform transition checklist items the primary school may tick.
PRIMARY_CHECKLIST_OWNERS = frozenset({"source", "both"})

#: How the transition row is shown back to primary staff.
SECONDARY_STATUS_LABELS: dict[str, str] = {
    "expected": "In the secondary's queue (expected)",
    "applied": "Application on file",
    "offered": "Place offered",
    "accepted": "Place accepted",
    "handover_approved": "Handover sent",
    "acknowledged": "Secondary acknowledged the handover",
    "admitted": "Admitted by the secondary",
    "completed": "Admitted — transfer complete",
    "rejected": "Rejected by the secondary",
    "cancelled": "Transition cancelled",
}

_STEP_ORDER = ("expected", "applied", "offered", "accepted", "handover_approved",
               "admitted", "completed")



# ── Data classes ────────────────────────────────────────────────────

@dataclass
class Year6Record:
    pupil_id: str
    academic_year: str
    destination_type: str = ""
    destination_school: str = ""
    application_status: str = "not_applied"
    applied_on: str | None = None
    offered_on: str | None = None
    offered_school: str | None = None
    accepted_on: str | None = None
    declined_on: str | None = None
    declined_reason: str | None = None
    transition_id: str | None = None
    consent: dict[str, bool] = field(default_factory=dict)
    consent_given_by: str | None = None
    consent_on: str | None = None
    consent_method: str | None = None
    handover_approved_on: str | None = None
    handover_approved_by: str | None = None
    secondary_status: str | None = None
    secondary_note: str | None = None
    secondary_status_at: str | None = None
    moved_on: str | None = None
    secondary_pupil_id: str | None = None
    notes: str | None = None

    @property
    def is_platform(self) -> bool:
        return self.destination_type == DESTINATION_PLATFORM

    @property
    def consented_fields(self) -> set[str]:
        return {k for k, v in self.consent.items() if v and k in CONSENT_FIELDS}

    @property
    def consent_recorded(self) -> bool:
        return bool(self.consent_on) and all(k in self.consent for k in CONSENT_FIELDS)

    @property
    def destination_label(self) -> str:
        if not self.destination_type:
            return ""
        return self.destination_school or DESTINATION_TYPES.get(self.destination_type, "")


@dataclass
class TransitionReport:
    pupil_id: str
    academic_year: str
    strengths: str = ""
    interests: str = ""
    learning_style: str = ""
    worries: str = ""
    friendships: list[str] = field(default_factory=list)
    keep_apart: list[str] = field(default_factory=list)
    all_about_me: str = ""
    teacher_comments: str = ""
    enhanced_transition: bool = False
    enhanced_reason: str = ""
    written_by: str = ""
    written_on: str | None = None


@dataclass
class Visit:
    visit_id: int
    pupil_id: str
    academic_year: str
    visit_date: str
    visit_type: str
    school_name: str | None
    attended: bool
    notes: str | None


@dataclass
class SafeguardingTransfer:
    transfer_id: int
    pupil_id: str
    academic_year: str
    has_file: bool
    sent_on: str | None
    sent_to_name: str | None
    sent_to_role: str | None
    sent_to_school: str | None
    method: str | None
    receipt_confirmed_on: str | None
    recorded_by: str | None
    notes: str | None

    @property
    def reference(self) -> str:
        """The opaque pointer that may cross in ``safeguarding_reference``."""
        return f"primary-dsl-transfer:{self.transfer_id}"


@dataclass
class ChecklistEntry:
    key: str
    label: str
    done: bool
    detail: str = ""


@dataclass
class CohortRow:
    pupil: Pupil
    record: Year6Record
    report_written: bool = False
    visits_attended: int = 0
    checklist_done: int = 0
    checklist_total: int = 0


@dataclass(frozen=True)
class Timetable:
    academic_year: str
    applications_open: str
    application_deadline: str
    offer_day: str
    reply_by: str
    induction_from: str


# ── DB plumbing ─────────────────────────────────────────────────────

_DB_READY = False


def _connect() -> Any:
    return store.connect(pupils_data.DB_PATH)


def init_db() -> None:
    """The Year 6 tables, in the primary pupils database (after ``pupils``,
    which they reference)."""
    global _DB_READY
    if _DB_READY:
        return
    pupils_data.init_db()
    try:
        store.init_schema(pupils_data.DB_PATH)
    except store.Error:
        logger.exception("Failed to initialise Year 6 transition tables")
        raise
    _DB_READY = True


# ── Dates and the national timetable ────────────────────────────────

def _parse_date(value: Any, label: str, *, required: bool = False) -> str | None:
    text = str(value or "").strip()
    if not text:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    try:
        return _dt.date.fromisoformat(text[:10]).isoformat()
    except ValueError as exc:
        raise ValidationError(f"{label} must be a date (YYYY-MM-DD)") from exc


def _start_year(academic_year: str) -> int:
    text = str(academic_year or "").strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    raise ValidationError(f"Academic year must look like 2026-27, got {academic_year!r}")


def normalise_year(academic_year: str | None) -> str:
    """``"2026-27"`` from "2026-27", "2026/27" or "2026-2027"."""
    if not academic_year or not str(academic_year).strip():
        return current_academic_year()
    y = _start_year(str(academic_year))
    return f"{y}-{str(y + 1)[-2:]}"


def _slash_year(academic_year: str) -> str:
    """The "2026/27" spelling SEND and Pupil Premium store."""
    y = _start_year(academic_year)
    return f"{y}/{str(y + 1)[-2:]}"


def current_academic_year(today: _dt.date | None = None) -> str:
    """The school's current year (Academic Year screen), else by date."""
    try:
        from education_system.systems.primary.domain.academics.academic_year import (
            academic_year as ay,
        )
        cur = ay.current_year()
        if cur is not None and cur.name[:4].isdigit():
            y = int(cur.name[:4])
            return f"{y}-{str(y + 1)[-2:]}"
    except Exception:  # noqa: BLE001 - the date rule below is always right enough
        logger.debug("current academic year lookup failed", exc_info=True)
    today = today or _dt.date.today()
    y = today.year if today.month >= 9 else today.year - 1
    return f"{y}-{str(y + 1)[-2:]}"


def year_dates(academic_year: str) -> tuple[str, str]:
    """First and last day of an academic year (Academic Year screen, else
    1 September – 31 August)."""
    y = _start_year(academic_year)
    try:
        from education_system.systems.primary.domain.academics.academic_year import (
            academic_year as ay,
        )
        for cand in ay.list_years():
            if cand.name[:4] == str(y):
                return cand.start_date, cand.end_date
    except Exception:  # noqa: BLE001
        logger.debug("academic year dates lookup failed", exc_info=True)
    return f"{y}-09-01", f"{y + 1}-08-31"


def _next_working_day(d: _dt.date) -> _dt.date:
    while d.weekday() >= 5:
        d += _dt.timedelta(days=1)
    return d


def national_timetable(academic_year: str) -> Timetable:
    """The secondary admissions round for children in Year 6 that year.

    Applications open in September and close on 31 October; national offer
    day is 1 March (moved to the next working day at a weekend). Councils
    usually ask parents to reply within about two weeks of offer day.
    """
    y = _start_year(academic_year)
    offer = _next_working_day(_dt.date(y + 1, 3, 1))
    return Timetable(
        academic_year=normalise_year(academic_year),
        applications_open=_dt.date(y, 9, 1).isoformat(),
        application_deadline=_dt.date(y, 10, 31).isoformat(),
        offer_day=offer.isoformat(),
        reply_by=(offer + _dt.timedelta(days=14)).isoformat(),
        induction_from=_dt.date(y + 1, 7, 1).isoformat(),
    )


def is_late_application(record: Year6Record) -> bool:
    if not record.applied_on:
        return False
    return record.applied_on > national_timetable(record.academic_year).application_deadline


# ── Records ─────────────────────────────────────────────────────────

def _row_record(r: Any) -> Year6Record:
    try:
        consent = json.loads(r["consent_json"] or "{}")
    except (TypeError, ValueError):
        consent = {}
    return Year6Record(
        pupil_id=r["pupil_id"], academic_year=r["academic_year"],
        destination_type=r["destination_type"] or "",
        destination_school=r["destination_school"] or "",
        application_status=r["application_status"] or "not_applied",
        applied_on=r["applied_on"], offered_on=r["offered_on"],
        offered_school=r["offered_school"], accepted_on=r["accepted_on"],
        declined_on=r["declined_on"], declined_reason=r["declined_reason"],
        transition_id=r["transition_id"],
        consent={str(k): bool(v) for k, v in (consent or {}).items()},
        consent_given_by=r["consent_given_by"], consent_on=r["consent_on"],
        consent_method=r["consent_method"],
        handover_approved_on=r["handover_approved_on"],
        handover_approved_by=r["handover_approved_by"],
        secondary_status=r["secondary_status"], secondary_note=r["secondary_note"],
        secondary_status_at=r["secondary_status_at"], moved_on=r["moved_on"],
        secondary_pupil_id=r["secondary_pupil_id"], notes=r["notes"])


def _require_pupil(pupil_id: str) -> Pupil:
    pid = (pupil_id or "").strip()
    if not pid:
        raise ValidationError("Pupil is required")
    pupil = pupils_data.get_pupil(pid)
    if pupil is None:
        raise ValidationError(f"No pupil with id {pid}")
    return pupil


def get_record(pupil_id: str, academic_year: str | None = None) -> Year6Record | None:
    init_db()
    year = normalise_year(academic_year)
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM y6_transition WHERE pupil_id = ? AND academic_year = ?",
            ((pupil_id or "").strip(), year)).fetchone()
    return _row_record(r) if r else None


def latest_record(pupil_id: str) -> Year6Record | None:
    """The pupil's most recent Year 6 record, whatever the year."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM y6_transition WHERE pupil_id = ? "
            "ORDER BY academic_year DESC LIMIT 1", ((pupil_id or "").strip(),)).fetchone()
    return _row_record(r) if r else None


def ensure_record(pupil_id: str, academic_year: str | None = None) -> Year6Record:
    """The pupil's record for the year, created blank if missing."""
    pupil = _require_pupil(pupil_id)
    year = normalise_year(academic_year)
    existing = get_record(pupil.pupil_id, year)
    if existing is not None:
        return existing
    if pupil.year_group != "6" and pupil.roll_status != "left":
        raise ValidationError(
            f"{pupil.full_name} is in year {pupil.year_group}; Year 6 transition "
            f"is for Year 6 pupils")
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO y6_transition (pupil_id, academic_year) VALUES (?, ?)",
            (pupil.pupil_id, year))
    rec = get_record(pupil.pupil_id, year)
    assert rec is not None
    return rec


def _update(pupil_id: str, academic_year: str, **fields: Any) -> Year6Record:
    if "consent" in fields:
        fields["consent_json"] = json.dumps(fields.pop("consent"), sort_keys=True)
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _connect() as conn:
        conn.execute(
            f"UPDATE y6_transition SET {sets}, updated_at = datetime('now') "  # nosec B608 - fixed keys
            "WHERE pupil_id = ? AND academic_year = ?",
            (*fields.values(), pupil_id, academic_year))
    rec = get_record(pupil_id, academic_year)
    assert rec is not None
    return rec


def update_notes(pupil_id: str, academic_year: str | None, notes: str) -> Year6Record:
    rec = ensure_record(pupil_id, academic_year)
    return _update(rec.pupil_id, rec.academic_year, notes=(notes or "").strip() or None)


def year6_pupils(academic_year: str | None = None) -> list[Pupil]:
    """The cohort's pupils: Year 6 on roll now (for the current year) plus
    anyone already holding a record for that year (including leavers)."""
    init_db()
    year = normalise_year(academic_year)
    with _connect() as conn:
        ids = {r[0] for r in conn.execute(
            "SELECT pupil_id FROM y6_transition WHERE academic_year = ?", (year,))}
    out: dict[str, Pupil] = {}
    if year == current_academic_year():
        for p in pupils_data.list_pupils():
            if p.year_group == "6":
                out[p.pupil_id] = p
    for pid in ids - set(out):
        p = pupils_data.get_pupil(pid)
        if p is not None:
            out[pid] = p
    return sorted(out.values(), key=lambda p: (p.last_name.lower(), p.first_name.lower()))


def cohort(academic_year: str | None = None) -> list[CohortRow]:
    """Every Year 6 pupil for the year with their record and progress."""
    year = normalise_year(academic_year)
    rows: list[CohortRow] = []
    with _connect() as conn:
        reports = {r[0] for r in conn.execute(
            "SELECT pupil_id FROM y6_transition_report WHERE academic_year = ?", (year,))}
        visits: dict[str, int] = {r[0]: r[1] for r in conn.execute(
            "SELECT pupil_id, COUNT(*) FROM y6_transition_visits "
            "WHERE academic_year = ? AND attended = 1 GROUP BY pupil_id", (year,))}
    for p in year6_pupils(year):
        rec = get_record(p.pupil_id, year) or Year6Record(p.pupil_id, year)
        items = checklist(p.pupil_id, year, record=rec)
        rows.append(CohortRow(
            pupil=p, record=rec, report_written=p.pupil_id in reports,
            visits_attended=visits.get(p.pupil_id, 0),
            checklist_done=sum(1 for i in items if i.done), checklist_total=len(items)))
    return rows


def cohort_summary(academic_year: str | None = None) -> dict[str, Any]:
    rows = cohort(academic_year)
    by_status: dict[str, int] = {k: 0 for k in APPLICATION_STATUSES}
    for row in rows:
        by_status[row.record.application_status] = (
            by_status.get(row.record.application_status, 0) + 1)
    return {
        "academic_year": normalise_year(academic_year),
        "pupils": len(rows),
        "platform": sum(1 for r in rows if r.record.destination_type == DESTINATION_PLATFORM),
        "external": sum(1 for r in rows if r.record.destination_type == DESTINATION_EXTERNAL),
        "no_destination": sum(1 for r in rows if not r.record.destination_type),
        "by_status": by_status,
        "reports_written": sum(1 for r in rows if r.report_written),
        "consent_recorded": sum(1 for r in rows if r.record.consent_recorded),
        "enhanced": sum(1 for r in rows if (get_report(r.pupil.pupil_id, r.record.academic_year)
                                            or TransitionReport("", "")).enhanced_transition),
    }


# ── Platform plumbing ───────────────────────────────────────────────

def _platform_errors() -> tuple[type[BaseException], ...]:
    from education_system.platform.cross_system import route_support, transitions
    from education_system.platform.cross_system.adapters.base import AdapterError
    return (route_support.RouteError, transitions.TransitionError, AdapterError)


def _transition_row(record: Year6Record, *, db_path: str | None = None) -> dict | None:
    """The record's platform transition, or the newest one on this boundary
    for the pupil's journey (which the final move may have opened)."""
    from education_system.platform.cross_system import identity_service, transitions
    if record.transition_id:
        row = transitions.get_transition(record.transition_id, db_path=db_path)
        if row is not None:
            return row
    pupil = pupils_data.get_pupil(record.pupil_id)
    journey_id = getattr(pupil, "journey_id", None) if pupil else None
    if not journey_id:
        try:
            found = identity_service.find_by_student(SOURCE, record.pupil_id, db_path=db_path)
        except Exception:  # noqa: BLE001 - no journey means no transition
            logger.debug("journey lookup failed for %s", record.pupil_id, exc_info=True)
            found = None
        journey_id = (found or {}).get("journey_id")
    if not journey_id:
        return None
    rows = [r for r in transitions.list_transitions(journey_id, db_path=db_path)
            if r.get("source_system") == SOURCE and r.get("destination_system") == DESTINATION]
    return rows[-1] if rows else None


def _live(row: dict | None) -> bool:
    return row is not None and row.get("status") not in ("completed", "cancelled")


def _identity(pupil: Pupil) -> dict[str, Any]:
    return {"first_name": pupil.first_name, "last_name": pupil.last_name,
            "date_of_birth": pupil.date_of_birth, "upn": getattr(pupil, "upn", None)}


def _ensure_transition(record: Year6Record, *, actor: str | None = None,
                       db_path: str | None = None) -> dict:
    """The live primary→secondary transition for this pupil, opened at
    ``expected`` if there is none."""
    from education_system.platform.cross_system import route_support, transitions
    row = _transition_row(record, db_path=db_path)
    if _live(row):
        assert row is not None
        if row["transition_id"] != record.transition_id:
            _update(record.pupil_id, record.academic_year, transition_id=row["transition_id"])
        return row
    pupil = _require_pupil(record.pupil_id)
    try:
        journey_id = route_support.journey_for(
            _identity(pupil), system=SOURCE, student_id=pupil.pupil_id, db_path=db_path)
        row, created = route_support.start(
            journey_id, source_system=SOURCE, destination_system=DESTINATION,
            student_id=pupil.pupil_id, reason="Year 6 transfer to secondary school",
            year_group=pupil.year_group, db_path=db_path)
        if created:
            start = f"{_start_year(record.academic_year) + 1}-09-01"
            row = transitions.set_effective_date(
                row["transition_id"], start, actor_user_id=actor,
                note="Start of Year 7", db_path=db_path)
    except _platform_errors() as exc:
        raise ValidationError(str(exc)) from exc
    _update(record.pupil_id, record.academic_year, transition_id=row["transition_id"])
    logger.info("Year 6 transition %s opened for %s", row["transition_id"], pupil.pupil_id)
    return row


def _before(row: dict, step: str) -> bool:
    status = row.get("status")
    if status not in _STEP_ORDER:
        return False
    return _STEP_ORDER.index(status) < _STEP_ORDER.index(step)


def safeguarding_reference_for(pupil_id: str, academic_year: str | None = None) -> str | None:
    """The pointer to the DSL-to-DSL file transfer, when there is a file."""
    sg = get_safeguarding_transfer(pupil_id, academic_year)
    if sg is None or not sg.has_file:
        return None
    return sg.reference


def _release(record: Year6Record, *, db_path: str | None = None):
    from education_system.platform.cross_system import route_support
    consent = record.consented_fields or None
    try:
        _raw, released = route_support.release(
            SOURCE, DESTINATION, record.pupil_id, consent=consent,
            safeguarding_reference=safeguarding_reference_for(
                record.pupil_id, record.academic_year))
    except _platform_errors() as exc:
        raise ValidationError(str(exc)) from exc
    if not released.complete:
        raise ValidationError(
            "The handover is missing required information: "
            + route_support.describe_missing(SOURCE, DESTINATION, released.missing_required))
    return released, route_support.consent_reference(consent)


# ── Destination and the admissions round ────────────────────────────

def set_destination(pupil_id: str, academic_year: str | None, destination_type: str,
                    school_name: str | None = None, *, actor: str | None = None,
                    db_path: str | None = None) -> Year6Record:
    """Where the pupil is going. Choosing the platform secondary opens the
    platform transition at ``expected``; moving away from it cancels it."""
    rec = ensure_record(pupil_id, academic_year)
    if rec.application_status == "moved":
        raise ValidationError("The pupil has already moved to secondary")
    if destination_type not in DESTINATION_TYPES:
        raise ValidationError(
            f"Destination must be one of {', '.join(DESTINATION_TYPES.values())}")
    name = (school_name or "").strip()
    if destination_type == DESTINATION_EXTERNAL and not name:
        raise ValidationError("Name the external secondary school")
    if destination_type == DESTINATION_PLATFORM:
        name = name or PLATFORM_DESTINATION_NAME

    if rec.is_platform and destination_type != DESTINATION_PLATFORM:
        row = _transition_row(rec, db_path=db_path)
        if _live(row):
            from education_system.platform.cross_system import transitions
            assert row is not None
            try:
                transitions.cancel(row["transition_id"],
                                   reason=f"Destination changed to {name}",
                                   actor_user_id=actor, db_path=db_path)
            except _platform_errors() as exc:
                raise ValidationError(str(exc)) from exc
        rec = _update(rec.pupil_id, rec.academic_year, transition_id=None,
                      secondary_status="cancelled", handover_approved_on=None,
                      handover_approved_by=None)

    changed = (destination_type != rec.destination_type)
    fields: dict[str, Any] = {"destination_type": destination_type,
                              "destination_school": name}
    if changed and rec.application_status in ("offered", "accepted", "declined"):
        # A new destination is a new application.
        fields.update(application_status="not_applied", applied_on=None, offered_on=None,
                      offered_school=None, accepted_on=None, declined_on=None,
                      declined_reason=None)
    rec = _update(rec.pupil_id, rec.academic_year, **fields)
    if destination_type == DESTINATION_PLATFORM:
        row = _ensure_transition(rec, actor=actor, db_path=db_path)
        rec = _update(rec.pupil_id, rec.academic_year, transition_id=row["transition_id"],
                      secondary_status=row.get("status"),
                      secondary_status_at=_dt.datetime.now().isoformat(timespec="seconds"))
    return rec


def record_application(pupil_id: str, academic_year: str | None, applied_on: str, *,
                       actor: str | None = None, db_path: str | None = None) -> Year6Record:
    """The parent applied (via the council). A date after 31 October is
    recorded as a late application (see :func:`is_late_application`)."""
    rec = ensure_record(pupil_id, academic_year)
    if not rec.destination_type:
        raise ValidationError("Record the destination school first")
    if rec.application_status not in ("not_applied", "applied"):
        raise ValidationError(
            f"The application is already at "
            f"'{APPLICATION_STATUSES[rec.application_status]}'")
    applied = _parse_date(applied_on, "Application date", required=True)
    tt = national_timetable(rec.academic_year)
    assert applied is not None
    if applied < tt.applications_open:
        raise ValidationError(
            f"Applications for {rec.academic_year} open on {tt.applications_open}")
    if rec.is_platform:
        row = _ensure_transition(rec, actor=actor, db_path=db_path)
        if _before(row, "applied"):
            from education_system.platform.cross_system import transitions
            try:
                transitions.record_application(
                    row["transition_id"], application_reference=f"{SOURCE}:{rec.pupil_id}",
                    actor_user_id=actor, db_path=db_path)
            except _platform_errors() as exc:
                raise ValidationError(str(exc)) from exc
    return _update(rec.pupil_id, rec.academic_year, application_status="applied",
                   applied_on=applied)


def record_offer(pupil_id: str, academic_year: str | None, offered_on: str,
                 offered_school: str | None = None, *, actor: str | None = None,
                 db_path: str | None = None) -> Year6Record:
    """A place was offered (national offer day or later).

    For the platform secondary this is where the pupil first exists there:
    the released handover (consented fields only) goes to the secondary's
    adapter, which creates the Year 7 applicant, and the transition moves
    to ``offered``.
    """
    rec = ensure_record(pupil_id, academic_year)
    if rec.application_status != "applied":
        raise ValidationError("Record the application before the offer")
    offered = _parse_date(offered_on, "Offer date", required=True)
    tt = national_timetable(rec.academic_year)
    assert offered is not None
    if offered < tt.offer_day:
        raise ValidationError(
            f"Offers are made on national offer day ({tt.offer_day}) or later")
    if rec.applied_on and offered < rec.applied_on:
        raise ValidationError("The offer cannot come before the application")
    school = (offered_school or "").strip() or rec.destination_school
    if rec.is_platform:
        from education_system.platform.cross_system import route_support, transitions
        row = _ensure_transition(rec, actor=actor, db_path=db_path)
        try:
            if row["status"] == "expected":
                row = transitions.record_application(
                    row["transition_id"], application_reference=f"{SOURCE}:{rec.pupil_id}",
                    actor_user_id=actor, db_path=db_path)
            if row["status"] == "applied":
                released, consent_ref = _release(rec, db_path=db_path)
                applicant = route_support.request_applicant(
                    row, released.payload, consent_reference=consent_ref,
                    year_group=SECONDARY_ENTRY_YEAR)
                transitions.offer_place(
                    row["transition_id"], local_student_id=applicant.local_applicant_id,
                    destination_enrolment_id=route_support.adopt_destination_enrolment(
                        row["journey_id"], DESTINATION, applicant.local_applicant_id,
                        db_path=db_path),
                    year_group=applicant.year_group or SECONDARY_ENTRY_YEAR,
                    actor_user_id=actor, db_path=db_path)
        except _platform_errors() as exc:
            raise ValidationError(str(exc)) from exc
    return _update(rec.pupil_id, rec.academic_year, application_status="offered",
                   offered_on=offered, offered_school=school)


def record_acceptance(pupil_id: str, academic_year: str | None, accepted_on: str, *,
                      actor: str | None = None, db_path: str | None = None) -> Year6Record:
    """The parent accepted the offered place."""
    rec = ensure_record(pupil_id, academic_year)
    if rec.application_status != "offered":
        raise ValidationError("Record the offer before the acceptance")
    accepted = _parse_date(accepted_on, "Acceptance date", required=True)
    assert accepted is not None
    if rec.offered_on and accepted < rec.offered_on:
        raise ValidationError("The acceptance cannot come before the offer")
    if rec.is_platform:
        from education_system.platform.cross_system import transitions
        row = _ensure_transition(rec, actor=actor, db_path=db_path)
        if row["status"] != "offered" and _before(row, "offered"):
            raise ValidationError(
                "The platform transition has no offer yet; record the offer again")
        if row["status"] == "offered":
            try:
                transitions.accept_place(row["transition_id"], accepted_by="parent",
                                         actor_user_id=actor, db_path=db_path)
            except _platform_errors() as exc:
                raise ValidationError(str(exc)) from exc
    return _update(rec.pupil_id, rec.academic_year, application_status="accepted",
                   accepted_on=accepted, declined_on=None, declined_reason=None)


def record_decline(pupil_id: str, academic_year: str | None, declined_on: str,
                   reason: str, *, actor: str | None = None,
                   db_path: str | None = None) -> Year6Record:
    """The parent declined the offer. A platform transition is cancelled;
    record a new destination afterwards."""
    rec = ensure_record(pupil_id, academic_year)
    if rec.application_status not in ("offered", "accepted"):
        raise ValidationError("Only an offered or accepted place can be declined")
    declined = _parse_date(declined_on, "Decline date", required=True)
    why = (reason or "").strip()
    if not why:
        raise ValidationError("Give a reason for declining")
    if rec.is_platform:
        row = _transition_row(rec, db_path=db_path)
        if _live(row):
            from education_system.platform.cross_system import transitions
            assert row is not None
            try:
                transitions.cancel(row["transition_id"], reason=f"Offer declined: {why}",
                                   actor_user_id=actor, db_path=db_path)
            except _platform_errors() as exc:
                raise ValidationError(str(exc)) from exc
    return _update(rec.pupil_id, rec.academic_year, application_status="declined",
                   declined_on=declined, declined_reason=why, transition_id=None,
                   secondary_status="cancelled" if rec.is_platform else rec.secondary_status)


# ── Consent and the handover ────────────────────────────────────────

def set_consent(pupil_id: str, academic_year: str | None, consents: Mapping[str, bool], *,
                given_by: str, given_on: str, method: str) -> Year6Record:
    """Record the parent's yes/no for each sensitive field."""
    rec = ensure_record(pupil_id, academic_year)
    unknown = set(consents) - set(CONSENT_FIELDS)
    if unknown:
        raise ValidationError(f"Unknown consent field(s): {', '.join(sorted(unknown))}")
    who = (given_by or "").strip()
    if not who:
        raise ValidationError("Who gave (or refused) consent is required")
    when = _parse_date(given_on, "Consent date", required=True)
    if method not in CONSENT_METHODS:
        raise ValidationError(f"Method must be one of {', '.join(CONSENT_METHODS)}")
    merged = {k: bool(consents.get(k, rec.consent.get(k, False))) for k in CONSENT_FIELDS}
    return _update(rec.pupil_id, rec.academic_year, consent=merged, consent_given_by=who,
                   consent_on=when, consent_method=method)


def preview_handover(pupil_id: str, academic_year: str | None = None) -> dict[str, Any]:
    """What would cross now: ``{included, withheld_no_consent, missing}``."""
    from education_system.platform.cross_system import route_support
    rec = ensure_record(pupil_id, academic_year)
    consent = rec.consented_fields or None
    try:
        _raw, released = route_support.release(
            SOURCE, DESTINATION, rec.pupil_id, consent=consent,
            safeguarding_reference=safeguarding_reference_for(rec.pupil_id, rec.academic_year))
    except _platform_errors() as exc:
        raise ValidationError(str(exc)) from exc
    return {"included": sorted(released.included),
            "withheld_no_consent": sorted(released.withheld_no_consent),
            "missing": sorted(released.missing_required),
            "payload": released.payload}


def approve_handover(pupil_id: str, academic_year: str | None, *, actor: str | None = None,
                     db_path: str | None = None) -> Year6Record:
    """Release the handover to the platform secondary (step 5).

    Needs an accepted place and recorded consent. Only once: the platform
    workflow moves forward only, so a handover cannot be re-approved after
    edits. Ticks the platform's ``transition_report_sent`` item when the
    report is written.
    """
    from education_system.platform.cross_system import transitions
    rec = ensure_record(pupil_id, academic_year)
    if not rec.is_platform:
        raise ValidationError(
            "Only a move to the platform's Secondary School System has a platform "
            "handover; for another school, send the records directly")
    if rec.application_status != "accepted":
        raise ValidationError("The place must be accepted before the handover is approved")
    if not rec.consent_recorded:
        raise ValidationError(
            "Record the parent's consent decision for each sensitive field first")
    row = _ensure_transition(rec, actor=actor, db_path=db_path)
    if not _before(row, "handover_approved"):
        raise ValidationError(
            "The handover was already approved. The platform workflow only moves "
            "forward, so it cannot be re-approved; pass later changes to the "
            "secondary school directly")
    released, consent_ref = _release(rec, db_path=db_path)
    try:
        if row["status"] != "accepted":
            raise ValidationError(
                f"The platform transition is at '{row['status']}', not 'accepted'")
        transitions.approve_handover(row["transition_id"], released,
                                     consent_reference=consent_ref,
                                     actor_user_id=actor, db_path=db_path)
        if get_report(rec.pupil_id, rec.academic_year) is not None:
            transitions.tick_checklist_item(
                row["transition_id"], "transition_report_sent", actor_user_id=actor,
                note="Year 6 transition report released with the handover",
                db_path=db_path)
    except _platform_errors() as exc:
        raise ValidationError(str(exc)) from exc
    return _update(rec.pupil_id, rec.academic_year,
                   handover_approved_on=_dt.date.today().isoformat(),
                   handover_approved_by=actor or "", secondary_status="handover_approved")


# ── What the secondary did (read back from the platform) ────────────

def platform_status(pupil_id: str, academic_year: str | None = None, *,
                    db_path: str | None = None) -> dict[str, Any] | None:
    """The secondary's side of the transition, from the platform row and
    its events. ``None`` for an external destination or no transition."""
    from education_system.platform.cross_system import transitions
    rec = get_record(pupil_id, academic_year)
    if rec is None or not rec.is_platform:
        return None
    row = _transition_row(rec, db_path=db_path)
    if row is None:
        return None
    if row.get("decision") == "rejected":
        key = "rejected"
    elif row.get("status") in ("admitted", "completed", "cancelled"):
        key = row["status"]
    elif row.get("acknowledged_at"):
        key = "acknowledged"
    else:
        key = row.get("status") or ""
    events = transitions.list_transition_events(row["transition_id"], db_path=db_path)
    checklist_rows = row.get("checklist") or []
    return {
        "transition_id": row["transition_id"],
        "status": row.get("status"),
        "secondary_status": key,
        "label": SECONDARY_STATUS_LABELS.get(key, key),
        "decision": row.get("decision"),
        "reason": row.get("decision_reason") or row.get("cancelled_reason"),
        "acknowledged_at": row.get("acknowledged_at"),
        "acknowledged_by": row.get("acknowledged_by"),
        "effective_date": row.get("effective_date"),
        "checklist": checklist_rows,
        "events": [{"step": e.get("step"), "at": e.get("at"),
                    "actor": e.get("actor"), "note": e.get("note")} for e in events],
    }


def refresh_secondary_status(academic_year: str | None = None, *,
                             db_path: str | None = None) -> int:
    """Cache the secondary's status on each platform record for the year.
    Returns how many records changed."""
    year = normalise_year(academic_year)
    changed = 0
    for row in cohort(year):
        rec = row.record
        if not rec.is_platform:
            continue
        status = platform_status(rec.pupil_id, year, db_path=db_path)
        if status is None:
            continue
        if (status["secondary_status"] != rec.secondary_status
                or status["transition_id"] != rec.transition_id):
            _update(rec.pupil_id, year, secondary_status=status["secondary_status"],
                    secondary_note=status.get("reason"),
                    transition_id=status["transition_id"],
                    secondary_status_at=_dt.datetime.now().isoformat(timespec="seconds"))
            changed += 1
    return changed


def tick_platform_item(pupil_id: str, academic_year: str | None, key: str, *,
                       done: bool = True, actor: str | None = None,
                       db_path: str | None = None) -> list[dict]:
    """Tick a platform checklist item the primary school owns."""
    from education_system.platform.cross_system import transitions
    rec = ensure_record(pupil_id, academic_year)
    row = _transition_row(rec, db_path=db_path) if rec.is_platform else None
    if row is None:
        raise ValidationError("There is no platform transition for this pupil")
    item = next((i for i in row.get("checklist") or [] if i.get("key") == key), None)
    if item is None:
        raise ValidationError(f"No checklist item {key!r}")
    if item.get("owner") not in PRIMARY_CHECKLIST_OWNERS:
        raise ValidationError(f"'{item.get('label')}' is ticked by the secondary school")
    try:
        return transitions.tick_checklist_item(row["transition_id"], key, actor_user_id=actor,
                                               done=done, db_path=db_path)
    except _platform_errors() as exc:
        raise ValidationError(str(exc)) from exc


# ── The move itself ─────────────────────────────────────────────────

def mark_moved(pupil_id: str, *, secondary_pupil_id: str | None = None,
               transition_id: str | None = None, moved_on: str | None = None) -> None:
    """Called after the pupil has left for secondary: closes the record."""
    rec = latest_record(pupil_id)
    if rec is None:
        return
    fields: dict[str, Any] = {"application_status": "moved",
                              "moved_on": moved_on or _dt.date.today().isoformat()}
    if secondary_pupil_id:
        fields["secondary_pupil_id"] = secondary_pupil_id
    if transition_id:
        fields.update(transition_id=transition_id, secondary_status="completed")
    _update(rec.pupil_id, rec.academic_year, **fields)


def complete_external_move(pupil_id: str, academic_year: str | None, leaving_date: str,
                           notes: str | None = None) -> str | None:
    """Take a pupil going to an external school off roll and write the leaver
    (with the destination). Nothing crosses the platform. Returns the
    leaver id."""
    from education_system.systems.primary.domain.learners.pupils import cross_system_adapter
    rec = ensure_record(pupil_id, academic_year)
    if rec.destination_type != DESTINATION_EXTERNAL:
        raise ValidationError(
            "This pupil is going to the platform secondary; use Move to Secondary")
    when = _parse_date(leaving_date, "Leaving date", required=True)
    pupil = _require_pupil(pupil_id)
    if pupil.roll_status == "left":
        raise ValidationError(f"{pupil.full_name} has already left the school")
    cross_system_adapter.ADAPTER.close_enrolment(
        pupil.pupil_id, "Moved to secondary school", end_date=when,
        destination_school=rec.destination_school, notes=notes or "")
    _update(rec.pupil_id, rec.academic_year, application_status="moved", moved_on=when)
    return cross_system_adapter.leaver_id_for(pupil.pupil_id)


# ── Transition report ───────────────────────────────────────────────

def _ids(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [v for v in value.replace(";", ",").split(",")]
    return [str(v).strip() for v in (value or []) if str(v).strip()]


def _row_report(r: Any) -> TransitionReport:
    def _list(raw: str | None) -> list[str]:
        try:
            got = json.loads(raw or "[]")
        except (TypeError, ValueError):
            got = []
        return [str(x) for x in got] if isinstance(got, list) else []
    return TransitionReport(
        pupil_id=r["pupil_id"], academic_year=r["academic_year"],
        strengths=r["strengths"] or "", interests=r["interests"] or "",
        learning_style=r["learning_style"] or "", worries=r["worries"] or "",
        friendships=_list(r["friendships_json"]), keep_apart=_list(r["keep_apart_json"]),
        all_about_me=r["all_about_me"] or "", teacher_comments=r["teacher_comments"] or "",
        enhanced_transition=bool(r["enhanced_transition"]),
        enhanced_reason=r["enhanced_reason"] or "", written_by=r["written_by"] or "",
        written_on=r["written_on"])


def get_report(pupil_id: str, academic_year: str | None = None) -> TransitionReport | None:
    init_db()
    year = normalise_year(academic_year)
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM y6_transition_report WHERE pupil_id = ? AND academic_year = ?",
            ((pupil_id or "").strip(), year)).fetchone()
    return _row_report(r) if r else None


def save_report(pupil_id: str, academic_year: str | None,
                data: Mapping[str, Any]) -> TransitionReport:
    """Create or replace the pupil's transition report.

    ``friendships`` / ``keep_apart`` are pupil ids from the same Year 6
    cohort; the same child cannot be in both lists.
    """
    rec = ensure_record(pupil_id, academic_year)
    cohort_ids = {p.pupil_id for p in year6_pupils(rec.academic_year)}
    friends = _ids(data.get("friendships"))
    apart = _ids(data.get("keep_apart"))
    for label, ids in (("Friendships", friends), ("Keep apart", apart)):
        if rec.pupil_id in ids:
            raise ValidationError(f"{label} cannot include the pupil themself")
        stray = [i for i in ids if i not in cohort_ids]
        if stray:
            raise ValidationError(f"{label}: not in the Year 6 cohort: {', '.join(stray)}")
    both = set(friends) & set(apart)
    if both:
        raise ValidationError(
            f"A pupil cannot be both a friend and someone to keep apart: "
            f"{', '.join(sorted(both))}")
    enhanced = bool(data.get("enhanced_transition"))
    reason = str(data.get("enhanced_reason") or "").strip()
    if enhanced and not reason:
        raise ValidationError("Say why the pupil needs an enhanced transition")
    written_by = str(data.get("written_by") or "").strip()
    if not written_by:
        raise ValidationError("Written by is required")
    written_on = _parse_date(data.get("written_on") or _dt.date.today().isoformat(),
                             "Written on")
    values = {
        "strengths": str(data.get("strengths") or "").strip(),
        "interests": str(data.get("interests") or "").strip(),
        "learning_style": str(data.get("learning_style") or "").strip(),
        "worries": str(data.get("worries") or "").strip(),
        "friendships_json": json.dumps(list(dict.fromkeys(friends))),
        "keep_apart_json": json.dumps(list(dict.fromkeys(apart))),
        "all_about_me": str(data.get("all_about_me") or "").strip(),
        "teacher_comments": str(data.get("teacher_comments") or "").strip(),
        "enhanced_transition": 1 if enhanced else 0,
        "enhanced_reason": reason if enhanced else "",
        "written_by": written_by,
        "written_on": written_on,
    }
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    updates = ", ".join(f"{k} = excluded.{k}" for k in values)
    with _connect() as conn:
        conn.execute(
            f"INSERT INTO y6_transition_report (pupil_id, academic_year, {cols}) "  # nosec B608 - fixed keys
            f"VALUES (?, ?, {marks}) ON CONFLICT(pupil_id, academic_year) DO UPDATE SET "
            f"{updates}, updated_at = datetime('now')",
            (rec.pupil_id, rec.academic_year, *values.values()))
    report = get_report(rec.pupil_id, rec.academic_year)
    assert report is not None
    return report


def _names(ids: Iterable[str]) -> list[str]:
    out = []
    for pid in ids:
        p = pupils_data.get_pupil(pid)
        out.append(p.full_name if p is not None else pid)
    return out


def report_payload(pupil_id: str, academic_year: str | None = None) -> dict[str, Any] | None:
    """The report in the handover's ``transition_report`` shape (names, not
    ids). The pupil's latest report when no year is given."""
    if academic_year:
        report = get_report(pupil_id, academic_year)
    else:
        init_db()
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM y6_transition_report WHERE pupil_id = ? "
                "ORDER BY academic_year DESC LIMIT 1", ((pupil_id or "").strip(),)).fetchone()
        report = _row_report(r) if r else None
    if report is None:
        return None
    return {
        "strengths": report.strengths, "interests": report.interests,
        "learning_style": report.learning_style, "worries": report.worries,
        "friendships": _names(report.friendships), "keep_apart": _names(report.keep_apart),
        "all_about_me": report.all_about_me, "teacher_comments": report.teacher_comments,
        "enhanced_transition": report.enhanced_transition,
        "enhanced_reason": report.enhanced_reason or None,
        "written_by": report.written_by, "written_on": report.written_on,
    }


# ── Visits ──────────────────────────────────────────────────────────

def _row_visit(r: Any) -> Visit:
    return Visit(visit_id=r["visit_id"], pupil_id=r["pupil_id"],
                 academic_year=r["academic_year"], visit_date=r["visit_date"],
                 visit_type=r["visit_type"], school_name=r["school_name"],
                 attended=bool(r["attended"]), notes=r["notes"])


def _validate_visit(data: Mapping[str, Any]) -> dict[str, Any]:
    vtype = str(data.get("visit_type") or "").strip()
    if vtype not in VISIT_TYPES:
        raise ValidationError(f"Visit type must be one of {', '.join(VISIT_TYPES)}")
    return {
        "visit_date": _parse_date(data.get("visit_date"), "Visit date", required=True),
        "visit_type": vtype,
        "school_name": str(data.get("school_name") or "").strip() or None,
        "attended": 1 if data.get("attended", True) else 0,
        "notes": str(data.get("notes") or "").strip() or None,
    }


def add_visit(pupil_id: str, academic_year: str | None, data: Mapping[str, Any]) -> Visit:
    rec = ensure_record(pupil_id, academic_year)
    values = _validate_visit(data)
    if not values["school_name"]:
        values["school_name"] = rec.destination_school or None
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO y6_transition_visits (pupil_id, academic_year, visit_date, "
            "visit_type, school_name, attended, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (rec.pupil_id, rec.academic_year, values["visit_date"], values["visit_type"],
             values["school_name"], values["attended"], values["notes"]))
        visit_id = int(cur.lastrowid or 0)
    visit = get_visit(visit_id)
    assert visit is not None
    return visit


def get_visit(visit_id: int) -> Visit | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM y6_transition_visits WHERE visit_id = ?",
                         (int(visit_id),)).fetchone()
    return _row_visit(r) if r else None


def update_visit(visit_id: int, data: Mapping[str, Any]) -> Visit:
    if get_visit(visit_id) is None:
        raise ValidationError(f"No visit {visit_id}")
    values = _validate_visit(data)
    with _connect() as conn:
        conn.execute(
            "UPDATE y6_transition_visits SET visit_date = ?, visit_type = ?, school_name = ?, "
            "attended = ?, notes = ? WHERE visit_id = ?",
            (values["visit_date"], values["visit_type"], values["school_name"],
             values["attended"], values["notes"], int(visit_id)))
    visit = get_visit(visit_id)
    assert visit is not None
    return visit


def delete_visit(visit_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM y6_transition_visits WHERE visit_id = ?",
                           (int(visit_id),))
    return cur.rowcount > 0


def list_visits(academic_year: str | None = None, *,
                pupil_id: str | None = None) -> list[Visit]:
    init_db()
    year = normalise_year(academic_year)
    sql = "SELECT * FROM y6_transition_visits WHERE academic_year = ?"
    args: list[Any] = [year]
    if pupil_id:
        sql += " AND pupil_id = ?"
        args.append(pupil_id.strip())
    sql += " ORDER BY visit_date, visit_id"
    with _connect() as conn:
        return [_row_visit(r) for r in conn.execute(sql, args).fetchall()]


def add_group_visit(pupil_ids: Iterable[str], academic_year: str | None,
                    data: Mapping[str, Any]) -> list[Visit]:
    """The same visit for several pupils (an induction day for a class)."""
    ids = _ids(list(pupil_ids))
    if not ids:
        raise ValidationError("Choose at least one pupil")
    return [add_visit(pid, academic_year, data) for pid in ids]


# ── Safeguarding file transfer (DSL only; pointer, never the file) ──

def _row_sg(r: Any) -> SafeguardingTransfer:
    return SafeguardingTransfer(
        transfer_id=r["transfer_id"], pupil_id=r["pupil_id"], academic_year=r["academic_year"],
        has_file=bool(r["has_file"]), sent_on=r["sent_on"], sent_to_name=r["sent_to_name"],
        sent_to_role=r["sent_to_role"], sent_to_school=r["sent_to_school"],
        method=r["method"], receipt_confirmed_on=r["receipt_confirmed_on"],
        recorded_by=r["recorded_by"], notes=r["notes"])


def get_safeguarding_transfer(pupil_id: str, academic_year: str | None = None
                              ) -> SafeguardingTransfer | None:
    init_db()
    year = normalise_year(academic_year)
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM y6_safeguarding_transfers WHERE pupil_id = ? AND academic_year = ?",
            ((pupil_id or "").strip(), year)).fetchone()
    return _row_sg(r) if r else None


def list_safeguarding_transfers(academic_year: str | None = None) -> list[SafeguardingTransfer]:
    init_db()
    year = normalise_year(academic_year)
    with _connect() as conn:
        return [_row_sg(r) for r in conn.execute(
            "SELECT * FROM y6_safeguarding_transfers WHERE academic_year = ? "
            "ORDER BY pupil_id", (year,)).fetchall()]


def save_safeguarding_transfer(pupil_id: str, academic_year: str | None,
                               data: Mapping[str, Any]) -> SafeguardingTransfer:
    """Record whether there is a child-protection file and, if so, when it
    went and to whom. ``has_file=False`` records "no file to transfer".

    Statutory guidance expects the file to reach the new school's DSL
    within five school days of the pupil starting, with receipt confirmed.
    """
    rec = ensure_record(pupil_id, academic_year)
    has_file = bool(data.get("has_file", True))
    recorded_by = str(data.get("recorded_by") or "").strip()
    if not recorded_by:
        raise ValidationError("Recorded by is required")
    values: dict[str, Any] = {
        "has_file": 1 if has_file else 0,
        "sent_on": _parse_date(data.get("sent_on"), "Date sent"),
        "sent_to_name": str(data.get("sent_to_name") or "").strip() or None,
        "sent_to_role": str(data.get("sent_to_role") or "").strip() or None,
        "sent_to_school": (str(data.get("sent_to_school") or "").strip()
                           or rec.destination_school or None),
        "method": str(data.get("method") or "").strip() or None,
        "receipt_confirmed_on": _parse_date(data.get("receipt_confirmed_on"),
                                            "Receipt confirmed on"),
        "recorded_by": recorded_by,
        "notes": str(data.get("notes") or "").strip() or None,
    }
    if has_file and values["sent_on"]:
        if not values["sent_to_name"]:
            raise ValidationError("Name the person (DSL) the file was sent to")
        if values["method"] not in SAFEGUARDING_METHODS:
            raise ValidationError(
                f"Method must be one of {', '.join(SAFEGUARDING_METHODS)}")
    if (values["receipt_confirmed_on"] and values["sent_on"]
            and values["receipt_confirmed_on"] < values["sent_on"]):
        raise ValidationError("Receipt cannot be confirmed before the file was sent")
    if values["receipt_confirmed_on"] and not values["sent_on"]:
        raise ValidationError("Record the date sent before the receipt")
    if not has_file:
        values.update(sent_on=None, sent_to_name=None, sent_to_role=None, method=None,
                      receipt_confirmed_on=None)
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    updates = ", ".join(f"{k} = excluded.{k}" for k in values)
    with _connect() as conn:
        conn.execute(
            f"INSERT INTO y6_safeguarding_transfers (pupil_id, academic_year, {cols}) "  # nosec B608 - fixed keys
            f"VALUES (?, ?, {marks}) ON CONFLICT(pupil_id, academic_year) DO UPDATE SET "
            f"{updates}, updated_at = datetime('now')",
            (rec.pupil_id, rec.academic_year, *values.values()))
    out = get_safeguarding_transfer(rec.pupil_id, rec.academic_year)
    assert out is not None
    return out


# ── Checklist ───────────────────────────────────────────────────────

def checklist(pupil_id: str, academic_year: str | None = None, *,
              record: Year6Record | None = None) -> list[ChecklistEntry]:
    """The pupil's transition checklist, derived from what is recorded.

    The safeguarding item says only done / not done, so staff who cannot
    open the DSL tab still see whether that step is complete.
    """
    year = normalise_year(academic_year)
    rec = record or get_record(pupil_id, year) or Year6Record(pupil_id, year)
    tt = national_timetable(year)
    report = get_report(pupil_id, year)
    visits = [v for v in list_visits(year, pupil_id=pupil_id) if v.attended]
    sg = get_safeguarding_transfer(pupil_id, year)
    after_accept = rec.application_status in ("accepted", "moved")
    items = [
        ChecklistEntry("destination", "Destination school recorded",
                       bool(rec.destination_type), rec.destination_label),
        ChecklistEntry("applied", f"Application made (deadline {tt.application_deadline})",
                       bool(rec.applied_on),
                       ("late" if is_late_application(rec) else rec.applied_on or "")),
        ChecklistEntry("offered", f"Place offered (offer day {tt.offer_day})",
                       bool(rec.offered_on), rec.offered_school or ""),
        ChecklistEntry("accepted", "Place accepted", after_accept, rec.accepted_on or ""),
        ChecklistEntry("consent", "Parental consent recorded for sensitive information",
                       rec.consent_recorded, rec.consent_on or ""),
        ChecklistEntry("report", "Transition report written", report is not None,
                       (report.written_on or "") if report else ""),
        ChecklistEntry("visit", "Secondary visit / induction day attended", bool(visits),
                       f"{len(visits)} attended" if visits else ""),
        ChecklistEntry("safeguarding", "Safeguarding file transfer recorded (DSL)",
                       sg is not None and (not sg.has_file or bool(sg.sent_on)), ""),
    ]
    if rec.destination_type != DESTINATION_EXTERNAL:
        items.append(ChecklistEntry(
            "handover", "Handover approved to the secondary",
            bool(rec.handover_approved_on) or rec.application_status == "moved",
            rec.handover_approved_on or ""))
        items.append(ChecklistEntry(
            "acknowledged", "Secondary acknowledged or admitted",
            rec.secondary_status in ("acknowledged", "admitted", "completed"),
            SECONDARY_STATUS_LABELS.get(rec.secondary_status or "", "")))
    return items


__all__ = [
    "APPLICATION_STATUSES", "CONSENT_FIELDS", "CONSENT_LABELS", "CONSENT_METHODS",
    "ChecklistEntry", "CohortRow", "DESTINATION_EXTERNAL", "DESTINATION_PLATFORM",
    "DESTINATION_TYPES", "PLATFORM_DESTINATION_NAME", "SAFEGUARDING_METHODS",
    "SECONDARY_STATUS_LABELS", "SafeguardingTransfer", "Timetable", "TransitionReport",
    "VISIT_TYPES", "ValidationError", "Visit", "Year6Record", "add_group_visit",
    "add_visit", "approve_handover", "checklist", "cohort", "cohort_summary",
    "complete_external_move", "current_academic_year", "delete_visit", "ensure_record",
    "get_record", "get_report", "get_safeguarding_transfer", "get_visit", "init_db",
    "is_late_application", "latest_record", "list_safeguarding_transfers", "list_visits",
    "mark_moved", "national_timetable", "normalise_year", "platform_status",
    "preview_handover", "record_acceptance", "record_application", "record_decline",
    "record_offer", "refresh_secondary_status", "report_payload",
    "safeguarding_reference_for", "save_report", "save_safeguarding_transfer",
    "set_consent", "set_destination", "tick_platform_item", "update_notes",
    "update_visit", "year6_pupils", "year_dates",
]
