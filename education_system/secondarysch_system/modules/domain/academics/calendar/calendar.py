"""Calendar — school-wide events for the Sixth Form System.

One row per event: meetings, trips, exams, INSET days, parents'
evenings, sports fixtures, social events, deadlines, etc. Events can
be all-day or time-bounded and may span multiple days.

The Calendar module is *not* the same as the Academic Year breaks
table — that one models holiday periods that exclude teaching days.
This one is the day-to-day events calendar.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.secondarysch_system.core import paths
from education_system.secondarysch_system.modules.domain.academics.calendar import (
    calendar as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.CALENDAR_DB


EVENT_TYPES: tuple[str, ...] = (
    "Lesson Block",
    "Assembly",
    "Tutor Time",
    "Meeting",
    "Trip",
    "Exam",
    "Mock Exam",
    "Deadline",
    "Parents' Evening",
    "Open Day",
    "Sports Fixture",
    "Social",
    "INSET",
    "Holiday",
    "Training",
    "Assembly Practice",
    "Other",
)
DEFAULT_EVENT_TYPE: str = "Meeting"

AUDIENCES: tuple[str, ...] = (
    "All",
    "Staff",
    "Students",
    "Year 12",
    "Year 13",
    "Parents",
    "External",
)
DEFAULT_AUDIENCE: str = "All"

STATUSES: tuple[str, ...] = (
    "Scheduled", "Cancelled", "Postponed", "Completed", "Draft",
)
DEFAULT_STATUS: str = "Scheduled"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS calendar_events (
    event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    event_type    TEXT NOT NULL DEFAULT 'Meeting',
    description   TEXT,
    start_date    TEXT NOT NULL,
    end_date      TEXT NOT NULL,
    start_time    TEXT,
    end_time      TEXT,
    all_day       INTEGER NOT NULL DEFAULT 0,
    location      TEXT,
    organiser     TEXT,
    audience      TEXT NOT NULL DEFAULT 'All',
    status        TEXT NOT NULL DEFAULT 'Scheduled',
    capacity      INTEGER,
    rsvp_required INTEGER NOT NULL DEFAULT 0,
    cost          REAL,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cal_start    ON calendar_events(start_date);
CREATE INDEX IF NOT EXISTS idx_cal_end      ON calendar_events(end_date);
CREATE INDEX IF NOT EXISTS idx_cal_type     ON calendar_events(event_type);
CREATE INDEX IF NOT EXISTS idx_cal_audience ON calendar_events(audience);
CREATE INDEX IF NOT EXISTS idx_cal_status   ON calendar_events(status);
"""


@dataclass
class Event:
    event_id: int
    title: str
    event_type: str
    description: str | None
    start_date: str
    end_date: str
    start_time: str | None
    end_time: str | None
    all_day: bool
    location: str | None
    organiser: str | None
    audience: str
    status: str
    capacity: int | None
    rsvp_required: bool
    cost: float | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_multiday(self) -> bool:
        return self.start_date != self.end_date

    @property
    def day_count(self) -> int:
        try:
            sd = _dt.date.fromisoformat(self.start_date)
            ed = _dt.date.fromisoformat(self.end_date)
            return max(0, (ed - sd).days) + 1
        except Exception:
            return 0

    @property
    def time_label(self) -> str:
        if self.all_day or not self.start_time:
            return "all day"
        if self.end_time:
            return f"{self.start_time[:5]}–{self.end_time[:5]}"
        return self.start_time[:5]

    def occurs_on(self, date_iso: str) -> bool:
        return self.start_date <= date_iso <= self.end_date


@dataclass
class Summary:
    total: int
    by_type: dict[str, int]
    by_audience: dict[str, int]
    by_status: dict[str, int]
    upcoming: int          # status=Scheduled, start_date in [today, today+window]
    today_count: int
    this_week_count: int


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Calendar schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> Event:
    return Event(
        event_id=r["event_id"], title=r["title"],
        event_type=r["event_type"], description=r["description"],
        start_date=r["start_date"], end_date=r["end_date"],
        start_time=r["start_time"], end_time=r["end_time"],
        all_day=bool(r["all_day"]), location=r["location"],
        organiser=r["organiser"], audience=r["audience"],
        status=r["status"], capacity=r["capacity"],
        rsvp_required=bool(r["rsvp_required"]),
        cost=r["cost"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
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


def _validate_time(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    s = str(value).strip()
    if not _TIME_RE.match(s):
        raise ValidationError(f"{label} must be HH:MM (24-hour)")
    # Normalise HH:MM → HH:MM:00 for storage.
    if len(s) == 5:
        s = s + ":00"
    try:
        _dt.time.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real time") from None
    return s


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["title"] = _require(payload.get("title"), "Title").strip()

    etype = (payload.get("event_type") or DEFAULT_EVENT_TYPE).strip()
    if etype not in EVENT_TYPES:
        raise ValidationError(
            f"Event type must be one of: {', '.join(EVENT_TYPES)}")
    out["event_type"] = etype

    audience = (payload.get("audience") or DEFAULT_AUDIENCE).strip()
    if audience not in AUDIENCES:
        raise ValidationError(
            f"Audience must be one of: {', '.join(AUDIENCES)}")
    out["audience"] = audience

    status = (payload.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["start_date"] = _validate_date(payload.get("start_date"),
                                          "Start date")
    out["end_date"] = (_validate_date(payload.get("end_date"),
                                          "End date",
                                          required=False)
                        or out["start_date"])
    if out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")

    out["all_day"] = bool(payload.get("all_day"))
    out["start_time"] = _validate_time(payload.get("start_time"),
                                            "Start time")
    out["end_time"]   = _validate_time(payload.get("end_time"),
                                            "End time")
    if out["all_day"]:
        out["start_time"] = None
        out["end_time"] = None
    elif (out["start_time"] and out["end_time"]
            and out["start_date"] == out["end_date"]
            and out["end_time"] <= out["start_time"]):
        raise ValidationError(
            "End time must be after start time on a same-day event")

    out["description"] = (payload.get("description") or "").strip() or None
    out["location"]    = (payload.get("location") or "").strip() or None
    out["organiser"]   = (payload.get("organiser") or "").strip() or None
    out["notes"]       = (payload.get("notes") or "").strip() or None

    cap = payload.get("capacity")
    if cap in (None, ""):
        out["capacity"] = None
    else:
        try:
            n = int(cap)
        except (TypeError, ValueError):
            raise ValidationError("Capacity must be a whole number") from None
        if n < 0:
            raise ValidationError("Capacity cannot be negative")
        out["capacity"] = n

    cost = payload.get("cost")
    if cost in (None, ""):
        out["cost"] = None
    else:
        try:
            f = float(cost)
        except (TypeError, ValueError):
            raise ValidationError("Cost must be a number") from None
        if f < 0:
            raise ValidationError("Cost cannot be negative")
        out["cost"] = f

    out["rsvp_required"] = bool(payload.get("rsvp_required"))
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_event(payload: dict[str, Any]) -> Event:
    init_db()
    p = _validate_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO calendar_events
                   (title, event_type, description, start_date,
                    end_date, start_time, end_time, all_day,
                    location, organiser, audience, status, capacity,
                    rsvp_required, cost, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["title"], p["event_type"], p["description"],
             p["start_date"], p["end_date"], p["start_time"],
             p["end_time"], 1 if p["all_day"] else 0,
             p["location"], p["organiser"], p["audience"],
             p["status"], p["capacity"],
             1 if p["rsvp_required"] else 0, p["cost"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_event(new_id)
    assert out is not None
    logger.info("Created event #%d %r on %s (%s, %s)",
                new_id, p["title"], p["start_date"],
                p["event_type"], p["audience"])
    return out


def get_event(event_id: int) -> Event | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM calendar_events WHERE event_id = ?",
            (event_id,)).fetchone()
        return _row(r) if r else None


def list_events(
    *,
    event_type: str | None = None,
    audience: str | None = None,
    status: str | None = None,
    location_like: str | None = None,
    organiser_like: str | None = None,
    title_like: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    overlapping: bool = True,
    upcoming_only: bool = False,
) -> list[Event]:
    """Return events filtered by the supplied criteria.

    ``date_from`` / ``date_to`` use overlap semantics by default
    (event's [start, end] overlaps [from, to]). Pass
    ``overlapping=False`` to filter strictly on ``start_date``.
    """
    init_db()
    clauses, args = [], []
    if event_type:
        if event_type not in EVENT_TYPES:
            raise ValidationError(
                f"Event type must be one of: {', '.join(EVENT_TYPES)}")
        clauses.append("event_type = ?")
        args.append(event_type)
    if audience:
        if audience not in AUDIENCES:
            raise ValidationError(
                f"Audience must be one of: {', '.join(AUDIENCES)}")
        clauses.append("audience = ?")
        args.append(audience)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if location_like:
        clauses.append("location LIKE ?")
        args.append(f"%{location_like.strip()}%")
    if organiser_like:
        clauses.append("organiser LIKE ?")
        args.append(f"%{organiser_like.strip()}%")
    if title_like:
        clauses.append("title LIKE ?")
        args.append(f"%{title_like.strip()}%")
    if upcoming_only:
        today = _dt.date.today().isoformat()
        clauses.append("end_date >= ?")
        args.append(today)
    if date_from or date_to:
        df = _validate_date(date_from, "date_from",
                              required=False) if date_from else None
        dt2 = _validate_date(date_to, "date_to",
                               required=False) if date_to else None
        if overlapping:
            # [start, end] overlaps [from, to] iff start <= to AND end >= from
            if df and dt2:
                clauses.append("start_date <= ? AND end_date >= ?")
                args.extend([dt2, df])
            elif df:
                clauses.append("end_date >= ?")
                args.append(df)
            elif dt2:
                clauses.append("start_date <= ?")
                args.append(dt2)
        else:
            if df:
                clauses.append("start_date >= ?")
                args.append(df)
            if dt2:
                clauses.append("start_date <= ?")
                args.append(dt2)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM calendar_events {where} "
           "ORDER BY start_date ASC, "
           "CASE WHEN start_time IS NULL THEN 1 ELSE 0 END, "
           "start_time ASC, event_id ASC")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def events_on(date_iso: str) -> list[Event]:
    """Return events that cover the given calendar date."""
    init_db()
    s = _validate_date(date_iso, "Date")
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM calendar_events "
            "WHERE start_date <= ? AND end_date >= ? "
            "ORDER BY CASE WHEN start_time IS NULL THEN 1 ELSE 0 END, "
            "start_time ASC, event_id ASC",
            (s, s)).fetchall()
        return [_row(r) for r in rows]


def events_in_week(any_date_iso: str) -> list[Event]:
    """Return events overlapping the Mon–Sun week of ``any_date_iso``."""
    s = _validate_date(any_date_iso, "Date")
    anchor = _dt.date.fromisoformat(s)
    monday = anchor - _dt.timedelta(days=anchor.weekday())
    sunday = monday + _dt.timedelta(days=6)
    return list_events(date_from=monday.isoformat(),
                        date_to=sunday.isoformat(),
                        overlapping=True)


def update_event(event_id: int, payload: dict[str, Any]) -> Event:
    init_db()
    existing = get_event(event_id)
    if existing is None:
        raise ValidationError(f"No event #{event_id}")
    merged = {
        "title":         payload.get("title", existing.title),
        "event_type":    payload.get("event_type", existing.event_type),
        "description":   payload.get("description", existing.description),
        "start_date":    payload.get("start_date", existing.start_date),
        "end_date":      payload.get("end_date", existing.end_date),
        "start_time":    payload.get("start_time", existing.start_time),
        "end_time":      payload.get("end_time", existing.end_time),
        "all_day":       payload.get("all_day", existing.all_day),
        "location":      payload.get("location", existing.location),
        "organiser":     payload.get("organiser", existing.organiser),
        "audience":      payload.get("audience", existing.audience),
        "status":        payload.get("status", existing.status),
        "capacity":      payload.get("capacity", existing.capacity),
        "rsvp_required": payload.get("rsvp_required",
                                     existing.rsvp_required),
        "cost":          payload.get("cost", existing.cost),
        "notes":         payload.get("notes", existing.notes),
    }
    p = _validate_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE calendar_events SET
                   title = ?, event_type = ?, description = ?,
                   start_date = ?, end_date = ?, start_time = ?,
                   end_time = ?, all_day = ?, location = ?,
                   organiser = ?, audience = ?, status = ?,
                   capacity = ?, rsvp_required = ?, cost = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE event_id = ?""",
            (p["title"], p["event_type"], p["description"],
             p["start_date"], p["end_date"], p["start_time"],
             p["end_time"], 1 if p["all_day"] else 0, p["location"],
             p["organiser"], p["audience"], p["status"],
             p["capacity"], 1 if p["rsvp_required"] else 0,
             p["cost"], p["notes"], event_id),
        )
        conn.commit()
    out = get_event(event_id)
    assert out is not None
    logger.info("Updated event #%d (status=%s)", event_id, out.status)
    return out


def set_status(event_id: int, status: str) -> Event:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_event(event_id, {"status": status})


def cancel_event(event_id: int) -> Event:
    return set_status(event_id, "Cancelled")


def complete_event(event_id: int) -> Event:
    return set_status(event_id, "Completed")


def delete_event(event_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM calendar_events WHERE event_id = ?",
            (event_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted event #%d", event_id)
            return True
        return False


# ── Summary ───────────────────────────────────────────────────────

def summary(*, upcoming_window_days: int = 14) -> Summary:
    init_db()
    today = _dt.date.today()
    today_iso = today.isoformat()
    horizon = (today + _dt.timedelta(days=upcoming_window_days)
                ).isoformat()
    monday = today - _dt.timedelta(days=today.weekday())
    sunday = monday + _dt.timedelta(days=6)

    rows = list_events()
    by_type = {t: 0 for t in EVENT_TYPES}
    by_aud  = {a: 0 for a in AUDIENCES}
    by_stat = {s: 0 for s in STATUSES}
    upcoming = 0
    today_count = 0
    week_count = 0
    for e in rows:
        by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
        by_aud[e.audience]    = by_aud.get(e.audience, 0) + 1
        by_stat[e.status]     = by_stat.get(e.status, 0) + 1
        if e.status == "Scheduled":
            if today_iso <= e.start_date <= horizon:
                upcoming += 1
        if e.occurs_on(today_iso):
            today_count += 1
        if (e.end_date >= monday.isoformat()
                and e.start_date <= sunday.isoformat()):
            week_count += 1

    return Summary(
        total=len(rows),
        by_type=by_type,
        by_audience=by_aud,
        by_status=by_stat,
        upcoming=upcoming,
        today_count=today_count,
        this_week_count=week_count,
    )
