"""Domain layer for Observations (Nursery System).

Owns the ``observations`` table — day-to-day EYFS observations of a child.
Each row records the observation type, EYFS area, title, description, context,
next steps, and the staff member who made the observation.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``observations_cli.py``, Tk GUI in ``observations_views.py``.
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

FEATURE_NAME = "Observations"
CATEGORY = "EYFS Learning & Development"

ID_PREFIX = "NOB"
ID_DIGITS = 3

OBS_TYPES = ("Spontaneous", "Planned", "Focused")
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
    """Raised for invalid observation input."""


@dataclass
class Observation:
    observation_id: str
    pupil_id: str
    observation_date: str | None
    observation_type: str | None
    area: str | None
    title: str | None
    description: str | None
    context: str | None
    next_step: str | None
    staff_id: str | None
    created_at: str | None
    child_name: str | None = None
    room: str | None = None
    staff_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for observations")
        raise


_SELECT = """
SELECT ob.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS staff_name
FROM observations ob
LEFT JOIN pupils p ON p.pupil_id = ob.pupil_id
LEFT JOIN staff s ON s.staff_id = ob.staff_id
"""


def _row(r: sqlite3.Row) -> Observation:
    keys = r.keys()
    return Observation(
        observation_id=r["observation_id"],
        pupil_id=r["pupil_id"],
        observation_date=r["observation_date"],
        observation_type=r["observation_type"],
        area=r["area"],
        title=r["title"],
        description=r["description"],
        context=r["context"],
        next_step=r["next_step"],
        staff_id=r["staff_id"],
        created_at=r["created_at"],
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

    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    out["title"] = title

    out["observation_date"] = _opt_date(data.get("observation_date"), "Observation date")

    obs_type = (data.get("observation_type") or "").strip()
    if obs_type and obs_type not in OBS_TYPES:
        raise ValidationError(
            "Observation type must be one of: " + ", ".join(OBS_TYPES))
    out["observation_type"] = obs_type or None

    area = (data.get("area") or "").strip()
    if area and area not in AREAS:
        raise ValidationError("Area must be one of: " + ", ".join(AREAS))
    out["area"] = area or None

    out["description"] = _opt(data.get("description"))
    out["context"] = _opt(data.get("context"))
    out["next_step"] = _opt(data.get("next_step"))
    out["staff_id"] = _opt(data.get("staff_id"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_observation_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT observation_id FROM observations").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing observation ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        oid = f"{ID_PREFIX}{n}"
        if oid not in existing:
            return oid
    raise RuntimeError("Could not allocate a unique observation id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_observations(*, pupil_id: str | None = None) -> list[Observation]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if pupil_id:
        sql += " WHERE ob.pupil_id = ?"
        params.append(pupil_id)
    sql += " ORDER BY ob.observation_date DESC, ob.observation_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_observations failed")
        raise
    return [_row(r) for r in rows]


def get_observation(observation_id: str) -> Observation | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE ob.observation_id = ?",
                (observation_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_observation(%s) failed", observation_id)
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

def create_observation(data: dict[str, Any]) -> Observation:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    oid = generate_observation_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO observations (
                    observation_id, pupil_id, observation_date, observation_type,
                    area, title, description, context, next_step, staff_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (oid, payload["pupil_id"], payload["observation_date"],
                 payload["observation_type"], payload["area"], payload["title"],
                 payload["description"], payload["context"], payload["next_step"],
                 payload["staff_id"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for observation id=%s", oid)
        raise ValidationError(f"Could not create observation — {e}") from e
    ob = get_observation(oid)
    assert ob is not None
    logger.info("Created observation %s for pupil %s", oid, payload["pupil_id"])
    return ob


def update_observation(observation_id: str, data: dict[str, Any]) -> Observation:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE observations SET
                    observation_date = ?, observation_type = ?, area = ?,
                    title = ?, description = ?, context = ?,
                    next_step = ?, staff_id = ?
                WHERE observation_id = ?
                """,
                (payload["observation_date"], payload["observation_type"],
                 payload["area"], payload["title"], payload["description"],
                 payload["context"], payload["next_step"], payload["staff_id"],
                 observation_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(
                    f"No observation with id {observation_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for observation id=%s", observation_id)
        raise ValidationError(f"Could not update observation — {e}") from e
    ob = get_observation(observation_id)
    assert ob is not None
    logger.info("Updated observation %s", observation_id)
    return ob


def delete_observation(observation_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM observations WHERE observation_id = ?",
                (observation_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting observation id=%s", observation_id)
        raise
    if deleted:
        logger.info("Deleted observation %s", observation_id)
    return deleted
