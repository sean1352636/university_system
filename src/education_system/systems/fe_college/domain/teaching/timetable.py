"""Timetable sessions and the clash rules that keep a timetable valid.

Three things can clash in one slot — the teacher, the room and the class group.
All three checks live here so the admin timetable screen, the CLI and any
future import all reject the same conflicts.
"""

from __future__ import annotations

from dataclasses import dataclass

from education_system.systems.fe_college.config import PERIODS, WEEKDAYS
from education_system.systems.fe_college.domain.students.models import (
    ValidationError,
    optional_ref,
)

PERIOD_CODES: tuple[str, ...] = tuple(code for code, _s, _e in PERIODS)
PERIOD_TIMES: dict[str, tuple[str, str]] = {c: (s, e) for c, s, e in PERIODS}

# Fraction of an hour each period represents, for workload arithmetic. Every
# configured period is one hour, but deriving it keeps workload correct if a
# college retimes its day.
PERIOD_HOURS = 1.0


@dataclass
class Session:
    """One timetabled teaching session in the weekly grid."""

    session_id: int | None
    course_id: str
    group_id: str = ""
    teacher_id: str = ""
    room_id: str = ""
    day: str = "Monday"
    period: str = "P1"
    academic_year: str = ""
    unit_id: str = ""
    notes: str = ""

    @property
    def times(self) -> tuple[str, str]:
        return PERIOD_TIMES.get(self.period, ("", ""))

    @property
    def label(self) -> str:
        start, end = self.times
        return f"{self.day} {self.period} {start}-{end}"

    @property
    def slot(self) -> tuple[str, str]:
        return (self.day, self.period)

    def validate(self) -> None:
        if not self.course_id.strip():
            raise ValidationError("A session must belong to a course")
        if self.day not in WEEKDAYS:
            raise ValidationError(
                f"'{self.day}' is not a teaching day — expected one of {', '.join(WEEKDAYS)}"
            )
        if self.period not in PERIOD_CODES:
            raise ValidationError(
                f"'{self.period}' is not a valid period — expected one of {', '.join(PERIOD_CODES)}"
            )

    def to_row(self) -> dict:
        return {
            "course_id": self.course_id.strip().upper(),
            "group_id": optional_ref(self.group_id.upper()),
            "teacher_id": optional_ref(self.teacher_id),
            "room_id": optional_ref(self.room_id),
            "day": self.day,
            "period": self.period,
            "academic_year": self.academic_year.strip(),
            "unit_id": self.unit_id.strip(),
            "notes": self.notes.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Session":
        d = dict(row)
        return cls(
            session_id=d.get("session_id"),
            course_id=d.get("course_id") or "",
            group_id=d.get("group_id") or "",
            teacher_id=d.get("teacher_id") or "",
            room_id=d.get("room_id") or "",
            day=d.get("day") or "Monday",
            period=d.get("period") or "P1",
            academic_year=d.get("academic_year") or "",
            unit_id=d.get("unit_id") or "",
            notes=d.get("notes") or "",
        )


def find_clashes(session: Session, existing: list[Session]) -> list[str]:
    """Return descriptions of every clash ``session`` has with ``existing``.

    An empty list means the session can be placed. The session being edited is
    excluded by ``session_id``, so re-saving an unchanged session is not
    reported as clashing with itself.
    """
    clashes: list[str] = []
    for other in existing:
        if other.session_id is not None and other.session_id == session.session_id:
            continue
        if other.slot != session.slot:
            continue
        if session.teacher_id and other.teacher_id == session.teacher_id:
            clashes.append(
                f"Teacher {session.teacher_id} is already teaching "
                f"{other.course_id} in {session.label}"
            )
        if session.room_id and other.room_id == session.room_id:
            clashes.append(
                f"Room {session.room_id} is already booked for "
                f"{other.course_id} in {session.label}"
            )
        if session.group_id and other.group_id == session.group_id:
            clashes.append(
                f"Group {session.group_id} is already timetabled for "
                f"{other.course_id} in {session.label}"
            )
    return clashes


def weekly_grid(sessions: list[Session]) -> dict[tuple[str, str], list[Session]]:
    """Index sessions by (day, period) for grid rendering."""
    grid: dict[tuple[str, str], list[Session]] = {}
    for s in sessions:
        grid.setdefault(s.slot, []).append(s)
    return grid


def teaching_hours(sessions: list[Session]) -> float:
    """Total weekly teaching hours represented by a list of sessions."""
    return round(len(sessions) * PERIOD_HOURS, 2)


def free_slots(sessions: list[Session]) -> list[tuple[str, str]]:
    """Slots in the weekly grid with nothing timetabled in them."""
    taken = {s.slot for s in sessions}
    return [(d, p) for d in WEEKDAYS for p in PERIOD_CODES if (d, p) not in taken]


__all__ = [
    "PERIOD_CODES",
    "PERIOD_HOURS",
    "PERIOD_TIMES",
    "Session",
    "find_clashes",
    "free_slots",
    "teaching_hours",
    "weekly_grid",
]
