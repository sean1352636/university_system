"""Quality Assurance data layer for Sixth Form System.

QA activities are organisational-level evidence-gathering events
(work scrutiny, learning walk, book look, etc.). Each activity has
a focus, a 1-4 OFSTED-style judgement, strengths, areas to develop,
evidence references and follow-up actions (with owner, due-date and
impact review). No FK to students.
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

ACTIVITY_TYPES: tuple[str, ...] = (
    "Work Scrutiny",
    "Learning Walk",
    "Book Look",
    "Planning Review",
    "Marking Sample",
    "Lesson Drop-In",
    "Curriculum Review",
    "Standardisation",
    "Self-Review",
    "Peer Review",
    "External Review",
    "Other",
)
DEFAULT_ACTIVITY_TYPE = "Learning Walk"

FOCUS_AREAS: tuple[str, ...] = (
    "Teaching & Learning",
    "Marking & Feedback",
    "Curriculum",
    "Assessment",
    "Behaviour & Engagement",
    "Differentiation",
    "Stretch & Challenge",
    "Literacy",
    "Numeracy",
    "Independent Study",
    "Pastoral",
    "SEND Support",
    "Pupil Premium",
    "Other",
)
DEFAULT_FOCUS_AREA = "Teaching & Learning"

STATUSES: tuple[str, ...] = (
    "Planned",
    "In Progress",
    "Findings Recorded",
    "Actions Set",
    "Action In Progress",
    "Closed",
)
DEFAULT_STATUS = "Planned"

JUDGEMENTS: tuple[int, ...] = (1, 2, 3, 4)
_JUDGEMENT_LABELS = {
    1: "Outstanding",
    2: "Good",
    3: "Requires Improvement",
    4: "Inadequate",
}


def judgement_label(j: int | None) -> str:
    if j is None:
        return "—"
    return _JUDGEMENT_LABELS.get(j, "Unknown")


class ValidationError(Exception):
    pass


@dataclass
class QAActivity:
    activity_id: int
    activity_date: str
    activity_type: str
    title: str
    focus_area: str | None
    lead: str
    participants: str
    subject: str | None
    department: str | None
    judgement: int | None
    status: str
    strengths: str | None
    areas_to_develop: str | None
    evidence: str | None
    action_summary: str | None
    action_owner: str | None
    action_due: str | None
    action_completed: bool
    impact_review: str | None
    impact_reviewed_on: str | None
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_open(self) -> bool:
        return self.status != "Closed"

    @property
    def judgement_label(self) -> str:
        return judgement_label(self.judgement)

    @property
    def action_overdue(self) -> bool:
        if not self.action_due or self.action_completed:
            return False
        return self.action_due < _dt.date.today().isoformat()


@dataclass
class QASummary:
    total: int = 0
    open_count: int = 0
    actions_outstanding: int = 0
    actions_overdue: int = 0
    average_judgement: float | None = None
    distinct_leads: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_type: dict[str, int] = field(default_factory=dict)
    by_focus: dict[str, int] = field(default_factory=dict)
    by_judgement: dict[int, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.QUALITY_ASSURANCE_DB)
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
            CREATE TABLE IF NOT EXISTS qa_activities (
                activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_date TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                title TEXT NOT NULL,
                focus_area TEXT,
                lead TEXT NOT NULL,
                participants TEXT NOT NULL DEFAULT '',
                subject TEXT,
                department TEXT,
                judgement INTEGER,
                status TEXT NOT NULL,
                strengths TEXT,
                areas_to_develop TEXT,
                evidence TEXT,
                action_summary TEXT,
                action_owner TEXT,
                action_due TEXT,
                action_completed INTEGER NOT NULL DEFAULT 0,
                impact_review TEXT,
                impact_reviewed_on TEXT,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL
            )
        """)


# ── Validation ─────────────────────────────────────────────────────

def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _validate_payload(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["activity_date"] = (out.get("activity_date") or "").strip()
    if not out["activity_date"]:
        raise ValidationError("Date is required (YYYY-MM-DD)")
    _check_date("Date", out["activity_date"])
    out["activity_type"] = (out.get("activity_type") or "").strip()
    if out["activity_type"] not in ACTIVITY_TYPES:
        raise ValidationError(
            f"Type must be one of: {', '.join(ACTIVITY_TYPES)}")
    out["title"] = (out.get("title") or "").strip()
    if not out["title"]:
        raise ValidationError("Title is required")
    fa = (out.get("focus_area") or "").strip()
    if fa and fa not in FOCUS_AREAS:
        raise ValidationError(
            f"Focus area must be one of: {', '.join(FOCUS_AREAS)}")
    out["focus_area"] = fa or None
    out["lead"] = (out.get("lead") or "").strip()
    if not out["lead"]:
        raise ValidationError("Lead is required")
    out["participants"] = (out.get("participants") or "").strip()
    out["subject"] = (out.get("subject") or "").strip() or None
    out["department"] = (out.get("department") or "").strip() or None

    j = out.get("judgement")
    if j in (None, ""):
        out["judgement"] = None
    else:
        try:
            jv = int(j)
        except (TypeError, ValueError):
            raise ValidationError("Judgement must be 1-4 (1=Outstanding)")
        if jv not in JUDGEMENTS:
            raise ValidationError("Judgement must be 1-4 (1=Outstanding)")
        out["judgement"] = jv

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    for k in ("strengths", "areas_to_develop", "evidence",
               "action_summary", "action_owner",
               "impact_review", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None

    _check_date("Action due",       out.get("action_due"))
    _check_date("Impact reviewed",  out.get("impact_reviewed_on"))
    out["action_due"] = (out.get("action_due") or "").strip() or None
    out["impact_reviewed_on"] = (
        (out.get("impact_reviewed_on") or "").strip() or None)
    out["action_completed"] = bool(out.get("action_completed"))
    return out


# ── CRUD ───────────────────────────────────────────────────────────

def _row_to_activity(r: sqlite3.Row) -> QAActivity:
    return QAActivity(
        activity_id=r["activity_id"],
        activity_date=r["activity_date"],
        activity_type=r["activity_type"],
        title=r["title"],
        focus_area=r["focus_area"],
        lead=r["lead"],
        participants=r["participants"] or "",
        subject=r["subject"],
        department=r["department"],
        judgement=r["judgement"],
        status=r["status"],
        strengths=r["strengths"],
        areas_to_develop=r["areas_to_develop"],
        evidence=r["evidence"],
        action_summary=r["action_summary"],
        action_owner=r["action_owner"],
        action_due=r["action_due"],
        action_completed=bool(r["action_completed"]),
        impact_review=r["impact_review"],
        impact_reviewed_on=r["impact_reviewed_on"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_activity(payload: dict[str, Any]) -> QAActivity:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO qa_activities (
                activity_date, activity_type, title, focus_area,
                lead, participants, subject, department,
                judgement, status,
                strengths, areas_to_develop, evidence,
                action_summary, action_owner, action_due,
                action_completed,
                impact_review, impact_reviewed_on,
                notes, created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["activity_date"], p["activity_type"], p["title"],
            p["focus_area"], p["lead"], p["participants"],
            p["subject"], p["department"],
            p["judgement"], p["status"],
            p["strengths"], p["areas_to_develop"], p["evidence"],
            p["action_summary"], p["action_owner"], p["action_due"],
            1 if p["action_completed"] else 0,
            p["impact_review"], p["impact_reviewed_on"],
            p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_activity(new_id)


def update_activity(activity_id: int,
                      payload: dict[str, Any]) -> QAActivity:
    init_db()
    if get_activity(activity_id) is None:
        raise ValidationError(f"No QA activity with id {activity_id}")
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE qa_activities SET
              activity_date=?, activity_type=?, title=?, focus_area=?,
              lead=?, participants=?, subject=?, department=?,
              judgement=?, status=?,
              strengths=?, areas_to_develop=?, evidence=?,
              action_summary=?, action_owner=?, action_due=?,
              action_completed=?,
              impact_review=?, impact_reviewed_on=?,
              notes=?, updated_on=?
            WHERE activity_id=?
        """, (
            p["activity_date"], p["activity_type"], p["title"],
            p["focus_area"], p["lead"], p["participants"],
            p["subject"], p["department"],
            p["judgement"], p["status"],
            p["strengths"], p["areas_to_develop"], p["evidence"],
            p["action_summary"], p["action_owner"], p["action_due"],
            1 if p["action_completed"] else 0,
            p["impact_review"], p["impact_reviewed_on"],
            p["notes"], now, activity_id,
        ))
    return get_activity(activity_id)


def delete_activity(activity_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM qa_activities WHERE activity_id=?",
            (activity_id,))
        return cur.rowcount > 0


def get_activity(activity_id: int) -> QAActivity | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM qa_activities WHERE activity_id=?",
            (activity_id,)).fetchone()
        return _row_to_activity(r) if r else None


def list_activities(*,
                      activity_type: str | None = None,
                      focus_area: str | None = None,
                      status: str | None = None,
                      lead_like: str | None = None,
                      subject: str | None = None,
                      department: str | None = None,
                      judgement: int | None = None,
                      open_only: bool = False,
                      action_outstanding: bool = False,
                      action_overdue: bool = False,
                      date_from: str | None = None,
                      date_to: str | None = None,
                      ) -> list[QAActivity]:
    init_db()
    sql = "SELECT * FROM qa_activities WHERE 1=1"
    params: list[Any] = []
    if activity_type:
        sql += " AND activity_type=?"
        params.append(activity_type)
    if focus_area:
        sql += " AND focus_area=?"
        params.append(focus_area)
    if status:
        sql += " AND status=?"
        params.append(status)
    if lead_like:
        sql += " AND lead LIKE ?"
        params.append(f"%{lead_like}%")
    if subject:
        sql += " AND subject LIKE ?"
        params.append(f"%{subject}%")
    if department:
        sql += " AND department LIKE ?"
        params.append(f"%{department}%")
    if judgement is not None:
        sql += " AND judgement=?"
        params.append(judgement)
    if open_only:
        sql += " AND status != 'Closed'"
    if action_outstanding:
        sql += (" AND action_summary IS NOT NULL"
                  " AND action_completed=0")
    if action_overdue:
        today = _dt.date.today().isoformat()
        sql += (" AND action_due IS NOT NULL AND action_due < ?"
                  " AND action_completed=0")
        params.append(today)
    if date_from:
        _check_date("From", date_from)
        sql += " AND activity_date >= ?"
        params.append(date_from)
    if date_to:
        _check_date("To", date_to)
        sql += " AND activity_date <= ?"
        params.append(date_to)
    sql += " ORDER BY activity_date DESC, activity_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_activity(r) for r in rows]


# ── Workflow helpers ──────────────────────────────────────────────

def set_status(activity_id: int, status: str) -> QAActivity:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    a = get_activity(activity_id)
    if a is None:
        raise ValidationError(f"No QA activity with id {activity_id}")
    return update_activity(activity_id, {**_to_dict(a), "status": status})


def record_findings(activity_id: int, *, strengths: str = "",
                       areas: str = "", evidence: str = "",
                       judgement: int | None = None) -> QAActivity:
    a = get_activity(activity_id)
    if a is None:
        raise ValidationError(f"No QA activity with id {activity_id}")
    data = _to_dict(a)
    data["strengths"] = strengths or data["strengths"]
    data["areas_to_develop"] = areas or data["areas_to_develop"]
    data["evidence"] = evidence or data["evidence"]
    if judgement is not None:
        data["judgement"] = judgement
    if data["status"] in ("Planned", "In Progress"):
        data["status"] = "Findings Recorded"
    return update_activity(activity_id, data)


def set_action(activity_id: int, *, summary: str, owner: str,
                  due: str | None = None) -> QAActivity:
    a = get_activity(activity_id)
    if a is None:
        raise ValidationError(f"No QA activity with id {activity_id}")
    data = _to_dict(a)
    data["action_summary"] = summary
    data["action_owner"] = owner
    data["action_due"] = due
    data["action_completed"] = False
    if data["status"] in ("Planned", "In Progress",
                              "Findings Recorded"):
        data["status"] = "Actions Set"
    return update_activity(activity_id, data)


def complete_action(activity_id: int, *, impact: str = "",
                       reviewed_on: str | None = None) -> QAActivity:
    a = get_activity(activity_id)
    if a is None:
        raise ValidationError(f"No QA activity with id {activity_id}")
    data = _to_dict(a)
    data["action_completed"] = True
    if impact:
        data["impact_review"] = impact
    data["impact_reviewed_on"] = (reviewed_on
                                       or _dt.date.today().isoformat())
    if data["status"] != "Closed":
        data["status"] = "Closed"
    return update_activity(activity_id, data)


def close_activity(activity_id: int) -> QAActivity:
    return set_status(activity_id, "Closed")


def _to_dict(a: QAActivity) -> dict[str, Any]:
    return {
        "activity_date": a.activity_date,
        "activity_type": a.activity_type,
        "title": a.title,
        "focus_area": a.focus_area,
        "lead": a.lead,
        "participants": a.participants,
        "subject": a.subject,
        "department": a.department,
        "judgement": a.judgement,
        "status": a.status,
        "strengths": a.strengths,
        "areas_to_develop": a.areas_to_develop,
        "evidence": a.evidence,
        "action_summary": a.action_summary,
        "action_owner": a.action_owner,
        "action_due": a.action_due,
        "action_completed": a.action_completed,
        "impact_review": a.impact_review,
        "impact_reviewed_on": a.impact_reviewed_on,
        "notes": a.notes,
    }


# ── Summary ───────────────────────────────────────────────────────

def summary() -> QASummary:
    rows = list_activities()
    out = QASummary(total=len(rows))
    if not rows:
        return out
    j_total = 0
    j_count = 0
    leads: set[str] = set()
    today = _dt.date.today().isoformat()
    for a in rows:
        if a.is_open:
            out.open_count += 1
        out.by_status[a.status] = out.by_status.get(a.status, 0) + 1
        out.by_type[a.activity_type] = out.by_type.get(
            a.activity_type, 0) + 1
        if a.focus_area:
            out.by_focus[a.focus_area] = out.by_focus.get(
                a.focus_area, 0) + 1
        if a.judgement is not None:
            j_total += a.judgement
            j_count += 1
            out.by_judgement[a.judgement] = out.by_judgement.get(
                a.judgement, 0) + 1
        if a.action_summary and not a.action_completed:
            out.actions_outstanding += 1
            if a.action_due and a.action_due < today:
                out.actions_overdue += 1
        leads.add(a.lead)
    out.distinct_leads = len(leads)
    if j_count:
        out.average_judgement = round(j_total / j_count, 2)
    return out


__all__ = [
    "ACTIVITY_TYPES", "DEFAULT_ACTIVITY_TYPE",
    "FOCUS_AREAS", "DEFAULT_FOCUS_AREA",
    "STATUSES", "DEFAULT_STATUS",
    "JUDGEMENTS", "judgement_label",
    "ValidationError",
    "QAActivity", "QASummary",
    "init_db",
    "create_activity", "update_activity", "delete_activity",
    "get_activity", "list_activities",
    "set_status", "record_findings", "set_action",
    "complete_action", "close_activity",
    "summary",
]
