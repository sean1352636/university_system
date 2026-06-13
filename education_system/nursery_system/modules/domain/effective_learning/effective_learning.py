"""Domain layer for Characteristics of Effective Learning (Nursery System).

Owns the ``effective_learning`` table — EYFS observations of HOW a child
learns, covering the three prime characteristics: Playing and Exploring,
Active Learning, and Creating and Thinking Critically.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``effective_learning_cli.py``, Tk GUI in ``effective_learning_views.py``.
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

FEATURE_NAME = "Characteristics of Effective Learning"
CATEGORY = "EYFS Learning & Development"

ID_PREFIX = "NEL"
ID_DIGITS = 3

CHARACTERISTICS = (
    "Playing and Exploring",
    "Active Learning",
    "Creating and Thinking Critically",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid effective learning input."""


@dataclass
class EffectiveLearning:
    record_id: str
    pupil_id: str
    observation_date: str | None
    characteristic: str | None
    aspect: str | None
    description: str | None
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
        logger.exception("Failed to initialise nursery DB for effective-learning")
        raise


_SELECT = """
SELECT el.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS staff_name
FROM effective_learning el
LEFT JOIN pupils p ON p.pupil_id = el.pupil_id
LEFT JOIN staff s ON s.staff_id = el.staff_id
"""


def _row(r: sqlite3.Row) -> EffectiveLearning:
    keys = r.keys()
    return EffectiveLearning(
        record_id=r["record_id"],
        pupil_id=r["pupil_id"],
        observation_date=r["observation_date"],
        characteristic=r["characteristic"],
        aspect=r["aspect"],
        description=r["description"],
        staff_id=r["staff_id"],
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


def _opt_date(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if v and not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v or None


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    out["observation_date"] = _opt_date(data.get("observation_date"), "Observation date")

    characteristic = (data.get("characteristic") or "").strip()
    if characteristic and characteristic not in CHARACTERISTICS:
        raise ValidationError(
            "Characteristic must be one of: " + ", ".join(CHARACTERISTICS))
    out["characteristic"] = characteristic or None

    out["aspect"] = _opt(data.get("aspect"))
    out["description"] = _opt(data.get("description"))
    out["staff_id"] = _opt(data.get("staff_id"))
    out["notes"] = _opt(data.get("notes"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_record_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT record_id FROM effective_learning").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing effective-learning ids")
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
    raise RuntimeError("Could not allocate a unique effective-learning id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_records(*, pupil_id: str | None = None) -> list[EffectiveLearning]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if pupil_id:
        sql += " WHERE el.pupil_id = ?"
        params.append(pupil_id)
    sql += " ORDER BY el.observation_date DESC, el.record_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    return [_row(r) for r in rows]


def get_record(record_id: str) -> EffectiveLearning | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE el.record_id = ?", (record_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_record(%s) failed", record_id)
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

def create_record(data: dict[str, Any]) -> EffectiveLearning:
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
                INSERT INTO effective_learning (
                    record_id, pupil_id, observation_date, characteristic,
                    aspect, description, staff_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["pupil_id"], payload["observation_date"],
                 payload["characteristic"], payload["aspect"],
                 payload["description"], payload["staff_id"],
                 payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for effective-learning id=%s", rid)
        raise ValidationError(f"Could not create record — {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created effective-learning record %s for pupil %s",
                rid, payload["pupil_id"])
    return rec


def update_record(record_id: str, data: dict[str, Any]) -> EffectiveLearning:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE effective_learning SET
                    observation_date = ?, characteristic = ?, aspect = ?,
                    description = ?, staff_id = ?, notes = ?
                WHERE record_id = ?
                """,
                (payload["observation_date"], payload["characteristic"],
                 payload["aspect"], payload["description"],
                 payload["staff_id"], payload["notes"], record_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(
                    f"No effective-learning record with id {record_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for effective-learning id=%s", record_id)
        raise ValidationError(f"Could not update record — {e}") from e
    rec = get_record(record_id)
    assert rec is not None
    logger.info("Updated effective-learning record %s", record_id)
    return rec


def delete_record(record_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM effective_learning WHERE record_id = ?", (record_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting effective-learning id=%s", record_id)
        raise
    if deleted:
        logger.info("Deleted effective-learning record %s", record_id)
    return deleted
