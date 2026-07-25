"""Domain layer for Allergies & Dietary Requirements (Nursery System).

Owns the ``dietary_requirements`` table — the structured allergy / intolerance
/ dietary register behind the free-text ``pupils.allergies`` label. Each row
captures the category, allergen, severity, the reaction and the action required
(e.g. EpiPen) plus a care-plan reference, so kitchen and room staff have an
auditable care plan per child.

Creating / editing / removing a record also recomputes the child's
``pupils.allergies`` summary (a comma-joined list of active allergens) so the
Child Directory stays in step.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``allergies_cli.py``, Tk GUI in ``allergies_views.py``.
"""

from __future__ import annotations

import logging
import random
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Allergies & Dietary Requirements"
CATEGORY = "Daily Care & Routines"

ID_PREFIX = "NDR"
ID_DIGITS = 3

CATEGORIES = ("allergy", "intolerance", "dietary", "preference", "medical")
SEVERITIES = ("mild", "moderate", "severe", "anaphylaxis")
STATUSES = ("active", "resolved")


class ValidationError(ValueError):
    """Raised for invalid dietary-requirement input."""


@dataclass
class DietaryRecord:
    record_id: str
    pupil_id: str
    category: str
    allergen: str | None
    severity: str | None
    reaction: str | None
    action_required: str | None
    epipen_required: int
    care_plan_ref: str | None
    status: str
    notes: str | None
    child_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for allergies")
        raise


_SELECT = """
SELECT d.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name
FROM dietary_requirements d
LEFT JOIN pupils p ON p.pupil_id = d.pupil_id
"""


def _row(r: sqlite3.Row) -> DietaryRecord:
    keys = r.keys()
    return DietaryRecord(
        record_id=r["record_id"],
        pupil_id=r["pupil_id"],
        category=r["category"],
        allergen=r["allergen"],
        severity=r["severity"],
        reaction=r["reaction"],
        action_required=r["action_required"],
        epipen_required=int(r["epipen_required"] or 0),
        care_plan_ref=r["care_plan_ref"],
        status=r["status"],
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _coerce_bool(value: Any) -> int:
    if isinstance(value, (bool, int)):
        return int(bool(value))
    return int(str(value or "").strip().lower() in ("1", "y", "yes", "true", "on"))


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    category = (data.get("category") or "allergy").strip().lower()
    if category not in CATEGORIES:
        raise ValidationError("Category must be one of: " + ", ".join(CATEGORIES))
    out["category"] = category

    severity = (data.get("severity") or "").strip().lower()
    if severity and severity not in SEVERITIES:
        raise ValidationError("Severity must be one of: " + ", ".join(SEVERITIES))
    out["severity"] = severity or None

    status = (data.get("status") or "active").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status

    out["epipen_required"] = _coerce_bool(data.get("epipen_required"))
    out["allergen"] = _opt(data.get("allergen"))
    out["reaction"] = _opt(data.get("reaction"))
    out["action_required"] = _opt(data.get("action_required"))
    out["care_plan_ref"] = _opt(data.get("care_plan_ref"))
    out["notes"] = _opt(data.get("notes"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_record_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT record_id FROM dietary_requirements").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing dietary ids")
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
    raise RuntimeError("Could not allocate a unique dietary id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_records(*, pupil_id: str | None = None, status: str | None = None,
                 category: str | None = None) -> list[DietaryRecord]:
    _ensure_schema()
    sql = _SELECT
    clauses: list[str] = []
    params: list[Any] = []
    if pupil_id:
        clauses.append("d.pupil_id = ?")
        params.append(pupil_id)
    if status:
        clauses.append("d.status = ?")
        params.append(status)
    if category:
        clauses.append("d.category = ?")
        params.append(category)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY child_name, d.record_id"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    return [_row(r) for r in rows]


def get_record(record_id: str) -> DietaryRecord | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE d.record_id = ?", (record_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_record(%s) failed", record_id)
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


def summary() -> dict[str, Any]:
    """Header totals across active records."""
    records = [r for r in list_records() if r.status == "active"]
    by_category: dict[str, int] = {}
    epipen_pupils: set[str] = set()
    anaphylaxis = 0
    for r in records:
        by_category[r.category] = by_category.get(r.category, 0) + 1
        if r.epipen_required:
            epipen_pupils.add(r.pupil_id)
        if r.severity == "anaphylaxis":
            anaphylaxis += 1
    return {"records": len(records), "epipen_children": len(epipen_pupils),
            "by_category": by_category, "anaphylaxis": anaphylaxis}


# ── Writes ───────────────────────────────────────────────────────────────────

def _sync_pupil_allergies(conn: sqlite3.Connection, pupil_id: str) -> None:
    """Recompute ``pupils.allergies`` as a comma-joined list of active allergens."""
    rows = conn.execute(
        "SELECT allergen FROM dietary_requirements "
        "WHERE pupil_id = ? AND status = 'active' AND allergen IS NOT NULL "
        "ORDER BY allergen", (pupil_id,)).fetchall()
    allergens = [r[0] for r in rows if (r[0] or "").strip()]
    summary_text = ", ".join(allergens) if allergens else "None"
    conn.execute("UPDATE pupils SET allergies = ? WHERE pupil_id = ?",
                 (summary_text, pupil_id))


def create_record(data: dict[str, Any]) -> DietaryRecord:
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
                INSERT INTO dietary_requirements (
                    record_id, pupil_id, category, allergen, severity, reaction,
                    action_required, epipen_required, care_plan_ref, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["pupil_id"], payload["category"], payload["allergen"],
                 payload["severity"], payload["reaction"], payload["action_required"],
                 payload["epipen_required"], payload["care_plan_ref"],
                 payload["status"], payload["notes"]),
            )
            _sync_pupil_allergies(conn, payload["pupil_id"])
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for dietary id=%s", rid)
        raise ValidationError(f"Could not create record — {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created dietary record %s for pupil %s (%s)",
                rid, payload["pupil_id"], payload["category"])
    return rec


def update_record(record_id: str, data: dict[str, Any]) -> DietaryRecord:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_record(record_id)
    if existing is None:
        raise ValidationError(f"No dietary record with id {record_id}")
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE dietary_requirements SET
                    category = ?, allergen = ?, severity = ?, reaction = ?,
                    action_required = ?, epipen_required = ?, care_plan_ref = ?,
                    status = ?, notes = ?
                WHERE record_id = ?
                """,
                (payload["category"], payload["allergen"], payload["severity"],
                 payload["reaction"], payload["action_required"],
                 payload["epipen_required"], payload["care_plan_ref"],
                 payload["status"], payload["notes"], record_id),
            )
            _sync_pupil_allergies(conn, existing.pupil_id)
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for dietary id=%s", record_id)
        raise ValidationError(f"Could not update record — {e}") from e
    rec = get_record(record_id)
    assert rec is not None
    logger.info("Updated dietary record %s", record_id)
    return rec


def delete_record(record_id: str) -> bool:
    _ensure_schema()
    existing = get_record(record_id)
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM dietary_requirements WHERE record_id = ?",
                (record_id,))
            deleted = cur.rowcount > 0
            if deleted and existing is not None:
                _sync_pupil_allergies(conn, existing.pupil_id)
            conn.commit()
    except sqlite3.Error:
        logger.exception("Database error deleting dietary id=%s", record_id)
        raise
    if deleted:
        logger.info("Deleted dietary record %s", record_id)
    return deleted


def set_status(record_id: str, status: str) -> DietaryRecord:
    _ensure_schema()
    status = (status or "").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    existing = get_record(record_id)
    if existing is None:
        raise ValidationError(f"No dietary record with id {record_id}")
    try:
        with connect() as conn:
            conn.execute(
                "UPDATE dietary_requirements SET status = ? WHERE record_id = ?",
                (status, record_id))
            _sync_pupil_allergies(conn, existing.pupil_id)
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Database error setting status for %s", record_id)
        raise
    rec = get_record(record_id)
    assert rec is not None
    return rec
