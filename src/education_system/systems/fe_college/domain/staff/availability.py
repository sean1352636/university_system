"""Staff availability — when a member of staff can be timetabled.

Sessional and part-time staff are only on site on certain days, so the
timetable service must be able to ask "is this lecturer free in this slot?"
before assigning a class. Availability is expressed as a set of (day, period)
slots a member of staff is *not* available, since the common case is "available
except…" and storing the exceptions keeps the table small.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from education_system.systems.fe_college.config import PERIODS, WEEKDAYS
from education_system.systems.fe_college.domain.students.models import ValidationError

PERIOD_CODES: tuple[str, ...] = tuple(code for code, _s, _e in PERIODS)

UNAVAILABILITY_REASONS = (
    "Not contracted",
    "Other employment",
    "Remission (management)",
    "Study leave",
    "Long-term absence",
    "Other commitment",
)


@dataclass(frozen=True)
class Slot:
    """A single timetable slot: a weekday and a period code."""

    day: str
    period: str

    def __str__(self) -> str:
        return f"{self.day} {self.period}"

    @property
    def times(self) -> tuple[str, str]:
        """(start, end) clock times for this slot's period."""
        for code, start, end in PERIODS:
            if code == self.period:
                return start, end
        return "", ""

    def validate(self) -> None:
        if self.day not in WEEKDAYS:
            raise ValidationError(f"'{self.day}' is not a teaching day")
        if self.period not in PERIOD_CODES:
            raise ValidationError(f"'{self.period}' is not a valid period")


@dataclass
class Availability:
    """When one member of staff can be timetabled."""

    staff_id: str
    unavailable: set[Slot] = field(default_factory=set)
    reason: str = ""

    def is_free(self, day: str, period: str) -> bool:
        return Slot(day, period) not in self.unavailable

    def block(self, day: str, period: str, reason: str = "") -> None:
        """Mark a slot as unavailable."""
        slot = Slot(day, period)
        slot.validate()
        self.unavailable.add(slot)
        if reason:
            self.reason = reason

    def unblock(self, day: str, period: str) -> None:
        self.unavailable.discard(Slot(day, period))

    def block_day(self, day: str, reason: str = "") -> None:
        """Mark a whole day unavailable — the usual part-time pattern."""
        if day not in WEEKDAYS:
            raise ValidationError(f"'{day}' is not a teaching day")
        for period in PERIOD_CODES:
            self.unavailable.add(Slot(day, period))
        if reason:
            self.reason = reason

    @property
    def available_slots(self) -> int:
        return len(WEEKDAYS) * len(PERIOD_CODES) - len(self.unavailable)

    def validate(self) -> None:
        if not self.staff_id.strip():
            raise ValidationError("Availability needs a staff member")
        if self.reason and self.reason not in UNAVAILABILITY_REASONS:
            raise ValidationError(f"Unknown unavailability reason '{self.reason}'")
        for slot in self.unavailable:
            slot.validate()

    def to_rows(self) -> list[dict]:
        """Flatten to one row per blocked slot, as the repository stores it."""
        return [
            {
                "staff_id": self.staff_id.strip(),
                "day": s.day,
                "period": s.period,
                "reason": self.reason,
            }
            for s in sorted(self.unavailable, key=lambda s: (WEEKDAYS.index(s.day), s.period))
        ]

    @classmethod
    def from_rows(cls, staff_id: str, rows) -> "Availability":
        av = cls(staff_id=staff_id)
        for row in rows:
            d = dict(row)
            av.unavailable.add(Slot(d.get("day") or "", d.get("period") or ""))
            if d.get("reason"):
                av.reason = d["reason"]
        return av


__all__ = [
    "PERIOD_CODES",
    "UNAVAILABILITY_REASONS",
    "Availability",
    "Slot",
]
