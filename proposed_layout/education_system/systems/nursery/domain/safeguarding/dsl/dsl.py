"""Domain layer for Designated Safeguarding Lead (Nursery System).

Owns the ``dsl_register`` table — the setting's Designated Safeguarding Lead and
deputies, their DSL training and renewal dates. Saving or removing a record
syncs ``staff.is_dsl`` so the Staff Directory reflects who currently holds an
active DSL role. The table is created on demand inside the shared nursery DB.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``dsl_cli.py``, Tk GUI in ``dsl_views.py``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Designated Safeguarding Lead"
CATEGORY = "Safeguarding & Welfare"

ID_PREFIX = "NDSL"
ID_DIGITS = 3

DSL_ROLES = ("Lead DSL", "Deputy DSL", "DSL trained")
STATUSES = ("active", "inactive")
EXPIRING_WINDOW_DAYS = 90

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dsl_register (
    record_id       TEXT PRIMARY KEY,
    staff_id        TEXT NOT NULL,
    dsl_role        TEXT,
    is_lead         INTEGER NOT NULL DEFAULT 0,
    training_date   TEXT,
    training_expiry TEXT,
    contact_number  TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_dsl_staff ON dsl_register(staff_id);
"""


class ValidationError(ValueError):
    """Raised for invalid DSL-register input."""


@dataclass
class DSLRecord:
    record_id: str
    staff_id: str
    dsl_role: str | None
    is_lead: bool
    training_date: str | None
    training_expiry: str | None
    contact_number: str | None
    status: str
    notes: str | None
    staff_name: str | None = None

    @property
    def training_status(self) -> str:
        if not self.training_expiry:
            return "unknown"
        try:
            exp = _dt.date.fromisoformat(self.training_expiry)
        except ValueError:
            return "unknown"
        today = _dt.date.today()
        if exp < today:
            return "expired"
        if (exp - today).days <= EXPIRING_WINDOW_DAYS:
            return "expiring"
        return "valid"


def _ensure_schema() -> None:
    try:
        init_db()
        with connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to initialise schema for DSL register")
        raise


_SELECT = """
SELECT d.*,
       TRIM(s.first_name || ' ' || s.last_name) AS staff_name
FROM dsl_register d
LEFT JOIN staff s ON s.staff_id = d.staff_id
"""


def _row(r: sqlite3.Row) -> DSLRecord:
    keys = r.keys()
    return DSLRecord(
        record_id=r["record_id"],
        staff_id=r["staff_id"],
        dsl_role=r["dsl_role"],
        is_lead=bool(r["is_lead"]),
        training_date=r["training_date"],
        training_expiry=r["training_expiry"],
        contact_number=r["contact_number"],
        status=r["status"],
        notes=r["notes"],
        staff_name=r["staff_name"] if "staff_name" in keys else None,
    )


def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _opt_date(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if v and not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v or None


def _as_bool(value: Any) -> int:
    if isinstance(value, (bool, int)):
        return int(bool(value))
    return int(str(value or "").strip().lower() in ("1", "y", "yes", "true", "on"))


def _validate(data: dict[str, Any], *, require_staff: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_staff:
        sid = (data.get("staff_id") or "").strip()
        if not sid:
            raise ValidationError("Staff member is required")
        out["staff_id"] = sid
    role = (data.get("dsl_role") or "").strip()
    if role and role not in DSL_ROLES:
        raise ValidationError("Role must be one of: " + ", ".join(DSL_ROLES))
    out["dsl_role"] = role or None
    out["is_lead"] = _as_bool(data.get("is_lead")) or (1 if role == "Lead DSL" else 0)
    out["training_date"] = _opt_date(data.get("training_date"), "Training date")
    out["training_expiry"] = _opt_date(data.get("training_expiry"), "Training expiry")
    out["contact_number"] = _opt(data.get("contact_number"))
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
                "SELECT record_id FROM dsl_register").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing DSL ids")
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
    raise RuntimeError("Could not allocate a unique DSL id")


def list_records() -> list[DSLRecord]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                _SELECT + " ORDER BY d.is_lead DESC, staff_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    return [_row(r) for r in rows]


def get_record(record_id: str) -> DSLRecord | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE d.record_id = ?", (record_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_record(%s) failed", record_id)
        raise
    return _row(row) if row else None


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
    records = [r for r in list_records() if r.status == "active"]
    leads = sum(1 for r in records if r.is_lead)
    expiring = sum(1 for r in records if r.training_status in ("expiring", "expired"))
    return {"total": len(records), "leads": leads,
            "deputies": len(records) - leads, "training_due": expiring}


def _sync_staff_flag(conn: sqlite3.Connection, staff_id: str) -> None:
    active = conn.execute(
        "SELECT 1 FROM dsl_register WHERE staff_id = ? AND status = 'active' LIMIT 1",
        (staff_id,)).fetchone() is not None
    conn.execute("UPDATE staff SET is_dsl = ? WHERE staff_id = ?",
                 (int(active), staff_id))


def create_record(data: dict[str, Any]) -> DSLRecord:
    _ensure_schema()
    payload = _validate(data, require_staff=True)
    rid = generate_record_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM staff WHERE staff_id = ?",
                                (payload["staff_id"],)).fetchone():
                raise ValidationError(f"No staff member with id {payload['staff_id']}")
            conn.execute(
                """
                INSERT INTO dsl_register (
                    record_id, staff_id, dsl_role, is_lead, training_date,
                    training_expiry, contact_number, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["staff_id"], payload["dsl_role"], payload["is_lead"],
                 payload["training_date"], payload["training_expiry"],
                 payload["contact_number"], payload["status"], payload["notes"]),
            )
            _sync_staff_flag(conn, payload["staff_id"])
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for DSL id=%s", rid)
        raise ValidationError(f"Could not create DSL record — {e}") from e
    record = get_record(rid)
    assert record is not None
    logger.info("Created DSL record %s for staff %s", rid, payload["staff_id"])
    return record


def update_record(record_id: str, data: dict[str, Any]) -> DSLRecord:
    _ensure_schema()
    payload = _validate(data, require_staff=False)
    existing = get_record(record_id)
    if existing is None:
        raise ValidationError(f"No DSL record with id {record_id}")
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE dsl_register SET
                    dsl_role = ?, is_lead = ?, training_date = ?,
                    training_expiry = ?, contact_number = ?, status = ?, notes = ?
                WHERE record_id = ?
                """,
                (payload["dsl_role"], payload["is_lead"], payload["training_date"],
                 payload["training_expiry"], payload["contact_number"],
                 payload["status"], payload["notes"], record_id),
            )
            _sync_staff_flag(conn, existing.staff_id)
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for DSL id=%s", record_id)
        raise ValidationError(f"Could not update DSL record — {e}") from e
    record = get_record(record_id)
    assert record is not None
    logger.info("Updated DSL record %s", record_id)
    return record


def delete_record(record_id: str) -> bool:
    _ensure_schema()
    existing = get_record(record_id)
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM dsl_register WHERE record_id = ?", (record_id,))
            if existing is not None:
                _sync_staff_flag(conn, existing.staff_id)
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting DSL id=%s", record_id)
        raise
    if deleted:
        logger.info("Deleted DSL record %s", record_id)
    return deleted
