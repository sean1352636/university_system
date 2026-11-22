"""Student Support data layer for Sixth Form System.

Tracks light-touch academic / pastoral support referrals: catch-up
sessions, study skills, exam prep, organisation support, welfare /
finance referrals etc. Distinct from wellbeing/safeguarding (which
have heavier confidentiality + DSL workflows). FK cascade on
students.

Also holds **external mental-health referrals** (``mh_referrals``):
CAMHS, NHS Talking Therapies, GP, college counsellor, Kooth, the
Mental Health Support Team and so on — date, service, reason, status,
time waiting, outcome and follow-up. Those functions require the
PASTORAL capability, respect tutor scoping (can_see_student) and are
written to the sensitive-access log.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system import paths as _paths
from education_system.systems.sixth_form.domain.pastoral import _records

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
    _paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(_paths.SIXTH_FORM_STUDENT_SUPPORT_DB)
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
        conn.executescript(_MH_SCHEMA)


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


# ── Learner self-referral (student portal) ───────────────────────

#: What a learner can ask for themselves. Staff-only routes (SENCo,
#: safeguarding) are not offered; a worry about safety goes through
#: safeguarding's "Report a concern" instead.
SELF_REFERRAL_TYPES: tuple[str, ...] = (
    "Wellbeing Referral",
    "Academic Catch-Up",
    "Study Skills",
    "Organisation Support",
    "Time Management",
    "Subject-Specific Help",
    "Exam Prep Tuition",
    "Pastoral Check-In",
    "Welfare / Finance",
    "Careers Drop-In",
    "Transition Support",
    "Other",
)

SELF_SOURCE = "Self-referral"


def self_refer(student_id: str, *, support_type: str, issue: str,
               referrer: str, subject_context: str | None = None,
               urgent: bool = False) -> Referral:
    """A learner asks for support for themselves.

    Filed as ``source='Self-referral'`` with status Referred, so it lands
    in the support team's triage queue like any other referral.
    """
    if support_type not in SELF_REFERRAL_TYPES:
        raise ValidationError(
            f"Choose one of: {', '.join(SELF_REFERRAL_TYPES)}")
    issue = (issue or "").strip()
    if not issue:
        raise ValidationError("Tell us a little about what you need help with")
    if len(issue) > 2000:
        raise ValidationError("Please keep it under 2000 characters")
    return create_referral({
        "student_id": student_id, "support_type": support_type,
        "source": SELF_SOURCE, "referrer": referrer or student_id,
        "priority": 4 if urgent else 3, "presenting_issue": issue,
        "subject_context": subject_context, "status": DEFAULT_STATUS,
    })


def self_referrals_for(student_id: str) -> list[Referral]:
    """Only the referrals the learner made themselves.

    Referrals staff raised about a learner are not shown back to them.
    """
    sid = (student_id or "").strip()
    if not sid:
        return []
    return list_referrals(student_id=sid, source=SELF_SOURCE)


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
    # Mental-health referrals
    "MH_SERVICES", "MH_URGENCIES", "MH_STATUSES", "MH_OPEN_STATUSES",
    "MHReferral", "MH_SPEC",
    "create_mh_referral", "get_mh_referral", "list_mh_referrals",
    "update_mh_referral", "delete_mh_referral", "set_mh_status",
    "record_mh_outcome", "mh_waiting_list", "mh_follow_ups_due",
]


# ══ External mental-health referrals ══════════════════════════════

MH_SERVICES: tuple[str, ...] = (
    "CAMHS",
    "Adult Mental Health Services",
    "NHS Talking Therapies",
    "GP",
    "College Counsellor",
    "Mental Health Support Team (MHST)",
    "Kooth",
    "School / College Nurse",
    "Eating Disorder Service",
    "Early Intervention in Psychosis",
    "Crisis Team",
    "Bereavement Service",
    "Substance Misuse Service",
    "Charity / Voluntary Service",
    "Other",
)
MH_URGENCIES: tuple[str, ...] = ("Routine", "Urgent", "Emergency")
MH_STATUSES: tuple[str, ...] = (
    "Considering",
    "Referred",
    "Accepted",
    "Waiting",
    "In Treatment",
    "Declined by Service",
    "Declined by Student",
    "Discharged",
    "Closed",
)
#: Statuses in which the student is still waiting to be seen.
MH_WAITING_STATUSES: tuple[str, ...] = ("Referred", "Accepted", "Waiting")
MH_OPEN_STATUSES: tuple[str, ...] = (
    "Considering", "Referred", "Accepted", "Waiting", "In Treatment",
)

_MH_SCHEMA = """
CREATE TABLE IF NOT EXISTS mh_referrals (
    referral_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id         TEXT NOT NULL,
    referred_on        TEXT NOT NULL,
    service            TEXT NOT NULL,
    service_detail     TEXT,
    referred_by        TEXT,
    reason             TEXT NOT NULL,
    urgency            TEXT NOT NULL DEFAULT 'Routine',
    student_consent    INTEGER NOT NULL DEFAULT 0,
    parent_informed    INTEGER NOT NULL DEFAULT 0,
    status             TEXT NOT NULL DEFAULT 'Referred',
    service_reference  TEXT,
    accepted_on        TEXT,
    first_appointment  TEXT,
    outcome            TEXT,
    follow_up_date     TEXT,
    follow_up_by       TEXT,
    closed_on          TEXT,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_mhr_student ON mh_referrals(student_id);
CREATE INDEX IF NOT EXISTS idx_mhr_status  ON mh_referrals(status);
"""


@dataclass
class MHReferral:
    referral_id: int
    student_id: str
    referred_on: str
    service: str
    service_detail: str | None
    referred_by: str | None
    reason: str
    urgency: str
    student_consent: bool
    parent_informed: bool
    status: str
    service_reference: str | None
    accepted_on: str | None
    first_appointment: str | None
    outcome: str | None
    follow_up_date: str | None
    follow_up_by: str | None
    closed_on: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def is_open(self) -> bool:
        return self.status in MH_OPEN_STATUSES

    @property
    def days_waiting(self) -> int | None:
        """Days from referral to first appointment (or to today while
        still waiting). None once seen with no appointment date."""
        start = _dt.date.fromisoformat(self.referred_on)
        if self.first_appointment:
            end = _dt.date.fromisoformat(self.first_appointment)
        elif self.status in MH_WAITING_STATUSES:
            end = _dt.date.today()
        else:
            return None
        return max(0, (end - start).days)

    @property
    def follow_up_overdue(self) -> bool:
        return bool(self.follow_up_date
                    and self.follow_up_date < _dt.date.today().isoformat()
                    and self.status not in ("Closed",))


_C = _records.Col

MH_SPEC = _records.TableSpec(
    table="mh_referrals", id_col="referral_id", row_type=MHReferral,
    label="Mental-health referral",
    order_by="referred_on DESC, referral_id DESC",
    cols=(
        _C("student_id", "Student", "student", required=True, fixed=True),
        _C("referred_on", "Referred on", "date", required=True,
           default=_records.today),
        _C("service", "Service", "choice", required=True,
           choices=MH_SERVICES),
        _C("service_detail", "Service detail / team", listed=False),
        _C("referred_by", "Referred by"),
        _C("reason", "Reason", "multiline", required=True),
        _C("urgency", "Urgency", "choice", choices=MH_URGENCIES,
           default="Routine"),
        _C("student_consent", "Student consented", "bool", listed=False),
        _C("parent_informed", "Parent informed", "bool", listed=False),
        _C("status", "Status", "choice", choices=MH_STATUSES,
           default="Referred"),
        _C("service_reference", "Service reference", listed=False),
        _C("accepted_on", "Accepted on", "date", listed=False),
        _C("first_appointment", "First appointment", "date"),
        _C("outcome", "Outcome", "multiline"),
        _C("follow_up_date", "Follow-up date", "date"),
        _C("follow_up_by", "Follow-up by", listed=False),
        _C("closed_on", "Closed on", "date", listed=False),
        _C("notes", "Notes", "multiline", listed=False),
    ))


def _mh_guard(action: str, student_id: str | None = None,
              ref: str | None = None) -> Any:
    return _records.guard("PASTORAL", "mental_health", action,
                          student_id=student_id, record_ref=ref)


def _mh_rules(p: dict[str, Any]) -> None:
    for k, label in (("accepted_on", "Accepted on"),
                     ("first_appointment", "First appointment"),
                     ("closed_on", "Closed on")):
        if p.get(k) and p[k] < p["referred_on"]:
            raise ValidationError(f"{label} cannot be before the referral")
    if p["status"] in ("Discharged", "Closed", "Declined by Service",
                       "Declined by Student") and not p.get("closed_on"):
        p["closed_on"] = _dt.date.today().isoformat()
    if p["status"] in MH_OPEN_STATUSES:
        p["closed_on"] = None


def create_mh_referral(data: dict[str, Any]) -> MHReferral:
    init_db()
    p = _records.validate(MH_SPEC, data, error=ValidationError,
                          student_exists=_student_exists)
    _mh_rules(p)
    actor = _mh_guard("create mental-health referral", p["student_id"])
    p["referred_by"] = (p["referred_by"] or actor.staff_name
                        or actor.username or None)
    with _connect() as conn:
        new_id = _records.insert(conn, MH_SPEC, p)
    logger.info("Created %s mental-health referral #%d (%s) for %s",
                p["urgency"].lower(), new_id, p["service"], p["student_id"])
    return get_mh_referral(new_id)


def get_mh_referral(referral_id: int) -> MHReferral | None:
    init_db()
    with _connect() as conn:
        r = _records.fetch(conn, MH_SPEC, referral_id)
    if r is not None:
        _mh_guard("view mental-health referral", r.student_id,
                  f"mh:{referral_id}")
    return r


def list_mh_referrals(*, student_id: str | None = None,
                      service: str | None = None,
                      status: str | None = None,
                      open_only: bool = False) -> list[MHReferral]:
    init_db()
    _mh_guard("list mental-health referrals", student_id)
    where, args = [], []
    if open_only:
        where.append("status IN (%s)" % ",".join("?" * len(MH_OPEN_STATUSES)))
        args.extend(MH_OPEN_STATUSES)
    with _connect() as conn:
        rows = _records.select(conn, MH_SPEC, equals={
            "student_id": student_id, "service": service, "status": status},
            where=where, args=args)
    return _records.visible_filter("PASTORAL", rows)


def update_mh_referral(referral_id: int,
                       data: dict[str, Any]) -> MHReferral:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, MH_SPEC, referral_id)
    if existing is None:
        raise ValidationError(f"No mental-health referral #{referral_id}")
    p = _records.validate(MH_SPEC, data, error=ValidationError,
                          existing=existing, student_exists=_student_exists)
    _mh_rules(p)
    _mh_guard("update mental-health referral", existing.student_id,
              f"mh:{referral_id}")
    with _connect() as conn:
        _records.update(conn, MH_SPEC, referral_id, p)
    return get_mh_referral(referral_id)


def set_mh_status(referral_id: int, status: str, *,
                  on: str | None = None) -> MHReferral:
    """Move a referral on; 'Accepted' stamps accepted_on, 'In Treatment'
    stamps first_appointment if it is blank."""
    if status not in MH_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(MH_STATUSES)}")
    when = _records.check_date(on, "Date", ValidationError) \
        or _dt.date.today().isoformat()
    existing = get_mh_referral(referral_id)
    if existing is None:
        raise ValidationError(f"No mental-health referral #{referral_id}")
    payload: dict[str, Any] = {"status": status}
    if status == "Accepted" and not existing.accepted_on:
        payload["accepted_on"] = when
    if status == "In Treatment" and not existing.first_appointment:
        payload["first_appointment"] = when
    if status in ("Discharged", "Closed", "Declined by Service",
                  "Declined by Student"):
        payload["closed_on"] = when
    return update_mh_referral(referral_id, payload)


def record_mh_outcome(referral_id: int, *, outcome: str,
                      follow_up_date: str | None = None,
                      follow_up_by: str | None = None,
                      close: bool = False) -> MHReferral:
    if not (outcome or "").strip():
        raise ValidationError("Outcome is required")
    payload: dict[str, Any] = {"outcome": outcome.strip(),
                               "follow_up_date": follow_up_date,
                               "follow_up_by": follow_up_by}
    if close:
        payload["status"] = "Closed"
    return update_mh_referral(referral_id, payload)


def delete_mh_referral(referral_id: int) -> bool:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, MH_SPEC, referral_id)
        if existing is None:
            return False
        _mh_guard("delete mental-health referral", existing.student_id,
                  f"mh:{referral_id}")
        return _records.delete(conn, MH_SPEC, referral_id)


def mh_waiting_list() -> list[MHReferral]:
    """Students referred but not yet seen, longest wait first."""
    rows = [r for r in list_mh_referrals()
            if r.status in MH_WAITING_STATUSES]
    rows.sort(key=lambda r: -(r.days_waiting or 0))
    return rows


def mh_follow_ups_due(*, within_days: int = 7) -> list[MHReferral]:
    horizon = (_dt.date.today()
               + _dt.timedelta(days=within_days)).isoformat()
    rows = [r for r in list_mh_referrals()
            if r.follow_up_date and r.follow_up_date <= horizon
            and r.status != "Closed"]
    rows.sort(key=lambda r: r.follow_up_date or "")
    return rows
