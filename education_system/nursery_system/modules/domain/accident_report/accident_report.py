"""Domain layer for the Accident / Incident Report (Nursery System).

Owns the ``accident_records`` table — the statutory accident / incident /
near-miss register. EYFS requires a written record of accidents, injuries and
first aid given, with parents informed the same day; serious injuries may be
RIDDOR-reportable. Each row links a child, what happened, the injury + body
part, the treatment given + first-aider, whether the parent was informed /
signed and whether it is RIDDOR-reportable, plus an open → closed workflow.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``accident_report_cli.py``, Tk GUI in ``accident_report_views.py``.
"""

from __future__ import annotations

import csv
import datetime as _dt
import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.nursery_system.core import paths
from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Accident / Incident Report"
CATEGORY = "Compliance & Reports"

ID_PREFIX = "NAC"
ID_DIGITS = 3

RECORD_TYPES = ("accident", "incident", "near-miss")
SEVERITIES = ("minor", "moderate", "major")
STATUSES = ("open", "closed")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_TRUE = ("1", "y", "yes", "true", "on")


class ValidationError(ValueError):
    """Raised for invalid accident / incident input."""


@dataclass
class AccidentRecord:
    record_id: str
    pupil_id: str
    record_type: str
    occurred_date: str | None
    occurred_time: str | None
    location: str | None
    description: str | None
    injury: str | None
    body_part: str | None
    treatment: str | None
    first_aider: str | None
    severity: str
    parent_informed: bool
    parent_signed: bool
    riddor_reportable: bool
    action_taken: str | None
    recorded_by: str | None
    status: str
    notes: str | None
    child_name: str | None = None
    first_aider_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for accident report")
        raise


_SELECT = """
SELECT a.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       TRIM(s.first_name || ' ' || s.last_name) AS first_aider_name
FROM accident_records a
LEFT JOIN pupils p ON p.pupil_id = a.pupil_id
LEFT JOIN staff  s ON s.staff_id = a.first_aider
"""


def _row(r: sqlite3.Row) -> AccidentRecord:
    keys = r.keys()
    return AccidentRecord(
        record_id=r["record_id"],
        pupil_id=r["pupil_id"],
        record_type=r["record_type"],
        occurred_date=r["occurred_date"],
        occurred_time=r["occurred_time"],
        location=r["location"],
        description=r["description"],
        injury=r["injury"],
        body_part=r["body_part"],
        treatment=r["treatment"],
        first_aider=r["first_aider"],
        severity=r["severity"],
        parent_informed=bool(r["parent_informed"]),
        parent_signed=bool(r["parent_signed"]),
        riddor_reportable=bool(r["riddor_reportable"]),
        action_taken=r["action_taken"],
        recorded_by=r["recorded_by"],
        status=r["status"],
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
        first_aider_name=r["first_aider_name"] if "first_aider_name" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _bool(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return int(bool(value))
    return int(str(value or "").strip().lower() in _TRUE)


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    record_type = (data.get("record_type") or "accident").strip().lower()
    if record_type not in RECORD_TYPES:
        raise ValidationError("Type must be one of: " + ", ".join(RECORD_TYPES))
    out["record_type"] = record_type

    severity = (data.get("severity") or "minor").strip().lower()
    if severity not in SEVERITIES:
        raise ValidationError("Severity must be one of: " + ", ".join(SEVERITIES))
    out["severity"] = severity

    status = (data.get("status") or "open").strip().lower()
    if status not in STATUSES:
        raise ValidationError("Status must be one of: " + ", ".join(STATUSES))
    out["status"] = status

    occurred_date = (data.get("occurred_date") or "").strip()
    if occurred_date and not _DATE_RE.match(occurred_date):
        raise ValidationError("Date must be YYYY-MM-DD")
    out["occurred_date"] = occurred_date or None

    occurred_time = (data.get("occurred_time") or "").strip()
    if occurred_time and not _TIME_RE.match(occurred_time):
        raise ValidationError("Time must be HH:MM")
    out["occurred_time"] = occurred_time or None

    out["location"] = _opt(data.get("location"))
    out["description"] = _opt(data.get("description"))
    out["injury"] = _opt(data.get("injury"))
    out["body_part"] = _opt(data.get("body_part"))
    out["treatment"] = _opt(data.get("treatment"))
    out["action_taken"] = _opt(data.get("action_taken"))
    out["recorded_by"] = _opt(data.get("recorded_by"))
    out["notes"] = _opt(data.get("notes"))

    out["parent_informed"] = _bool(data.get("parent_informed"))
    out["parent_signed"] = _bool(data.get("parent_signed"))
    out["riddor_reportable"] = _bool(data.get("riddor_reportable"))

    first_aider = _opt(data.get("first_aider"))
    if first_aider:
        try:
            with connect() as conn:
                if not conn.execute(
                        "SELECT 1 FROM staff WHERE staff_id = ?",
                        (first_aider,)).fetchone():
                    logger.warning("First-aider %s not found in staff", first_aider)
        except sqlite3.Error:
            logger.debug("Could not verify first-aider id", exc_info=True)
    out["first_aider"] = first_aider
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_record_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT record_id FROM accident_records").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing accident ids")
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
    raise RuntimeError("Could not allocate a unique accident id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_records(*, record_type: str | None = None, status: str | None = None,
                 riddor_only: bool = False) -> list[AccidentRecord]:
    _ensure_schema()
    sql = _SELECT
    clauses: list[str] = []
    params: list[Any] = []
    if record_type:
        clauses.append("a.record_type = ?")
        params.append(record_type)
    if status:
        clauses.append("a.status = ?")
        params.append(status)
    if riddor_only:
        clauses.append("a.riddor_reportable = 1")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY a.occurred_date DESC, a.record_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    return [_row(r) for r in rows]


def get_record(record_id: str) -> AccidentRecord | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE a.record_id = ?", (record_id,)).fetchone()
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
    """Return ``(staff_id, "Name (id) — role")`` pairs for first-aider pickers."""
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
    records = list_records()
    total = len(records)
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    open_count = 0
    riddor_count = 0
    parent_informed_count = 0
    for r in records:
        by_type[r.record_type] = by_type.get(r.record_type, 0) + 1
        by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
        if r.status == "open":
            open_count += 1
        if r.riddor_reportable:
            riddor_count += 1
        if r.parent_informed:
            parent_informed_count += 1
    cutoff = (_dt.date.today() - _dt.timedelta(days=30)).isoformat()
    last_30 = sum(1 for r in records if r.occurred_date and r.occurred_date >= cutoff)
    rate = round(parent_informed_count / total * 100, 1) if total else 0.0
    return {
        "total": total,
        "by_type": by_type,
        "by_severity": by_severity,
        "open_count": open_count,
        "riddor_count": riddor_count,
        "parent_informed_count": parent_informed_count,
        "parent_informed_rate": rate,
        "last_30_days": last_30,
    }


# ── Writes ───────────────────────────────────────────────────────────────────

def create_record(data: dict[str, Any]) -> AccidentRecord:
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
                INSERT INTO accident_records (
                    record_id, pupil_id, record_type, occurred_date, occurred_time,
                    location, description, injury, body_part, treatment,
                    first_aider, severity, parent_informed, parent_signed,
                    riddor_reportable, action_taken, recorded_by, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["pupil_id"], payload["record_type"],
                 payload["occurred_date"], payload["occurred_time"],
                 payload["location"], payload["description"], payload["injury"],
                 payload["body_part"], payload["treatment"], payload["first_aider"],
                 payload["severity"], payload["parent_informed"],
                 payload["parent_signed"], payload["riddor_reportable"],
                 payload["action_taken"], payload["recorded_by"], payload["status"],
                 payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for accident id=%s", rid)
        raise ValidationError(f"Could not create record — {e}") from e
    rec = get_record(rid)
    assert rec is not None
    logger.info("Created accident record %s for pupil %s (%s)",
                rid, payload["pupil_id"], payload["record_type"])
    return rec


def update_record(record_id: str, data: dict[str, Any]) -> AccidentRecord:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_record(record_id)
    if existing is None:
        raise ValidationError(f"No accident record with id {record_id}")
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE accident_records SET
                    record_type = ?, occurred_date = ?, occurred_time = ?,
                    location = ?, description = ?, injury = ?, body_part = ?,
                    treatment = ?, first_aider = ?, severity = ?,
                    parent_informed = ?, parent_signed = ?, riddor_reportable = ?,
                    action_taken = ?, recorded_by = ?, status = ?, notes = ?
                WHERE record_id = ?
                """,
                (payload["record_type"], payload["occurred_date"],
                 payload["occurred_time"], payload["location"],
                 payload["description"], payload["injury"], payload["body_part"],
                 payload["treatment"], payload["first_aider"], payload["severity"],
                 payload["parent_informed"], payload["parent_signed"],
                 payload["riddor_reportable"], payload["action_taken"],
                 payload["recorded_by"], payload["status"], payload["notes"],
                 record_id),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for accident id=%s", record_id)
        raise ValidationError(f"Could not update record — {e}") from e
    rec = get_record(record_id)
    assert rec is not None
    logger.info("Updated accident record %s", record_id)
    return rec


def delete_record(record_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM accident_records WHERE record_id = ?", (record_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting accident id=%s", record_id)
        raise
    if deleted:
        logger.info("Deleted accident record %s", record_id)
    return deleted


def set_status(record_id: str, status: str) -> AccidentRecord:
    _ensure_schema()
    status = (status or "").strip().lower()
    if status not in STATUSES:
        raise ValidationError("Status must be one of: " + ", ".join(STATUSES))
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE accident_records SET status = ? WHERE record_id = ?",
                (status, record_id))
            if cur.rowcount == 0:
                raise ValidationError(f"No accident record with id {record_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Database error setting status for %s", record_id)
        raise
    rec = get_record(record_id)
    assert rec is not None
    return rec


# ── Export ───────────────────────────────────────────────────────────────────

def export_csv(path: str | Path | None = None) -> dict[str, object]:
    """Write all accident / incident records to CSV; return path + row count."""
    rows = list_records()
    if path is None:
        paths.ensure_directories()
        path = paths.DATA_DIR / (
            f"accident_report_{_dt.date.today().isoformat()}.csv")
    path = Path(path)
    headers = [
        "record_id", "pupil_id", "child_name", "record_type", "occurred_date",
        "occurred_time", "location", "description", "injury", "body_part",
        "treatment", "first_aider", "first_aider_name", "severity",
        "parent_informed", "parent_signed", "riddor_reportable", "action_taken",
        "recorded_by", "status", "notes",
    ]
    try:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for r in rows:
                w.writerow([
                    r.record_id, r.pupil_id, r.child_name or "", r.record_type,
                    r.occurred_date or "", r.occurred_time or "", r.location or "",
                    r.description or "", r.injury or "", r.body_part or "",
                    r.treatment or "", r.first_aider or "", r.first_aider_name or "",
                    r.severity, int(r.parent_informed), int(r.parent_signed),
                    int(r.riddor_reportable), r.action_taken or "",
                    r.recorded_by or "", r.status, r.notes or "",
                ])
    except OSError as e:
        logger.exception("Could not write accident CSV to %s", path)
        raise OSError(f"Could not write report — {e}") from e
    return {"path": str(path), "row_count": len(rows)}
