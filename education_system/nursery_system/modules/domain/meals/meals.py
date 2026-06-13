"""Domain layer for Meals & Menus (Nursery System).

Owns the ``meals`` table — the per-child meal log behind the daily care
routine. One row per child per meal (breakfast, snacks, lunch, tea) recording
the menu served, how much was eaten, the drink offered, whether the meal was
safe against the child's allergies, the staff member who recorded it and any
notes for parents.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``meals_cli.py``, Tk GUI in ``meals_views.py``.
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

FEATURE_NAME = "Meals & Menus"
CATEGORY = "Daily Care & Routines"

ID_PREFIX = "NML"
ID_DIGITS = 3

MEAL_TYPES = ("Breakfast", "Morning snack", "Lunch", "Afternoon snack", "Tea")
AMOUNTS = ("none", "some", "most", "all")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid meal-log input."""


@dataclass
class MealRecord:
    meal_id: str
    pupil_id: str
    meal_date: str
    meal_type: str
    menu: str | None
    amount_eaten: str | None
    drink: str | None
    allergy_safe: int
    staff_id: str | None
    notes: str | None
    child_name: str | None = None
    staff_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for meals")
        raise


_SELECT = """
SELECT m.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       TRIM(s.first_name || ' ' || s.last_name) AS staff_name
FROM meals m
LEFT JOIN pupils p ON p.pupil_id = m.pupil_id
LEFT JOIN staff  s ON s.staff_id = m.staff_id
"""


def _row(r: sqlite3.Row) -> MealRecord:
    keys = r.keys()
    return MealRecord(
        meal_id=r["meal_id"],
        pupil_id=r["pupil_id"],
        meal_date=r["meal_date"],
        meal_type=r["meal_type"],
        menu=r["menu"],
        amount_eaten=r["amount_eaten"],
        drink=r["drink"],
        allergy_safe=int(r["allergy_safe"]),
        staff_id=r["staff_id"],
        notes=r["notes"],
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

    meal_date = (data.get("meal_date") or "").strip() or _dt.date.today().isoformat()
    if not _DATE_RE.match(meal_date):
        raise ValidationError("Meal date must be YYYY-MM-DD")
    out["meal_date"] = meal_date

    meal_type = (data.get("meal_type") or "Lunch").strip()
    if meal_type not in MEAL_TYPES:
        raise ValidationError("Meal type must be one of: " + ", ".join(MEAL_TYPES))
    out["meal_type"] = meal_type

    amount = (data.get("amount_eaten") or "").strip().lower()
    if amount and amount not in AMOUNTS:
        raise ValidationError("Amount eaten must be one of: " + ", ".join(AMOUNTS))
    out["amount_eaten"] = amount or None

    out["menu"] = _opt(data.get("menu"))
    out["drink"] = _opt(data.get("drink"))
    out["notes"] = _opt(data.get("notes"))
    out["staff_id"] = _opt(data.get("staff_id"))

    safe = data.get("allergy_safe", 1)
    if isinstance(safe, (bool, int)):
        out["allergy_safe"] = int(bool(safe))
    else:
        out["allergy_safe"] = int(
            str(safe or "").strip().lower() in ("1", "y", "yes", "true", "on"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_record_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT meal_id FROM meals").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing meal ids")
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
    raise RuntimeError("Could not allocate a unique meal id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_records(*, meal_date: str | None = None, pupil_id: str | None = None,
                 meal_type: str | None = None) -> list[MealRecord]:
    _ensure_schema()
    sql = _SELECT
    clauses: list[str] = []
    params: list[Any] = []
    if meal_date:
        clauses.append("m.meal_date = ?")
        params.append(meal_date.strip())
    if pupil_id:
        clauses.append("m.pupil_id = ?")
        params.append(pupil_id.strip())
    if meal_type:
        clauses.append("m.meal_type = ?")
        params.append(meal_type.strip())
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY m.meal_date DESC, m.meal_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    return [_row(r) for r in rows]


def get_record(meal_id: str) -> MealRecord | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE m.meal_id = ?", (meal_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_record(%s) failed", meal_id)
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
                "WHERE employment_status != 'Left' "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    return [(r["staff_id"], f"{r['first_name']} {r['last_name']} ({r['staff_id']})")
            for r in rows]


# ── Writes ───────────────────────────────────────────────────────────────────

def create_record(data: dict[str, Any]) -> MealRecord:
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
                INSERT INTO meals (
                    meal_id, pupil_id, meal_date, meal_type, menu,
                    amount_eaten, drink, allergy_safe, staff_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["pupil_id"], payload["meal_date"],
                 payload["meal_type"], payload["menu"], payload["amount_eaten"],
                 payload["drink"], payload["allergy_safe"], payload["staff_id"],
                 payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for meal id=%s", rid)
        raise ValidationError(f"Could not create record — {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created meal record %s for pupil %s (%s)",
                rid, payload["pupil_id"], payload["meal_type"])
    return rec


def update_record(meal_id: str, data: dict[str, Any]) -> MealRecord:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_record(meal_id)
    if existing is None:
        raise ValidationError(f"No meal record with id {meal_id}")
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE meals SET
                    meal_date = ?, meal_type = ?, menu = ?, amount_eaten = ?,
                    drink = ?, allergy_safe = ?, staff_id = ?, notes = ?
                WHERE meal_id = ?
                """,
                (payload["meal_date"], payload["meal_type"], payload["menu"],
                 payload["amount_eaten"], payload["drink"],
                 payload["allergy_safe"], payload["staff_id"], payload["notes"],
                 meal_id),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for meal id=%s", meal_id)
        raise ValidationError(f"Could not update record — {e}") from e
    rec = get_record(meal_id)
    assert rec is not None
    logger.info("Updated meal record %s", meal_id)
    return rec


def delete_record(meal_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute("DELETE FROM meals WHERE meal_id = ?", (meal_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting meal id=%s", meal_id)
        raise
    if deleted:
        logger.info("Deleted meal record %s", meal_id)
    return deleted
