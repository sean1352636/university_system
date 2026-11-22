"""Appraisals & CPD: the appraisal cycle, lesson observations, training and
the statutory training every adult in school needs.

Kept from the old Appraisals window: one appraisal per member of staff per
cycle (now the academic year) with appraiser, job role, objectives-set /
mid-year / end-of-year review dates, self review, overall grade (1
Outstanding - 4 Unsatisfactory), upholding the Teachers' Standards, pay
progression (Yes, No, Deferred, Not Applicable, Pending), strengths, areas
to develop, CPD needs, appraiser's and appraisee's comments, status (Setting
Objectives ... Archived) and notes; objectives numbered per appraisal with
type, title, description, target, success criteria, progress notes,
mid-year progress, end-year evidence, status, reviewed on and weighting; the
lists (open only, mid-year overdue, per staff, by cycle) and the summary.

Kept from the old CPD window: the activity catalogue (title, provider,
type, dates, hours, cost, certificated, accreditor, location, capacity,
organiser, description, outcomes, status) and per-staff records (booked,
attended, hours, evaluation rating 1-5 with notes and impact on practice,
certificate received / filed / reference, cost to staff, status), with Mark
completed, Mark attended, Record evaluation, File certificate.

New:

* **Who sees what.** Staff see their own appraisal, observations, CPD and
  training; an appraiser sees their appraisees'; :data:`APPRAISAL_EDITORS`
  see and manage everything. The appraiser runs the reviews and objectives;
  the appraisee adds their comments, self review and progress on objectives.
* **The cycle.** :func:`start_cycle` opens an appraisal for every current
  member of staff, the appraiser defaulting to their line manager. Objectives
  must have success criteria before they're set; the end-of-year review needs
  an outcome and a pay progression recommendation.
* **Lesson observations** linked to the appraisal for that year, with focus,
  strengths, development points, a judgement and the teacher's response.
* **Training requests.** Any member of staff asks for a course (title,
  provider, dates, cost, cover needed); editors approve or decline against
  the year's CPD budget; after attending it is evaluated. :func:`cpd_log`
  is a person's CPD history; :func:`budget` shows used vs available.
* **Statutory training**: safeguarding / KCSIE (yearly), Prevent, first aid,
  fire marshal ... with expiry dates worked out and :func:`training_due`
  listing what is missing, overdue or due soon.
* Every change in ``appraisal_audit`` and the activity log (ids only).
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.modules.staff.domain import staff_directory as SD  # registers the FK target
from education_system.systems.secondary.core.permissions.access import (
    APPRAISAL_EDITORS,
    STAFF_ROLES,
    Principal,
)
from education_system.systems.secondary.core.academic_calendar.school_year import current_year, year_of
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = SD.ValidationError
PermissionDenied = SD.PermissionDenied
NotFound = SD.NotFound
_date, _choice, _text, _number, _bool = (SD.clean_date, SD.clean_choice, SD.clean_text,
                                         SD.clean_number, SD.clean_bool)

GRADES: tuple[int, ...] = (1, 2, 3, 4)
GRADE_LABELS = {1: "Outstanding", 2: "Good", 3: "Requires Improvement", 4: "Unsatisfactory"}
PAY_PROGRESSION: tuple[str, ...] = ("Yes", "No", "Deferred", "Not Applicable", "Pending")
DEFAULT_PAY_PROGRESSION = "Pending"
STATUSES: tuple[str, ...] = ("Setting Objectives", "In Progress", "Mid-Year Review",
                             "Awaiting End Year", "End Year Review", "Completed", "Closed",
                             "Archived")
DEFAULT_STATUS = "Setting Objectives"
CLOSED_STATUSES = frozenset({"Completed", "Closed", "Archived"})
OUTCOMES: tuple[str, ...] = ("Exceeded objectives", "Met objectives", "Partly met objectives",
                             "Did not meet objectives")
OBJECTIVE_TYPES: tuple[str, ...] = (
    "Pupil Outcomes", "Subject / Curriculum", "Pastoral", "Personal Development",
    "Whole-School Priority", "Department Priority", "Leadership", "CPD", "Other")
DEFAULT_OBJECTIVE_TYPE = "Pupil Outcomes"
OBJECTIVE_STATUSES: tuple[str, ...] = (
    "Not Started", "In Progress", "On Track", "At Risk", "Achieved", "Partially Achieved",
    "Not Achieved", "Removed")
DEFAULT_OBJECTIVE_STATUS = "Not Started"
MID_YEAR_AFTER_DAYS = 183

OBSERVATION_TYPES: tuple[str, ...] = ("Formal", "Informal / drop-in", "Learning walk", "Peer",
                                      "Coaching")
JUDGEMENTS: tuple[str, ...] = ("Highly effective", "Effective", "Developing",
                               "Requires support", "Not judged")

ACTIVITY_TYPES: tuple[str, ...] = (
    "Internal Training", "External Course", "Online Course", "Webinar", "Conference",
    "Seminar", "Workshop", "Twilight", "INSET Day", "Coaching / Mentoring",
    "Reading / Research", "Cross-School Visit", "Qualification", "Other")
DEFAULT_ACTIVITY_TYPE = "Internal Training"
ACTIVITY_STATUSES: tuple[str, ...] = ("Planned", "Confirmed", "Open for Booking", "Cancelled",
                                      "Completed", "Archived")
DEFAULT_ACTIVITY_STATUS = "Planned"
RECORD_STATUSES: tuple[str, ...] = (
    "Requested", "Approved", "Declined", "Booked", "Confirmed", "Attended", "Completed",
    "Cancelled", "No-Show")
DEFAULT_RECORD_STATUS = "Booked"
#: Statuses whose cost counts against the CPD budget.
SPENDING = frozenset({"Approved", "Booked", "Confirmed", "Attended", "Completed"})
GOING = frozenset({"Approved", "Booked", "Confirmed"})
DONE = frozenset({"Attended", "Completed"})
RATINGS: tuple[int, ...] = (1, 2, 3, 4, 5)
RATING_LABELS = {1: "Poor", 2: "Below Expectation", 3: "Good", 4: "Very Good", 5: "Excellent"}

#: Statutory / safety training and how long each lasts (months; None = no expiry).
TRAINING_TYPES: dict[str, int | None] = {
    "Safeguarding / KCSIE": 12, "Prevent": 24, "First aid at work": 36,
    "Emergency first aid": 36, "Paediatric first aid": 36, "Fire marshal": 36,
    "DSL training": 24, "Safer recruitment": 60, "Manual handling": 36, "Food hygiene": 36,
    "Other": None}
#: Every member of staff must have these.
REQUIRED_TRAINING: tuple[str, ...] = ("Safeguarding / KCSIE", "Prevent")
DUE_SOON_DAYS = 60


def grade_label(g: int | None) -> str:
    return "—" if g is None else GRADE_LABELS.get(g, "Unknown")


def rating_label(r: int | None) -> str:
    return "—" if r is None else RATING_LABELS.get(r, "Unknown")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS appraisals (
    appraisal_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id            INTEGER NOT NULL REFERENCES staff_members (staff_id),
    academic_year       TEXT NOT NULL,
    appraiser_id        INTEGER REFERENCES staff_members (staff_id) ON DELETE SET NULL,
    job_role            TEXT,
    objectives_set_on   TEXT,
    mid_year_review_on  TEXT,
    mid_year_notes      TEXT,
    end_year_review_on  TEXT,
    self_review_completed INTEGER NOT NULL DEFAULT 0,
    overall_grade       INTEGER CHECK (overall_grade IS NULL OR overall_grade BETWEEN 1 AND 4),
    upholding_standards INTEGER NOT NULL DEFAULT 1,
    outcome             TEXT,
    pay_progression     TEXT NOT NULL DEFAULT 'Pending',
    pay_notes           TEXT,
    strengths           TEXT,
    areas_to_develop    TEXT,
    cpd_needs           TEXT,
    appraiser_comments  TEXT,
    appraisee_comments  TEXT,
    status              TEXT NOT NULL DEFAULT 'Setting Objectives',
    notes               TEXT,
    created_by          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by          TEXT,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (staff_id, academic_year)
);
CREATE TABLE IF NOT EXISTS appraisal_objectives (
    objective_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    appraisal_id      INTEGER NOT NULL REFERENCES appraisals (appraisal_id) ON DELETE CASCADE,
    objective_number  INTEGER NOT NULL,
    objective_type    TEXT NOT NULL DEFAULT 'Pupil Outcomes',
    title             TEXT NOT NULL,
    description       TEXT,
    target_metric     TEXT,
    success_criteria  TEXT,
    progress_notes    TEXT,
    progress_percent  INTEGER CHECK (progress_percent IS NULL OR progress_percent BETWEEN 0 AND 100),
    mid_year_progress TEXT,
    end_year_evidence TEXT,
    status            TEXT NOT NULL DEFAULT 'Not Started',
    reviewed_on       TEXT,
    weighting         REAL,
    notes             TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS lesson_observations (
    observation_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id           INTEGER NOT NULL REFERENCES staff_members (staff_id),
    appraisal_id       INTEGER REFERENCES appraisals (appraisal_id) ON DELETE SET NULL,
    observer_id        INTEGER REFERENCES staff_members (staff_id) ON DELETE SET NULL,
    observed_on        TEXT NOT NULL,
    observation_type   TEXT NOT NULL DEFAULT 'Formal',
    class_observed     TEXT,
    focus              TEXT,
    strengths          TEXT,
    development_points TEXT,
    judgement          TEXT,
    feedback_given_on  TEXT,
    staff_response     TEXT,
    notes              TEXT,
    created_by         TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS cpd_activities (
    activity_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    provider      TEXT,
    activity_type TEXT NOT NULL DEFAULT 'Internal Training',
    activity_date TEXT NOT NULL,
    end_date      TEXT,
    hours         REAL,
    cost          REAL,
    certificated  INTEGER NOT NULL DEFAULT 0,
    accreditor    TEXT,
    location      TEXT,
    capacity      INTEGER,
    organiser     TEXT,
    description   TEXT,
    outcomes      TEXT,
    status        TEXT NOT NULL DEFAULT 'Planned',
    notes         TEXT,
    created_by    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS cpd_records (
    record_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id          INTEGER REFERENCES cpd_activities (activity_id) ON DELETE SET NULL,
    staff_id             INTEGER NOT NULL REFERENCES staff_members (staff_id),
    title                TEXT NOT NULL,
    provider             TEXT,
    start_date           TEXT,
    end_date             TEXT,
    cost                 REAL,
    cover_needed         INTEGER NOT NULL DEFAULT 0,
    cover_days           REAL,
    reason               TEXT,
    status               TEXT NOT NULL DEFAULT 'Booked',
    requested_by         TEXT,
    decided_by           TEXT,
    decided_at           TEXT,
    decision_note        TEXT,
    booked_on            TEXT,
    attended_on          TEXT,
    hours_completed      REAL,
    evaluation_rating    INTEGER CHECK (evaluation_rating IS NULL OR evaluation_rating BETWEEN 1 AND 5),
    evaluation_notes     TEXT,
    impact_on_practice   TEXT,
    certificate_received INTEGER NOT NULL DEFAULT 0,
    certificate_filed    INTEGER NOT NULL DEFAULT 0,
    certificate_ref      TEXT,
    cost_to_staff        REAL,
    notes                TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_cpd_records_staff ON cpd_records (staff_id);
CREATE TABLE IF NOT EXISTS cpd_budgets (
    academic_year TEXT PRIMARY KEY,
    amount        REAL NOT NULL CHECK (amount >= 0),
    set_by        TEXT,
    set_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS statutory_training (
    training_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id        INTEGER NOT NULL REFERENCES staff_members (staff_id),
    training_type   TEXT NOT NULL,
    completed_on    TEXT NOT NULL,
    expires_on      TEXT,
    provider        TEXT,
    certificate_ref TEXT,
    notes           TEXT,
    recorded_by     TEXT,
    recorded_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_statutory_training ON statutory_training (staff_id, training_type);
CREATE TABLE IF NOT EXISTS appraisal_audit (
    audit_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    kind      TEXT NOT NULL,
    record_id INTEGER,
    staff_id  INTEGER,
    action    TEXT NOT NULL,
    detail    TEXT,
    actor     TEXT NOT NULL,
    at        TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("appraisals", _SCHEMA)
for _t, _c, _l in (("appraisals", "staff_id", "appraisal(s)"),
                   ("appraisals", "appraiser_id", "appraisee(s)"),
                   ("lesson_observations", "staff_id", "lesson observation(s)"),
                   ("lesson_observations", "observer_id", "observation(s) made"),
                   ("cpd_records", "staff_id", "CPD record(s)"),
                   ("statutory_training", "staff_id", "training record(s)")):
    SD.register_reference(_t, _c, _l)


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Appraisal:
    appraisal_id: int
    staff_id: int
    academic_year: str
    appraiser_id: int | None
    job_role: str | None
    objectives_set_on: str | None
    mid_year_review_on: str | None
    mid_year_notes: str | None
    end_year_review_on: str | None
    self_review_completed: bool
    overall_grade: int | None
    upholding_standards: bool
    outcome: str | None
    pay_progression: str
    pay_notes: str | None
    strengths: str | None
    areas_to_develop: str | None
    cpd_needs: str | None
    appraiser_comments: str | None
    appraisee_comments: str | None
    status: str
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    staff_name: str = ""
    staff_code: str = ""
    appraiser_name: str | None = None
    objectives: int = 0

    @property
    def cycle(self) -> str:
        return self.academic_year

    @property
    def is_open(self) -> bool:
        return self.status not in CLOSED_STATUSES

    @property
    def grade_label(self) -> str:
        return grade_label(self.overall_grade)

    @property
    def mid_year_overdue(self) -> bool:
        if not self.is_open or self.mid_year_review_on or not self.objectives_set_on:
            return False
        due = _dt.date.fromisoformat(self.objectives_set_on) + _dt.timedelta(
            days=MID_YEAR_AFTER_DAYS)
        return _today() > due


@dataclass(frozen=True)
class Objective:
    objective_id: int
    appraisal_id: int
    objective_number: int
    objective_type: str
    title: str
    description: str | None
    target_metric: str | None
    success_criteria: str | None
    progress_notes: str | None
    progress_percent: int | None
    mid_year_progress: str | None
    end_year_evidence: str | None
    status: str
    reviewed_on: str | None
    weighting: float | None
    notes: str | None
    created_at: str


@dataclass(frozen=True)
class Observation:
    observation_id: int
    staff_id: int
    appraisal_id: int | None
    observer_id: int | None
    observed_on: str
    observation_type: str
    class_observed: str | None
    focus: str | None
    strengths: str | None
    development_points: str | None
    judgement: str | None
    feedback_given_on: str | None
    staff_response: str | None
    notes: str | None
    created_by: str | None
    created_at: str
    updated_at: str
    staff_name: str = ""
    observer_name: str | None = None


@dataclass(frozen=True)
class Activity:
    activity_id: int
    title: str
    provider: str | None
    activity_type: str
    activity_date: str
    end_date: str | None
    hours: float | None
    cost: float | None
    certificated: bool
    accreditor: str | None
    location: str | None
    capacity: int | None
    organiser: str | None
    description: str | None
    outcomes: str | None
    status: str
    notes: str | None
    created_by: str | None
    created_at: str
    updated_at: str
    records: int = 0

    @property
    def is_upcoming(self) -> bool:
        return self.activity_date >= _today().isoformat() and self.status not in (
            "Cancelled", "Completed", "Archived")


@dataclass(frozen=True)
class Record:
    record_id: int
    activity_id: int | None
    staff_id: int
    title: str
    provider: str | None
    start_date: str | None
    end_date: str | None
    cost: float | None
    cover_needed: bool
    cover_days: float | None
    reason: str | None
    status: str
    requested_by: str | None
    decided_by: str | None
    decided_at: str | None
    decision_note: str | None
    booked_on: str | None
    attended_on: str | None
    hours_completed: float | None
    evaluation_rating: int | None
    evaluation_notes: str | None
    impact_on_practice: str | None
    certificate_received: bool
    certificate_filed: bool
    certificate_ref: str | None
    cost_to_staff: float | None
    notes: str | None
    created_at: str
    updated_at: str
    staff_name: str = ""
    staff_code: str = ""

    @property
    def academic_year(self) -> str:
        return year_of(self.start_date or self.created_at[:10])

    @property
    def awaiting_certificate(self) -> bool:
        return self.status in DONE and not self.certificate_filed

    @property
    def needs_evaluation(self) -> bool:
        return self.status == "Attended" and self.evaluation_rating is None


@dataclass(frozen=True)
class Training:
    training_id: int
    staff_id: int
    training_type: str
    completed_on: str
    expires_on: str | None
    provider: str | None
    certificate_ref: str | None
    notes: str | None
    recorded_by: str | None
    recorded_at: str
    staff_name: str = ""

    @property
    def expired(self) -> bool:
        return bool(self.expires_on and self.expires_on < _today().isoformat())


_BOOLS = ("self_review_completed", "upholding_standards", "certificated", "cover_needed",
          "certificate_received", "certificate_filed")
_NAME = "coalesce({a}.preferred_name, {a}.first_name) || ' ' || {a}.last_name"


def _make(cls, r):
    keys = r.keys()
    d = {k: r[k] for k in cls.__dataclass_fields__ if k in keys}
    for k in _BOOLS:
        if k in d:
            d[k] = bool(d[k])
    return cls(**d)


_AP_SELECT = f"""
SELECT a.*, {_NAME.format(a='s')} AS staff_name, s.staff_code,
       {_NAME.format(a='r')} AS appraiser_name,
       (SELECT COUNT(*) FROM appraisal_objectives o WHERE o.appraisal_id = a.appraisal_id
        AND o.status != 'Removed') AS objectives
FROM appraisals a JOIN staff_members s ON s.staff_id = a.staff_id
LEFT JOIN staff_members r ON r.staff_id = a.appraiser_id
"""
_OB_SELECT = f"""
SELECT o.*, {_NAME.format(a='s')} AS staff_name, {_NAME.format(a='b')} AS observer_name
FROM lesson_observations o JOIN staff_members s ON s.staff_id = o.staff_id
LEFT JOIN staff_members b ON b.staff_id = o.observer_id
"""
_AC_SELECT = """
SELECT c.*, (SELECT COUNT(*) FROM cpd_records r WHERE r.activity_id = c.activity_id) AS records
FROM cpd_activities c
"""
_RC_SELECT = f"""
SELECT r.*, {_NAME.format(a='s')} AS staff_name, s.staff_code
FROM cpd_records r JOIN staff_members s ON s.staff_id = r.staff_id
"""
_TR_SELECT = f"""
SELECT t.*, {_NAME.format(a='s')} AS staff_name
FROM statutory_training t JOIN staff_members s ON s.staff_id = t.staff_id
"""


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in APPRAISAL_EDITORS


def _me_id(actor: Principal) -> int | None:
    m = SD.me(actor) if actor.role in STAFF_ROLES else None
    return m.staff_id if m else None


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"appraisals.{action}", target=target, outcome="denied",
                        principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can use Appraisals & CPD.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the appraisal / CPD lead can do that.")


def can_view_appraisal(actor: Principal, a: Appraisal) -> bool:
    me = _me_id(actor)
    return is_editor(actor) or (me is not None and me in (a.staff_id, a.appraiser_id))


def can_manage_appraisal(actor: Principal, a: Appraisal) -> bool:
    """The appraiser's side: reviews, objectives, grade, pay recommendation."""
    me = _me_id(actor)
    return is_editor(actor) or (me is not None and me == a.appraiser_id)


def is_appraisee(actor: Principal, a: Appraisal) -> bool:
    me = _me_id(actor)
    return me is not None and me == a.staff_id


def _appraisees(actor: Principal) -> set[int]:
    me = _me_id(actor)
    if me is None:
        return set()
    with database.connect() as conn:
        return {r[0] for r in conn.execute("SELECT staff_id FROM appraisals WHERE appraiser_id = ?",
                                           (me,))}


def is_appraiser(actor: Principal) -> bool:
    """Appraises anyone (or is the lead) - the appraiser's buttons are for them."""
    return is_editor(actor) or bool(_appraisees(actor))


def _audit(conn, kind: str, action: str, actor: Principal, record_id: int | None,
           staff_id: int | None, **detail: Any) -> None:
    conn.execute("INSERT INTO appraisal_audit (kind, record_id, staff_id, action, detail, actor) "
                 "VALUES (?, ?, ?, ?, ?, ?)",
                 (kind, record_id, staff_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(*, kind: str | None = None, record_id: int | None = None,
            staff_id: int | None = None, limit: int = 300) -> list[dict[str, Any]]:
    sql, where, params = "SELECT * FROM appraisal_audit", [], []
    for col, val in (("kind", kind), ("record_id", record_id), ("staff_id", staff_id)):
        if val is not None:
            where.append(f"{col} = ?")
            params.append(val)
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [{"at": r["at"], "kind": r["kind"], "record_id": r["record_id"],
                 "staff_id": r["staff_id"], "action": r["action"], "actor": r["actor"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


def _update_row(table: str, key: str, ident: int, values: dict[str, Any],
                stamp: str | None = "updated_at") -> None:
    if not values:
        return
    sets = ", ".join(f"{k} = ?" for k in values)
    if stamp:
        sets += f", {stamp} = datetime('now')"
    with database.connect() as conn:
        conn.execute(f"UPDATE {table} SET {sets} WHERE {key} = ?",  # nosec B608 - fixed names
                     (*(int(v) if isinstance(v, bool) else v for v in values.values()), ident))


def _staff(value: Any, label: str, problems: list[str], *, current_only: bool = True
           ) -> SD.StaffMember | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    m = SD.find(value)
    if m is None:
        problems.append(f"{label}: no staff record {value}")
    elif current_only and m.is_leaver:
        problems.append(f"{label}: {m.full_name} has left")
    return m


def _year(value: Any, problems: list[str]) -> str:
    v = str(value or "").strip() or current_year()
    if len(v) != 7 or v[4] != "/" or not (v[:4].isdigit() and v[5:].isdigit()) or \
            (int(v[:4]) + 1) % 100 != int(v[5:]):
        problems.append("Academic year looks like 2026/27")
    return v


# ── Appraisals ───────────────────────────────────────────────────────

def get_appraisal(appraisal_id: int, *, actor: Principal | None = None) -> Appraisal:
    with database.connect() as conn:
        r = conn.execute(_AP_SELECT + " WHERE a.appraisal_id = ?",
                         (int(appraisal_id),)).fetchone()
    if r is None:
        raise NotFound(f"No appraisal {appraisal_id}")
    a = _make(Appraisal, r)
    if actor is not None and not can_view_appraisal(actor, a):
        _deny(actor, "view", a.appraisal_id, "That appraisal isn't yours to see.")
    return a


def list_appraisals(*, actor: Principal, academic_year: str | None = None,
                    staff_id: int | None = None, status: str | None = None,
                    open_only: bool = False, mid_year_overdue: bool = False,
                    appraiser_id: int | None = None) -> list[Appraisal]:
    """What *actor* may see: everything for editors, else their own and their
    appraisees'."""
    _require_staff(actor, "list")
    sql, params = _AP_SELECT + " WHERE 1=1", []
    for col, val in (("a.academic_year", academic_year), ("a.status", status)):
        if val:
            sql += f" AND {col} = ?"
            params.append(val)
    for col, val in (("a.staff_id", staff_id), ("a.appraiser_id", appraiser_id)):
        if val is not None:
            sql += f" AND {col} = ?"
            params.append(int(val))
    if not is_editor(actor):
        me = _me_id(actor)
        if me is None:
            return []
        sql += " AND (a.staff_id = ? OR a.appraiser_id = ?)"
        params += [me, me]
    with database.connect() as conn:
        rows = [_make(Appraisal, r) for r in conn.execute(
            sql + " ORDER BY a.academic_year DESC, s.last_name COLLATE NOCASE", params)]
    if open_only:
        rows = [a for a in rows if a.is_open]
    if mid_year_overdue:
        rows = [a for a in rows if a.mid_year_overdue]
    return rows


def list_cycles() -> list[str]:
    with database.connect() as conn:
        years = {r[0] for r in conn.execute("SELECT DISTINCT academic_year FROM appraisals")}
    return sorted(years | {current_year()}, reverse=True)


A_FIELDS = ("appraiser_id", "job_role", "objectives_set_on", "mid_year_review_on",
            "mid_year_notes", "end_year_review_on", "self_review_completed", "overall_grade",
            "upholding_standards", "outcome", "pay_progression", "pay_notes", "strengths",
            "areas_to_develop", "cpd_needs", "appraiser_comments", "appraisee_comments",
            "status", "notes")
#: What the appraisee changes on their own appraisal.
APPRAISEE_FIELDS = frozenset({"appraisee_comments", "self_review_completed"})


def _clean_appraisal(data: dict[str, Any], current: Appraisal | None, staff_id: int
                     ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in A_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in A_FIELDS})
    out: dict[str, Any] = {}
    ap = merged.get("appraiser_id")
    if current is not None and ap == current.appraiser_id:
        out["appraiser_id"] = ap
    else:
        m = _staff(ap, "Appraiser", problems)
        out["appraiser_id"] = m.staff_id if m else None
    if out["appraiser_id"] == staff_id:
        problems.append("Someone can't appraise themselves")
    out["job_role"] = _text(merged.get("job_role"), 100)
    for k, label in (("objectives_set_on", "Objectives set on"),
                     ("mid_year_review_on", "Mid-year review"),
                     ("end_year_review_on", "End-year review")):
        out[k] = _date(merged.get(k), label, problems)
    if out["mid_year_review_on"] and out["objectives_set_on"] and \
            out["mid_year_review_on"] < out["objectives_set_on"]:
        problems.append("The mid-year review can't be before the objectives were set")
    if out["end_year_review_on"] and out["mid_year_review_on"] and \
            out["end_year_review_on"] < out["mid_year_review_on"]:
        problems.append("The end-year review can't be before the mid-year review")
    out["self_review_completed"] = _bool(merged.get("self_review_completed"))
    out["upholding_standards"] = _bool(merged.get("upholding_standards", True)
                                       if current is None else merged.get("upholding_standards"))
    g = merged.get("overall_grade")
    if g in (None, ""):
        out["overall_grade"] = None
    else:
        try:
            out["overall_grade"] = int(str(g).strip()[:1])
            if out["overall_grade"] not in GRADES:
                raise ValueError
        except ValueError:
            problems.append("Overall grade must be 1-4")
            out["overall_grade"] = None
    oc = _text(merged.get("outcome"), 60)
    out["outcome"] = _choice(oc, OUTCOMES, "Outcome", problems, None) if oc else None
    out["pay_progression"] = _choice(merged.get("pay_progression"), PAY_PROGRESSION,
                                     "Pay progression", problems, DEFAULT_PAY_PROGRESSION)
    out["status"] = _choice(merged.get("status"), STATUSES, "Status", problems, DEFAULT_STATUS)
    for k in ("mid_year_notes", "pay_notes", "strengths", "areas_to_develop", "cpd_needs",
              "appraiser_comments", "appraisee_comments", "notes"):
        out[k] = _text(merged.get(k), 4000)
    return out, problems


def create_appraisal(data: dict[str, Any], *, actor: Principal) -> Appraisal:
    """The old New appraisal. The appraiser defaults to the line manager."""
    _require_editor(actor, "create")
    problems: list[str] = []
    m = _staff(data.get("staff_id") or data.get("staff"), "Staff", problems)
    if m is None and not problems:
        problems.append("Staff is required")
    year = _year(data.get("academic_year") or data.get("cycle"), problems)
    if m is None:
        raise ValidationError(problems)
    data = dict(data)
    if data.get("appraiser_id") in (None, "") and m.line_manager_id:
        data["appraiser_id"] = m.line_manager_id
    if not data.get("job_role"):
        data["job_role"] = m.job_title or m.role
    c, more = _clean_appraisal(data, None, m.staff_id)
    problems += more
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM appraisals WHERE staff_id = ? AND academic_year = ?",
                        (m.staff_id, year)).fetchone():
            problems.append(f"{m.full_name} already has an appraisal for {year}")
        if problems:
            raise ValidationError(problems)
        aid = conn.execute(
            f"INSERT INTO appraisals (staff_id, academic_year, {', '.join(A_FIELDS)}, "  # nosec B608 - fixed
            f"created_by, updated_by) VALUES (?, ?, {', '.join('?' * len(A_FIELDS))}, ?, ?)",
            (m.staff_id, year, *(int(c[k]) if isinstance(c[k], bool) else c[k]
                                 for k in A_FIELDS), actor.username, actor.username)).lastrowid
        _audit(conn, "appraisal", "create", actor, aid, m.staff_id, year=year)
    activity_log.record("appraisals.create", target=aid, principal=actor)
    return get_appraisal(aid)


def start_cycle(academic_year: str | None = None, *, actor: Principal) -> dict[str, Any]:
    """An appraisal for every current member of staff who hasn't one this year.
    Returns {"created": [...], "no_appraiser": [names]}."""
    _require_editor(actor, "start_cycle")
    problems: list[str] = []
    year = _year(academic_year, problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        have = {r[0] for r in conn.execute("SELECT staff_id FROM appraisals WHERE "
                                           "academic_year = ?", (year,))}
    made, no_appraiser = [], []
    for m in SD.list_staff():
        if m.staff_id in have or not m.is_active:
            continue
        a = create_appraisal({"staff_id": m.staff_id, "academic_year": year}, actor=actor)
        made.append(a)
        if a.appraiser_id is None:
            no_appraiser.append(m.full_name)
    return {"created": made, "no_appraiser": no_appraiser}


def update_appraisal(appraisal_id: int, changes: dict[str, Any], *, actor: Principal
                     ) -> Appraisal:
    """The old Edit. The appraisee may change only their comments and self review."""
    cur = get_appraisal(appraisal_id, actor=actor)
    keys = {k for k in changes if k in A_FIELDS}
    if not can_manage_appraisal(actor, cur):
        if not (is_appraisee(actor, cur) and keys <= APPRAISEE_FIELDS):
            _deny(actor, "update", cur.appraisal_id,
                  "Only the appraiser or the appraisal lead can change that.")
    if "appraiser_id" in keys and not is_editor(actor):
        _deny(actor, "update", cur.appraisal_id, "Only the appraisal lead changes the appraiser.")
    c, problems = _clean_appraisal(changes, cur, cur.staff_id)
    if problems:
        raise ValidationError(problems)
    changed = {k: c[k] for k in A_FIELDS if c[k] != getattr(cur, k)}
    if not changed:
        return cur
    _update_row("appraisals", "appraisal_id", cur.appraisal_id,
                {**changed, "updated_by": actor.username})
    with database.connect() as conn:
        _audit(conn, "appraisal", "update", actor, cur.appraisal_id, cur.staff_id,
               fields=sorted(changed))
    activity_log.record("appraisals.update", target=cur.appraisal_id, principal=actor,
                        fields=sorted(changed))
    return get_appraisal(cur.appraisal_id)


def _manage(appraisal_id: int, actor: Principal, action: str) -> Appraisal:
    a = get_appraisal(appraisal_id, actor=actor)
    if not can_manage_appraisal(actor, a):
        _deny(actor, action, a.appraisal_id, "Only the appraiser or the appraisal lead can "
                                             "do that.")
    if not a.is_open:
        raise ValidationError([f"The appraisal is {a.status.lower()}"])
    return a


def set_objectives(appraisal_id: int, *, actor: Principal, on: str | None = None) -> Appraisal:
    """The old Set objectives date. Needs objectives, each with success criteria."""
    a = _manage(appraisal_id, actor, "objectives_set")
    objs = [o for o in list_objectives(a.appraisal_id) if o.status != "Removed"]
    problems: list[str] = []
    if not objs:
        problems.append("Add the objectives first")
    problems += [f"Objective {o.objective_number} needs success criteria" for o in objs
                 if not o.success_criteria]
    day = _date(on, "Date", problems) or _today().isoformat()
    if problems:
        raise ValidationError(problems)
    return update_appraisal(a.appraisal_id, {
        "objectives_set_on": day,
        "status": "In Progress" if a.status == "Setting Objectives" else a.status}, actor=actor)


def record_mid_year(appraisal_id: int, *, actor: Principal, reviewed_on: str | None = None,
                    notes: str | None = None) -> Appraisal:
    a = _manage(appraisal_id, actor, "mid_year")
    if not a.objectives_set_on:
        raise ValidationError(["Set the objectives before the mid-year review"])
    changes: dict[str, Any] = {"mid_year_review_on": reviewed_on or _today().isoformat(),
                               "status": "Awaiting End Year"}
    if notes is not None:
        changes["mid_year_notes"] = notes
    return update_appraisal(a.appraisal_id, changes, actor=actor)


def record_end_year(appraisal_id: int, *, actor: Principal, reviewed_on: str | None = None,
                    overall_grade: Any = None, pay_progression: str | None = None,
                    upholding_standards: bool | None = None, outcome: str | None = None,
                    strengths: str | None = None, areas_to_develop: str | None = None,
                    cpd_needs: str | None = None, appraiser_comments: str | None = None,
                    pay_notes: str | None = None) -> Appraisal:
    """The old End-year review; now needs an outcome and a pay recommendation."""
    a = _manage(appraisal_id, actor, "end_year")
    problems: list[str] = []
    if not a.objectives_set_on:
        problems.append("Objectives were never set")
    if not (outcome or a.outcome):
        problems.append("Choose the outcome")
    pay = pay_progression or a.pay_progression
    if pay == "Pending":
        problems.append("Make the pay progression recommendation")
    if problems:
        raise ValidationError(problems)
    changes: dict[str, Any] = {"end_year_review_on": reviewed_on or _today().isoformat(),
                               "pay_progression": pay, "status": "Completed"}
    for k, v in (("overall_grade", overall_grade), ("upholding_standards", upholding_standards),
                 ("outcome", outcome), ("strengths", strengths),
                 ("areas_to_develop", areas_to_develop), ("cpd_needs", cpd_needs),
                 ("appraiser_comments", appraiser_comments), ("pay_notes", pay_notes)):
        if v is not None:
            changes[k] = v
    return update_appraisal(a.appraisal_id, changes, actor=actor)


def close_appraisal(appraisal_id: int, *, actor: Principal) -> Appraisal:
    a = get_appraisal(appraisal_id, actor=actor)
    if not can_manage_appraisal(actor, a):
        _deny(actor, "close", a.appraisal_id, "Only the appraiser or the lead can close it.")
    return update_appraisal(a.appraisal_id, {"status": "Closed"}, actor=actor)


def set_appraisal_status(appraisal_id: int, status: str, *, actor: Principal) -> Appraisal:
    a = get_appraisal(appraisal_id, actor=actor)
    if not can_manage_appraisal(actor, a):
        _deny(actor, "status", a.appraisal_id, "Only the appraiser or the lead can do that.")
    problems: list[str] = []
    st = _choice(status, STATUSES, "Status", problems, None)
    if problems or st is None:
        raise ValidationError(problems or ["Choose a status"])
    return update_appraisal(a.appraisal_id, {"status": st}, actor=actor)


def delete_appraisal(appraisal_id: int, *, actor: Principal) -> bool:
    a = get_appraisal(appraisal_id)
    _require_editor(actor, "delete", a.appraisal_id)
    if a.end_year_review_on:
        raise ValidationError(["A reviewed appraisal is kept - archive it instead"])
    with database.connect() as conn:
        conn.execute("DELETE FROM appraisals WHERE appraisal_id = ?", (a.appraisal_id,))
        _audit(conn, "appraisal", "delete", actor, a.appraisal_id, a.staff_id)
    activity_log.record("appraisals.delete", target=a.appraisal_id, principal=actor)
    return True


# ── Objectives ───────────────────────────────────────────────────────

O_FIELDS = ("objective_type", "title", "description", "target_metric", "success_criteria",
            "progress_notes", "progress_percent", "mid_year_progress", "end_year_evidence",
            "status", "reviewed_on", "weighting", "notes")
#: What the appraisee updates on their own objectives.
APPRAISEE_OBJECTIVE_FIELDS = frozenset({"progress_notes", "progress_percent"})


def get_objective(objective_id: int) -> Objective:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM appraisal_objectives WHERE objective_id = ?",
                         (int(objective_id),)).fetchone()
    if r is None:
        raise NotFound(f"No objective {objective_id}")
    return _make(Objective, r)


def list_objectives(appraisal_id: int, *, actor: Principal | None = None) -> list[Objective]:
    if actor is not None:
        get_appraisal(appraisal_id, actor=actor)
    with database.connect() as conn:
        return [_make(Objective, r) for r in conn.execute(
            "SELECT * FROM appraisal_objectives WHERE appraisal_id = ? ORDER BY objective_number",
            (int(appraisal_id),))]


def objective_count(appraisal_id: int) -> int:
    return sum(1 for o in list_objectives(appraisal_id) if o.status != "Removed")


def _clean_objective(data: dict[str, Any], current: Objective | None
                     ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in O_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in O_FIELDS})
    out: dict[str, Any] = {
        "objective_type": _choice(merged.get("objective_type"), OBJECTIVE_TYPES, "Type",
                                  problems, DEFAULT_OBJECTIVE_TYPE),
        "status": _choice(merged.get("status"), OBJECTIVE_STATUSES, "Status", problems,
                          DEFAULT_OBJECTIVE_STATUS),
        "title": _text(merged.get("title"), 200),
        "reviewed_on": _date(merged.get("reviewed_on"), "Reviewed on", problems)}
    if not out["title"]:
        problems.append("Title is required")
    for k in ("description", "target_metric", "success_criteria", "progress_notes",
              "mid_year_progress", "end_year_evidence", "notes"):
        out[k] = _text(merged.get(k), 4000)
    pct = _number(merged.get("progress_percent"), "Progress %", problems, 0, 100)
    out["progress_percent"] = int(pct) if pct is not None else None
    out["weighting"] = _number(merged.get("weighting"), "Weighting", problems, 0, 100)
    return out, problems


def add_objective(appraisal_id: int, data: dict[str, Any], *, actor: Principal) -> Objective:
    a = _manage(appraisal_id, actor, "objective_add")
    c, problems = _clean_objective(data, None)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        n = conn.execute("SELECT coalesce(MAX(objective_number), 0) + 1 FROM "
                         "appraisal_objectives WHERE appraisal_id = ?",
                         (a.appraisal_id,)).fetchone()[0]
        oid = conn.execute(
            f"INSERT INTO appraisal_objectives (appraisal_id, objective_number, "  # nosec B608 - fixed
            f"{', '.join(O_FIELDS)}) VALUES (?, ?, {', '.join('?' * len(O_FIELDS))})",
            (a.appraisal_id, n, *(c[k] for k in O_FIELDS))).lastrowid
        _audit(conn, "objective", "create", actor, oid, a.staff_id, appraisal=a.appraisal_id)
    return get_objective(oid)


def update_objective(objective_id: int, changes: dict[str, Any], *, actor: Principal
                     ) -> Objective:
    """The appraiser / lead change anything; the appraisee their progress."""
    cur = get_objective(objective_id)
    a = get_appraisal(cur.appraisal_id, actor=actor)
    keys = {k for k in changes if k in O_FIELDS}
    if not can_manage_appraisal(actor, a) and not (
            is_appraisee(actor, a) and keys <= APPRAISEE_OBJECTIVE_FIELDS):
        _deny(actor, "objective_update", cur.objective_id,
              "Only the appraiser or the lead can change that objective.")
    c, problems = _clean_objective(changes, cur)
    if problems:
        raise ValidationError(problems)
    changed = {k: c[k] for k in O_FIELDS if c[k] != getattr(cur, k)}
    _update_row("appraisal_objectives", "objective_id", cur.objective_id, changed, stamp=None)
    if changed:
        with database.connect() as conn:
            _audit(conn, "objective", "update", actor, cur.objective_id, a.staff_id,
                   fields=sorted(changed))
    return get_objective(cur.objective_id)


def set_objective_status(objective_id: int, status: str, *, actor: Principal,
                         reviewed_on: str | None = None) -> Objective:
    return update_objective(objective_id, {"status": status,
                                           "reviewed_on": reviewed_on or _today().isoformat()},
                            actor=actor)


def delete_objective(objective_id: int, *, actor: Principal) -> bool:
    cur = get_objective(objective_id)
    a = _manage(cur.appraisal_id, actor, "objective_delete")
    if a.objectives_set_on:
        raise ValidationError(["Objectives have been set - mark it Removed instead"])
    with database.connect() as conn:
        conn.execute("DELETE FROM appraisal_objectives WHERE objective_id = ?",
                     (cur.objective_id,))
        _audit(conn, "objective", "delete", actor, cur.objective_id, a.staff_id)
    return True


def appraisal_text(appraisal_id: int, *, actor: Principal) -> str:
    a = get_appraisal(appraisal_id, actor=actor)
    lines = [f"Appraisal #{a.appraisal_id} - {a.staff_name} ({a.staff_code}), {a.academic_year}"]
    for label, v in (("Appraiser", a.appraiser_name), ("Job role", a.job_role),
                     ("Status", a.status), ("Objectives set", a.objectives_set_on),
                     ("Mid-year review", a.mid_year_review_on
                      + (" (OVERDUE)" if a.mid_year_overdue else "") if a.mid_year_review_on
                      else ("OVERDUE" if a.mid_year_overdue else None)),
                     ("Mid-year notes", a.mid_year_notes),
                     ("End-year review", a.end_year_review_on),
                     ("Self review", "complete" if a.self_review_completed else "not yet"),
                     ("Overall grade", f"{a.overall_grade or '—'} ({a.grade_label})"),
                     ("Upholding standards", "yes" if a.upholding_standards else "no"),
                     ("Outcome", a.outcome), ("Pay progression", a.pay_progression),
                     ("Pay notes", a.pay_notes), ("Strengths", a.strengths),
                     ("Areas to develop", a.areas_to_develop), ("CPD needs", a.cpd_needs),
                     ("Appraiser comments", a.appraiser_comments),
                     ("Appraisee comments", a.appraisee_comments), ("Notes", a.notes)):
        if v not in (None, ""):
            lines.append(f"  {label + ':':<22} {v}")
    lines.append("")
    lines.append("Objectives:")
    for o in list_objectives(a.appraisal_id):
        lines.append(f"  {o.objective_number}. [{o.status}] {o.title} ({o.objective_type})"
                     + (f" - {o.progress_percent}%" if o.progress_percent is not None else ""))
        for label, v in (("Success criteria", o.success_criteria), ("Target", o.target_metric),
                         ("Progress", o.progress_notes), ("Mid-year", o.mid_year_progress),
                         ("Evidence", o.end_year_evidence)):
            if v:
                lines.append(f"       {label}: {v}")
    obs = list_observations(actor=actor, appraisal_id=a.appraisal_id)
    if obs:
        lines += ["", "Lesson observations:"]
        lines += [f"  {o.observed_on} {o.observation_type} by {o.observer_name or '-'}: "
                  f"{o.judgement or '-'}" for o in obs]
    return "\n".join(lines)


# ── Lesson observations ──────────────────────────────────────────────

def can_observe(actor: Principal, staff_id: int) -> bool:
    return is_editor(actor) or staff_id in _appraisees(actor)


def get_observation(observation_id: int, *, actor: Principal | None = None) -> Observation:
    with database.connect() as conn:
        r = conn.execute(_OB_SELECT + " WHERE o.observation_id = ?",
                         (int(observation_id),)).fetchone()
    if r is None:
        raise NotFound(f"No observation {observation_id}")
    o = _make(Observation, r)
    if actor is not None and not _can_see_observation(actor, o):
        _deny(actor, "observation_view", o.observation_id, "That observation isn't yours to see.")
    return o


def _can_see_observation(actor: Principal, o: Observation) -> bool:
    me = _me_id(actor)
    return is_editor(actor) or (me is not None and (me in (o.staff_id, o.observer_id)
                                                    or o.staff_id in _appraisees(actor)))


def list_observations(*, actor: Principal, staff_id: int | None = None,
                      appraisal_id: int | None = None, academic_year: str | None = None
                      ) -> list[Observation]:
    _require_staff(actor, "observations")
    sql, params = _OB_SELECT + " WHERE 1=1", []
    for col, val in (("o.staff_id", staff_id), ("o.appraisal_id", appraisal_id)):
        if val is not None:
            sql += f" AND {col} = ?"
            params.append(int(val))
    with database.connect() as conn:
        rows = [_make(Observation, r) for r in conn.execute(
            sql + " ORDER BY o.observed_on DESC", params)]
    if academic_year:
        rows = [o for o in rows if year_of(o.observed_on) == academic_year]
    return [o for o in rows if _can_see_observation(actor, o)]


OB_FIELDS = ("observed_on", "observation_type", "class_observed", "focus", "strengths",
             "development_points", "judgement", "feedback_given_on", "notes")


def _clean_observation(data: dict[str, Any], current: Observation | None
                       ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in OB_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in OB_FIELDS})
    out: dict[str, Any] = {
        "observed_on": _date(merged.get("observed_on"), "Date", problems)
        or _today().isoformat(),
        "observation_type": _choice(merged.get("observation_type"), OBSERVATION_TYPES, "Type",
                                    problems, "Formal"),
        "feedback_given_on": _date(merged.get("feedback_given_on"), "Feedback given",
                                   problems)}
    j = _text(merged.get("judgement"), 40)
    out["judgement"] = _choice(j, JUDGEMENTS, "Judgement", problems, None) if j else None
    out["class_observed"] = _text(merged.get("class_observed"), 60)
    for k in ("focus", "strengths", "development_points", "notes"):
        out[k] = _text(merged.get(k), 4000)
    if out["observed_on"] > _today().isoformat():
        problems.append("An observation is recorded after it happens")
    if out["feedback_given_on"] and out["feedback_given_on"] < out["observed_on"]:
        problems.append("Feedback can't be before the observation")
    return out, problems


def add_observation(data: dict[str, Any], *, actor: Principal) -> Observation:
    """Linked to the observed teacher's appraisal for that year, if any."""
    _require_staff(actor, "observation_add")
    problems: list[str] = []
    m = _staff(data.get("staff_id") or data.get("staff"), "Teacher", problems)
    if m is None and not problems:
        problems.append("Choose who was observed")
    if m is None:
        raise ValidationError(problems)
    if not can_observe(actor, m.staff_id):
        _deny(actor, "observation_add", m.staff_code,
              "Only their appraiser or the appraisal lead records observations.")
    obs = _staff(data.get("observer_id") or data.get("observer"), "Observer", problems)
    observer = obs.staff_id if obs else _me_id(actor)
    if observer == m.staff_id:
        problems.append("Someone can't observe their own lesson")
    c, more = _clean_observation(data, None)
    problems += more
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        r = conn.execute("SELECT appraisal_id FROM appraisals WHERE staff_id = ? AND "
                         "academic_year = ?", (m.staff_id, year_of(c["observed_on"]))).fetchone()
        oid = conn.execute(
            f"INSERT INTO lesson_observations (staff_id, appraisal_id, observer_id, "  # nosec B608 - fixed
            f"{', '.join(OB_FIELDS)}, created_by) VALUES (?, ?, ?, "
            f"{', '.join('?' * len(OB_FIELDS))}, ?)",
            (m.staff_id, r[0] if r else None, observer, *(c[k] for k in OB_FIELDS),
             actor.username)).lastrowid
        _audit(conn, "observation", "create", actor, oid, m.staff_id)
    activity_log.record("appraisals.observation", target=oid, principal=actor)
    return get_observation(oid)


def update_observation(observation_id: int, changes: dict[str, Any], *, actor: Principal
                       ) -> Observation:
    """The observer / lead change the record; the teacher adds their response."""
    cur = get_observation(observation_id, actor=actor)
    me = _me_id(actor)
    keys = set(changes)
    if keys == {"staff_response"}:
        if me != cur.staff_id and not is_editor(actor):
            _deny(actor, "observation_update", cur.observation_id,
                  "Only the teacher observed adds a response.")
        _update_row("lesson_observations", "observation_id", cur.observation_id,
                    {"staff_response": _text(changes["staff_response"], 4000)})
    else:
        if not (is_editor(actor) or (me is not None and me == cur.observer_id)):
            _deny(actor, "observation_update", cur.observation_id,
                  "Only the observer or the appraisal lead can change it.")
        c, problems = _clean_observation(changes, cur)
        if problems:
            raise ValidationError(problems)
        _update_row("lesson_observations", "observation_id", cur.observation_id,
                    {k: c[k] for k in OB_FIELDS if c[k] != getattr(cur, k)})
    with database.connect() as conn:
        _audit(conn, "observation", "update", actor, cur.observation_id, cur.staff_id,
               fields=sorted(keys))
    return get_observation(cur.observation_id)


def delete_observation(observation_id: int, *, actor: Principal) -> bool:
    cur = get_observation(observation_id)
    _require_editor(actor, "observation_delete", cur.observation_id)
    with database.connect() as conn:
        conn.execute("DELETE FROM lesson_observations WHERE observation_id = ?",
                     (cur.observation_id,))
        _audit(conn, "observation", "delete", actor, cur.observation_id, cur.staff_id)
    return True
