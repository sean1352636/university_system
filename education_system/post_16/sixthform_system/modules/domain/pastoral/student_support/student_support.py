"""Student Support data layer for Sixth Form System.

Tracks light-touch academic / pastoral support referrals: catch-up
sessions, study skills, exam prep, organisation support, welfare /
finance referrals etc. Distinct from wellbeing/safeguarding (which
have heavier confidentiality + DSL workflows). FK cascade on
students.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.post_16.sixthform_system.core import paths as _paths

logger = logging.getLogger(__name__)

SUPPORT_TYPES: tuple[str, ...] = (
    "Academic Catch-Up",
    "Exam Prep Tuition",
    "Study Skills",
    "Organisation Support",
    "Time Management",
    "Subject-Specific Help",
    "Pastoral Check-In",
    "Welfare / Finance",
    "Careers Drop-In",
    "Wellbeing Referral",
    "Transition Support",
    "Other",
)
DEFAULT_SUPPORT_TYPE = "Academic Catch-Up"

SOURCES: tuple[str, ...] = (
    "Self-referral",
    "Subject Teacher",
    "Tutor",
    "Head of Year",
    "Parent / Guardian",
    "SENCo",
    "Pastoral Lead",
    "Safeguarding Lead",
    "Other",
)
DEFAULT_SOURCE = "Subject Teacher"

PRIORITIES: tuple[int, ...] = (1, 2, 3, 4, 5)
_PRIORITY_LABELS = {
    1: "Low", 2: "Routine", 3: "Standard",
    4: "High", 5: "Urgent",
}


def priority_label(p: int | None) -> str:
    if p is None:
        return "—"
    return _PRIORITY_LABELS.get(p, "Unknown")


STATUSES: tuple[str, ...] = (
    "Referred",
    "Triaged",
    "In Progress",
    "On Hold",
    "Resolved",
    "Closed",
)
DEFAULT_STATUS = "Referred"


class ValidationError(Exception):
    pass


@dataclass
class Referral:
    referral_id: int
    student_id: str
    referred_on: str
    support_type: str
    source: str
    referrer: str
    priority: int
    subject_context: str | None
    presenting_issue: str | None
    agreed_actions: str | None
    assigned_to: str | None
    target_close_date: str | None
    sessions_planned: int | None
    sessions_completed: int
    outcome: str | None
    closed_on: str | None
    review_notes: str | None
    status: str
    created_on: str
    updated_on: str

    @property
    def is_open(self) -> bool:
        return self.status not in ("Resolved", "Closed")

    @property
    def priority_label(self) -> str:
        return priority_label(self.priority)

    @property
    def overdue(self) -> bool:
        if not self.is_open or not self.target_close_date:
            return False
        return self.target_close_date < _dt.date.today().isoformat()


@dataclass
class ReferralSummary:
    total: int = 0
    open_count: int = 0
    overdue: int = 0
    urgent_open: int = 0
    distinct_students: int = 0
    total_sessions: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    by_source: dict[str, int] = field(default_factory=dict)
    by_priority: dict[int, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.STUDENT_SUPPORT_DB)
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
            CREATE TABLE IF NOT EXISTS student_support_referrals (
                referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                referred_on TEXT NOT NULL,
                support_type TEXT NOT NULL,
                source TEXT NOT NULL,
                referrer TEXT NOT NULL,
                priority INTEGER NOT NULL,
                subject_context TEXT,
                presenting_issue TEXT,
                agreed_actions TEXT,
                assigned_to TEXT,
                target_close_date TEXT,
                sessions_planned INTEGER,
                sessions_completed INTEGER NOT NULL DEFAULT 0,
                outcome TEXT,
                closed_on TEXT,
                review_notes TEXT,
                status TEXT NOT NULL,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(student_id)
                  ON DELETE CASCADE
            )
        """)


def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _student_exists(student_id: str) -> bool:
    with _connect() as conn:
        try:
            row = conn.execute(
                "SELECT 1 FROM students WHERE student_id=?",
                (student_id,)).fetchone()
        except sqlite3.OperationalError:
            return False
    return row is not None


def _validate_payload(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["student_id"] = (out.get("student_id") or "").strip()
    if not out["student_id"]:
        raise ValidationError("Student is required")
    if not _student_exists(out["student_id"]):
        raise ValidationError(
            f"No student with id {out['student_id']}")

    out["referred_on"] = (out.get("referred_on") or "").strip()
    if not out["referred_on"]:
        out["referred_on"] = _dt.date.today().isoformat()
    _check_date("Referred on", out["referred_on"])
    _check_date("Target close", out.get("target_close_date"))
    _check_date("Closed on",    out.get("closed_on"))

    st = (out.get("support_type") or "").strip()
    if st not in SUPPORT_TYPES:
        raise ValidationError(
            f"Support type must be one of: "
            f"{', '.join(SUPPORT_TYPES)}")
    out["support_type"] = st

    src = (out.get("source") or "").strip()
    if src not in SOURCES:
        raise ValidationError(
            f"Source must be one of: {', '.join(SOURCES)}")
    out["source"] = src

    out["referrer"] = (out.get("referrer") or "").strip()
    if not out["referrer"]:
        raise ValidationError("Referrer is required")

    try:
        pri = int(out.get("priority") or 3)
    except (TypeError, ValueError):
        raise ValidationError("Priority must be 1-5")
    if pri not in PRIORITIES:
        raise ValidationError("Priority must be 1-5")
    out["priority"] = pri

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    for k in ("subject_context", "presenting_issue",
               "agreed_actions", "assigned_to", "outcome",
               "review_notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("target_close_date", "closed_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v

    for key, label in (("sessions_planned", "Sessions planned"),
                          ("sessions_completed",
                           "Sessions completed")):
        v = out.get(key)
        if v in (None, ""):
            out[key] = None if key == "sessions_planned" else 0
        else:
            try:
                iv = int(v)
            except (TypeError, ValueError):
                raise ValidationError(f"{label} must be an integer")
            if iv < 0:
                raise ValidationError(f"{label} must be >= 0")
            out[key] = iv
    if out["sessions_completed"] is None:
        out["sessions_completed"] = 0
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def _row(r: sqlite3.Row) -> Referral:
    return Referral(
        referral_id=r["referral_id"],
        student_id=r["student_id"],
        referred_on=r["referred_on"],
        support_type=r["support_type"],
        source=r["source"],
        referrer=r["referrer"],
        priority=r["priority"],
        subject_context=r["subject_context"],
        presenting_issue=r["presenting_issue"],
        agreed_actions=r["agreed_actions"],
        assigned_to=r["assigned_to"],
        target_close_date=r["target_close_date"],
        sessions_planned=r["sessions_planned"],
        sessions_completed=r["sessions_completed"],
        outcome=r["outcome"],
        closed_on=r["closed_on"],
        review_notes=r["review_notes"],
        status=r["status"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_referral(payload: dict[str, Any]) -> Referral:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO student_support_referrals (
              student_id, referred_on, support_type, source,
              referrer, priority, subject_context, presenting_issue,
              agreed_actions, assigned_to, target_close_date,
              sessions_planned, sessions_completed,
              outcome, closed_on, review_notes, status,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?)
        """, (
            p["student_id"], p["referred_on"], p["support_type"],
            p["source"], p["referrer"], p["priority"],
            p["subject_context"], p["presenting_issue"],
            p["agreed_actions"], p["assigned_to"],
            p["target_close_date"], p["sessions_planned"],
            p["sessions_completed"], p["outcome"], p["closed_on"],
            p["review_notes"], p["status"], now, now,
        ))
        new_id = cur.lastrowid
    return get_referral(new_id)


def update_referral(referral_id: int,
                       payload: dict[str, Any]) -> Referral:
    init_db()
    if get_referral(referral_id) is None:
        raise ValidationError(
            f"No referral with id {referral_id}")
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE student_support_referrals SET
              student_id=?, referred_on=?, support_type=?, source=?,
              referrer=?, priority=?, subject_context=?,
              presenting_issue=?, agreed_actions=?, assigned_to=?,
              target_close_date=?, sessions_planned=?,
              sessions_completed=?, outcome=?, closed_on=?,
              review_notes=?, status=?, updated_on=?
            WHERE referral_id=?
        """, (
            p["student_id"], p["referred_on"], p["support_type"],
            p["source"], p["referrer"], p["priority"],
            p["subject_context"], p["presenting_issue"],
            p["agreed_actions"], p["assigned_to"],
            p["target_close_date"], p["sessions_planned"],
            p["sessions_completed"], p["outcome"], p["closed_on"],
            p["review_notes"], p["status"], now, referral_id,
        ))
    return get_referral(referral_id)


def delete_referral(referral_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM student_support_referrals "
            "WHERE referral_id=?", (referral_id,))
        return cur.rowcount > 0


def get_referral(referral_id: int) -> Referral | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM student_support_referrals "
            "WHERE referral_id=?", (referral_id,)).fetchone()
        return _row(r) if r else None


def list_referrals(*,
                       student_id: str | None = None,
                       support_type: str | None = None,
                       source: str | None = None,
                       status: str | None = None,
                       priority: int | None = None,
                       priority_min: int | None = None,
                       open_only: bool = False,
                       overdue_only: bool = False,
                       urgent_only: bool = False,
                       assigned_to_like: str | None = None,
                       referrer_like: str | None = None,
                       date_from: str | None = None,
                       date_to: str | None = None,
                       ) -> list[Referral]:
    init_db()
    sql = "SELECT * FROM student_support_referrals WHERE 1=1"
    params: list[Any] = []
    if student_id:
        sql += " AND student_id=?"
        params.append(student_id)
    if support_type:
        sql += " AND support_type=?"
        params.append(support_type)
    if source:
        sql += " AND source=?"
        params.append(source)
    if status:
        sql += " AND status=?"
        params.append(status)
    if priority is not None:
        sql += " AND priority=?"
        params.append(priority)
    if priority_min is not None:
        sql += " AND priority >= ?"
        params.append(priority_min)
    if open_only:
        sql += " AND status NOT IN ('Resolved','Closed')"
    if overdue_only:
        today = _dt.date.today().isoformat()
        sql += (" AND target_close_date IS NOT NULL"
                  " AND target_close_date < ?"
                  " AND status NOT IN ('Resolved','Closed')")
        params.append(today)
    if urgent_only:
        sql += (" AND priority >= 4"
                  " AND status NOT IN ('Resolved','Closed')")
    if assigned_to_like:
        sql += " AND assigned_to LIKE ?"
        params.append(f"%{assigned_to_like}%")
    if referrer_like:
        sql += " AND referrer LIKE ?"
        params.append(f"%{referrer_like}%")
    if date_from:
        _check_date("From", date_from)
        sql += " AND referred_on >= ?"
        params.append(date_from)
    if date_to:
        _check_date("To", date_to)
        sql += " AND referred_on <= ?"
        params.append(date_to)
    sql += (" ORDER BY priority DESC, referred_on DESC,"
              " referral_id DESC")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


def referrals_for_student(student_id: str) -> list[Referral]:
    return list_referrals(student_id=student_id)


# ── Workflow ─────────────────────────────────────────────────────

def _to_dict(r: Referral) -> dict[str, Any]:
    return {
        "student_id": r.student_id,
        "referred_on": r.referred_on,
        "support_type": r.support_type,
        "source": r.source,
        "referrer": r.referrer,
        "priority": r.priority,
        "subject_context": r.subject_context,
        "presenting_issue": r.presenting_issue,
        "agreed_actions": r.agreed_actions,
        "assigned_to": r.assigned_to,
        "target_close_date": r.target_close_date,
        "sessions_planned": r.sessions_planned,
        "sessions_completed": r.sessions_completed,
        "outcome": r.outcome,
        "closed_on": r.closed_on,
        "review_notes": r.review_notes,
        "status": r.status,
    }


def triage(referral_id: int, *, assigned_to: str,
              priority: int | None = None,
              target_close_date: str | None = None
              ) -> Referral:
    r = get_referral(referral_id)
    if r is None:
        raise ValidationError(f"No referral with id {referral_id}")
    if not assigned_to:
        raise ValidationError("Assigned-to is required for triage")
    data = _to_dict(r)
    data["assigned_to"] = assigned_to
    if priority is not None:
        data["priority"] = priority
    if target_close_date is not None:
        data["target_close_date"] = target_close_date
    if r.status == "Referred":
        data["status"] = "Triaged"
    return update_referral(referral_id, data)


def start_progress(referral_id: int) -> Referral:
    r = get_referral(referral_id)
    if r is None:
        raise ValidationError(f"No referral with id {referral_id}")
    data = _to_dict(r)
    data["status"] = "In Progress"
    return update_referral(referral_id, data)


def log_session(referral_id: int, *,
                    note: str | None = None) -> Referral:
    r = get_referral(referral_id)
    if r is None:
        raise ValidationError(f"No referral with id {referral_id}")
    data = _to_dict(r)
    data["sessions_completed"] = r.sessions_completed + 1
    if note:
        existing = data["review_notes"] or ""
        prefix = (existing + "\n") if existing else ""
        data["review_notes"] = (
            prefix + f"{_dt.date.today().isoformat()}: {note}")
    if r.status in ("Referred", "Triaged"):
        data["status"] = "In Progress"
    return update_referral(referral_id, data)


def resolve(referral_id: int, *, outcome: str) -> Referral:
    if not outcome:
        raise ValidationError("Outcome is required")
    r = get_referral(referral_id)
    if r is None:
        raise ValidationError(f"No referral with id {referral_id}")
    data = _to_dict(r)
    data["outcome"] = outcome
    data["status"] = "Resolved"
    data["closed_on"] = _dt.date.today().isoformat()
    return update_referral(referral_id, data)


def close_referral(referral_id: int) -> Referral:
    r = get_referral(referral_id)
    if r is None:
        raise ValidationError(f"No referral with id {referral_id}")
    data = _to_dict(r)
    data["status"] = "Closed"
    if not data["closed_on"]:
        data["closed_on"] = _dt.date.today().isoformat()
    return update_referral(referral_id, data)


def set_status(referral_id: int, new_status: str) -> Referral:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    r = get_referral(referral_id)
    if r is None:
        raise ValidationError(f"No referral with id {referral_id}")
    return update_referral(referral_id,
                                {**_to_dict(r), "status": new_status})


# ── Summary ───────────────────────────────────────────────────────

def summary() -> ReferralSummary:
    rows = list_referrals()
    out = ReferralSummary(total=len(rows))
    if not rows:
        return out
    students: set[str] = set()
    today = _dt.date.today().isoformat()
    for r in rows:
        students.add(r.student_id)
        out.total_sessions += r.sessions_completed
        if r.is_open:
            out.open_count += 1
            if (r.target_close_date
                    and r.target_close_date < today):
                out.overdue += 1
            if r.priority >= 4:
                out.urgent_open += 1
        out.by_type[r.support_type] = (
            out.by_type.get(r.support_type, 0) + 1)
        out.by_source[r.source] = (
            out.by_source.get(r.source, 0) + 1)
        out.by_priority[r.priority] = (
            out.by_priority.get(r.priority, 0) + 1)
        out.by_status[r.status] = (
            out.by_status.get(r.status, 0) + 1)
    out.distinct_students = len(students)
    return out


__all__ = [
    "SUPPORT_TYPES", "DEFAULT_SUPPORT_TYPE",
    "SOURCES", "DEFAULT_SOURCE",
    "PRIORITIES", "priority_label",
    "STATUSES", "DEFAULT_STATUS",
    "ValidationError",
    "Referral", "ReferralSummary",
    "init_db",
    "create_referral", "update_referral", "delete_referral",
    "get_referral", "list_referrals", "referrals_for_student",
    "triage", "start_progress", "log_session",
    "resolve", "close_referral", "set_status",
    "summary",
]
