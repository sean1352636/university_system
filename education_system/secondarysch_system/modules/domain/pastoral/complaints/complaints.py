"""Complaints data layer for Secondary School System.

Formal complaints register. Three-stage workflow (Informal →
Formal Stage 1 → Formal Stage 2 → Appeal/Governors). Outcomes
(Upheld / Partially Upheld / Not Upheld / Withdrawn) and full
escalation tracking. Complainants are free-text (parent / student /
member of public / staff) so the table doesn't require an FK.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.secondarysch_system.core import paths as _paths

logger = logging.getLogger(__name__)

CATEGORIES: tuple[str, ...] = (
    "Teaching & Learning",
    "Behaviour & Discipline",
    "Communication",
    "Premises & Facilities",
    "Admissions",
    "Exams & Assessment",
    "Pastoral / Wellbeing",
    "Safeguarding",
    "Bullying / Harassment",
    "Staff Conduct",
    "Discrimination",
    "SEND Provision",
    "Catering",
    "Transport",
    "Finance / Fees",
    "Data Protection",
    "Other",
)
DEFAULT_CATEGORY = "Other"

COMPLAINANT_ROLES: tuple[str, ...] = (
    "Parent / Carer",
    "Student",
    "Member of Public",
    "Staff",
    "Former Student",
    "Anonymous",
    "Other",
)
DEFAULT_COMPLAINANT_ROLE = "Parent / Carer"

STAGES: tuple[str, ...] = (
    "Informal",
    "Formal Stage 1",
    "Formal Stage 2",
    "Appeal / Governors",
)
DEFAULT_STAGE = "Informal"

SEVERITIES: tuple[int, ...] = (1, 2, 3, 4, 5)
_SEVERITY_LABELS = {
    1: "Low", 2: "Routine", 3: "Standard",
    4: "Serious", 5: "Major",
}


def severity_label(s: int | None) -> str:
    if s is None:
        return "—"
    return _SEVERITY_LABELS.get(s, "Unknown")


STATUSES: tuple[str, ...] = (
    "Received",
    "Acknowledged",
    "Under Investigation",
    "Response Drafted",
    "Response Issued",
    "Escalated",
    "Closed",
)
DEFAULT_STATUS = "Received"

OUTCOMES: tuple[str, ...] = (
    "Upheld",
    "Partially Upheld",
    "Not Upheld",
    "Withdrawn",
    "No Action",
)

SATISFACTIONS: tuple[str, ...] = (
    "Satisfied",
    "Partially Satisfied",
    "Not Satisfied",
    "Not Recorded",
)
DEFAULT_SATISFACTION = "Not Recorded"


class ValidationError(Exception):
    pass


@dataclass
class Complaint:
    complaint_id: int
    received_on: str
    complainant_name: str
    complainant_role: str
    contact_email: str | None
    contact_phone: str | None
    subject: str
    description: str | None
    category: str
    stage: str
    severity: int
    assigned_to: str | None
    acknowledged_on: str | None
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
    created_on: str
    updated_on: str

    @property
    def is_open(self) -> bool:
        return self.status != "Closed"

    @property
    def severity_label(self) -> str:
        return severity_label(self.severity)

    @property
    def response_overdue(self) -> bool:
        if (not self.is_open or self.response_issued_on
                or not self.target_response_date):
            return False
        return self.target_response_date < _dt.date.today().isoformat()

    @property
    def days_open(self) -> int | None:
        try:
            start = _dt.date.fromisoformat(self.received_on)
        except ValueError:
            return None
        end = (_dt.date.fromisoformat(self.closed_on)
                if self.closed_on else _dt.date.today())
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
    by_category: dict[str, int] = field(default_factory=dict)
    by_stage: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_outcome: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.COMPLAINTS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                complaint_id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_on TEXT NOT NULL,
                complainant_name TEXT NOT NULL,
                complainant_role TEXT NOT NULL,
                contact_email TEXT,
                contact_phone TEXT,
                subject TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                stage TEXT NOT NULL,
                severity INTEGER NOT NULL,
                assigned_to TEXT,
                acknowledged_on TEXT,
                target_response_date TEXT,
                response_issued_on TEXT,
                response_summary TEXT,
                outcome TEXT,
                actions_taken TEXT,
                complainant_informed INTEGER NOT NULL DEFAULT 0,
                complainant_satisfaction TEXT NOT NULL,
                escalated_to_stage_2 INTEGER NOT NULL DEFAULT 0,
                escalated_to_appeal INTEGER NOT NULL DEFAULT 0,
                governors_informed INTEGER NOT NULL DEFAULT 0,
                linked_to TEXT,
                status TEXT NOT NULL,
                closed_on TEXT,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL
            )
        """)


def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _validate_payload(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["received_on"] = (out.get("received_on") or "").strip()
    if not out["received_on"]:
        out["received_on"] = _dt.date.today().isoformat()
    _check_date("Received on",          out["received_on"])
    _check_date("Acknowledged on",      out.get("acknowledged_on"))
    _check_date("Target response date", out.get("target_response_date"))
    _check_date("Response issued on",   out.get("response_issued_on"))
    _check_date("Closed on",            out.get("closed_on"))

    out["complainant_name"] = (out.get("complainant_name") or "").strip()
    if not out["complainant_name"]:
        raise ValidationError("Complainant name is required")

    role = (out.get("complainant_role")
              or DEFAULT_COMPLAINANT_ROLE).strip()
    if role not in COMPLAINANT_ROLES:
        raise ValidationError(
            f"Complainant role must be one of: "
            f"{', '.join(COMPLAINANT_ROLES)}")
    out["complainant_role"] = role

    out["subject"] = (out.get("subject") or "").strip()
    if not out["subject"]:
        raise ValidationError("Subject is required")

    cat = (out.get("category") or DEFAULT_CATEGORY).strip()
    if cat not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(CATEGORIES)}")
    out["category"] = cat

    stage = (out.get("stage") or DEFAULT_STAGE).strip()
    if stage not in STAGES:
        raise ValidationError(
            f"Stage must be one of: {', '.join(STAGES)}")
    out["stage"] = stage

    try:
        sev = int(out.get("severity") or 2)
    except (TypeError, ValueError):
        raise ValidationError("Severity must be 1-5")
    if sev not in SEVERITIES:
        raise ValidationError("Severity must be 1-5")
    out["severity"] = sev

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    outcome = (out.get("outcome") or "").strip()
    if outcome and outcome not in OUTCOMES:
        raise ValidationError(
            f"Outcome must be one of: {', '.join(OUTCOMES)}")
    out["outcome"] = outcome or None

    sat = (out.get("complainant_satisfaction")
             or DEFAULT_SATISFACTION).strip()
    if sat not in SATISFACTIONS:
        raise ValidationError(
            f"Satisfaction must be one of: "
            f"{', '.join(SATISFACTIONS)}")
    out["complainant_satisfaction"] = sat

    for k in ("contact_email", "contact_phone", "description",
               "assigned_to", "response_summary", "actions_taken",
               "linked_to", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("acknowledged_on", "target_response_date",
               "response_issued_on", "closed_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    for k in ("complainant_informed", "escalated_to_stage_2",
               "escalated_to_appeal", "governors_informed"):
        out[k] = bool(out.get(k))
    return out


def _row(r: sqlite3.Row) -> Complaint:
    return Complaint(
        complaint_id=r["complaint_id"],
        received_on=r["received_on"],
        complainant_name=r["complainant_name"],
        complainant_role=r["complainant_role"],
        contact_email=r["contact_email"],
        contact_phone=r["contact_phone"],
        subject=r["subject"],
        description=r["description"],
        category=r["category"],
        stage=r["stage"],
        severity=r["severity"],
        assigned_to=r["assigned_to"],
        acknowledged_on=r["acknowledged_on"],
        target_response_date=r["target_response_date"],
        response_issued_on=r["response_issued_on"],
        response_summary=r["response_summary"],
        outcome=r["outcome"],
        actions_taken=r["actions_taken"],
        complainant_informed=bool(r["complainant_informed"]),
        complainant_satisfaction=r["complainant_satisfaction"],
        escalated_to_stage_2=bool(r["escalated_to_stage_2"]),
        escalated_to_appeal=bool(r["escalated_to_appeal"]),
        governors_informed=bool(r["governors_informed"]),
        linked_to=r["linked_to"],
        status=r["status"],
        closed_on=r["closed_on"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_complaint(payload: dict[str, Any]) -> Complaint:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO complaints (
              received_on, complainant_name, complainant_role,
              contact_email, contact_phone, subject, description,
              category, stage, severity,
              assigned_to, acknowledged_on, target_response_date,
              response_issued_on, response_summary,
              outcome, actions_taken,
              complainant_informed, complainant_satisfaction,
              escalated_to_stage_2, escalated_to_appeal,
              governors_informed, linked_to, status, closed_on, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["received_on"], p["complainant_name"],
            p["complainant_role"], p["contact_email"],
            p["contact_phone"], p["subject"], p["description"],
            p["category"], p["stage"], p["severity"],
            p["assigned_to"], p["acknowledged_on"],
            p["target_response_date"], p["response_issued_on"],
            p["response_summary"], p["outcome"], p["actions_taken"],
            1 if p["complainant_informed"] else 0,
            p["complainant_satisfaction"],
            1 if p["escalated_to_stage_2"] else 0,
            1 if p["escalated_to_appeal"] else 0,
            1 if p["governors_informed"] else 0,
            p["linked_to"], p["status"], p["closed_on"],
            p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_complaint(new_id)


def update_complaint(complaint_id: int,
                        payload: dict[str, Any]) -> Complaint:
    init_db()
    if get_complaint(complaint_id) is None:
        raise ValidationError(
            f"No complaint with id {complaint_id}")
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE complaints SET
              received_on=?, complainant_name=?, complainant_role=?,
              contact_email=?, contact_phone=?, subject=?, description=?,
              category=?, stage=?, severity=?,
              assigned_to=?, acknowledged_on=?, target_response_date=?,
              response_issued_on=?, response_summary=?,
              outcome=?, actions_taken=?,
              complainant_informed=?, complainant_satisfaction=?,
              escalated_to_stage_2=?, escalated_to_appeal=?,
              governors_informed=?, linked_to=?, status=?,
              closed_on=?, notes=?, updated_on=?
            WHERE complaint_id=?
        """, (
            p["received_on"], p["complainant_name"],
            p["complainant_role"], p["contact_email"],
            p["contact_phone"], p["subject"], p["description"],
            p["category"], p["stage"], p["severity"],
            p["assigned_to"], p["acknowledged_on"],
            p["target_response_date"], p["response_issued_on"],
            p["response_summary"], p["outcome"], p["actions_taken"],
            1 if p["complainant_informed"] else 0,
            p["complainant_satisfaction"],
            1 if p["escalated_to_stage_2"] else 0,
            1 if p["escalated_to_appeal"] else 0,
            1 if p["governors_informed"] else 0,
            p["linked_to"], p["status"], p["closed_on"],
            p["notes"], now, complaint_id,
        ))
    return get_complaint(complaint_id)


def delete_complaint(complaint_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM complaints WHERE complaint_id=?",
            (complaint_id,))
        return cur.rowcount > 0


def get_complaint(complaint_id: int) -> Complaint | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM complaints WHERE complaint_id=?",
            (complaint_id,)).fetchone()
        return _row(r) if r else None


def list_complaints(*,
                        category: str | None = None,
                        stage: str | None = None,
                        status: str | None = None,
                        outcome: str | None = None,
                        complainant_role: str | None = None,
                        severity: int | None = None,
                        severity_min: int | None = None,
                        assigned_to_like: str | None = None,
                        complainant_like: str | None = None,
                        subject_like: str | None = None,
                        open_only: bool = False,
                        overdue_only: bool = False,
                        stage2_or_higher: bool = False,
                        date_from: str | None = None,
                        date_to: str | None = None,
                        ) -> list[Complaint]:
    init_db()
    sql = "SELECT * FROM complaints WHERE 1=1"
    params: list[Any] = []
    if category:
        sql += " AND category=?"
        params.append(category)
    if stage:
        sql += " AND stage=?"
        params.append(stage)
    if status:
        sql += " AND status=?"
        params.append(status)
    if outcome:
        sql += " AND outcome=?"
        params.append(outcome)
    if complainant_role:
        sql += " AND complainant_role=?"
        params.append(complainant_role)
    if severity is not None:
        sql += " AND severity=?"
        params.append(severity)
    if severity_min is not None:
        sql += " AND severity >= ?"
        params.append(severity_min)
    if assigned_to_like:
        sql += " AND assigned_to LIKE ?"
        params.append(f"%{assigned_to_like}%")
    if complainant_like:
        sql += " AND complainant_name LIKE ?"
        params.append(f"%{complainant_like}%")
    if subject_like:
        sql += " AND subject LIKE ?"
        params.append(f"%{subject_like}%")
    if open_only:
        sql += " AND status != 'Closed'"
    if overdue_only:
        today = _dt.date.today().isoformat()
        sql += (" AND target_response_date IS NOT NULL"
                  " AND target_response_date < ?"
                  " AND response_issued_on IS NULL"
                  " AND status != 'Closed'")
        params.append(today)
    if stage2_or_higher:
        sql += " AND stage IN ('Formal Stage 2','Appeal / Governors')"
    if date_from:
        _check_date("From", date_from)
        sql += " AND received_on >= ?"
        params.append(date_from)
    if date_to:
        _check_date("To", date_to)
        sql += " AND received_on <= ?"
        params.append(date_to)
    sql += " ORDER BY received_on DESC, complaint_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


# ── Workflow ─────────────────────────────────────────────────────

def _to_dict(c: Complaint) -> dict[str, Any]:
    return {
        "received_on": c.received_on,
        "complainant_name": c.complainant_name,
        "complainant_role": c.complainant_role,
        "contact_email": c.contact_email,
        "contact_phone": c.contact_phone,
        "subject": c.subject,
        "description": c.description,
        "category": c.category,
        "stage": c.stage,
        "severity": c.severity,
        "assigned_to": c.assigned_to,
        "acknowledged_on": c.acknowledged_on,
        "target_response_date": c.target_response_date,
        "response_issued_on": c.response_issued_on,
        "response_summary": c.response_summary,
        "outcome": c.outcome,
        "actions_taken": c.actions_taken,
        "complainant_informed": c.complainant_informed,
        "complainant_satisfaction": c.complainant_satisfaction,
        "escalated_to_stage_2": c.escalated_to_stage_2,
        "escalated_to_appeal": c.escalated_to_appeal,
        "governors_informed": c.governors_informed,
        "linked_to": c.linked_to,
        "status": c.status,
        "closed_on": c.closed_on,
        "notes": c.notes,
    }


def acknowledge(complaint_id: int, *,
                    assigned_to: str | None = None,
                    acknowledged_on: str | None = None,
                    target_response_date: str | None = None
                    ) -> Complaint:
    c = get_complaint(complaint_id)
    if c is None:
        raise ValidationError(
            f"No complaint with id {complaint_id}")
    data = _to_dict(c)
    data["acknowledged_on"] = (acknowledged_on
                                    or _dt.date.today().isoformat())
    if assigned_to:
        data["assigned_to"] = assigned_to
    if target_response_date:
        data["target_response_date"] = target_response_date
    if c.status == "Received":
        data["status"] = "Acknowledged"
    return update_complaint(complaint_id, data)


def start_investigation(complaint_id: int) -> Complaint:
    c = get_complaint(complaint_id)
    if c is None:
        raise ValidationError(
            f"No complaint with id {complaint_id}")
    data = _to_dict(c)
    data["status"] = "Under Investigation"
    return update_complaint(complaint_id, data)


def issue_response(complaint_id: int, *,
                       summary: str,
                       outcome: str,
                       issued_on: str | None = None,
                       actions_taken: str | None = None
                       ) -> Complaint:
    if not summary:
        raise ValidationError("Response summary is required")
    if outcome not in OUTCOMES:
        raise ValidationError(
            f"Outcome must be one of: {', '.join(OUTCOMES)}")
    c = get_complaint(complaint_id)
    if c is None:
        raise ValidationError(
            f"No complaint with id {complaint_id}")
    data = _to_dict(c)
    data["response_summary"] = summary
    data["outcome"] = outcome
    data["response_issued_on"] = (issued_on
                                       or _dt.date.today().isoformat())
    if actions_taken:
        data["actions_taken"] = actions_taken
    data["status"] = "Response Issued"
    data["complainant_informed"] = True
    return update_complaint(complaint_id, data)


def escalate(complaint_id: int, *,
                 to_stage: str,
                 reason: str | None = None) -> Complaint:
    if to_stage not in STAGES:
        raise ValidationError(
            f"Stage must be one of: {', '.join(STAGES)}")
    c = get_complaint(complaint_id)
    if c is None:
        raise ValidationError(
            f"No complaint with id {complaint_id}")
    if STAGES.index(to_stage) <= STAGES.index(c.stage):
        raise ValidationError(
            f"Cannot escalate from {c.stage} to {to_stage}")
    data = _to_dict(c)
    data["stage"] = to_stage
    data["status"] = "Escalated"
    if to_stage == "Formal Stage 2":
        data["escalated_to_stage_2"] = True
    elif to_stage == "Appeal / Governors":
        data["escalated_to_appeal"] = True
        data["governors_informed"] = True
    if reason:
        existing = data["notes"] or ""
        prefix = (existing + "\n") if existing else ""
        data["notes"] = (
            prefix
            + f"{_dt.date.today().isoformat()} escalated to "
            f"{to_stage}: {reason}")
    # Re-open response cycle for new stage
    data["response_issued_on"] = None
    data["response_summary"] = None
    data["outcome"] = None
    return update_complaint(complaint_id, data)


def record_satisfaction(complaint_id: int, *,
                            satisfaction: str) -> Complaint:
    if satisfaction not in SATISFACTIONS:
        raise ValidationError(
            f"Satisfaction must be one of: "
            f"{', '.join(SATISFACTIONS)}")
    c = get_complaint(complaint_id)
    if c is None:
        raise ValidationError(
            f"No complaint with id {complaint_id}")
    return update_complaint(complaint_id, {
        **_to_dict(c),
        "complainant_satisfaction": satisfaction,
    })


def close_complaint(complaint_id: int) -> Complaint:
    c = get_complaint(complaint_id)
    if c is None:
        raise ValidationError(
            f"No complaint with id {complaint_id}")
    data = _to_dict(c)
    data["status"] = "Closed"
    data["closed_on"] = (data["closed_on"]
                              or _dt.date.today().isoformat())
    return update_complaint(complaint_id, data)


def set_status(complaint_id: int, new_status: str) -> Complaint:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    c = get_complaint(complaint_id)
    if c is None:
        raise ValidationError(
            f"No complaint with id {complaint_id}")
    return update_complaint(complaint_id,
                                {**_to_dict(c), "status": new_status})


# ── Summary ───────────────────────────────────────────────────────

def summary() -> ComplaintsSummary:
    rows = list_complaints()
    out = ComplaintsSummary(total=len(rows))
    if not rows:
        return out
    closed_days: list[int] = []
    today = _dt.date.today().isoformat()
    for c in rows:
        if c.is_open:
            out.open_count += 1
            if c.response_overdue:
                out.overdue += 1
        else:
            out.closed_count += 1
            d = c.days_open
            if d is not None:
                closed_days.append(d)
        if c.severity >= 4:
            out.serious_or_major += 1
        if c.stage in ("Formal Stage 2", "Appeal / Governors"):
            out.at_stage_2_or_appeal += 1
        if c.governors_informed:
            out.governors_informed += 1
        if c.outcome == "Upheld":
            out.upheld_count += 1
        if c.outcome == "Not Upheld":
            out.not_upheld_count += 1
        out.by_category[c.category] = (
            out.by_category.get(c.category, 0) + 1)
        out.by_stage[c.stage] = (
            out.by_stage.get(c.stage, 0) + 1)
        out.by_status[c.status] = (
            out.by_status.get(c.status, 0) + 1)
        if c.outcome:
            out.by_outcome[c.outcome] = (
                out.by_outcome.get(c.outcome, 0) + 1)
    if closed_days:
        out.average_days_to_close = round(
            sum(closed_days) / len(closed_days), 1)
    return out


__all__ = [
    "CATEGORIES", "DEFAULT_CATEGORY",
    "COMPLAINANT_ROLES", "DEFAULT_COMPLAINANT_ROLE",
    "STAGES", "DEFAULT_STAGE",
    "SEVERITIES", "severity_label",
    "STATUSES", "DEFAULT_STATUS",
    "OUTCOMES",
    "SATISFACTIONS", "DEFAULT_SATISFACTION",
    "ValidationError",
    "Complaint", "ComplaintsSummary",
    "init_db",
    "create_complaint", "update_complaint", "delete_complaint",
    "get_complaint", "list_complaints",
    "acknowledge", "start_investigation", "issue_response",
    "escalate", "record_satisfaction",
    "close_complaint", "set_status",
    "summary",
]
