"""Domain layer for SEND & Additional Needs (Nursery System).

Owns the ``send_records`` table — children on SEN Support or with additional
needs: the primary area of need, the SENCO, support level and plan. Created on
demand inside the shared nursery DB.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``send_cli.py``, Tk GUI in ``send_views.py``.
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

FEATURE_NAME = "SEND & Additional Needs"
CATEGORY = "Safeguarding & Welfare"

ID_PREFIX = "NSEN"
ID_DIGITS = 3

PRIMARY_NEEDS = (
    "Communication & interaction", "Cognition & learning",
    "Social, emotional & mental health", "Sensory &/or physical",
)
SUPPORT_LEVELS = ("Monitoring", "SEN Support", "EHC Plan")
STATUSES = ("active", "closed")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS send_records (
    record_id        TEXT PRIMARY KEY,
    pupil_id         TEXT NOT NULL,
    primary_need     TEXT,
    support_level    TEXT,
    senco            TEXT,
    start_date       TEXT,
    review_date      TEXT,
    support_plan     TEXT,
    external_agencies TEXT,
    status           TEXT NOT NULL DEFAULT 'active',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (senco) REFERENCES staff(staff_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_send_pupil ON send_records(pupil_id);
"""


class ValidationError(ValueError):
    """Raised for invalid SEND-record input."""


@dataclass
class SENDRecord:
    record_id: str
    pupil_id: str
    primary_need: str | None
    support_level: str | None
    senco: str | None
    start_date: str | None
    review_date: str | None
    support_plan: str | None
    external_agencies: str | None
    status: str
    notes: str | None
    child_name: str | None = None
    room: str | None = None
    senco_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
        with connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to initialise schema for SEND")
        raise


_SELECT = """
SELECT r.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) AS senco_name
FROM send_records r
LEFT JOIN pupils p ON p.pupil_id = r.pupil_id
LEFT JOIN staff s ON s.staff_id = r.senco
"""


def _row(r: sqlite3.Row) -> SENDRecord:
    keys = r.keys()
    return SENDRecord(
        record_id=r["record_id"], pupil_id=r["pupil_id"],
        primary_need=r["primary_need"], support_level=r["support_level"],
        senco=r["senco"], start_date=r["start_date"], review_date=r["review_date"],
        support_plan=r["support_plan"], external_agencies=r["external_agencies"],
        status=r["status"], notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
        senco_name=(r["senco_name"] or None) if "senco_name" in keys else None,
    )


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
    need = (data.get("primary_need") or "").strip()
    if need and need not in PRIMARY_NEEDS:
        raise ValidationError("Primary need must be one of: " + ", ".join(PRIMARY_NEEDS))
    out["primary_need"] = need or None
    level = (data.get("support_level") or "").strip()
    if level and level not in SUPPORT_LEVELS:
        raise ValidationError("Support level must be one of: " + ", ".join(SUPPORT_LEVELS))
    out["support_level"] = level or None
    out["senco"] = _opt(data.get("senco"))
    out["start_date"] = _opt_date(data.get("start_date"), "Start date")
    out["review_date"] = _opt_date(data.get("review_date"), "Review date")
    out["support_plan"] = _opt(data.get("support_plan"))
    out["external_agencies"] = _opt(data.get("external_agencies"))
    out["notes"] = _opt(data.get("notes"))
    status = (data.get("status") or "active").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    return out


def generate_record_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT record_id FROM send_records").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing SEND ids")
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
    raise RuntimeError("Could not allocate a unique SEND id")


def list_records(*, status: str | None = None) -> list[SENDRecord]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if status:
        sql += " WHERE r.status = ?"
        params.append(status)
    sql += " ORDER BY child_name, r.record_id"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    return [_row(r) for r in rows]


def get_record(record_id: str) -> SENDRecord | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE r.record_id = ?", (record_id,)).fetchone()
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


def summary() -> dict[str, int]:
    records = list_records()
    active = [r for r in records if r.status == "active"]
    ehcp = sum(1 for r in active if r.support_level == "EHC Plan")
    sen_support = sum(1 for r in active if r.support_level == "SEN Support")
    return {"total": len(records), "active": len(active),
            "ehc_plan": ehcp, "sen_support": sen_support}


def create_record(data: dict[str, Any]) -> SENDRecord:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    rid = generate_record_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO send_records (
                    record_id, pupil_id, primary_need, support_level, senco,
                    start_date, review_date, support_plan, external_agencies,
                    status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["pupil_id"], payload["primary_need"],
                 payload["support_level"], payload["senco"], payload["start_date"],
                 payload["review_date"], payload["support_plan"],
                 payload["external_agencies"], payload["status"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for SEND id=%s", rid)
        raise ValidationError(f"Could not create record — {e}") from e
    record = get_record(rid)
    assert record is not None
    logger.info("Created SEND record %s for pupil %s", rid, payload["pupil_id"])
    return record


def update_record(record_id: str, data: dict[str, Any]) -> SENDRecord:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE send_records SET
                    primary_need = ?, support_level = ?, senco = ?, start_date = ?,
                    review_date = ?, support_plan = ?, external_agencies = ?,
                    status = ?, notes = ?
                WHERE record_id = ?
                """,
                (payload["primary_need"], payload["support_level"], payload["senco"],
                 payload["start_date"], payload["review_date"],
                 payload["support_plan"], payload["external_agencies"],
                 payload["status"], payload["notes"], record_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No SEND record with id {record_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for SEND id=%s", record_id)
        raise ValidationError(f"Could not update record — {e}") from e
    record = get_record(record_id)
    assert record is not None
    logger.info("Updated SEND record %s", record_id)
    return record


def delete_record(record_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM send_records WHERE record_id = ?", (record_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting SEND id=%s", record_id)
        raise
    if deleted:
        logger.info("Deleted SEND record %s", record_id)
    return deleted
