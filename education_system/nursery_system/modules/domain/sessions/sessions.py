"""Domain layer for Sessions & Bookings (Nursery System).

The setting's booking calendar. Three tables, layered:

* ``booking_patterns`` — a child's **contracted weekly pattern**: which
  weekdays, which session (am / pm / all-day), between which dates, funded or
  paid. This is the baseline everything else is measured against.
* ``session_bookings`` — the **dated exceptions**: an ad-hoc extra session on
  top of the contract, or a cancellation of a contracted one.
* ``setting_closures`` — the dates the setting (or one room) is **shut**, so a
  closed day resolves to zero booked children rather than a hall of breaches.

Resolving a date is therefore: take that weekday's live patterns, drop the
cancellations, add the extras, and return nothing at all if the day is closed.
``day_sessions`` does exactly that, and ``room_day_capacity`` compares the
result against each room's capacity so an over-booked day is visible before it
happens.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``sessions_cli.py``, Tk GUI in ``sessions_views.py``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Sessions & Bookings"
CATEGORY = "Children & Admissions"

PATTERN_PREFIX = "NBP"
BOOKING_PREFIX = "NSB"
CLOSURE_PREFIX = "NCL"
ID_DIGITS = 3

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday")

SESSION_TYPES = ("am", "pm", "all-day")
FUNDING_TYPES = ("funded", "paid", "mixed")
PATTERN_STATUSES = ("active", "ended")
BOOKING_KINDS = ("extra", "cancellation")
BOOKING_STATUSES = ("confirmed", "requested", "declined")
CLOSURE_TYPES = ("holiday", "bank-holiday", "inset", "emergency")

# The session times a setting defaults to when none are given. Overridable per
# pattern / booking — these only fill the blanks.
DEFAULT_TIMES: dict[str, tuple[str, str]] = {
    "am": ("08:00", "13:00"),
    "pm": ("13:00", "18:00"),
    "all-day": ("08:00", "18:00"),
}

# Hours each session type counts for when totalling a child's booked hours.
SESSION_HOURS: dict[str, float] = {"am": 5.0, "pm": 5.0, "all-day": 10.0}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid session / booking input."""


@dataclass
class BookingPattern:
    pattern_id: str
    pupil_id: str
    weekday: int
    session_type: str
    start_time: str | None
    end_time: str | None
    room: str | None
    funding: str
    start_date: str
    end_date: str | None
    status: str
    notes: str | None
    child_name: str | None = None

    @property
    def weekday_name(self) -> str:
        return WEEKDAYS[self.weekday] if 0 <= self.weekday < 7 else "?"

    @property
    def hours(self) -> float:
        return SESSION_HOURS.get(self.session_type, 0.0)


@dataclass
class SessionBooking:
    booking_id: str
    pupil_id: str
    session_date: str
    session_type: str
    kind: str
    start_time: str | None
    end_time: str | None
    room: str | None
    chargeable: bool
    notice_days: int | None
    reason: str | None
    status: str
    notes: str | None
    child_name: str | None = None


@dataclass
class Closure:
    closure_id: str
    name: str
    start_date: str
    end_date: str
    closure_type: str
    room: str | None
    chargeable: bool
    notes: str | None

    @property
    def whole_setting(self) -> bool:
        return not self.room

    def covers(self, day: str, room: str | None = None) -> bool:
        if not (self.start_date <= day <= self.end_date):
            return False
        return self.whole_setting or (room is not None and room == self.room)


@dataclass
class DaySession:
    """One child's resolved session on one date."""

    pupil_id: str
    child_name: str | None
    session_date: str
    session_type: str
    start_time: str | None
    end_time: str | None
    room: str | None
    source: str  # 'contracted' or 'extra'
    funding: str | None
    source_id: str

    @property
    def hours(self) -> float:
        return SESSION_HOURS.get(self.session_type, 0.0)


@dataclass
class RoomDay:
    """A room's booked headcount for a date against its capacity."""

    room: str
    capacity: int
    booked: int

    @property
    def free(self) -> int:
        return self.capacity - self.booked

    @property
    def over_capacity(self) -> bool:
        return self.capacity > 0 and self.booked > self.capacity


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for sessions")
        raise


# ── Validation helpers ───────────────────────────────────────────────────────

def _opt(value: Any) -> str | None:
    # ``value or ""`` would swallow a legitimate 0 (weekday Monday, 0 days'
    # notice), so test for None explicitly.
    v = "" if value is None else str(value).strip()
    return v or None


def _today() -> str:
    return _dt.date.today().isoformat()


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "y", "yes", "true", "on")
    return bool(value)


def _check_date(value: Any, label: str, *, required: bool = True) -> str | None:
    v = _opt(value)
    if v is None:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(v)
    except ValueError as e:
        raise ValidationError(f"{label} is not a real date") from e
    return v


def _check_time(value: Any, label: str) -> str | None:
    v = _opt(value)
    if v is None:
        return None
    if not _TIME_RE.match(v):
        raise ValidationError(f"{label} must be HH:MM")
    hh, mm = int(v[:2]), int(v[3:])
    if hh > 23 or mm > 59:
        raise ValidationError(f"{label} is not a real time")
    return v


def _check_choice(value: Any, choices: tuple[str, ...], label: str,
                  default: str) -> str:
    v = (str(value or "").strip().lower() or default)
    if v not in choices:
        raise ValidationError(f"{label} must be one of: " + ", ".join(choices))
    return v


def _check_weekday(value: Any) -> int:
    v = "" if value is None else str(value).strip()
    if not v:
        raise ValidationError("Weekday is required")
    # Accept both "0"–"6" and a day name / prefix ("Mon", "monday").
    if v.isdigit():
        n = int(v)
        if not 0 <= n <= 6:
            raise ValidationError("Weekday must be 0 (Monday) to 6 (Sunday)")
        return n
    lower = v.lower()
    for i, name in enumerate(WEEKDAYS):
        if name.lower().startswith(lower):
            return i
    raise ValidationError("Weekday must be a day name or 0 (Monday) to 6 (Sunday)")


def _fill_times(session_type: str, start: str | None,
                end: str | None) -> tuple[str | None, str | None]:
    default_start, default_end = DEFAULT_TIMES.get(session_type, (None, None))
    start = start or default_start
    end = end or default_end
    if start and end and end <= start:
        raise ValidationError("End time must be after the start time")
    return start, end


def _require_pupil(conn: sqlite3.Connection, pupil_id: str) -> None:
    if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                        (pupil_id,)).fetchone():
        raise ValidationError(f"No child on roll with id {pupil_id}")


# ── ID allocation ────────────────────────────────────────────────────────────

def _generate_id(table: str, column: str, prefix: str) -> str:
    """Allocate the next free ``<prefix>NNN`` id for a table."""
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                f"SELECT {column} FROM {table}").fetchall()}  # noqa: S608
    except sqlite3.Error:
        logger.exception("Could not read existing ids from %s", table)
        raise
    seq = 1
    while f"{prefix}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{prefix}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        candidate = f"{prefix}{n}"
        if candidate not in existing:
            return candidate
    raise RuntimeError(f"Could not allocate a unique id for {table}")


def generate_pattern_id() -> str:
    return _generate_id("booking_patterns", "pattern_id", PATTERN_PREFIX)


def generate_booking_id() -> str:
    return _generate_id("session_bookings", "booking_id", BOOKING_PREFIX)


def generate_closure_id() -> str:
    return _generate_id("setting_closures", "closure_id", CLOSURE_PREFIX)


# ── Row mapping ──────────────────────────────────────────────────────────────

def _pattern_row(r: sqlite3.Row) -> BookingPattern:
    keys = r.keys()
    return BookingPattern(
        pattern_id=r["pattern_id"], pupil_id=r["pupil_id"],
        weekday=int(r["weekday"]), session_type=r["session_type"],
        start_time=r["start_time"], end_time=r["end_time"], room=r["room"],
        funding=r["funding"], start_date=r["start_date"],
        end_date=r["end_date"], status=r["status"], notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
    )


def _booking_row(r: sqlite3.Row) -> SessionBooking:
    keys = r.keys()
    return SessionBooking(
        booking_id=r["booking_id"], pupil_id=r["pupil_id"],
        session_date=r["session_date"], session_type=r["session_type"],
        kind=r["kind"], start_time=r["start_time"], end_time=r["end_time"],
        room=r["room"], chargeable=bool(r["chargeable"]),
        notice_days=r["notice_days"], reason=r["reason"], status=r["status"],
        notes=r["notes"],
        child_name=r["child_name"] if "child_name" in keys else None,
    )


def _closure_row(r: sqlite3.Row) -> Closure:
    return Closure(
        closure_id=r["closure_id"], name=r["name"],
        start_date=r["start_date"], end_date=r["end_date"],
        closure_type=r["closure_type"], room=r["room"],
        chargeable=bool(r["chargeable"]), notes=r["notes"],
    )


_PATTERN_SELECT = """
SELECT b.*, TRIM(p.first_name || ' ' || p.last_name) AS child_name
FROM booking_patterns b
LEFT JOIN pupils p ON p.pupil_id = b.pupil_id
"""

_BOOKING_SELECT = """
SELECT s.*, TRIM(p.first_name || ' ' || p.last_name) AS child_name
FROM session_bookings s
LEFT JOIN pupils p ON p.pupil_id = s.pupil_id
"""


# ── Contracted weekly patterns ───────────────────────────────────────────────

def list_patterns(*, pupil_id: str | None = None, weekday: int | None = None,
                  status: str | None = None) -> list[BookingPattern]:
    _ensure_schema()
    clauses: list[str] = []
    params: list[Any] = []
    if pupil_id:
        clauses.append("b.pupil_id = ?")
        params.append(pupil_id)
    if weekday is not None:
        clauses.append("b.weekday = ?")
        params.append(weekday)
    if status:
        clauses.append("b.status = ?")
        params.append(status)
    sql = _PATTERN_SELECT
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY b.weekday, b.session_type, child_name"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_patterns failed")
        raise
    return [_pattern_row(r) for r in rows]


def get_pattern(pattern_id: str) -> BookingPattern | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(_PATTERN_SELECT + " WHERE b.pattern_id = ?",
                               (pattern_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_pattern(%s) failed", pattern_id)
        raise
    return _pattern_row(row) if row else None


def _validate_pattern(data: dict[str, Any], *,
                      require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = _opt(data.get("pupil_id"))
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid
    out["weekday"] = _check_weekday(data.get("weekday"))
    out["session_type"] = _check_choice(
        data.get("session_type"), SESSION_TYPES, "Session", "all-day")
    start = _check_time(data.get("start_time"), "Start time")
    end = _check_time(data.get("end_time"), "End time")
    out["start_time"], out["end_time"] = _fill_times(
        out["session_type"], start, end)
    out["room"] = _opt(data.get("room"))
    out["funding"] = _check_choice(
        data.get("funding"), FUNDING_TYPES, "Funding", "funded")
    out["start_date"] = _check_date(
        data.get("start_date") or _today(), "Start date")
    out["end_date"] = _check_date(data.get("end_date"), "End date",
                                  required=False)
    if out["end_date"] and out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before the start date")
    out["status"] = _check_choice(
        data.get("status"), PATTERN_STATUSES, "Status", "active")
    out["notes"] = _opt(data.get("notes"))
    return out


def create_pattern(data: dict[str, Any]) -> BookingPattern:
    """Add a contracted weekly session for a child."""
    _ensure_schema()
    payload = _validate_pattern(data)
    pid = generate_pattern_id()
    try:
        with connect() as conn:
            _require_pupil(conn, payload["pupil_id"])
            conn.execute(
                """
                INSERT INTO booking_patterns (
                    pattern_id, pupil_id, weekday, session_type, start_time,
                    end_time, room, funding, start_date, end_date, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pid, payload["pupil_id"], payload["weekday"],
                 payload["session_type"], payload["start_time"],
                 payload["end_time"], payload["room"], payload["funding"],
                 payload["start_date"], payload["end_date"], payload["status"],
                 payload["notes"]),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        raise ValidationError(
            "That child already has a session booked for that weekday and "
            "session, starting on that date."
        ) from e
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for booking pattern %s", pid)
        raise ValidationError(f"Could not create pattern — {e}") from e
    p = get_pattern(pid)
    assert p is not None
    logger.info("Created booking pattern %s for pupil %s (%s %s)",
                pid, payload["pupil_id"], p.weekday_name, p.session_type)
    return p


def update_pattern(pattern_id: str, data: dict[str, Any]) -> BookingPattern:
    _ensure_schema()
    existing = get_pattern(pattern_id)
    if existing is None:
        raise ValidationError(f"No booking pattern with id {pattern_id}")
    payload = _validate_pattern(data, require_pupil=False)
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE booking_patterns SET
                    weekday = ?, session_type = ?, start_time = ?, end_time = ?,
                    room = ?, funding = ?, start_date = ?, end_date = ?,
                    status = ?, notes = ?
                WHERE pattern_id = ?
                """,
                (payload["weekday"], payload["session_type"],
                 payload["start_time"], payload["end_time"], payload["room"],
                 payload["funding"], payload["start_date"], payload["end_date"],
                 payload["status"], payload["notes"], pattern_id),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        raise ValidationError(
            "Another pattern already covers that weekday and session for this "
            "child."
        ) from e
    except sqlite3.Error:
        logger.exception("UPDATE failed for booking pattern %s", pattern_id)
        raise
    p = get_pattern(pattern_id)
    assert p is not None
    logger.info("Updated booking pattern %s", pattern_id)
    return p


def end_pattern(pattern_id: str, end_date: str | None = None) -> BookingPattern:
    """Close a contracted session off from ``end_date`` (default today)."""
    _ensure_schema()
    existing = get_pattern(pattern_id)
    if existing is None:
        raise ValidationError(f"No booking pattern with id {pattern_id}")
    day = _check_date(end_date or _today(), "End date")
    assert day is not None
    if day < existing.start_date:
        raise ValidationError("End date cannot be before the start date")
    try:
        with connect() as conn:
            conn.execute(
                "UPDATE booking_patterns SET end_date = ?, status = 'ended' "
                "WHERE pattern_id = ?", (day, pattern_id))
            conn.commit()
    except sqlite3.Error:
        logger.exception("Could not end booking pattern %s", pattern_id)
        raise
    p = get_pattern(pattern_id)
    assert p is not None
    logger.info("Ended booking pattern %s on %s", pattern_id, day)
    return p


def delete_pattern(pattern_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM booking_patterns WHERE pattern_id = ?",
                (pattern_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting booking pattern %s", pattern_id)
        raise
    if deleted:
        logger.info("Deleted booking pattern %s", pattern_id)
    return deleted


# ── Dated exceptions: extras and cancellations ───────────────────────────────

def list_bookings(*, pupil_id: str | None = None,
                  session_date: str | None = None,
                  date_from: str | None = None, date_to: str | None = None,
                  kind: str | None = None) -> list[SessionBooking]:
    _ensure_schema()
    clauses: list[str] = []
    params: list[Any] = []
    if pupil_id:
        clauses.append("s.pupil_id = ?")
        params.append(pupil_id)
    if session_date:
        clauses.append("s.session_date = ?")
        params.append(session_date)
    if date_from:
        clauses.append("s.session_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("s.session_date <= ?")
        params.append(date_to)
    if kind:
        clauses.append("s.kind = ?")
        params.append(kind)
    sql = _BOOKING_SELECT
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY s.session_date DESC, child_name, s.session_type"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_bookings failed")
        raise
    return [_booking_row(r) for r in rows]


def get_booking(booking_id: str) -> SessionBooking | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(_BOOKING_SELECT + " WHERE s.booking_id = ?",
                               (booking_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_booking(%s) failed", booking_id)
        raise
    return _booking_row(row) if row else None


def _validate_booking(data: dict[str, Any], *,
                      require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = _opt(data.get("pupil_id"))
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid
    out["session_date"] = _check_date(data.get("session_date"), "Session date")
    out["session_type"] = _check_choice(
        data.get("session_type"), SESSION_TYPES, "Session", "all-day")
    out["kind"] = _check_choice(data.get("kind"), BOOKING_KINDS, "Kind", "extra")
    start = _check_time(data.get("start_time"), "Start time")
    end = _check_time(data.get("end_time"), "End time")
    if out["kind"] == "extra":
        out["start_time"], out["end_time"] = _fill_times(
            out["session_type"], start, end)
    else:
        out["start_time"], out["end_time"] = start, end
    out["room"] = _opt(data.get("room"))
    out["chargeable"] = _as_bool(data.get("chargeable", out["kind"] == "extra"))
    notice = _opt(data.get("notice_days"))
    if notice is None:
        out["notice_days"] = None
    else:
        try:
            out["notice_days"] = int(notice)
        except ValueError as e:
            raise ValidationError("Notice (days) must be a whole number") from e
        if out["notice_days"] < 0:
            raise ValidationError("Notice (days) cannot be negative")
    out["reason"] = _opt(data.get("reason"))
    out["status"] = _check_choice(
        data.get("status"), BOOKING_STATUSES, "Status", "confirmed")
    out["notes"] = _opt(data.get("notes"))
    return out


def create_booking(data: dict[str, Any]) -> SessionBooking:
    """Log an ad-hoc extra session or a cancellation for one date."""
    _ensure_schema()
    payload = _validate_booking(data)
    bid = generate_booking_id()
    try:
        with connect() as conn:
            _require_pupil(conn, payload["pupil_id"])
            conn.execute(
                """
                INSERT INTO session_bookings (
                    booking_id, pupil_id, session_date, session_type, kind,
                    start_time, end_time, room, chargeable, notice_days,
                    reason, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (bid, payload["pupil_id"], payload["session_date"],
                 payload["session_type"], payload["kind"],
                 payload["start_time"], payload["end_time"], payload["room"],
                 int(payload["chargeable"]), payload["notice_days"],
                 payload["reason"], payload["status"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        raise ValidationError(
            f"That child already has a {payload['kind']} logged for that "
            "session on that date."
        ) from e
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for session booking %s", bid)
        raise ValidationError(f"Could not create booking — {e}") from e
    b = get_booking(bid)
    assert b is not None
    logger.info("Created %s booking %s for pupil %s on %s",
                payload["kind"], bid, payload["pupil_id"],
                payload["session_date"])
    return b


def update_booking(booking_id: str, data: dict[str, Any]) -> SessionBooking:
    _ensure_schema()
    if get_booking(booking_id) is None:
        raise ValidationError(f"No booking with id {booking_id}")
    payload = _validate_booking(data, require_pupil=False)
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE session_bookings SET
                    session_date = ?, session_type = ?, kind = ?,
                    start_time = ?, end_time = ?, room = ?, chargeable = ?,
                    notice_days = ?, reason = ?, status = ?, notes = ?
                WHERE booking_id = ?
                """,
                (payload["session_date"], payload["session_type"],
                 payload["kind"], payload["start_time"], payload["end_time"],
                 payload["room"], int(payload["chargeable"]),
                 payload["notice_days"], payload["reason"], payload["status"],
                 payload["notes"], booking_id),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        raise ValidationError(
            "Another booking already covers that session on that date for this "
            "child."
        ) from e
    except sqlite3.Error:
        logger.exception("UPDATE failed for session booking %s", booking_id)
        raise
    b = get_booking(booking_id)
    assert b is not None
    logger.info("Updated session booking %s", booking_id)
    return b


def delete_booking(booking_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM session_bookings WHERE booking_id = ?",
                (booking_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting session booking %s", booking_id)
        raise
    if deleted:
        logger.info("Deleted session booking %s", booking_id)
    return deleted


def book_extra_session(pupil_id: str, session_date: str,
                       session_type: str = "all-day",
                       **extra: Any) -> SessionBooking:
    """Convenience wrapper: book an ad-hoc session on top of the contract."""
    return create_booking({"pupil_id": pupil_id, "session_date": session_date,
                           "session_type": session_type, "kind": "extra",
                           **extra})


def cancel_session(pupil_id: str, session_date: str,
                   session_type: str = "all-day",
                   **extra: Any) -> SessionBooking:
    """Convenience wrapper: cancel a contracted session for one date."""
    return create_booking({"pupil_id": pupil_id, "session_date": session_date,
                           "session_type": session_type, "kind": "cancellation",
                           "chargeable": extra.pop("chargeable", False),
                           **extra})


# ── Closures & holidays ──────────────────────────────────────────────────────

def list_closures(*, date_from: str | None = None,
                  date_to: str | None = None) -> list[Closure]:
    _ensure_schema()
    clauses: list[str] = []
    params: list[Any] = []
    if date_from:
        clauses.append("end_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("start_date <= ?")
        params.append(date_to)
    sql = "SELECT * FROM setting_closures"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY start_date"
    try:
        with connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_closures failed")
        raise
    return [_closure_row(r) for r in rows]


def get_closure(closure_id: str) -> Closure | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM setting_closures WHERE closure_id = ?",
                (closure_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_closure(%s) failed", closure_id)
        raise
    return _closure_row(row) if row else None


def _validate_closure(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = _opt(data.get("name"))
    if not name:
        raise ValidationError("Closure name is required")
    out["name"] = name
    out["start_date"] = _check_date(data.get("start_date"), "Start date")
    out["end_date"] = _check_date(
        data.get("end_date") or data.get("start_date"), "End date")
    if out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before the start date")
    out["closure_type"] = _check_choice(
        data.get("closure_type"), CLOSURE_TYPES, "Closure type", "holiday")
    out["room"] = _opt(data.get("room"))
    out["chargeable"] = _as_bool(data.get("chargeable"))
    out["notes"] = _opt(data.get("notes"))
    return out


def create_closure(data: dict[str, Any]) -> Closure:
    """Record a holiday, bank holiday, INSET day or emergency closure."""
    _ensure_schema()
    payload = _validate_closure(data)
    cid = generate_closure_id()
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO setting_closures (
                    closure_id, name, start_date, end_date, closure_type,
                    room, chargeable, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, payload["name"], payload["start_date"],
                 payload["end_date"], payload["closure_type"], payload["room"],
                 int(payload["chargeable"]), payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.exception("INSERT failed for closure %s", cid)
        raise ValidationError(f"Could not create closure — {e}") from e
    c = get_closure(cid)
    assert c is not None
    logger.info("Created closure %s (%s %s→%s)", cid, payload["name"],
                payload["start_date"], payload["end_date"])
    return c


def update_closure(closure_id: str, data: dict[str, Any]) -> Closure:
    _ensure_schema()
    if get_closure(closure_id) is None:
        raise ValidationError(f"No closure with id {closure_id}")
    payload = _validate_closure(data)
    try:
        with connect() as conn:
            conn.execute(
                """
                UPDATE setting_closures SET
                    name = ?, start_date = ?, end_date = ?, closure_type = ?,
                    room = ?, chargeable = ?, notes = ?
                WHERE closure_id = ?
                """,
                (payload["name"], payload["start_date"], payload["end_date"],
                 payload["closure_type"], payload["room"],
                 int(payload["chargeable"]), payload["notes"], closure_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("UPDATE failed for closure %s", closure_id)
        raise
    c = get_closure(closure_id)
    assert c is not None
    logger.info("Updated closure %s", closure_id)
    return c


def delete_closure(closure_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM setting_closures WHERE closure_id = ?",
                (closure_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting closure %s", closure_id)
        raise
    if deleted:
        logger.info("Deleted closure %s", closure_id)
    return deleted


def closures_on(day: str, room: str | None = None) -> list[Closure]:
    """Closures in force on ``day`` — whole-setting ones plus this room's."""
    return [c for c in list_closures(date_from=day, date_to=day)
            if c.covers(day, room)]


def is_closed(day: str, room: str | None = None) -> bool:
    """True when the whole setting (or ``room``, if given) is shut that day."""
    return bool(closures_on(day, room))


# ── Resolving a date ─────────────────────────────────────────────────────────

def day_sessions(day: str) -> list[DaySession]:
    """Every child booked in on ``day``, contract plus extras minus cancellations.

    Returns an empty list when the whole setting is closed. A room-only closure
    drops just that room's children.
    """
    _ensure_schema()
    day = _check_date(day, "Date") or _today()
    if is_closed(day):
        return []
    weekday = _dt.date.fromisoformat(day).weekday()

    contracted = [
        p for p in list_patterns(weekday=weekday, status="active")
        if p.start_date <= day and (not p.end_date or day <= p.end_date)
    ]
    same_day = list_bookings(session_date=day)
    cancelled = {
        (b.pupil_id, b.session_type) for b in same_day
        if b.kind == "cancellation" and b.status != "declined"
    }
    extras = [b for b in same_day
              if b.kind == "extra" and b.status == "confirmed"]

    rooms = _pupil_rooms()
    out: list[DaySession] = []
    for p in contracted:
        if (p.pupil_id, p.session_type) in cancelled:
            continue
        out.append(DaySession(
            pupil_id=p.pupil_id, child_name=p.child_name, session_date=day,
            session_type=p.session_type, start_time=p.start_time,
            end_time=p.end_time, room=p.room or rooms.get(p.pupil_id),
            source="contracted", funding=p.funding, source_id=p.pattern_id))
    booked = {(s.pupil_id, s.session_type) for s in out}
    for b in extras:
        if (b.pupil_id, b.session_type) in booked:
            continue
        start, end = _fill_times(b.session_type, b.start_time, b.end_time)
        out.append(DaySession(
            pupil_id=b.pupil_id, child_name=b.child_name, session_date=day,
            session_type=b.session_type, start_time=start, end_time=end,
            room=b.room or rooms.get(b.pupil_id), source="extra",
            funding=None, source_id=b.booking_id))

    closed_rooms = {c.room for c in list_closures(date_from=day, date_to=day)
                    if c.room}
    if closed_rooms:
        out = [s for s in out if s.room not in closed_rooms]
    out.sort(key=lambda s: ((s.child_name or "").lower(), s.session_type))
    return out


def _pupil_rooms() -> dict[str, str]:
    """Fallback room per active child, for sessions that don't name one."""
    try:
        with connect() as conn:
            return {r["pupil_id"]: r["room"] for r in conn.execute(
                "SELECT pupil_id, room FROM pupils WHERE status = 'active' "
                "AND room IS NOT NULL AND room <> ''").fetchall()}
    except sqlite3.Error:
        logger.exception("_pupil_rooms failed")
        return {}


def room_day_capacity(day: str) -> list[RoomDay]:
    """Booked headcount vs capacity for every open room on ``day``."""
    _ensure_schema()
    sessions = day_sessions(day)
    booked: dict[str, set[str]] = {}
    for s in sessions:
        if s.room:
            booked.setdefault(s.room, set()).add(s.pupil_id)
    try:
        with connect() as conn:
            rooms = conn.execute(
                "SELECT name, capacity FROM rooms WHERE status = 'open' "
                "ORDER BY min_age_months, name").fetchall()
    except sqlite3.Error:
        logger.exception("room_day_capacity failed")
        raise
    out = [RoomDay(room=r["name"], capacity=int(r["capacity"] or 0),
                   booked=len(booked.get(r["name"], ())))
           for r in rooms]
    known = {r.room for r in out}
    for name, pupils in sorted(booked.items()):
        if name not in known:
            # Children booked into a room that isn't open / defined — still
            # surfaced so the count never silently disappears.
            out.append(RoomDay(room=name, capacity=0, booked=len(pupils)))
    return out


def week_sessions(start_day: str) -> dict[str, list[DaySession]]:
    """Resolved sessions for the seven days from ``start_day``."""
    start = _check_date(start_day, "Start date") or _today()
    base = _dt.date.fromisoformat(start)
    return {(base + _dt.timedelta(days=i)).isoformat():
            day_sessions((base + _dt.timedelta(days=i)).isoformat())
            for i in range(7)}


def contracted_hours(pupil_id: str, on_day: str | None = None) -> float:
    """Weekly contracted hours for a child from their live patterns."""
    day = _check_date(on_day or _today(), "Date")
    assert day is not None
    return sum(
        p.hours for p in list_patterns(pupil_id=pupil_id, status="active")
        if p.start_date <= day and (not p.end_date or day <= p.end_date)
    )


# ── Pickers / summary ────────────────────────────────────────────────────────

def list_pupil_choices() -> list[tuple[str, str]]:
    """Return ``(pupil_id, "Name (id) — room")`` pairs for child pickers."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id, first_name, last_name, room FROM pupils "
                "WHERE status = 'active' ORDER BY last_name, first_name"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_pupil_choices failed")
        raise
    out = []
    for r in rows:
        room = f" — {r['room']}" if r["room"] else ""
        out.append((r["pupil_id"],
                    f"{r['first_name']} {r['last_name']} ({r['pupil_id']}){room}"))
    return out


def list_room_choices() -> list[str]:
    _ensure_schema()
    try:
        with connect() as conn:
            return [r[0] for r in conn.execute(
                "SELECT name FROM rooms ORDER BY min_age_months, name").fetchall()]
    except sqlite3.Error:
        logger.exception("list_room_choices failed")
        raise


def summary(day: str | None = None) -> dict[str, Any]:
    """Headline counts for the bookings board, for ``day`` (default today)."""
    day = _check_date(day or _today(), "Date")
    assert day is not None
    sessions = day_sessions(day)
    capacity = room_day_capacity(day)
    same_day = list_bookings(session_date=day)
    return {
        "date": day,
        "closed": is_closed(day),
        "closure_names": [c.name for c in closures_on(day)],
        "booked_children": len({s.pupil_id for s in sessions}),
        "booked_sessions": len(sessions),
        "extras": sum(1 for s in sessions if s.source == "extra"),
        "cancellations": sum(1 for b in same_day if b.kind == "cancellation"),
        "booked_hours": round(sum(s.hours for s in sessions), 1),
        "over_capacity_rooms": sum(1 for r in capacity if r.over_capacity),
        "active_patterns": len(list_patterns(status="active")),
        "upcoming_closures": len(list_closures(date_from=day)),
    }
