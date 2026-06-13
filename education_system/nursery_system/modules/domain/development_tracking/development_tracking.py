"""Domain layer for Development Tracking (Nursery System).

Owns the ``development_tracking`` table — EYFS assessments recording a child's
progress across prime and specific learning areas over time. Each row captures
the area, aspect, age band, judgement, and next steps for a single assessment.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``development_tracking_cli.py``, Tk GUI in ``development_tracking_views.py``.
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

FEATURE_NAME = "Development Tracking"
CATEGORY = "EYFS Learning & Development"

ID_PREFIX = "NDT"
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
AGE_BANDS = (
    "Birth to 12 months",
    "8 to 20 months",
    "16 to 26 months",
    "22 to 36 months",
    "30 to 50 months",
    "40 to 60+ months",
)
JUDGEMENTS = ("Emerging", "Developing", "Secure")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid development-tracking input."""


@dataclass
class DevRecord:
    record_id: str
    pupil_id: str
    area: str
    aspect: str | None
    age_band: str | None
    judgement: str | None
    assessment_date: str | None
    assessor: str | None
    next_steps: str | None
    notes: str | None
    created_at: str | None = None
    child_name: str | None = None
    room: str | None = None
    assessor_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for development tracking")
        raise


_SELECT = """
SELECT dt.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS assessor_name
FROM development_tracking dt
LEFT JOIN pupils p ON p.pupil_id = dt.pupil_id
LEFT JOIN staff s ON s.staff_id = dt.assessor
"""


def _row(r: sqlite3.Row) -> DevRecord:
    keys = r.keys()
    return DevRecord(
        record_id=r["record_id"],
        pupil_id=r["pupil_id"],
        area=r["area"],
        aspect=r["aspect"],
        age_band=r["age_band"],
        judgement=r["judgement"],
        assessment_date=r["assessment_date"],
        assessor=r["assessor"],
        next_steps=r["next_steps"],
        notes=r["notes"],
        created_at=r["created_at"] if "created_at" in keys else None,
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
        assessor_name=(r["assessor_name"] or None) if "assessor_name" in keys else None,
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

    area = (data.get("area") or "").strip()
    if not area:
        raise ValidationError("Area is required")
    if area not in AREAS:
        raise ValidationError("Area must be one of: " + ", ".join(AREAS))
    out["area"] = area

    out["aspect"] = _opt(data.get("aspect"))

    age_band = (data.get("age_band") or "").strip()
    if age_band and age_band not in AGE_BANDS:
        raise ValidationError("Age band must be one of: " + ", ".join(AGE_BANDS))
    out["age_band"] = age_band or None

    judgement = (data.get("judgement") or "").strip()
    if judgement and judgement not in JUDGEMENTS:
        raise ValidationError("Judgement must be one of: " + ", ".join(JUDGEMENTS))
    out["judgement"] = judgement or None

    out["assessment_date"] = _opt_date(data.get("assessment_date"), "Assessment date")
    out["assessor"] = _opt(data.get("assessor"))
    out["next_steps"] = _opt(data.get("next_steps"))
    out["notes"] = _opt(data.get("notes"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_record_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT record_id FROM development_tracking").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing development tracking ids")
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
    raise RuntimeError("Could not allocate a unique development tracking id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_records(*, pupil_id: str | None = None) -> list[DevRecord]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if pupil_id:
        sql += " WHERE dt.pupil_id = ?"
        params.append(pupil_id)
    sql += " ORDER BY dt.assessment_date DESC, dt.record_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    return [_row(r) for r in rows]


def get_record(record_id: str) -> DevRecord | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE dt.record_id = ?", (record_id,)).fetchone()
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

def create_record(data: dict[str, Any]) -> DevRecord:
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
                INSERT INTO development_tracking (
                    record_id, pupil_id, area, aspect, age_band, judgement,
                    assessment_date, assessor, next_steps, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["pupil_id"], payload["area"], payload["aspect"],
                 payload["age_band"], payload["judgement"],
                 payload["assessment_date"], payload["assessor"],
                 payload["next_steps"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for development tracking id=%s", rid)
        raise ValidationError(f"Could not create record — {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created development tracking record %s for pupil %s",
                rid, payload["pupil_id"])
    return rec


def update_record(record_id: str, data: dict[str, Any]) -> DevRecord:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE development_tracking SET
                    area = ?, aspect = ?, age_band = ?, judgement = ?,
                    assessment_date = ?, assessor = ?, next_steps = ?, notes = ?
                WHERE record_id = ?
                """,
                (payload["area"], payload["aspect"], payload["age_band"],
                 payload["judgement"], payload["assessment_date"],
                 payload["assessor"], payload["next_steps"], payload["notes"],
                 record_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(
                    f"No development tracking record with id {record_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for development tracking id=%s", record_id)
        raise ValidationError(f"Could not update record — {e}") from e
    rec = get_record(record_id)
    assert rec is not None
    logger.info("Updated development tracking record %s", record_id)
    return rec


def delete_record(record_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM development_tracking WHERE record_id = ?", (record_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting development tracking id=%s", record_id)
        raise
    if deleted:
        logger.info("Deleted development tracking record %s", record_id)
    return deleted
