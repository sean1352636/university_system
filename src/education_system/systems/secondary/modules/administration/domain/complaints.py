"""Complaints: the school's complaints procedure (DfE best-practice model).

Kept from the old Complaints register:

* Received on, complainant name and role (Parent / Carer, Student, Member of
  Public, Staff, Former Student, Anonymous, Other), e-mail, phone, subject,
  description, category (Teaching & Learning ... Other), stage, severity 1-5
  (Low, Routine, Standard, Serious, Major), assigned to, acknowledged on,
  target response date, response issued on and summary, outcome (Upheld,
  Partially Upheld, Not Upheld, Withdrawn, No Action), actions taken,
  complainant informed, satisfaction (Satisfied, Partially Satisfied, Not
  Satisfied, Not Recorded), escalated to stage 2 / appeal, governors
  informed, linked to, status (Received, Acknowledged, Under Investigation,
  Response Drafted, Response Issued, Escalated, Closed), closed on and notes.
* Lists (all, open, overdue, stage 2 / appeal, filtered), view, new, edit,
  acknowledge, start investigation, issue response, escalate, record
  satisfaction, close, change status, delete, and the summary (open,
  overdue, serious, at stage 2 or appeal, upheld / not upheld, average days
  to close, by category / stage / status / outcome).

New, following the DfE "Best practice guidance for school complaints
procedures":

* **Stages.** Stage 1 - informal (a member of staff), Stage 2 - formal (the
  headteacher), Stage 3 - governors' panel, then referral to the DfE. (The
  old stage names are still accepted: Informal, Formal Stage 1, Formal Stage
  2 and Appeal / Governors.) Escalating needs the stage's response (or its
  deadline to have passed) and resets the response; a request long after the
  response is flagged. The panel has at least three members, none involved
  in the complaint.
* **Deadlines in school days** (the school calendar, else weekdays):
  acknowledgement within :data:`ACK_DAYS`, response within
  :data:`RESPONSE_DAYS` for the stage, counted from when the stage started.
  :func:`overdue` lists what is late.
* **A pupil** can be linked (optional); the complainant's address too.
* **Timeline** of dated events (calls, meetings, letters, decisions).
* **Letters** through the school outbox: acknowledgement, the stage
  response, and the escalation / panel letter, to the complainant's e-mail.
* **Unreasonable / serial complainants.** A flag with notes and a review
  date; a new complaint from a flagged complainant (or a third in twelve
  months) is pointed out.
* **Annual report** for governors: counts by category, stage reached,
  outcome and role, closed on time and average days to close.
* **Who.** The complaints lead (:data:`COMPLAINT_EDITORS` - headteacher's
  office / clerk) sees and does everything. A member of staff sees the
  complaints assigned to them, adds events and handles stage 1 (acknowledge,
  respond). Every change is in ``complaint_audit`` and the activity log
  (ids only).
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.pupils.domain import pupils as P  # registers the FK target
from education_system.systems.secondary.core.permissions.access import (
    COMPLAINT_EDITORS,
    STAFF_ROLES,
    Principal,
)
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import current_year, year_of
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

CATEGORIES: tuple[str, ...] = (
    "Teaching & Learning", "Behaviour & Discipline", "Communication",
    "Premises & Facilities", "Admissions", "Exams & Assessment", "Pastoral / Wellbeing",
    "Safeguarding", "Bullying / Harassment", "Staff Conduct", "Discrimination",
    "SEND Provision", "Catering", "Transport", "Finance / Fees", "Data Protection", "Other")
DEFAULT_CATEGORY = "Other"
#: Categories that go through a different procedure, not this one.
OTHER_PROCEDURES = {
    "Admissions": "Admissions appeals go to an independent appeal panel.",
    "Safeguarding": "Allegations about staff or concerns about a child go to the DSL / LADO "
                    "under safeguarding procedures, not the complaints procedure.",
    "Exams & Assessment": "Exam results and access arrangements follow the exam board's "
                          "procedures.",
    "Staff Conduct": "Staff discipline is dealt with under the staff conduct procedure; the "
                     "complainant is told it is being handled but not the detail.",
    "Data Protection": "Subject access requests and data breaches go to the data protection "
                       "officer."}
COMPLAINANT_ROLES: tuple[str, ...] = (
    "Parent / Carer", "Student", "Member of Public", "Staff", "Former Student", "Anonymous",
    "Other")
DEFAULT_COMPLAINANT_ROLE = "Parent / Carer"

STAGE_1, STAGE_2, STAGE_3, DFE = ("Stage 1 - Informal", "Stage 2 - Formal",
                                  "Stage 3 - Governors' panel", "Referred to DfE")
STAGES: tuple[str, ...] = (STAGE_1, STAGE_2, STAGE_3, DFE)
DEFAULT_STAGE = STAGE_1
STAGE_HANDLER = {STAGE_1: "a member of staff", STAGE_2: "the headteacher",
                 STAGE_3: "a panel of governors", DFE: "the Department for Education"}
#: The old register's stage names.
_STAGE_ALIASES = {"informal": STAGE_1, "formal stage 1": STAGE_2, "formal stage 2": STAGE_3,
                  "appeal / governors": STAGE_3, "1": STAGE_1, "2": STAGE_2, "3": STAGE_3}

SEVERITIES: tuple[int, ...] = (1, 2, 3, 4, 5)
_SEVERITY_LABELS = {1: "Low", 2: "Routine", 3: "Standard", 4: "Serious", 5: "Major"}
STATUSES: tuple[str, ...] = (
    "Received", "Acknowledged", "Under Investigation", "Response Drafted", "Response Issued",
    "Escalated", "Closed")
DEFAULT_STATUS = "Received"
OUTCOMES: tuple[str, ...] = ("Upheld", "Partially Upheld", "Not Upheld", "Withdrawn",
                             "No Action")
SATISFACTIONS: tuple[str, ...] = ("Satisfied", "Partially Satisfied", "Not Satisfied",
                                  "Not Recorded")
DEFAULT_SATISFACTION = "Not Recorded"
EVENT_TYPES: tuple[str, ...] = (
    "Note", "Phone call", "Meeting", "Letter sent", "E-mail", "Investigation",
    "Acknowledged", "Response", "Escalated", "Panel", "Decision", "Other")

ACK_DAYS = 5
RESPONSE_DAYS = {STAGE_1: 10, STAGE_2: 15, STAGE_3: 20, DFE: 0}
ESCALATE_WITHIN = 10          # school days after a response to ask for the next stage
PANEL_MIN = 3
SERIAL_COUNT = 3              # complaints in SERIAL_MONTHS
SERIAL_MONTHS = 12
LETTERS = {"acknowledgement": ("complaint_acknowledgement", "Complaint acknowledged"),
           "response": ("complaint_response", "Complaint response"),
           "escalation": ("complaint_escalation", "Complaint escalated")}


def severity_label(s: int | None) -> str:
    return "—" if s is None else _SEVERITY_LABELS.get(s, "Unknown")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS complaints (
    complaint_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    received_on              TEXT NOT NULL,
    complainant_name         TEXT NOT NULL,
    complainant_role         TEXT NOT NULL DEFAULT 'Parent / Carer',
    contact_email            TEXT,
    contact_phone            TEXT,
    complainant_address      TEXT,
    pupil_id                 INTEGER REFERENCES pupils (pupil_id) ON DELETE SET NULL,
    subject                  TEXT NOT NULL,
    description              TEXT,
    category                 TEXT NOT NULL DEFAULT 'Other',
    stage                    TEXT NOT NULL DEFAULT 'Stage 1 - Informal',
    stage_started_on         TEXT NOT NULL,
    severity                 INTEGER NOT NULL DEFAULT 2 CHECK (severity BETWEEN 1 AND 5),
    assigned_to              TEXT,
    acknowledged_on          TEXT,
    ack_due                  TEXT,
    target_response_date     TEXT,
    response_issued_on       TEXT,
    response_summary         TEXT,
    outcome                  TEXT,
    actions_taken            TEXT,
    complainant_informed     INTEGER NOT NULL DEFAULT 0,
    complainant_satisfaction TEXT NOT NULL DEFAULT 'Not Recorded',
    escalated_to_stage_2     INTEGER NOT NULL DEFAULT 0,
    escalated_to_appeal      INTEGER NOT NULL DEFAULT 0,
    governors_informed       INTEGER NOT NULL DEFAULT 0,
    linked_to                TEXT,
    status                   TEXT NOT NULL DEFAULT 'Received',
    closed_on                TEXT,
    notes                    TEXT,
    panel_date               TEXT,
    panel_members            TEXT,
    unreasonable             INTEGER NOT NULL DEFAULT 0,
    unreasonable_notes       TEXT,
    unreasonable_review      TEXT,
    created_by               TEXT,
    created_on               TEXT NOT NULL DEFAULT (datetime('now')),
    updated_on               TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_complaints_received ON complaints (received_on);
CREATE INDEX IF NOT EXISTS ix_complaints_status ON complaints (status);
CREATE TABLE IF NOT EXISTS complaint_events (
    event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id  INTEGER NOT NULL REFERENCES complaints (complaint_id) ON DELETE CASCADE,
    event_date    TEXT NOT NULL,
    event_type    TEXT NOT NULL DEFAULT 'Note',
    stage         TEXT,
    summary       TEXT NOT NULL,
    created_by    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_complaint_events ON complaint_events (complaint_id);
CREATE TABLE IF NOT EXISTS complaint_audit (
    audit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id  INTEGER,
    action        TEXT NOT NULL,
    detail        TEXT,
    actor         TEXT NOT NULL,
    at            TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("complaints", _SCHEMA)


@dataclass(frozen=True)
class Complaint:
    complaint_id: int
    received_on: str
    complainant_name: str
    complainant_role: str
    contact_email: str | None
    contact_phone: str | None
    complainant_address: str | None
    pupil_id: int | None
    subject: str
    description: str | None
    category: str
    stage: str
    stage_started_on: str
    severity: int
    assigned_to: str | None
    acknowledged_on: str | None
    ack_due: str | None
    target_response_date: str | None
    response_issued_on: str | None
    response_summary: str | None
    outcome: str | None
    actions_taken: str | None
    complainant_informed: bool
    complainant_satisfaction: str
    escalated_to_stage_2: bool
    escalated_to_appeal: bool
    governors_informed: bool
    linked_to: str | None
    status: str
    closed_on: str | None
    notes: str | None
    panel_date: str | None
    panel_members: str | None
    unreasonable: bool
    unreasonable_notes: str | None
    unreasonable_review: str | None
    created_by: str | None
    created_on: str
    updated_on: str
    pupil_name: str = ""

    @property
    def is_open(self) -> bool:
        return self.status != "Closed"

    @property
    def severity_label(self) -> str:
        return severity_label(self.severity)

    @property
    def stage_no(self) -> int:
        return STAGES.index(self.stage) + 1 if self.stage in STAGES else 0

    @property
    def ack_overdue(self) -> bool:
        return bool(self.is_open and not self.acknowledged_on and self.ack_due and
                    self.ack_due < _today().isoformat())

    @property
    def response_overdue(self) -> bool:
        if not self.is_open or self.response_issued_on or not self.target_response_date:
            return False
        return self.target_response_date < _today().isoformat()

    @property
    def overdue(self) -> bool:
        return self.ack_overdue or self.response_overdue

    @property
    def days_open(self) -> int | None:
        try:
            start = _dt.date.fromisoformat(self.received_on)
        except ValueError:
            return None
        end = _dt.date.fromisoformat(self.closed_on) if self.closed_on else _today()
        return (end - start).days


@dataclass
class ComplaintsSummary:
    total: int = 0
    open_count: int = 0
    overdue: int = 0
    serious_or_major: int = 0
    at_stage_2_or_appeal: int = 0
    governors_informed: int = 0
    closed_count: int = 0
    upheld_count: int = 0
    not_upheld_count: int = 0
    average_days_to_close: float | None = None
    unreasonable: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_stage: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_outcome: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Event:
    event_id: int
    complaint_id: int
    event_date: str
    event_type: str
    stage: str | None
    summary: str
    created_by: str | None
    created_at: str


_BOOLS = ("complainant_informed", "escalated_to_stage_2", "escalated_to_appeal",
          "governors_informed", "unreasonable")
_SELECT = ("SELECT c.*, p.legal_last_name, p.legal_first_name, p.preferred_name "
           "FROM complaints c LEFT JOIN pupils p ON p.pupil_id = c.pupil_id")


def _row(r) -> Complaint:
    vals = {k: r[k] for k in Complaint.__dataclass_fields__ if k != "pupil_name"}
    for b in _BOOLS:
        vals[b] = bool(vals[b])
    name = (f"{r['preferred_name'] or r['legal_first_name']} {r['legal_last_name']}"
            if r["legal_last_name"] else "")
    return Complaint(**vals, pupil_name=name)


def _event_row(r) -> Event:
    return Event(**{k: r[k] for k in Event.__dataclass_fields__})


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in COMPLAINT_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"complaints.{action}", target=target, outcome="denied",
                        principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can see complaints.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the complaints lead can do that.")


def _me(actor: Principal) -> set[str]:
    from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
    return BH._me(actor)


def is_assigned(actor: Principal, c: Complaint) -> bool:
    return actor.role in STAFF_ROLES and bool(c.assigned_to) and \
        c.assigned_to.strip().lower() in _me(actor)


def can_see(actor: Principal, c: Complaint) -> bool:
    return is_editor(actor) or is_assigned(actor, c)


def can_handle_stage_1(actor: Principal, c: Complaint) -> bool:
    """The lead, or the member of staff it is assigned to at stage 1."""
    return is_editor(actor) or (is_assigned(actor, c) and c.stage == STAGE_1)


def _see(actor: Principal, c: Complaint, action: str) -> None:
    if not can_see(actor, c):
        _deny(actor, action, f"complaint:{c.complaint_id}",
              "Only the complaints lead or the member of staff dealing with it can see this "
              "complaint.")


def _audit(conn, action: str, actor: Principal, complaint_id: int | None, **detail: Any
           ) -> None:
    conn.execute("INSERT INTO complaint_audit (complaint_id, action, detail, actor) "
                 "VALUES (?, ?, ?, ?)",
                 (complaint_id, action, json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(complaint_id: int | None = None, *, limit: int = 300) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM complaint_audit", []
    if complaint_id is not None:
        sql += " WHERE complaint_id = ?"
        params.append(int(complaint_id))
    with database.connect() as conn:
        return [{"at": r["at"], "complaint_id": r["complaint_id"], "action": r["action"],
                 "actor": r["actor"], "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


# ── School days ──────────────────────────────────────────────────────

def school_days_after(day: str | _dt.date, n: int) -> _dt.date:
    """The *n*-th school day after *day* (calendar, else weekdays)."""
    d = _dt.date.fromisoformat(str(day)) if not isinstance(day, _dt.date) else day
    if n <= 0:
        return d
    from education_system.systems.secondary.modules.attendance.domain import attendance as AT
    span = max(14, n * 3)
    while span <= 800:
        try:
            days = AT.school_days(d + _dt.timedelta(days=1), d + _dt.timedelta(days=span))
        except Exception:  # noqa: BLE001 - no calendar: weekdays
            break
        if len(days) >= n:
            return days[n - 1]
        span *= 2
    k = 0
    while True:
        d += _dt.timedelta(days=1)
        if d.weekday() < 5:
            k += 1
            if k == n:
                return d


def school_days_between(start: str, end: str) -> int:
    from education_system.systems.secondary.modules.attendance.domain import attendance as AT
    s, e = _dt.date.fromisoformat(start), _dt.date.fromisoformat(end)
    if e <= s:
        return 0
    try:
        return len(AT.school_days(s + _dt.timedelta(days=1), e))
    except Exception:  # noqa: BLE001
        return sum(1 for i in range(1, (e - s).days + 1)
                   if (s + _dt.timedelta(days=i)).weekday() < 5)


def deadlines_for(stage: str, started: str) -> tuple[str, str | None]:
    """(acknowledgement due, response due) for a stage starting on *started*."""
    ack = school_days_after(started, ACK_DAYS).isoformat()
    n = RESPONSE_DAYS.get(stage, 0)
    return ack, (school_days_after(started, n).isoformat() if n else None)


# ── Cleaning ─────────────────────────────────────────────────────────

def _date(value: Any, label: str, problems: list[str]) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return _dt.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _choice(value: Any, options: tuple[str, ...], label: str, problems: list[str],
            default: str | None) -> str | None:
    v = str(value or "").strip()
    if not v:
        return default
    hit = next((o for o in options if o.lower() == v.lower()), None)
    if hit is None:
        problems.append(f"{label} must be one of {', '.join(options)}")
        return default
    return hit


def stage_of(value: Any, problems: list[str] | None = None) -> str | None:
    v = str(value or "").strip()
    if not v:
        return None
    hit = next((s for s in STAGES if s.lower() == v.lower()), None) or \
        _STAGE_ALIASES.get(v.lower())
    if hit is None and problems is not None:
        problems.append(f"Stage must be one of {', '.join(STAGES)}")
    return hit


def _text(value: Any, limit: int) -> str | None:
    return (str(value or "").strip()[:limit]) or None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _pupil(ref: Any) -> P.Pupil | None:
    if ref in (None, ""):
        return None
    if isinstance(ref, int) or str(ref).strip().isdigit():
        return P.get_pupil(int(ref))
    return P.find_by_reference(str(ref).strip())


FIELDS = ("received_on", "complainant_name", "complainant_role", "contact_email",
          "contact_phone", "complainant_address", "subject", "description", "category",
          "severity", "assigned_to", "acknowledged_on", "target_response_date",
          "response_issued_on", "response_summary", "outcome", "actions_taken",
          "complainant_informed", "complainant_satisfaction", "escalated_to_stage_2",
          "escalated_to_appeal", "governors_informed", "linked_to", "status", "closed_on",
          "notes")


def _clean(data: dict[str, Any], cur: Complaint | None) -> tuple[dict[str, Any], list[str]]:
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    problems: list[str] = []
    merged = {k: getattr(cur, k) for k in (*FIELDS, "stage")} if cur else {}
    merged.update({k: v for k, v in data.items() if k in (*FIELDS, "stage")})
    out: dict[str, Any] = {}
    for k, label in (("received_on", "Received on"), ("acknowledged_on", "Acknowledged on"),
                     ("target_response_date", "Target response date"),
                     ("response_issued_on", "Response issued on"), ("closed_on", "Closed on")):
        out[k] = _date(merged.get(k), label, problems)
    today = _today().isoformat()
    out["received_on"] = out["received_on"] or today
    if out["received_on"] > today:
        problems.append("Received on can't be in the future")
    for k in ("acknowledged_on", "response_issued_on", "closed_on"):
        if out[k] and out[k] < out["received_on"]:
            problems.append(f"{k.replace('_', ' ').capitalize()} can't be before the complaint "
                            "was received")
    out["complainant_role"] = _choice(merged.get("complainant_role"), COMPLAINANT_ROLES,
                                      "Complainant role", problems, DEFAULT_COMPLAINANT_ROLE)
    out["complainant_name"] = _text(merged.get("complainant_name"), 120)
    if not out["complainant_name"]:
        if out["complainant_role"] == "Anonymous":
            out["complainant_name"] = "Anonymous"
        else:
            problems.append("Complainant name is required")
    out["contact_email"] = _text(merged.get("contact_email"), 200)
    if out["contact_email"] and not C.valid_email(out["contact_email"]):
        problems.append("Contact e-mail doesn't look like an e-mail address")
    out["contact_phone"] = _text(merged.get("contact_phone"), 40)
    out["complainant_address"] = _text(merged.get("complainant_address"), 300)
    out["subject"] = _text(merged.get("subject"), 200)
    if not out["subject"]:
        problems.append("Subject is required")
    out["description"] = _text(merged.get("description"), 8000)
    out["category"] = _choice(merged.get("category"), CATEGORIES, "Category", problems,
                              DEFAULT_CATEGORY)
    out["stage"] = stage_of(merged.get("stage"), problems) or DEFAULT_STAGE
    try:
        sev = int(str(merged.get("severity") or 2).strip())
    except ValueError:
        sev = 0
    if sev not in SEVERITIES:
        problems.append("Severity must be 1-5")
        sev = 2
    out["severity"] = sev
    out["status"] = _choice(merged.get("status"), STATUSES, "Status", problems, DEFAULT_STATUS)
    oc = str(merged.get("outcome") or "").strip()
    out["outcome"] = _choice(oc, OUTCOMES, "Outcome", problems, None) if oc else None
    out["complainant_satisfaction"] = _choice(merged.get("complainant_satisfaction"),
                                              SATISFACTIONS, "Satisfaction", problems,
                                              DEFAULT_SATISFACTION)
    for k, n in (("assigned_to", 80), ("response_summary", 8000), ("actions_taken", 4000),
                 ("linked_to", 200), ("notes", 8000)):
        out[k] = _text(merged.get(k), n)
    for k in ("complainant_informed", "escalated_to_stage_2", "escalated_to_appeal",
              "governors_informed"):
        out[k] = _bool(merged.get(k))
    if out["status"] == "Closed" and not out["closed_on"]:
        out["closed_on"] = today
    if out["status"] != "Closed" and out["closed_on"]:
        if cur is not None and cur.status == "Closed" and "closed_on" not in data:
            out["closed_on"] = None
        else:
            problems.append("Closed on should only be set when the status is Closed")
    if out["response_issued_on"] and not out["response_summary"]:
        problems.append("Add the response summary when a response has been issued")
    return out, problems


# ── Reading ──────────────────────────────────────────────────────────

def get(complaint_id: int) -> Complaint:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE c.complaint_id = ?", (int(complaint_id),)).fetchone()
    if r is None:
        raise NotFound(f"No complaint #{complaint_id}")
    return _row(r)


def get_complaint(complaint_id: int) -> Complaint | None:
    """The old lookup: None when there is no such complaint."""
    try:
        return get(complaint_id)
    except NotFound:
        return None


def list_complaints(*, actor: Principal | None = None, category: str | None = None,
                    stage: str | None = None, status: str | None = None,
                    outcome: str | None = None, complainant_role: str | None = None,
                    severity: int | None = None, severity_min: int | None = None,
                    assigned_to_like: str | None = None, complainant_like: str | None = None,
                    subject_like: str | None = None, pupil_id: int | None = None,
                    open_only: bool = False, overdue_only: bool = False,
                    stage2_or_higher: bool = False, unreasonable_only: bool = False,
                    date_from: str | None = None, date_to: str | None = None
                    ) -> list[Complaint]:
    """Newest first (the old filters). With *actor*, only what they may see."""
    where, params = [], []
    st = stage_of(stage) if stage else None
    for col, val in (("c.category", category), ("c.stage", st), ("c.status", status),
                     ("c.outcome", outcome), ("c.complainant_role", complainant_role),
                     ("c.severity", severity), ("c.pupil_id", pupil_id)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if severity_min is not None:
        where.append("c.severity >= ?")
        params.append(int(severity_min))
    for col, val in (("c.assigned_to", assigned_to_like),
                     ("c.complainant_name", complainant_like), ("c.subject", subject_like)):
        if val:
            where.append(f"{col} LIKE ?")
            params.append(f"%{val}%")
    if open_only:
        where.append("c.status != 'Closed'")
    if stage2_or_higher:
        where.append("c.stage IN (?, ?, ?)")
        params += [STAGE_2, STAGE_3, DFE]
    if unreasonable_only:
        where.append("c.unreasonable = 1")
    probs: list[str] = []
    for col, op, val, label in (("c.received_on", ">=", date_from, "From"),
                                ("c.received_on", "<=", date_to, "To")):
        d = _date(val, label, probs)
        if d:
            where.append(f"{col} {op} ?")
            params.append(d)
    if probs:
        raise ValidationError(probs)
    sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY c.received_on DESC, c.complaint_id DESC"
    with database.connect() as conn:
        rows = [_row(r) for r in conn.execute(sql, params)]
    if overdue_only:
        rows = [c for c in rows if c.overdue]
    if actor is None:
        return rows
    _require_staff(actor, "list")
    return [c for c in rows if can_see(actor, c)]


def list_events(complaint_id: int) -> list[Event]:
    with database.connect() as conn:
        return [_event_row(r) for r in conn.execute(
            "SELECT * FROM complaint_events WHERE complaint_id = ? ORDER BY event_date, "
            "event_id", (int(complaint_id),))]


def _same_complainant(c: dict[str, Any] | Complaint, other: Complaint) -> bool:
    get_ = (lambda k: c.get(k)) if isinstance(c, dict) else (lambda k: getattr(c, k))
    email = (get_("contact_email") or "").strip().lower()
    name = (get_("complainant_name") or "").strip().lower()
    if email and (other.contact_email or "").lower() == email:
        return True
    return bool(name) and name != "anonymous" and other.complainant_name.lower() == name


def check(data: dict[str, Any], *, actor: Principal, complaint_id: int | None = None
          ) -> list[str]:
    """Things to know before saving: another procedure applies, the
    complainant is flagged or has complained often, a closed complaint about
    the same thing."""
    _require_staff(actor, "check")
    cur = get(complaint_id) if complaint_id else None
    c, _problems = _clean(data, cur)
    out: list[str] = []
    if c["category"] in OTHER_PROCEDURES:
        out.append(OTHER_PROCEDURES[c["category"]])
    if cur is None and c["complainant_name"]:
        since = (_today() - _dt.timedelta(days=30 * SERIAL_MONTHS)).isoformat()
        theirs = [o for o in list_complaints(date_from=since) if _same_complainant(c, o)]
        if any(o.unreasonable for o in theirs):
            out.append("This complainant is flagged as unreasonable / serial - follow the "
                       "agreed communication plan.")
        if len(theirs) + 1 >= SERIAL_COUNT:
            out.append(f"This would be complaint number {len(theirs) + 1} from this "
                       f"complainant in {SERIAL_MONTHS} months.")
        words = {w for w in (c["subject"] or "").lower().split() if len(w) > 3}
        for o in theirs:
            if not o.is_open and words & {w for w in o.subject.lower().split() if len(w) > 3}:
                out.append(f"Complaint #{o.complaint_id} ('{o.subject}') was closed - if this "
                           "is the same matter, the procedure has been completed.")
                break
    if c["severity"] >= 4:
        out.append("Serious or major: tell the headteacher (and the chair of governors if it "
                   "is about the headteacher).")
    return out


# ── Writing ──────────────────────────────────────────────────────────

def _event(conn, complaint_id: int, event_type: str, summary: str, actor: Principal, *,
           stage: str | None = None, day: str | None = None) -> int:
    return conn.execute(
        "INSERT INTO complaint_events (complaint_id, event_date, event_type, stage, summary, "
        "created_by) VALUES (?, ?, ?, ?, ?, ?)",
        (complaint_id, day or _today().isoformat(), event_type, stage, summary[:4000],
         actor.username)).lastrowid


def create_complaint(payload: dict[str, Any], *, actor: Principal) -> Complaint:
    """The old New complaint. Deadlines are set from the received date in
    school days when not given; ``pupil_id`` (id or admission no.) is optional."""
    _require_editor(actor, "create")
    c, problems = _clean(payload, None)
    pref = payload.get("pupil_id") or payload.get("pupil")
    p = _pupil(pref) if pref not in (None, "") else None
    if pref not in (None, "") and p is None:
        problems.append(f"No pupil {pref}")
    if problems:
        activity_log.record("complaints.create", outcome="invalid", principal=actor,
                            problems=len(problems))
        raise ValidationError(problems)
    started = _date(payload.get("stage_started_on"), "Stage started", []) or c["received_on"]
    ack, resp = deadlines_for(c["stage"], started)
    c["target_response_date"] = c["target_response_date"] or resp
    cols = (*FIELDS, "stage")
    with database.connect() as conn:
        cid = conn.execute(
            f"INSERT INTO complaints ({', '.join(cols)}, pupil_id, stage_started_on, ack_due, "
            f"created_by) VALUES ({', '.join('?' * len(cols))}, ?, ?, ?, ?)",
            (*(int(c[k]) if k in _BOOLS else c[k] for k in cols),
             p.pupil_id if p else None, started, ack, actor.username)).lastrowid
        _event(conn, cid, "Note", f"Complaint received ({c['category']})", actor,
               stage=c["stage"], day=c["received_on"])
        _audit(conn, "create", actor, cid, stage=c["stage"])
    activity_log.record("complaints.create", target=f"complaint:{cid}", principal=actor)
    return get(cid)


def update_complaint(complaint_id: int, payload: dict[str, Any], *, actor: Principal
                     ) -> Complaint:
    """The old Edit. The stage changes through :func:`escalate`."""
    cur = get(complaint_id)
    _require_editor(actor, "update", f"complaint:{cur.complaint_id}")
    data = dict(payload)
    st = stage_of(data.pop("stage", None))
    if st and st != cur.stage:
        raise ValidationError([f"Use Escalate to move from {cur.stage} to {st}"])
    c, problems = _clean(data, cur)
    sets: dict[str, Any] = {k: (int(c[k]) if k in _BOOLS else c[k]) for k in FIELDS
                            if c[k] != getattr(cur, k)}
    if "pupil_id" in payload:
        pref = payload.get("pupil_id")
        p = _pupil(pref) if pref not in (None, "") else None
        if pref not in (None, "") and p is None:
            problems.append(f"No pupil {pref}")
        if (p.pupil_id if p else None) != cur.pupil_id:
            sets["pupil_id"] = p.pupil_id if p else None
    if problems:
        raise ValidationError(problems)
    if not sets:
        return cur
    with database.connect() as conn:
        conn.execute("UPDATE complaints SET " + ", ".join(f"{k} = ?" for k in sets)
                     + ", updated_on = datetime('now') WHERE complaint_id = ?",
                     (*sets.values(), cur.complaint_id))
        _audit(conn, "update", actor, cur.complaint_id, fields=list(sets))
    activity_log.record("complaints.update", target=f"complaint:{cur.complaint_id}",
                        principal=actor, fields=",".join(sets))
    return get(cur.complaint_id)


def delete_complaint(complaint_id: int, *, actor: Principal) -> bool:
    c = get(complaint_id)
    _require_editor(actor, "delete", f"complaint:{c.complaint_id}")
    if c.stage_no >= 3:
        raise ValidationError(["A complaint that reached the governors' panel is part of the "
                               "governors' record - close it instead"])
    with database.connect() as conn:
        conn.execute("DELETE FROM complaints WHERE complaint_id = ?", (c.complaint_id,))
        _audit(conn, "delete", actor, c.complaint_id)
    activity_log.record("complaints.delete", target=f"complaint:{c.complaint_id}",
                        principal=actor)
    return True


def _set(c: Complaint, actor: Principal, action: str, sets: dict[str, Any],
         event: tuple[str, str] | None = None, day: str | None = None) -> Complaint:
    with database.connect() as conn:
        conn.execute("UPDATE complaints SET " + ", ".join(f"{k} = ?" for k in sets)
                     + ", updated_on = datetime('now') WHERE complaint_id = ?",
                     (*sets.values(), c.complaint_id))
        if event:
            _event(conn, c.complaint_id, event[0], event[1], actor, stage=sets.get("stage",
                                                                                   c.stage),
                   day=day)
        _audit(conn, action, actor, c.complaint_id, **{k: v for k, v in sets.items()
                                                       if k in ("status", "stage", "outcome")})
    activity_log.record(f"complaints.{action}", target=f"complaint:{c.complaint_id}",
                        principal=actor)
    return get(c.complaint_id)


def add_event(complaint_id: int, data: dict[str, Any], *, actor: Principal) -> Event:
    c = get(complaint_id)
    _see(actor, c, "event")
    problems: list[str] = []
    etype = _choice(data.get("event_type"), EVENT_TYPES, "Type", problems, "Note")
    day = _date(data.get("event_date"), "Date", problems) or _today().isoformat()
    if day > _today().isoformat():
        problems.append("The date can't be in the future")
    summary = str(data.get("summary") or "").strip()
    if not summary:
        problems.append("Summary is required")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        eid = _event(conn, c.complaint_id, etype, summary, actor, stage=c.stage, day=day)
        _audit(conn, "event", actor, c.complaint_id, event=eid, type=etype)
        return _event_row(conn.execute("SELECT * FROM complaint_events WHERE event_id = ?",
                                       (eid,)).fetchone())


def delete_event(event_id: int, *, actor: Principal) -> bool:
    with database.connect() as conn:
        r = conn.execute("SELECT complaint_id FROM complaint_events WHERE event_id = ?",
                         (int(event_id),)).fetchone()
    if r is None:
        raise NotFound(f"No event #{event_id}")
    _require_editor(actor, "event_delete", f"complaint:{r['complaint_id']}")
    with database.connect() as conn:
        conn.execute("DELETE FROM complaint_events WHERE event_id = ?", (int(event_id),))
        _audit(conn, "event_delete", actor, r["complaint_id"], event=int(event_id))
    return True


# ── Workflow ─────────────────────────────────────────────────────────

def acknowledge(complaint_id: int, *, actor: Principal, assigned_to: str | None = None,
                acknowledged_on: str | None = None,
                target_response_date: str | None = None) -> Complaint:
    c = get(complaint_id)
    if not can_handle_stage_1(actor, c):
        _deny(actor, "acknowledge", f"complaint:{c.complaint_id}",
              "Only the complaints lead (or the member of staff at stage 1) can do that.")
    problems: list[str] = []
    d = _date(acknowledged_on, "Acknowledged on", problems) or _today().isoformat()
    t = _date(target_response_date, "Target response date", problems)
    if d < c.received_on:
        problems.append("Acknowledged on can't be before the complaint was received")
    if t and t < d:
        problems.append("The target response date can't be before the acknowledgement")
    if assigned_to and not is_editor(actor):
        problems.append("Only the complaints lead can assign the complaint")
    if problems:
        raise ValidationError(problems)
    sets: dict[str, Any] = {"acknowledged_on": d}
    if assigned_to:
        sets["assigned_to"] = assigned_to.strip()[:80]
    if t:
        sets["target_response_date"] = t
    if c.status in ("Received", "Escalated"):
        sets["status"] = "Acknowledged"
    late = c.ack_due and d > c.ack_due
    return _set(c, actor, "acknowledge", sets, ("Acknowledged", "Complaint acknowledged"
                                                + (" (late)" if late else "")), day=d)


def start_investigation(complaint_id: int, *, actor: Principal,
                        investigator: str | None = None) -> Complaint:
    c = get(complaint_id)
    if not can_handle_stage_1(actor, c):
        _deny(actor, "investigate", f"complaint:{c.complaint_id}",
              "Only the complaints lead (or the member of staff at stage 1) can do that.")
    if not c.is_open:
        raise ValidationError(["The complaint is closed"])
    sets: dict[str, Any] = {"status": "Under Investigation"}
    if investigator and is_editor(actor):
        sets["assigned_to"] = investigator.strip()[:80]
    if not c.acknowledged_on:
        sets["acknowledged_on"] = _today().isoformat()
    return _set(c, actor, "investigate", sets,
                ("Investigation", "Investigation started"
                 + (f" by {sets['assigned_to']}" if "assigned_to" in sets else "")))


def issue_response(complaint_id: int, *, actor: Principal, summary: str, outcome: str,
                   issued_on: str | None = None, actions_taken: str | None = None
                   ) -> Complaint:
    """The written response for the current stage (outcome and summary)."""
    c = get(complaint_id)
    if not can_handle_stage_1(actor, c):
        _deny(actor, "respond", f"complaint:{c.complaint_id}",
              "Only the complaints lead (or the member of staff at stage 1) can do that.")
    problems: list[str] = []
    if not (summary or "").strip():
        problems.append("Response summary is required")
    oc = _choice(outcome, OUTCOMES, "Outcome", problems, None)
    if not oc and not problems:
        problems.append(f"Outcome must be one of: {', '.join(OUTCOMES)}")
    d = _date(issued_on, "Issued on", problems) or _today().isoformat()
    if d < c.received_on:
        problems.append("Issued on can't be before the complaint was received")
    if not c.is_open:
        problems.append("The complaint is closed")
    if c.stage == STAGE_3 and not c.panel_date:
        problems.append("Record the governors' panel (date and members) first")
    if problems:
        raise ValidationError(problems)
    sets: dict[str, Any] = {"response_summary": summary.strip()[:8000], "outcome": oc,
                            "response_issued_on": d, "status": "Response Issued",
                            "complainant_informed": 1}
    if c.stage == STAGE_3:
        sets["governors_informed"] = 1
    if actions_taken and actions_taken.strip():
        sets["actions_taken"] = actions_taken.strip()[:4000]
    if not c.acknowledged_on:
        sets["acknowledged_on"] = d
    return _set(c, actor, "respond", sets, ("Response", f"{c.stage} response: {oc}"), day=d)


def escalation_problems(c: Complaint, to_stage: str) -> list[str]:
    out: list[str] = []
    if to_stage not in STAGES:
        return [f"Stage must be one of: {', '.join(STAGES)}"]
    if STAGES.index(to_stage) <= STAGES.index(c.stage):
        out.append(f"Cannot escalate from {c.stage} to {to_stage}")
    if c.outcome == "Withdrawn":
        out.append("The complaint was withdrawn")
    if not c.response_issued_on and not c.response_overdue:
        out.append(f"Wait for the {c.stage} response (due {c.target_response_date or '-'}) - "
                   "or escalate once it is overdue")
    return out


def escalate(complaint_id: int, *, actor: Principal, to_stage: str,
             reason: str | None = None, requested_on: str | None = None) -> Complaint:
    """Move to a later stage at the complainant's request: new deadlines
    from the request date; the stage's response is cleared."""
    c = get(complaint_id)
    _require_editor(actor, "escalate", f"complaint:{c.complaint_id}")
    problems: list[str] = []
    st = stage_of(to_stage, problems) or ""
    problems += escalation_problems(c, st) if st else []
    d = _date(requested_on, "Requested on", problems) or _today().isoformat()
    if problems:
        raise ValidationError(problems)
    ack, resp = deadlines_for(st, d)
    note = f"{d} escalated to {st}" + (f": {reason.strip()}" if reason and reason.strip()
                                       else "")
    if c.response_issued_on and school_days_between(c.response_issued_on, d) > ESCALATE_WITHIN:
        note += f" (asked more than {ESCALATE_WITHIN} school days after the response)"
    sets: dict[str, Any] = {
        "stage": st, "stage_started_on": d, "ack_due": ack, "target_response_date": resp,
        "acknowledged_on": None, "status": "Escalated", "response_issued_on": None,
        "response_summary": None, "outcome": None, "closed_on": None,
        "notes": ((c.notes + "\n") if c.notes else "") + note}
    if st == STAGE_2:
        sets["escalated_to_stage_2"] = 1
    elif st in (STAGE_3, DFE):
        sets["escalated_to_appeal"] = 1
        sets["governors_informed"] = 1
    return _set(c, actor, "escalate", sets, ("Escalated", note), day=d)


def set_panel(complaint_id: int, *, actor: Principal, panel_date: str, members: list[str] |
              str, note: str | None = None) -> Complaint:
    """The governors' panel for stage 3: date and at least three members,
    none of them involved in the complaint."""
    c = get(complaint_id)
    _require_editor(actor, "panel", f"complaint:{c.complaint_id}")
    problems: list[str] = []
    if c.stage != STAGE_3:
        problems.append("Only a stage 3 complaint goes to the governors' panel")
    d = _date(panel_date, "Panel date", problems)
    if not d:
        problems.append("Panel date is required")
    names = [m.strip() for m in (members.split(",") if isinstance(members, str) else members)
             if m and m.strip()]
    if len(set(n.lower() for n in names)) < PANEL_MIN:
        problems.append(f"The panel needs at least {PANEL_MIN} members")
    involved = {(c.assigned_to or "").lower()} - {""}
    if any(n.lower() in involved for n in names):
        problems.append("Panel members can't have been involved in the complaint")
    if problems:
        raise ValidationError(problems)
    sets = {"panel_date": d, "panel_members": ", ".join(names), "governors_informed": 1}
    return _set(c, actor, "panel", sets, ("Panel", f"Governors' panel on {d}: "
                                                   f"{', '.join(names)}"
                                                   + (f". {note.strip()}" if note and
                                                      note.strip() else "")))


def record_satisfaction(complaint_id: int, *, actor: Principal, satisfaction: str
                        ) -> Complaint:
    c = get(complaint_id)
    _see(actor, c, "satisfaction")
    problems: list[str] = []
    s = _choice(satisfaction, SATISFACTIONS, "Satisfaction", problems, None)
    if problems or not s:
        raise ValidationError(problems or [f"Satisfaction must be one of: "
                                           f"{', '.join(SATISFACTIONS)}"])
    return _set(c, actor, "satisfaction", {"complainant_satisfaction": s},
                ("Note", f"Complainant {s.lower()}"))


def close_complaint(complaint_id: int, *, actor: Principal, closed_on: str | None = None
                    ) -> Complaint:
    c = get(complaint_id)
    _require_editor(actor, "close", f"complaint:{c.complaint_id}")
    problems: list[str] = []
    d = _date(closed_on, "Closed on", problems) or c.closed_on or _today().isoformat()
    if d < c.received_on:
        problems.append("Closed on can't be before the complaint was received")
    if not c.outcome:
        problems.append("Issue the response (or withdraw the complaint) before closing it")
    if problems:
        raise ValidationError(problems)
    return _set(c, actor, "close", {"status": "Closed", "closed_on": d},
                ("Decision", "Complaint closed"), day=d)


def withdraw(complaint_id: int, *, actor: Principal, reason: str = "") -> Complaint:
    c = get(complaint_id)
    _require_editor(actor, "withdraw", f"complaint:{c.complaint_id}")
    if not c.is_open:
        raise ValidationError(["The complaint is already closed"])
    return _set(c, actor, "withdraw", {"outcome": "Withdrawn", "status": "Closed",
                                       "closed_on": _today().isoformat()},
                ("Decision", "Withdrawn by the complainant"
                 + (f": {reason.strip()}" if reason and reason.strip() else "")))


def set_status(complaint_id: int, new_status: str, *, actor: Principal) -> Complaint:
    c = get(complaint_id)
    _require_editor(actor, "status", f"complaint:{c.complaint_id}")
    problems: list[str] = []
    st = _choice(new_status, STATUSES, "Status", problems, None)
    if problems or not st:
        raise ValidationError(problems or [f"Status must be one of: {', '.join(STATUSES)}"])
    sets: dict[str, Any] = {"status": st}
    if st == "Closed":
        sets["closed_on"] = c.closed_on or _today().isoformat()
    elif c.closed_on:
        sets["closed_on"] = None
    return _set(c, actor, "status", sets, ("Note", f"Status: {c.status} -> {st}"))


def flag_unreasonable(complaint_id: int, flag: bool, *, actor: Principal,
                      notes: str | None = None, review_date: str | None = None) -> Complaint:
    """Mark the complainant as unreasonable / serial (a communication plan,
    reviewed), or clear it. Applies to the complainant's other complaints."""
    c = get(complaint_id)
    _require_editor(actor, "unreasonable", f"complaint:{c.complaint_id}")
    problems: list[str] = []
    rd = _date(review_date, "Review date", problems)
    if flag and not (notes or "").strip():
        problems.append("Record why, and what the communication plan is")
    if flag and not rd:
        rd = (_today() + _dt.timedelta(days=180)).isoformat()
    if problems:
        raise ValidationError(problems)
    targets = [o for o in list_complaints() if o.complaint_id == c.complaint_id or
               _same_complainant(c, o)]
    with database.connect() as conn:
        for o in targets:
            conn.execute("UPDATE complaints SET unreasonable = ?, unreasonable_notes = ?, "
                         "unreasonable_review = ?, updated_on = datetime('now') "
                         "WHERE complaint_id = ?",
                         (int(flag), ((notes or "").strip()[:2000] or None) if flag else None,
                          rd if flag else None, o.complaint_id))
        _event(conn, c.complaint_id, "Decision",
               "Complainant flagged as unreasonable / serial" if flag else
               "Unreasonable-complainant flag removed", actor)
        _audit(conn, "unreasonable", actor, c.complaint_id, flag=flag, complaints=len(targets))
    return get(c.complaint_id)


# ── Lists and reports ────────────────────────────────────────────────

def overdue(*, actor: Principal | None = None) -> list[tuple[Complaint, str, str]]:
    """(complaint, what, due) for late acknowledgements and responses."""
    out = []
    for c in list_complaints(actor=actor, open_only=True):
        if c.ack_overdue:
            out.append((c, "Acknowledgement", c.ack_due or ""))
        if c.response_overdue:
            out.append((c, f"{c.stage} response", c.target_response_date or ""))
    return sorted(out, key=lambda x: x[2])


def serial_complainants(*, months: int = SERIAL_MONTHS, min_count: int = SERIAL_COUNT
                        ) -> list[dict[str, Any]]:
    since = (_today() - _dt.timedelta(days=30 * months)).isoformat()
    groups: dict[str, list[Complaint]] = {}
    for c in list_complaints(date_from=since):
        if c.complainant_role == "Anonymous":
            continue
        key = (c.contact_email or c.complainant_name).strip().lower()
        groups.setdefault(key, []).append(c)
    out = [{"complainant": v[0].complainant_name, "email": v[0].contact_email,
            "count": len(v), "flagged": any(x.unreasonable for x in v),
            "ids": [x.complaint_id for x in v]}
           for v in groups.values() if len(v) >= min_count or any(x.unreasonable for x in v)]
    return sorted(out, key=lambda x: -x["count"])


def summary() -> ComplaintsSummary:
    rows = list_complaints()
    out = ComplaintsSummary(total=len(rows))
    days: list[int] = []
    for c in rows:
        if c.is_open:
            out.open_count += 1
            out.overdue += int(c.overdue)
        else:
            out.closed_count += 1
            if c.days_open is not None:
                days.append(c.days_open)
        out.serious_or_major += int(c.severity >= 4)
        out.at_stage_2_or_appeal += int(c.stage_no >= 2)
        out.governors_informed += int(c.governors_informed)
        out.upheld_count += int(c.outcome == "Upheld")
        out.not_upheld_count += int(c.outcome == "Not Upheld")
        out.unreasonable += int(c.unreasonable)
        for d, k in ((out.by_category, c.category), (out.by_stage, c.stage),
                     (out.by_status, c.status)):
            d[k] = d.get(k, 0) + 1
        if c.outcome:
            out.by_outcome[c.outcome] = out.by_outcome.get(c.outcome, 0) + 1
    if days:
        out.average_days_to_close = round(sum(days) / len(days), 1)
    return out


def annual_report(academic_year: str | None = None) -> dict[str, Any]:
    """For the governors: complaints received in the school year."""
    year = academic_year or current_year()
    rows = [c for c in list_complaints() if year_of(c.received_on) == year]
    closed = [c for c in rows if not c.is_open]
    on_time = 0
    responded = 0
    for c in rows:
        if c.response_issued_on and c.target_response_date:
            responded += 1
            on_time += int(c.response_issued_on <= c.target_response_date)
    days = [c.days_open for c in closed if c.days_open is not None]
    return {"academic_year": year, "received": len(rows), "closed": len(closed),
            "open": len(rows) - len(closed),
            "by_category": dict(Counter(c.category for c in rows).most_common()),
            "by_stage_reached": {s: sum(1 for c in rows if c.stage == s) for s in STAGES},
            "by_outcome": dict(Counter(c.outcome or "(not yet)" for c in rows)),
            "by_role": dict(Counter(c.complainant_role for c in rows)),
            "responses_on_time": on_time, "responses": responded,
            "on_time_pct": round(100.0 * on_time / responded, 1) if responded else None,
            "avg_days_to_close": round(sum(days) / len(days), 1) if days else None,
            "withdrawn": sum(1 for c in rows if c.outcome == "Withdrawn"),
            "unreasonable": len({(c.contact_email or c.complainant_name).lower()
                                 for c in rows if c.unreasonable}),
            "panels": sum(1 for c in rows if c.panel_date)}


# ── Letters ──────────────────────────────────────────────────────────

def letter_text(c: Complaint, kind: str) -> tuple[str, str, str]:
    """(headline, intro, details) for a letter."""
    if kind == "acknowledgement":
        ack, resp = c.ack_due, c.target_response_date
        return (f"We have received your complaint ({c.stage.split(' - ')[0].lower()})",
                f"Thank you for your complaint about \"{c.subject}\", which we received on "
                f"{c.received_on}. It is being dealt with by {STAGE_HANDLER[c.stage]}"
                + (f" ({c.assigned_to})" if c.assigned_to and c.stage == STAGE_1 else "")
                + ".",
                (f"We aim to send you a full response by {resp}." if resp else "")
                + (" If we need longer we will tell you why and give a new date."
                   if resp else ""))
    if kind == "response":
        nxt = STAGES[c.stage_no] if c.stage_no < len(STAGES) else None
        return (f"Our response to your complaint ({c.stage.split(' - ')[0].lower()})",
                f"We have now looked into your complaint about \"{c.subject}\". Our "
                f"conclusion: {(c.outcome or '').lower()}.",
                (c.response_summary or "")
                + (f"\n\nWhat we will do: {c.actions_taken}" if c.actions_taken else "")
                + (f"\n\nIf you are not satisfied, you can ask for your complaint to go to "
                   f"{nxt.split(' - ')[-1].lower()} ({STAGE_HANDLER[nxt]}) within "
                   f"{ESCALATE_WITHIN} school days of this letter." if nxt and nxt != DFE else
                   "\n\nThis completes the school's complaints procedure. If you believe the "
                   "school did not follow its procedure, you can contact the Department for "
                   "Education." if c.stage == STAGE_3 else ""))
    return (f"Your complaint has moved to {c.stage.split(' - ')[0].lower()}",
            f"We have received your request for your complaint about \"{c.subject}\" to be "
            f"considered at {c.stage.lower()} ({STAGE_HANDLER[c.stage]}).",
            (f"The governors' panel will meet on {c.panel_date} ({c.panel_members}). You may "
             "attend and bring someone with you." if c.panel_date else
             f"We will send you a response by {c.target_response_date}."
             if c.target_response_date else ""))


def send_letter(complaint_id: int, kind: str, *, actor: Principal, note: str | None = None
                ) -> dict[str, Any]:
    """E-mail the complainant through the school outbox: acknowledgement,
    response or escalation. Returns {'message_id', 'emails'}."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
    c = get(complaint_id)
    if kind not in LETTERS:
        raise ValidationError([f"Letter must be one of {', '.join(LETTERS)}"])
    if not (is_editor(actor) or (kind != "escalation" and can_handle_stage_1(actor, c))):
        _deny(actor, "letter", f"complaint:{c.complaint_id}",
              "Only the complaints lead can send that letter.")
    problems: list[str] = []
    if kind == "response" and not c.response_issued_on:
        problems.append("Issue the response first")
    if kind == "escalation" and c.stage_no < 2:
        problems.append("The complaint hasn't been escalated")
    if problems:
        raise ValidationError(problems)
    if not c.contact_email:
        return {"message_id": None, "emails": 0}
    template_name, label = LETTERS[kind]
    headline, intro, details = letter_text(c, kind)
    if note and note.strip():
        details = (details + "\n\n" + note.strip()).strip()
    subject, body = email_templates.load_template(template_name).render({
        "recipient_name": c.complainant_name, "headline": headline, "reference": c.complaint_id,
        "complaint_subject": c.subject, "intro": intro, "details": details,
        "sender_name": BH._staff_name(actor)})
    mid = E.save_prepared(f"complaint_{kind}", label, subject, "(complaint letter)",
                          [(c.contact_email, c.complainant_name, subject, body)], actor=actor)
    with database.connect() as conn:
        conn.execute("UPDATE complaints SET complainant_informed = 1, updated_on = "
                     "datetime('now') WHERE complaint_id = ?", (c.complaint_id,))
        _event(conn, c.complaint_id, "Letter sent", f"{label} e-mailed", actor, stage=c.stage)
        _audit(conn, "letter", actor, c.complaint_id, kind=kind)
    activity_log.record("complaints.letter", target=f"complaint:{c.complaint_id}",
                        principal=actor, kind=kind)
    return {"message_id": mid, "emails": 1}


# ── Export ───────────────────────────────────────────────────────────

def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    _require_staff(actor, "export")
    rows = list_complaints(actor=actor, **filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "received", "complainant", "role", "pupil", "category", "subject",
                    "stage", "severity", "assigned_to", "acknowledged", "ack_due",
                    "response_due", "responded", "outcome", "status", "closed", "satisfaction",
                    "panel_date", "unreasonable"])
        for c in rows:
            w.writerow([c.complaint_id, c.received_on, _safe(c.complainant_name),
                        c.complainant_role, _safe(c.pupil_name), c.category, _safe(c.subject),
                        c.stage, c.severity, _safe(c.assigned_to), c.acknowledged_on or "",
                        c.ack_due or "", c.target_response_date or "",
                        c.response_issued_on or "", c.outcome or "", c.status,
                        c.closed_on or "", c.complainant_satisfaction, c.panel_date or "",
                        "yes" if c.unreasonable else ""])
    activity_log.record("complaints.export", principal=actor, rows=len(rows))
    return len(rows)
