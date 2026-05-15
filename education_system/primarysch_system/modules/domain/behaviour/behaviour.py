"""Behaviour-log data layer for the Primary School System.

One row per ``behaviour_incidents`` event. The log captures both
positive recognitions (achievement, house points, helping others) and
negative incidents (disruption, defiance, uniform, etc.). Points carry
sign — positive types get >= 0 points and negative types get <= 0 —
so the running tally per pupil can be summed directly.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.primarysch_system.modules.domain.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

# (label, polarity) — polarity "positive" or "negative".
INCIDENT_TYPES: dict[str, str] = {
    "Achievement":       "positive",
    "House points":      "positive",
    "Helping others":    "positive",
    "Above and beyond":  "positive",
    "Good attendance":   "positive",
    "Other positive":    "positive",
    "Disruption":        "negative",
    "Lateness":          "negative",
    "No homework":       "negative",
    "Uniform":           "negative",
    "Defiance":          "negative",
    "Bullying":          "negative",
    "Physical":          "negative",
    "Verbal abuse":      "negative",
    "Damage":            "negative",
    "Phone misuse":      "negative",
    "Other negative":    "negative",
}

SEVERITIES: tuple[str, ...] = ("Low", "Medium", "High", "Critical")
DEFAULT_SEVERITY: str = "Low"

INCIDENT_STATUSES: tuple[str, ...] = (
    "Open", "Resolved", "Escalated", "Withdrawn")
DEFAULT_STATUS: str = "Open"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS behaviour_incidents (
    incident_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id        TEXT NOT NULL,
    incident_date   TEXT NOT NULL DEFAULT (date('now')),
    incident_time   TEXT,
    location        TEXT,
    subject_id      INTEGER,
    incident_type   TEXT NOT NULL,
    polarity        TEXT NOT NULL,
    points          INTEGER NOT NULL DEFAULT 0,
    severity        TEXT NOT NULL DEFAULT 'Low',
    description     TEXT NOT NULL,
    raised_by       TEXT,
    action_taken    TEXT,
    status          TEXT NOT NULL DEFAULT 'Open',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE INDEX IF NOT EXISTS idx_beh_pupil
    ON behaviour_incidents(pupil_id);
CREATE INDEX IF NOT EXISTS idx_beh_date
    ON behaviour_incidents(incident_date);
CREATE INDEX IF NOT EXISTS idx_beh_status
    ON behaviour_incidents(status);
CREATE INDEX IF NOT EXISTS idx_beh_polarity
    ON behaviour_incidents(polarity);
"""


@dataclass
class Incident:
    incident_id: int
    pupil_id: str
    incident_date: str
    incident_time: str | None
    location: str | None
    subject_id: int | None
    incident_type: str
    polarity: str
    points: int
    severity: str
    description: str
    raised_by: str | None
    action_taken: str | None
    status: str
    notes: str | None
    subject_code: str | None = None
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
    from education_system.primarysch_system.modules.domain.subjects import (
        subjects as subjects_data,
    )
    subjects_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise behaviour_incidents table")
        raise
    logger.info("Secondary behaviour_incidents table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Incident:
    keys = r.keys()
    return Incident(
        incident_id=r["incident_id"], pupil_id=r["pupil_id"],
        incident_date=r["incident_date"],
        incident_time=r["incident_time"],
        location=r["location"], subject_id=r["subject_id"],
        incident_type=r["incident_type"],
        polarity=r["polarity"], points=r["points"],
        severity=r["severity"],
        description=r["description"], raised_by=r["raised_by"],
        action_taken=r["action_taken"], status=r["status"],
        notes=r["notes"],
        subject_code=r["subject_code"] if "subject_code" in keys else None,
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
    from education_system.primarysch_system.modules.domain.pupils import (
        pupils as pupils_data,
    )
    if pupils_data.get_pupil(pid) is None:
        raise ValidationError(f"No pupil with id {pid}")
    out["pupil_id"] = pid

    out["incident_date"] = _validate_date(
        data.get("incident_date"), "Incident date")

    t = (data.get("incident_time") or "").strip()
    if t:
        if not _TIME_RE.match(t):
            raise ValidationError(
                "Incident time must be HH:MM (24-hour)")
    out["incident_time"] = t or None

    out["location"] = (data.get("location") or "").strip() or None

    sid_raw = data.get("subject_id")
    if sid_raw in (None, "") or (isinstance(sid_raw, str)
                                  and not sid_raw.strip()):
        out["subject_id"] = None
    else:
        try:
            sid = int(sid_raw)
        except (TypeError, ValueError):
            raise ValidationError(
                "Subject ID must be a number") from None
        from education_system.primarysch_system.modules.domain.subjects import (
            subjects as subjects_data,
        )
        if subjects_data.get(sid) is None:
            raise ValidationError(f"No subject #{sid}")
        out["subject_id"] = sid

    itype = (data.get("incident_type") or "").strip()
    if not itype:
        raise ValidationError("Incident type is required")
    if itype not in INCIDENT_TYPES:
        raise ValidationError(
            f"Incident type must be one of: "
            f"{', '.join(sorted(INCIDENT_TYPES.keys()))}")
    out["incident_type"] = itype
    out["polarity"] = INCIDENT_TYPES[itype]

    pts_raw = data.get("points")
    if pts_raw in (None, "") or (isinstance(pts_raw, str)
                                   and not pts_raw.strip()):
        # Default: +1 for positive, -1 for negative.
        out["points"] = 1 if out["polarity"] == "positive" else -1
    else:
        try:
            pts = int(pts_raw)
        except (TypeError, ValueError):
            raise ValidationError(
                "Points must be a whole number") from None
        if pts < -100 or pts > 100:
            raise ValidationError(
                "Points must be between -100 and 100")
        if out["polarity"] == "positive" and pts < 0:
            raise ValidationError(
                "Positive incident types cannot have negative points")
        if out["polarity"] == "negative" and pts > 0:
            raise ValidationError(
                "Negative incident types cannot have positive points")
        out["points"] = pts

    severity = (data.get("severity") or DEFAULT_SEVERITY).strip()
    if severity not in SEVERITIES:
        raise ValidationError(
            f"Severity must be one of {', '.join(SEVERITIES)}")
    out["severity"] = severity

    description = (data.get("description") or "").strip()
    if not description:
        raise ValidationError("Description is required")
    if len(description) > 500:
        raise ValidationError("Description must be 500 chars or fewer")
    out["description"] = description

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in INCIDENT_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(INCIDENT_STATUSES)}")
    out["status"] = status

    out["raised_by"]   = (data.get("raised_by") or "").strip() or None
    out["action_taken"] = (data.get("action_taken") or "").strip() or None
    out["notes"]       = (data.get("notes") or "").strip() or None
    return out


def log_incident(data: dict[str, Any]) -> Incident:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO behaviour_incidents
                       (pupil_id, incident_date, incident_time,
                        location, subject_id, incident_type, polarity,
                        points, severity, description, raised_by,
                        action_taken, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["incident_date"],
                 payload["incident_time"], payload["location"],
                 payload["subject_id"], payload["incident_type"],
                 payload["polarity"], payload["points"],
                 payload["severity"], payload["description"],
                 payload["raised_by"], payload["action_taken"],
                 payload["status"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to log behaviour incident")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info(
        "Logged behaviour incident #%d pupil=%s type=%s "
        "polarity=%s points=%d severity=%s",
        rec.incident_id, rec.pupil_id, rec.incident_type,
        rec.polarity, rec.points, rec.severity)
    return rec


def get(incident_id: int) -> Incident | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT i.*, s.code AS subject_code,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM behaviour_incidents i
                   LEFT JOIN subjects s ON s.subject_id = i.subject_id
                   LEFT JOIN pupils p ON p.pupil_id = i.pupil_id
                   WHERE i.incident_id = ?""",
                (incident_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", incident_id)
        raise
    return _row(r) if r else None


def list_incidents(*, pupil_id: str | None = None,
                   year_group: str | None = None,
                   incident_type: str | None = None,
                   polarity: str | None = None,
                   severity: str | None = None,
                   status: str | None = None,
                   date_from: str | None = None,
                   date_to: str | None = None) -> list[Incident]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if pupil_id:
        where.append("i.pupil_id = ?")
        params.append(pupil_id.strip())
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("p.year_group = ?")
        params.append(year_group)
    if incident_type:
        if incident_type not in INCIDENT_TYPES:
            raise ValidationError(
                f"Type filter must be one of: "
                f"{', '.join(sorted(INCIDENT_TYPES.keys()))}")
        where.append("i.incident_type = ?")
        params.append(incident_type)
    if polarity:
        if polarity not in ("positive", "negative"):
            raise ValidationError(
                "Polarity filter must be 'positive' or 'negative'")
        where.append("i.polarity = ?")
        params.append(polarity)
    if severity:
        if severity not in SEVERITIES:
            raise ValidationError(
                f"Severity filter must be one of "
                f"{', '.join(SEVERITIES)}")
        where.append("i.severity = ?")
        params.append(severity)
    if status:
        if status not in INCIDENT_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(INCIDENT_STATUSES)}")
        where.append("i.status = ?")
        params.append(status)
    if date_from:
        where.append("i.incident_date >= ?")
        params.append(_validate_date(date_from, "From date"))
    if date_to:
        where.append("i.incident_date <= ?")
        params.append(_validate_date(date_to, "To date"))
    sql = ("""SELECT i.*, s.code AS subject_code,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM behaviour_incidents i
              LEFT JOIN subjects s ON s.subject_id = i.subject_id
              LEFT JOIN pupils p ON p.pupil_id = i.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY i.incident_date DESC, "
            "i.incident_time DESC, i.incident_id DESC")
    try:
        with _connect() as conn:
            return [_row(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_incidents failed")
        raise


def update(incident_id: int, data: dict[str, Any]) -> Incident:
    init_db()
    existing = get(incident_id)
    if existing is None:
        raise ValidationError(
            f"No behaviour incident #{incident_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("pupil_id", "incident_date", "incident_time",
                         "location", "subject_id", "incident_type",
                         "points", "severity", "description",
                         "raised_by", "action_taken", "status",
                         "notes")}
    payload = _validate(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE behaviour_incidents SET
                       pupil_id = ?, incident_date = ?,
                       incident_time = ?, location = ?,
                       subject_id = ?, incident_type = ?,
                       polarity = ?, points = ?, severity = ?,
                       description = ?, raised_by = ?,
                       action_taken = ?, status = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE incident_id = ?""",
                (payload["pupil_id"], payload["incident_date"],
                 payload["incident_time"], payload["location"],
                 payload["subject_id"], payload["incident_type"],
                 payload["polarity"], payload["points"],
                 payload["severity"], payload["description"],
                 payload["raised_by"], payload["action_taken"],
                 payload["status"], payload["notes"], incident_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to update incident #%d", incident_id)
        raise
    rec = get(incident_id)
    assert rec is not None
    logger.info("Updated behaviour incident #%d (status %s, points %d)",
                rec.incident_id, rec.status, rec.points)
    return rec


def set_status(incident_id: int, status: str) -> Incident:
    return update(incident_id, {"status": status})


def delete(incident_id: int) -> bool:
    init_db()
    existing = get(incident_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM behaviour_incidents WHERE incident_id = ?",
                (incident_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete incident #%d", incident_id)
        raise
    if deleted:
        logger.info("Deleted behaviour incident #%d (pupil %s)",
                    incident_id, existing.pupil_id)
    return deleted


def pupil_summary(pupil_id: str,
                   *, date_from: str | None = None,
                   date_to: str | None = None) -> dict[str, Any]:
    rows = list_incidents(pupil_id=pupil_id,
                            date_from=date_from, date_to=date_to)
    pos = sum(1 for r in rows if r.polarity == "positive")
    neg = sum(1 for r in rows if r.polarity == "negative")
    total_points = sum(r.points for r in rows)
    return {
        "pupil_id":     (pupil_id or "").strip(),
        "total":        len(rows),
        "positive":     pos,
        "negative":     neg,
        "total_points": total_points,
        "by_type":      dict(Counter(r.incident_type for r in rows)),
        "by_status":    dict(Counter(r.status for r in rows)),
        "by_severity":  dict(Counter(r.severity for r in rows)),
        "incidents":    rows,
    }


def cohort_summary(*, year_group: str | None = None,
                   date_from: str | None = None,
                   date_to: str | None = None) -> dict[str, Any]:
    rows = list_incidents(year_group=year_group,
                            date_from=date_from, date_to=date_to)
    pos = sum(1 for r in rows if r.polarity == "positive")
    neg = sum(1 for r in rows if r.polarity == "negative")
    return {
        "total":      len(rows),
        "positive":   pos,
        "negative":   neg,
        "open":       sum(1 for r in rows if r.status == "Open"),
        "by_type":    dict(Counter(r.incident_type for r in rows)),
        "by_severity": dict(Counter(r.severity for r in rows)),
        "by_status":  dict(Counter(r.status for r in rows)),
    }


def pupils_above_threshold(*, points_below: int = -10,
                           year_group: str | None = None
                           ) -> list[tuple[str, int]]:
    """Return ``[(pupil_id, total_points)]`` for pupils whose total
    behaviour points are at or below ``points_below`` (default −10).
    Useful for "pupils flagged on negative-points threshold" reports."""
    init_db()
    rows = list_incidents(year_group=year_group)
    totals: dict[str, int] = {}
    for r in rows:
        totals[r.pupil_id] = totals.get(r.pupil_id, 0) + r.points
    return sorted(((pid, pts) for pid, pts in totals.items()
                   if pts <= points_below),
                  key=lambda kv: kv[1])
