"""Disciplinary data layer for Sixth Form System.

Formal disciplinary cases that escalate beyond the behaviour log:
warnings, detentions, internal/external exclusions, suspensions,
permanent exclusions, behaviour contracts and parent meetings.
Each case has a workflow Reported → Under Investigation → Sanction
Issued → Sanction Served → Closed (with an optional Appealed
branch). FK cascade on students.

The appeal branch has formal stages (``disciplinary_hearings``): an
appeal hearing, the governor panel that must consider suspensions and
exclusions, and an independent review panel — each with panel members,
hearing date, outcome and the date the decision letter went out.
``disciplinary_la_notifications`` records every statutory notification
of a suspension / exclusion (local authority, virtual school head for
a looked-after child, governing board, parents).
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system import paths as _paths
from education_system.systems.sixth_form.infrastructure import soft_delete as _soft
from education_system.systems.sixth_form.domain.pastoral import _records

logger = logging.getLogger(__name__)

CASE_TYPES: tuple[str, ...] = (
    "Verbal Warning",
    "Written Warning",
    "Final Written Warning",
    "Detention",
    "Internal Exclusion",
    "Fixed-Term Suspension",
    "Permanent Exclusion",
    "Behaviour Contract",
    "Parent Meeting",
    "Restorative Conference",
    "Other",
)
DEFAULT_CASE_TYPE = "Written Warning"

SEVERITIES: tuple[int, ...] = (1, 2, 3, 4, 5)
_SEVERITY_LABELS = {
    1: "Low", 2: "Moderate", 3: "Serious",
    4: "Severe", 5: "Critical",
}


def severity_label(s: int | None) -> str:
    if s is None:
        return "—"
    return _SEVERITY_LABELS.get(s, "Unknown")


STATUSES: tuple[str, ...] = (
    "Reported",
    "Under Investigation",
    "Sanction Issued",
    "Sanction Served",
    "Appealed",
    "Appeal Upheld",
    "Appeal Overturned",
    "Closed",
)
DEFAULT_STATUS = "Reported"


class ValidationError(Exception):
    pass


@dataclass
class DisciplinaryCase:
    case_id: int
    student_id: str
    incident_date: str
    reported_on: str
    case_type: str
    severity: int
    title: str
    description: str | None
    location: str | None
    witnesses: str | None
    related_behaviour_id: int | None
    status: str
    issued_by: str | None
    signed_off_by: str | None
    sanction_summary: str | None
    sanction_start: str | None
    sanction_end: str | None
    sanction_days: int | None
    parent_informed: bool
    parent_informed_on: str | None
    parent_meeting_on: str | None
    appeal_submitted_on: str | None
    appeal_outcome: str | None
    reintegration_plan: str | None
    notes: str | None
    created_on: str
    updated_on: str
    #: Archive (soft delete) — set by delete_*, cleared by restore_*.
    archived_at: str | None = None
    archived_by: str | None = None
    archive_reason: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status not in ("Closed", "Appeal Upheld",
                                          "Appeal Overturned")

    @property
    def severity_label(self) -> str:
        return severity_label(self.severity)

    @property
    def sanction_active(self) -> bool:
        if not self.sanction_start or not self.sanction_end:
            return False
        today = _dt.date.today().isoformat()
        return (self.sanction_start <= today
                  <= self.sanction_end)

    @property
    def parent_meeting_pending(self) -> bool:
        return (self.case_type == "Parent Meeting"
                  and not self.parent_meeting_on
                  and self.is_open)


@dataclass
class DisciplinarySummary:
    total: int = 0
    open_count: int = 0
    active_sanctions: int = 0
    appeals_pending: int = 0
    pending_parent_meetings: int = 0
    distinct_students: int = 0
    average_severity: float | None = None
    by_status: dict[str, int] = field(default_factory=dict)
    by_type: dict[str, int] = field(default_factory=dict)
    by_severity: dict[int, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(_paths.SIXTH_FORM_DISCIPLINARY_DB)
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
            CREATE TABLE IF NOT EXISTS disciplinary_cases (
                case_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                incident_date TEXT NOT NULL,
                reported_on TEXT NOT NULL,
                case_type TEXT NOT NULL,
                severity INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                location TEXT,
                witnesses TEXT,
                related_behaviour_id INTEGER,
                status TEXT NOT NULL,
                issued_by TEXT,
                signed_off_by TEXT,
                sanction_summary TEXT,
                sanction_start TEXT,
                sanction_end TEXT,
                sanction_days INTEGER,
                parent_informed INTEGER NOT NULL DEFAULT 0,
                parent_informed_on TEXT,
                parent_meeting_on TEXT,
                appeal_submitted_on TEXT,
                appeal_outcome TEXT,
                reintegration_plan TEXT,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(student_id)
                  ON DELETE CASCADE
            )
        """)
        conn.executescript(_HEARING_SCHEMA)
        _soft.ensure_columns(conn, "disciplinary_cases")


# ── Validation ─────────────────────────────────────────────────────

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

    out["incident_date"] = (out.get("incident_date") or "").strip()
    if not out["incident_date"]:
        raise ValidationError("Incident date is required")
    _check_date("Incident date", out["incident_date"])

    out["reported_on"] = (out.get("reported_on") or "").strip()
    if not out["reported_on"]:
        out["reported_on"] = _dt.date.today().isoformat()
    _check_date("Reported on", out["reported_on"])

    ct = (out.get("case_type") or "").strip()
    if ct not in CASE_TYPES:
        raise ValidationError(
            f"Case type must be one of: {', '.join(CASE_TYPES)}")
    out["case_type"] = ct

    try:
        sev = int(out.get("severity") or 1)
    except (TypeError, ValueError):
        raise ValidationError("Severity must be 1-5")
    if sev not in SEVERITIES:
        raise ValidationError("Severity must be 1-5")
    out["severity"] = sev

    out["title"] = (out.get("title") or "").strip()
    if not out["title"]:
        raise ValidationError("Title is required")

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    for k in ("description", "location", "witnesses",
               "issued_by", "signed_off_by", "sanction_summary",
               "appeal_outcome", "reintegration_plan", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None

    for k in ("sanction_start", "sanction_end",
               "parent_informed_on", "parent_meeting_on",
               "appeal_submitted_on"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
        _check_date(k.replace("_", " ").title(), out[k])

    if (out["sanction_start"] and out["sanction_end"]
            and out["sanction_start"] > out["sanction_end"]):
        raise ValidationError(
            "Sanction start must be on or before sanction end")

    days = out.get("sanction_days")
    if days in (None, ""):
        out["sanction_days"] = None
    else:
        try:
            d = int(days)
        except (TypeError, ValueError):
            raise ValidationError("Sanction days must be an integer")
        if d < 0:
            raise ValidationError("Sanction days must be >= 0")
        out["sanction_days"] = d

    rb = out.get("related_behaviour_id")
    if rb in (None, ""):
        out["related_behaviour_id"] = None
    else:
        try:
            out["related_behaviour_id"] = int(rb)
        except (TypeError, ValueError):
            raise ValidationError(
                "Related behaviour id must be an integer")

    out["parent_informed"] = bool(out.get("parent_informed"))
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def _row(r: sqlite3.Row) -> DisciplinaryCase:
    return DisciplinaryCase(
        case_id=r["case_id"],
        student_id=r["student_id"],
        incident_date=r["incident_date"],
        reported_on=r["reported_on"],
        case_type=r["case_type"],
        severity=r["severity"],
        title=r["title"],
        description=r["description"],
        location=r["location"],
        witnesses=r["witnesses"],
        related_behaviour_id=r["related_behaviour_id"],
        status=r["status"],
        issued_by=r["issued_by"],
        signed_off_by=r["signed_off_by"],
        sanction_summary=r["sanction_summary"],
        sanction_start=r["sanction_start"],
        sanction_end=r["sanction_end"],
        sanction_days=r["sanction_days"],
        parent_informed=bool(r["parent_informed"]),
        parent_informed_on=r["parent_informed_on"],
        parent_meeting_on=r["parent_meeting_on"],
        appeal_submitted_on=r["appeal_submitted_on"],
        appeal_outcome=r["appeal_outcome"],
        reintegration_plan=r["reintegration_plan"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
        archived_at=r["archived_at"] if "archived_at" in r.keys() else None,
        archived_by=r["archived_by"] if "archived_by" in r.keys() else None,
        archive_reason=r["archive_reason"] if "archive_reason" in r.keys() else None,
    )


def create_case(payload: dict[str, Any]) -> DisciplinaryCase:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO disciplinary_cases (
              student_id, incident_date, reported_on,
              case_type, severity, title,
              description, location, witnesses,
              related_behaviour_id, status,
              issued_by, signed_off_by,
              sanction_summary, sanction_start, sanction_end,
              sanction_days,
              parent_informed, parent_informed_on, parent_meeting_on,
              appeal_submitted_on, appeal_outcome,
              reintegration_plan, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["student_id"], p["incident_date"], p["reported_on"],
            p["case_type"], p["severity"], p["title"],
            p["description"], p["location"], p["witnesses"],
            p["related_behaviour_id"], p["status"],
            p["issued_by"], p["signed_off_by"],
            p["sanction_summary"], p["sanction_start"],
            p["sanction_end"], p["sanction_days"],
            1 if p["parent_informed"] else 0,
            p["parent_informed_on"], p["parent_meeting_on"],
            p["appeal_submitted_on"], p["appeal_outcome"],
            p["reintegration_plan"], p["notes"],
            now, now,
        ))
        new_id = cur.lastrowid
    return get_case(new_id)


def update_case(case_id: int,
                   payload: dict[str, Any]) -> DisciplinaryCase:
    init_db()
    if get_case(case_id) is None:
        raise ValidationError(
            f"No disciplinary case with id {case_id}")
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE disciplinary_cases SET
              student_id=?, incident_date=?, reported_on=?,
              case_type=?, severity=?, title=?,
              description=?, location=?, witnesses=?,
              related_behaviour_id=?, status=?,
              issued_by=?, signed_off_by=?,
              sanction_summary=?, sanction_start=?, sanction_end=?,
              sanction_days=?,
              parent_informed=?, parent_informed_on=?,
              parent_meeting_on=?,
              appeal_submitted_on=?, appeal_outcome=?,
              reintegration_plan=?, notes=?,
              updated_on=?
            WHERE case_id=?
        """, (
            p["student_id"], p["incident_date"], p["reported_on"],
            p["case_type"], p["severity"], p["title"],
            p["description"], p["location"], p["witnesses"],
            p["related_behaviour_id"], p["status"],
            p["issued_by"], p["signed_off_by"],
            p["sanction_summary"], p["sanction_start"],
            p["sanction_end"], p["sanction_days"],
            1 if p["parent_informed"] else 0,
            p["parent_informed_on"], p["parent_meeting_on"],
            p["appeal_submitted_on"], p["appeal_outcome"],
            p["reintegration_plan"], p["notes"],
            now, case_id,
        ))
    return get_case(case_id)


def delete_case(case_id: int, *, reason: str | None = None) -> bool:
    """Archive the disciplinary case (a soft delete: UK retention rules expect it to
    be kept). It drops out of :func:`list_cases` unless
    ``include_archived=True``, keeps who/when/why, and can be brought
    back with :func:`restore_case`. Nothing is
    hard-deleted. Returns False if unknown or already archived."""
    init_db()
    with _connect() as conn:
        ok = _soft.archive(conn, "disciplinary_cases", "case_id", case_id,
                           by=_archive_actor(), reason=reason)
    return ok


def restore_case(case_id: int) -> bool:
    """Undo :func:`delete_case` (archive)."""
    init_db()
    with _connect() as conn:
        ok = _soft.restore(conn, "disciplinary_cases", "case_id", case_id)
    return ok


def _archive_actor() -> str | None:
    """Username recorded on archive (the signed-in principal)."""
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or None
    except Exception:
        return None


def get_case(case_id: int) -> DisciplinaryCase | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM disciplinary_cases WHERE case_id=?",
            (case_id,)).fetchone()
        return _row(r) if r else None


def list_cases(*,
                  include_archived: bool = False,
                  student_id: str | None = None,
                  case_type: str | None = None,
                  status: str | None = None,
                  severity: int | None = None,
                  severity_min: int | None = None,
                  open_only: bool = False,
                  active_sanction: bool = False,
                  appeal_pending: bool = False,
                  parent_meeting_pending: bool = False,
                  issued_by_like: str | None = None,
                  date_from: str | None = None,
                  date_to: str | None = None,
                  ) -> list[DisciplinaryCase]:
    init_db()
    sql = "SELECT * FROM disciplinary_cases WHERE 1=1"
    if not include_archived:
        sql += " AND archived_at IS NULL"
    params: list[Any] = []
    if student_id:
        sql += " AND student_id=?"
        params.append(student_id)
    if case_type:
        sql += " AND case_type=?"
        params.append(case_type)
    if status:
        sql += " AND status=?"
        params.append(status)
    if severity is not None:
        sql += " AND severity=?"
        params.append(severity)
    if severity_min is not None:
        sql += " AND severity >= ?"
        params.append(severity_min)
    if open_only:
        sql += (" AND status NOT IN "
                  "('Closed','Appeal Upheld','Appeal Overturned')")
    if active_sanction:
        today = _dt.date.today().isoformat()
        sql += (" AND sanction_start IS NOT NULL"
                  " AND sanction_end IS NOT NULL"
                  " AND sanction_start <= ?"
                  " AND sanction_end >= ?")
        params.extend([today, today])
    if appeal_pending:
        sql += " AND status='Appealed'"
    if parent_meeting_pending:
        sql += (" AND case_type='Parent Meeting'"
                  " AND parent_meeting_on IS NULL"
                  " AND status NOT IN "
                  "('Closed','Appeal Upheld','Appeal Overturned')")
    if issued_by_like:
        sql += " AND issued_by LIKE ?"
        params.append(f"%{issued_by_like}%")
    if date_from:
        _check_date("From", date_from)
        sql += " AND incident_date >= ?"
        params.append(date_from)
    if date_to:
        _check_date("To", date_to)
        sql += " AND incident_date <= ?"
        params.append(date_to)
    sql += " ORDER BY incident_date DESC, case_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


def cases_for_student(student_id: str) -> list[DisciplinaryCase]:
    return list_cases(student_id=student_id)


# ── Workflow ─────────────────────────────────────────────────────

def _to_dict(c: DisciplinaryCase) -> dict[str, Any]:
    return {
        "student_id": c.student_id,
        "incident_date": c.incident_date,
        "reported_on": c.reported_on,
        "case_type": c.case_type,
        "severity": c.severity,
        "title": c.title,
        "description": c.description,
        "location": c.location,
        "witnesses": c.witnesses,
        "related_behaviour_id": c.related_behaviour_id,
        "status": c.status,
        "issued_by": c.issued_by,
        "signed_off_by": c.signed_off_by,
        "sanction_summary": c.sanction_summary,
        "sanction_start": c.sanction_start,
        "sanction_end": c.sanction_end,
        "sanction_days": c.sanction_days,
        "parent_informed": c.parent_informed,
        "parent_informed_on": c.parent_informed_on,
        "parent_meeting_on": c.parent_meeting_on,
        "appeal_submitted_on": c.appeal_submitted_on,
        "appeal_outcome": c.appeal_outcome,
        "reintegration_plan": c.reintegration_plan,
        "notes": c.notes,
    }


def issue_sanction(case_id: int, *,
                       summary: str, issued_by: str,
                       start: str | None = None,
                       end: str | None = None,
                       days: int | None = None) -> DisciplinaryCase:
    c = get_case(case_id)
    if c is None:
        raise ValidationError(
            f"No disciplinary case with id {case_id}")
    if not summary:
        raise ValidationError("Sanction summary is required")
    if not issued_by:
        raise ValidationError("Issued by is required")
    data = _to_dict(c)
    data["sanction_summary"] = summary
    data["issued_by"] = issued_by
    data["sanction_start"] = start
    data["sanction_end"] = end
    data["sanction_days"] = days
    data["status"] = "Sanction Issued"
    return update_case(case_id, data)


def mark_served(case_id: int) -> DisciplinaryCase:
    c = get_case(case_id)
    if c is None:
        raise ValidationError(
            f"No disciplinary case with id {case_id}")
    data = _to_dict(c)
    data["status"] = "Sanction Served"
    return update_case(case_id, data)


def inform_parent(case_id: int, *,
                      informed_on: str | None = None,
                      meeting_on: str | None = None
                      ) -> DisciplinaryCase:
    c = get_case(case_id)
    if c is None:
        raise ValidationError(
            f"No disciplinary case with id {case_id}")
    data = _to_dict(c)
    data["parent_informed"] = True
    data["parent_informed_on"] = (
        informed_on or _dt.date.today().isoformat())
    if meeting_on:
        data["parent_meeting_on"] = meeting_on
    return update_case(case_id, data)


def submit_appeal(case_id: int, *,
                      submitted_on: str | None = None
                      ) -> DisciplinaryCase:
    c = get_case(case_id)
    if c is None:
        raise ValidationError(
            f"No disciplinary case with id {case_id}")
    data = _to_dict(c)
    data["status"] = "Appealed"
    data["appeal_submitted_on"] = (
        submitted_on or _dt.date.today().isoformat())
    return update_case(case_id, data)


def resolve_appeal(case_id: int, *,
                       outcome: str, upheld: bool) -> DisciplinaryCase:
    if not outcome:
        raise ValidationError("Outcome is required")
    c = get_case(case_id)
    if c is None:
        raise ValidationError(
            f"No disciplinary case with id {case_id}")
    data = _to_dict(c)
    data["appeal_outcome"] = outcome
    data["status"] = "Appeal Upheld" if upheld else "Appeal Overturned"
    return update_case(case_id, data)


def close_case(case_id: int, *,
                  reintegration_plan: str | None = None
                  ) -> DisciplinaryCase:
    c = get_case(case_id)
    if c is None:
        raise ValidationError(
            f"No disciplinary case with id {case_id}")
    data = _to_dict(c)
    if reintegration_plan:
        data["reintegration_plan"] = reintegration_plan
    data["status"] = "Closed"
    return update_case(case_id, data)


def set_status(case_id: int, new_status: str) -> DisciplinaryCase:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    c = get_case(case_id)
    if c is None:
        raise ValidationError(
            f"No disciplinary case with id {case_id}")
    return update_case(case_id,
                          {**_to_dict(c), "status": new_status})


# ── Summary ───────────────────────────────────────────────────────

def summary() -> DisciplinarySummary:
    rows = list_cases()
    out = DisciplinarySummary(total=len(rows))
    if not rows:
        return out
    s_total = 0
    s_count = 0
    students: set[str] = set()
    today = _dt.date.today().isoformat()
    for c in rows:
        students.add(c.student_id)
        if c.is_open:
            out.open_count += 1
        if (c.sanction_start and c.sanction_end
                and c.sanction_start <= today <= c.sanction_end):
            out.active_sanctions += 1
        if c.status == "Appealed":
            out.appeals_pending += 1
        if c.parent_meeting_pending:
            out.pending_parent_meetings += 1
        out.by_status[c.status] = out.by_status.get(c.status, 0) + 1
        out.by_type[c.case_type] = out.by_type.get(c.case_type, 0) + 1
        out.by_severity[c.severity] = out.by_severity.get(
            c.severity, 0) + 1
        s_total += c.severity
        s_count += 1
    out.distinct_students = len(students)
    if s_count:
        out.average_severity = round(s_total / s_count, 2)
    return out


__all__ = [
    "CASE_TYPES", "DEFAULT_CASE_TYPE",
    "SEVERITIES", "severity_label",
    "STATUSES", "DEFAULT_STATUS",
    "ValidationError",
    "DisciplinaryCase", "DisciplinarySummary",
    "init_db",
    "create_case", "update_case", "delete_case",
    "get_case", "list_cases", "cases_for_student",
    "issue_sanction", "mark_served", "inform_parent",
    "submit_appeal", "resolve_appeal", "close_case",
    "set_status",
    "summary",
    # Appeal stages + LA notifications
    "HEARING_STAGES", "HEARING_OUTCOMES", "EXCLUSION_CASE_TYPES",
    "NOTIFICATION_TYPES", "NOTIFIED_PARTIES", "NOTIFICATION_METHODS",
    "Hearing", "LANotification", "HEARING_SPEC", "NOTIFICATION_SPEC",
    "NotificationGap", "add_school_days",
    "schedule_hearing", "get_hearing", "list_hearings", "update_hearing",
    "record_hearing_outcome", "mark_letter_sent", "delete_hearing",
    "governor_panel_deadline", "record_notification", "list_notifications",
    "update_notification", "delete_notification",
    "notifications_outstanding",
]


# ══ Appeal hearings, governor panel, LA notifications ═════════════

HEARING_STAGES: tuple[str, ...] = (
    "Appeal Hearing",
    "Governor Panel",
    "Independent Review Panel",
)
HEARING_OUTCOMES: tuple[str, ...] = (
    "Pending",
    "Sanction upheld",
    "Sanction varied",
    "Sanction overturned",
    "Reinstated",
    "Reconsider (IRP direction)",
    "Withdrawn",
)
#: Case types that need the governor panel and LA notification.
EXCLUSION_CASE_TYPES: tuple[str, ...] = (
    "Fixed-Term Suspension", "Permanent Exclusion",
)
NOTIFICATION_TYPES: tuple[str, ...] = (
    "Suspension", "Permanent Exclusion", "Governor Decision",
    "Reinstatement", "Exclusion Withdrawn", "IRP Outcome",
)
NOTIFIED_PARTIES: tuple[str, ...] = (
    "Local Authority", "Home Local Authority", "Virtual School Head",
    "Social Worker", "Parent / Carer", "Governing Board",
)
NOTIFICATION_METHODS: tuple[str, ...] = (
    "E-mail", "Letter", "LA portal", "Phone", "In person",
)

#: Hearing outcome -> case status (others leave the status alone).
_OUTCOME_STATUS: dict[str, str] = {
    "Sanction upheld": "Appeal Upheld",
    "Sanction overturned": "Appeal Overturned",
    "Reinstated": "Appeal Overturned",
}

_HEARING_SCHEMA = """
CREATE TABLE IF NOT EXISTS disciplinary_hearings (
    hearing_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id           INTEGER NOT NULL,
    student_id        TEXT NOT NULL,
    stage             TEXT NOT NULL,
    requested_on      TEXT,
    hearing_date      TEXT,
    panel_members     TEXT,
    chair             TEXT,
    clerk             TEXT,
    parent_attended   INTEGER NOT NULL DEFAULT 0,
    student_attended  INTEGER NOT NULL DEFAULT 0,
    representations   TEXT,
    outcome           TEXT NOT NULL DEFAULT 'Pending',
    outcome_reasons   TEXT,
    decision_date     TEXT,
    letter_sent_on    TEXT,
    letter_sent_by    TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (case_id) REFERENCES disciplinary_cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS disciplinary_la_notifications (
    notification_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id            INTEGER NOT NULL,
    student_id         TEXT NOT NULL,
    notification_type  TEXT NOT NULL,
    notified_party     TEXT NOT NULL,
    party_name         TEXT,
    notified_on        TEXT NOT NULL,
    method             TEXT,
    reference          TEXT,
    days_excluded      INTEGER,
    reason             TEXT,
    notified_by        TEXT,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (case_id) REFERENCES disciplinary_cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dh_case  ON disciplinary_hearings(case_id);
CREATE INDEX IF NOT EXISTS idx_dln_case ON disciplinary_la_notifications(case_id);
"""


@dataclass
class Hearing:
    hearing_id: int
    case_id: int
    student_id: str
    stage: str
    requested_on: str | None
    hearing_date: str | None
    panel_members: str | None
    chair: str | None
    clerk: str | None
    parent_attended: bool
    student_attended: bool
    representations: str | None
    outcome: str
    outcome_reasons: str | None
    decision_date: str | None
    letter_sent_on: str | None
    letter_sent_by: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def letter_outstanding(self) -> bool:
        return self.outcome != "Pending" and not self.letter_sent_on


@dataclass
class LANotification:
    notification_id: int
    case_id: int
    student_id: str
    notification_type: str
    notified_party: str
    party_name: str | None
    notified_on: str
    method: str | None
    reference: str | None
    days_excluded: int | None
    reason: str | None
    notified_by: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None


_C = _records.Col

HEARING_SPEC = _records.TableSpec(
    table="disciplinary_hearings", id_col="hearing_id", row_type=Hearing,
    label="Hearing", order_by="hearing_date IS NULL, hearing_date, hearing_id",
    cols=(
        _C("case_id", "Case #", "int", required=True, fixed=True),
        _C("student_id", "Student", "student", fixed=True, hidden=True),
        _C("stage", "Stage", "choice", required=True,
           choices=HEARING_STAGES),
        _C("requested_on", "Requested on", "date"),
        _C("hearing_date", "Hearing date", "date"),
        _C("panel_members", "Panel members", "multiline"),
        _C("chair", "Chair"),
        _C("clerk", "Clerk", listed=False),
        _C("parent_attended", "Parent attended", "bool", listed=False),
        _C("student_attended", "Student attended", "bool", listed=False),
        _C("representations", "Representations", "multiline",
           listed=False),
        _C("outcome", "Outcome", "choice", choices=HEARING_OUTCOMES,
           default="Pending"),
        _C("outcome_reasons", "Reasons", "multiline", listed=False),
        _C("decision_date", "Decision date", "date"),
        _C("letter_sent_on", "Letter sent", "date"),
        _C("letter_sent_by", "Letter sent by", listed=False),
        _C("notes", "Notes", "multiline", listed=False),
    ))

NOTIFICATION_SPEC = _records.TableSpec(
    table="disciplinary_la_notifications", id_col="notification_id",
    row_type=LANotification, label="Statutory notification",
    order_by="notified_on DESC, notification_id DESC",
    cols=(
        _C("case_id", "Case #", "int", required=True, fixed=True),
        _C("student_id", "Student", "student", fixed=True, hidden=True),
        _C("notification_type", "Type", "choice", required=True,
           choices=NOTIFICATION_TYPES),
        _C("notified_party", "Notified", "choice", required=True,
           choices=NOTIFIED_PARTIES, default="Local Authority"),
        _C("party_name", "Name / authority"),
        _C("notified_on", "Notified on", "date", required=True,
           default=_records.today),
        _C("method", "Method", "choice", choices=NOTIFICATION_METHODS),
        _C("reference", "Reference"),
        _C("days_excluded", "School days excluded", "int", min_value=0),
        _C("reason", "Reason given", "multiline", listed=False),
        _C("notified_by", "Notified by", listed=False),
        _C("notes", "Notes", "multiline", listed=False),
    ))


def _case_or_error(case_id: int) -> DisciplinaryCase:
    c = get_case(case_id)
    if c is None:
        raise ValidationError(f"No disciplinary case with id {case_id}")
    return c


def add_school_days(start: str, days: int) -> str:
    """*start* plus *days* school days (Mon-Fri; holidays not known)."""
    d = _dt.date.fromisoformat(start)
    left = days
    while left > 0:
        d += _dt.timedelta(days=1)
        if d.weekday() < 5:
            left -= 1
    return d.isoformat()


def governor_panel_deadline(case: DisciplinaryCase) -> str | None:
    """Governors must consider a permanent exclusion (or a suspension
    taking the student over 15 school days in a term) within 15 school
    days of being notified. Counted from the sanction start."""
    if case.case_type not in EXCLUSION_CASE_TYPES:
        return None
    if case.case_type == "Fixed-Term Suspension" \
            and (case.sanction_days or 0) <= 5:
        return None
    start = case.sanction_start or case.reported_on
    return add_school_days(start, 15)


def _hearing_rules(p: dict[str, Any], case: DisciplinaryCase) -> None:
    if p["stage"] in ("Governor Panel", "Independent Review Panel") \
            and case.case_type not in EXCLUSION_CASE_TYPES:
        raise ValidationError(
            f"A {p['stage']} is only for suspensions and exclusions "
            f"(case #{case.case_id} is a {case.case_type})")
    if p["stage"] == "Independent Review Panel" \
            and case.case_type != "Permanent Exclusion":
        raise ValidationError(
            "An independent review panel only follows a permanent "
            "exclusion")
    if p["hearing_date"] and p["requested_on"] \
            and p["hearing_date"] < p["requested_on"]:
        raise ValidationError("Hearing date cannot be before the request")
    if p["outcome"] != "Pending":
        if not p["hearing_date"]:
            raise ValidationError("Record the hearing date with the outcome")
        if not (p["panel_members"] or "").strip():
            raise ValidationError("Record the panel members with the outcome")
        if not p["decision_date"]:
            p["decision_date"] = p["hearing_date"]
    if p["letter_sent_on"] and p["outcome"] == "Pending":
        raise ValidationError("A decision letter needs an outcome first")


def schedule_hearing(data: dict[str, Any]) -> Hearing:
    """Open an appeal / governor panel / IRP stage on a case. The case
    moves to 'Appealed' and appeal_submitted_on is filled if blank."""
    init_db()
    p = _records.validate(HEARING_SPEC, data, error=ValidationError)
    case = _case_or_error(p["case_id"])
    p["student_id"] = case.student_id
    _hearing_rules(p, case)
    with _connect() as conn:
        new_id = _records.insert(conn, HEARING_SPEC, p)
    if case.status != "Appealed" and p["outcome"] == "Pending":
        submit_appeal(case.case_id, submitted_on=(
            case.appeal_submitted_on or p["requested_on"]
            or _records.today()))
    logger.info("Scheduled %s #%d for case #%d", p["stage"], new_id,
                case.case_id)
    if p["outcome"] != "Pending":
        _apply_outcome(case.case_id, p)
    return get_hearing(new_id)


def get_hearing(hearing_id: int) -> Hearing | None:
    init_db()
    with _connect() as conn:
        return _records.fetch(conn, HEARING_SPEC, hearing_id)


def list_hearings(*, case_id: int | None = None,
                  stage: str | None = None,
                  pending_only: bool = False,
                  letters_outstanding: bool = False) -> list[Hearing]:
    init_db()
    where = []
    if pending_only:
        where.append("outcome = 'Pending'")
    if letters_outstanding:
        where.append("outcome <> 'Pending' AND letter_sent_on IS NULL")
    with _connect() as conn:
        return _records.select(conn, HEARING_SPEC, equals={
            "case_id": case_id, "stage": stage}, where=where)


def update_hearing(hearing_id: int, data: dict[str, Any]) -> Hearing:
    init_db()
    existing = get_hearing(hearing_id)
    if existing is None:
        raise ValidationError(f"No hearing #{hearing_id}")
    p = _records.validate(HEARING_SPEC, data, error=ValidationError,
                          existing=existing)
    case = _case_or_error(existing.case_id)
    _hearing_rules(p, case)
    with _connect() as conn:
        _records.update(conn, HEARING_SPEC, hearing_id, p)
    if p["outcome"] != existing.outcome and p["outcome"] != "Pending":
        _apply_outcome(case.case_id, p)
    return get_hearing(hearing_id)


def _apply_outcome(case_id: int, p: dict[str, Any]) -> None:
    case = _case_or_error(case_id)
    data = _to_dict(case)
    line = (f"{p['stage']} {p['decision_date'] or p['hearing_date']}: "
            f"{p['outcome']}"
            + (f" — {p['outcome_reasons']}" if p.get("outcome_reasons")
               else ""))
    data["appeal_outcome"] = (f"{case.appeal_outcome}\n{line}"
                              if case.appeal_outcome else line)
    new_status = _OUTCOME_STATUS.get(p["outcome"])
    if new_status:
        data["status"] = new_status
    update_case(case_id, data)


def record_hearing_outcome(hearing_id: int, *, outcome: str,
                           panel_members: str | None = None,
                           hearing_date: str | None = None,
                           reasons: str | None = None,
                           decision_date: str | None = None) -> Hearing:
    if outcome not in HEARING_OUTCOMES or outcome == "Pending":
        raise ValidationError(
            "Outcome must be one of: "
            + ", ".join(o for o in HEARING_OUTCOMES if o != "Pending"))
    payload: dict[str, Any] = {"outcome": outcome}
    for k, v in (("panel_members", panel_members),
                 ("hearing_date", hearing_date),
                 ("outcome_reasons", reasons),
                 ("decision_date", decision_date)):
        if v not in (None, ""):
            payload[k] = v
    return update_hearing(hearing_id, payload)


def mark_letter_sent(hearing_id: int, *, sent_on: str | None = None,
                     sent_by: str | None = None) -> Hearing:
    return update_hearing(hearing_id, {
        "letter_sent_on": sent_on or _records.today(),
        "letter_sent_by": sent_by or _records.current_username()})


def delete_hearing(hearing_id: int) -> bool:
    init_db()
    with _connect() as conn:
        return _records.delete(conn, HEARING_SPEC, hearing_id)


# ── Statutory notifications ───────────────────────────────────────

def record_notification(data: dict[str, Any]) -> LANotification:
    init_db()
    p = _records.validate(NOTIFICATION_SPEC, data, error=ValidationError)
    case = _case_or_error(p["case_id"])
    p["student_id"] = case.student_id
    if p["days_excluded"] is None and case.sanction_days is not None:
        p["days_excluded"] = case.sanction_days
    p["notified_by"] = p["notified_by"] or _records.current_username()
    with _connect() as conn:
        new_id = _records.insert(conn, NOTIFICATION_SPEC, p)
        out = _records.fetch(conn, NOTIFICATION_SPEC, new_id)
    logger.info("Recorded %s notification to %s for case #%d",
                p["notification_type"], p["notified_party"], case.case_id)
    return out


def list_notifications(*, case_id: int | None = None,
                       student_id: str | None = None
                       ) -> list[LANotification]:
    init_db()
    with _connect() as conn:
        return _records.select(conn, NOTIFICATION_SPEC, equals={
            "case_id": case_id, "student_id": student_id})


def update_notification(notification_id: int,
                        data: dict[str, Any]) -> LANotification:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, NOTIFICATION_SPEC, notification_id)
        if existing is None:
            raise ValidationError(f"No notification #{notification_id}")
        p = _records.validate(NOTIFICATION_SPEC, data, error=ValidationError,
                              existing=existing)
        _records.update(conn, NOTIFICATION_SPEC, notification_id, p)
        return _records.fetch(conn, NOTIFICATION_SPEC, notification_id)


def delete_notification(notification_id: int) -> bool:
    init_db()
    with _connect() as conn:
        return _records.delete(conn, NOTIFICATION_SPEC, notification_id)


@dataclass
class NotificationGap:
    case: DisciplinaryCase
    missing: list[str]
    governor_deadline: str | None


def notifications_outstanding() -> list[NotificationGap]:
    """Suspension / exclusion cases with a sanction issued that are
    missing a statutory notification: the local authority always,
    parents always, the virtual school head when the student has an
    active care record (looked-after / previously looked-after)."""
    init_db()
    today = _records.today()
    with _connect() as conn:
        lac: set[str] = set()
        if _records.table_exists(conn, "vg_care_records"):
            lac = {r[0] for r in conn.execute(
                "SELECT student_id FROM vg_care_records "
                "WHERE care_status IN ('Looked-After Child', "
                "'Previously Looked-After') "
                "AND (end_date IS NULL OR end_date >= ?)", (today,))}
    out: list[NotificationGap] = []
    for c in list_cases():
        if c.case_type not in EXCLUSION_CASE_TYPES:
            continue
        if c.status in ("Reported", "Under Investigation"):
            continue
        sent = {n.notified_party for n in list_notifications(
            case_id=c.case_id)}
        missing = []
        if not sent & {"Local Authority", "Home Local Authority"}:
            missing.append("Local Authority")
        if "Parent / Carer" not in sent and not c.parent_informed:
            missing.append("Parent / Carer")
        if c.student_id in lac and "Virtual School Head" not in sent:
            missing.append("Virtual School Head")
        deadline = governor_panel_deadline(c)
        if deadline and "Governing Board" not in sent and not list_hearings(
                case_id=c.case_id, stage="Governor Panel"):
            missing.append("Governing Board")
        if missing:
            out.append(NotificationGap(c, missing, deadline))
    return out
