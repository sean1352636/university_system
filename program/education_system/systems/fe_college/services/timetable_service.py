"""Timetable use cases: placing sessions, checking clashes, rooms and plans."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.config import PERIODS, WEEKDAYS
from education_system.systems.fe_college.domain.facilities.bookings import (
    Booking,
    find_clashes as find_booking_clashes,
)
from education_system.systems.fe_college.domain.facilities.rooms import Room
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.domain.teaching.lesson_plans import LessonPlan
from education_system.systems.fe_college.domain.teaching.timetable import (
    PERIOD_CODES,
    PERIOD_TIMES,
    Session,
    find_clashes,
    free_slots,
    teaching_hours,
    weekly_grid,
)
from education_system.systems.fe_college.infrastructure.persistence import session as db_session
from education_system.systems.fe_college.infrastructure.persistence.repositories import (
    course_repository as course_repo,
    staff_repository as staff_repo,
    timetable_repository as repo,
)


@dataclass(frozen=True)
class TimetableCell:
    """One populated cell of a weekly grid."""

    session: Session
    course_title: str = ""
    teacher_name: str = ""
    room_name: str = ""

    @property
    def summary(self) -> str:
        bits = [self.course_title or self.session.course_id]
        if self.session.group_id:
            bits.append(self.session.group_id)
        if self.room_name or self.session.room_id:
            bits.append(self.room_name or self.session.room_id)
        return " · ".join(bits)


@dataclass(frozen=True)
class Timetable:
    """A weekly grid, indexed by (day, period)."""

    title: str
    cells: dict[tuple[str, str], list[TimetableCell]]
    total_sessions: int

    @property
    def hours(self) -> float:
        return round(self.total_sessions * 1.0, 1)

    def at(self, day: str, period: str) -> list[TimetableCell]:
        return self.cells.get((day, period), [])


def days() -> tuple[str, ...]:
    return WEEKDAYS


def periods() -> tuple[tuple[str, str, str], ...]:
    return PERIODS


def period_codes() -> tuple[str, ...]:
    return PERIOD_CODES


def period_label(period: str) -> str:
    start, end = PERIOD_TIMES.get(period, ("", ""))
    return f"{period} {start}-{end}" if start else period


# ── Building a grid ─────────────────────────────────────────────────────────

def _decorate(sessions: list[Session], title: str) -> Timetable:
    """Attach human-readable names to a list of sessions."""
    with db_session():
        courses = {c.course_id: c.title for c in course_repo.list_courses()}
        staff = {s.staff_id: s.full_name for s in staff_repo.list_staff()}
        rooms = {r.room_id: r.name for r in repo.list_rooms()}

    cells: dict[tuple[str, str], list[TimetableCell]] = {}
    for s in sessions:
        cells.setdefault(s.slot, []).append(TimetableCell(
            session=s,
            course_title=courses.get(s.course_id, s.course_id),
            teacher_name=staff.get(s.teacher_id, s.teacher_id),
            room_name=rooms.get(s.room_id, s.room_id),
        ))
    return Timetable(title=title, cells=cells, total_sessions=len(sessions))


def for_course(course_id: str) -> Timetable:
    return _decorate(repo.list_sessions(course_id=course_id), f"Course {course_id}")


def for_staff(staff_id: str) -> Timetable:
    return _decorate(repo.list_sessions(teacher_id=staff_id), f"Staff {staff_id}")


def for_student(student_id: str) -> Timetable:
    """A learner's own timetable, from the courses they are enrolled on."""
    return _decorate(repo.list_sessions(student_id=student_id), f"Learner {student_id}")


def for_room(room_id: str) -> Timetable:
    return _decorate(repo.list_sessions(room_id=room_id), f"Room {room_id}")


def whole_college(academic_year: str | None = None) -> Timetable:
    return _decorate(repo.list_sessions(academic_year=academic_year), "College timetable")


def grid(sessions: list[Session]) -> dict[tuple[str, str], list[Session]]:
    return weekly_grid(sessions)


def as_text(timetable: Timetable, *, days: int = 6) -> str:
    """Render a timetable as a plain-text grid.

    Lives here rather than beside the Tk renderer so the CLI can print a
    timetable without importing the GUI package (and with it, tkinter).
    """
    weekdays = list(WEEKDAYS[:days])
    lines = [timetable.title, "=" * 76]
    header = f"{'Period':<14}" + "".join(f"{d[:9]:<22}" for d in weekdays)
    lines += [header, "-" * len(header)]
    for code, start, end in PERIODS:
        row = f"{code} {start}-{end:<6}"
        for day in weekdays:
            entries = timetable.at(day, code)
            if not entries:
                row += f"{'·':<22}"
            else:
                text = entries[0].summary
                if len(entries) > 1:
                    text = f"{text} (+{len(entries) - 1})"
                row += f"{text[:21]:<22}"
        lines.append(row.rstrip())
    lines += [
        "",
        f"{timetable.total_sessions} session(s) · {timetable.hours:g} hours per week",
    ]
    return "\n".join(lines)


# ── Placing sessions ────────────────────────────────────────────────────────

def check_clashes(session: Session) -> list[str]:
    """Everything that would clash if ``session`` were placed."""
    existing = repo.sessions_in_slot(
        session.day, session.period, session.academic_year or None
    )
    clashes = find_clashes(session, existing)

    # Staff availability is a separate constraint from a timetable clash: the
    # slot may be empty and the lecturer still not contracted to be in.
    if session.teacher_id:
        availability = staff_repo.get_availability(session.teacher_id)
        if not availability.is_free(session.day, session.period):
            clashes.append(
                f"{session.teacher_id} is not available in "
                f"{session.day} {session.period}"
            )
    return clashes


def place(session: Session, *, force: bool = False) -> Session:
    """Add a session to the timetable, refusing a clash unless forced."""
    session.validate()
    with db_session():
        clashes = check_clashes(session)
        if clashes and not force:
            raise ValidationError("; ".join(clashes))
        return repo.create_session(session)


def move(session_id: int, day: str, period: str, *, force: bool = False) -> Session:
    """Move a session to another slot, re-checking clashes at the target."""
    with db_session():
        existing = repo.get_session(session_id)
        if existing is None:
            raise ValidationError(f"No session with ID {session_id}")
        existing.day = day
        existing.period = period
        existing.validate()
        clashes = check_clashes(existing)
        if clashes and not force:
            raise ValidationError("; ".join(clashes))
        return repo.update_session(existing)


def remove(session_id: int) -> bool:
    return repo.delete_session(session_id)


def free_periods(academic_year: str | None = None) -> list[tuple[str, str]]:
    return free_slots(repo.list_sessions(academic_year=academic_year))


def suggest_slots(course_id: str, *, teacher_id: str = "", room_id: str = "",
                  limit: int = 8) -> list[tuple[str, str]]:
    """Slots where a session could be placed without clashing.

    Cheaper than trial-and-error in the UI: one pass over the week rather than
    the user picking slots until one is accepted.
    """
    candidate = Session(
        session_id=None, course_id=course_id,
        teacher_id=teacher_id, room_id=room_id,
    )
    found: list[tuple[str, str]] = []
    with db_session():
        for day in WEEKDAYS[:5]:
            for period in PERIOD_CODES:
                candidate.day, candidate.period = day, period
                if not check_clashes(candidate):
                    found.append((day, period))
                    if len(found) >= limit:
                        return found
    return found


# ── Rooms & bookings ────────────────────────────────────────────────────────

def rooms(**filters) -> list[Room]:
    return repo.list_rooms(**filters)


def save_room(room: Room) -> Room:
    return repo.save_room(room)


def delete_room(room_id: str) -> bool:
    return repo.delete_room(room_id)


def free_rooms(day: str, period: str, *, min_capacity: int = 0,
               room_type: str | None = None) -> list[Room]:
    return repo.free_rooms(day, period, min_capacity=min_capacity, room_type=room_type)


def bookings(room_id: str | None = None, on: date | None = None) -> list[Booking]:
    return repo.list_bookings(room_id=room_id, booking_date=on)


def book(booking: Booking, *, force: bool = False) -> Booking:
    """Book a room, refusing an overlap with an existing booking."""
    booking.validate()
    with db_session():
        existing = repo.list_bookings(
            room_id=booking.room_id, booking_date=booking.booking_date
        )
        clashes = find_booking_clashes(booking, existing)
        if clashes and not force:
            raise ValidationError("; ".join(clashes))
        return repo.create_booking(booking)


def cancel_booking(booking_id: int) -> bool:
    return repo.cancel_booking(booking_id)


# ── Lesson plans ────────────────────────────────────────────────────────────

def lesson_plans(**filters) -> list[LessonPlan]:
    return repo.list_lesson_plans(**filters)


def get_lesson_plan(plan_id: int) -> LessonPlan | None:
    return repo.get_lesson_plan(plan_id)


def save_lesson_plan(plan: LessonPlan) -> LessonPlan:
    return repo.save_lesson_plan(plan)


def delete_lesson_plan(plan_id: int) -> bool:
    return repo.delete_lesson_plan(plan_id)


__all__ = [
    "Timetable",
    "TimetableCell",
    "as_text",
    "book",
    "bookings",
    "cancel_booking",
    "check_clashes",
    "days",
    "delete_lesson_plan",
    "delete_room",
    "for_course",
    "for_room",
    "for_staff",
    "for_student",
    "free_periods",
    "free_rooms",
    "get_lesson_plan",
    "grid",
    "lesson_plans",
    "move",
    "period_codes",
    "period_label",
    "periods",
    "place",
    "remove",
    "rooms",
    "save_lesson_plan",
    "save_room",
    "suggest_slots",
    "whole_college",
]
