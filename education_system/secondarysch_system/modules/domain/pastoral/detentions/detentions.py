"""Detentions data layer for the Secondary School System.

One row per scheduled detention. Status tracks attendance after the
fact (Attended / Missed / Excused / Cancelled). A detention may
optionally link back to a behaviour-log incident via
``related_incident_id``.
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

DETENTION_TYPES: tuple[str, ...] = (
    "Lunchtime", "After school", "Saturday", "Friday",
    "Departmental", "SLT", "Other")
DEFAULT_TYPE: str = "After school"

DETENTION_STATUSES: tuple[str, ...] = (
    "Scheduled", "Attended", "Missed", "Excused",
    "Cancelled", "Rescheduled")
DEFAULT_STATUS: str = "Scheduled"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS detentions (
    detention_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id            TEXT NOT NULL,
    detention_date      TEXT NOT NULL,
    start_time          TEXT,
    duration_min        INTEGER NOT NULL DEFAULT 30,
    detention_type      TEXT NOT NULL DEFAULT 'After school',
    location            TEXT,
    supervisor          TEXT,
    reason              TEXT NOT NULL,
    set_by              TEXT,
    status              TEXT NOT NULL DEFAULT 'Scheduled',
    related_incident_id INTEGER,
    rescheduled_to      INTEGER,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (related_incident_id)
        REFERENCES behaviour_incidents(incident_id),
    FOREIGN KEY (rescheduled_to)
        REFERENCES detentions(detention_id)
);

CREATE INDEX IF NOT EXISTS idx_det_pupil
    ON detentions(pupil_id);
CREATE INDEX IF NOT EXISTS idx_det_date
    ON detentions(detention_date);
CREATE INDEX IF NOT EXISTS idx_det_status
    ON detentions(status);
"""


@dataclass
class Detention:
    detention_id: int
    pupil_id: str
    detention_date: str
    start_time: str | None
    duration_min: int
    detention_type: str
    location: str | None
    supervisor: str | None
    reason: str
    set_by: str | None
    status: str
    related_incident_id: int | None
    rescheduled_to: int | None
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
    # Behaviour table referenced by FK — make sure it exists first.
    from education_system.secondarysch_system.modules.domain.pastoral.behaviour import (
        behaviour as behaviour_data,
    )
    behaviour_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise detentions table")
        raise
    logger.info("Secondary detentions table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Detention:
    keys = r.keys()
    return Detention(
        detention_id=r["detention_id"], pupil_id=r["pupil_id"],
        detention_date=r["detention_date"],
        start_time=r["start_time"],
        duration_min=r["duration_min"],
        detention_type=r["detention_type"],
        location=r["location"], supervisor=r["supervisor"],
        reason=r["reason"], set_by=r["set_by"],
        status=r["status"],
        related_incident_id=r["related_incident_id"],
        rescheduled_to=r["rescheduled_to"],
        notes=r["notes"],
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str, *,
                   required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
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

    out["detention_date"] = _validate_date(
        data.get("detention_date"), "Detention date")

    t = (data.get("start_time") or "").strip()
    if t:
        if not _TIME_RE.match(t):
            raise ValidationError(
                "Start time must be HH:MM (24-hour)")
    out["start_time"] = t or None

    dur = data.get("duration_min")
    if dur in (None, "") or (isinstance(dur, str) and not dur.strip()):
        out["duration_min"] = 30
    else:
        try:
            d = int(dur)
        except (TypeError, ValueError):
            raise ValidationError(
                "Duration must be a whole number") from None
        if d < 5 or d > 480:
            raise ValidationError(
                "Duration must be between 5 and 480 minutes")
        out["duration_min"] = d

    dtype = (data.get("detention_type") or DEFAULT_TYPE).strip()
    if dtype not in DETENTION_TYPES:
        raise ValidationError(
            f"Detention type must be one of "
            f"{', '.join(DETENTION_TYPES)}")
    out["detention_type"] = dtype

    out["location"]   = (data.get("location") or "").strip() or None
    out["supervisor"] = (data.get("supervisor") or "").strip() or None

    reason = (data.get("reason") or "").strip()
    if not reason:
        raise ValidationError("Reason is required")
    if len(reason) > 200:
        raise ValidationError("Reason must be 200 chars or fewer")
    out["reason"] = reason

    out["set_by"] = (data.get("set_by") or "").strip() or None

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in DETENTION_STATUSES:
        raise ValidationError(
            f"Status must be one of "
            f"{', '.join(DETENTION_STATUSES)}")
    out["status"] = status

    inc_raw = data.get("related_incident_id")
    if inc_raw in (None, "") or (isinstance(inc_raw, str)
                                  and not inc_raw.strip()):
        out["related_incident_id"] = None
    else:
        try:
            iid = int(inc_raw)
        except (TypeError, ValueError):
            raise ValidationError(
                "Related incident ID must be a number") from None
        from education_system.secondarysch_system.modules.domain.pastoral.behaviour import (
            behaviour as behaviour_data,
        )
        if behaviour_data.get(iid) is None:
            raise ValidationError(f"No behaviour incident #{iid}")
        out["related_incident_id"] = iid

    resched_raw = data.get("rescheduled_to")
    if resched_raw in (None, "") or (isinstance(resched_raw, str)
                                       and not resched_raw.strip()):
        out["rescheduled_to"] = None
    else:
        try:
            out["rescheduled_to"] = int(resched_raw)
        except (TypeError, ValueError):
            raise ValidationError(
                "Rescheduled-to must be a number") from None

    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> Detention:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO detentions
                       (pupil_id, detention_date, start_time,
                        duration_min, detention_type, location,
                        supervisor, reason, set_by, status,
                        related_incident_id, rescheduled_to, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["detention_date"],
                 payload["start_time"], payload["duration_min"],
                 payload["detention_type"], payload["location"],
                 payload["supervisor"], payload["reason"],
                 payload["set_by"], payload["status"],
                 payload["related_incident_id"],
                 payload["rescheduled_to"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create detention")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("Created detention #%d pupil=%s on %s %s "
                "(%s, %d min, %s)",
                rec.detention_id, rec.pupil_id,
                rec.detention_date, rec.start_time or "",
                rec.detention_type, rec.duration_min, rec.status)
    return rec


def get(detention_id: int) -> Detention | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT d.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM detentions d
                   LEFT JOIN pupils p ON p.pupil_id = d.pupil_id
                   WHERE d.detention_id = ?""",
                (detention_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", detention_id)
        raise
    return _row(r) if r else None


def list_detentions(*, pupil_id: str | None = None,
                    year_group: str | None = None,
                    status: str | None = None,
                    detention_type: str | None = None,
                    date_from: str | None = None,
                    date_to: str | None = None,
                    supervisor: str | None = None) -> list[Detention]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if pupil_id:
        where.append("d.pupil_id = ?")
        params.append(pupil_id.strip())
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("p.year_group = ?")
        params.append(year_group)
    if status:
        if status not in DETENTION_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(DETENTION_STATUSES)}")
        where.append("d.status = ?")
        params.append(status)
    if detention_type:
        if detention_type not in DETENTION_TYPES:
            raise ValidationError(
                f"Type filter must be one of "
                f"{', '.join(DETENTION_TYPES)}")
        where.append("d.detention_type = ?")
        params.append(detention_type)
    if date_from:
        where.append("d.detention_date >= ?")
        params.append(_validate_date(date_from, "From date"))
    if date_to:
        where.append("d.detention_date <= ?")
        params.append(_validate_date(date_to, "To date"))
    if supervisor:
        where.append("d.supervisor = ?")
        params.append(supervisor.strip())
    sql = ("""SELECT d.*,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM detentions d
              LEFT JOIN pupils p ON p.pupil_id = d.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY d.detention_date DESC, d.start_time DESC"
    try:
        with _connect() as conn:
            return [_row(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_detentions failed")
        raise


def update(detention_id: int, data: dict[str, Any]) -> Detention:
    init_db()
    existing = get(detention_id)
    if existing is None:
        raise ValidationError(f"No detention #{detention_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("pupil_id", "detention_date", "start_time",
                         "duration_min", "detention_type", "location",
                         "supervisor", "reason", "set_by", "status",
                         "related_incident_id", "rescheduled_to",
                         "notes")}
    payload = _validate(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE detentions SET
                       pupil_id = ?, detention_date = ?,
                       start_time = ?, duration_min = ?,
                       detention_type = ?, location = ?,
                       supervisor = ?, reason = ?, set_by = ?,
                       status = ?, related_incident_id = ?,
                       rescheduled_to = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE detention_id = ?""",
                (payload["pupil_id"], payload["detention_date"],
                 payload["start_time"], payload["duration_min"],
                 payload["detention_type"], payload["location"],
                 payload["supervisor"], payload["reason"],
                 payload["set_by"], payload["status"],
                 payload["related_incident_id"],
                 payload["rescheduled_to"], payload["notes"],
                 detention_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to update detention #%d", detention_id)
        raise
    rec = get(detention_id)
    assert rec is not None
    logger.info("Updated detention #%d (status %s)",
                rec.detention_id, rec.status)
    return rec


def set_status(detention_id: int, status: str) -> Detention:
    return update(detention_id, {"status": status})


def reschedule(detention_id: int, *, new_date: str,
                new_start_time: str | None = None,
                new_location: str | None = None,
                new_supervisor: str | None = None,
                notes: str | None = None) -> Detention:
    """Create a new detention copying details from the original, link
    the two via ``rescheduled_to``, and mark the original Rescheduled."""
    init_db()
    existing = get(detention_id)
    if existing is None:
        raise ValidationError(f"No detention #{detention_id}")
    if existing.status not in ("Scheduled", "Missed"):
        raise ValidationError(
            f"Cannot reschedule a detention with status "
            f"{existing.status}")
    new = create({
        "pupil_id":            existing.pupil_id,
        "detention_date":      new_date,
        "start_time":          new_start_time or existing.start_time,
        "duration_min":        existing.duration_min,
        "detention_type":      existing.detention_type,
        "location":            new_location or existing.location,
        "supervisor":          (new_supervisor
                                  or existing.supervisor),
        "reason":              existing.reason,
        "set_by":              existing.set_by,
        "status":              "Scheduled",
        "related_incident_id": existing.related_incident_id,
        "notes":               notes
                                 or (f"Rescheduled from #{detention_id}"),
    })
    update(detention_id, {
        "status":         "Rescheduled",
        "rescheduled_to": new.detention_id,
    })
    return new


def delete(detention_id: int) -> bool:
    init_db()
    existing = get(detention_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM detentions WHERE detention_id = ?",
                (detention_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete detention #%d", detention_id)
        raise
    if deleted:
        logger.info("Deleted detention #%d (pupil %s)",
                    detention_id, existing.pupil_id)
    return deleted


def pupil_summary(pupil_id: str) -> dict[str, Any]:
    rows = list_detentions(pupil_id=pupil_id)
    return {
        "pupil_id":   (pupil_id or "").strip(),
        "total":      len(rows),
        "attended":   sum(1 for r in rows if r.status == "Attended"),
        "missed":     sum(1 for r in rows if r.status == "Missed"),
        "excused":    sum(1 for r in rows if r.status == "Excused"),
        "scheduled":  sum(1 for r in rows if r.status == "Scheduled"),
        "minutes_served": sum(r.duration_min for r in rows
                                if r.status == "Attended"),
        "detentions": rows,
    }


def daily_register(date_iso: str,
                    *, detention_type: str | None = None
                    ) -> list[Detention]:
    return list_detentions(date_from=date_iso, date_to=date_iso,
                              detention_type=detention_type)


def cohort_summary(*, year_group: str | None = None,
                   date_from: str | None = None,
                   date_to: str | None = None) -> dict[str, Any]:
    rows = list_detentions(year_group=year_group,
                              date_from=date_from, date_to=date_to)
    return {
        "total":         len(rows),
        "by_status":     dict(Counter(r.status for r in rows)),
        "by_type":       dict(Counter(r.detention_type for r in rows)),
        "missed":        sum(1 for r in rows if r.status == "Missed"),
        "attended":      sum(1 for r in rows if r.status == "Attended"),
        "minutes_served": sum(r.duration_min for r in rows
                                if r.status == "Attended"),
    }
