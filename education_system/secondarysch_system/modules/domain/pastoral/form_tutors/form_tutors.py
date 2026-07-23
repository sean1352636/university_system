"""Form-tutor roster + meeting log for the Secondary School System.

Two tables:

* ``form_tutor_assignments`` — one row per (year_group, form_group,
                                 academic_year, tutor_name) showing
                                 who is currently tutoring which form.
                                 The role distinguishes the primary
                                 Tutor from a Co-tutor (cover, second
                                 staff member).
* ``form_tutor_meetings``    — meeting log attached to an assignment;
                                 used to capture form-time agendas,
                                 1-to-1 chats, parent contacts and
                                 follow-up actions.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

ROLES: tuple[str, ...] = ("Tutor", "Co-tutor", "Cover", "Mentor")
DEFAULT_ROLE: str = "Tutor"

ASSIGNMENT_STATUSES: tuple[str, ...] = (
    "Active", "Ended", "Suspended", "Provisional")
DEFAULT_ASSIGNMENT_STATUS: str = "Active"

MEETING_TYPES: tuple[str, ...] = (
    "Form time", "1-to-1", "Parent contact", "Pastoral",
    "Behaviour", "Attendance", "Wellbeing", "Other")
DEFAULT_MEETING_TYPE: str = "Form time"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AY_RE = re.compile(r"^\d{4}/\d{2}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS form_tutor_assignments (
    assignment_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    year_group       TEXT NOT NULL,
    form_group       TEXT NOT NULL,
    academic_year    TEXT NOT NULL,
    tutor_name       TEXT NOT NULL,
    role             TEXT NOT NULL DEFAULT 'Tutor',
    contact_email    TEXT,
    start_date       TEXT NOT NULL DEFAULT (date('now')),
    end_date         TEXT,
    status           TEXT NOT NULL DEFAULT 'Active',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    UNIQUE (year_group, form_group, academic_year, tutor_name, role)
);

CREATE TABLE IF NOT EXISTS form_tutor_meetings (
    meeting_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id    INTEGER NOT NULL,
    meeting_date     TEXT NOT NULL DEFAULT (date('now')),
    meeting_type     TEXT NOT NULL DEFAULT 'Form time',
    pupils_present   TEXT,
    agenda           TEXT,
    decisions        TEXT,
    follow_up_actions TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (assignment_id) REFERENCES form_tutor_assignments(assignment_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fta_year_form
    ON form_tutor_assignments(year_group, form_group);
CREATE INDEX IF NOT EXISTS idx_fta_tutor
    ON form_tutor_assignments(tutor_name);
CREATE INDEX IF NOT EXISTS idx_ftm_assignment
    ON form_tutor_meetings(assignment_id);
"""


@dataclass
class TutorAssignment:
    assignment_id: int
    year_group: str
    form_group: str
    academic_year: str
    tutor_name: str
    role: str
    contact_email: str | None
    start_date: str
    end_date: str | None
    status: str
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class TutorMeeting:
    meeting_id: int
    assignment_id: int
    meeting_date: str
    meeting_type: str
    pupils_present: str | None
    agenda: str | None
    decisions: str | None
    follow_up_actions: str | None
    notes: str | None
    tutor_name: str | None = None
    year_group: str | None = None
    form_group: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise form_tutors tables")
        raise
    logger.info("Secondary form_tutors tables ready")
    _DB_READY = True


def _row_assignment(r: sqlite3.Row) -> TutorAssignment:
    return TutorAssignment(
        assignment_id=r["assignment_id"],
        year_group=r["year_group"], form_group=r["form_group"],
        academic_year=r["academic_year"],
        tutor_name=r["tutor_name"], role=r["role"],
        contact_email=r["contact_email"],
        start_date=r["start_date"], end_date=r["end_date"],
        status=r["status"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_meeting(r: sqlite3.Row) -> TutorMeeting:
    keys = r.keys()
    return TutorMeeting(
        meeting_id=r["meeting_id"],
        assignment_id=r["assignment_id"],
        meeting_date=r["meeting_date"],
        meeting_type=r["meeting_type"],
        pupils_present=r["pupils_present"],
        agenda=r["agenda"], decisions=r["decisions"],
        follow_up_actions=r["follow_up_actions"],
        notes=r["notes"],
        tutor_name=r["tutor_name"] if "tutor_name" in keys else None,
        year_group=r["year_group"] if "year_group" in keys else None,
        form_group=r["form_group"] if "form_group" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str, *,
                   required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            return _dt.date.today().isoformat()
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_assignment(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    yg = (data.get("year_group") or "").strip()
    if not yg:
        raise ValidationError("Year group is required")
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(YEAR_GROUPS)}")
    out["year_group"] = yg

    fg = (data.get("form_group") or "").strip()
    if not fg:
        raise ValidationError("Form group is required")
    if len(fg) > 16:
        raise ValidationError("Form group must be 16 chars or fewer")
    out["form_group"] = fg

    ay = (data.get("academic_year") or "").strip()
    if not ay:
        raise ValidationError("Academic year is required (e.g. 2025/26)")
    if not _AY_RE.match(ay):
        raise ValidationError(
            "Academic year must be in form YYYY/YY (e.g. 2025/26)")
    out["academic_year"] = ay

    tutor = (data.get("tutor_name") or "").strip()
    if not tutor:
        raise ValidationError("Tutor name is required")
    if len(tutor) > 64:
        raise ValidationError("Tutor name must be 64 chars or fewer")
    out["tutor_name"] = tutor

    role = (data.get("role") or DEFAULT_ROLE).strip()
    if role not in ROLES:
        raise ValidationError(
            f"Role must be one of {', '.join(ROLES)}")
    out["role"] = role

    email = (data.get("contact_email") or "").strip()
    if email and not _EMAIL_RE.match(email):
        raise ValidationError("Contact email is not a valid address")
    out["contact_email"] = email or None

    out["start_date"] = _validate_date(data.get("start_date"),
                                         "Start date")
    out["end_date"]   = _validate_date(data.get("end_date"),
                                         "End date", required=False)
    if out["end_date"] and out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")

    status = (data.get("status") or DEFAULT_ASSIGNMENT_STATUS).strip()
    if status not in ASSIGNMENT_STATUSES:
        raise ValidationError(
            f"Status must be one of "
            f"{', '.join(ASSIGNMENT_STATUSES)}")
    out["status"] = status
    out["notes"]  = (data.get("notes") or "").strip() or None
    return out


def _validate_meeting(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    aid_raw = data.get("assignment_id")
    if aid_raw in (None, ""):
        raise ValidationError("Assignment ID is required")
    try:
        out["assignment_id"] = int(aid_raw)
    except (TypeError, ValueError):
        raise ValidationError(
            "Assignment ID must be a number") from None

    out["meeting_date"] = _validate_date(data.get("meeting_date"),
                                           "Meeting date")
    mtype = (data.get("meeting_type") or DEFAULT_MEETING_TYPE).strip()
    if mtype not in MEETING_TYPES:
        raise ValidationError(
            f"Meeting type must be one of "
            f"{', '.join(MEETING_TYPES)}")
    out["meeting_type"] = mtype

    out["pupils_present"]    = (data.get("pupils_present") or "").strip() or None
    out["agenda"]            = (data.get("agenda") or "").strip() or None
    out["decisions"]         = (data.get("decisions") or "").strip() or None
    out["follow_up_actions"] = (data.get("follow_up_actions") or "").strip() or None
    out["notes"]             = (data.get("notes") or "").strip() or None
    return out


# ── Assignment CRUD ─────────────────────────────────────────────

def create_assignment(data: dict[str, Any]) -> TutorAssignment:
    init_db()
    payload = _validate_assignment(data)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT assignment_id FROM form_tutor_assignments "
                "WHERE year_group = ? AND form_group = ? "
                "  AND academic_year = ? AND tutor_name = ? AND role = ?",
                (payload["year_group"], payload["form_group"],
                 payload["academic_year"], payload["tutor_name"],
                 payload["role"]),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"{payload['tutor_name']} is already assigned as "
                    f"{payload['role']} for Yr{payload['year_group']}/"
                    f"{payload['form_group']} in "
                    f"{payload['academic_year']}")
            cur = conn.execute(
                """INSERT INTO form_tutor_assignments
                       (year_group, form_group, academic_year,
                        tutor_name, role, contact_email,
                        start_date, end_date, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["year_group"], payload["form_group"],
                 payload["academic_year"], payload["tutor_name"],
                 payload["role"], payload["contact_email"],
                 payload["start_date"], payload["end_date"],
                 payload["status"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create tutor assignment")
        raise
    rec = get_assignment(new_id)
    assert rec is not None
    logger.info(
        "Created tutor assignment #%d Yr%s/%s %s — %s (%s, %s)",
        rec.assignment_id, rec.year_group, rec.form_group,
        rec.academic_year, rec.tutor_name, rec.role, rec.status)
    return rec


def get_assignment(assignment_id: int) -> TutorAssignment | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM form_tutor_assignments "
                "WHERE assignment_id = ?",
                (assignment_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_assignment(%s) failed", assignment_id)
        raise
    return _row_assignment(r) if r else None


def list_assignments(*, year_group: str | None = None,
                     form_group: str | None = None,
                     academic_year: str | None = None,
                     tutor_name: str | None = None,
                     status: str | None = None,
                     role: str | None = None
                     ) -> list[TutorAssignment]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("year_group = ?")
        params.append(year_group)
    if form_group:
        where.append("form_group = ?")
        params.append(form_group.strip())
    if academic_year:
        where.append("academic_year = ?")
        params.append(academic_year.strip())
    if tutor_name:
        where.append("tutor_name = ?")
        params.append(tutor_name.strip())
    if status:
        if status not in ASSIGNMENT_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(ASSIGNMENT_STATUSES)}")
        where.append("status = ?")
        params.append(status)
    if role:
        if role not in ROLES:
            raise ValidationError(
                f"Role filter must be one of {', '.join(ROLES)}")
        where.append("role = ?")
        params.append(role)
    sql = "SELECT * FROM form_tutor_assignments"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY academic_year DESC, year_group, form_group, "
            "role, tutor_name")
    try:
        with _connect() as conn:
            return [_row_assignment(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_assignments failed")
        raise


def update_assignment(assignment_id: int,
                      data: dict[str, Any]) -> TutorAssignment:
    init_db()
    existing = get_assignment(assignment_id)
    if existing is None:
        raise ValidationError(
            f"No tutor assignment #{assignment_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("year_group", "form_group", "academic_year",
                         "tutor_name", "role", "contact_email",
                         "start_date", "end_date", "status", "notes")}
    payload = _validate_assignment(merged)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT assignment_id FROM form_tutor_assignments "
                "WHERE year_group = ? AND form_group = ? "
                "  AND academic_year = ? AND tutor_name = ? AND role = ? "
                "  AND assignment_id <> ?",
                (payload["year_group"], payload["form_group"],
                 payload["academic_year"], payload["tutor_name"],
                 payload["role"], assignment_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    "Another assignment with the same year/form/year/"
                    "tutor/role already exists")
            conn.execute(
                """UPDATE form_tutor_assignments SET
                       year_group = ?, form_group = ?,
                       academic_year = ?, tutor_name = ?, role = ?,
                       contact_email = ?, start_date = ?, end_date = ?,
                       status = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE assignment_id = ?""",
                (payload["year_group"], payload["form_group"],
                 payload["academic_year"], payload["tutor_name"],
                 payload["role"], payload["contact_email"],
                 payload["start_date"], payload["end_date"],
                 payload["status"], payload["notes"], assignment_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to update tutor assignment #%d", assignment_id)
        raise
    rec = get_assignment(assignment_id)
    assert rec is not None
    logger.info("Updated tutor assignment #%d (status %s)",
                rec.assignment_id, rec.status)
    return rec


def end_assignment(assignment_id: int,
                    end_date: str | None = None) -> TutorAssignment:
    return update_assignment(assignment_id, {
        "status": "Ended",
        "end_date": end_date or _dt.date.today().isoformat(),
    })


def delete_assignment(assignment_id: int) -> bool:
    init_db()
    existing = get_assignment(assignment_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM form_tutor_assignments "
                "WHERE assignment_id = ?", (assignment_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete tutor assignment #%d", assignment_id)
        raise
    if deleted:
        logger.info("Deleted tutor assignment #%d "
                    "(cascade: meetings)",
                    assignment_id)
    return deleted


# ── Meetings ────────────────────────────────────────────────────

def add_meeting(data: dict[str, Any]) -> TutorMeeting:
    init_db()
    payload = _validate_meeting(data)
    if get_assignment(payload["assignment_id"]) is None:
        raise ValidationError(
            f"No tutor assignment #{payload['assignment_id']}")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO form_tutor_meetings
                       (assignment_id, meeting_date, meeting_type,
                        pupils_present, agenda, decisions,
                        follow_up_actions, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["assignment_id"], payload["meeting_date"],
                 payload["meeting_type"], payload["pupils_present"],
                 payload["agenda"], payload["decisions"],
                 payload["follow_up_actions"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception(
            "Failed to add meeting to assignment %d",
            payload["assignment_id"])
        raise
    logger.info("Added meeting #%d to assignment #%d (%s, %s)",
                new_id, payload["assignment_id"],
                payload["meeting_date"], payload["meeting_type"])
    rec = get_meeting(new_id)
    assert rec is not None
    return rec


def get_meeting(meeting_id: int) -> TutorMeeting | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT m.*,
                          a.tutor_name AS tutor_name,
                          a.year_group AS year_group,
                          a.form_group AS form_group
                   FROM form_tutor_meetings m
                   LEFT JOIN form_tutor_assignments a
                     ON a.assignment_id = m.assignment_id
                   WHERE m.meeting_id = ?""",
                (meeting_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_meeting(%s) failed", meeting_id)
        raise
    return _row_meeting(r) if r else None


def list_meetings(*, assignment_id: int | None = None,
                  meeting_type: str | None = None,
                  date_from: str | None = None,
                  date_to: str | None = None) -> list[TutorMeeting]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if assignment_id is not None:
        where.append("m.assignment_id = ?")
        params.append(int(assignment_id))
    if meeting_type:
        if meeting_type not in MEETING_TYPES:
            raise ValidationError(
                f"Type filter must be one of "
                f"{', '.join(MEETING_TYPES)}")
        where.append("m.meeting_type = ?")
        params.append(meeting_type)
    if date_from:
        where.append("m.meeting_date >= ?")
        params.append(_validate_date(date_from, "From date"))
    if date_to:
        where.append("m.meeting_date <= ?")
        params.append(_validate_date(date_to, "To date"))
    sql = ("""SELECT m.*,
                     a.tutor_name AS tutor_name,
                     a.year_group AS year_group,
                     a.form_group AS form_group
              FROM form_tutor_meetings m
              LEFT JOIN form_tutor_assignments a
                ON a.assignment_id = m.assignment_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY m.meeting_date DESC, m.meeting_id DESC"
    try:
        with _connect() as conn:
            return [_row_meeting(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_meetings failed")
        raise


def update_meeting(meeting_id: int,
                   data: dict[str, Any]) -> TutorMeeting:
    init_db()
    existing = get_meeting(meeting_id)
    if existing is None:
        raise ValidationError(f"No meeting #{meeting_id}")
    merged = {
        "assignment_id":     existing.assignment_id,
        "meeting_date":      data.get("meeting_date",
                                        existing.meeting_date),
        "meeting_type":      data.get("meeting_type",
                                        existing.meeting_type),
        "pupils_present":    data.get("pupils_present",
                                        existing.pupils_present),
        "agenda":            data.get("agenda", existing.agenda),
        "decisions":         data.get("decisions",
                                        existing.decisions),
        "follow_up_actions": data.get("follow_up_actions",
                                        existing.follow_up_actions),
        "notes":             data.get("notes", existing.notes),
    }
    payload = _validate_meeting(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE form_tutor_meetings SET
                       meeting_date = ?, meeting_type = ?,
                       pupils_present = ?, agenda = ?,
                       decisions = ?, follow_up_actions = ?,
                       notes = ?, updated_at = datetime('now')
                   WHERE meeting_id = ?""",
                (payload["meeting_date"], payload["meeting_type"],
                 payload["pupils_present"], payload["agenda"],
                 payload["decisions"], payload["follow_up_actions"],
                 payload["notes"], meeting_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update meeting #%d", meeting_id)
        raise
    rec = get_meeting(meeting_id)
    assert rec is not None
    logger.info("Updated tutor meeting #%d", rec.meeting_id)
    return rec


def delete_meeting(meeting_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM form_tutor_meetings WHERE meeting_id = ?",
                (meeting_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete meeting #%d", meeting_id)
        raise
    if deleted:
        logger.info("Deleted tutor meeting #%d", meeting_id)
    return deleted


def assignment_summary(assignment_id: int) -> dict[str, Any]:
    init_db()
    rec = get_assignment(assignment_id)
    if rec is None:
        raise ValidationError(
            f"No tutor assignment #{assignment_id}")
    meetings = list_meetings(assignment_id=assignment_id)
    return {
        "assignment":   rec,
        "meetings":     meetings,
        "meeting_count": len(meetings),
        "by_type":      dict(Counter(m.meeting_type
                                       for m in meetings)),
    }


def cohort_summary(*, academic_year: str | None = None
                   ) -> dict[str, Any]:
    rows = list_assignments(academic_year=academic_year)
    return {
        "total":      len(rows),
        "by_status":  dict(Counter(r.status for r in rows)),
        "by_role":    dict(Counter(r.role for r in rows)),
        "by_year":    dict(Counter(r.year_group for r in rows)),
        "tutors":     len({r.tutor_name for r in rows}),
        "forms":      len({(r.year_group, r.form_group) for r in rows}),
    }
