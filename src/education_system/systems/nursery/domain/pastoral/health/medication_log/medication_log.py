"""Domain layer for Medication Log (Nursery System).

Owns the ``medication_log`` table — the record of medicine administered to a
child (and the prior parental consent). Each row captures the medicine, dose,
route, reason, when it was given and by whom, who witnessed it, whether written
parental consent is held, an optional expiry date, and a status (administered /
scheduled / refused).

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``medication_log_cli.py``, Tk GUI in ``medication_log_views.py``.
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

FEATURE_NAME = "Medication Log"
CATEGORY = "Daily Care & Routines"

ID_PREFIX = "NMD"
ID_DIGITS = 3

ROUTES = ("Oral", "Topical", "Inhaled", "Drops", "Other")
STATUSES = ("administered", "scheduled", "refused")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid medication-log input."""


@dataclass
class MedicationRecord:
    record_id: str
    pupil_id: str
    medication_name: str
    dose: str | None
    route: str | None
    reason: str | None
    administered_date: str | None
    administered_time: str | None
    administered_by: str | None
    witnessed_by: str | None
    parent_consent: int
    expiry_date: str | None
    status: str
    notes: str | None
    child_name: str | None = None
    administered_by_name: str | None = None
    witnessed_by_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for medication log")
        raise


_SELECT = """
SELECT m.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       TRIM(a.first_name || ' ' || a.last_name) AS administered_by_name,
       TRIM(w.first_name || ' ' || w.last_name) AS witnessed_by_name
FROM medication_log m
LEFT JOIN pupils p ON p.pupil_id = m.pupil_id
LEFT JOIN staff a ON a.staff_id = m.administered_by
LEFT JOIN staff w ON w.staff_id = m.witnessed_by
"""


def _row(r: sqlite3.Row) -> MedicationRecord:
    keys = r.keys()
    return MedicationRecord(
        record_id=r["record_id"],
        pupil_id=r["pupil_id"],
        medication_name=r["medication_name"],
        dose=r["dose"],
        route=r["route"],
        reason=r["reason"],
        administered_date=r["administered_date"],
        administered_time=r["administered_time"],
        administered_by=r["administered_by"],
        witnessed_by=r["witnessed_by"],
        parent_consent=int(r["parent_consent"] or 0),
        expiry_date=r["expiry_date"],
        status=r["status"],
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        administered_by_name=(
            r["administered_by_name"] if "administered_by_name" in keys else None),
        witnessed_by_name=(
            r["witnessed_by_name"] if "witnessed_by_name" in keys else None),
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

    name = (data.get("medication_name") or "").strip()
    if not name:
        raise ValidationError("Medication name is required")
    out["medication_name"] = name

    out["dose"] = _opt(data.get("dose"))
    out["reason"] = _opt(data.get("reason"))
    out["notes"] = _opt(data.get("notes"))

    route = (data.get("route") or "").strip() or "Oral"
    if route not in ROUTES:
        raise ValidationError("Route must be one of: " + ", ".join(ROUTES))
    out["route"] = route

    status = (data.get("status") or "administered").strip().lower()
    if status not in STATUSES:
        raise ValidationError("Status must be one of: " + ", ".join(STATUSES))
    out["status"] = status

    adate = (data.get("administered_date") or "").strip()
    out["administered_date"] = _opt_date(
        adate or _dt.date.today().isoformat(), "Administered date")

    atime = (data.get("administered_time") or "").strip()
    if atime and not _TIME_RE.match(atime):
        raise ValidationError("Administered time must be HH:MM")
    out["administered_time"] = atime or None

    out["expiry_date"] = _opt_date(data.get("expiry_date"), "Expiry date")

    consent = data.get("parent_consent")
    if isinstance(consent, (bool, int)):
        out["parent_consent"] = int(bool(consent))
    else:
        out["parent_consent"] = int(
            str(consent or "").strip().lower() in ("1", "y", "yes", "true", "on"))

    out["administered_by"] = _opt(data.get("administered_by"))
    out["witnessed_by"] = _opt(data.get("witnessed_by"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_record_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT record_id FROM medication_log").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing medication-log ids")
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
    raise RuntimeError("Could not allocate a unique medication-log id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_records(*, administered_date: str | None = None,
                 pupil_id: str | None = None,
                 status: str | None = None) -> list[MedicationRecord]:
    _ensure_schema()
    sql = _SELECT
    clauses: list[str] = []
    params: list[Any] = []
    if administered_date:
        clauses.append("m.administered_date = ?")
        params.append(administered_date)
    if pupil_id:
        clauses.append("m.pupil_id = ?")
        params.append(pupil_id)
    if status:
        clauses.append("m.status = ?")
        params.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY m.administered_date DESC, m.record_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    return [_row(r) for r in rows]


def get_record(record_id: str) -> MedicationRecord | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE m.record_id = ?", (record_id,)).fetchone()
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
    """Return ``(staff_id, "Name (id) — role")`` pairs for employed staff."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name, role FROM staff "
                "WHERE end_date IS NULL OR end_date = '' "
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


def summary() -> dict[str, Any]:
    """Totals for the header: record + status counts + no-consent count."""
    records = list_records()
    administered = sum(1 for r in records if r.status == "administered")
    scheduled = sum(1 for r in records if r.status == "scheduled")
    refused = sum(1 for r in records if r.status == "refused")
    no_consent = sum(1 for r in records
                     if r.status == "administered" and not r.parent_consent)
    return {"records": len(records), "administered": administered,
            "scheduled": scheduled, "refused": refused, "no_consent": no_consent}


# ── Writes ───────────────────────────────────────────────────────────────────

def create_record(data: dict[str, Any]) -> MedicationRecord:
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
                INSERT INTO medication_log (
                    record_id, pupil_id, medication_name, dose, route, reason,
                    administered_date, administered_time, administered_by,
                    witnessed_by, parent_consent, expiry_date, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["pupil_id"], payload["medication_name"],
                 payload["dose"], payload["route"], payload["reason"],
                 payload["administered_date"], payload["administered_time"],
                 payload["administered_by"], payload["witnessed_by"],
                 payload["parent_consent"], payload["expiry_date"],
                 payload["status"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for medication-log id=%s", rid)
        raise ValidationError(f"Could not create record — {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created medication-log record %s for pupil %s (%s)",
                rid, payload["pupil_id"], payload["medication_name"])
    return rec


def update_record(record_id: str, data: dict[str, Any]) -> MedicationRecord:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_record(record_id)
    if existing is None:
        raise ValidationError(f"No medication-log record with id {record_id}")
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE medication_log SET
                    medication_name = ?, dose = ?, route = ?, reason = ?,
                    administered_date = ?, administered_time = ?,
                    administered_by = ?, witnessed_by = ?, parent_consent = ?,
                    expiry_date = ?, status = ?, notes = ?
                WHERE record_id = ?
                """,
                (payload["medication_name"], payload["dose"], payload["route"],
                 payload["reason"], payload["administered_date"],
                 payload["administered_time"], payload["administered_by"],
                 payload["witnessed_by"], payload["parent_consent"],
                 payload["expiry_date"], payload["status"], payload["notes"],
                 record_id),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for medication-log id=%s", record_id)
        raise ValidationError(f"Could not update record — {e}") from e
    rec = get_record(record_id)
    assert rec is not None
    logger.info("Updated medication-log record %s", record_id)
    return rec


def delete_record(record_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM medication_log WHERE record_id = ?", (record_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting medication-log id=%s", record_id)
        raise
    if deleted:
        logger.info("Deleted medication-log record %s", record_id)
    return deleted


def set_status(record_id: str, status: str) -> MedicationRecord:
    _ensure_schema()
    status = (status or "").strip().lower()
    if status not in STATUSES:
        raise ValidationError("Status must be one of: " + ", ".join(STATUSES))
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE medication_log SET status = ? WHERE record_id = ?",
                (status, record_id))
            if cur.rowcount == 0:
                raise ValidationError(
                    f"No medication-log record with id {record_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Database error setting status for %s", record_id)
        raise
    rec = get_record(record_id)
    assert rec is not None
    return rec
