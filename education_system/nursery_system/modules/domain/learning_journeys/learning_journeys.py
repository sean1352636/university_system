"""Domain layer for Learning Journeys (Nursery System).

Owns the ``learning_journeys`` table — curated journal entries / "wow moments"
per child, mapped to the seven EYFS areas of learning. Each entry optionally
links to the staff member who observed it and can be flagged as a wow moment
and/or shared with parents.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``learning_journeys_cli.py``, Tk GUI in ``learning_journeys_views.py``.
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

FEATURE_NAME = "Learning Journeys"
CATEGORY = "EYFS Learning & Development"

ID_PREFIX = "NLJ"
ID_DIGITS = 3

AREAS = (
    "Communication and Language",
    "Physical Development",
    "Personal, Social and Emotional Development",
    "Literacy",
    "Mathematics",
    "Understanding the World",
    "Expressive Arts and Design",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid learning-journey input."""


@dataclass
class JourneyEntry:
    entry_id: str
    pupil_id: str
    entry_date: str | None
    title: str
    area: str | None
    description: str | None
    wow_moment: bool
    shared_with_parent: bool
    staff_id: str | None
    notes: str | None
    created_at: str | None = None
    child_name: str | None = None
    room: str | None = None
    staff_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for learning journeys")
        raise


_SELECT = """
SELECT lj.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS staff_name
FROM learning_journeys lj
LEFT JOIN pupils p ON p.pupil_id = lj.pupil_id
LEFT JOIN staff s ON s.staff_id = lj.staff_id
"""


def _row(r: sqlite3.Row) -> JourneyEntry:
    keys = r.keys()
    return JourneyEntry(
        entry_id=r["entry_id"],
        pupil_id=r["pupil_id"],
        entry_date=r["entry_date"],
        title=r["title"],
        area=r["area"],
        description=r["description"],
        wow_moment=bool(r["wow_moment"]),
        shared_with_parent=bool(r["shared_with_parent"]),
        staff_id=r["staff_id"],
        notes=r["notes"],
        created_at=r["created_at"] if "created_at" in keys else None,
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
        staff_name=r["staff_name"] if "staff_name" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
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

    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    out["title"] = title

    area = (data.get("area") or "").strip()
    if area and area not in AREAS:
        raise ValidationError("Area must be one of: " + ", ".join(AREAS))
    out["area"] = area or None

    entry_date = (data.get("entry_date") or "").strip()
    if entry_date and not _DATE_RE.match(entry_date):
        raise ValidationError("Entry date must be in YYYY-MM-DD format")
    out["entry_date"] = entry_date or None

    out["description"] = _opt(data.get("description"))
    out["notes"] = _opt(data.get("notes"))
    out["wow_moment"] = _as_bool(data.get("wow_moment"))
    out["shared_with_parent"] = _as_bool(data.get("shared_with_parent"))

    staff_id = (data.get("staff_id") or "").strip()
    out["staff_id"] = staff_id or None

    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_entry_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT entry_id FROM learning_journeys").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing learning-journey ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        eid = f"{ID_PREFIX}{n}"
        if eid not in existing:
            return eid
    raise RuntimeError("Could not allocate a unique learning-journey id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_entries(*, pupil_id: str | None = None) -> list[JourneyEntry]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if pupil_id:
        sql += " WHERE lj.pupil_id = ?"
        params.append(pupil_id)
    sql += " ORDER BY lj.entry_date DESC, lj.entry_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_entries failed")
        raise
    return [_row(r) for r in rows]


def get_entry(entry_id: str) -> JourneyEntry | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE lj.entry_id = ?", (entry_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_entry(%s) failed", entry_id)
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

def create_entry(data: dict[str, Any]) -> JourneyEntry:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    eid = generate_entry_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO learning_journeys (
                    entry_id, pupil_id, entry_date, title, area, description,
                    wow_moment, shared_with_parent, staff_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (eid, payload["pupil_id"], payload["entry_date"], payload["title"],
                 payload["area"], payload["description"], payload["wow_moment"],
                 payload["shared_with_parent"], payload["staff_id"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for learning-journey id=%s", eid)
        raise ValidationError(f"Could not create entry — {e}") from e
    entry = get_entry(eid)
    assert entry is not None
    logger.info("Created learning journey %s for pupil %s", eid, payload["pupil_id"])
    return entry


def update_entry(entry_id: str, data: dict[str, Any]) -> JourneyEntry:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_entry(entry_id)
    if existing is None:
        raise ValidationError(f"No learning journey with id {entry_id}")
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE learning_journeys SET
                    entry_date = ?, title = ?, area = ?, description = ?,
                    wow_moment = ?, shared_with_parent = ?, staff_id = ?, notes = ?
                WHERE entry_id = ?
                """,
                (payload["entry_date"], payload["title"], payload["area"],
                 payload["description"], payload["wow_moment"],
                 payload["shared_with_parent"], payload["staff_id"],
                 payload["notes"], entry_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No learning journey with id {entry_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for learning-journey id=%s", entry_id)
        raise ValidationError(f"Could not update entry — {e}") from e
    entry = get_entry(entry_id)
    assert entry is not None
    logger.info("Updated learning journey %s", entry_id)
    return entry


def delete_entry(entry_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM learning_journeys WHERE entry_id = ?", (entry_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting learning-journey id=%s", entry_id)
        raise
    if deleted:
        logger.info("Deleted learning journey %s", entry_id)
    return deleted
