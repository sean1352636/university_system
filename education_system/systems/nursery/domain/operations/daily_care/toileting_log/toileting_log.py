"""Domain layer for the Nappy / Toileting Log (Nursery System).

Owns the ``toileting_log`` table — one row per nappy change, toilet visit,
potty use or accident for a child. Records the date and time, the type of
event, whether barrier cream was applied, the staff member who dealt with it
and any notes, so the setting can evidence personal-care routines and share
them with parents.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``toileting_log_cli.py``, Tk GUI in ``toileting_log_views.py``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Nappy / Toileting Log"
CATEGORY = "Daily Care & Routines"

ID_PREFIX = "NTL"
ID_DIGITS = 3

TYPES = (
    "nappy - wet",
    "nappy - soiled",
    "nappy - dry",
    "toilet",
    "potty",
    "accident",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid toileting-log input."""


@dataclass
class ToiletingRecord:
    record_id: str
    pupil_id: str
    log_date: str
    log_time: str | None
    type: str
    cream_applied: int
    staff_id: str | None
    notes: str | None
    child_name: str | None = None
    staff_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for toileting log")
        raise


_SELECT = """
SELECT t.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       TRIM(s.first_name || ' ' || s.last_name) AS staff_name
FROM toileting_log t
LEFT JOIN pupils p ON p.pupil_id = t.pupil_id
LEFT JOIN staff  s ON s.staff_id = t.staff_id
"""


def _row(r: sqlite3.Row) -> ToiletingRecord:
    keys = r.keys()
    return ToiletingRecord(
        record_id=r["record_id"],
        pupil_id=r["pupil_id"],
        log_date=r["log_date"],
        log_time=r["log_time"],
        type=r["type"],
        cream_applied=int(r["cream_applied"] or 0),
        staff_id=r["staff_id"],
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        staff_name=r["staff_name"] if "staff_name" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _coerce_bool(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return int(bool(value))
    return int(str(value or "").strip().lower() in ("1", "y", "yes", "true", "on"))


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    log_date = (data.get("log_date") or "").strip() or _dt.date.today().isoformat()
    if not _DATE_RE.match(log_date):
        raise ValidationError("Date must be YYYY-MM-DD")
    out["log_date"] = log_date

    log_time = (data.get("log_time") or "").strip()
    if log_time and not _TIME_RE.match(log_time):
        raise ValidationError("Time must be HH:MM")
    out["log_time"] = log_time or None

    rtype = (data.get("type") or "").strip() or "nappy - wet"
    if rtype not in TYPES:
        raise ValidationError("Type must be one of: " + ", ".join(TYPES))
    out["type"] = rtype

    out["cream_applied"] = _coerce_bool(data.get("cream_applied"))
    out["staff_id"] = _opt(data.get("staff_id"))
    out["notes"] = _opt(data.get("notes"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_record_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT record_id FROM toileting_log").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing toileting-log ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        rid = f"{ID_PREFIX}{n}"
        if rid not in existing:
            return rid
    raise RuntimeError("Could not allocate a unique toileting-log id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_records(*, log_date: str | None = None, pupil_id: str | None = None,
                 type: str | None = None) -> list[ToiletingRecord]:
    _ensure_schema()
    sql = _SELECT
    clauses: list[str] = []
    params: list[Any] = []
    if log_date:
        clauses.append("t.log_date = ?")
        params.append(log_date.strip())
    if pupil_id:
        clauses.append("t.pupil_id = ?")
        params.append(pupil_id.strip())
    if type:
        clauses.append("t.type = ?")
        params.append(type.strip())
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY t.log_date DESC, t.log_time DESC, t.record_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    return [_row(r) for r in rows]


def get_record(record_id: str) -> ToiletingRecord | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE t.record_id = ?", (record_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_record(%s) failed", record_id)
        raise
    return _row(row) if row else None


def list_pupil_choices() -> list[tuple[str, str]]:
    """Return ``(pupil_id, "Name (id) — room")`` pairs for child pickers."""
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
    """Return ``(staff_id, "Name (id)")`` pairs for currently-employed staff."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name FROM staff "
                "WHERE end_date IS NULL OR end_date = '' "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    return [(r["staff_id"], f"{r['first_name']} {r['last_name']} ({r['staff_id']})")
            for r in rows]


# ── Writes ───────────────────────────────────────────────────────────────────

def create_record(data: dict[str, Any]) -> ToiletingRecord:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    rid = generate_record_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO toileting_log (
                    record_id, pupil_id, log_date, log_time, type,
                    cream_applied, staff_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["pupil_id"], payload["log_date"],
                 payload["log_time"], payload["type"], payload["cream_applied"],
                 payload["staff_id"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for toileting-log id=%s", rid)
        raise ValidationError(f"Could not create record — {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created toileting-log record %s for pupil %s (%s)",
                rid, payload["pupil_id"], payload["type"])
    return rec


def update_record(record_id: str, data: dict[str, Any]) -> ToiletingRecord:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_record(record_id)
    if existing is None:
        raise ValidationError(f"No toileting-log record with id {record_id}")
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE toileting_log SET
                    log_date = ?, log_time = ?, type = ?, cream_applied = ?,
                    staff_id = ?, notes = ?
                WHERE record_id = ?
                """,
                (payload["log_date"], payload["log_time"], payload["type"],
                 payload["cream_applied"], payload["staff_id"],
                 payload["notes"], record_id),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for toileting-log id=%s", record_id)
        raise ValidationError(f"Could not update record — {e}") from e
    rec = get_record(record_id)
    assert rec is not None
    logger.info("Updated toileting-log record %s", record_id)
    return rec


def delete_record(record_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM toileting_log WHERE record_id = ?", (record_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting toileting-log id=%s", record_id)
        raise
    if deleted:
        logger.info("Deleted toileting-log record %s", record_id)
    return deleted
