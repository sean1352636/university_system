"""SEND: the SENCO's register, plans, reviews, provision map and access.

Built on what the school already keeps - the census SEN status on the pupil
record (N none, K SEN support, E EHC plan) and the SEN details beside it
(:mod:`modules.pupils.domain.sen_details`: areas of need, EHC plan reference
and issue date, provision, strategies, exam access, notes). Nothing here is
a second copy of those.

Kept from the old SEND window:

* The register: provision stage (No SEN, Monitoring, SEN Support, EHCP,
  EHCP assessment in progress), primary and secondary need, status (Active,
  Discharged, Transitioned, On hold), SENCo, keyworker, parent contact (from
  the pupil's contacts), EHCP reference, start date, next review, provision
  summary, diagnosis and notes. The stage is the pupil's SEN status (plus a
  "monitoring" flag and the EHC needs assessment); the needs, plan reference,
  provision and notes are the SEN details.
* Reviews (date, reviewer, progress, adjustments, outcome, next review,
  notes); the record summary; the cohort summary (total, by stage / primary
  need / status, EHCP count); overdue reviews.
* The old Accessibility arrangements (reasonable adjustments and exam access
  arrangements: type, category, description, exam only, dates, status,
  evidence source and reference, approved by / on, review date, notes),
  their status, the expired list and their summary.

New:

* **Who.** :data:`SEND_EDITORS` (the SENCO) changes everything; all staff
  read the register and the strategies (teachers need them). Every change is
  in ``send_audit`` and the activity log (ids only - never needs or names).
* **Plans** - SEN support plans and pupil passports run in assess - plan -
  do - review cycles: reviewing a plan records the review and starts the
  next cycle with the outcomes carried over.
* **EHC plans** - the annual review is due 12 months from the plan's issue
  or the last annual review; the review report goes to the local authority
  within 2 weeks of the meeting and the authority decides (maintain, amend,
  cease) within 4 weeks. An EHC needs assessment request is tracked to the
  6-week decision and the 20-week final plan.
* **Provision map** - provision per pupil with hours, weeks and cost (per
  hour shared across the group, or a fixed cost), and the map by provision.
* **Exam access** - JCQ Form 8 evidence must come from an assessment no
  earlier than the start of Year 9.
* **External agencies** - referrals, appointments, reports.
* **Due** - every overdue or upcoming review across the school.
* **Reports** - pupils by primary need and year, SEN support vs EHC plan by
  year, by broad area of need; CSV export.
* **Families** - an invitation to a review meeting and the plan, e-mailed to
  contacts with parental responsibility.
"""

from __future__ import annotations

import csv
import datetime as _dt
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.send.domain import send_access as _SA
from education_system.systems.secondary.modules.send.domain.send_access import (  # noqa: F401
    ACCESS_CATEGORIES,
    ACCESS_STATUSES,
    ACCESS_TYPES,
    AGENCIES,
    AGENCY_STATUSES,
    EVIDENCE_SOURCES,
    EXAM_ACCESS,
    FORM_8,
    Agency,
    Arrangement,
    access_summary,
    add_agency,
    add_arrangement,
    copy_exam_access,
    delete_agency,
    delete_arrangement,
    exam_access_text,
    expire_overdue,
    expired_arrangements,
    get_agency,
    get_arrangement,
    list_agencies,
    list_arrangements,
    set_arrangement_status,
    update_agency,
    update_arrangement,
    year9_start,
)
from education_system.systems.secondary.modules.send.domain.send_common import (  # noqa: F401
    PUPIL_COLS as _PUPIL_COLS,
)
from education_system.systems.secondary.modules.send.domain.send_common import (  # noqa: F401
    _audit,
    _blank,
    _bool,
    _choice,
    _date,
    _make,
    _name,
    _need_pupil,
    _number,
    _plus,
    _pupil,
    _require_editor,
    _require_staff,
    _text,
    add_months,
    history,
    is_editor,
)
from education_system.systems.secondary.modules.pupils.domain import sen_details as SD  # registers the FK target
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import SEND_EDITORS, STAFF_ROLES, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import current_year, year_of
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

NO_SEN = "No SEN"
MONITORING = "Monitoring"
SUPPORT = "SEN Support"
EHCP = "EHCP (Education, Health, Care Plan)"
ASSESSING = "EHCP assessment in progress"
STAGES: tuple[str, ...] = (NO_SEN, MONITORING, SUPPORT, EHCP, ASSESSING)
DEFAULT_STAGE = MONITORING
NEED_AREAS: tuple[str, ...] = (
    "Communication and interaction", "Cognition and learning",
    "Social, emotional and mental health", "Sensory and/or physical needs", "Other")
STATUSES: tuple[str, ...] = ("Active", "Discharged", "Transitioned", "On hold")
DEFAULT_STATUS = "Active"
REVIEW_TYPES: tuple[str, ...] = ("SEN support review", "Annual review (EHCP)",
                                 "Interim review", "Other")
ANNUAL = "Annual review (EHCP)"
REVIEW_OUTCOMES: tuple[str, ...] = ("Continue", "Adjust", "Escalate", "Discharge", "Reassess",
                                    "No change")
DEFAULT_OUTCOME = "Continue"
LA_DECISIONS: tuple[str, ...] = ("Maintain the plan", "Amend the plan", "Cease the plan")
EHCNA_STATUSES: tuple[str, ...] = ("Requested", "Agreed to assess", "Refused to assess",
                                   "Plan issued", "Plan not issued", "Withdrawn")
PLAN_KINDS: tuple[str, ...] = ("SEN support plan", "Pupil passport", "One-page profile",
                               "Provision plan")
PLAN_STATUSES: tuple[str, ...] = ("Draft", "Active", "Reviewed", "Closed")
PROVISION_STATUSES: tuple[str, ...] = ("Planned", "Active", "Ended")
DELIVERY: tuple[str, ...] = ("1:1", "Small group", "In class", "External", "Other")
SUPPORT_REVIEW_DAYS = 91        # termly
ANNUAL_REVIEW_MONTHS = 12
LA_REPORT_DAYS = 14             # the annual review report goes to the LA
LA_DECISION_DAYS = 28           # the LA decides after the meeting
EHCNA_DECISION_DAYS = 42        # 6 weeks to decide whether to assess
EHCNA_PLAN_DAYS = 140           # 20 weeks to the final plan
DUE_SOON_DAYS = 30

_STAGE_TO_STATUS = {NO_SEN: "N", MONITORING: "N", SUPPORT: "K", EHCP: "E"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS send_register (
    pupil_id            INTEGER PRIMARY KEY REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    status              TEXT NOT NULL DEFAULT 'Active'
                        CHECK (status IN ('Active', 'Discharged', 'Transitioned', 'On hold')),
    monitoring          INTEGER NOT NULL DEFAULT 0 CHECK (monitoring IN (0, 1)),
    senco               TEXT,
    keyworker           TEXT,
    added_on            TEXT,
    next_review_date    TEXT,
    diagnosis           TEXT,
    ehcna_status        TEXT,
    ehcna_requested_on  TEXT,
    ehcna_decision_on   TEXT,
    ehcna_plan_on       TEXT,
    created_by          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by          TEXT,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS send_plans (
    plan_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id            INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    kind                TEXT NOT NULL DEFAULT 'SEN support plan',
    title               TEXT,
    cycle               INTEGER NOT NULL DEFAULT 1,
    status              TEXT NOT NULL DEFAULT 'Draft'
                        CHECK (status IN ('Draft', 'Active', 'Reviewed', 'Closed')),
    start_date          TEXT NOT NULL,
    review_date         TEXT,
    assess              TEXT,
    outcomes            TEXT,
    provision           TEXT,
    strategies          TEXT,
    pupil_voice         TEXT,
    parent_voice        TEXT,
    review_notes        TEXT,
    review_outcome      TEXT,
    reviewed_on         TEXT,
    shared_on           TEXT,
    created_by          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by          TEXT,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_send_plans_pupil ON send_plans (pupil_id, status);
CREATE TABLE IF NOT EXISTS send_reviews (
    review_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id            INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    plan_id             INTEGER REFERENCES send_plans (plan_id) ON DELETE SET NULL,
    review_type         TEXT NOT NULL DEFAULT 'SEN support review',
    review_date         TEXT NOT NULL,
    reviewer            TEXT,
    attendees           TEXT,
    progress            TEXT,
    adjustments         TEXT,
    outcome             TEXT NOT NULL DEFAULT 'Continue',
    next_review_date    TEXT,
    pupil_views         TEXT,
    parent_views        TEXT,
    la_report_sent_on   TEXT,
    la_decision         TEXT,
    la_decision_on      TEXT,
    notes               TEXT,
    created_by          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_send_reviews_pupil ON send_reviews (pupil_id, review_date);
CREATE TABLE IF NOT EXISTS send_provision (
    provision_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id            INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    academic_year       TEXT NOT NULL,
    provision           TEXT NOT NULL,
    need_area           TEXT,
    provider            TEXT,
    delivery            TEXT NOT NULL DEFAULT 'Small group',
    group_size          INTEGER NOT NULL DEFAULT 1 CHECK (group_size BETWEEN 1 AND 40),
    hours_per_week      REAL NOT NULL DEFAULT 0 CHECK (hours_per_week >= 0),
    weeks               INTEGER NOT NULL DEFAULT 0 CHECK (weeks BETWEEN 0 AND 52),
    cost_per_hour       REAL CHECK (cost_per_hour IS NULL OR cost_per_hour >= 0),
    fixed_cost          REAL CHECK (fixed_cost IS NULL OR fixed_cost >= 0),
    start_date          TEXT,
    end_date            TEXT,
    status              TEXT NOT NULL DEFAULT 'Planned'
                        CHECK (status IN ('Planned', 'Active', 'Ended')),
    in_ehcp             INTEGER NOT NULL DEFAULT 0 CHECK (in_ehcp IN (0, 1)),
    outcome             TEXT,
    notes               TEXT,
    created_by          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by          TEXT,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_send_provision_pupil ON send_provision (pupil_id, academic_year);
"""
database.register_schema("send", _SCHEMA)


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Record:
    """One pupil on the SEND register (pupil record + SEN details + register)."""
    pupil_id: int
    admission_no: str
    pupil_name: str
    year_group: int
    form_group: str | None
    sen_status: str
    monitoring: bool
    status: str
    senco: str | None
    keyworker: str | None
    added_on: str | None
    next_review_date: str | None
    diagnosis: str | None
    ehcna_status: str | None
    ehcna_requested_on: str | None
    ehcna_decision_on: str | None
    ehcna_plan_on: str | None
    primary_need: str | None
    secondary_need: str | None
    ehcp_reference: str | None
    ehcp_issued_on: str | None
    provision: str | None
    strategies: str | None
    exam_access: str | None
    notes: str | None
    on_register: bool = False      # has a send_register row

    @property
    def stage(self) -> str:
        if self.sen_status == "E":
            return EHCP
        if self.ehcna_status in ("Requested", "Agreed to assess"):
            return ASSESSING
        if self.sen_status == "K":
            return SUPPORT
        return MONITORING if self.monitoring else NO_SEN

    @property
    def area(self) -> str:
        return SD.area_of(self.primary_need)

    @property
    def primary_label(self) -> str:
        return SD.NEEDS.get(self.primary_need or "", "")

    @property
    def academic_year(self) -> str:
        return year_of(self.added_on) if self.added_on else current_year()


@dataclass(frozen=True)
class Plan:
    plan_id: int
    pupil_id: int
    kind: str
    title: str | None
    cycle: int
    status: str
    start_date: str
    review_date: str | None
    assess: str | None
    outcomes: str | None
    provision: str | None
    strategies: str | None
    pupil_voice: str | None
    parent_voice: str | None
    review_notes: str | None
    review_outcome: str | None
    reviewed_on: str | None
    shared_on: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0


@dataclass(frozen=True)
class Review:
    review_id: int
    pupil_id: int
    plan_id: int | None
    review_type: str
    review_date: str
    reviewer: str | None
    attendees: str | None
    progress: str | None
    adjustments: str | None
    outcome: str
    next_review_date: str | None
    pupil_views: str | None
    parent_views: str | None
    la_report_sent_on: str | None
    la_decision: str | None
    la_decision_on: str | None
    notes: str | None
    created_by: str | None
    created_at: str


@dataclass(frozen=True)
class Provision:
    provision_id: int
    pupil_id: int
    academic_year: str
    provision: str
    need_area: str | None
    provider: str | None
    delivery: str
    group_size: int
    hours_per_week: float
    weeks: int
    cost_per_hour: float | None
    fixed_cost: float | None
    start_date: str | None
    end_date: str | None
    status: str
    in_ehcp: bool
    outcome: str | None
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0

    @property
    def hours(self) -> float:
        return round(self.hours_per_week * self.weeks, 1)

    @property
    def cost(self) -> float:
        """Cost for this pupil: the fixed cost, else hours x rate shared by the group."""
        if self.fixed_cost is not None:
            return round(self.fixed_cost, 2)
        return round(self.hours * (self.cost_per_hour or 0) / max(1, self.group_size), 2)


# ── The register ─────────────────────────────────────────────────────

_REGISTER_SQL = """
SELECT p.pupil_id, p.admission_no, p.legal_last_name, p.legal_first_name, p.preferred_name,
       p.year_group, p.form_group, p.sen_status, p.roll_status,
       r.pupil_id AS reg_id, r.status, r.monitoring, r.senco, r.keyworker, r.added_on,
       r.next_review_date, r.diagnosis, r.ehcna_status, r.ehcna_requested_on,
       r.ehcna_decision_on, r.ehcna_plan_on,
       s.primary_need, s.secondary_need, s.ehcp_reference, s.ehcp_issued_on, s.provision,
       s.strategies, s.exam_access, s.notes
FROM pupils p
LEFT JOIN send_register r ON r.pupil_id = p.pupil_id
LEFT JOIN pupil_sen s ON s.pupil_id = p.pupil_id
"""


def _record(r) -> Record:
    return Record(
        pupil_id=r["pupil_id"], admission_no=r["admission_no"], pupil_name=_name(r),
        year_group=r["year_group"], form_group=r["form_group"], sen_status=r["sen_status"],
        monitoring=bool(r["monitoring"]), status=r["status"] or DEFAULT_STATUS,
        senco=r["senco"], keyworker=r["keyworker"], added_on=r["added_on"],
        next_review_date=r["next_review_date"], diagnosis=r["diagnosis"],
        ehcna_status=r["ehcna_status"], ehcna_requested_on=r["ehcna_requested_on"],
        ehcna_decision_on=r["ehcna_decision_on"], ehcna_plan_on=r["ehcna_plan_on"],
        primary_need=r["primary_need"], secondary_need=r["secondary_need"],
        ehcp_reference=r["ehcp_reference"], ehcp_issued_on=r["ehcp_issued_on"],
        provision=r["provision"], strategies=r["strategies"], exam_access=r["exam_access"],
        notes=r["notes"], on_register=r["reg_id"] is not None)


def get(pupil_ref: Any) -> Record:
    """The pupil's SEND record (also for a pupil with no SEN)."""
    p = _need_pupil(pupil_ref) if not isinstance(pupil_ref, P.Pupil) else pupil_ref
    with database.connect() as conn:
        r = conn.execute(_REGISTER_SQL + " WHERE p.pupil_id = ?", (p.pupil_id,)).fetchone()
    if r is None:
        raise NotFound(f"No pupil {pupil_ref}")
    return _record(r)


def get_for(pupil_ref: Any) -> Record | None:
    """The old lookup: None when the pupil isn't on the register."""
    try:
        rec = get(pupil_ref)
    except (NotFound, ValidationError):
        return None
    return rec if rec.stage != NO_SEN or rec.on_register else None


def list_records(*, year_group: int | str | None = None, stage: str | None = None,
                 status: str | None = None, need: str | None = None, area: str | None = None,
                 form_group: str | None = None, search: str | None = None,
                 include_left: bool = False) -> list[Record]:
    """The register: pupils with SEN support, an EHC plan, or a register entry
    (monitoring, discharged...), by year then surname. *need* is a census code;
    *area* one of :data:`NEED_AREAS`."""
    where = ["(p.sen_status IN ('K', 'E') OR r.pupil_id IS NOT NULL)"]
    params: list[Any] = []
    if not include_left:
        where.append("p.roll_status = 'on_roll'")
    if not _blank(year_group):
        where.append("p.year_group = ?")
        params.append(int(year_group))  # type: ignore[arg-type]
    if form_group:
        where.append("upper(p.form_group) = upper(?)")
        params.append(form_group)
    if need:
        where.append("s.primary_need = ?")
        params.append(need.upper())
    for term in (search or "").split():
        where.append("(p.legal_first_name LIKE ? OR p.legal_last_name LIKE ? OR "
                     "p.preferred_name LIKE ? OR p.admission_no LIKE ?)")
        params += [f"%{term}%"] * 4
    sql = _REGISTER_SQL + " WHERE " + " AND ".join(where) + \
        " ORDER BY p.year_group, p.legal_last_name COLLATE NOCASE, p.legal_first_name COLLATE NOCASE"
    with database.connect() as conn:
        rows = [_record(r) for r in conn.execute(sql, params)]
    if stage:
        rows = [r for r in rows if r.stage == stage]
    if status:
        rows = [r for r in rows if r.status == status]
    if area:
        rows = [r for r in rows if r.area == area]
    return rows


_REG_FIELDS = ("status", "senco", "keyworker", "added_on", "next_review_date", "diagnosis",
               "ehcna_status", "ehcna_requested_on", "ehcna_decision_on", "ehcna_plan_on")


def _clean_register(data: dict[str, Any], cur: Record, problems: list[str]
                    ) -> dict[str, Any]:
    merged = {k: getattr(cur, k) for k in _REG_FIELDS}
    merged.update({k: v for k, v in data.items() if k in _REG_FIELDS})
    out: dict[str, Any] = {
        "status": _choice(merged["status"], STATUSES, "Status", problems, DEFAULT_STATUS),
        "senco": _text(merged["senco"], 80), "keyworker": _text(merged["keyworker"], 80),
        "diagnosis": _text(merged["diagnosis"], 1000),
        "ehcna_status": _choice(merged["ehcna_status"], EHCNA_STATUSES, "EHC needs assessment",
                                problems, None)}
    for k, label in (("added_on", "Start date"), ("next_review_date", "Next review"),
                     ("ehcna_requested_on", "Assessment requested"),
                     ("ehcna_decision_on", "Decision to assess"),
                     ("ehcna_plan_on", "Plan issued")):
        out[k] = _date(merged[k], label, problems)
    out["added_on"] = out["added_on"] or _today().isoformat()
    if out["added_on"] > _today().isoformat():
        problems.append("The start date can't be in the future")
    if out["next_review_date"] and out["next_review_date"] < out["added_on"]:
        problems.append("The next review can't be before the start date")
    if out["ehcna_status"] and not out["ehcna_requested_on"]:
        problems.append("Give the date the EHC needs assessment was requested")
    for k in ("ehcna_decision_on", "ehcna_plan_on"):
        if out[k] and out["ehcna_requested_on"] and out[k] < out["ehcna_requested_on"]:
            problems.append("Assessment dates can't be before the request")
    return out


def save_record(pupil_ref: Any, data: dict[str, Any], *, actor: Principal) -> Record:
    """The old Add / update SEND record. *data* may hold ``stage`` (sets the
    pupil's SEN status, monitoring flag and assessment), the register fields
    and the SEN details fields (needs, EHCP reference / issue date, provision,
    strategies, exam access, notes)."""
    _require_editor(actor, "save")
    p = _need_pupil(pupil_ref)
    cur = get(p)
    problems: list[str] = []
    stage = _choice(data.get("stage"), STAGES, "Stage", problems, None) or cur.stage
    new_status = _STAGE_TO_STATUS.get(stage, cur.sen_status if cur.sen_status != "N" else "K")
    monitoring = stage == MONITORING
    reg = _clean_register(data, cur, problems)
    if stage == ASSESSING and not reg["ehcna_status"]:
        reg["ehcna_status"] = "Requested"
        reg["ehcna_requested_on"] = reg["ehcna_requested_on"] or _today().isoformat()
        problems[:] = [x for x in problems if "was requested" not in x]
    if stage == EHCP and reg["ehcna_status"] in ("Requested", "Agreed to assess"):
        reg["ehcna_status"] = "Plan issued"
        reg["ehcna_plan_on"] = reg["ehcna_plan_on"] or _today().isoformat()
    sd = {k: data[k] for k in SD.FIELDS if k in data}
    if new_status in ("K", "E") and sd:
        problems += SD.validate(p.pupil_id, sd, sen_status=new_status)
    if problems:
        activity_log.record("send.save", target=p.admission_no, outcome="invalid",
                            principal=actor, problems=len(problems))
        raise ValidationError(problems)
    if new_status != p.sen_status:
        P.set_sen_status(p.pupil_id, new_status, actor=actor)   # the SENCO may
    if new_status in ("K", "E") and sd:
        SD.save(p.pupil_id, sd, actor=actor)
    changed = [k for k in _REG_FIELDS if reg[k] != getattr(cur, k)]
    if monitoring != cur.monitoring:
        changed.append("monitoring")
    with database.connect() as conn:
        conn.execute(
            f"INSERT INTO send_register (pupil_id, monitoring, {', '.join(_REG_FIELDS)}, "
            f"created_by, updated_by) VALUES (?, ?, {', '.join('?' * len(_REG_FIELDS))}, ?, ?) "
            "ON CONFLICT (pupil_id) DO UPDATE SET monitoring = excluded.monitoring, "
            + ", ".join(f"{k} = excluded.{k}" for k in _REG_FIELDS)
            + ", updated_by = excluded.updated_by, updated_at = datetime('now')",
            (p.pupil_id, int(monitoring), *(reg[k] for k in _REG_FIELDS), actor.username,
             actor.username))
        _audit(conn, actor, "record", "save", pupil_id=p.pupil_id,
               fields=changed + sorted(sd), sen_status=new_status)
    activity_log.record("send.save", target=p.admission_no, principal=actor)
    return get(p.pupil_id)


def upsert(data: dict[str, Any], *, actor: Principal) -> Record:
    """The old upsert: *data* carries ``pupil_id`` (id or admission no.)."""
    return save_record(data.get("pupil_id") or data.get("pupil"),
                       {k: v for k, v in data.items() if k not in ("pupil_id", "pupil")},
                       actor=actor)


def delete(pupil_ref: Any, *, actor: Principal) -> bool:
    """The old Delete record: the register entry goes (plans, reviews,
    provision and the pupil's SEN status stay - discharge instead to keep it
    on the register)."""
    _require_editor(actor, "delete")
    p = _need_pupil(pupil_ref)
    with database.connect() as conn:
        n = conn.execute("DELETE FROM send_register WHERE pupil_id = ?",
                         (p.pupil_id,)).rowcount
        if n:
            _audit(conn, actor, "record", "delete", pupil_id=p.pupil_id)
    activity_log.record("send.delete", target=p.admission_no, principal=actor)
    return bool(n)


def parent_contact(pupil_id: int) -> str:
    """The first contact with parental responsibility: "name (phone / e-mail)"."""
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    for c in C.list_for_pupil(pupil_id):
        if c.parental_responsibility:
            bits = [x for x in (c.phone, c.email) if x]
            return f"{c.full_name} ({c.relationship})" + (f" - {' / '.join(bits)}"
                                                          if bits else "")
    return ""


# ── Plans (assess - plan - do - review) ──────────────────────────────

_PLAN_FIELDS = ("kind", "title", "status", "start_date", "review_date", "assess", "outcomes",
                "provision", "strategies", "pupil_voice", "parent_voice")


def _plan_select() -> str:
    return (f"SELECT x.*, {_PUPIL_COLS} FROM send_plans x JOIN pupils p USING (pupil_id)")


def get_plan(plan_id: int) -> Plan:
    with database.connect() as conn:
        r = conn.execute(_plan_select() + " WHERE x.plan_id = ?", (int(plan_id),)).fetchone()
    if r is None:
        raise NotFound(f"No plan #{plan_id}")
    return _make(Plan, r)


def list_plans(*, pupil_id: int | None = None, status: str | None = None,
               kind: str | None = None, year_group: int | str | None = None) -> list[Plan]:
    where, params = [], []
    for col, val in (("x.pupil_id", pupil_id), ("x.status", status), ("x.kind", kind)):
        if not _blank(val):
            where.append(f"{col} = ?")
            params.append(val)
    if not _blank(year_group):
        where.append("p.year_group = ?")
        params.append(int(year_group))  # type: ignore[arg-type]
    sql = _plan_select() + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY x.pupil_id, x.cycle DESC, x.plan_id DESC"
    with database.connect() as conn:
        return [_make(Plan, r) for r in conn.execute(sql, params)]


def _clean_plan(data: dict[str, Any], cur: Plan | None, problems: list[str]
                ) -> dict[str, Any]:
    merged = {k: getattr(cur, k) for k in _PLAN_FIELDS} if cur else {}
    merged.update({k: v for k, v in data.items() if k in _PLAN_FIELDS})
    out = {"kind": _choice(merged.get("kind"), PLAN_KINDS, "Kind", problems, PLAN_KINDS[0]),
           "status": _choice(merged.get("status"), PLAN_STATUSES, "Status", problems, "Draft"),
           "title": _text(merged.get("title"), 120),
           "start_date": _date(merged.get("start_date"), "Start date", problems)
           or _today().isoformat(),
           "review_date": _date(merged.get("review_date"), "Review date", problems)}
    for k in ("assess", "outcomes", "provision", "strategies", "pupil_voice", "parent_voice"):
        out[k] = _text(merged.get(k), 4000)
    if out["review_date"] is None and not any(x.startswith("Review date") for x in problems):
        out["review_date"] = _plus(out["start_date"], SUPPORT_REVIEW_DAYS)
    if out["review_date"] and out["review_date"] <= out["start_date"]:
        problems.append("The review date must be after the start date")
    if out["status"] == "Active" and not out["outcomes"]:
        problems.append("An active plan needs its outcomes (what the pupil is working towards)")
    return out


def create_plan(data: dict[str, Any], *, actor: Principal) -> Plan:
    _require_editor(actor, "plan")
    problems: list[str] = []
    p = _pupil(data.get("pupil_id") or data.get("pupil"))
    if p is None:
        problems.append("Pupil ID is required")
    c = _clean_plan(data, None, problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        last = conn.execute("SELECT MAX(cycle) FROM send_plans WHERE pupil_id = ? AND kind = ?",
                            (p.pupil_id, c["kind"])).fetchone()[0]
        pid = conn.execute(
            f"INSERT INTO send_plans (pupil_id, cycle, {', '.join(_PLAN_FIELDS)}, created_by, "
            f"updated_by) VALUES (?, ?, {', '.join('?' * len(_PLAN_FIELDS))}, ?, ?)",
            (p.pupil_id, int(data.get("cycle") or (last or 0) + 1),
             *(c[k] for k in _PLAN_FIELDS), actor.username, actor.username)).lastrowid
        _audit(conn, actor, "plan", "create", pupil_id=p.pupil_id, item_id=pid)
    activity_log.record("send.plan", target=p.admission_no, principal=actor, plan=pid)
    return get_plan(pid)


def update_plan(plan_id: int, changes: dict[str, Any], *, actor: Principal) -> Plan:
    cur = get_plan(plan_id)
    _require_editor(actor, "plan_update", cur.admission_no)
    problems: list[str] = []
    if cur.status in ("Reviewed", "Closed") and set(changes) - {"status"}:
        problems.append("A reviewed or closed plan can't be changed - the next cycle is the "
                        "plan in use")
    c = _clean_plan(changes, cur, problems)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in _PLAN_FIELDS if c[k] != getattr(cur, k)]
    if changed:
        with database.connect() as conn:
            conn.execute("UPDATE send_plans SET " + ", ".join(f"{k} = ?" for k in changed)
                         + ", updated_by = ?, updated_at = datetime('now') WHERE plan_id = ?",
                         (*(c[k] for k in changed), actor.username, cur.plan_id))
            _audit(conn, actor, "plan", "update", pupil_id=cur.pupil_id, item_id=cur.plan_id,
                   fields=changed)
        activity_log.record("send.plan_update", target=cur.admission_no, principal=actor,
                            plan=cur.plan_id)
    return get_plan(cur.plan_id)


def review_plan(plan_id: int, data: dict[str, Any], *, actor: Principal) -> dict[str, Any]:
    """Review a plan: record what happened (``review_notes``, ``outcome`` from
    :data:`REVIEW_OUTCOMES`, ``reviewed_on``, ``attendees``, ``pupil_views``,
    ``parent_views``), file a review and - unless the outcome is Discharge or
    ``next_cycle`` is false - start the next cycle with the outcomes carried
    over. Returns {'plan', 'review', 'next'}."""
    cur = get_plan(plan_id)
    _require_editor(actor, "plan_review", cur.admission_no)
    problems: list[str] = []
    if cur.status not in ("Draft", "Active"):
        problems.append("This plan has already been reviewed or closed")
    on = _date(data.get("reviewed_on"), "Reviewed on", problems) or _today().isoformat()
    if on > _today().isoformat():
        problems.append("Record the review once it has happened")
    outcome = _choice(data.get("outcome"), REVIEW_OUTCOMES, "Outcome", problems,
                      DEFAULT_OUTCOME)
    notes = _text(data.get("review_notes"), 4000)
    if not notes:
        problems.append("Say how the pupil got on (the review)")
    nxt_review = _date(data.get("next_review_date"), "Next review", problems) or \
        _plus(on, SUPPORT_REVIEW_DAYS)
    if problems:
        raise ValidationError(problems)
    go_on = outcome != "Discharge" and data.get("next_cycle", True) not in (False, 0, "0", "no")
    with database.connect() as conn:
        conn.execute("UPDATE send_plans SET status = 'Reviewed', review_notes = ?, "
                     "review_outcome = ?, reviewed_on = ?, updated_by = ?, "
                     "updated_at = datetime('now') WHERE plan_id = ?",
                     (notes, outcome, on, actor.username, cur.plan_id))
        _audit(conn, actor, "plan", "review", pupil_id=cur.pupil_id, item_id=cur.plan_id,
               outcome=outcome)
    review = add_review({"pupil_id": cur.pupil_id, "plan_id": cur.plan_id,
                         "review_type": "SEN support review", "review_date": on,
                         "reviewer": data.get("reviewer"), "attendees": data.get("attendees"),
                         "progress": notes, "adjustments": data.get("adjustments"),
                         "outcome": outcome, "pupil_views": data.get("pupil_views"),
                         "parent_views": data.get("parent_views"),
                         "next_review_date": nxt_review if go_on else None}, actor=actor)
    nxt = None
    if go_on:
        nxt = create_plan({"pupil_id": cur.pupil_id, "kind": cur.kind, "title": cur.title,
                           "cycle": cur.cycle + 1, "status": "Active" if cur.outcomes else
                           "Draft", "start_date": on, "review_date": nxt_review,
                           "assess": f"From the review on {on}: {notes}"[:4000],
                           "outcomes": cur.outcomes, "provision": cur.provision,
                           "strategies": cur.strategies}, actor=actor)
    return {"plan": get_plan(cur.plan_id), "review": review, "next": nxt}


def close_plan(plan_id: int, *, actor: Principal) -> Plan:
    cur = get_plan(plan_id)
    _require_editor(actor, "plan_close", cur.admission_no)
    with database.connect() as conn:
        conn.execute("UPDATE send_plans SET status = 'Closed', updated_by = ?, "
                     "updated_at = datetime('now') WHERE plan_id = ?",
                     (actor.username, cur.plan_id))
        _audit(conn, actor, "plan", "close", pupil_id=cur.pupil_id, item_id=cur.plan_id)
    activity_log.record("send.plan_close", target=cur.admission_no, principal=actor,
                        plan=cur.plan_id)
    return get_plan(cur.plan_id)


def delete_plan(plan_id: int, *, actor: Principal) -> bool:
    cur = get_plan(plan_id)
    _require_editor(actor, "plan_delete", cur.admission_no)
    if cur.status != "Draft":
        raise ValidationError(["Only a draft plan can be deleted - close it instead"])
    with database.connect() as conn:
        conn.execute("DELETE FROM send_plans WHERE plan_id = ?", (cur.plan_id,))
        _audit(conn, actor, "plan", "delete", pupil_id=cur.pupil_id, item_id=cur.plan_id)
    activity_log.record("send.plan_delete", target=cur.admission_no, principal=actor,
                        plan=cur.plan_id)
    return True


def plan_text(plan: Plan) -> str:
    """The plan as plain text (for the family and print)."""
    lines = [f"{plan.kind} - cycle {plan.cycle}" + (f": {plan.title}" if plan.title else ""),
             f"From {plan.start_date}; review by {plan.review_date or '-'}", ""]
    for label, v in (("What we know (assess)", plan.assess), ("Outcomes (plan)", plan.outcomes),
                     ("Support in place (do)", plan.provision),
                     ("Strategies that help", plan.strategies),
                     ("The pupil's views", plan.pupil_voice),
                     ("The family's views", plan.parent_voice),
                     ("Review", plan.review_notes)):
        if v:
            lines += [label, f"  {v}", ""]
    return "\n".join(lines).rstrip()


# ── Reviews ──────────────────────────────────────────────────────────

def _review_row(r) -> Review:
    return Review(**{k: r[k] for k in Review.__dataclass_fields__})


def get_review(review_id: int) -> Review:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM send_reviews WHERE review_id = ?",
                         (int(review_id),)).fetchone()
    if r is None:
        raise NotFound(f"No review #{review_id}")
    return _review_row(r)


def list_reviews(pupil_id: int, *, review_type: str | None = None) -> list[Review]:
    """A pupil's reviews, newest first (the old review history)."""
    sql, params = "SELECT * FROM send_reviews WHERE pupil_id = ?", [int(pupil_id)]
    if review_type:
        sql += " AND review_type = ?"
        params.append(review_type)
    with database.connect() as conn:
        return [_review_row(r) for r in conn.execute(
            sql + " ORDER BY review_date DESC, review_id DESC", params)]


def add_review(data: dict[str, Any], *, actor: Principal) -> Review:
    """The old Add review (*data* carries ``pupil_id``). The pupil's next
    review moves to the review's next review date; an annual review of an EHC
    plan defaults to 12 months on."""
    _require_editor(actor, "review")
    problems: list[str] = []
    p = _pupil(data.get("pupil_id") or data.get("pupil"))
    if p is None:
        raise ValidationError(["Pupil ID is required"])
    rtype = _choice(data.get("review_type"), REVIEW_TYPES, "Review type", problems,
                    REVIEW_TYPES[0])
    day = _date(data.get("review_date"), "Date", problems) or _today().isoformat()
    if day > _today().isoformat():
        problems.append("The review date can't be in the future - record it once it's held "
                        "(use Invite to plan one)")
    outcome = _choice(data.get("outcome"), REVIEW_OUTCOMES, "Outcome", problems,
                      DEFAULT_OUTCOME)
    nxt = _date(data.get("next_review_date"), "Next review", problems)
    if nxt is None and "next_review_date" not in data and outcome != "Discharge":
        nxt = add_months(day, ANNUAL_REVIEW_MONTHS).isoformat() if rtype == ANNUAL else \
            _plus(day, SUPPORT_REVIEW_DAYS)
    if nxt and nxt <= day:
        problems.append("The next review must be after this one")
    if rtype == ANNUAL and p.sen_status != "E":
        problems.append(f"{p.display_name} has no EHC plan - choose another review type")
    plan_id = data.get("plan_id")
    if not _blank(plan_id):
        try:
            if get_plan(int(plan_id)).pupil_id != p.pupil_id:
                problems.append("That plan is for another pupil")
        except (ValueError, NotFound):
            problems.append(f"No plan #{plan_id}")
    if not any(_text(data.get(k), 10) for k in ("progress", "adjustments", "notes")):
        problems.append("Record the progress, adjustments or notes")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        rid = conn.execute(
            "INSERT INTO send_reviews (pupil_id, plan_id, review_type, review_date, reviewer, "
            "attendees, progress, adjustments, outcome, next_review_date, pupil_views, "
            "parent_views, notes, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (p.pupil_id, None if _blank(plan_id) else int(plan_id), rtype, day,
             _text(data.get("reviewer"), 80), _text(data.get("attendees"), 500),
             _text(data.get("progress"), 4000), _text(data.get("adjustments"), 4000),
             outcome, nxt, _text(data.get("pupil_views"), 2000),
             _text(data.get("parent_views"), 2000), _text(data.get("notes"), 2000),
             actor.username)).lastrowid
        conn.execute("INSERT INTO send_register (pupil_id, added_on, next_review_date, "
                     "created_by, updated_by) VALUES (?, ?, ?, ?, ?) ON CONFLICT (pupil_id) DO "
                     "UPDATE SET next_review_date = excluded.next_review_date, "
                     "updated_by = excluded.updated_by, updated_at = datetime('now')",
                     (p.pupil_id, day, nxt, actor.username, actor.username))
        if outcome == "Discharge":
            conn.execute("UPDATE send_register SET status = 'Discharged' WHERE pupil_id = ?",
                         (p.pupil_id,))
        _audit(conn, actor, "review", "add", pupil_id=p.pupil_id, item_id=rid, type=rtype,
               outcome=outcome)
    activity_log.record("send.review", target=p.admission_no, principal=actor, review=rid)
    return get_review(rid)


def record_la(review_id: int, *, actor: Principal, report_sent_on: str | None = None,
              decision: str | None = None, decision_on: str | None = None) -> Review:
    """An annual review's report to the local authority and its decision."""
    rv = get_review(review_id)
    _require_editor(actor, "la")
    problems: list[str] = []
    if rv.review_type != ANNUAL:
        problems.append("Only an EHC plan annual review goes to the local authority")
    sent = _date(report_sent_on, "Report sent", problems) or rv.la_report_sent_on
    dec = _choice(decision, LA_DECISIONS, "Decision", problems, rv.la_decision)
    dec_on = _date(decision_on, "Decision date", problems) or rv.la_decision_on
    if dec and not dec_on:
        dec_on = _today().isoformat()
    for d in (sent, dec_on):
        if d and d < rv.review_date:
            problems.append("Dates can't be before the review meeting")
    if dec and not sent:
        problems.append("Record when the report went to the local authority first")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE send_reviews SET la_report_sent_on = ?, la_decision = ?, "
                     "la_decision_on = ? WHERE review_id = ?", (sent, dec, dec_on, rv.review_id))
        _audit(conn, actor, "review", "la", pupil_id=rv.pupil_id, item_id=rv.review_id,
               decision=dec)
    activity_log.record("send.la", principal=actor, review=rv.review_id)
    return get_review(rv.review_id)


def delete_review(review_id: int, *, actor: Principal) -> bool:
    rv = get_review(review_id)
    _require_editor(actor, "review_delete")
    with database.connect() as conn:
        conn.execute("DELETE FROM send_reviews WHERE review_id = ?", (rv.review_id,))
        _audit(conn, actor, "review", "delete", pupil_id=rv.pupil_id, item_id=rv.review_id)
    activity_log.record("send.review_delete", principal=actor, review=rv.review_id)
    return True


def ehcp_due(rec: Record) -> str | None:
    """When the EHC plan's next annual review is due: 12 months from the
    last annual review, else from the plan's issue date."""
    if rec.sen_status != "E":
        return None
    last = next((r.review_date for r in list_reviews(rec.pupil_id, review_type=ANNUAL)), None)
    base = max(x for x in (last, rec.ehcp_issued_on, rec.ehcna_plan_on, "") if x is not None) \
        or None
    return add_months(base, ANNUAL_REVIEW_MONTHS).isoformat() if base else None


def record_summary(pupil_ref: Any) -> dict[str, Any]:
    """The old record summary plus plans, provision and access."""
    rec = get(pupil_ref)
    reviews = list_reviews(rec.pupil_id)
    return {"record": rec, "reviews": reviews, "review_count": len(reviews),
            "by_outcome": dict(Counter(r.outcome for r in reviews)),
            "last_review": reviews[0].review_date if reviews else None,
            "plans": list_plans(pupil_id=rec.pupil_id),
            "provision": list_provision(pupil_id=rec.pupil_id),
            "access": list_arrangements(pupil_id=rec.pupil_id),
            "agencies": list_agencies(pupil_id=rec.pupil_id),
            "ehcp_due": ehcp_due(rec), "parent_contact": parent_contact(rec.pupil_id)}


# ── Provision map ────────────────────────────────────────────────────

_PROV_FIELDS = ("provision", "need_area", "provider", "delivery", "group_size",
                "hours_per_week", "weeks", "cost_per_hour", "fixed_cost", "start_date",
                "end_date", "status", "in_ehcp", "outcome", "notes")


def _prov_select() -> str:
    return f"SELECT x.*, {_PUPIL_COLS} FROM send_provision x JOIN pupils p USING (pupil_id)"


def get_provision(provision_id: int) -> Provision:
    with database.connect() as conn:
        r = conn.execute(_prov_select() + " WHERE x.provision_id = ?",
                         (int(provision_id),)).fetchone()
    if r is None:
        raise NotFound(f"No provision #{provision_id}")
    return _make(Provision, r)


def list_provision(*, pupil_id: int | None = None, academic_year: str | None = None,
                   status: str | None = None, year_group: int | str | None = None,
                   provision: str | None = None) -> list[Provision]:
    where, params = [], []
    for col, val in (("x.pupil_id", pupil_id), ("x.academic_year", academic_year),
                     ("x.status", status), ("x.provision", provision)):
        if not _blank(val):
            where.append(f"{col} = ?")
            params.append(val)
    if not _blank(year_group):
        where.append("p.year_group = ?")
        params.append(int(year_group))  # type: ignore[arg-type]
    sql = _prov_select() + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY x.provision COLLATE NOCASE, p.legal_last_name COLLATE NOCASE"
    with database.connect() as conn:
        return [_make(Provision, r) for r in conn.execute(sql, params)]


def provision_names() -> list[str]:
    with database.connect() as conn:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT provision FROM send_provision ORDER BY provision COLLATE NOCASE")]


def _clean_provision(data: dict[str, Any], cur: Provision | None, problems: list[str]
                     ) -> dict[str, Any]:
    merged = {k: getattr(cur, k) for k in _PROV_FIELDS} if cur else {}
    merged.update({k: v for k, v in data.items() if k in _PROV_FIELDS})
    out: dict[str, Any] = {"provision": _text(merged.get("provision"), 120)}
    if not out["provision"]:
        problems.append("Name the provision (e.g. Reading intervention)")
    out["need_area"] = _choice(merged.get("need_area"), NEED_AREAS, "Area of need", problems,
                               None)
    out["provider"] = _text(merged.get("provider"), 120)
    out["delivery"] = _choice(merged.get("delivery"), DELIVERY, "Delivery", problems,
                              "Small group")
    out["status"] = _choice(merged.get("status"), PROVISION_STATUSES, "Status", problems,
                            "Planned")
    gs = _number(merged.get("group_size"), "Group size", problems, lo=1, hi=40, whole=True)
    out["group_size"] = int(gs) if gs is not None else 1
    out["hours_per_week"] = _number(merged.get("hours_per_week"), "Hours a week", problems,
                                    hi=40) or 0
    w = _number(merged.get("weeks"), "Weeks", problems, hi=52, whole=True)
    out["weeks"] = int(w) if w is not None else 0
    out["cost_per_hour"] = _number(merged.get("cost_per_hour"), "Cost per hour", problems,
                                   hi=1000)
    out["fixed_cost"] = _number(merged.get("fixed_cost"), "Fixed cost", problems, hi=200000)
    out["start_date"] = _date(merged.get("start_date"), "Start date", problems)
    out["end_date"] = _date(merged.get("end_date"), "End date", problems)
    if out["start_date"] and out["end_date"] and out["end_date"] < out["start_date"]:
        problems.append("End date cannot be before start date")
    if out["status"] == "Active" and not out["start_date"]:
        out["start_date"] = _today().isoformat()
    if out["status"] == "Ended" and not out["end_date"]:
        out["end_date"] = _today().isoformat()
    out["in_ehcp"] = int(_bool(merged.get("in_ehcp")))
    out["outcome"] = _text(merged.get("outcome"), 2000)
    out["notes"] = _text(merged.get("notes"), 2000)
    return out


def add_provision(data: dict[str, Any], *, actor: Principal) -> Provision:
    _require_editor(actor, "provision")
    problems: list[str] = []
    p = _pupil(data.get("pupil_id") or data.get("pupil"))
    if p is None:
        problems.append("Pupil ID is required")
    c = _clean_provision(data, None, problems)
    if p is not None and c["in_ehcp"] and p.sen_status != "E":
        problems.append("Only a pupil with an EHC plan has provision specified in a plan")
    year = str(data.get("academic_year") or "").strip() or (
        year_of(c["start_date"]) if c["start_date"] else current_year())
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        xid = conn.execute(
            f"INSERT INTO send_provision (pupil_id, academic_year, {', '.join(_PROV_FIELDS)}, "
            f"created_by, updated_by) VALUES (?, ?, {', '.join('?' * len(_PROV_FIELDS))}, ?, ?)",
            (p.pupil_id, year, *(c[k] for k in _PROV_FIELDS), actor.username,
             actor.username)).lastrowid
        _audit(conn, actor, "provision", "add", pupil_id=p.pupil_id, item_id=xid)
    activity_log.record("send.provision", target=p.admission_no, principal=actor, item=xid)
    return get_provision(xid)


def add_provision_many(pupil_ids: list[int], data: dict[str, Any], *, actor: Principal
                       ) -> list[Provision]:
    """The same provision for a group (group size = the number of pupils
    unless given)."""
    if not pupil_ids:
        raise ValidationError(["Choose the pupils"])
    data = {"group_size": len(pupil_ids), **data}
    return [add_provision({**data, "pupil_id": pid}, actor=actor) for pid in pupil_ids]


def update_provision(provision_id: int, changes: dict[str, Any], *, actor: Principal
                     ) -> Provision:
    cur = get_provision(provision_id)
    _require_editor(actor, "provision_update", cur.admission_no)
    problems: list[str] = []
    c = _clean_provision(changes, cur, problems)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in _PROV_FIELDS if c[k] != (int(getattr(cur, k)) if k == "in_ehcp"
                                                   else getattr(cur, k))]
    if changed:
        with database.connect() as conn:
            conn.execute("UPDATE send_provision SET " + ", ".join(f"{k} = ?" for k in changed)
                         + ", updated_by = ?, updated_at = datetime('now') "
                           "WHERE provision_id = ?",
                         (*(c[k] for k in changed), actor.username, cur.provision_id))
            _audit(conn, actor, "provision", "update", pupil_id=cur.pupil_id,
                   item_id=cur.provision_id, fields=changed)
        activity_log.record("send.provision_update", target=cur.admission_no, principal=actor,
                            item=cur.provision_id)
    return get_provision(cur.provision_id)


def delete_provision(provision_id: int, *, actor: Principal) -> bool:
    cur = get_provision(provision_id)
    _require_editor(actor, "provision_delete", cur.admission_no)
    with database.connect() as conn:
        conn.execute("DELETE FROM send_provision WHERE provision_id = ?", (cur.provision_id,))
        _audit(conn, actor, "provision", "delete", pupil_id=cur.pupil_id,
               item_id=cur.provision_id)
    activity_log.record("send.provision_delete", target=cur.admission_no, principal=actor)
    return True


def provision_map(*, academic_year: str | None = None, year_group: int | str | None = None
                  ) -> list[dict[str, Any]]:
    """The map by provision: {'provision', 'pupils', 'hours', 'cost', 'active',
    'areas'} for a school year (cancelled - "Ended" before starting - still count)."""
    out: dict[str, dict[str, Any]] = {}
    for x in list_provision(academic_year=academic_year or current_year(),
                            year_group=year_group):
        g = out.setdefault(x.provision, {"provision": x.provision, "pupils": set(), "hours": 0.0,
                                         "cost": 0.0, "active": 0, "areas": set()})
        g["pupils"].add(x.pupil_id)
        g["hours"] += x.hours
        g["cost"] += x.cost
        g["active"] += x.status == "Active"
        if x.need_area:
            g["areas"].add(x.need_area)
    return sorted(({**g, "pupils": len(g["pupils"]), "hours": round(g["hours"], 1),
                    "cost": round(g["cost"], 2), "areas": ", ".join(sorted(g["areas"]))}
                   for g in out.values()), key=lambda g: (-g["cost"], g["provision"]))


# ── Strategies (all staff) ───────────────────────────────────────────

def my_pupil_ids(actor: Principal) -> set[int]:
    """Pupils in the teaching groups the signed-in teacher teaches this year."""
    from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
    out: set[int] = set()
    for g in TG.list_groups(teacher=actor.username):
        out |= {p.pupil_id for p in TG.members(g.group_id)}
    return out


def strategies(*, actor: Principal, year_group: int | str | None = None,
               form_group: str | None = None, mine: bool = False) -> list[dict[str, Any]]:
    """What teachers need: for each pupil on the register (active), their
    stage, needs, the strategies that help (SEN details and the active plan),
    their day-to-day adjustments and exam access arrangements, keyworker."""
    _require_staff(actor, "strategies")
    rows = [r for r in list_records(year_group=year_group, form_group=form_group)
            if r.status == "Active" and r.stage != NO_SEN]
    if mine:
        ids = my_pupil_ids(actor)
        rows = [r for r in rows if r.pupil_id in ids]
    plans: dict[int, Plan] = {}
    for pl in list_plans(status="Active"):
        plans.setdefault(pl.pupil_id, pl)
    access: dict[int, list[Arrangement]] = {}
    for a in list_arrangements(status="Active"):
        access.setdefault(a.pupil_id, []).append(a)
    out = []
    for r in rows:
        pl = plans.get(r.pupil_id)
        acc = access.get(r.pupil_id, [])
        out.append({
            "pupil_id": r.pupil_id, "pupil_name": r.pupil_name, "admission_no": r.admission_no,
            "year_group": r.year_group, "form_group": r.form_group, "stage": r.stage,
            "needs": ", ".join(x for x in (r.primary_label, SD.NEEDS.get(r.secondary_need or "",
                                                                         "")) if x),
            "strategies": "\n".join(x for x in (r.strategies, pl.strategies if pl else None)
                                    if x),
            "adjustments": "; ".join(a.category for a in acc if not a.exam_only
                                   and a.arrangement_type != EXAM_ACCESS),
            "exam_access": "; ".join(a.category for a in acc if a.exam_only or
                                     a.arrangement_type == EXAM_ACCESS) or (r.exam_access or ""),
            "keyworker": r.keyworker or ""})
    activity_log.record("send.strategies", principal=actor, rows=len(out))
    return out


# ── Due ──────────────────────────────────────────────────────────────

def overdue_reviews(today: str | None = None) -> list[Record]:
    """The old Overdue: Active records whose next review has passed."""
    day = today or _today().isoformat()
    return [r for r in list_records(status="Active")
            if r.next_review_date and r.next_review_date < day]


def due(*, today: _dt.date | None = None, within: int = DUE_SOON_DAYS,
        year_group: int | str | None = None) -> list[dict[str, Any]]:
    """Every review, deadline and expiry due within *within* days or overdue:
    {'pupil_id', 'pupil_name', 'admission_no', 'year_group', 'item', 'due',
    'overdue', 'ref'}, soonest first."""
    day = today or _today()
    iso, horizon = day.isoformat(), (day + _dt.timedelta(days=within)).isoformat()
    out: list[dict[str, Any]] = []
    recs = {r.pupil_id: r for r in list_records(year_group=year_group)}

    def add(pid: int, item: str, when: str | None, ref: str = "") -> None:
        r = recs.get(pid)
        if when and when <= horizon and r is not None:
            out.append({"pupil_id": pid, "pupil_name": r.pupil_name,
                        "admission_no": r.admission_no, "year_group": r.year_group,
                        "item": item, "due": when, "overdue": when < iso, "ref": ref})
    for r in recs.values():
        if r.status != "Active":
            continue
        add(r.pupil_id, "SEN review", r.next_review_date)
        e = ehcp_due(r)
        if e:
            add(r.pupil_id, "EHC plan annual review", e)
        if r.ehcna_status == "Requested" and r.ehcna_requested_on:
            add(r.pupil_id, "LA decision on EHC needs assessment (6 weeks)",
                _plus(r.ehcna_requested_on, EHCNA_DECISION_DAYS))
        if r.ehcna_status == "Agreed to assess" and r.ehcna_requested_on:
            add(r.pupil_id, "Final EHC plan (20 weeks)",
                _plus(r.ehcna_requested_on, EHCNA_PLAN_DAYS))
    for pl in list_plans(year_group=year_group):
        if pl.status in ("Draft", "Active"):
            add(pl.pupil_id, f"{pl.kind} review (cycle {pl.cycle})", pl.review_date,
                f"plan:{pl.plan_id}")
    with database.connect() as conn:
        annual = conn.execute("SELECT * FROM send_reviews WHERE review_type = ? AND "
                              "(la_report_sent_on IS NULL OR la_decision IS NULL)",
                              (ANNUAL,)).fetchall()
    for rv in map(_review_row, annual):
        if not rv.la_report_sent_on:
            add(rv.pupil_id, "Annual review report to the LA (2 weeks)",
                _plus(rv.review_date, LA_REPORT_DAYS), f"review:{rv.review_id}")
        elif not rv.la_decision:
            add(rv.pupil_id, "LA decision after annual review (4 weeks)",
                _plus(rv.review_date, LA_DECISION_DAYS), f"review:{rv.review_id}")
    for a in list_arrangements(year_group=year_group):
        if a.status in ("Active", "Proposed", "Under review"):
            add(a.pupil_id, f"Access arrangement review: {a.category}", a.review_date,
                f"access:{a.arrangement_id}")
            if a.status == "Active":
                add(a.pupil_id, f"Access arrangement ends: {a.category}", a.end_date,
                    f"access:{a.arrangement_id}")
    for g in list_agencies(year_group=year_group):
        if g.status in ("Referred", "Waiting", "Active") and g.next_appointment and \
                g.next_appointment >= iso:
            add(g.pupil_id, f"{g.agency} appointment", g.next_appointment,
                f"agency:{g.agency_id}")
    return sorted(out, key=lambda x: (x["due"], x["pupil_name"]))


# ── Reports ──────────────────────────────────────────────────────────

def cohort_summary(*, year_group: int | str | None = None) -> dict[str, Any]:
    """The old cohort summary (total, by stage / primary need / status, EHCP count)."""
    rows = list_records(year_group=year_group)
    return {"total": len(rows), "by_stage": dict(Counter(r.stage for r in rows)),
            "by_primary_need": dict(Counter(r.primary_label or "(not recorded)"
                                            for r in rows if r.sen_status in ("K", "E"))),
            "by_status": dict(Counter(r.status for r in rows)),
            "ehcp_count": sum(1 for r in rows if r.sen_status == "E"),
            "support_count": sum(1 for r in rows if r.sen_status == "K"),
            "monitoring": sum(1 for r in rows if r.stage == MONITORING),
            "on_roll": len(P.list_pupils(year_group=int(year_group) if not _blank(year_group)
                                         else None))}


def needs_by_year() -> list[dict[str, Any]]:
    """Pupils with SEN support or an EHC plan by primary need and year:
    {'need', 'label', 'area', 7: n, ..., 11: n, 'total'}."""
    grid: dict[str, dict[str, Any]] = {}
    for r in list_records():
        if r.sen_status not in ("K", "E"):
            continue
        code = r.primary_need or ""
        g = grid.setdefault(code, {"need": code or "-", "label": r.primary_label or
                                   "(not recorded)", "area": r.area,
                                   **{y: 0 for y in P.YEAR_GROUPS}, "total": 0})
        g[r.year_group] += 1
        g["total"] += 1
    return sorted(grid.values(), key=lambda g: (-g["total"], g["label"]))


def stage_by_year() -> list[dict[str, Any]]:
    """SEN support (K) vs EHC plan (E) by year, with % of pupils on roll."""
    out = []
    recs = list_records()
    for y in P.YEAR_GROUPS:
        roll = len(P.list_pupils(year_group=y))
        k = sum(1 for r in recs if r.year_group == y and r.sen_status == "K")
        e = sum(1 for r in recs if r.year_group == y and r.sen_status == "E")
        m = sum(1 for r in recs if r.year_group == y and r.stage == MONITORING)
        out.append({"year": y, "on_roll": roll, "K": k, "E": e, "monitoring": m,
                    "k_pct": round(100 * k / roll, 1) if roll else None,
                    "e_pct": round(100 * e / roll, 1) if roll else None})
    return out


def by_area() -> list[dict[str, Any]]:
    c = Counter(r.area or "(not recorded)" for r in list_records()
                if r.sen_status in ("K", "E"))
    return [{"area": a, "pupils": n} for a, n in c.most_common()]


# ── Families ─────────────────────────────────────────────────────────

def _family(pupil_id: int) -> list[tuple[str, str]]:
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    return [(x.email, x.full_name) for x in C.emailable_for_pupils([pupil_id]).get(pupil_id, [])
            if x.email and x.parental_responsibility]


def _send(template: str, label: str, pupil: P.Pupil, values: dict[str, Any],
          actor: Principal) -> dict[str, Any]:
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
    to = _family(pupil.pupil_id)
    if not to:
        return {"message_id": None, "emails": 0}
    t = email_templates.load_template(template)
    letters = []
    for address, name in to:
        subject, body = t.render({"recipient_name": name, "pupil_name": pupil.display_name,
                                  "sender_name": BH._staff_name(actor), **values})
        letters.append((address, name, subject, body))
    mid = E.save_prepared(template, label, label, "(one letter per contact)", letters,
                          actor=actor)
    return {"message_id": mid, "emails": len(letters)}


def invite_to_review(pupil_ref: Any, *, when: str, actor: Principal,
                     review_type: str = REVIEW_TYPES[0], where: str = "",
                     note: str = "") -> dict[str, Any]:
    """E-mail the family an invitation to a review meeting. Returns
    {'message_id', 'emails'}; deliver with the outbox."""
    _require_editor(actor, "invite")
    p = _need_pupil(pupil_ref)
    problems: list[str] = []
    rtype = _choice(review_type, REVIEW_TYPES, "Review type", problems, REVIEW_TYPES[0])
    if not str(when or "").strip():
        problems.append("Say when the meeting is")
    if problems:
        raise ValidationError(problems)
    res = _send("send_review_invitation", "SEND review invitation", p,
                {"review_type": rtype.lower(), "when": str(when).strip(),
                 "where": where.strip() or "at school", "note": note.strip()}, actor)
    with database.connect() as conn:
        _audit(conn, actor, "review", "invite", pupil_id=p.pupil_id, emails=res["emails"])
    activity_log.record("send.invite", target=p.admission_no, principal=actor,
                        emails=res["emails"])
    return res


def share_plan(plan_id: int, *, actor: Principal, note: str = "") -> dict[str, Any]:
    """E-mail the plan to the family; records the date it was shared."""
    pl = get_plan(plan_id)
    _require_editor(actor, "share", pl.admission_no)
    p = P.get_pupil(pl.pupil_id)
    res = _send("send_plan_shared", "SEND plan", p,
                {"plan_kind": pl.kind, "plan_text": plan_text(pl), "note": note.strip()}, actor)
    if res["emails"]:
        with database.connect() as conn:
            conn.execute("UPDATE send_plans SET shared_on = ? WHERE plan_id = ?",
                         (_today().isoformat(), pl.plan_id))
            _audit(conn, actor, "plan", "share", pupil_id=pl.pupil_id, item_id=pl.plan_id,
                   emails=res["emails"])
    activity_log.record("send.share", target=pl.admission_no, principal=actor,
                        plan=pl.plan_id, emails=res["emails"])
    return res


# ── Export ───────────────────────────────────────────────────────────

def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    _require_staff(actor, "export")
    rows = list_records(**filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["admission_no", "pupil", "year", "form", "sen_status", "stage", "status",
                    "primary_need", "secondary_need", "area", "ehcp_reference",
                    "ehcp_issued_on", "ehcp_annual_review_due", "next_review", "senco",
                    "keyworker", "exam_access"])
        for r in rows:
            w.writerow([_safe(r.admission_no), _safe(r.pupil_name), r.year_group,
                        _safe(r.form_group), r.sen_status, r.stage, r.status,
                        r.primary_need or "", r.secondary_need or "", r.area,
                        _safe(r.ehcp_reference), r.ehcp_issued_on or "", ehcp_due(r) or "",
                        r.next_review_date or "", _safe(r.senco), _safe(r.keyworker),
                        _safe(r.exam_access)])
    activity_log.record("send.export", principal=actor, rows=len(rows))
    return len(rows)


def for_profile(pupil_id: int) -> dict[str, Any] | None:
    """A short block for the pupil profile / My Day (None when not on the
    register): stage, needs, strategies, exam access, next review."""
    rec = get_for(pupil_id)
    if rec is None:
        return None
    plan = next(iter(list_plans(pupil_id=rec.pupil_id, status="Active")), None)
    return {"stage": rec.stage, "status": rec.status,
            "needs": rec.primary_label or "", "area": rec.area,
            "strategies": "\n".join(x for x in (rec.strategies,
                                                plan.strategies if plan else None) if x),
            "exam_access": exam_access_text(rec.pupil_id) or rec.exam_access or "",
            "next_review": rec.next_review_date, "ehcp_due": ehcp_due(rec),
            "keyworker": rec.keyworker}

