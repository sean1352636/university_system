"""Domain layer for the Existing Injuries Log (Nursery System).

Owns the ``existing_injuries`` table — injuries a child arrives WITH (not
sustained at the setting). EYFS good practice is to log these on arrival with
the parent's explanation and a signature, to safeguard both the child and the
setting. Each record captures where/when the injury was observed, a body part,
a description, the parent's explanation, who observed it, and whether the
parent has been informed and has signed.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``existing_injuries_cli.py``, Tk GUI in ``existing_injuries_views.py``.
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

FEATURE_NAME = "Existing Injuries Log"
CATEGORY = "Daily Care & Routines"

ID_PREFIX = "NEI"
ID_DIGITS = 3

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid existing-injury input."""


@dataclass
class ExistingInjury:
    record_id: str
    pupil_id: str
    observed_date: str
    observed_time: str | None
    body_part: str | None
    description: str | None
    explanation: str | None
    observed_by: str | None
    parent_informed: int
    parent_signed: int
    notes: str | None
    child_name: str | None = None
    observed_by_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for existing injuries")
        raise


_SELECT = """
SELECT e.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       TRIM(s.first_name || ' ' || s.last_name) AS observed_by_name
FROM existing_injuries e
LEFT JOIN pupils p ON p.pupil_id = e.pupil_id
LEFT JOIN staff  s ON s.staff_id = e.observed_by
"""


def _row(r: sqlite3.Row) -> ExistingInjury:
    keys = r.keys()
    return ExistingInjury(
        record_id=r["record_id"],
        pupil_id=r["pupil_id"],
        observed_date=r["observed_date"],
        observed_time=r["observed_time"],
        body_part=r["body_part"],
        description=r["description"],
        explanation=r["explanation"],
        observed_by=r["observed_by"],
        parent_informed=r["parent_informed"],
        parent_signed=r["parent_signed"],
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        observed_by_name=r["observed_by_name"] if "observed_by_name" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _coerce_flag(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return 1 if value else 0
    raw = str(value).strip().lower()
    if not raw:
        return default
    return int(raw in ("1", "y", "yes", "true", "on"))


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    observed_date = (data.get("observed_date") or "").strip()
    if not observed_date:
        observed_date = _dt.date.today().isoformat()
    if not _DATE_RE.match(observed_date):
        raise ValidationError("Observed date must be YYYY-MM-DD")
    out["observed_date"] = observed_date

    observed_time = (data.get("observed_time") or "").strip()
    if observed_time and not _TIME_RE.match(observed_time):
        raise ValidationError("Observed time must be HH:MM")
    out["observed_time"] = observed_time or None

    out["body_part"] = _opt(data.get("body_part"))
    out["description"] = _opt(data.get("description"))
    out["explanation"] = _opt(data.get("explanation"))
    out["notes"] = _opt(data.get("notes"))
    out["observed_by"] = _opt(data.get("observed_by"))

    out["parent_informed"] = _coerce_flag(data.get("parent_informed"), 1)
    out["parent_signed"] = _coerce_flag(data.get("parent_signed"), 0)
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_record_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT record_id FROM existing_injuries").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing existing-injury ids")
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
    raise RuntimeError("Could not allocate a unique existing-injury id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_records(*, observed_date: str | None = None,
                 pupil_id: str | None = None) -> list[ExistingInjury]:
    _ensure_schema()
    sql = _SELECT
    clauses: list[str] = []
    params: list[Any] = []
    if observed_date:
        clauses.append("e.observed_date = ?")
        params.append(observed_date.strip())
    if pupil_id:
        clauses.append("e.pupil_id = ?")
        params.append(pupil_id.strip())
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY e.observed_date DESC, e.record_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    return [_row(r) for r in rows]


def get_record(record_id: str) -> ExistingInjury | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE e.record_id = ?", (record_id,)).fetchone()
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


def list_staff_choices() -> list[tuple[str, str]]:
    """Return ``(staff_id, "Name (id)")`` pairs for currently-employed staff."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name FROM staff "
                "WHERE end_date IS NULL OR end_date = '' "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    return [(r["staff_id"], f"{r['first_name']} {r['last_name']} ({r['staff_id']})")
            for r in rows]


# ── Writes ───────────────────────────────────────────────────────────────────

def create_record(data: dict[str, Any]) -> ExistingInjury:
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
                INSERT INTO existing_injuries (
                    record_id, pupil_id, observed_date, observed_time,
                    body_part, description, explanation, observed_by,
                    parent_informed, parent_signed, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["pupil_id"], payload["observed_date"],
                 payload["observed_time"], payload["body_part"],
                 payload["description"], payload["explanation"],
                 payload["observed_by"], payload["parent_informed"],
                 payload["parent_signed"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for existing-injury id=%s", rid)
        raise ValidationError(f"Could not create record — {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created existing-injury record %s for pupil %s",
                rid, payload["pupil_id"])
    return rec


def update_record(record_id: str, data: dict[str, Any]) -> ExistingInjury:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_record(record_id)
    if existing is None:
        raise ValidationError(f"No existing-injury record with id {record_id}")
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE existing_injuries SET
                    observed_date = ?, observed_time = ?, body_part = ?,
                    description = ?, explanation = ?, observed_by = ?,
                    parent_informed = ?, parent_signed = ?, notes = ?
                WHERE record_id = ?
                """,
                (payload["observed_date"], payload["observed_time"],
                 payload["body_part"], payload["description"],
                 payload["explanation"], payload["observed_by"],
                 payload["parent_informed"], payload["parent_signed"],
                 payload["notes"], record_id),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for existing-injury id=%s", record_id)
        raise ValidationError(f"Could not update record — {e}") from e
    rec = get_record(record_id)
    assert rec is not None
    logger.info("Updated existing-injury record %s", record_id)
    return rec


def delete_record(record_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM existing_injuries WHERE record_id = ?",
                (record_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting existing-injury id=%s", record_id)
        raise
    if deleted:
        logger.info("Deleted existing-injury record %s", record_id)
    return deleted
