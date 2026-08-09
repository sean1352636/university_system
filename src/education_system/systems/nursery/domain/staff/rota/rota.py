"""Domain layer for Staff Rota (Nursery System).

Owns the ``rota_shifts`` table — staff shift scheduling. One row per shift,
attached to a staff member, with a date, start/end time, the room they're
deployed to and a scheduled → confirmed → cancelled workflow. The Staff:Child
Ratios board reads confirmed/scheduled shifts to see who is on duty.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``rota_cli.py``, Tk GUI in ``rota_views.py``.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Staff Rota"
CATEGORY = "Staff & Ratios"

ID_PREFIX = "NRS"
ID_DIGITS = 3

STATUSES = ("scheduled", "confirmed", "cancelled")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


class ValidationError(ValueError):
    """Raised for invalid rota-shift input."""


@dataclass
class Shift:
    shift_id: str
    staff_id: str
    shift_date: str | None
    start_time: str | None
    end_time: str | None
    room: str | None
    role: str | None
    status: str
    notes: str | None
    staff_name: str | None = None

    @property
    def time_span(self) -> str:
        if self.start_time and self.end_time:
            return f"{self.start_time}–{self.end_time}"
        return self.start_time or self.end_time or "-"


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for rota")
        raise


_SELECT = """
SELECT r.*,
       TRIM(s.first_name || ' ' || s.last_name) AS staff_name
FROM rota_shifts r
LEFT JOIN staff s ON s.staff_id = r.staff_id
"""


def _row(r: sqlite3.Row) -> Shift:
    keys = r.keys()
    return Shift(
        shift_id=r["shift_id"],
        staff_id=r["staff_id"],
        shift_date=r["shift_date"],
        start_time=r["start_time"],
        end_time=r["end_time"],
        room=r["room"],
        role=r["role"],
        status=r["status"],
        notes=r["notes"],
        staff_name=r["staff_name"] if "staff_name" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _require(value: str | None, label: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _opt_date(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if v and not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v or None


def _opt_time(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if v and not _TIME_RE.match(v):
        raise ValidationError(f"{label} must be HH:MM (24-hour)")
    return v or None


def _validate(data: dict[str, Any], *, require_staff: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_staff:
        out["staff_id"] = _require(data.get("staff_id"), "Staff member")
    out["shift_date"] = _opt_date(data.get("shift_date"), "Shift date")
    out["start_time"] = _opt_time(data.get("start_time"), "Start time")
    out["end_time"] = _opt_time(data.get("end_time"), "End time")
    if out["start_time"] and out["end_time"] and out["end_time"] <= out["start_time"]:
        raise ValidationError("End time must be after start time")
    out["room"] = _opt(data.get("room"))
    out["role"] = _opt(data.get("role"))
    out["notes"] = _opt(data.get("notes"))
    status = (data.get("status") or "scheduled").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_shift_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT shift_id FROM rota_shifts").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing shift ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        sid = f"{ID_PREFIX}{n}"
        if sid not in existing:
            return sid
    raise RuntimeError("Could not allocate a unique shift id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_shifts(*, shift_date: str | None = None,
                staff_id: str | None = None,
                include_cancelled: bool = True) -> list[Shift]:
    _ensure_schema()
    sql = _SELECT
    clauses: list[str] = []
    params: list[Any] = []
    if shift_date:
        clauses.append("r.shift_date = ?")
        params.append(shift_date)
    if staff_id:
        clauses.append("r.staff_id = ?")
        params.append(staff_id)
    if not include_cancelled:
        clauses.append("r.status != 'cancelled'")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY r.shift_date, r.start_time, staff_name"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_shifts failed")
        raise
    return [_row(r) for r in rows]


def get_shift(shift_id: str) -> Shift | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE r.shift_id = ?", (shift_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_shift(%s) failed", shift_id)
        raise
    return _row(row) if row else None


def list_dates() -> list[str]:
    """Distinct shift dates present, most recent first — for date pickers."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT shift_date FROM rota_shifts "
                "WHERE shift_date IS NOT NULL ORDER BY shift_date DESC").fetchall()
    except sqlite3.Error:
        logger.exception("list_dates failed")
        raise
    return [r[0] for r in rows]


def list_staff_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name, role FROM staff "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    out = []
    for r in rows:
        role = f" — {r['role']}" if r["role"] else ""
        out.append((r["staff_id"],
                    f"{r['first_name']} {r['last_name']} ({r['staff_id']}){role}"))
    return out


def list_room_choices() -> list[str]:
    try:
        from education_system.systems.nursery.domain.operations.rooms import rooms
        return rooms.list_room_choices()
    except Exception:
        logger.exception("Could not load room choices for rota")
        return []


# ── Writes ───────────────────────────────────────────────────────────────────

def create_shift(data: dict[str, Any]) -> Shift:
    _ensure_schema()
    payload = _validate(data, require_staff=True)
    sid = generate_shift_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM staff WHERE staff_id = ?",
                                (payload["staff_id"],)).fetchone():
                raise ValidationError(
                    f"No staff member with id {payload['staff_id']}")
            conn.execute(
                """
                INSERT INTO rota_shifts (
                    shift_id, staff_id, shift_date, start_time, end_time,
                    room, role, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sid, payload["staff_id"], payload["shift_date"],
                 payload["start_time"], payload["end_time"], payload["room"],
                 payload["role"], payload["status"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for shift id=%s", sid)
        raise ValidationError(f"Could not create shift — {e}") from e
    shift = get_shift(sid)
    assert shift is not None
    logger.info("Created rota shift %s for staff %s", sid, payload["staff_id"])
    return shift


def update_shift(shift_id: str, data: dict[str, Any]) -> Shift:
    _ensure_schema()
    payload = _validate(data, require_staff=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE rota_shifts SET
                    shift_date = ?, start_time = ?, end_time = ?, room = ?,
                    role = ?, status = ?, notes = ?
                WHERE shift_id = ?
                """,
                (payload["shift_date"], payload["start_time"],
                 payload["end_time"], payload["room"], payload["role"],
                 payload["status"], payload["notes"], shift_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No shift with id {shift_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for shift id=%s", shift_id)
        raise ValidationError(f"Could not update shift — {e}") from e
    shift = get_shift(shift_id)
    assert shift is not None
    logger.info("Updated rota shift %s", shift_id)
    return shift


def delete_shift(shift_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM rota_shifts WHERE shift_id = ?", (shift_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting shift id=%s", shift_id)
        raise
    if deleted:
        logger.info("Deleted rota shift %s", shift_id)
    return deleted


def set_status(shift_id: str, status: str) -> Shift:
    _ensure_schema()
    status = (status or "").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE rota_shifts SET status = ? WHERE shift_id = ?",
                (status, shift_id))
            if cur.rowcount == 0:
                raise ValidationError(f"No shift with id {shift_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Database error setting status for shift %s", shift_id)
        raise
    shift = get_shift(shift_id)
    assert shift is not None
    return shift
