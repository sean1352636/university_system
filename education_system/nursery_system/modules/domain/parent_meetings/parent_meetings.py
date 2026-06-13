"""Domain layer for Parent Meetings (Nursery System).

Owns the ``parent_meetings`` table — scheduled meetings / consultations between
nursery staff and a child's parents (e.g. settling reviews, progress meetings,
2-year checks, parents' evenings).

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``parent_meetings_cli.py``, Tk GUI in ``parent_meetings_views.py``.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Parent Meetings"
CATEGORY = "Parents & Communication"

ID_PREFIX = "NPM"
ID_DIGITS = 3

MEETING_TYPES = (
    "Settling review",
    "Progress meeting",
    "2-year progress check",
    "Concern",
    "Parents' evening",
    "Transition planning",
    "Other",
)

STATUSES = ("scheduled", "completed", "cancelled")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid parent-meetings input."""


@dataclass
class Meeting:
    meeting_id: str
    pupil_id: str
    meeting_date: str | None
    meeting_time: str | None
    meeting_type: str | None
    staff_id: str | None
    location: str | None
    status: str
    summary: str | None
    notes: str | None
    created_at: str | None
    child_name: str | None = None
    room: str | None = None
    staff_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for parent meetings")
        raise


_SELECT = """
SELECT pm.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS staff_name
FROM parent_meetings pm
LEFT JOIN pupils p ON p.pupil_id = pm.pupil_id
LEFT JOIN staff s ON s.staff_id = pm.staff_id
"""


def _row(r: sqlite3.Row) -> Meeting:
    keys = r.keys()
    return Meeting(
        meeting_id=r["meeting_id"],
        pupil_id=r["pupil_id"],
        meeting_date=r["meeting_date"],
        meeting_time=r["meeting_time"],
        meeting_type=r["meeting_type"],
        staff_id=r["staff_id"],
        location=r["location"],
        status=r["status"],
        summary=r["summary"],
        notes=r["notes"],
        created_at=r["created_at"] if "created_at" in keys else None,
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
        staff_name=(r["staff_name"] or None) if "staff_name" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    date_val = (data.get("meeting_date") or "").strip()
    if date_val and not _DATE_RE.match(date_val):
        raise ValidationError("Meeting date must be YYYY-MM-DD")
    out["meeting_date"] = date_val or None

    time_val = (data.get("meeting_time") or "").strip()
    if time_val and not _TIME_RE.match(time_val):
        raise ValidationError("Meeting time must be HH:MM (e.g. 15:30)")
    out["meeting_time"] = time_val or None

    mtype = (data.get("meeting_type") or "").strip()
    if mtype and mtype not in MEETING_TYPES:
        raise ValidationError(
            "Meeting type must be one of: " + ", ".join(MEETING_TYPES))
    out["meeting_type"] = mtype or None

    out["staff_id"] = _opt(data.get("staff_id"))
    out["location"] = _opt(data.get("location"))

    status = (data.get("status") or "scheduled").strip()
    if status not in STATUSES:
        raise ValidationError("Status must be one of: " + ", ".join(STATUSES))
    out["status"] = status

    out["summary"] = _opt(data.get("summary"))
    out["notes"] = _opt(data.get("notes"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_meeting_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT meeting_id FROM parent_meetings").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing parent-meeting ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        mid = f"{ID_PREFIX}{n}"
        if mid not in existing:
            return mid
    raise RuntimeError("Could not allocate a unique parent-meeting id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_meetings(*, pupil_id: str | None = None) -> list[Meeting]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if pupil_id:
        sql += " WHERE pm.pupil_id = ?"
        params.append(pupil_id)
    sql += " ORDER BY pm.meeting_date DESC, pm.meeting_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_meetings failed")
        raise
    return [_row(r) for r in rows]


def get_meeting(meeting_id: str) -> Meeting | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE pm.meeting_id = ?", (meeting_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_meeting(%s) failed", meeting_id)
        raise
    return _row(row) if row else None


def list_pupil_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id, first_name, last_name, room FROM pupils "
                "WHERE status = 'active' ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_pupil_choices failed")
        raise
    out = []
    for r in rows:
        room = f" — {r['room']}" if r["room"] else ""
        out.append((r["pupil_id"],
                    f"{r['first_name']} {r['last_name']} ({r['pupil_id']}){room}"))
    return out


def list_staff_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name FROM staff "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    return [(r["staff_id"], f"{r['first_name']} {r['last_name']} ({r['staff_id']})")
            for r in rows]


# ── Writes ───────────────────────────────────────────────────────────────────

def create_meeting(data: dict[str, Any]) -> Meeting:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    mid = generate_meeting_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO parent_meetings (
                    meeting_id, pupil_id, meeting_date, meeting_time, meeting_type,
                    staff_id, location, status, summary, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (mid, payload["pupil_id"], payload["meeting_date"],
                 payload["meeting_time"], payload["meeting_type"],
                 payload["staff_id"], payload["location"], payload["status"],
                 payload["summary"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for parent-meeting id=%s", mid)
        raise ValidationError(f"Could not create meeting — {e}") from e
    m = get_meeting(mid)
    assert m is not None
    logger.info("Created parent meeting %s for pupil %s", mid, payload["pupil_id"])
    return m


def update_meeting(meeting_id: str, data: dict[str, Any]) -> Meeting:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    if get_meeting(meeting_id) is None:
        raise ValidationError(f"No parent meeting with id {meeting_id}")
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE parent_meetings SET
                    meeting_date = ?, meeting_time = ?, meeting_type = ?,
                    staff_id = ?, location = ?, status = ?, summary = ?, notes = ?
                WHERE meeting_id = ?
                """,
                (payload["meeting_date"], payload["meeting_time"],
                 payload["meeting_type"], payload["staff_id"],
                 payload["location"], payload["status"],
                 payload["summary"], payload["notes"], meeting_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No parent meeting with id {meeting_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for parent-meeting id=%s", meeting_id)
        raise ValidationError(f"Could not update meeting — {e}") from e
    m = get_meeting(meeting_id)
    assert m is not None
    logger.info("Updated parent meeting %s", meeting_id)
    return m


def delete_meeting(meeting_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM parent_meetings WHERE meeting_id = ?", (meeting_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting parent-meeting id=%s", meeting_id)
        raise
    if deleted:
        logger.info("Deleted parent meeting %s", meeting_id)
    return deleted
