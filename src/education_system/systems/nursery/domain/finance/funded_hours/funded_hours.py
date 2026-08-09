"""Domain layer for Funded Hours (15/30 & 2-Year-Old) (Nursery System).

Owns the ``funded_hours_records`` table — the detailed funding entitlement
behind the simple ``pupils.funded_hours`` label. Captures the weekly funded
hours, any additional paid hours, the DfE eligibility code (30-hour / 2-year-old
funding), the eligibility window and the funding period, so funded-hours claims
can be evidenced and reconfirmed each term.

Creating / editing a record also writes the headline entitlement back to the
child's ``pupils.funded_hours`` so the Child Directory stays in step.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``funded_hours_cli.py``, Tk GUI in ``funded_hours_views.py``.
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

FEATURE_NAME = "Funded Hours (15/30 & 2-Year-Old)"
CATEGORY = "Children & Admissions"

ID_PREFIX = "NFH"
ID_DIGITS = 3

ENTITLEMENTS = ("15 hours", "30 hours", "2-year-old funding", "Private (unfunded)")
STATUSES = ("active", "ended")

# Default weekly funded hours suggested for each entitlement (term-time basis).
_DEFAULT_HOURS = {
    "15 hours": 15.0,
    "30 hours": 30.0,
    "2-year-old funding": 15.0,
    "Private (unfunded)": 0.0,
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid funded-hours input."""


@dataclass
class FundedHoursRecord:
    record_id: str
    pupil_id: str
    entitlement: str
    funded_hours_pw: float | None
    additional_hours: float | None
    eligibility_code: str | None
    eligibility_start: str | None
    eligibility_end: str | None
    funding_period: str | None
    stretched: bool
    notes: str | None
    status: str
    child_name: str | None = None
    room: str | None = None

    @property
    def total_hours(self) -> float:
        return (self.funded_hours_pw or 0.0) + (self.additional_hours or 0.0)


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for funded hours")
        raise


_SELECT = """
SELECT f.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room
FROM funded_hours_records f
LEFT JOIN pupils p ON p.pupil_id = f.pupil_id
"""


def _row(r: sqlite3.Row) -> FundedHoursRecord:
    keys = r.keys()
    return FundedHoursRecord(
        record_id=r["record_id"],
        pupil_id=r["pupil_id"],
        entitlement=r["entitlement"],
        funded_hours_pw=r["funded_hours_pw"],
        additional_hours=r["additional_hours"],
        eligibility_code=r["eligibility_code"],
        eligibility_start=r["eligibility_start"],
        eligibility_end=r["eligibility_end"],
        funding_period=r["funding_period"],
        stretched=bool(r["stretched"]),
        notes=r["notes"],
        status=r["status"],
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
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


def _opt_float(value: Any, label: str) -> float | None:
    raw = str(value if value is not None else "").strip()
    if not raw:
        return None
    try:
        n = float(raw)
    except ValueError as e:
        raise ValidationError(f"{label} must be a number") from e
    if n < 0:
        raise ValidationError(f"{label} cannot be negative")
    return n


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    entitlement = (data.get("entitlement") or "").strip()
    if entitlement not in ENTITLEMENTS:
        raise ValidationError(
            "Entitlement must be one of: " + ", ".join(ENTITLEMENTS))
    out["entitlement"] = entitlement

    hours = _opt_float(data.get("funded_hours_pw"), "Funded hours/week")
    out["funded_hours_pw"] = hours if hours is not None else _DEFAULT_HOURS.get(
        entitlement, 0.0)
    if out["funded_hours_pw"] > 50:
        raise ValidationError("Funded hours/week looks too high (max 50)")

    out["additional_hours"] = _opt_float(
        data.get("additional_hours"), "Additional hours/week") or 0.0

    code = _opt(data.get("eligibility_code"))
    if entitlement == "30 hours" and code and not re.fullmatch(r"\d{11}", code):
        raise ValidationError("A 30-hour eligibility code is 11 digits")
    out["eligibility_code"] = code

    out["eligibility_start"] = _opt_date(data.get("eligibility_start"),
                                         "Eligibility start")
    out["eligibility_end"] = _opt_date(data.get("eligibility_end"),
                                       "Eligibility end")
    out["funding_period"] = _opt(data.get("funding_period"))

    stretched = data.get("stretched")
    if isinstance(stretched, (bool, int)):
        out["stretched"] = int(bool(stretched))
    else:
        out["stretched"] = int(
            str(stretched or "").strip().lower() in ("1", "y", "yes", "true", "on"))

    out["notes"] = _opt(data.get("notes"))

    status = (data.get("status") or "active").strip().lower()
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
                "SELECT record_id FROM funded_hours_records").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing funded-hours ids")
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
    raise RuntimeError("Could not allocate a unique funded-hours id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_records(*, include_ended: bool = True) -> list[FundedHoursRecord]:
    _ensure_schema()
    sql = _SELECT
    params: tuple[Any, ...] = ()
    if not include_ended:
        sql += " WHERE f.status = ?"
        params = ("active",)
    sql += " ORDER BY child_name, f.record_id"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    return [_row(r) for r in rows]


def get_record(record_id: str) -> FundedHoursRecord | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE f.record_id = ?", (record_id,)).fetchone()
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
    """Totals for the header: record count + funded hours by entitlement."""
    records = [r for r in list_records() if r.status == "active"]
    by_ent: dict[str, int] = {}
    funded_total = 0.0
    for r in records:
        by_ent[r.entitlement] = by_ent.get(r.entitlement, 0) + 1
        funded_total += r.funded_hours_pw or 0.0
    return {"records": len(records), "funded_hours_total": funded_total,
            "by_entitlement": by_ent}


# ── Writes ───────────────────────────────────────────────────────────────────

def _sync_pupil_label(conn: sqlite3.Connection, pupil_id: str,
                      entitlement: str) -> None:
    """Keep the Child Directory's headline funded_hours label in step."""
    conn.execute("UPDATE pupils SET funded_hours = ? WHERE pupil_id = ?",
                 (entitlement, pupil_id))


def create_record(data: dict[str, Any]) -> FundedHoursRecord:
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
                INSERT INTO funded_hours_records (
                    record_id, pupil_id, entitlement, funded_hours_pw,
                    additional_hours, eligibility_code, eligibility_start,
                    eligibility_end, funding_period, stretched, notes, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["pupil_id"], payload["entitlement"],
                 payload["funded_hours_pw"], payload["additional_hours"],
                 payload["eligibility_code"], payload["eligibility_start"],
                 payload["eligibility_end"], payload["funding_period"],
                 payload["stretched"], payload["notes"], payload["status"]),
            )
            _sync_pupil_label(conn, payload["pupil_id"], payload["entitlement"])
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for funded-hours id=%s", rid)
        raise ValidationError(f"Could not create record — {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created funded-hours record %s for pupil %s (%s)",
                rid, payload["pupil_id"], payload["entitlement"])
    return rec


def update_record(record_id: str, data: dict[str, Any]) -> FundedHoursRecord:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_record(record_id)
    if existing is None:
        raise ValidationError(f"No funded-hours record with id {record_id}")
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE funded_hours_records SET
                    entitlement = ?, funded_hours_pw = ?, additional_hours = ?,
                    eligibility_code = ?, eligibility_start = ?,
                    eligibility_end = ?, funding_period = ?, stretched = ?,
                    notes = ?, status = ?
                WHERE record_id = ?
                """,
                (payload["entitlement"], payload["funded_hours_pw"],
                 payload["additional_hours"], payload["eligibility_code"],
                 payload["eligibility_start"], payload["eligibility_end"],
                 payload["funding_period"], payload["stretched"],
                 payload["notes"], payload["status"], record_id),
            )
            _sync_pupil_label(conn, existing.pupil_id, payload["entitlement"])
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for funded-hours id=%s", record_id)
        raise ValidationError(f"Could not update record — {e}") from e
    rec = get_record(record_id)
    assert rec is not None
    logger.info("Updated funded-hours record %s", record_id)
    return rec


def delete_record(record_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM funded_hours_records WHERE record_id = ?",
                (record_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting funded-hours id=%s", record_id)
        raise
    if deleted:
        logger.info("Deleted funded-hours record %s", record_id)
    return deleted


def set_status(record_id: str, status: str) -> FundedHoursRecord:
    _ensure_schema()
    status = (status or "").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE funded_hours_records SET status = ? WHERE record_id = ?",
                (status, record_id))
            if cur.rowcount == 0:
                raise ValidationError(f"No funded-hours record with id {record_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Database error setting status for %s", record_id)
        raise
    rec = get_record(record_id)
    assert rec is not None
    return rec
