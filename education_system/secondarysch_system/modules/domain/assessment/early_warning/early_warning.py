"""Early-warning alert data layer for the Secondary School System.

One row per ``early_warning_alerts`` raised for a pupil. An alert
captures the category of concern (academic, behaviour, attendance,
wellbeing, …), a severity, who raised it, and a status workflow:

    Open → Acknowledged → InAction → Resolved   (or Dismissed)

The schema is denormalised on purpose — alerts can carry their own
title/details rather than always linking to an external case so the
flow stays light for pastoral staff.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

ALERT_TYPES: tuple[str, ...] = (
    "Attendance", "Behaviour", "Academic", "Engagement",
    "Wellbeing", "Safeguarding flag", "SEND concern", "Other")
DEFAULT_TYPE: str = "Academic"

SEVERITIES: tuple[str, ...] = ("Low", "Medium", "High", "Critical")
DEFAULT_SEVERITY: str = "Medium"

ALERT_STATUSES: tuple[str, ...] = (
    "Open", "Acknowledged", "InAction", "Resolved", "Dismissed")
DEFAULT_STATUS: str = "Open"

SOURCES: tuple[str, ...] = (
    "Auto", "Teacher", "Form tutor", "Head of year",
    "Pastoral", "Attendance team", "SLT", "Other")
DEFAULT_SOURCE: str = "Teacher"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS early_warning_alerts (
    alert_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id        TEXT NOT NULL,
    alert_type      TEXT NOT NULL DEFAULT 'Academic',
    severity        TEXT NOT NULL DEFAULT 'Medium',
    title           TEXT NOT NULL,
    details         TEXT,
    source          TEXT NOT NULL DEFAULT 'Teacher',
    raised_by       TEXT,
    raised_date     TEXT NOT NULL DEFAULT (date('now')),
    status          TEXT NOT NULL DEFAULT 'Open',
    assigned_to     TEXT,
    resolution      TEXT,
    resolved_date   TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ewa_pupil
    ON early_warning_alerts(pupil_id);
CREATE INDEX IF NOT EXISTS idx_ewa_status
    ON early_warning_alerts(status);
CREATE INDEX IF NOT EXISTS idx_ewa_severity
    ON early_warning_alerts(severity);
"""


@dataclass
class Alert:
    alert_id: int
    pupil_id: str
    alert_type: str
    severity: str
    title: str
    details: str | None
    source: str
    raised_by: str | None
    raised_date: str
    status: str
    assigned_to: str | None
    resolution: str | None
    resolved_date: str | None
    notes: str | None
    pupil_name: str | None = None
    pupil_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise early_warning_alerts table")
        raise
    logger.info("Secondary early_warning_alerts table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Alert:
    keys = r.keys()
    return Alert(
        alert_id=r["alert_id"], pupil_id=r["pupil_id"],
        alert_type=r["alert_type"], severity=r["severity"],
        title=r["title"], details=r["details"],
        source=r["source"], raised_by=r["raised_by"],
        raised_date=r["raised_date"], status=r["status"],
        assigned_to=r["assigned_to"], resolution=r["resolution"],
        resolved_date=r["resolved_date"], notes=r["notes"],
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str, *,
                   required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            return _dt.date.today().isoformat()
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    from education_system.secondarysch_system.modules.domain.pupils.pupils import (
        pupils as pupils_data,
    )
    if pupils_data.get_pupil(pid) is None:
        raise ValidationError(f"No pupil with id {pid}")
    out["pupil_id"] = pid

    alert_type = (data.get("alert_type") or DEFAULT_TYPE).strip()
    if alert_type not in ALERT_TYPES:
        raise ValidationError(
            f"Alert type must be one of {', '.join(ALERT_TYPES)}")
    out["alert_type"] = alert_type

    severity = (data.get("severity") or DEFAULT_SEVERITY).strip()
    if severity not in SEVERITIES:
        raise ValidationError(
            f"Severity must be one of {', '.join(SEVERITIES)}")
    out["severity"] = severity

    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    if len(title) > 120:
        raise ValidationError("Title must be 120 characters or fewer")
    out["title"] = title

    out["details"] = (data.get("details") or "").strip() or None

    source = (data.get("source") or DEFAULT_SOURCE).strip()
    if source not in SOURCES:
        raise ValidationError(
            f"Source must be one of {', '.join(SOURCES)}")
    out["source"] = source

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in ALERT_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(ALERT_STATUSES)}")
    out["status"] = status

    out["raised_by"]     = (data.get("raised_by") or "").strip() or None
    out["assigned_to"]   = (data.get("assigned_to") or "").strip() or None
    out["resolution"]    = (data.get("resolution") or "").strip() or None
    out["notes"]         = (data.get("notes") or "").strip() or None
    out["raised_date"]   = _validate_date(
        data.get("raised_date"), "Raised date")
    out["resolved_date"] = _validate_date(
        data.get("resolved_date"), "Resolved date", required=False)

    if (out["status"] in ("Resolved", "Dismissed")
            and not out["resolution"]):
        raise ValidationError(
            f"Resolution is required when status is {out['status']}")
    if out["status"] == "Resolved" and not out["resolved_date"]:
        out["resolved_date"] = _dt.date.today().isoformat()
    if (out["resolved_date"]
            and out["resolved_date"] < out["raised_date"]):
        raise ValidationError(
            "Resolved date cannot be before raised date")
    return out


def create(data: dict[str, Any]) -> Alert:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO early_warning_alerts
                       (pupil_id, alert_type, severity, title, details,
                        source, raised_by, raised_date, status,
                        assigned_to, resolution, resolved_date, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["alert_type"],
                 payload["severity"], payload["title"],
                 payload["details"], payload["source"],
                 payload["raised_by"], payload["raised_date"],
                 payload["status"], payload["assigned_to"],
                 payload["resolution"], payload["resolved_date"],
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create early-warning alert")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("Created early-warning alert #%d pupil=%s type=%s "
                "severity=%s status=%s",
                rec.alert_id, rec.pupil_id, rec.alert_type,
                rec.severity, rec.status)
    return rec


def get(alert_id: int) -> Alert | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT a.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM early_warning_alerts a
                   LEFT JOIN pupils p ON p.pupil_id = a.pupil_id
                   WHERE a.alert_id = ?""",
                (alert_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", alert_id)
        raise
    return _row(r) if r else None


def list_alerts(*, year_group: str | None = None,
                pupil_id: str | None = None,
                alert_type: str | None = None,
                severity: str | None = None,
                status: str | None = None,
                source: str | None = None,
                assigned_to: str | None = None,
                date_from: str | None = None,
                date_to: str | None = None) -> list[Alert]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("p.year_group = ?")
        params.append(year_group)
    if pupil_id:
        where.append("a.pupil_id = ?")
        params.append(pupil_id.strip())
    if alert_type:
        if alert_type not in ALERT_TYPES:
            raise ValidationError(
                f"Type filter must be one of {', '.join(ALERT_TYPES)}")
        where.append("a.alert_type = ?")
        params.append(alert_type)
    if severity:
        if severity not in SEVERITIES:
            raise ValidationError(
                f"Severity filter must be one of "
                f"{', '.join(SEVERITIES)}")
        where.append("a.severity = ?")
        params.append(severity)
    if status:
        if status not in ALERT_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(ALERT_STATUSES)}")
        where.append("a.status = ?")
        params.append(status)
    if source:
        if source not in SOURCES:
            raise ValidationError(
                f"Source filter must be one of {', '.join(SOURCES)}")
        where.append("a.source = ?")
        params.append(source)
    if assigned_to:
        where.append("a.assigned_to = ?")
        params.append(assigned_to.strip())
    if date_from:
        where.append("a.raised_date >= ?")
        params.append(_validate_date(date_from, "From date"))
    if date_to:
        where.append("a.raised_date <= ?")
        params.append(_validate_date(date_to, "To date"))
    sql = ("""SELECT a.*,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM early_warning_alerts a
              LEFT JOIN pupils p ON p.pupil_id = a.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY CASE a.severity "
            "  WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 "
            "  WHEN 'Medium' THEN 3 WHEN 'Low' THEN 4 END, "
            "a.raised_date DESC, a.alert_id DESC")
    try:
        with _connect() as conn:
            return [_row(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_alerts failed")
        raise


def update(alert_id: int, data: dict[str, Any]) -> Alert:
    init_db()
    existing = get(alert_id)
    if existing is None:
        raise ValidationError(f"No early-warning alert #{alert_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("pupil_id", "alert_type", "severity", "title",
                         "details", "source", "raised_by",
                         "raised_date", "status", "assigned_to",
                         "resolution", "resolved_date", "notes")}
    payload = _validate(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE early_warning_alerts SET
                       pupil_id = ?, alert_type = ?, severity = ?,
                       title = ?, details = ?, source = ?,
                       raised_by = ?, raised_date = ?, status = ?,
                       assigned_to = ?, resolution = ?,
                       resolved_date = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE alert_id = ?""",
                (payload["pupil_id"], payload["alert_type"],
                 payload["severity"], payload["title"],
                 payload["details"], payload["source"],
                 payload["raised_by"], payload["raised_date"],
                 payload["status"], payload["assigned_to"],
                 payload["resolution"], payload["resolved_date"],
                 payload["notes"], alert_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update alert #%d", alert_id)
        raise
    rec = get(alert_id)
    assert rec is not None
    logger.info("Updated alert #%d (status %s, severity %s)",
                rec.alert_id, rec.status, rec.severity)
    return rec


def resolve(alert_id: int, *, resolution: str,
            resolved_date: str | None = None) -> Alert:
    return update(alert_id, {
        "status": "Resolved",
        "resolution": resolution,
        "resolved_date": resolved_date or _dt.date.today().isoformat(),
    })


def dismiss(alert_id: int, *, resolution: str) -> Alert:
    return update(alert_id, {
        "status": "Dismissed",
        "resolution": resolution,
    })


def set_status(alert_id: int, status: str) -> Alert:
    return update(alert_id, {"status": status})


def delete(alert_id: int) -> bool:
    init_db()
    existing = get(alert_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM early_warning_alerts WHERE alert_id = ?",
                (alert_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete alert #%d", alert_id)
        raise
    if deleted:
        logger.info("Deleted early-warning alert #%d (pupil %s)",
                    alert_id, existing.pupil_id)
    return deleted


def cohort_summary(*, year_group: str | None = None) -> dict[str, Any]:
    rows = list_alerts(year_group=year_group)
    open_alerts = [r for r in rows
                   if r.status not in ("Resolved", "Dismissed")]
    return {
        "total":         len(rows),
        "open":          len(open_alerts),
        "by_status":     dict(Counter(r.status for r in rows)),
        "by_type":       dict(Counter(r.alert_type for r in rows)),
        "by_severity":   dict(Counter(r.severity for r in rows)),
        "open_critical": sum(1 for r in open_alerts
                              if r.severity == "Critical"),
        "open_high":     sum(1 for r in open_alerts
                              if r.severity == "High"),
    }


def pupils_at_risk(*, severity_min: str = "High"
                   ) -> dict[str, list[Alert]]:
    """Return ``{pupil_id: [open alerts]}`` for pupils with at least
    one open alert of ``severity_min`` or above."""
    init_db()
    if severity_min not in SEVERITIES:
        raise ValidationError(
            f"severity_min must be one of {', '.join(SEVERITIES)}")
    threshold = SEVERITIES.index(severity_min)
    rows = list_alerts()
    out: dict[str, list[Alert]] = {}
    for r in rows:
        if r.status in ("Resolved", "Dismissed"):
            continue
        if SEVERITIES.index(r.severity) < threshold:
            continue
        out.setdefault(r.pupil_id, []).append(r)
    return out
