"""Exam series and sittings.

External assessment in FE runs in awarding-body *series* (e.g. "Summer 2026"),
each containing individual sittings with a date, a room and an invigilator.
Entries (:mod:`entries`) attach learners to sittings; results (:mod:`results`)
come back against them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time

from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

SERIES_STATUSES = ("planned", "entries_open", "entries_closed", "sitting", "results_released", "closed")

# Awarding-body entry deadlines are hard: a late entry costs the college a fee
# and a very late one cannot be made at all.
LATE_ENTRY_FEE = 35.00


@dataclass
class ExamSeries:
    """One awarding-body assessment window."""

    series_id: str
    name: str
    awarding_body: str = ""
    academic_year: str = ""
    status: str = "planned"
    entry_deadline: date | None = None
    late_entry_deadline: date | None = None
    results_date: date | None = None

    @property
    def entries_open(self) -> bool:
        return self.status == "entries_open"

    def is_late_entry(self, on: date | None = None) -> bool:
        """Whether an entry made now would attract the late fee."""
        if self.entry_deadline is None:
            return False
        return (on or date.today()) > self.entry_deadline

    def accepts_entries(self, on: date | None = None) -> bool:
        """Whether an entry can still be made at all."""
        if not self.entries_open:
            return False
        deadline = self.late_entry_deadline or self.entry_deadline
        if deadline is None:
            return True
        return (on or date.today()) <= deadline

    def validate(self) -> None:
        if not self.series_id.strip():
            raise ValidationError("Exam series needs a code")
        if not self.name.strip():
            raise ValidationError("Exam series needs a name")
        if self.status not in SERIES_STATUSES:
            raise ValidationError(f"Unknown exam-series status '{self.status}'")
        if (
            self.entry_deadline and self.late_entry_deadline
            and self.late_entry_deadline < self.entry_deadline
        ):
            raise ValidationError("Late-entry deadline cannot be before the standard deadline")

    def to_row(self) -> dict:
        return {
            "series_id": self.series_id.strip().upper(),
            "name": self.name.strip(),
            "awarding_body": self.awarding_body.strip(),
            "academic_year": self.academic_year.strip(),
            "status": self.status,
            "entry_deadline": self.entry_deadline.isoformat() if self.entry_deadline else None,
            "late_entry_deadline": (
                self.late_entry_deadline.isoformat() if self.late_entry_deadline else None
            ),
            "results_date": self.results_date.isoformat() if self.results_date else None,
        }

    @classmethod
    def from_row(cls, row) -> "ExamSeries":
        d = dict(row)
        return cls(
            series_id=d.get("series_id") or "",
            name=d.get("name") or "",
            awarding_body=d.get("awarding_body") or "",
            academic_year=d.get("academic_year") or "",
            status=d.get("status") or "planned",
            entry_deadline=parse_date(d.get("entry_deadline")),
            late_entry_deadline=parse_date(d.get("late_entry_deadline")),
            results_date=parse_date(d.get("results_date")),
        )


@dataclass
class ExamSitting:
    """One scheduled paper within a series."""

    sitting_id: int | None
    series_id: str
    unit_id: str
    paper: str = ""
    exam_date: date | None = None
    start_time: str = "09:00"
    duration_minutes: int = 90
    room_id: str = ""
    invigilator_id: str = ""
    seats: int = 0
    entered: int = 0                 # derived; populated by the repository

    @property
    def seats_remaining(self) -> int | None:
        if self.seats <= 0:
            return None
        return max(0, self.seats - self.entered)

    @property
    def label(self) -> str:
        when = self.exam_date.isoformat() if self.exam_date else "unscheduled"
        return f"{self.unit_id} {self.paper} — {when} {self.start_time}".strip()

    def validate(self) -> None:
        if not self.series_id.strip():
            raise ValidationError("A sitting must belong to an exam series")
        if not self.unit_id.strip():
            raise ValidationError("A sitting must be for a unit")
        if self.duration_minutes <= 0:
            raise ValidationError("Exam duration must be positive")
        if self.duration_minutes > 480:
            raise ValidationError("Exam duration cannot exceed 8 hours")
        if self.seats < 0:
            raise ValidationError("Seat count cannot be negative")
        try:
            time.fromisoformat(self.start_time)
        except ValueError as exc:
            raise ValidationError(
                f"'{self.start_time}' is not a valid start time (expected HH:MM)"
            ) from exc

    def to_row(self) -> dict:
        return {
            "series_id": self.series_id.strip().upper(),
            "unit_id": self.unit_id.strip().upper(),
            "paper": self.paper.strip(),
            "exam_date": self.exam_date.isoformat() if self.exam_date else None,
            "start_time": self.start_time.strip(),
            "duration_minutes": int(self.duration_minutes),
            "room_id": optional_ref(self.room_id),
            "invigilator_id": optional_ref(self.invigilator_id),
            "seats": int(self.seats),
        }

    @classmethod
    def from_row(cls, row) -> "ExamSitting":
        d = dict(row)
        return cls(
            sitting_id=d.get("sitting_id"),
            series_id=d.get("series_id") or "",
            unit_id=d.get("unit_id") or "",
            paper=d.get("paper") or "",
            exam_date=parse_date(d.get("exam_date")),
            start_time=d.get("start_time") or "09:00",
            duration_minutes=int(d.get("duration_minutes") or 0),
            room_id=d.get("room_id") or "",
            invigilator_id=d.get("invigilator_id") or "",
            seats=int(d.get("seats") or 0),
            entered=int(d.get("entered") or 0),
        )


__all__ = ["LATE_ENTRY_FEE", "SERIES_STATUSES", "ExamSeries", "ExamSitting"]
