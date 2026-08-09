"""Domain layer for Next Steps Planning (Nursery System).

Owns the ``next_steps`` table — planned next steps for a child's learning,
each linked to an EYFS area, with a status lifecycle from planned through
in_progress to achieved. Staff can be assigned as the lead for each step.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``next_steps_cli.py``, Tk GUI in ``next_steps_views.py``.
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

FEATURE_NAME = "Next Steps Planning"
CATEGORY = "EYFS Learning & Development"

ID_PREFIX = "NNS"
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
STATUSES = ("planned", "in_progress", "achieved")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid next-steps input."""


@dataclass
class NextStep:
    step_id: str
    pupil_id: str
    area: str | None
    description: str
    planned_date: str | None
    target_date: str | None
    status: str
    achieved_date: str | None
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
        logger.exception("Failed to initialise nursery DB for next-steps")
        raise


_SELECT = """
SELECT ns.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS staff_name
FROM next_steps ns
LEFT JOIN pupils p ON p.pupil_id = ns.pupil_id
LEFT JOIN staff s ON s.staff_id = ns.staff_id
"""


def _row(r: sqlite3.Row) -> NextStep:
    keys = r.keys()
    return NextStep(
        step_id=r["step_id"],
        pupil_id=r["pupil_id"],
        area=r["area"],
        description=r["description"],
        planned_date=r["planned_date"],
        target_date=r["target_date"],
        status=r["status"],
        achieved_date=r["achieved_date"],
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


def _validate(data_: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data_.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    desc = (data_.get("description") or "").strip()
    if not desc:
        raise ValidationError("Description is required")
    out["description"] = desc

    area = (data_.get("area") or "").strip()
    if area and area not in AREAS:
        raise ValidationError("Area must be one of: " + ", ".join(AREAS))
    out["area"] = area or None

    status = (data_.get("status") or "").strip()
    if status and status not in STATUSES:
        raise ValidationError("Status must be one of: " + ", ".join(STATUSES))
    out["status"] = status or "planned"

    out["planned_date"] = _opt_date(data_.get("planned_date"), "Planned date")
    out["target_date"] = _opt_date(data_.get("target_date"), "Target date")
    out["achieved_date"] = _opt_date(data_.get("achieved_date"), "Achieved date")
    out["staff_id"] = _opt(data_.get("staff_id"))
    out["notes"] = _opt(data_.get("notes"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_step_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT step_id FROM next_steps").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing next-steps ids")
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
    raise RuntimeError("Could not allocate a unique next-step id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_steps(*, pupil_id: str | None = None) -> list[NextStep]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if pupil_id:
        sql += " WHERE ns.pupil_id = ?"
        params.append(pupil_id)
    sql += " ORDER BY ns.target_date DESC, ns.step_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_steps failed")
        raise
    return [_row(r) for r in rows]


def get_step(step_id: str) -> NextStep | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE ns.step_id = ?", (step_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_step(%s) failed", step_id)
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

def create_step(data_: dict[str, Any]) -> NextStep:
    _ensure_schema()
    payload = _validate(data_, require_pupil=True)
    sid = generate_step_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO next_steps (
                    step_id, pupil_id, area, description,
                    planned_date, target_date, status, achieved_date,
                    staff_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sid, payload["pupil_id"], payload["area"], payload["description"],
                 payload["planned_date"], payload["target_date"], payload["status"],
                 payload["achieved_date"], payload["staff_id"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for next-step id=%s", sid)
        raise ValidationError(f"Could not create step — {e}") from e
    s = get_step(sid)
    assert s is not None
    logger.info("Created next-step %s for pupil %s", sid, payload["pupil_id"])
    return s


def update_step(step_id: str, data_: dict[str, Any]) -> NextStep:
    _ensure_schema()
    payload = _validate(data_, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE next_steps SET
                    area = ?, description = ?, planned_date = ?,
                    target_date = ?, status = ?, achieved_date = ?,
                    staff_id = ?, notes = ?
                WHERE step_id = ?
                """,
                (payload["area"], payload["description"], payload["planned_date"],
                 payload["target_date"], payload["status"], payload["achieved_date"],
                 payload["staff_id"], payload["notes"], step_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No next-step with id {step_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for next-step id=%s", step_id)
        raise ValidationError(f"Could not update step — {e}") from e
    s = get_step(step_id)
    assert s is not None
    logger.info("Updated next-step %s", step_id)
    return s


def delete_step(step_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM next_steps WHERE step_id = ?", (step_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting next-step id=%s", step_id)
        raise
    if deleted:
        logger.info("Deleted next-step %s", step_id)
    return deleted
