"""Domain layer for Qualifications & Training (Nursery System).

Owns the ``staff_training`` table — structured qualification / training records
behind the free-text ``staff.qualifications`` field. Each row captures the
course, level, awarding body, completion + expiry dates and a status, so
renewals (safeguarding, food hygiene, SENCO, etc.) can be planned. An effective
expiry state (valid / expiring soon / expired) is derived from ``expiry_date``.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``qualifications_cli.py``, Tk GUI in ``qualifications_views.py``.
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

FEATURE_NAME = "Qualifications & Training"
CATEGORY = "Staff & Ratios"

ID_PREFIX = "NQT"
ID_DIGITS = 3

STATUSES = ("valid", "in_progress", "expired")
# Days before expiry at which a still-valid record is flagged "expiring".
EXPIRING_WINDOW_DAYS = 60

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid training-record input."""


@dataclass
class TrainingRecord:
    record_id: str
    staff_id: str
    course: str
    level: str | None
    awarding_body: str | None
    completed_date: str | None
    expiry_date: str | None
    certificate_ref: str | None
    status: str
    notes: str | None
    staff_name: str | None = None
    staff_role: str | None = None

    @property
    def expiry_status(self) -> str:
        """Effective state: in_progress / expired / expiring / valid."""
        if self.status == "in_progress":
            return "in_progress"
        if not self.expiry_date:
            return "valid"
        try:
            exp = _dt.date.fromisoformat(self.expiry_date)
        except ValueError:
            return self.status
        today = _dt.date.today()
        if exp < today:
            return "expired"
        if (exp - today).days <= EXPIRING_WINDOW_DAYS:
            return "expiring"
        return "valid"


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for training")
        raise


_SELECT = """
SELECT t.*,
       TRIM(s.first_name || ' ' || s.last_name) AS staff_name,
       s.role AS staff_role
FROM staff_training t
LEFT JOIN staff s ON s.staff_id = t.staff_id
"""


def _row(r: sqlite3.Row) -> TrainingRecord:
    keys = r.keys()
    return TrainingRecord(
        record_id=r["record_id"],
        staff_id=r["staff_id"],
        course=r["course"],
        level=r["level"],
        awarding_body=r["awarding_body"],
        completed_date=r["completed_date"],
        expiry_date=r["expiry_date"],
        certificate_ref=r["certificate_ref"],
        status=r["status"],
        notes=r["notes"],
        staff_name=r["staff_name"] if "staff_name" in keys else None,
        staff_role=r["staff_role"] if "staff_role" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _require(value: str | None, label: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _opt_date(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if v and not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v or None


def _validate(data: dict[str, Any], *, require_staff: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_staff:
        out["staff_id"] = _require(data.get("staff_id"), "Staff member")
    out["course"] = _require(data.get("course"), "Course / qualification")
    out["level"] = _opt(data.get("level"))
    out["awarding_body"] = _opt(data.get("awarding_body"))
    out["completed_date"] = _opt_date(data.get("completed_date"), "Completed date")
    out["expiry_date"] = _opt_date(data.get("expiry_date"), "Expiry date")
    out["certificate_ref"] = _opt(data.get("certificate_ref"))
    out["notes"] = _opt(data.get("notes"))
    status = (data.get("status") or "valid").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_record_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT record_id FROM staff_training").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing training ids")
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
    raise RuntimeError("Could not allocate a unique training id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_records(*, staff_id: str | None = None) -> list[TrainingRecord]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if staff_id:
        sql += " WHERE t.staff_id = ?"
        params.append(staff_id)
    sql += " ORDER BY staff_name, t.course"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    return [_row(r) for r in rows]


def get_record(record_id: str) -> TrainingRecord | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE t.record_id = ?", (record_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_record(%s) failed", record_id)
        raise
    return _row(row) if row else None


def list_expiring(*, include_expired: bool = True) -> list[TrainingRecord]:
    """Records that are expired or within the expiring window."""
    states = {"expired", "expiring"} if include_expired else {"expiring"}
    return [r for r in list_records() if r.expiry_status in states]


def list_staff_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name, role FROM staff "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    out = []
    for r in rows:
        role = f" — {r['role']}" if r["role"] else ""
        out.append((r["staff_id"],
                    f"{r['first_name']} {r['last_name']} ({r['staff_id']}){role}"))
    return out


def summary() -> dict[str, int]:
    records = list_records()
    valid = sum(1 for r in records if r.expiry_status == "valid")
    expiring = sum(1 for r in records if r.expiry_status == "expiring")
    expired = sum(1 for r in records if r.expiry_status == "expired")
    in_progress = sum(1 for r in records if r.expiry_status == "in_progress")
    return {"total": len(records), "valid": valid, "expiring": expiring,
            "expired": expired, "in_progress": in_progress}


# ── Writes ───────────────────────────────────────────────────────────────────

def create_record(data: dict[str, Any]) -> TrainingRecord:
    _ensure_schema()
    payload = _validate(data, require_staff=True)
    rid = generate_record_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM staff WHERE staff_id = ?",
                                (payload["staff_id"],)).fetchone():
                raise ValidationError(
                    f"No staff member with id {payload['staff_id']}")
            conn.execute(
                """
                INSERT INTO staff_training (
                    record_id, staff_id, course, level, awarding_body,
                    completed_date, expiry_date, certificate_ref, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["staff_id"], payload["course"], payload["level"],
                 payload["awarding_body"], payload["completed_date"],
                 payload["expiry_date"], payload["certificate_ref"],
                 payload["status"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for training id=%s", rid)
        raise ValidationError(f"Could not create record — {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created training record %s for staff %s", rid, payload["staff_id"])
    return rec


def update_record(record_id: str, data: dict[str, Any]) -> TrainingRecord:
    _ensure_schema()
    payload = _validate(data, require_staff=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE staff_training SET
                    course = ?, level = ?, awarding_body = ?, completed_date = ?,
                    expiry_date = ?, certificate_ref = ?, status = ?, notes = ?
                WHERE record_id = ?
                """,
                (payload["course"], payload["level"], payload["awarding_body"],
                 payload["completed_date"], payload["expiry_date"],
                 payload["certificate_ref"], payload["status"], payload["notes"],
                 record_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No training record with id {record_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for training id=%s", record_id)
        raise ValidationError(f"Could not update record — {e}") from e
    rec = get_record(record_id)
    assert rec is not None
    logger.info("Updated training record %s", record_id)
    return rec


def delete_record(record_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM staff_training WHERE record_id = ?", (record_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting training id=%s", record_id)
        raise
    if deleted:
        logger.info("Deleted training record %s", record_id)
    return deleted
