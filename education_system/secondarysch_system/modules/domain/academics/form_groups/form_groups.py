"""Form-group (tutor group) data layer for the Secondary School System.

A form group is a tutor group within a year (e.g. "7A"). Each form has a
name unique within its year, a year group, an optional form tutor, an
optional room, and notes. Live pupil counts are read from the ``pupils``
table on demand via the ``form_group`` column.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS form_groups (
    form_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    year_group     TEXT NOT NULL,
    form_tutor     TEXT,
    room           TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now')),
    UNIQUE (name, year_group)
);
CREATE INDEX IF NOT EXISTS idx_form_groups_year ON form_groups(year_group);
"""


@dataclass
class FormGroup:
    form_id: int
    name: str
    year_group: str
    form_tutor: str | None
    room: str | None
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
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise form_groups table")
        raise
    logger.info("Secondary form_groups table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> FormGroup:
    return FormGroup(
        form_id=r["form_id"],
        name=r["name"],
        year_group=r["year_group"],
        form_tutor=r["form_tutor"],
        room=r["room"],
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("Form name is required")
    if len(name) > 16:
        raise ValidationError("Form name must be 16 characters or fewer")
    out["name"] = name
    yg = (data.get("year_group") or "").strip()
    if not yg:
        raise ValidationError("Year group is required")
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(YEAR_GROUPS)}")
    out["year_group"] = yg
    out["form_tutor"] = (data.get("form_tutor") or "").strip() or None
    out["room"]       = (data.get("room") or "").strip() or None
    out["notes"]      = (data.get("notes") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> FormGroup:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT form_id FROM form_groups "
                "WHERE name = ? AND year_group = ?",
                (payload["name"], payload["year_group"]),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"Form {payload['name']!r} already exists "
                    f"for Year {payload['year_group']}")
            cur = conn.execute(
                """INSERT INTO form_groups
                       (name, year_group, form_tutor, room, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (payload["name"], payload["year_group"],
                 payload["form_tutor"], payload["room"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create form group %s/%s",
                         payload["year_group"], payload["name"])
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("Created form group #%d %s (Year %s, tutor=%s)",
                rec.form_id, rec.name, rec.year_group, rec.form_tutor)
    return rec


def get(form_id: int) -> FormGroup | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM form_groups WHERE form_id = ?", (form_id,)
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get form_group(%s) failed", form_id)
        raise
    return _row(r) if r else None


def get_by_name(name: str, year_group: str) -> FormGroup | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM form_groups WHERE name = ? AND year_group = ?",
                (name.strip(), year_group.strip()),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_by_name(%s,%s) failed", name, year_group)
        raise
    return _row(r) if r else None


def list_all(year_group: str | None = None) -> list[FormGroup]:
    init_db()
    sql = "SELECT * FROM form_groups"
    params: tuple[Any, ...] = ()
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        sql += " WHERE year_group = ?"
        params = (year_group,)
    sql += " ORDER BY year_group, name"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_all form_groups failed")
        raise
    return [_row(r) for r in rows]


def pupil_counts() -> dict[int, int]:
    """Return ``{form_id: pupil_count}`` matched on (year_group, name)."""
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                """SELECT fg.form_id AS form_id, COUNT(p.pupil_id) AS n
                   FROM form_groups fg
                   LEFT JOIN pupils p
                     ON p.form_group = fg.name
                    AND p.year_group = fg.year_group
                   GROUP BY fg.form_id"""
            ).fetchall()
    except sqlite3.Error:
        logger.exception("form_groups pupil_counts failed")
        raise
    return {r["form_id"]: r["n"] for r in rows}


def update(form_id: int, data: dict[str, Any]) -> FormGroup:
    init_db()
    existing = get(form_id)
    if existing is None:
        raise ValidationError(f"No form group #{form_id}")
    merged = {
        "name":       data.get("name", existing.name),
        "year_group": data.get("year_group", existing.year_group),
        "form_tutor": data.get("form_tutor", existing.form_tutor),
        "room":       data.get("room", existing.room),
        "notes":      data.get("notes", existing.notes),
    }
    payload = _validate(merged)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT form_id FROM form_groups "
                "WHERE name = ? AND year_group = ? AND form_id <> ?",
                (payload["name"], payload["year_group"], form_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"Form {payload['name']!r} already exists "
                    f"for Year {payload['year_group']}")
            conn.execute(
                """UPDATE form_groups SET
                       name = ?, year_group = ?, form_tutor = ?,
                       room = ?, notes = ?, updated_at = datetime('now')
                   WHERE form_id = ?""",
                (payload["name"], payload["year_group"],
                 payload["form_tutor"], payload["room"], payload["notes"],
                 form_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update form group #%d", form_id)
        raise
    rec = get(form_id)
    assert rec is not None
    logger.info("Updated form group #%d %s (Year %s)",
                rec.form_id, rec.name, rec.year_group)
    return rec


def delete(form_id: int) -> bool:
    init_db()
    existing = get(form_id)
    counts = pupil_counts()
    if existing and counts.get(form_id, 0) > 0:
        raise ValidationError(
            f"Form {existing.name} (Year {existing.year_group}) still has "
            f"{counts[form_id]} pupil(s) assigned — reassign before deleting")
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM form_groups WHERE form_id = ?", (form_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete form group #%d", form_id)
        raise
    if deleted and existing:
        logger.info("Deleted form group #%d %s (Year %s)",
                    form_id, existing.name, existing.year_group)
    return deleted
