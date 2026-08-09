"""Emergency events and drills data layer for the Secondary School System.

One table tracking both:
* real emergencies (fire, lockdown, medical, severe weather, etc.)
* planned drills (fire drill, lockdown drill).

Each row captures kind (Drill/Real/Test), type, response time,
evacuation count, lessons-learned and follow-up actions.
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

EVENT_KINDS: tuple[str, ...] = (
    "Drill", "Real", "Test", "False alarm")
DEFAULT_KIND: str = "Drill"

EMERGENCY_TYPES: tuple[str, ...] = (
    "Fire", "Lockdown", "Invacuation", "Bomb threat",
    "Severe weather", "Power failure", "Gas leak",
    "Flood", "Medical — pupil", "Medical — staff",
    "Intruder", "Missing pupil", "Cyber/IT outage", "Other")
DEFAULT_TYPE: str = "Fire"

OUTCOMES: tuple[str, ...] = (
    "Successful", "Partial success", "Issues identified",
    "Aborted", "Under review")
DEFAULT_OUTCOME: str = "Successful"

STATUSES: tuple[str, ...] = (
    "Logged", "Under review", "Actions outstanding", "Closed")
DEFAULT_STATUS: str = "Logged"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS emergency_events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    kind            TEXT NOT NULL DEFAULT 'Drill',
    event_type      TEXT NOT NULL DEFAULT 'Fire',
    event_date      TEXT NOT NULL DEFAULT (date('now')),
    start_time      TEXT,
    end_time        TEXT,
    duration_min    INTEGER,
    location        TEXT,
    trigger         TEXT,
    reported_by     TEXT,
    incident_commander TEXT,
    pupils_evacuated INTEGER,
    staff_evacuated  INTEGER,
    missing_count   INTEGER NOT NULL DEFAULT 0,
    injuries_count  INTEGER NOT NULL DEFAULT 0,
    emergency_services INTEGER NOT NULL DEFAULT 0,
    services_attended TEXT,
    outcome         TEXT NOT NULL DEFAULT 'Successful',
    status          TEXT NOT NULL DEFAULT 'Logged',
    lessons_learned TEXT,
    follow_up_actions TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_em_date
    ON emergency_events(event_date);
CREATE INDEX IF NOT EXISTS idx_em_kind
    ON emergency_events(kind);
CREATE INDEX IF NOT EXISTS idx_em_type
    ON emergency_events(event_type);
CREATE INDEX IF NOT EXISTS idx_em_status
    ON emergency_events(status);
"""


@dataclass
class Event:
    event_id: int
    kind: str
    event_type: str
    event_date: str
    start_time: str | None
    end_time: str | None
    duration_min: int | None
    location: str | None
    trigger: str | None
    reported_by: str | None
    incident_commander: str | None
    pupils_evacuated: int | None
    staff_evacuated: int | None
    missing_count: int
    injuries_count: int
    emergency_services: bool
    services_attended: str | None
    outcome: str
    status: str
    lessons_learned: str | None
    follow_up_actions: str | None
    notes: str | None
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
            "Failed to initialise emergency_events tables")
        raise
    logger.info("Secondary emergency_events tables ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Event:
    return Event(
        event_id=r["event_id"], kind=r["kind"],
        event_type=r["event_type"], event_date=r["event_date"],
        start_time=r["start_time"], end_time=r["end_time"],
        duration_min=r["duration_min"], location=r["location"],
        trigger=r["trigger"], reported_by=r["reported_by"],
        incident_commander=r["incident_commander"],
        pupils_evacuated=r["pupils_evacuated"],
        staff_evacuated=r["staff_evacuated"],
        missing_count=r["missing_count"],
        injuries_count=r["injuries_count"],
        emergency_services=bool(r["emergency_services"]),
        services_attended=r["services_attended"],
        outcome=r["outcome"], status=r["status"],
        lessons_learned=r["lessons_learned"],
        follow_up_actions=r["follow_up_actions"],
        notes=r["notes"],
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


def _parse_int(value: Any, label: str, *,
                  required: bool = False,
                  min_value: int | None = 0,
                  max_value: int | None = None) -> int | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    try:
        i = int(value)
    except (TypeError, ValueError):
        raise ValidationError(
            f"{label} must be a whole number") from None
    if min_value is not None and i < min_value:
        raise ValidationError(f"{label} cannot be below {min_value}")
    if max_value is not None and i > max_value:
        raise ValidationError(f"{label} cannot exceed {max_value}")
    return i


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    kind = (data.get("kind") or DEFAULT_KIND).strip()
    if kind not in EVENT_KINDS:
        raise ValidationError(
            f"Kind must be one of {', '.join(EVENT_KINDS)}")
    out["kind"] = kind

    etype = (data.get("event_type") or DEFAULT_TYPE).strip()
    if etype not in EMERGENCY_TYPES:
        raise ValidationError(
            f"Event type must be one of "
            f"{', '.join(EMERGENCY_TYPES)}")
    out["event_type"] = etype

    out["event_date"] = _validate_date(
        data.get("event_date"), "Event date")
    out["start_time"] = _validate_time(
        data.get("start_time"), "Start time")
    out["end_time"]   = _validate_time(
        data.get("end_time"),   "End time")

    duration_in = data.get("duration_min")
    if duration_in in (None, "") or (isinstance(duration_in, str)
                                          and not duration_in.strip()):
        if out["start_time"] and out["end_time"]:
            sh, sm = [int(x) for x in out["start_time"].split(":")]
            eh, em = [int(x) for x in out["end_time"].split(":")]
            diff = (eh * 60 + em) - (sh * 60 + sm)
            if diff < 0:
                raise ValidationError(
                    "End time cannot be before start time")
            out["duration_min"] = diff
        else:
            out["duration_min"] = None
    else:
        out["duration_min"] = _parse_int(
            duration_in, "Duration (min)",
            min_value=0, max_value=24 * 60)

    out["location"] = (data.get("location") or "").strip() or None
    out["trigger"]  = (data.get("trigger")  or "").strip() or None

    out["reported_by"] = (
        data.get("reported_by") or "").strip() or None
    out["incident_commander"] = (
        data.get("incident_commander") or "").strip() or None

    out["pupils_evacuated"] = _parse_int(
        data.get("pupils_evacuated"), "Pupils evacuated",
        min_value=0)
    out["staff_evacuated"]  = _parse_int(
        data.get("staff_evacuated"), "Staff evacuated",
        min_value=0)
    out["missing_count"]    = _parse_int(
        data.get("missing_count"), "Missing count",
        min_value=0) or 0
    out["injuries_count"]   = _parse_int(
        data.get("injuries_count"), "Injuries count",
        min_value=0) or 0

    out["emergency_services"] = bool(data.get("emergency_services"))
    out["services_attended"]  = (
        data.get("services_attended") or "").strip() or None
    if out["services_attended"] and not out["emergency_services"]:
        out["emergency_services"] = True

    outcome = (data.get("outcome") or DEFAULT_OUTCOME).strip()
    if outcome not in OUTCOMES:
        raise ValidationError(
            f"Outcome must be one of {', '.join(OUTCOMES)}")
    out["outcome"] = outcome

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status

    out["lessons_learned"] = (
        data.get("lessons_learned") or "").strip() or None
    out["follow_up_actions"] = (
        data.get("follow_up_actions") or "").strip() or None
    out["notes"] = (data.get("notes") or "").strip() or None

    if outcome == "Issues identified" and not out["follow_up_actions"]:
        raise ValidationError(
            "Follow-up actions are required when outcome is "
            "'Issues identified'")
    return out


def create(data: dict[str, Any]) -> Event:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO emergency_events
                       (kind, event_type, event_date, start_time,
                        end_time, duration_min, location, trigger,
                        reported_by, incident_commander,
                        pupils_evacuated, staff_evacuated,
                        missing_count, injuries_count,
                        emergency_services, services_attended,
                        outcome, status, lessons_learned,
                        follow_up_actions, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["kind"], payload["event_type"],
                 payload["event_date"], payload["start_time"],
                 payload["end_time"], payload["duration_min"],
                 payload["location"], payload["trigger"],
                 payload["reported_by"],
                 payload["incident_commander"],
                 payload["pupils_evacuated"],
                 payload["staff_evacuated"],
                 payload["missing_count"],
                 payload["injuries_count"],
                 1 if payload["emergency_services"] else 0,
                 payload["services_attended"],
                 payload["outcome"], payload["status"],
                 payload["lessons_learned"],
                 payload["follow_up_actions"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create emergency event")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info(
        "Created emergency event #%d %s/%s on %s "
        "(outcome=%s, status=%s, missing=%d, injuries=%d)",
        rec.event_id, rec.kind, rec.event_type, rec.event_date,
        rec.outcome, rec.status, rec.missing_count,
        rec.injuries_count)
    return rec


def get(event_id: int) -> Event | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM emergency_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", event_id)
        raise
    return _row(r) if r else None


def list_events(*, kind: str | None = None,
                 event_type: str | None = None,
                 status: str | None = None,
                 from_date: str | None = None,
                 to_date: str | None = None,
                 outstanding_only: bool = False) -> list[Event]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if kind:
        if kind not in EVENT_KINDS:
            raise ValidationError(
                f"Kind filter must be one of "
                f"{', '.join(EVENT_KINDS)}")
        where.append("kind = ?")
        params.append(kind)
    if event_type:
        if event_type not in EMERGENCY_TYPES:
            raise ValidationError(
                f"Event type filter must be one of "
                f"{', '.join(EMERGENCY_TYPES)}")
        where.append("event_type = ?")
        params.append(event_type)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(STATUSES)}")
        where.append("status = ?")
        params.append(status)
    if from_date:
        if not _DATE_RE.match(from_date):
            raise ValidationError("From date must be YYYY-MM-DD")
        where.append("event_date >= ?")
        params.append(from_date)
    if to_date:
        if not _DATE_RE.match(to_date):
            raise ValidationError("To date must be YYYY-MM-DD")
        where.append("event_date <= ?")
        params.append(to_date)
    if outstanding_only:
        where.append("status IN ('Under review','Actions outstanding')")
    sql = "SELECT * FROM emergency_events"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY event_date DESC, start_time DESC, "
              "event_id DESC")
    try:
        with _connect() as conn:
            return [_row(r) for r in
                    conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_events failed")
        raise


def update(event_id: int, data: dict[str, Any]) -> Event:
    init_db()
    existing = get(event_id)
    if existing is None:
        raise ValidationError(f"No emergency event #{event_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("kind", "event_type", "event_date",
                         "start_time", "end_time", "duration_min",
                         "location", "trigger", "reported_by",
                         "incident_commander", "pupils_evacuated",
                         "staff_evacuated", "missing_count",
                         "injuries_count", "emergency_services",
                         "services_attended", "outcome", "status",
                         "lessons_learned", "follow_up_actions",
                         "notes")}
    payload = _validate(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE emergency_events SET
                       kind = ?, event_type = ?, event_date = ?,
                       start_time = ?, end_time = ?, duration_min = ?,
                       location = ?, trigger = ?, reported_by = ?,
                       incident_commander = ?,
                       pupils_evacuated = ?, staff_evacuated = ?,
                       missing_count = ?, injuries_count = ?,
                       emergency_services = ?, services_attended = ?,
                       outcome = ?, status = ?, lessons_learned = ?,
                       follow_up_actions = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE event_id = ?""",
                (payload["kind"], payload["event_type"],
                 payload["event_date"], payload["start_time"],
                 payload["end_time"], payload["duration_min"],
                 payload["location"], payload["trigger"],
                 payload["reported_by"],
                 payload["incident_commander"],
                 payload["pupils_evacuated"],
                 payload["staff_evacuated"],
                 payload["missing_count"],
                 payload["injuries_count"],
                 1 if payload["emergency_services"] else 0,
                 payload["services_attended"],
                 payload["outcome"], payload["status"],
                 payload["lessons_learned"],
                 payload["follow_up_actions"], payload["notes"],
                 event_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to update emergency event #%d", event_id)
        raise
    rec = get(event_id)
    assert rec is not None
    logger.info(
        "Updated emergency event #%d (status %s, outcome %s)",
        rec.event_id, rec.status, rec.outcome)
    return rec


def set_status(event_id: int, status: str) -> Event:
    return update(event_id, {"status": status})


def close_event(event_id: int) -> Event:
    return update(event_id, {"status": "Closed"})


def delete(event_id: int) -> bool:
    init_db()
    existing = get(event_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM emergency_events WHERE event_id = ?",
                (event_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete emergency event #%d", event_id)
        raise
    if deleted:
        logger.info("Deleted emergency event #%d", event_id)
    return deleted


def cohort_summary(*, from_date: str | None = None,
                    to_date: str | None = None) -> dict[str, Any]:
    rows = list_events(from_date=from_date, to_date=to_date)
    drills = [r for r in rows if r.kind == "Drill"]
    real = [r for r in rows if r.kind == "Real"]
    avg_dur = None
    durations = [r.duration_min for r in rows
                   if r.duration_min is not None]
    if durations:
        avg_dur = round(sum(durations) / len(durations), 1)
    return {
        "total":     len(rows),
        "drills":    len(drills),
        "real":      len(real),
        "outstanding": sum(1 for r in rows
                              if r.status in (
                                  "Under review",
                                  "Actions outstanding")),
        "by_type":   dict(Counter(r.event_type for r in rows)),
        "by_outcome": dict(Counter(r.outcome for r in rows)),
        "by_status": dict(Counter(r.status for r in rows)),
        "total_missing":  sum(r.missing_count for r in rows),
        "total_injuries": sum(r.injuries_count for r in rows),
        "services_called": sum(1 for r in rows
                                  if r.emergency_services),
        "avg_duration_min": avg_dur,
    }
