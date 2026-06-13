"""Health & Safety data layer for Primary School System.

Incident / hazard register: one parent row per H&S incident, near
miss or hazard observation; plus a child table of corrective
actions (FK CASCADE). Tracks category, severity, RIDDOR reporting,
affected party (student / staff / visitor / contractor / public),
and a status workflow Open → Investigating → Actions Pending →
Resolved → Closed (with optional Reopened).
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.primarysch_system.core import paths as _paths
from education_system.primarysch_system.modules.domain import _pupils_bridge as _students
from education_system.primarysch_system.modules.domain.staff import (
    staff as _staff,
)

logger = logging.getLogger(__name__)

CATEGORIES: tuple[str, ...] = (
    "Slip/Trip/Fall",
    "Manual Handling",
    "Struck By Object",
    "Cut/Laceration",
    "Burn/Scald",
    "Chemical Exposure",
    "Electrical",
    "Fire/Smoke",
    "Asbestos",
    "Violence/Aggression",
    "Vehicle/Traffic",
    "Equipment Failure",
    "Environmental",
    "Near Miss",
    "Hazard Observation",
    "Other",
)
DEFAULT_CATEGORY = "Other"

SEVERITIES: tuple[str, ...] = (
    "Negligible",
    "Minor",
    "Moderate",
    "Major",
    "Catastrophic",
)
DEFAULT_SEVERITY = "Minor"

INCIDENT_TYPES: tuple[str, ...] = (
    "Incident",
    "Near Miss",
    "Hazard",
)
DEFAULT_INCIDENT_TYPE = "Incident"

AFFECTED_PARTIES: tuple[str, ...] = (
    "Student",
    "Staff",
    "Visitor",
    "Contractor",
    "Public",
    "Property Only",
    "None",
    "Other",
)
# Affected parties that name a person (must have a name/id link)
_PERSON_PARTIES = {"Student", "Staff", "Visitor",
                       "Contractor", "Public", "Other"}

STATUSES: tuple[str, ...] = (
    "Open",
    "Investigating",
    "Actions Pending",
    "Resolved",
    "Closed",
    "Reopened",
)
DEFAULT_STATUS = "Open"

ACTION_STATUSES: tuple[str, ...] = (
    "Open",
    "In Progress",
    "Completed",
    "Cancelled",
    "Overdue",
)
DEFAULT_ACTION_STATUS = "Open"

ACTION_PRIORITIES: tuple[str, ...] = (
    "Low",
    "Medium",
    "High",
    "Critical",
)
DEFAULT_ACTION_PRIORITY = "Medium"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


class ValidationError(ValueError):
    pass


# ── Dataclasses ────────────────────────────────────────────────────

@dataclass
class Incident:
    incident_id: int
    incident_date: str
    incident_time: str | None
    location: str
    category: str
    severity: str
    incident_type: str
    affected_party: str | None
    affected_student_id: str | None
    affected_staff_id: str | None
    affected_name: str | None
    description: str
    immediate_action: str | None
    riddor_reportable: bool
    riddor_reference: str | None
    riddor_reported_on: str | None
    reported_by: str | None
    assessor_id: str | None
    status: str
    root_cause: str | None
    parent_informed: bool
    hse_notified: bool
    lessons_learned: str | None
    review_due: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status not in ("Closed",)

    @property
    def is_high_severity(self) -> bool:
        return self.severity in ("Major", "Catastrophic")


@dataclass
class Action:
    action_id: int
    incident_id: int
    action: str
    owner_id: str | None
    due_date: str | None
    completed_on: str | None
    status: str
    priority: str
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_overdue(self) -> bool:
        if self.status in ("Completed", "Cancelled"):
            return False
        if not self.due_date:
            return False
        return self.due_date < _dt.date.today().isoformat()


@dataclass
class IncidentView:
    incident: Incident
    open_actions: list[Action] = field(default_factory=list)
    completed_actions: list[Action] = field(default_factory=list)
    reporter_name: str | None = None
    assessor_name: str | None = None
    affected_display: str | None = None

    @property
    def actions_count(self) -> int:
        return len(self.open_actions) + len(self.completed_actions)


@dataclass
class Summary:
    total: int = 0
    open_incidents: int = 0
    riddor_reportable: int = 0
    open_actions: int = 0
    overdue_actions: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_severity: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)
    by_type: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.HEALTH_SAFETY_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    # Ensure FK targets exist
    try:
        _students.init_db()
    except Exception:
        logger.debug("students.init_db() failed", exc_info=True)
    try:
        _staff.init_db()
    except Exception:
        logger.debug("staff.init_db() failed", exc_info=True)
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hs_incidents (
                incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_date TEXT NOT NULL,
                incident_time TEXT,
                location TEXT NOT NULL,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                incident_type TEXT NOT NULL,
                affected_party TEXT,
                affected_student_id TEXT,
                affected_staff_id TEXT,
                affected_name TEXT,
                description TEXT NOT NULL,
                immediate_action TEXT,
                riddor_reportable INTEGER NOT NULL DEFAULT 0,
                riddor_reference TEXT,
                riddor_reported_on TEXT,
                reported_by TEXT,
                assessor_id TEXT,
                status TEXT NOT NULL DEFAULT 'Open',
                root_cause TEXT,
                parent_informed INTEGER NOT NULL DEFAULT 0,
                hse_notified INTEGER NOT NULL DEFAULT 0,
                lessons_learned TEXT,
                review_due TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(affected_student_id)
                    REFERENCES students(student_id) ON DELETE SET NULL,
                FOREIGN KEY(affected_staff_id)
                    REFERENCES staff(staff_id) ON DELETE SET NULL,
                FOREIGN KEY(reported_by)
                    REFERENCES staff(staff_id) ON DELETE SET NULL,
                FOREIGN KEY(assessor_id)
                    REFERENCES staff(staff_id) ON DELETE SET NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hs_actions (
                action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                owner_id TEXT,
                due_date TEXT,
                completed_on TEXT,
                status TEXT NOT NULL DEFAULT 'Open',
                priority TEXT NOT NULL DEFAULT 'Medium',
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(incident_id)
                    REFERENCES hs_incidents(incident_id)
                    ON DELETE CASCADE,
                FOREIGN KEY(owner_id)
                    REFERENCES staff(staff_id) ON DELETE SET NULL
            )
        """)
        for stmt in (
                "CREATE INDEX IF NOT EXISTS ix_hs_inc_date "
                "ON hs_incidents(incident_date)",
                "CREATE INDEX IF NOT EXISTS ix_hs_inc_status "
                "ON hs_incidents(status)",
                "CREATE INDEX IF NOT EXISTS ix_hs_inc_severity "
                "ON hs_incidents(severity)",
                "CREATE INDEX IF NOT EXISTS ix_hs_inc_category "
                "ON hs_incidents(category)",
                "CREATE INDEX IF NOT EXISTS ix_hs_act_incident "
                "ON hs_actions(incident_id)",
        ):
            conn.execute(stmt)


# ── Validation ─────────────────────────────────────────────────────

def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    if not _DATE_RE.match(value):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _check_time(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    if not _TIME_RE.match(value):
        raise ValidationError(f"{label} must be HH:MM")
    try:
        _dt.time.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be HH:MM")


def _student_exists(sid: str) -> bool:
    try:
        return _students.get_student(sid) is not None
    except Exception:
        return False


def _staff_exists(sid: str) -> bool:
    try:
        return _staff.get_staff(sid) is not None
    except Exception:
        return False


def _norm_text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _norm_required(label: str, v: Any) -> str:
    s = _norm_text(v)
    if not s:
        raise ValidationError(f"{label} is required")
    return s


def _validate_incident(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["incident_date"] = _norm_required(
        "Incident date", out.get("incident_date"))
    _check_date("Incident date", out["incident_date"])
    out["incident_time"] = _norm_text(out.get("incident_time"))
    _check_time("Incident time", out["incident_time"])

    out["location"] = _norm_required("Location", out.get("location"))

    cat = _norm_required("Category", out.get("category"))
    if cat not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(CATEGORIES)}")
    out["category"] = cat

    sev = _norm_required("Severity", out.get("severity"))
    if sev not in SEVERITIES:
        raise ValidationError(
            f"Severity must be one of: {', '.join(SEVERITIES)}")
    out["severity"] = sev

    it = _norm_required("Incident type", out.get("incident_type"))
    if it not in INCIDENT_TYPES:
        raise ValidationError(
            f"Incident type must be one of: "
            f"{', '.join(INCIDENT_TYPES)}")
    out["incident_type"] = it

    ap = _norm_text(out.get("affected_party"))
    if ap is not None and ap not in AFFECTED_PARTIES:
        raise ValidationError(
            f"Affected party must be one of: "
            f"{', '.join(AFFECTED_PARTIES)}")
    out["affected_party"] = ap

    out["affected_student_id"] = _norm_text(
        out.get("affected_student_id"))
    out["affected_staff_id"] = _norm_text(
        out.get("affected_staff_id"))
    out["affected_name"] = _norm_text(out.get("affected_name"))

    if out["affected_student_id"]:
        if not _student_exists(out["affected_student_id"]):
            raise ValidationError(
                f"No student with id "
                f"{out['affected_student_id']}")
    if out["affected_staff_id"]:
        if not _staff_exists(out["affected_staff_id"]):
            raise ValidationError(
                f"No staff with id {out['affected_staff_id']}")

    if ap in _PERSON_PARTIES:
        if not (out["affected_student_id"]
                  or out["affected_staff_id"]
                  or out["affected_name"]):
            raise ValidationError(
                f"Affected party '{ap}' requires a student id, "
                "staff id, or affected name")

    out["description"] = _norm_required(
        "Description", out.get("description"))
    out["immediate_action"] = _norm_text(
        out.get("immediate_action"))

    out["riddor_reportable"] = bool(out.get("riddor_reportable"))
    out["riddor_reference"] = _norm_text(out.get("riddor_reference"))
    out["riddor_reported_on"] = _norm_text(
        out.get("riddor_reported_on"))
    _check_date("RIDDOR reported on", out["riddor_reported_on"])
    if out["riddor_reportable"] and not out["riddor_reported_on"]:
        raise ValidationError(
            "RIDDOR-reportable incidents require "
            "'RIDDOR reported on' (YYYY-MM-DD)")

    out["reported_by"] = _norm_text(out.get("reported_by"))
    if out["reported_by"] and not _staff_exists(out["reported_by"]):
        raise ValidationError(
            f"No staff with id {out['reported_by']}")
    out["assessor_id"] = _norm_text(out.get("assessor_id"))
    if out["assessor_id"] and not _staff_exists(out["assessor_id"]):
        raise ValidationError(
            f"No staff with id {out['assessor_id']}")

    status = _norm_text(out.get("status")) or DEFAULT_STATUS
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["root_cause"] = _norm_text(out.get("root_cause"))
    out["parent_informed"] = bool(out.get("parent_informed"))
    out["hse_notified"] = bool(out.get("hse_notified"))
    out["lessons_learned"] = _norm_text(out.get("lessons_learned"))
    out["review_due"] = _norm_text(out.get("review_due"))
    _check_date("Review due", out["review_due"])
    out["notes"] = _norm_text(out.get("notes"))
    return out


def _validate_action(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["action"] = _norm_required("Action", out.get("action"))
    out["owner_id"] = _norm_text(out.get("owner_id"))
    if out["owner_id"] and not _staff_exists(out["owner_id"]):
        raise ValidationError(
            f"No staff with id {out['owner_id']}")
    out["due_date"] = _norm_text(out.get("due_date"))
    _check_date("Due date", out["due_date"])
    out["completed_on"] = _norm_text(out.get("completed_on"))
    _check_date("Completed on", out["completed_on"])

    status = _norm_text(out.get("status")) or DEFAULT_ACTION_STATUS
    if status not in ACTION_STATUSES:
        raise ValidationError(
            f"Action status must be one of: "
            f"{', '.join(ACTION_STATUSES)}")
    out["status"] = status

    priority = (_norm_text(out.get("priority"))
                  or DEFAULT_ACTION_PRIORITY)
    if priority not in ACTION_PRIORITIES:
        raise ValidationError(
            f"Priority must be one of: "
            f"{', '.join(ACTION_PRIORITIES)}")
    out["priority"] = priority
    out["notes"] = _norm_text(out.get("notes"))

    if status == "Completed" and not out["completed_on"]:
        out["completed_on"] = _dt.date.today().isoformat()
    return out


# ── Row builders ───────────────────────────────────────────────────

def _row_incident(r: sqlite3.Row) -> Incident:
    return Incident(
        incident_id=r["incident_id"],
        incident_date=r["incident_date"],
        incident_time=r["incident_time"],
        location=r["location"],
        category=r["category"],
        severity=r["severity"],
        incident_type=r["incident_type"],
        affected_party=r["affected_party"],
        affected_student_id=r["affected_student_id"],
        affected_staff_id=r["affected_staff_id"],
        affected_name=r["affected_name"],
        description=r["description"],
        immediate_action=r["immediate_action"],
        riddor_reportable=bool(r["riddor_reportable"]),
        riddor_reference=r["riddor_reference"],
        riddor_reported_on=r["riddor_reported_on"],
        reported_by=r["reported_by"],
        assessor_id=r["assessor_id"],
        status=r["status"],
        root_cause=r["root_cause"],
        parent_informed=bool(r["parent_informed"]),
        hse_notified=bool(r["hse_notified"]),
        lessons_learned=r["lessons_learned"],
        review_due=r["review_due"],
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _row_action(r: sqlite3.Row) -> Action:
    return Action(
        action_id=r["action_id"],
        incident_id=r["incident_id"],
        action=r["action"],
        owner_id=r["owner_id"],
        due_date=r["due_date"],
        completed_on=r["completed_on"],
        status=r["status"],
        priority=r["priority"],
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


# ── Incident CRUD ──────────────────────────────────────────────────

def create_incident(payload: dict[str, Any]) -> Incident:
    init_db()
    p = _validate_incident(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO hs_incidents (
              incident_date, incident_time, location, category,
              severity, incident_type, affected_party,
              affected_student_id, affected_staff_id, affected_name,
              description, immediate_action,
              riddor_reportable, riddor_reference,
              riddor_reported_on, reported_by, assessor_id,
              status, root_cause, parent_informed, hse_notified,
              lessons_learned, review_due, notes,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["incident_date"], p["incident_time"], p["location"],
            p["category"], p["severity"], p["incident_type"],
            p["affected_party"], p["affected_student_id"],
            p["affected_staff_id"], p["affected_name"],
            p["description"], p["immediate_action"],
            1 if p["riddor_reportable"] else 0,
            p["riddor_reference"], p["riddor_reported_on"],
            p["reported_by"], p["assessor_id"], p["status"],
            p["root_cause"],
            1 if p["parent_informed"] else 0,
            1 if p["hse_notified"] else 0,
            p["lessons_learned"], p["review_due"], p["notes"],
            now, now,
        ))
        new_id = cur.lastrowid
    return get_incident(new_id)  # type: ignore[return-value]


def update_incident(incident_id: int,
                       payload: dict[str, Any]) -> Incident:
    init_db()
    if get_incident(incident_id) is None:
        raise ValidationError(f"No incident with id {incident_id}")
    p = _validate_incident(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE hs_incidents SET
              incident_date=?, incident_time=?, location=?,
              category=?, severity=?, incident_type=?,
              affected_party=?, affected_student_id=?,
              affected_staff_id=?, affected_name=?,
              description=?, immediate_action=?,
              riddor_reportable=?, riddor_reference=?,
              riddor_reported_on=?, reported_by=?, assessor_id=?,
              status=?, root_cause=?, parent_informed=?,
              hse_notified=?, lessons_learned=?, review_due=?,
              notes=?, updated_at=?
            WHERE incident_id=?
        """, (
            p["incident_date"], p["incident_time"], p["location"],
            p["category"], p["severity"], p["incident_type"],
            p["affected_party"], p["affected_student_id"],
            p["affected_staff_id"], p["affected_name"],
            p["description"], p["immediate_action"],
            1 if p["riddor_reportable"] else 0,
            p["riddor_reference"], p["riddor_reported_on"],
            p["reported_by"], p["assessor_id"], p["status"],
            p["root_cause"],
            1 if p["parent_informed"] else 0,
            1 if p["hse_notified"] else 0,
            p["lessons_learned"], p["review_due"], p["notes"],
            now, incident_id,
        ))
    return get_incident(incident_id)  # type: ignore[return-value]


def delete_incident(incident_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM hs_incidents WHERE incident_id=?",
            (incident_id,))
        return cur.rowcount > 0


def get_incident(incident_id: int) -> Incident | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM hs_incidents WHERE incident_id=?",
            (incident_id,)).fetchone()
        return _row_incident(r) if r else None


def list_incidents(*,
                       status: str | None = None,
                       severity: str | None = None,
                       category: str | None = None,
                       incident_type: str | None = None,
                       affected_party: str | None = None,
                       riddor_only: bool = False,
                       open_only: bool = False,
                       date_from: str | None = None,
                       date_to: str | None = None,
                       search: str | None = None,
                       ) -> list[Incident]:
    init_db()
    sql = "SELECT * FROM hs_incidents WHERE 1=1"
    params: list[Any] = []
    if status:
        sql += " AND status=?"
        params.append(status)
    if severity:
        sql += " AND severity=?"
        params.append(severity)
    if category:
        sql += " AND category=?"
        params.append(category)
    if incident_type:
        sql += " AND incident_type=?"
        params.append(incident_type)
    if affected_party:
        sql += " AND affected_party=?"
        params.append(affected_party)
    if riddor_only:
        sql += " AND riddor_reportable=1"
    if open_only:
        sql += " AND status != 'Closed'"
    if date_from:
        _check_date("From", date_from)
        sql += " AND incident_date >= ?"
        params.append(date_from)
    if date_to:
        _check_date("To", date_to)
        sql += " AND incident_date <= ?"
        params.append(date_to)
    if search:
        like = f"%{search}%"
        sql += (" AND (description LIKE ? OR location LIKE ?"
                  " OR affected_name LIKE ? OR notes LIKE ?)")
        params.extend([like, like, like, like])
    sql += (" ORDER BY incident_date DESC,"
              " incident_time DESC, incident_id DESC")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_incident(r) for r in rows]


def set_status(incident_id: int, new_status: str) -> Incident:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    i = get_incident(incident_id)
    if i is None:
        raise ValidationError(f"No incident with id {incident_id}")
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            "UPDATE hs_incidents SET status=?, updated_at=? "
            "WHERE incident_id=?",
            (new_status, now, incident_id))
    return get_incident(incident_id)  # type: ignore[return-value]


# ── Action CRUD ────────────────────────────────────────────────────

def add_action(incident_id: int,
                  payload: dict[str, Any]) -> Action:
    init_db()
    if get_incident(incident_id) is None:
        raise ValidationError(f"No incident with id {incident_id}")
    p = _validate_action(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO hs_actions (
              incident_id, action, owner_id, due_date,
              completed_on, status, priority, notes,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            incident_id, p["action"], p["owner_id"],
            p["due_date"], p["completed_on"], p["status"],
            p["priority"], p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_action(new_id)  # type: ignore[return-value]


def get_action(action_id: int) -> Action | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM hs_actions WHERE action_id=?",
            (action_id,)).fetchone()
        return _row_action(r) if r else None


def list_actions(*,
                    incident_id: int | None = None,
                    status: str | None = None,
                    overdue_only: bool = False,
                    ) -> list[Action]:
    init_db()
    sql = "SELECT * FROM hs_actions WHERE 1=1"
    params: list[Any] = []
    if incident_id is not None:
        sql += " AND incident_id=?"
        params.append(incident_id)
    if status:
        sql += " AND status=?"
        params.append(status)
    if overdue_only:
        today = _dt.date.today().isoformat()
        sql += (" AND due_date IS NOT NULL AND due_date < ?"
                  " AND status NOT IN ('Completed', 'Cancelled')")
        params.append(today)
    sql += (" ORDER BY (completed_on IS NOT NULL),"
              " due_date IS NULL, due_date ASC, action_id ASC")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_action(r) for r in rows]


def update_action(action_id: int,
                     payload: dict[str, Any]) -> Action:
    init_db()
    existing = get_action(action_id)
    if existing is None:
        raise ValidationError(f"No action with id {action_id}")
    p = _validate_action(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE hs_actions SET
              action=?, owner_id=?, due_date=?, completed_on=?,
              status=?, priority=?, notes=?, updated_at=?
            WHERE action_id=?
        """, (
            p["action"], p["owner_id"], p["due_date"],
            p["completed_on"], p["status"], p["priority"],
            p["notes"], now, action_id,
        ))
    return get_action(action_id)  # type: ignore[return-value]


def complete_action(action_id: int, *,
                       completed_on: str | None = None) -> Action:
    a = get_action(action_id)
    if a is None:
        raise ValidationError(f"No action with id {action_id}")
    _check_date("Completed on", completed_on)
    when = completed_on or _dt.date.today().isoformat()
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            "UPDATE hs_actions SET status=?, completed_on=?, "
            "updated_at=? WHERE action_id=?",
            ("Completed", when, now, action_id))
    return get_action(action_id)  # type: ignore[return-value]


def delete_action(action_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM hs_actions WHERE action_id=?",
            (action_id,))
        return cur.rowcount > 0


# ── Views ──────────────────────────────────────────────────────────

def _staff_name(staff_id: str | None) -> str | None:
    if not staff_id:
        return None
    try:
        s = _staff.get_staff(staff_id)
    except Exception:
        return staff_id
    if s is None:
        return staff_id
    return f"{staff_id} — {s.full_name}"


def _student_name(student_id: str | None) -> str | None:
    if not student_id:
        return None
    try:
        s = _students.get_student(student_id)
    except Exception:
        return student_id
    if s is None:
        return student_id
    return f"{student_id} — {s.full_name}"


def _affected_display(i: Incident) -> str:
    if i.affected_student_id:
        s = _student_name(i.affected_student_id)
        if s:
            return s
    if i.affected_staff_id:
        s = _staff_name(i.affected_staff_id)
        if s:
            return s
    if i.affected_name:
        if i.affected_party:
            return f"{i.affected_name} ({i.affected_party})"
        return i.affected_name
    if i.affected_party:
        return i.affected_party
    return "—"


def view_incident(incident_id: int) -> IncidentView | None:
    i = get_incident(incident_id)
    if i is None:
        return None
    acts = list_actions(incident_id=incident_id)
    return IncidentView(
        incident=i,
        open_actions=[a for a in acts
                          if a.status not in ("Completed",
                                                 "Cancelled")],
        completed_actions=[a for a in acts
                                if a.status in ("Completed",
                                                   "Cancelled")],
        reporter_name=_staff_name(i.reported_by),
        assessor_name=_staff_name(i.assessor_id),
        affected_display=_affected_display(i),
    )


def list_views(**filters: Any) -> list[IncidentView]:
    out: list[IncidentView] = []
    for i in list_incidents(**filters):
        v = view_incident(i.incident_id)
        if v is not None:
            out.append(v)
    return out


# ── Summary ────────────────────────────────────────────────────────

def summary() -> Summary:
    incs = list_incidents()
    out = Summary(total=len(incs))
    for i in incs:
        if i.is_open:
            out.open_incidents += 1
        if i.riddor_reportable:
            out.riddor_reportable += 1
        out.by_status[i.status] = out.by_status.get(i.status, 0) + 1
        out.by_severity[i.severity] = (
            out.by_severity.get(i.severity, 0) + 1)
        out.by_category[i.category] = (
            out.by_category.get(i.category, 0) + 1)
        out.by_type[i.incident_type] = (
            out.by_type.get(i.incident_type, 0) + 1)
    today = _dt.date.today().isoformat()
    for a in list_actions():
        if a.status in ("Completed", "Cancelled"):
            continue
        out.open_actions += 1
        if a.due_date and a.due_date < today:
            out.overdue_actions += 1
    return out


__all__ = [
    "CATEGORIES", "DEFAULT_CATEGORY",
    "SEVERITIES", "DEFAULT_SEVERITY",
    "INCIDENT_TYPES", "DEFAULT_INCIDENT_TYPE",
    "AFFECTED_PARTIES",
    "STATUSES", "DEFAULT_STATUS",
    "ACTION_STATUSES", "DEFAULT_ACTION_STATUS",
    "ACTION_PRIORITIES", "DEFAULT_ACTION_PRIORITY",
    "ValidationError",
    "Incident", "Action", "IncidentView", "Summary",
    "init_db",
    "create_incident", "get_incident", "list_incidents",
    "update_incident", "set_status", "delete_incident",
    "view_incident", "list_views",
    "add_action", "get_action", "list_actions",
    "update_action", "complete_action", "delete_action",
    "summary",
]
