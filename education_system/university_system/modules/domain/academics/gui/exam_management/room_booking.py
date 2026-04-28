"""Reservation of physical rooms for scheduled exams.

Delegates to the canonical :class:`RoomBookingService` (campus.room_booking)
so exams share the same ``room_bookings`` table — and the same clash
detection — as lectures, society events, and ad-hoc bookings.

Each exam owns at most one booking. The mapping between an exam and its
booking is recorded by embedding ``[exam:<id>]`` in the booking's purpose
text (the service has no native external-ref column), letting us locate
and update or cancel the same row without changing the schema.

Recurring weekly lecture slots in ``module_schedule`` are checked
separately because the service only knows about ``room_bookings``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from education_system.university_system.modules.domain.academics.gui.exam_management.models import Exam

logger = logging.getLogger(__name__)

_EXAM_MARKER = "[exam:{}]"
_BOOKING_TYPE = "exam"


def _service():
    """Return a RoomBookingService instance, or None if unavailable."""
    try:
        from education_system.university_system.modules.domain.campus.room_booking.services.room_booking_service import (
            RoomBookingService,
        )
        return RoomBookingService()
    except Exception as exc:
        logger.debug("RoomBookingService unavailable: %s", exc)
        return None


def _resolve_room_id(room_name: str) -> Optional[int]:
    """Map the exam's free-text room field to a rooms.id, or None."""
    if not room_name:
        return None
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
    except Exception:
        return None
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM rooms WHERE room_name = ? OR room_number = ? LIMIT 1",
                (room_name, room_name),
            ).fetchone()
        return row[0] if row else None
    except Exception as exc:
        logger.debug("Room lookup failed for %r: %s", room_name, exc)
        return None


def _find_booking_id_for_exam(exam_id) -> Optional[int]:
    """Return the room_bookings.booking_id linked to *exam_id*, if any."""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
    except Exception:
        return None
    try:
        marker = _EXAM_MARKER.format(exam_id)
        with get_connection() as conn:
            row = conn.execute(
                "SELECT booking_id FROM room_bookings "
                "WHERE booking_type = ? AND purpose LIKE ? "
                "  AND booking_status != 'cancelled' "
                "ORDER BY booking_id DESC LIMIT 1",
                (_BOOKING_TYPE, f"%{marker}%"),
            ).fetchone()
        return row[0] if row else None
    except Exception as exc:
        logger.debug("Booking lookup failed for exam %s: %s", exam_id, exc)
        return None


def _purpose_for(exam: Exam) -> str:
    return (
        f"Exam: {exam.module_code} - {exam.module_name} "
        f"{_EXAM_MARKER.format(exam.id)}"
    )


def reserve_room_for_exam(exam: Exam,
                          booked_by: str = "exam_management") -> bool:
    """Create-or-reschedule the room booking for *exam*. Returns True on
    success.

    On a clash with another booking the underlying service raises; we
    swallow it and return False so the GUI can surface the situation
    through :func:`find_external_conflicts` instead. (The GUI calls the
    conflict helper *before* this, with a confirmation dialog, so by the
    time we get here the user has already accepted any overlap.)
    """
    svc = _service()
    if svc is None:
        return False

    room_id = _resolve_room_id(exam.room)
    if room_id is None:
        logger.info("Skipping room reservation: no rooms row matches %r",
                    exam.room)
        return False

    start_dt = f"{exam.date} {exam.start_time}"
    end_dt = f"{exam.date} {exam.end_time}"

    existing_id = _find_booking_id_for_exam(exam.id)
    try:
        if existing_id is not None:
            # Reschedule (and update room/purpose) by cancelling +
            # recreating; the service exposes reschedule but not
            # room/purpose edits, so we go through cancel→create when
            # anything other than time changed. For simplicity always
            # cancel-then-create — it's idempotent and the cancelled
            # row is preserved for audit.
            svc.cancel_booking(int(existing_id))

        svc.create_booking(
            room_id=room_id,
            start_datetime=start_dt,
            end_datetime=end_dt,
            booked_by=booked_by,
            purpose=_purpose_for(exam),
            booking_type=_BOOKING_TYPE,
        )
        logger.info("Reserved room '%s' for exam %s", exam.room, exam.id)
        return True
    except Exception as exc:
        logger.warning("Room reservation refused for exam %s: %s",
                       exam.id, exc)
        return False


def release_room_for_exam(exam_id) -> bool:
    """Cancel the room booking owned by *exam_id*, if any."""
    svc = _service()
    if svc is None:
        return False
    booking_id = _find_booking_id_for_exam(exam_id)
    if booking_id is None:
        return True  # nothing to release — treat as success
    try:
        svc.cancel_booking(int(booking_id))
        return True
    except Exception as exc:
        logger.error("Failed to cancel booking for exam %s: %s",
                     exam_id, exc)
        return False


# ── Conflict detection ─────────────────────────────────────────────────

_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday",
              "Friday", "Saturday", "Sunday")


def _day_of_week(date_str: str) -> Optional[str]:
    try:
        return _DAY_NAMES[datetime.strptime(date_str, "%Y-%m-%d").weekday()]
    except ValueError:
        return None


def _intervals_overlap(a_start: str, a_end: str,
                       b_start: str, b_end: str) -> bool:
    """Half-open interval overlap test."""
    return a_start < b_end and a_end > b_start


def find_external_conflicts(date: str, start_time: str, end_time: str,
                            room_name: str,
                            exclude_exam_id: Optional[int] = None
                            ) -> List[Tuple[str, str]]:
    """Return [(source, description), ...] of bookings/lectures that
    overlap the interval on this room.

    Sources:
    - ``room_bookings`` via :meth:`RoomBookingService.list_bookings`
      (any booking_type other than the exam's own booking).
    - ``module_schedule`` weekly lectures whose day-of-week matches
      *date* and whose times overlap.
    """
    svc = _service()
    if svc is None:
        return []

    room_id = _resolve_room_id(room_name)
    if room_id is None:
        return []

    conflicts: List[Tuple[str, str]] = []
    start_dt = f"{date} {start_time}"
    end_dt = f"{date} {end_time}"
    exclude_marker = (_EXAM_MARKER.format(exclude_exam_id)
                      if exclude_exam_id is not None else None)

    # 1) room_bookings overlap
    try:
        for b in svc.list_bookings(room_id=room_id, on_date=date):
            if b.get("booking_status") == "cancelled":
                continue
            if exclude_marker and exclude_marker in (b.get("purpose") or ""):
                continue
            if _intervals_overlap(start_dt, end_dt,
                                  b["start_datetime"], b["end_datetime"]):
                conflicts.append((
                    f"room_bookings#{b['booking_id']}",
                    f"{b.get('booking_type','?')}: {b.get('purpose','')} "
                    f"({b['start_datetime']} – {b['end_datetime']})",
                ))
    except Exception as exc:
        logger.debug("list_bookings failed: %s", exc)

    # 2) module_schedule recurring weekly lecture
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        dow = _day_of_week(date)
        if dow:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT module_code, day_of_week, start_time, end_time "
                    "FROM module_schedule "
                    "WHERE room_id = ? AND day_of_week = ? "
                    "  AND COALESCE(status,'') != 'cancelled' "
                    "  AND start_time < ? AND end_time > ?",
                    (room_id, dow, end_time, start_time),
                ).fetchall()
            for code, _dow, lst, let in rows:
                conflicts.append((
                    "module_schedule",
                    f"Lecture {code} every {dow} {lst}–{let}",
                ))
    except Exception as exc:
        logger.debug("module_schedule check failed: %s", exc)

    return conflicts
