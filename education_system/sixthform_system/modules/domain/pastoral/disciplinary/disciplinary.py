"""Disciplinary data layer for Sixth Form System.

Formal disciplinary cases that escalate beyond the behaviour log:
warnings, detentions, internal/external exclusions, suspensions,
permanent exclusions, behaviour contracts and parent meetings.
Each case has a workflow Reported → Under Investigation → Sanction
Issued → Sanction Served → Closed (with an optional Appealed
branch). FK cascade on students.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.sixthform_system.core import paths as _paths

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
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.DISCIPLINARY_DB)
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


def delete_case(case_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM disciplinary_cases WHERE case_id=?",
            (case_id,))
        return cur.rowcount > 0


def get_case(case_id: int) -> DisciplinaryCase | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM disciplinary_cases WHERE case_id=?",
            (case_id,)).fetchone()
        return _row(r) if r else None


def list_cases(*,
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
]
