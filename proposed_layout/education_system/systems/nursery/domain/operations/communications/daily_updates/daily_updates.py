"""Domain layer for Daily Updates (Nursery System).

Owns the ``daily_updates`` table — the at-a-glance "how was my child's day"
summary shared with parents. Each row records the date, the child's mood,
meals, sleep, nappies, activities, and free-text notes, plus a flag indicating
whether the update has been shared with the parent.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``daily_updates_cli.py``, Tk GUI in ``daily_updates_views.py``.
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

FEATURE_NAME = "Daily Updates"
CATEGORY = "Parents & Communication"

ID_PREFIX = "NDU"
ID_DIGITS = 3

MOODS = ("Happy", "Settled", "Tired", "Unsettled", "Upset", "Poorly")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid daily-update input."""


@dataclass
class DailyUpdate:
    update_id: str
    pupil_id: str
    update_date: str | None
    mood: str | None
    meals: str | None
    sleep: str | None
    nappies: str | None
    activities: str | None
    notes: str | None
    staff_id: str | None
    shared: bool
    created_at: str | None = None
    child_name: str | None = None
    room: str | None = None
    staff_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for daily updates")
        raise


_SELECT = """
SELECT du.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS staff_name
FROM daily_updates du
LEFT JOIN pupils p ON p.pupil_id = du.pupil_id
LEFT JOIN staff s ON s.staff_id = du.staff_id
"""


def _row(r: sqlite3.Row) -> DailyUpdate:
    keys = r.keys()
    return DailyUpdate(
        update_id=r["update_id"],
        pupil_id=r["pupil_id"],
        update_date=r["update_date"],
        mood=r["mood"],
        meals=r["meals"],
        sleep=r["sleep"],
        nappies=r["nappies"],
        activities=r["activities"],
        notes=r["notes"],
        staff_id=r["staff_id"],
        shared=bool(r["shared"]),
        created_at=r["created_at"] if "created_at" in keys else None,
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
        staff_name=(r["staff_name"] or None) if "staff_name" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _opt_date(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if v and not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v or None


def _as_bool(value: Any) -> int:
    if isinstance(value, str):
        return 1 if value.strip().lower() in ("1", "y", "yes", "true", "on") else 0
    return 1 if value else 0


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    out["update_date"] = _opt_date(data.get("update_date"), "Update date")

    mood = (data.get("mood") or "").strip()
    if mood and mood not in MOODS:
        raise ValidationError("Mood must be one of: " + ", ".join(MOODS))
    out["mood"] = mood or None

    out["meals"] = _opt(data.get("meals"))
    out["sleep"] = _opt(data.get("sleep"))
    out["nappies"] = _opt(data.get("nappies"))
    out["activities"] = _opt(data.get("activities"))
    out["notes"] = _opt(data.get("notes"))
    out["staff_id"] = _opt(data.get("staff_id"))
    out["shared"] = _as_bool(data.get("shared"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_update_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT update_id FROM daily_updates").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing daily-update ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        uid = f"{ID_PREFIX}{n}"
        if uid not in existing:
            return uid
    raise RuntimeError("Could not allocate a unique daily-update id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_updates(*, pupil_id: str | None = None) -> list[DailyUpdate]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if pupil_id:
        sql += " WHERE du.pupil_id = ?"
        params.append(pupil_id)
    sql += " ORDER BY du.update_date DESC, du.update_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_updates failed")
        raise
    return [_row(r) for r in rows]


def get_update(update_id: str) -> DailyUpdate | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE du.update_id = ?", (update_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_update(%s) failed", update_id)
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

def create_update(data_: dict[str, Any]) -> DailyUpdate:
    _ensure_schema()
    payload = _validate(data_, require_pupil=True)
    uid = generate_update_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO daily_updates (
                    update_id, pupil_id, update_date, mood, meals, sleep,
                    nappies, activities, notes, staff_id, shared
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (uid, payload["pupil_id"], payload["update_date"],
                 payload["mood"], payload["meals"], payload["sleep"],
                 payload["nappies"], payload["activities"], payload["notes"],
                 payload["staff_id"], payload["shared"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for daily-update id=%s", uid)
        raise ValidationError(f"Could not create daily update — {e}") from e
    u = get_update(uid)
    assert u is not None
    logger.info("Created daily update %s for pupil %s", uid, payload["pupil_id"])
    return u


def update_update(update_id: str, data_: dict[str, Any]) -> DailyUpdate:
    _ensure_schema()
    payload = _validate(data_, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE daily_updates SET
                    update_date = ?, mood = ?, meals = ?, sleep = ?,
                    nappies = ?, activities = ?, notes = ?, staff_id = ?,
                    shared = ?
                WHERE update_id = ?
                """,
                (payload["update_date"], payload["mood"], payload["meals"],
                 payload["sleep"], payload["nappies"], payload["activities"],
                 payload["notes"], payload["staff_id"], payload["shared"],
                 update_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No daily update with id {update_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for daily-update id=%s", update_id)
        raise ValidationError(f"Could not update daily update — {e}") from e
    u = get_update(update_id)
    assert u is not None
    logger.info("Updated daily update %s", update_id)
    return u


def delete_update(update_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM daily_updates WHERE update_id = ?", (update_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting daily-update id=%s", update_id)
        raise
    if deleted:
        logger.info("Deleted daily update %s", update_id)
    return deleted
