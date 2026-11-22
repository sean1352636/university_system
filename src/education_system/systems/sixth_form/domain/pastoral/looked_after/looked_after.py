"""Looked-after children & care leavers register for the Sixth Form.

Builds on the vulnerable-groups records in
:mod:`domain.pastoral.wellbeing.wellbeing` — ``vg_care_records`` (care
status, local authority, legal status, social worker, virtual school,
start/end dates) and ``vg_pep_reviews`` — which stay the one place that
holds a learner's care status. This module adds what the register was
missing:

* **Designated teacher** — the statutory designated teacher for
  looked-after and previously looked-after learners, kept as dated
  appointments (``lac_designated_teachers``), and a staff link on each
  care record (``vg_care_records.designated_teacher_id``). A new record
  with no designated teacher gets the current appointee.
* **PEP actions** — the actions agreed at a Personal Education Plan
  review, each with an owner, a due date and an outcome
  (``lac_pep_actions``).
* **Care-leaver support plans** — pathway plan, personal adviser,
  accommodation, education goal, financial support and the link to the
  16-19 vulnerable bursary application (``lac_leaver_plans``). The
  bursary itself is finance's: this module only *reads* bursary
  applications filed under the bursary module's own "In care
  (looked-after child)" / "Care leaver" categories.
* **Reports** — PEP reviews overdue or due soon (including looked-after
  learners with no PEP recorded at all), PEP actions overdue, and
  care-experienced learners with no vulnerable bursary application.

Everything is sensitive: every call needs the PASTORAL capability plus
the object-level ``can_see_student`` check, and every read and write is
written to the sensitive-access log (area ``vulnerable_groups``, the
same area the wellbeing care records use).

PEP actions and leaver plans reference their care record and student
with ``ON DELETE RESTRICT``: a care record with that history cannot be
deleted (end it instead), so the history is never lost by cascade.
"""

from __future__ import annotations

import datetime as _dt
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system.systems.sixth_form.domain.pastoral import _people, _records
from education_system.systems.sixth_form.domain.pastoral.wellbeing import (
    wellbeing as _wb,
)
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

AREA = "vulnerable_groups"

# The care vocabularies are the wellbeing module's; re-exported so the
# interfaces need only this module.
CARE_STATUSES = _wb.CARE_STATUSES
LEGAL_STATUSES = _wb.LEGAL_STATUSES
PLACEMENT_TYPES = _wb.PLACEMENT_TYPES
CARE_LEAVER_STATUSES: tuple[str, ...] = tuple(
    s for s in CARE_STATUSES if s.startswith("Care Leaver"))
LAC = "Looked-After Child"
PLAC = "Previously Looked-After"

PEP_ACTION_AREAS: tuple[str, ...] = (
    "Attendance", "Attainment / Progress", "Wellbeing", "Careers / Progression",
    "Pupil Premium Plus / Funding", "SEND", "Enrichment", "Placement / Home",
    "Other",
)
OPEN = "Open"
PEP_ACTION_STATUSES: tuple[str, ...] = (OPEN, "Completed", "Not Achieved",
                                        "Cancelled")

PLAN_ACTIVE = "Active"
PLAN_CLOSED = "Closed"
PLAN_STATUSES: tuple[str, ...] = (PLAN_ACTIVE, PLAN_CLOSED)
ACCOMMODATION_TYPES: tuple[str, ...] = (
    "Staying Put (with former foster carer)", "Supported Lodgings",
    "Semi-Independent", "Independent Tenancy", "With Family",
    "Residential", "Higher Education Halls", "Temporary / Emergency",
    "Unknown", "Other",
)

#: Care status -> the bursary module's vulnerable category it files under.
#: Previously looked-after learners are not a defined vulnerable group.
_BURSARY_CATEGORY: dict[str, str] = {
    LAC: "In care (looked-after child)",
    **{s: "Care leaver" for s in CARE_LEAVER_STATUSES},
}
#: The bursary module's matching eligibility bases (older applications
#: recorded the basis but not the category).
_BURSARY_BASES = ("Looked-After Child", "Care Leaver")

DEFAULT_DUE_SOON_DAYS = 28

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lac_designated_teachers (
    appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id       TEXT NOT NULL,
    start_date     TEXT NOT NULL,
    end_date       TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS lac_pep_actions (
    action_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id    INTEGER NOT NULL,
    review_id    INTEGER,
    student_id   TEXT NOT NULL,
    action       TEXT NOT NULL,
    area         TEXT,
    owner        TEXT,
    due_date     TEXT,
    status       TEXT NOT NULL DEFAULT 'Open',
    completed_on TEXT,
    outcome      TEXT,
    created_by   TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (record_id) REFERENCES vg_care_records(record_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (review_id) REFERENCES vg_pep_reviews(review_id)
        ON DELETE SET NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS lac_leaver_plans (
    plan_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id              INTEGER NOT NULL,
    student_id             TEXT NOT NULL,
    plan_date              TEXT NOT NULL,
    personal_adviser       TEXT,
    personal_adviser_phone TEXT,
    personal_adviser_email TEXT,
    pathway_plan_held      INTEGER NOT NULL DEFAULT 0,
    pathway_plan_date      TEXT,
    accommodation          TEXT,
    education_goal         TEXT,
    financial_support      TEXT,
    bursary_application_id INTEGER,
    support_needs          TEXT,
    review_due             TEXT,
    status                 TEXT NOT NULL DEFAULT 'Active',
    closed_on              TEXT,
    notes                  TEXT,
    created_by             TEXT,
    created_at             TEXT DEFAULT (datetime('now')),
    updated_at             TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (record_id) REFERENCES vg_care_records(record_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (bursary_application_id)
        REFERENCES bursary_applications(application_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_lac_dt_open   ON lac_designated_teachers(end_date);
CREATE INDEX IF NOT EXISTS idx_lac_pa_record ON lac_pep_actions(record_id);
CREATE INDEX IF NOT EXISTS idx_lac_pa_due    ON lac_pep_actions(status, due_date);
CREATE INDEX IF NOT EXISTS idx_lac_lp_record ON lac_leaver_plans(record_id);
"""


class ValidationError(ValueError):
    pass


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Appointment:
    appointment_id: int
    staff_id: str
    start_date: str
    end_date: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def current(self) -> bool:
        t = _records.today()
        return self.start_date <= t and (not self.end_date
                                         or self.end_date >= t)


@dataclass
class PEPAction:
    action_id: int
    record_id: int
    review_id: int | None
    student_id: str
    action: str
    area: str | None
    owner: str | None
    due_date: str | None
    status: str
    completed_on: str | None
    outcome: str | None
    created_by: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def overdue(self) -> bool:
        return bool(self.status == OPEN and self.due_date
                    and self.due_date < _records.today())


@dataclass
class LeaverPlan:
    plan_id: int
    record_id: int
    student_id: str
    plan_date: str
    personal_adviser: str | None
    personal_adviser_phone: str | None
    personal_adviser_email: str | None
    pathway_plan_held: bool
    pathway_plan_date: str | None
    accommodation: str | None
    education_goal: str | None
    financial_support: str | None
    bursary_application_id: int | None
    support_needs: str | None
    review_due: str | None
    status: str
    closed_on: str | None
    notes: str | None
    created_by: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def review_overdue(self) -> bool:
        return bool(self.status == PLAN_ACTIVE and self.review_due
                    and self.review_due < _records.today())


@dataclass
class BursaryLink:
    """One bursary application filed under a care category (read-only)."""
    application_id: int
    academic_year: str | None
    bursary_type: str
    category: str | None
    status: str
    amount_awarded: float | None
    application_date: str


@dataclass
class PEPDueRow:
    record_id: int
    student_id: str
    student_name: str
    care_status: str
    local_authority: str
    designated_teacher: str | None
    virtual_school_contact: str | None
    last_pep_on: str | None
    next_pep_due: str | None
    state: str              # "Overdue" / "Due soon" / "No PEP recorded"
    days: int | None        # days overdue (+) or until due (-)
    open_actions: int = 0
    overdue_actions: int = 0


@dataclass
class BursaryGapRow:
    record_id: int
    student_id: str
    student_name: str
    care_status: str
    expected_category: str
    applications: list[BursaryLink] = field(default_factory=list)

    @property
    def note(self) -> str:
        if not self.applications:
            return "No vulnerable bursary application on file"
        return "Applications on file but none active or approved"


@dataclass
class CareFile:
    """Everything on one care record, for the detail view."""
    record: Any
    student_name: str
    designated_teacher: str | None
    pep_reviews: list[Any]
    actions: list[PEPAction]
    leaver_plans: list[LeaverPlan]
    bursaries: list[BursaryLink]


_C = _records.Col

APPOINTMENT_SPEC = _records.TableSpec(
    table="lac_designated_teachers", id_col="appointment_id",
    row_type=Appointment, label="Designated teacher appointment",
    order_by="start_date DESC, appointment_id DESC",
    cols=(
        _C("staff_id", "Designated teacher (staff)", required=True),
        _C("start_date", "From", "date", required=True,
           default=_records.today),
        _C("end_date", "To", "date"),
        _C("notes", "Notes", "multiline", listed=False),
    ))

PEP_ACTION_SPEC = _records.TableSpec(
    table="lac_pep_actions", id_col="action_id", row_type=PEPAction,
    label="PEP action",
    order_by="status <> 'Open', due_date IS NULL, due_date, action_id",
    cols=(
        _C("record_id", "Care record #", "int", required=True, fixed=True),
        _C("review_id", "PEP review #", "int", listed=False),
        _C("student_id", "Student", "student", fixed=True, hidden=True),
        _C("action", "Action", "multiline", required=True),
        _C("area", "Area", "choice", choices=PEP_ACTION_AREAS),
        _C("owner", "Owner"),
        _C("due_date", "Due", "date"),
        _C("status", "Status", "choice", choices=PEP_ACTION_STATUSES,
           default=OPEN),
        _C("completed_on", "Completed on", "date"),
        _C("outcome", "Outcome", "multiline", listed=False),
        _C("created_by", "Recorded by", hidden=True),
    ))

LEAVER_PLAN_SPEC = _records.TableSpec(
    table="lac_leaver_plans", id_col="plan_id", row_type=LeaverPlan,
    label="Care-leaver support plan",
    order_by="status <> 'Active', plan_date DESC, plan_id DESC",
    cols=(
        _C("record_id", "Care record #", "int", required=True, fixed=True),
        _C("student_id", "Student", "student", fixed=True, hidden=True),
        _C("plan_date", "Plan date", "date", required=True,
           default=_records.today),
        _C("personal_adviser", "Personal adviser"),
        _C("personal_adviser_phone", "Adviser phone", listed=False),
        _C("personal_adviser_email", "Adviser e-mail", listed=False),
        _C("pathway_plan_held", "Pathway plan seen", "bool"),
        _C("pathway_plan_date", "Pathway plan dated", "date", listed=False),
        _C("accommodation", "Accommodation", "choice",
           choices=ACCOMMODATION_TYPES),
        _C("education_goal", "Education / career goal", "multiline",
           listed=False),
        _C("financial_support", "Financial support (LA / setting)",
           "multiline", listed=False),
        _C("bursary_application_id", "16-19 bursary application #", "int"),
        _C("support_needs", "Support agreed / needs", "multiline",
           listed=False),
        _C("review_due", "Review due", "date"),
        _C("status", "Status", "choice", choices=PLAN_STATUSES,
           default=PLAN_ACTIVE),
        _C("closed_on", "Closed on", "date", listed=False),
        _C("notes", "Notes", "multiline", listed=False),
        _C("created_by", "Recorded by", hidden=True),
    ))


# ── DB plumbing ─────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[_sql.Connection]:
    from education_system import paths
    paths.ensure_sixth_form_directories()
    # The tables this module extends are the wellbeing module's, so it
    # follows that module's file (sixthform.db in production).
    conn = _sql.connect(str(_wb.DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    # FK targets first: students + vg_* (wellbeing), staff, bursaries.
    _wb.init_db()
    from education_system.systems.sixth_form.domain.staff import staff as _staff
    _staff.init_db()
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries as _burs,
    )
    _burs.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        _records.ensure_columns(conn, "vg_care_records", {
            "designated_teacher_id":
                "TEXT REFERENCES staff(staff_id) ON DELETE SET NULL",
        })
    logger.debug("Looked-after register schema ready at %s", _wb.DB_PATH)
    _DB_READY = True


def _guard(action: str, student_id: str | None = None,
           ref: str | None = None) -> Any:
    return _records.guard("PASTORAL", AREA, action, student_id=student_id,
                          record_ref=ref)


def _actor_name(p: Any) -> str | None:
    return p.staff_name or p.username or None


def _care_record(conn: Any, record_id: int) -> Any:
    rec = _records.fetch(conn, _wb.CARE_SPEC, int(record_id))
    if rec is None:
        raise ValidationError(f"No care record #{record_id}")
    return rec


def _designated_id(conn: Any, record_id: int) -> str | None:
    r = conn.execute("SELECT designated_teacher_id FROM vg_care_records "
                     "WHERE record_id = ?", (record_id,)).fetchone()
    return r[0] if r else None


# ── Designated teacher ──────────────────────────────────────────────

def appoint_designated_teacher(staff: str, *, start_date: str | None = None,
                               notes: str | None = None) -> Appointment:
    """Appoint the college's designated teacher from *start_date*.

    The open appointment (if any) ends the day before, so the history
    shows who held the role when.
    """
    init_db()
    staff_id = _people.check_staff(staff, "Designated teacher",
                                   ValidationError)
    if not staff_id:
        raise ValidationError("Designated teacher is required")
    start = _records.check_date(start_date, "From",
                                ValidationError) or _records.today()
    _guard("appoint designated teacher", ref=f"staff:{staff_id}")
    day_before = (_dt.date.fromisoformat(start)
                  - _dt.timedelta(days=1)).isoformat()
    with _connect() as conn:
        clash = conn.execute(
            "SELECT appointment_id FROM lac_designated_teachers "
            "WHERE start_date >= ?", (start,)).fetchone()
        if clash:
            raise ValidationError(
                "An appointment already starts on or after that date; "
                "edit it instead")
        conn.execute(
            "UPDATE lac_designated_teachers SET end_date = ?, "
            "updated_at = datetime('now') WHERE end_date IS NULL "
            "OR end_date >= ?", (day_before, start))
        new_id = _records.insert(conn, APPOINTMENT_SPEC, {
            "staff_id": staff_id, "start_date": start, "end_date": None,
            "notes": (notes or "").strip() or None})
        out = _records.fetch(conn, APPOINTMENT_SPEC, new_id)
    logger.info("Designated teacher appointed: %s from %s", staff_id, start)
    return out


def update_appointment(appointment_id: int, data: dict[str, Any]
                       ) -> Appointment:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, APPOINTMENT_SPEC, appointment_id)
    if existing is None:
        raise ValidationError(f"No appointment #{appointment_id}")
    p = _records.validate(APPOINTMENT_SPEC, data, error=ValidationError,
                          existing=existing)
    p["staff_id"] = _people.check_staff(p["staff_id"], "Designated teacher",
                                        ValidationError)
    if not p["staff_id"]:
        raise ValidationError("Designated teacher is required")
    if p["end_date"] and p["end_date"] < p["start_date"]:
        raise ValidationError("'To' cannot be before 'From'")
    _guard("update designated teacher appointment",
           ref=f"lac_dt:{appointment_id}")
    with _connect() as conn:
        _records.update(conn, APPOINTMENT_SPEC, appointment_id, p)
        return _records.fetch(conn, APPOINTMENT_SPEC, appointment_id)


def delete_appointment(appointment_id: int) -> bool:
    init_db()
    _guard("delete designated teacher appointment",
           ref=f"lac_dt:{appointment_id}")
    with _connect() as conn:
        return _records.delete(conn, APPOINTMENT_SPEC, appointment_id)


def list_appointments() -> list[Appointment]:
    init_db()
    _guard("list designated teacher appointments")
    with _connect() as conn:
        return _records.select(conn, APPOINTMENT_SPEC)


def current_designated_teacher(on: str | None = None) -> Appointment | None:
    """The appointment in force on *on* (default today). Not sensitive:
    who the designated teacher is, is public information."""
    init_db()
    day = on or _records.today()
    with _connect() as conn:
        rows = _records.select(
            conn, APPOINTMENT_SPEC,
            where=["start_date <= ?", "(end_date IS NULL OR end_date >= ?)"],
            args=[day, day], limit=1)
    return rows[0] if rows else None


# ── Care records (wrapping the wellbeing store) ─────────────────────

def _split_designated(data: dict[str, Any]) -> tuple[dict[str, Any],
                                                     str | None, bool]:
    """Pull ``designated_teacher_id`` out of *data* and fill the text
    ``designated_teacher`` column (other screens read it) from it."""
    payload = dict(data)
    given = "designated_teacher_id" in payload
    staff_id = _people.check_staff(payload.pop("designated_teacher_id", None),
                                   "Designated teacher", ValidationError)
    if staff_id:
        payload["designated_teacher"] = _people.staff_name(staff_id)
    return payload, staff_id, given


def create_care_record(data: dict[str, Any]) -> Any:
    """Create a care record (in the wellbeing store, so the wellbeing
    flag follows). A blank designated teacher takes the current
    appointee."""
    init_db()
    payload, staff_id, _given = _split_designated(data)
    if not staff_id and payload.get("care_status") in (LAC, PLAC):
        appt = current_designated_teacher()
        if appt is not None:
            staff_id = appt.staff_id
            payload.setdefault("designated_teacher",
                               _people.staff_name(staff_id))
    rec = _wb.create_care_record(payload)
    if staff_id:
        with _connect() as conn:
            conn.execute("UPDATE vg_care_records SET designated_teacher_id = ?"
                         " WHERE record_id = ?", (staff_id, rec.record_id))
    return rec


def update_care_record(record_id: int, data: dict[str, Any]) -> Any:
    init_db()
    payload, staff_id, given = _split_designated(data)
    if given and not staff_id:
        payload.setdefault("designated_teacher", "")
    rec = _wb.update_care_record(record_id, payload)
    if given:
        with _connect() as conn:
            conn.execute("UPDATE vg_care_records SET designated_teacher_id = ?"
                         " WHERE record_id = ?", (staff_id, record_id))
    return rec


def delete_care_record(record_id: int) -> bool:
    """Delete a care record entered by mistake. Refused once PEP actions
    or a leaver plan hang off it — end the record instead."""
    init_db()
    with _connect() as conn:
        n_act = conn.execute("SELECT COUNT(*) FROM lac_pep_actions "
                             "WHERE record_id = ?", (record_id,)).fetchone()[0]
        n_plan = conn.execute("SELECT COUNT(*) FROM lac_leaver_plans "
                              "WHERE record_id = ?", (record_id,)).fetchone()[0]
    if n_act or n_plan:
        raise ValidationError(
            f"Care record #{record_id} has {n_act} PEP action(s) and "
            f"{n_plan} leaver plan(s); set an end date instead of deleting")
    return _wb.delete_care_record(record_id)


@dataclass
class CareRow(_wb.CareRecord):
    """A wellbeing care record plus its designated-teacher staff link."""
    designated_teacher_id: str | None = None


def _with_designated(recs: list[Any]) -> list[CareRow]:
    if not recs:
        return []
    with _connect() as conn:
        ids = {r[0]: r[1] for r in conn.execute(
            "SELECT record_id, designated_teacher_id FROM vg_care_records")}
    out = []
    for r in recs:
        row = CareRow(**{f: getattr(r, f) for f in
                         r.__dataclass_fields__})
        row.designated_teacher_id = ids.get(r.record_id)
        out.append(row)
    return out


def list_care_records(**kwargs: Any) -> list[CareRow]:
    """The wellbeing care records (same filters), with the designated
    teacher's staff id."""
    init_db()
    return _with_designated(_wb.list_care_records(**kwargs))


def get_care_record(record_id: int) -> CareRow | None:
    init_db()
    rec = _wb.get_care_record(record_id)
    return _with_designated([rec])[0] if rec else None


def designated_teacher_id(record_id: int) -> str | None:
    init_db()
    rec = _wb.get_care_record(record_id)       # guards + logs
    if rec is None:
        return None
    with _connect() as conn:
        return _designated_id(conn, record_id)


# ── PEP reviews (wellbeing) + actions ───────────────────────────────

def record_pep_review(data: dict[str, Any], *,
                      actions: list[dict[str, Any]] | None = None) -> Any:
    """Log a PEP review (rolling the record's PEP dates forward, as the
    wellbeing store does) and the actions agreed at it."""
    init_db()
    for a in actions or ():
        if not str(a.get("action") or "").strip():
            raise ValidationError("Each agreed action needs a description")
    review = _wb.record_pep_review(data)
    for a in actions or ():
        add_pep_action({**a, "record_id": review.record_id,
                        "review_id": review.review_id})
    return review


def _action_rules(conn: Any, p: dict[str, Any]) -> Any:
    rec = _care_record(conn, p["record_id"])
    if p.get("review_id"):
        r = conn.execute("SELECT record_id FROM vg_pep_reviews "
                         "WHERE review_id = ?", (p["review_id"],)).fetchone()
        if r is None:
            raise ValidationError(f"No PEP review #{p['review_id']}")
        if int(r[0]) != int(p["record_id"]):
            raise ValidationError(
                "That PEP review belongs to a different care record")
    if p["status"] == OPEN:
        p["completed_on"] = None
    elif p["status"] == "Completed" and not p["completed_on"]:
        p["completed_on"] = _records.today()
    return rec


def add_pep_action(data: dict[str, Any]) -> PEPAction:
    init_db()
    p = _records.validate(PEP_ACTION_SPEC, data, error=ValidationError)
    with _connect() as conn:
        rec = _action_rules(conn, p)
    actor = _guard("add PEP action", rec.student_id,
                   f"vg_care:{rec.record_id}")
    p["student_id"] = rec.student_id
    p["created_by"] = _actor_name(actor)
    with _connect() as conn:
        new_id = _records.insert(conn, PEP_ACTION_SPEC, p)
        out = _records.fetch(conn, PEP_ACTION_SPEC, new_id)
    logger.info("PEP action #%d for care record #%d", new_id, rec.record_id)
    return out


def update_pep_action(action_id: int, data: dict[str, Any]) -> PEPAction:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, PEP_ACTION_SPEC, action_id)
    if existing is None:
        raise ValidationError(f"No PEP action #{action_id}")
    p = _records.validate(PEP_ACTION_SPEC, data, error=ValidationError,
                          existing=existing)
    with _connect() as conn:
        _action_rules(conn, p)
    _guard("update PEP action", existing.student_id, f"lac_pa:{action_id}")
    with _connect() as conn:
        _records.update(conn, PEP_ACTION_SPEC, action_id, p)
        return _records.fetch(conn, PEP_ACTION_SPEC, action_id)


def complete_pep_action(action_id: int, *, outcome: str | None = None,
                        status: str = "Completed",
                        on: str | None = None) -> PEPAction:
    if status == OPEN:
        raise ValidationError("Choose how the action ended")
    return update_pep_action(action_id, {
        "status": status, "outcome": outcome,
        "completed_on": on or _records.today()})


def delete_pep_action(action_id: int) -> bool:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, PEP_ACTION_SPEC, action_id)
        if existing is None:
            return False
    _guard("delete PEP action", existing.student_id, f"lac_pa:{action_id}")
    with _connect() as conn:
        return _records.delete(conn, PEP_ACTION_SPEC, action_id)


def list_pep_actions(*, record_id: int | None = None,
                     student_id: str | None = None,
                     open_only: bool = False,
                     overdue_only: bool = False) -> list[PEPAction]:
    init_db()
    _guard("list PEP actions", student_id,
           f"vg_care:{record_id}" if record_id else None)
    where, args = [], []
    if open_only or overdue_only:
        where.append("status = 'Open'")
    if overdue_only:
        where.append("due_date IS NOT NULL AND due_date < ?")
        args.append(_records.today())
    with _connect() as conn:
        rows = _records.select(
            conn, PEP_ACTION_SPEC,
            equals={"record_id": record_id, "student_id": student_id},
            where=where, args=args)
    return _records.visible_filter("PASTORAL", rows)


# ── Care-leaver support plans ───────────────────────────────────────

def _plan_rules(conn: Any, p: dict[str, Any]) -> Any:
    rec = _care_record(conn, p["record_id"])
    if rec.care_status == PLAC:
        raise ValidationError(
            "Previously looked-after learners are not care leavers; "
            "a leaving-care support plan does not apply")
    if p.get("bursary_application_id"):
        r = conn.execute(
            "SELECT student_id FROM bursary_applications "
            "WHERE application_id = ?",
            (p["bursary_application_id"],)).fetchone()
        if r is None:
            raise ValidationError(
                f"No bursary application #{p['bursary_application_id']}")
        if r[0] != rec.student_id:
            raise ValidationError(
                "That bursary application is for a different student")
    if p["review_due"] and p["review_due"] < p["plan_date"]:
        raise ValidationError("Review due cannot be before the plan date")
    if p["status"] == PLAN_CLOSED and not p["closed_on"]:
        p["closed_on"] = _records.today()
    if p["status"] == PLAN_ACTIVE:
        p["closed_on"] = None
    return rec


def create_leaver_plan(data: dict[str, Any]) -> LeaverPlan:
    init_db()
    p = _records.validate(LEAVER_PLAN_SPEC, data, error=ValidationError)
    with _connect() as conn:
        rec = _plan_rules(conn, p)
    actor = _guard("create care-leaver plan", rec.student_id,
                   f"vg_care:{rec.record_id}")
    p["student_id"] = rec.student_id
    p["created_by"] = _actor_name(actor)
    if not p["personal_adviser"] and rec.personal_adviser:
        p["personal_adviser"] = rec.personal_adviser
    if not p["bursary_application_id"]:
        p["bursary_application_id"] = _latest_bursary_id(rec)
    with _connect() as conn:
        if p["status"] == PLAN_ACTIVE and conn.execute(
                "SELECT 1 FROM lac_leaver_plans WHERE record_id = ? "
                "AND status = 'Active'", (rec.record_id,)).fetchone():
            raise ValidationError(
                "This care record already has an active plan; close it "
                "or edit it")
        new_id = _records.insert(conn, LEAVER_PLAN_SPEC, p)
        out = _records.fetch(conn, LEAVER_PLAN_SPEC, new_id)
    logger.info("Care-leaver plan #%d for %s", new_id, rec.student_id)
    return out


def update_leaver_plan(plan_id: int, data: dict[str, Any]) -> LeaverPlan:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, LEAVER_PLAN_SPEC, plan_id)
    if existing is None:
        raise ValidationError(f"No care-leaver plan #{plan_id}")
    p = _records.validate(LEAVER_PLAN_SPEC, data, error=ValidationError,
                          existing=existing)
    with _connect() as conn:
        _plan_rules(conn, p)
        if p["status"] == PLAN_ACTIVE and conn.execute(
                "SELECT 1 FROM lac_leaver_plans WHERE record_id = ? "
                "AND status = 'Active' AND plan_id <> ?",
                (existing.record_id, plan_id)).fetchone():
            raise ValidationError(
                "This care record already has another active plan")
    _guard("update care-leaver plan", existing.student_id,
           f"lac_lp:{plan_id}")
    with _connect() as conn:
        _records.update(conn, LEAVER_PLAN_SPEC, plan_id, p)
        return _records.fetch(conn, LEAVER_PLAN_SPEC, plan_id)


def delete_leaver_plan(plan_id: int) -> bool:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, LEAVER_PLAN_SPEC, plan_id)
        if existing is None:
            return False
    _guard("delete care-leaver plan", existing.student_id,
           f"lac_lp:{plan_id}")
    with _connect() as conn:
        return _records.delete(conn, LEAVER_PLAN_SPEC, plan_id)


def list_leaver_plans(*, record_id: int | None = None,
                      student_id: str | None = None,
                      active_only: bool = False,
                      review_overdue_only: bool = False) -> list[LeaverPlan]:
    init_db()
    _guard("list care-leaver plans", student_id,
           f"vg_care:{record_id}" if record_id else None)
    where, args = [], []
    if active_only or review_overdue_only:
        where.append("status = 'Active'")
    if review_overdue_only:
        where.append("review_due IS NOT NULL AND review_due < ?")
        args.append(_records.today())
    with _connect() as conn:
        rows = _records.select(
            conn, LEAVER_PLAN_SPEC,
            equals={"record_id": record_id, "student_id": student_id},
            where=where, args=args)
    return _records.visible_filter("PASTORAL", rows)


# ── 16-19 bursary link (read-only) ──────────────────────────────────

def bursary_category_for(care_status: str) -> str | None:
    """The bursary module's vulnerable category for a care status."""
    return _BURSARY_CATEGORY.get(care_status)


def _bursaries():
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries as _b,
    )
    return _b


def _care_bursaries(student_id: str) -> list[BursaryLink]:
    b = _bursaries()
    cats = {c for c in b.VULNERABLE_CATEGORIES
            if c in _BURSARY_CATEGORY.values()}
    out = []
    for a in b.list_applications(student_id=student_id):
        if a.vulnerable_category in cats or (
                not a.vulnerable_category
                and a.eligibility_basis in _BURSARY_BASES):
            out.append(BursaryLink(
                application_id=a.application_id,
                academic_year=a.academic_year, bursary_type=a.bursary_type,
                category=a.vulnerable_category or a.eligibility_basis,
                status=a.status, amount_awarded=a.amount_awarded,
                application_date=a.application_date))
    return out


def _latest_bursary_id(rec: Any) -> int | None:
    apps = _care_bursaries(rec.student_id)
    return apps[0].application_id if apps else None


def bursary_applications_for(student_id: str) -> list[BursaryLink]:
    """The student's bursary applications filed under a care category."""
    init_db()
    _guard("view care bursary applications", student_id)
    return _care_bursaries(student_id)


def bursary_gaps() -> list[BursaryGapRow]:
    """Current looked-after children and care leavers with no active or
    approved vulnerable bursary application."""
    init_db()
    _guard("view care bursary gaps")
    b = _bursaries()
    live = set(b.ACTIVE_STATUSES) | set(b.APPROVED_STATUSES)
    names = _people.student_names()
    out: list[BursaryGapRow] = []
    seen: set[str] = set()
    for rec in _wb.list_care_records(active_only=True):
        cat = bursary_category_for(rec.care_status)
        if not cat or rec.student_id in seen:
            continue
        seen.add(rec.student_id)
        apps = _care_bursaries(rec.student_id)
        if any(a.status in live for a in apps):
            continue
        out.append(BursaryGapRow(
            record_id=rec.record_id, student_id=rec.student_id,
            student_name=names.get(rec.student_id, "(unknown)"),
            care_status=rec.care_status, expected_category=cat,
            applications=apps))
    out.sort(key=lambda r: r.student_name)
    return out


# ── Reports ─────────────────────────────────────────────────────────

def pep_due_list(*, within_days: int = DEFAULT_DUE_SOON_DAYS
                 ) -> list[PEPDueRow]:
    """PEP reviews overdue, due within *within_days*, and current
    looked-after learners with no PEP recorded at all — the designated
    teacher's chase list, most overdue first."""
    init_db()
    if within_days < 0:
        raise ValidationError("Days ahead cannot be negative")
    _guard("view PEP due list")
    today = _dt.date.today()
    horizon = (today + _dt.timedelta(days=within_days)).isoformat()
    names = _people.student_names()
    with _connect() as conn:
        counts = {r["record_id"]: (r["open_n"], r["late_n"]) for r in
                  conn.execute(
                      "SELECT record_id, COUNT(*) AS open_n, "
                      "SUM(CASE WHEN due_date < ? THEN 1 ELSE 0 END) "
                      "AS late_n FROM lac_pep_actions WHERE status = 'Open' "
                      "GROUP BY record_id", (today.isoformat(),))}
    out: list[PEPDueRow] = []
    for rec in _wb.list_care_records(active_only=True):
        if rec.next_pep_due:
            if rec.next_pep_due > horizon:
                continue
            days = (today - _dt.date.fromisoformat(rec.next_pep_due)).days
            state = "Overdue" if days > 0 else "Due soon"
        elif rec.care_status == LAC and not rec.last_pep_on:
            days, state = None, "No PEP recorded"
        else:
            continue
        o, late = counts.get(rec.record_id, (0, 0))
        out.append(PEPDueRow(
            record_id=rec.record_id, student_id=rec.student_id,
            student_name=names.get(rec.student_id, "(unknown)"),
            care_status=rec.care_status,
            local_authority=rec.local_authority,
            designated_teacher=rec.designated_teacher,
            virtual_school_contact=rec.virtual_school_contact,
            last_pep_on=rec.last_pep_on, next_pep_due=rec.next_pep_due,
            state=state, days=days, open_actions=o,
            overdue_actions=late or 0))
    order = {"Overdue": 0, "No PEP recorded": 1, "Due soon": 2}
    out.sort(key=lambda r: (order[r.state], -(r.days or 0), r.student_name))
    return out


def care_file(record_id: int) -> CareFile:
    """One care record with its PEP reviews, actions, leaver plans and
    bursary applications."""
    init_db()
    rec = _wb.get_care_record(record_id)          # guards + logs
    if rec is None:
        raise ValidationError(f"No care record #{record_id}")
    with _connect() as conn:
        dt_id = _designated_id(conn, record_id)
        actions = _records.select(conn, PEP_ACTION_SPEC,
                                  equals={"record_id": record_id})
        plans = _records.select(conn, LEAVER_PLAN_SPEC,
                                equals={"record_id": record_id})
    return CareFile(
        record=rec,
        student_name=_people.student_names().get(rec.student_id,
                                                 "(unknown)"),
        designated_teacher=(_people.staff_label(dt_id)
                            or rec.designated_teacher),
        pep_reviews=_wb.list_pep_reviews(record_id),
        actions=actions, leaver_plans=plans,
        bursaries=_care_bursaries(rec.student_id))


def care_file_text(record_id: int) -> str:
    """:func:`care_file` as plain text for the detail window / CLI."""
    f = care_file(record_id)
    r = f.record
    lines = [
        f"Care record #{r.record_id} — {r.student_id} {f.student_name}",
        "",
        f"  Care status:        {r.care_status}",
        f"  Local authority:    {r.local_authority}",
        f"  Legal status:       {r.legal_status or '—'}",
        f"  Placement:          {r.placement_type or '—'}",
        f"  Dates:              {r.start_date or '?'} to "
        f"{r.end_date or 'current'}",
        f"  Social worker:      {r.social_worker or '—'} "
        f"{r.social_worker_phone or ''} {r.social_worker_email or ''}",
        f"  Personal adviser:   {r.personal_adviser or '—'}",
        f"  Virtual school:     {r.virtual_school_contact or '—'} "
        f"{r.virtual_school_phone or ''} {r.virtual_school_email or ''}",
        f"  Designated teacher: {f.designated_teacher or '—'}",
        f"  Last PEP / next:    {r.last_pep_on or '—'} / "
        f"{r.next_pep_due or '—'}"
        + ("  (OVERDUE)" if r.pep_overdue else ""),
        f"  16-19 bursary:      "
        f"{'eligible (vulnerable group)' if r.bursary_eligible else 'no'}",
        "", f"PEP reviews ({len(f.pep_reviews)}):"]
    for p in f.pep_reviews:
        lines.append(f"  #{p.review_id} {p.review_date}  next "
                     f"{p.next_review_due or '—'}  {p.targets or ''}"
                     .replace("\n", " / "))
    lines += ["", f"PEP actions ({len(f.actions)}):"]
    for a in f.actions:
        flag = " OVERDUE" if a.overdue else ""
        lines.append(f"  #{a.action_id} [{a.status}{flag}] due "
                     f"{a.due_date or '—'}  {a.owner or ''}: {a.action}"
                     .replace("\n", " / "))
    lines += ["", f"Care-leaver plans ({len(f.leaver_plans)}):"]
    for p in f.leaver_plans:
        lines.append(f"  #{p.plan_id} {p.plan_date} [{p.status}] adviser "
                     f"{p.personal_adviser or '—'}, accommodation "
                     f"{p.accommodation or '—'}, review {p.review_due or '—'}"
                     f", bursary app #{p.bursary_application_id or '—'}")
    lines += ["", f"Bursary applications under a care category "
              f"({len(f.bursaries)}):"]
    for b in f.bursaries:
        lines.append(f"  #{b.application_id} {b.academic_year or ''} "
                     f"{b.bursary_type} — {b.category} — {b.status}"
                     + (f" £{b.amount_awarded:,.2f}"
                        if b.amount_awarded else ""))
    return "\n".join(lines)


@dataclass
class RegisterSummary:
    by_status: dict[str, int] = field(default_factory=dict)
    by_local_authority: dict[str, int] = field(default_factory=dict)
    peps_overdue: int = 0
    no_pep: int = 0
    actions_open: int = 0
    actions_overdue: int = 0
    leaver_plans_active: int = 0
    leaver_reviews_overdue: int = 0
    bursary_gaps: int = 0
    designated_teacher: str | None = None


def summary() -> RegisterSummary:
    init_db()
    _guard("view looked-after summary")
    s = RegisterSummary()
    for rec in _wb.list_care_records(active_only=True):
        s.by_status[rec.care_status] = s.by_status.get(rec.care_status, 0) + 1
        s.by_local_authority[rec.local_authority] = (
            s.by_local_authority.get(rec.local_authority, 0) + 1)
    for row in pep_due_list(within_days=0):
        if row.state == "Overdue":
            s.peps_overdue += 1
        elif row.state == "No PEP recorded":
            s.no_pep += 1
    acts = list_pep_actions(open_only=True)
    s.actions_open = len(acts)
    s.actions_overdue = sum(1 for a in acts if a.overdue)
    plans = list_leaver_plans(active_only=True)
    s.leaver_plans_active = len(plans)
    s.leaver_reviews_overdue = sum(1 for p in plans if p.review_overdue)
    s.bursary_gaps = len(bursary_gaps())
    appt = current_designated_teacher()
    s.designated_teacher = _people.staff_label(appt.staff_id) if appt else None
    return s
