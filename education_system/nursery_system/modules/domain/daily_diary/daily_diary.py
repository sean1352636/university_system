"""Domain layer for Daily Diary (Nursery System).

Owns the ``daily_diary`` table — the staff diary of a child's day: mood,
activities, highlights and free-text notes, with one row per child per day.
This is the fuller practitioner record behind the parent-facing daily updates.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``daily_diary_cli.py``, Tk GUI in ``daily_diary_views.py``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Daily Diary"
CATEGORY = "Daily Care & Routines"

ID_PREFIX = "NDD"
ID_DIGITS = 3

MOODS = ("Happy", "Settled", "Tired", "Upset", "Unwell")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid daily-diary input."""


@dataclass
class DiaryEntry:
    entry_id: str
    pupil_id: str
    entry_date: str
    mood: str | None
    activities: str | None
    highlights: str | None
    notes: str | None
    staff_id: str | None
    child_name: str | None = None
    staff_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for daily diary")
        raise


_SELECT = """
SELECT d.entry_id, d.pupil_id, d.entry_date, d.mood, d.activities,
       d.highlights, d.notes, d.staff_id,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       TRIM(s.first_name || ' ' || s.last_name) AS staff_name
FROM daily_diary d
LEFT JOIN pupils p ON p.pupil_id = d.pupil_id
LEFT JOIN staff  s ON s.staff_id = d.staff_id
"""


def _row(r: sqlite3.Row) -> DiaryEntry:
    keys = r.keys()
    return DiaryEntry(
        entry_id=r["entry_id"],
        pupil_id=r["pupil_id"],
        entry_date=r["entry_date"],
        mood=r["mood"],
        activities=r["activities"],
        highlights=r["highlights"],
        notes=r["notes"],
        staff_id=r["staff_id"],
        child_name=r["child_name"] if "child_name" in keys else None,
        staff_name=r["staff_name"] if "staff_name" in keys else None,
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

    entry_date = (data.get("entry_date") or "").strip()
    if not entry_date:
        entry_date = _dt.date.today().isoformat()
    if not _DATE_RE.match(entry_date):
        raise ValidationError("Entry date must be YYYY-MM-DD")
    out["entry_date"] = entry_date

    out["mood"] = _opt(data.get("mood"))
    out["activities"] = _opt(data.get("activities"))
    out["highlights"] = _opt(data.get("highlights"))
    out["notes"] = _opt(data.get("notes"))
    out["staff_id"] = _opt(data.get("staff_id"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_record_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT entry_id FROM daily_diary").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing daily-diary ids")
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
    raise RuntimeError("Could not allocate a unique daily-diary id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_records(*, entry_date: str | None = None,
                 pupil_id: str | None = None) -> list[DiaryEntry]:
    _ensure_schema()
    sql = _SELECT
    clauses: list[str] = []
    params: list[Any] = []
    if entry_date:
        clauses.append("d.entry_date = ?")
        params.append(entry_date.strip())
    if pupil_id:
        clauses.append("d.pupil_id = ?")
        params.append(pupil_id.strip())
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY d.entry_date DESC, d.entry_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    return [_row(r) for r in rows]


def get_record(entry_id: str) -> DiaryEntry | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE d.entry_id = ?", (entry_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_record(%s) failed", entry_id)
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
    """Return ``(staff_id, "Name (id) — role")`` pairs for staff pickers."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name, role FROM staff "
                "WHERE end_date IS NULL OR end_date = '' "
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


# ── Writes ───────────────────────────────────────────────────────────────────

def create_record(data: dict[str, Any]) -> DiaryEntry:
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
                INSERT INTO daily_diary (
                    entry_id, pupil_id, entry_date, mood, activities,
                    highlights, notes, staff_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["pupil_id"], payload["entry_date"], payload["mood"],
                 payload["activities"], payload["highlights"], payload["notes"],
                 payload["staff_id"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for daily-diary id=%s", rid)
        raise ValidationError(f"Could not create entry — {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created daily-diary entry %s for pupil %s (%s)",
                rid, payload["pupil_id"], payload["entry_date"])
    return rec


def update_record(entry_id: str, data: dict[str, Any]) -> DiaryEntry:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_record(entry_id)
    if existing is None:
        raise ValidationError(f"No daily-diary entry with id {entry_id}")
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE daily_diary SET
                    entry_date = ?, mood = ?, activities = ?, highlights = ?,
                    notes = ?, staff_id = ?
                WHERE entry_id = ?
                """,
                (payload["entry_date"], payload["mood"], payload["activities"],
                 payload["highlights"], payload["notes"], payload["staff_id"],
                 entry_id),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for daily-diary id=%s", entry_id)
        raise ValidationError(f"Could not update entry — {e}") from e
    rec = get_record(entry_id)
    assert rec is not None
    logger.info("Updated daily-diary entry %s", entry_id)
    return rec


def delete_record(entry_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM daily_diary WHERE entry_id = ?", (entry_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting daily-diary id=%s", entry_id)
        raise
    if deleted:
        logger.info("Deleted daily-diary entry %s", entry_id)
    return deleted
