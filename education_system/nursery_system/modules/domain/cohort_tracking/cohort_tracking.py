"""Domain layer for Cohort Tracking (Nursery System).

Owns the ``cohort_tracking`` table — cohort-level (group) attainment snapshots
per room/term/area. Records are NOT attached to a single child; they capture
whole-group attainment data for EYFS reporting.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``cohort_tracking_cli.py``, Tk GUI in ``cohort_tracking_views.py``.
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

FEATURE_NAME = "Cohort Tracking"
CATEGORY = "EYFS Learning & Development"

ID_PREFIX = "NCT"
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

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid cohort tracking input."""


@dataclass
class Cohort:
    cohort_id: str
    cohort_name: str
    room: str | None
    term: str | None
    area: str | None
    total_children: int | None
    below_count: int | None
    on_track_count: int | None
    above_count: int | None
    assessment_date: str | None
    staff_id: str | None
    notes: str | None
    created_at: str | None
    staff_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for cohort tracking")
        raise


_SELECT = """
SELECT ct.*,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS staff_name
FROM cohort_tracking ct
LEFT JOIN staff s ON s.staff_id = ct.staff_id
"""


def _row(r: sqlite3.Row) -> Cohort:
    keys = r.keys()
    return Cohort(
        cohort_id=r["cohort_id"],
        cohort_name=r["cohort_name"],
        room=r["room"],
        term=r["term"],
        area=r["area"],
        total_children=r["total_children"],
        below_count=r["below_count"],
        on_track_count=r["on_track_count"],
        above_count=r["above_count"],
        assessment_date=r["assessment_date"],
        staff_id=r["staff_id"],
        notes=r["notes"],
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


def _opt_int(value: Any, label: str) -> int | None:
    raw = str(value if value is not None else "").strip()
    if not raw:
        return None
    try:
        n = int(raw)
    except ValueError as e:
        raise ValidationError(f"{label} must be a whole number") from e
    if n < 0:
        raise ValidationError(f"{label} cannot be negative")
    return n


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    cohort_name = (data.get("cohort_name") or "").strip()
    if not cohort_name:
        raise ValidationError("Cohort name is required")
    out["cohort_name"] = cohort_name

    room = (data.get("room") or "").strip()
    if room and room not in ROOMS:
        raise ValidationError("Room must be one of: " + ", ".join(ROOMS))
    out["room"] = room or None

    out["term"] = _opt(data.get("term"))

    area = (data.get("area") or "").strip()
    if area and area not in AREAS:
        raise ValidationError("Area must be one of: " + ", ".join(AREAS))
    out["area"] = area or None

    out["total_children"] = _opt_int(data.get("total_children"), "Total children")
    out["below_count"] = _opt_int(data.get("below_count"), "Below count")
    out["on_track_count"] = _opt_int(data.get("on_track_count"), "On-track count")
    out["above_count"] = _opt_int(data.get("above_count"), "Above count")

    out["assessment_date"] = _opt_date(data.get("assessment_date"), "Assessment date")
    out["staff_id"] = _opt(data.get("staff_id"))
    out["notes"] = _opt(data.get("notes"))
    return out


# ── ID allocation ─────────────────────────────────────────────────────────────

def generate_cohort_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT cohort_id FROM cohort_tracking").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing cohort tracking ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        cid = f"{ID_PREFIX}{n}"
        if cid not in existing:
            return cid
    raise RuntimeError("Could not allocate a unique cohort tracking id")


# ── Reads ─────────────────────────────────────────────────────────────────────

def list_cohorts() -> list[Cohort]:
    _ensure_schema()
    sql = (
        _SELECT
        + " ORDER BY COALESCE(ct.assessment_date, '') DESC, ct.cohort_id DESC"
    )
    try:
        with connect() as conn:
            rows = conn.execute(sql).fetchall()
    except sqlite3.Error:
        logger.exception("list_cohorts failed")
        raise
    return [_row(r) for r in rows]


def get_cohort(cohort_id: str) -> Cohort | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE ct.cohort_id = ?",
                (cohort_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_cohort(%s) failed", cohort_id)
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

def create_cohort(data: dict[str, Any]) -> Cohort:
    _ensure_schema()
    payload = _validate(data)
    cid = generate_cohort_id()
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO cohort_tracking (
                    cohort_id, cohort_name, room, term, area,
                    total_children, below_count, on_track_count, above_count,
                    assessment_date, staff_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, payload["cohort_name"], payload["room"],
                 payload["term"], payload["area"],
                 payload["total_children"], payload["below_count"],
                 payload["on_track_count"], payload["above_count"],
                 payload["assessment_date"], payload["staff_id"],
                 payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.exception("INSERT failed for cohort id=%s", cid)
        raise ValidationError(f"Could not create cohort — {e}") from e
    c = get_cohort(cid)
    assert c is not None
    logger.info("Created cohort tracking record %s", cid)
    return c


def update_cohort(cohort_id: str, data: dict[str, Any]) -> Cohort:
    _ensure_schema()
    payload = _validate(data)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE cohort_tracking SET
                    cohort_name = ?, room = ?, term = ?, area = ?,
                    total_children = ?, below_count = ?, on_track_count = ?,
                    above_count = ?, assessment_date = ?, staff_id = ?, notes = ?
                WHERE cohort_id = ?
                """,
                (payload["cohort_name"], payload["room"],
                 payload["term"], payload["area"],
                 payload["total_children"], payload["below_count"],
                 payload["on_track_count"], payload["above_count"],
                 payload["assessment_date"], payload["staff_id"],
                 payload["notes"], cohort_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No cohort with id {cohort_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for cohort id=%s", cohort_id)
        raise ValidationError(f"Could not update cohort — {e}") from e
    c = get_cohort(cohort_id)
    assert c is not None
    logger.info("Updated cohort tracking record %s", cohort_id)
    return c


def delete_cohort(cohort_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM cohort_tracking WHERE cohort_id = ?",
                (cohort_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting cohort id=%s", cohort_id)
        raise
    if deleted:
        logger.info("Deleted cohort tracking record %s", cohort_id)
    return deleted
