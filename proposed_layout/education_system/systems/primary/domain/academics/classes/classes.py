"""Classes data layer for the Primary School System.

One row per class/form group (e.g. "3 Maple", "R Robin"). Each class
has a year group, an optional class teacher, an optional room, and an
optional capacity. ``pupils_in_class`` returns the pupils whose
``class_name`` matches.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils import (
    pupils as pupils_data,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    Pupil, ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS classes (
    class_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    year_group    TEXT NOT NULL,
    teacher       TEXT,
    room          TEXT,
    capacity      INTEGER,
    is_active     INTEGER NOT NULL DEFAULT 1,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_classes_year_group ON classes(year_group);
CREATE INDEX IF NOT EXISTS idx_classes_active     ON classes(is_active);
"""


@dataclass
class SchoolClass:
    class_id: int
    name: str
    year_group: str
    teacher: str | None
    room: str | None
    capacity: int | None
    is_active: bool
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    pupils_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise classes table")
        raise
    logger.info("Primary classes table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> SchoolClass:
    return SchoolClass(
        class_id=r["class_id"],
        name=r["name"],
        year_group=r["year_group"],
        teacher=r["teacher"],
        room=r["room"],
        capacity=r["capacity"],
        is_active=bool(r["is_active"]),
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("Class name is required")
    if len(name) > 64:
        raise ValidationError("Class name must be 64 characters or fewer")
    out["name"] = name
    yg = (data.get("year_group") or "").strip()
    if not yg:
        raise ValidationError("Year group is required")
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(YEAR_GROUPS)}")
    out["year_group"] = yg
    out["teacher"] = (data.get("teacher") or "").strip() or None
    out["room"]    = (data.get("room") or "").strip() or None
    cap_raw = data.get("capacity")
    if cap_raw in (None, ""):
        out["capacity"] = None
    else:
        try:
            cap = int(cap_raw)
        except (TypeError, ValueError) as e:
            raise ValidationError("Capacity must be an integer") from e
        if cap < 0 or cap > 200:
            raise ValidationError("Capacity must be between 0 and 200")
        out["capacity"] = cap
    is_active = data.get("is_active")
    out["is_active"] = True if is_active is None else bool(is_active)
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> SchoolClass:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT class_id FROM classes WHERE name = ?",
                (payload["name"],),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A class named {payload['name']!r} already exists")
            cur = conn.execute(
                """INSERT INTO classes
                       (name, year_group, teacher, room, capacity,
                        is_active, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (payload["name"], payload["year_group"], payload["teacher"],
                 payload["room"], payload["capacity"],
                 1 if payload["is_active"] else 0, payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create class %s", payload["name"])
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("Created class #%d %s (year %s)",
                rec.class_id, rec.name, rec.year_group)
    return rec


def get(class_id: int) -> SchoolClass | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM classes WHERE class_id = ?", (class_id,)
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get class(%s) failed", class_id)
        raise
    return _row(r) if r else None


def get_by_name(name: str) -> SchoolClass | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM classes WHERE name = ?",
                ((name or "").strip(),),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_by_name(%s) failed", name)
        raise
    return _row(r) if r else None


def list_all(*, year_group: str | None = None,
             active_only: bool = False) -> list[SchoolClass]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("year_group = ?")
        params.append(year_group)
    if active_only:
        where.append("is_active = 1")
    sql = "SELECT * FROM classes"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY year_group, name COLLATE NOCASE"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list classes failed")
        raise
    return [_row(r) for r in rows]


def update(class_id: int, data: dict[str, Any]) -> SchoolClass:
    init_db()
    existing = get(class_id)
    if existing is None:
        raise ValidationError(f"No class #{class_id}")
    merged = {
        "name":       data.get("name", existing.name),
        "year_group": data.get("year_group", existing.year_group),
        "teacher":    data.get("teacher", existing.teacher),
        "room":       data.get("room", existing.room),
        "capacity":   data.get("capacity", existing.capacity),
        "is_active":  data.get("is_active", existing.is_active),
        "notes":      data.get("notes", existing.notes),
    }
    payload = _validate(merged)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT class_id FROM classes "
                "WHERE name = ? AND class_id <> ?",
                (payload["name"], class_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A class named {payload['name']!r} already exists")
            conn.execute(
                """UPDATE classes SET
                       name = ?, year_group = ?, teacher = ?, room = ?,
                       capacity = ?, is_active = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE class_id = ?""",
                (payload["name"], payload["year_group"], payload["teacher"],
                 payload["room"], payload["capacity"],
                 1 if payload["is_active"] else 0,
                 payload["notes"], class_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update class #%d", class_id)
        raise
    rec = get(class_id)
    assert rec is not None
    logger.info("Updated class #%d %s", rec.class_id, rec.name)
    return rec


def toggle_active(class_id: int) -> SchoolClass:
    init_db()
    existing = get(class_id)
    if existing is None:
        raise ValidationError(f"No class #{class_id}")
    new_val = 0 if existing.is_active else 1
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE classes SET is_active = ?, "
                "updated_at = datetime('now') WHERE class_id = ?",
                (new_val, class_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to toggle class #%d", class_id)
        raise
    rec = get(class_id)
    assert rec is not None
    logger.info("Toggled class #%d %s -> active=%s",
                rec.class_id, rec.name, rec.is_active)
    return rec


def pupils_in_class(name: str) -> list[Pupil]:
    """Return pupils whose ``class_name`` matches the given class name."""
    init_db()
    pname = (name or "").strip()
    if not pname:
        return []
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pupils WHERE class_name = ? "
                "ORDER BY last_name, first_name",
                (pname,),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("pupils_in_class(%s) failed", pname)
        raise
    return [pupils_data._row(r) for r in rows]


def delete(class_id: int) -> bool:
    init_db()
    existing = get(class_id)
    if existing is None:
        return False
    pupils = pupils_in_class(existing.name)
    if pupils:
        raise ValidationError(
            f"Class {existing.name!r} has {len(pupils)} pupil(s) assigned — "
            f"reassign them before deleting, or deactivate the class")
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM classes WHERE class_id = ?", (class_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete class #%d", class_id)
        raise
    if deleted:
        logger.info("Deleted class #%d %s", class_id, existing.name)
    return deleted


def counts() -> dict[str, int]:
    init_db()
    try:
        with _connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM classes WHERE is_active = 1"
            ).fetchone()[0]
    except sqlite3.Error:
        logger.exception("class counts failed")
        raise
    return {"total": total, "active": active, "inactive": total - active}
