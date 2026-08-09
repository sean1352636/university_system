"""Ad-hoc room bookings — anything outside the weekly timetable.

The timetable owns the recurring weekly grid; this module owns one-off bookings
(an exam, a parents' evening, an employer visit) on a specific date. A booking
must not collide with either another booking or a timetabled session, so the
clash check takes both.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time

from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

BOOKING_STATUSES = ("requested", "confirmed", "cancelled")

BOOKING_PURPOSES = (
    "Examination",
    "Additional class",
    "Meeting",
    "Employer / industry visit",
    "Open event",
    "Enrichment",
    "Staff training",
    "Maintenance",
)


def _to_time(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"'{value}' is not a valid time (expected HH:MM)") from exc


@dataclass
class Booking:
    """One room booked for a period on a specific date."""

    booking_id: int | None
    room_id: str
    booking_date: date | None
    start_time: str = "09:00"
    end_time: str = "10:00"
    purpose: str = "Meeting"
    booked_by: str = ""              # staff_id
    status: str = "confirmed"
    headcount: int = 0
    notes: str = ""

    @property
    def is_live(self) -> bool:
        return self.status in ("requested", "confirmed")

    @property
    def label(self) -> str:
        when = self.booking_date.isoformat() if self.booking_date else "unscheduled"
        return f"{self.room_id} {when} {self.start_time}-{self.end_time}"

    def overlaps(self, other: "Booking") -> bool:
        """Whether two bookings collide in the same room on the same date."""
        if self.room_id != other.room_id or self.booking_date != other.booking_date:
            return False
        if not (self.is_live and other.is_live):
            return False
        if self.booking_id is not None and self.booking_id == other.booking_id:
            return False
        # Half-open intervals: a booking ending at 10:00 and one starting at
        # 10:00 are back-to-back, not overlapping.
        return (
            _to_time(self.start_time) < _to_time(other.end_time)
            and _to_time(other.start_time) < _to_time(self.end_time)
        )

    def validate(self) -> None:
        if not self.room_id.strip():
            raise ValidationError("A booking needs a room")
        if self.booking_date is None:
            raise ValidationError("A booking needs a date")
        if self.purpose not in BOOKING_PURPOSES:
            raise ValidationError(f"Unknown booking purpose '{self.purpose}'")
        if self.status not in BOOKING_STATUSES:
            raise ValidationError(f"Unknown booking status '{self.status}'")
        if self.headcount < 0:
            raise ValidationError("Headcount cannot be negative")
        if _to_time(self.end_time) <= _to_time(self.start_time):
            raise ValidationError("A booking must end after it starts")

    def to_row(self) -> dict:
        return {
            "room_id": self.room_id.strip().upper(),
            "booking_date": self.booking_date.isoformat() if self.booking_date else None,
            "start_time": self.start_time.strip(),
            "end_time": self.end_time.strip(),
            "purpose": self.purpose,
            "booked_by": optional_ref(self.booked_by),
            "status": self.status,
            "headcount": int(self.headcount),
            "notes": self.notes.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Booking":
        d = dict(row)
        return cls(
            booking_id=d.get("booking_id"),
            room_id=d.get("room_id") or "",
            booking_date=parse_date(d.get("booking_date")),
            start_time=d.get("start_time") or "09:00",
            end_time=d.get("end_time") or "10:00",
            purpose=d.get("purpose") or "Meeting",
            booked_by=d.get("booked_by") or "",
            status=d.get("status") or "confirmed",
            headcount=int(d.get("headcount") or 0),
            notes=d.get("notes") or "",
        )


def find_clashes(booking: Booking, existing: list[Booking]) -> list[str]:
    """Descriptions of every existing booking ``booking`` collides with."""
    return [
        f"{other.room_id} is already booked {other.start_time}-{other.end_time} "
        f"for {other.purpose}"
        for other in existing
        if booking.overlaps(other)
    ]


__all__ = ["BOOKING_PURPOSES", "BOOKING_STATUSES", "Booking", "find_clashes"]
