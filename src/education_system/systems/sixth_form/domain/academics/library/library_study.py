"""Library study-space bookings (item 48).

Lightweight booking of the library's own silent desks / group rooms,
kept separate from the system-wide ``room_booking`` module (which
handles classrooms). Bookings clash-check on space + date + time range.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from dataclasses import dataclass

from education_system.systems.sixth_form.domain.academics.library import (
    library as _lib,
)

logger = logging.getLogger(__name__)

ValidationError = _lib.ValidationError

BOOKING_STATUSES: tuple[str, ...] = (
    "Booked", "Cancelled", "Completed", "No-show",
)
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _notify(method: str, *args) -> None:
    """Best-effort call into the sixth-form email system."""
    try:
        from education_system.systems.sixth_form.domain.academics.library import (
            library_notifications as _n,
        )
        getattr(_n, method)(*args)
    except Exception:
        logger.debug("Notification %s skipped", method, exc_info=True)


@dataclass
class StudyBooking:
    booking_id: int
    space: str
    student_id: str | None
    staff: str | None
    date: str
    start_time: str
    end_time: str
    purpose: str | None
    status: str
    created_at: str


def _row(r) -> StudyBooking:
    return StudyBooking(
        booking_id=r["booking_id"], space=r["space"],
        student_id=r["student_id"], staff=r["staff"],
        date=r["date"], start_time=r["start_time"],
        end_time=r["end_time"], purpose=r["purpose"],
        status=r["status"], created_at=r["created_at"])


def _check_time(label: str, value: str) -> str:
    if not _TIME_RE.match(value or ""):
        raise ValidationError(f"{label} must be HH:MM (24h)")
    return value


def book(space: str, *, date: str, start_time: str, end_time: str,
         student_id: str | None = None, staff: str | None = None,
         purpose: str | None = None) -> StudyBooking:
    _lib.init_db()
    if not (space or "").strip():
        raise ValidationError("Space is required")
    if not _lib._DATE_RE.match(date or ""):
        raise ValidationError("Date must be YYYY-MM-DD")
    start = _check_time("Start time", start_time)
    end = _check_time("End time", end_time)
    if end <= start:
        raise ValidationError("End time must be after start time")
    if student_id:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        if _students.get_student(student_id) is None:
            raise ValidationError(f"No student with id {student_id}")
    # Clash detection: same space/date with overlapping time, active.
    for b in list_bookings(space=space.strip(), date=date):
        if b.status != "Booked":
            continue
        if start < b.end_time and end > b.start_time:
            raise ValidationError(
                f"Clashes with booking #{b.booking_id} "
                f"({b.start_time}-{b.end_time})")
    with _lib._connect() as conn:
        cur = conn.execute(
            "INSERT INTO library_study_bookings "
            "(space, student_id, staff, date, start_time, end_time, "
            " purpose, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'Booked', datetime('now'))",
            (space.strip(), (student_id or "").strip() or None,
             (staff or "").strip() or None, date, start, end,
             (purpose or "").strip() or None))
        conn.commit()
        bid = cur.lastrowid
    logger.info("Study booking #%d: %s on %s %s-%s",
                bid, space, date, start, end)
    out = get_booking(bid)
    assert out is not None
    _notify("notify_study_booking", out)
    return out


def get_booking(booking_id: int) -> StudyBooking | None:
    _lib.init_db()
    with _lib._connect() as conn:
        r = conn.execute(
            "SELECT * FROM library_study_bookings "
            "WHERE booking_id = ?", (booking_id,)).fetchone()
    return _row(r) if r else None


def list_bookings(*, space: str | None = None,
                  date: str | None = None,
                  student_id: str | None = None,
                  status: str | None = None) -> list[StudyBooking]:
    _lib.init_db()
    clauses, args = [], []
    if space:
        clauses.append("space = ?")
        args.append(space.strip())
    if date:
        clauses.append("date = ?")
        args.append(date)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if status:
        clauses.append("status = ?")
        args.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _lib._connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM library_study_bookings {where} "
            "ORDER BY date, start_time, space", args).fetchall()
    return [_row(r) for r in rows]


def set_status(booking_id: int, status: str) -> StudyBooking:
    if status not in BOOKING_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(BOOKING_STATUSES)}")
    if get_booking(booking_id) is None:
        raise ValidationError(f"No booking #{booking_id}")
    with _lib._connect() as conn:
        conn.execute(
            "UPDATE library_study_bookings SET status = ? "
            "WHERE booking_id = ?", (status, int(booking_id)))
        conn.commit()
    out = get_booking(booking_id)
    assert out is not None
    return out


def cancel(booking_id: int) -> StudyBooking:
    return set_status(booking_id, "Cancelled")
