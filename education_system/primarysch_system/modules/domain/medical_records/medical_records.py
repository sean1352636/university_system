"""Medical records data layer.

One row per medical record. A pupil can have many records — allergies,
chronic conditions, current medications, dietary requirements,
one-off injuries, immunisations, etc. Each record has a severity
marker so safeguarding-critical entries can be surfaced quickly.

This data is sensitive. The data layer keeps logs at INFO level by
record id only (no clinical detail) so the application log is not a
back door into private medical content.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.primarysch_system.modules.domain.pupils import (
    pupils as pupils_data,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
    Pupil, ValidationError, YEAR_GROUPS,
    _connect as _pupils_connect, _DOB_RE,
)

logger = logging.getLogger(__name__)

RECORD_TYPES: tuple[str, ...] = (
    "allergy", "condition", "medication", "dietary",
    "injury", "immunisation", "other",
)
RECORD_TYPE_LABELS: dict[str, str] = {
    "allergy":      "Allergy",
    "condition":    "Medical condition",
    "medication":   "Medication / prescription",
    "dietary":      "Dietary requirement",
    "injury":       "Injury / accident",
    "immunisation": "Immunisation",
    "other":        "Other",
}

SEVERITIES: tuple[str, ...] = ("low", "medium", "high", "critical")
SEVERITY_LABELS: dict[str, str] = {
    "low":      "Low",
    "medium":   "Medium",
    "high":     "High",
    "critical": "Critical — may need emergency response",
}

_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS medical_records (
    record_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id       TEXT NOT NULL,
    record_type    TEXT NOT NULL,
    title          TEXT NOT NULL,
    description    TEXT,
    severity       TEXT NOT NULL DEFAULT 'low',
    start_date     TEXT,
    end_date       TEXT,
    action_plan    TEXT,
    contact_name   TEXT,
    contact_phone  TEXT,
    is_active      INTEGER NOT NULL DEFAULT 1,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_med_pupil    ON medical_records(pupil_id);
CREATE INDEX IF NOT EXISTS idx_med_type     ON medical_records(record_type);
CREATE INDEX IF NOT EXISTS idx_med_severity ON medical_records(severity);
CREATE INDEX IF NOT EXISTS idx_med_active   ON medical_records(is_active);
"""


@dataclass
class MedicalRecord:
    record_id: int
    pupil_id: str
    record_type: str
    title: str
    description: str | None
    severity: str
    start_date: str | None
    end_date: str | None
    action_plan: str | None
    contact_name: str | None
    contact_phone: str | None
    is_active: bool
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def is_critical(self) -> bool:
        return self.severity == "critical"


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    pupils_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise medical_records table")
        raise
    logger.info("Primary medical_records table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> MedicalRecord:
    return MedicalRecord(
        record_id=r["record_id"],
        pupil_id=r["pupil_id"],
        record_type=r["record_type"],
        title=r["title"],
        description=r["description"],
        severity=r["severity"],
        start_date=r["start_date"],
        end_date=r["end_date"],
        action_plan=r["action_plan"],
        contact_name=r["contact_name"],
        contact_phone=r["contact_phone"],
        is_active=bool(r["is_active"]),
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    out["pupil_id"] = pid
    rt = (data.get("record_type") or "").strip().lower()
    if not rt:
        raise ValidationError("Record type is required")
    if rt not in RECORD_TYPES:
        raise ValidationError(
            f"Record type must be one of {', '.join(RECORD_TYPES)}")
    out["record_type"] = rt
    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    if len(title) > 100:
        raise ValidationError("Title must be 100 characters or fewer")
    out["title"] = title
    out["description"] = (data.get("description") or "").strip() or None
    sev = (data.get("severity") or "low").strip().lower() or "low"
    if sev not in SEVERITIES:
        raise ValidationError(
            f"Severity must be one of {', '.join(SEVERITIES)}")
    out["severity"] = sev
    sd = (data.get("start_date") or "").strip()
    if sd and not _DOB_RE.match(sd):
        raise ValidationError("Start date must be YYYY-MM-DD")
    ed = (data.get("end_date") or "").strip()
    if ed and not _DOB_RE.match(ed):
        raise ValidationError("End date must be YYYY-MM-DD")
    if sd and ed and ed < sd:
        raise ValidationError("End date cannot be before start date")
    out["start_date"] = sd or None
    out["end_date"] = ed or None
    out["action_plan"]   = (data.get("action_plan") or "").strip() or None
    out["contact_name"]  = (data.get("contact_name") or "").strip() or None
    phone = (data.get("contact_phone") or "").strip()
    if phone and not _PHONE_RE.match(phone):
        raise ValidationError("Contact phone contains invalid characters")
    out["contact_phone"] = phone or None
    is_active = data.get("is_active")
    out["is_active"] = True if is_active is None else bool(is_active)
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> MedicalRecord:
    init_db()
    payload = _validate(data)
    if pupils_data.get_pupil(payload["pupil_id"]) is None:
        raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO medical_records
                       (pupil_id, record_type, title, description, severity,
                        start_date, end_date, action_plan,
                        contact_name, contact_phone, is_active, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["record_type"], payload["title"],
                 payload["description"], payload["severity"],
                 payload["start_date"], payload["end_date"],
                 payload["action_plan"], payload["contact_name"],
                 payload["contact_phone"],
                 1 if payload["is_active"] else 0, payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create medical record")
        raise
    rec = get(new_id)
    assert rec is not None
    # NOTE: do not log title/description — see module docstring.
    logger.info("Created medical record #%d (pupil %s, type=%s, severity=%s)",
                rec.record_id, rec.pupil_id, rec.record_type, rec.severity)
    return rec


def get(record_id: int) -> MedicalRecord | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM medical_records WHERE record_id = ?",
                (record_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get medical(%s) failed", record_id)
        raise
    return _row(r) if r else None


def update(record_id: int, data: dict[str, Any]) -> MedicalRecord:
    init_db()
    existing = get(record_id)
    if existing is None:
        raise ValidationError(f"No medical record #{record_id}")
    merged = {
        "pupil_id":      data.get("pupil_id", existing.pupil_id),
        "record_type":   data.get("record_type", existing.record_type),
        "title":         data.get("title", existing.title),
        "description":   data.get("description", existing.description),
        "severity":      data.get("severity", existing.severity),
        "start_date":    data.get("start_date", existing.start_date),
        "end_date":      data.get("end_date", existing.end_date),
        "action_plan":   data.get("action_plan", existing.action_plan),
        "contact_name":  data.get("contact_name", existing.contact_name),
        "contact_phone": data.get("contact_phone", existing.contact_phone),
        "is_active":     data.get("is_active", existing.is_active),
        "notes":         data.get("notes", existing.notes),
    }
    payload = _validate(merged)
    if pupils_data.get_pupil(payload["pupil_id"]) is None:
        raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE medical_records SET
                       pupil_id = ?, record_type = ?, title = ?,
                       description = ?, severity = ?, start_date = ?,
                       end_date = ?, action_plan = ?, contact_name = ?,
                       contact_phone = ?, is_active = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE record_id = ?""",
                (payload["pupil_id"], payload["record_type"], payload["title"],
                 payload["description"], payload["severity"],
                 payload["start_date"], payload["end_date"],
                 payload["action_plan"], payload["contact_name"],
                 payload["contact_phone"],
                 1 if payload["is_active"] else 0,
                 payload["notes"], record_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update medical #%d", record_id)
        raise
    rec = get(record_id)
    assert rec is not None
    logger.info("Updated medical record #%d", record_id)
    return rec


def toggle_active(record_id: int) -> MedicalRecord:
    init_db()
    existing = get(record_id)
    if existing is None:
        raise ValidationError(f"No medical record #{record_id}")
    new_val = 0 if existing.is_active else 1
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE medical_records SET is_active = ?, "
                "updated_at = datetime('now') WHERE record_id = ?",
                (new_val, record_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("toggle_active(%s) failed", record_id)
        raise
    rec = get(record_id)
    assert rec is not None
    logger.info("Medical #%d -> active=%s", record_id, rec.is_active)
    return rec


def delete(record_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM medical_records WHERE record_id = ?",
                (record_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete medical #%d", record_id)
        raise
    if deleted:
        logger.info("Deleted medical record #%d", record_id)
    return deleted


def list_records(
    *, record_type: str | None = None,
    severity: str | None = None,
    pupil_id: str | None = None,
    year_group: str | None = None,
    active_only: bool = False,
    critical_only: bool = False,
    search: str | None = None,
) -> list[tuple[MedicalRecord, Pupil | None]]:
    init_db()
    if record_type is not None and record_type not in RECORD_TYPES:
        raise ValidationError(
            f"Type filter must be one of {', '.join(RECORD_TYPES)}")
    if severity is not None and severity not in SEVERITIES:
        raise ValidationError(
            f"Severity filter must be one of {', '.join(SEVERITIES)}")
    if year_group is not None and year_group not in YEAR_GROUPS:
        raise ValidationError(
            f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
    where: list[str] = []
    params: list[Any] = []
    if record_type:
        where.append("record_type = ?")
        params.append(record_type)
    if severity:
        where.append("severity = ?")
        params.append(severity)
    if pupil_id:
        where.append("pupil_id = ?")
        params.append(pupil_id.strip())
    if active_only:
        where.append("is_active = 1")
    if critical_only:
        where.append("severity = 'critical'")
    if search:
        q = f"%{search.strip()}%"
        where.append("(title LIKE ? OR description LIKE ? OR notes LIKE ?)")
        params.extend([q, q, q])
    sql = "SELECT * FROM medical_records"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY CASE severity "
            "WHEN 'critical' THEN 0 WHEN 'high' THEN 1 "
            "WHEN 'medium' THEN 2 ELSE 3 END, "
            "pupil_id, record_id DESC")
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    out: list[tuple[MedicalRecord, Pupil | None]] = []
    for r in rows:
        rec = _row(r)
        p = pupils_data.get_pupil(rec.pupil_id)
        if year_group and (p is None or p.year_group != year_group):
            continue
        out.append((rec, p))
    return out


def list_for_pupil(pupil_id: str,
                   *, active_only: bool = False) -> list[MedicalRecord]:
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    sql = "SELECT * FROM medical_records WHERE pupil_id = ?"
    if active_only:
        sql += " AND is_active = 1"
    sql += (" ORDER BY CASE severity "
            "WHEN 'critical' THEN 0 WHEN 'high' THEN 1 "
            "WHEN 'medium' THEN 2 ELSE 3 END, record_type")
    try:
        with _connect() as conn:
            rows = conn.execute(sql, (pupil_id,)).fetchall()
    except sqlite3.Error:
        logger.exception("list_for_pupil(%s) failed", pupil_id)
        raise
    return [_row(r) for r in rows]


def summary() -> dict[str, Any]:
    init_db()
    try:
        with _connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM medical_records").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM medical_records WHERE is_active = 1"
            ).fetchone()[0]
            critical = conn.execute(
                "SELECT COUNT(*) FROM medical_records "
                "WHERE is_active = 1 AND severity = 'critical'"
            ).fetchone()[0]
            distinct = conn.execute(
                "SELECT COUNT(DISTINCT pupil_id) FROM medical_records"
            ).fetchone()[0]
            by_type = {
                r["record_type"]: r["n"]
                for r in conn.execute(
                    "SELECT record_type, COUNT(*) AS n "
                    "FROM medical_records WHERE is_active = 1 "
                    "GROUP BY record_type"
                ).fetchall()
            }
            by_severity = {
                r["severity"]: r["n"]
                for r in conn.execute(
                    "SELECT severity, COUNT(*) AS n "
                    "FROM medical_records WHERE is_active = 1 "
                    "GROUP BY severity"
                ).fetchall()
            }
    except sqlite3.Error:
        logger.exception("medical summary failed")
        raise
    return {
        "total": total,
        "active": active,
        "critical_active": critical,
        "pupils_with_records": distinct,
        "by_type": {t: by_type.get(t, 0) for t in RECORD_TYPES},
        "by_severity": {s: by_severity.get(s, 0) for s in SEVERITIES},
    }
