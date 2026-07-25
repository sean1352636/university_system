"""Domain layer for Activity & Curriculum Planning (Nursery System).

Owns the ``curriculum_planning`` table — room/setting-level activity plans.
Plans are NOT attached to a child; they are setting- or room-level plans.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``curriculum_planning_cli.py``, Tk GUI in ``curriculum_planning_views.py``.
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

FEATURE_NAME = "Activity & Curriculum Planning"
CATEGORY = "EYFS Learning & Development"

ID_PREFIX = "NCP"
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
ROOMS = (
    "Whole setting",
    "Baby Room",
    "Toddler Room",
    "Preschool Room",
)
STATUSES = ("planned", "delivered")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid curriculum plan input."""


@dataclass
class CurriculumPlan:
    plan_id: str
    title: str
    plan_date: str | None
    room: str | None
    area: str | None
    theme: str | None
    learning_intention: str | None
    activities: str | None
    resources: str | None
    staff_id: str | None
    status: str
    created_at: str | None
    staff_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for curriculum_planning")
        raise


_SELECT = """
SELECT p.*,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS staff_name
FROM curriculum_planning p
LEFT JOIN staff s ON s.staff_id = p.staff_id
"""


def _row(r: sqlite3.Row) -> CurriculumPlan:
    keys = r.keys()
    return CurriculumPlan(
        plan_id=r["plan_id"],
        title=r["title"],
        plan_date=r["plan_date"],
        room=r["room"],
        area=r["area"],
        theme=r["theme"],
        learning_intention=r["learning_intention"],
        activities=r["activities"],
        resources=r["resources"],
        staff_id=r["staff_id"],
        status=r["status"],
        created_at=r["created_at"],
        staff_name=(r["staff_name"] or None) if "staff_name" in keys else None,
    )


# ── Validation ────────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _opt_date(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if v and not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v or None


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    out["title"] = title

    out["plan_date"] = _opt_date(data.get("plan_date"), "Plan date")

    room = (data.get("room") or "").strip()
    if room and room not in ROOMS:
        raise ValidationError("Room must be one of: " + ", ".join(ROOMS))
    out["room"] = room or None

    area = (data.get("area") or "").strip()
    if area and area not in AREAS:
        raise ValidationError("Area must be one of: " + ", ".join(AREAS))
    out["area"] = area or None

    out["theme"] = _opt(data.get("theme"))
    out["learning_intention"] = _opt(data.get("learning_intention"))
    out["activities"] = _opt(data.get("activities"))
    out["resources"] = _opt(data.get("resources"))
    out["staff_id"] = _opt(data.get("staff_id"))

    status = (data.get("status") or "planned").strip()
    if status not in STATUSES:
        raise ValidationError("Status must be one of: " + ", ".join(STATUSES))
    out["status"] = status

    return out


# ── ID allocation ─────────────────────────────────────────────────────────────

def generate_plan_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT plan_id FROM curriculum_planning").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing plan ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        nid = f"{ID_PREFIX}{n}"
        if nid not in existing:
            return nid
    raise RuntimeError("Could not allocate a unique plan id")


# ── Reads ─────────────────────────────────────────────────────────────────────

def list_plans() -> list[CurriculumPlan]:
    _ensure_schema()
    sql = (
        _SELECT
        + " ORDER BY COALESCE(p.plan_date, '') DESC, p.plan_id DESC"
    )
    try:
        with connect() as conn:
            rows = conn.execute(sql).fetchall()
    except sqlite3.Error:
        logger.exception("list_plans failed")
        raise
    return [_row(r) for r in rows]


def get_plan(plan_id: str) -> CurriculumPlan | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE p.plan_id = ?",
                (plan_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_plan(%s) failed", plan_id)
        raise
    return _row(row) if row else None


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


# ── Writes ────────────────────────────────────────────────────────────────────

def create_plan(data: dict[str, Any]) -> CurriculumPlan:
    _ensure_schema()
    payload = _validate(data)
    pid = generate_plan_id()
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO curriculum_planning (
                    plan_id, title, plan_date, room, area, theme,
                    learning_intention, activities, resources, staff_id, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pid, payload["title"], payload["plan_date"],
                 payload["room"], payload["area"], payload["theme"],
                 payload["learning_intention"], payload["activities"],
                 payload["resources"], payload["staff_id"], payload["status"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.exception("INSERT failed for plan id=%s", pid)
        raise ValidationError(f"Could not create plan — {e}") from e
    p = get_plan(pid)
    assert p is not None
    logger.info("Created curriculum plan %s", pid)
    return p


def update_plan(plan_id: str, data: dict[str, Any]) -> CurriculumPlan:
    _ensure_schema()
    payload = _validate(data)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE curriculum_planning SET
                    title = ?, plan_date = ?, room = ?, area = ?, theme = ?,
                    learning_intention = ?, activities = ?, resources = ?,
                    staff_id = ?, status = ?
                WHERE plan_id = ?
                """,
                (payload["title"], payload["plan_date"],
                 payload["room"], payload["area"], payload["theme"],
                 payload["learning_intention"], payload["activities"],
                 payload["resources"], payload["staff_id"],
                 payload["status"], plan_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No plan with id {plan_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for plan id=%s", plan_id)
        raise ValidationError(f"Could not update plan — {e}") from e
    p = get_plan(plan_id)
    assert p is not None
    logger.info("Updated curriculum plan %s", plan_id)
    return p


def delete_plan(plan_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM curriculum_planning WHERE plan_id = ?",
                (plan_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting plan id=%s", plan_id)
        raise
    if deleted:
        logger.info("Deleted curriculum plan %s", plan_id)
    return deleted
