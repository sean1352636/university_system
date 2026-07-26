"""First-aid incident data layer for the Secondary School System.

One row per first-aid event: pupil, date/time, location, injury type,
treatment given, by whom, parent contact, hospital referral, follow-up.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

INJURY_TYPES: tuple[str, ...] = (
    "Bump/Bruise", "Cut/Graze", "Sprain/Strain",
    "Fracture (suspected)", "Burn/Scald", "Bite/Sting",
    "Nose bleed", "Headache", "Stomach ache",
    "Asthma", "Allergic reaction", "Anaphylaxis",
    "Seizure", "Faint/Dizziness", "Concussion (suspected)",
    "Eye injury", "Dental", "Mental-health (panic)", "Other")
DEFAULT_INJURY: str = "Bump/Bruise"

SEVERITIES: tuple[str, ...] = (
    "Minor", "Moderate", "Severe", "Critical")
DEFAULT_SEVERITY: str = "Minor"

OUTCOMES: tuple[str, ...] = (
    "Returned to lesson", "Sent home", "Hospital — A&E",
    "Hospital — minor injuries", "Ambulance called",
    "GP referral", "School nurse referral", "Other")
DEFAULT_OUTCOME: str = "Returned to lesson"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS first_aid_incidents (
    incident_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id         TEXT NOT NULL,
    incident_date    TEXT NOT NULL DEFAULT (date('now')),
    incident_time    TEXT,
    location         TEXT NOT NULL,
    injury_type      TEXT NOT NULL DEFAULT 'Bump/Bruise',
    severity         TEXT NOT NULL DEFAULT 'Minor',
    body_part        TEXT,
    description      TEXT NOT NULL,
    treatment        TEXT NOT NULL,
    treated_by       TEXT NOT NULL,
    outcome          TEXT NOT NULL DEFAULT 'Returned to lesson',
    parent_contacted INTEGER NOT NULL DEFAULT 0,
    parent_contact_time TEXT,
    hospital_referral INTEGER NOT NULL DEFAULT 0,
    accident_book_ref TEXT,
    riddor_reportable INTEGER NOT NULL DEFAULT 0,
    follow_up        TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_fa_pupil
    ON first_aid_incidents(pupil_id);
CREATE INDEX IF NOT EXISTS idx_fa_date
    ON first_aid_incidents(incident_date);
CREATE INDEX IF NOT EXISTS idx_fa_severity
    ON first_aid_incidents(severity);
"""


@dataclass
class Incident:
    incident_id: int
    pupil_id: str
    incident_date: str
    incident_time: str | None
    location: str
    injury_type: str
    severity: str
    body_part: str | None
    description: str
    treatment: str
    treated_by: str
    outcome: str
    parent_contacted: bool
    parent_contact_time: str | None
    hospital_referral: bool
    accident_book_ref: str | None
    riddor_reportable: bool
    follow_up: str | None
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
        logger.exception(
            "Failed to initialise first_aid_incidents tables")
        raise
    logger.info("Secondary first_aid_incidents tables ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Incident:
    keys = r.keys()
    return Incident(
        incident_id=r["incident_id"], pupil_id=r["pupil_id"],
        incident_date=r["incident_date"],
        incident_time=r["incident_time"],
        location=r["location"], injury_type=r["injury_type"],
        severity=r["severity"], body_part=r["body_part"],
        description=r["description"], treatment=r["treatment"],
        treated_by=r["treated_by"], outcome=r["outcome"],
        parent_contacted=bool(r["parent_contacted"]),
        parent_contact_time=r["parent_contact_time"],
        hospital_referral=bool(r["hospital_referral"]),
        accident_book_ref=r["accident_book_ref"],
        riddor_reportable=bool(r["riddor_reportable"]),
        follow_up=r["follow_up"], notes=r["notes"],
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str, *,
                   required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
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


def _validate_time(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    s = str(value).strip()
    if not _TIME_RE.match(s):
        raise ValidationError(f"{label} must be HH:MM (24-hour)")
    return s


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    from education_system.systems.secondary.domain.learners.pupils import (
        pupils as pupils_data,
    )
    if pupils_data.get_pupil(pid) is None:
        raise ValidationError(f"No pupil with id {pid}")
    out["pupil_id"] = pid

    out["incident_date"] = _validate_date(
        data.get("incident_date"), "Incident date")
    out["incident_time"] = _validate_time(
        data.get("incident_time"), "Incident time")

    location = (data.get("location") or "").strip()
    if not location:
        raise ValidationError("Location is required")
    out["location"] = location

    injury = (data.get("injury_type") or DEFAULT_INJURY).strip()
    if injury not in INJURY_TYPES:
        raise ValidationError(
            f"Injury type must be one of {', '.join(INJURY_TYPES)}")
    out["injury_type"] = injury

    severity = (data.get("severity") or DEFAULT_SEVERITY).strip()
    if severity not in SEVERITIES:
        raise ValidationError(
            f"Severity must be one of {', '.join(SEVERITIES)}")
    out["severity"] = severity

    out["body_part"] = (data.get("body_part") or "").strip() or None

    description = (data.get("description") or "").strip()
    if not description:
        raise ValidationError("Description is required")
    if len(description) > 2000:
        raise ValidationError(
            "Description is too long (max 2000 chars)")
    out["description"] = description

    treatment = (data.get("treatment") or "").strip()
    if not treatment:
        raise ValidationError("Treatment is required")
    out["treatment"] = treatment

    treated_by = (data.get("treated_by") or "").strip()
    if not treated_by:
        raise ValidationError("Treated-by is required")
    out["treated_by"] = treated_by

    outcome = (data.get("outcome") or DEFAULT_OUTCOME).strip()
    if outcome not in OUTCOMES:
        raise ValidationError(
            f"Outcome must be one of {', '.join(OUTCOMES)}")
    out["outcome"] = outcome

    out["parent_contacted"]   = bool(data.get("parent_contacted"))
    out["parent_contact_time"] = _validate_time(
        data.get("parent_contact_time"), "Parent contact time")
    if (out["parent_contacted"] and not out["parent_contact_time"]
            and data.get("parent_contact_time") not in (None, "")):
        # caller passed a value but it was bad
        pass

    out["hospital_referral"] = bool(data.get("hospital_referral"))
    if outcome in ("Hospital — A&E", "Hospital — minor injuries",
                     "Ambulance called"):
        out["hospital_referral"] = True

    out["accident_book_ref"] = (
        data.get("accident_book_ref") or "").strip() or None
    out["riddor_reportable"] = bool(data.get("riddor_reportable"))
    out["follow_up"] = (data.get("follow_up") or "").strip() or None
    out["notes"]     = (data.get("notes") or "").strip() or None

    if severity in ("Severe", "Critical") and not out["parent_contacted"]:
        raise ValidationError(
            "Severe/Critical incidents must have parent_contacted=True")
    return out


def create(data: dict[str, Any]) -> Incident:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO first_aid_incidents
                       (pupil_id, incident_date, incident_time,
                        location, injury_type, severity, body_part,
                        description, treatment, treated_by, outcome,
                        parent_contacted, parent_contact_time,
                        hospital_referral, accident_book_ref,
                        riddor_reportable, follow_up, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["incident_date"],
                 payload["incident_time"], payload["location"],
                 payload["injury_type"], payload["severity"],
                 payload["body_part"], payload["description"],
                 payload["treatment"], payload["treated_by"],
                 payload["outcome"],
                 1 if payload["parent_contacted"] else 0,
                 payload["parent_contact_time"],
                 1 if payload["hospital_referral"] else 0,
                 payload["accident_book_ref"],
                 1 if payload["riddor_reportable"] else 0,
                 payload["follow_up"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create first-aid incident")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info(
        "Created first-aid incident #%d pupil=%s date=%s "
        "injury=%s severity=%s outcome=%s riddor=%s",
        rec.incident_id, rec.pupil_id, rec.incident_date,
        rec.injury_type, rec.severity, rec.outcome,
        rec.riddor_reportable)
    return rec


def get(incident_id: int) -> Incident | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT fa.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM first_aid_incidents fa
                   LEFT JOIN pupils p ON p.pupil_id = fa.pupil_id
                   WHERE fa.incident_id = ?""",
                (incident_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", incident_id)
        raise
    return _row(r) if r else None


def list_incidents(*, pupil_id: str | None = None,
                    from_date: str | None = None,
                    to_date: str | None = None,
                    severity: str | None = None,
                    injury_type: str | None = None,
                    riddor_only: bool = False,
                    hospital_only: bool = False) -> list[Incident]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if pupil_id:
        where.append("fa.pupil_id = ?")
        params.append(pupil_id.strip())
    if from_date:
        if not _DATE_RE.match(from_date):
            raise ValidationError("From date must be YYYY-MM-DD")
        where.append("fa.incident_date >= ?")
        params.append(from_date)
    if to_date:
        if not _DATE_RE.match(to_date):
            raise ValidationError("To date must be YYYY-MM-DD")
        where.append("fa.incident_date <= ?")
        params.append(to_date)
    if severity:
        if severity not in SEVERITIES:
            raise ValidationError(
                f"Severity filter must be one of "
                f"{', '.join(SEVERITIES)}")
        where.append("fa.severity = ?")
        params.append(severity)
    if injury_type:
        if injury_type not in INJURY_TYPES:
            raise ValidationError(
                f"Injury type filter must be one of "
                f"{', '.join(INJURY_TYPES)}")
        where.append("fa.injury_type = ?")
        params.append(injury_type)
    if riddor_only:
        where.append("fa.riddor_reportable = 1")
    if hospital_only:
        where.append("fa.hospital_referral = 1")
    sql = ("""SELECT fa.*,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM first_aid_incidents fa
              LEFT JOIN pupils p ON p.pupil_id = fa.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY fa.incident_date DESC, "
              "fa.incident_time DESC, fa.incident_id DESC")
    try:
        with _connect() as conn:
            return [_row(r) for r in
                    conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_incidents failed")
        raise


def update(incident_id: int, data: dict[str, Any]) -> Incident:
    init_db()
    existing = get(incident_id)
    if existing is None:
        raise ValidationError(
            f"No first-aid incident #{incident_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("pupil_id", "incident_date", "incident_time",
                         "location", "injury_type", "severity",
                         "body_part", "description", "treatment",
                         "treated_by", "outcome", "parent_contacted",
                         "parent_contact_time", "hospital_referral",
                         "accident_book_ref", "riddor_reportable",
                         "follow_up", "notes")}
    payload = _validate(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE first_aid_incidents SET
                       pupil_id = ?, incident_date = ?, incident_time = ?,
                       location = ?, injury_type = ?, severity = ?,
                       body_part = ?, description = ?, treatment = ?,
                       treated_by = ?, outcome = ?,
                       parent_contacted = ?, parent_contact_time = ?,
                       hospital_referral = ?, accident_book_ref = ?,
                       riddor_reportable = ?, follow_up = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE incident_id = ?""",
                (payload["pupil_id"], payload["incident_date"],
                 payload["incident_time"], payload["location"],
                 payload["injury_type"], payload["severity"],
                 payload["body_part"], payload["description"],
                 payload["treatment"], payload["treated_by"],
                 payload["outcome"],
                 1 if payload["parent_contacted"] else 0,
                 payload["parent_contact_time"],
                 1 if payload["hospital_referral"] else 0,
                 payload["accident_book_ref"],
                 1 if payload["riddor_reportable"] else 0,
                 payload["follow_up"], payload["notes"],
                 incident_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to update incident #%d", incident_id)
        raise
    rec = get(incident_id)
    assert rec is not None
    logger.info("Updated first-aid incident #%d (severity %s)",
                rec.incident_id, rec.severity)
    return rec


def delete(incident_id: int) -> bool:
    init_db()
    existing = get(incident_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM first_aid_incidents "
                "WHERE incident_id = ?", (incident_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete incident #%d", incident_id)
        raise
    if deleted:
        logger.info("Deleted first-aid incident #%d", incident_id)
    return deleted


def cohort_summary(*, from_date: str | None = None,
                    to_date: str | None = None) -> dict[str, Any]:
    rows = list_incidents(from_date=from_date, to_date=to_date)
    return {
        "total":          len(rows),
        "by_severity":    dict(Counter(r.severity for r in rows)),
        "by_injury":      dict(Counter(r.injury_type for r in rows)),
        "by_outcome":     dict(Counter(r.outcome for r in rows)),
        "by_location":    dict(Counter(r.location for r in rows)),
        "pupils":         len({r.pupil_id for r in rows}),
        "parent_contacted": sum(1 for r in rows if r.parent_contacted),
        "hospital":       sum(1 for r in rows if r.hospital_referral),
        "riddor":         sum(1 for r in rows if r.riddor_reportable),
    }
