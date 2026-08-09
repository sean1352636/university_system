"""Attendance use cases: taking registers and reading the rates back."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from education_system.systems.fe_college.config import (
    ATTENDANCE_AT_RISK_PCT,
    ATTENDANCE_MARKS,
    ATTENDANCE_TARGET_PCT,
)
from education_system.systems.fe_college.domain.students.attendance import (
    MARK_LABELS,
    AttendanceRecord,
    AttendanceSummary,
)
from education_system.systems.fe_college.domain.students.models import (
    Student,
    ValidationError,
)
from education_system.systems.fe_college.infrastructure.persistence import session
from education_system.systems.fe_college.infrastructure.persistence.repositories import (
    attendance_repository as repo,
    course_repository as course_repo,
    student_repository as student_repo,
)


@dataclass
class RegisterRow:
    """One learner's line on a register, ready for the GUI to render."""

    student: Student
    mark: str = "present"
    minutes_late: int = 0
    note: str = ""
    attendance_pct: float | None = None   # their running rate, for context

    @property
    def label(self) -> str:
        return MARK_LABELS.get(self.mark, self.mark)


@dataclass(frozen=True)
class Register:
    """A whole register for one course, date and period."""

    course_id: str
    course_title: str
    session_date: date
    period: str
    rows: list[RegisterRow]
    already_taken: bool = False

    @property
    def present_count(self) -> int:
        return sum(1 for r in self.rows if r.mark in ("present", "late"))


def marks() -> tuple[str, ...]:
    return ATTENDANCE_MARKS


# ── Taking a register ───────────────────────────────────────────────────────

def build_register(course_id: str, session_date: date | None = None,
                   period: str = "") -> Register:
    """Prepare a register for a course, pre-filled with any existing marks.

    Re-opening a register shows what was recorded rather than defaulting
    everyone back to present — otherwise a correction visit silently wipes the
    absences that were already entered.
    """
    on = session_date or date.today()
    with session():
        course = course_repo.get(course_id)
        if course is None:
            raise ValidationError(f"No course with code {course_id}")
        learners = student_repo.list_students(course_id=course_id)
        existing = {
            m.student_id: m
            for m in repo.list_marks(course_id=course_id, session_date=on, period=period)
        }
        rates = repo.summaries_by_student(course_id=course_id)

    rows = [
        RegisterRow(
            student=learner,
            mark=existing[learner.student_id].mark if learner.student_id in existing else "present",
            minutes_late=(
                existing[learner.student_id].minutes_late
                if learner.student_id in existing else 0
            ),
            note=existing[learner.student_id].note if learner.student_id in existing else "",
            attendance_pct=(
                rates[learner.student_id].attendance_pct
                if learner.student_id in rates else None
            ),
        )
        for learner in learners
    ]
    return Register(
        course_id=course_id,
        course_title=course.title,
        session_date=on,
        period=period,
        rows=rows,
        already_taken=bool(existing),
    )


def save_register(register: Register, recorded_by: str = "") -> int:
    """Persist a whole register. Returns the number of marks written."""
    records = [
        AttendanceRecord(
            record_id=None,
            student_id=row.student.student_id,
            course_id=register.course_id,
            session_date=register.session_date,
            period=register.period,
            mark=row.mark,
            minutes_late=row.minutes_late if row.mark == "late" else 0,
            recorded_by=recorded_by,
            note=row.note,
        )
        for row in register.rows
    ]
    return repo.save_register(records)


def mark_one(student_id: str, course_id: str, mark: str, *,
             session_date: date | None = None, period: str = "",
             minutes_late: int = 0, recorded_by: str = "",
             note: str = "") -> AttendanceRecord:
    """Record or correct a single learner's mark."""
    record = AttendanceRecord(
        record_id=None,
        student_id=student_id,
        course_id=course_id,
        session_date=session_date or date.today(),
        period=period,
        mark=mark,
        minutes_late=minutes_late if mark == "late" else 0,
        recorded_by=recorded_by,
        note=note,
    )
    return repo.save_mark(record)


def register_dates(course_id: str, limit: int = 30) -> list[str]:
    return repo.register_dates(course_id, limit)


# ── Reading rates back ──────────────────────────────────────────────────────

def for_student(student_id: str, course_id: str | None = None,
                since: date | None = None) -> AttendanceSummary:
    return repo.summary_for_student(student_id, course_id=course_id, date_from=since)


def for_course(course_id: str, since: date | None = None) -> AttendanceSummary:
    return repo.summary_for_course(course_id, date_from=since)


def college(since: date | None = None) -> AttendanceSummary:
    return repo.college_summary(since)


def by_course(since: date | None = None) -> list[tuple[str, str, AttendanceSummary]]:
    """``(course_id, title, summary)`` per course, worst attendance first."""
    with session():
        summaries = repo.summaries_by_course(since)
        titles = {c.course_id: c.title for c in course_repo.list_courses()}
    rows = [
        (cid, titles.get(cid, cid), summary) for cid, summary in summaries.items()
    ]
    return sorted(rows, key=lambda r: r[2].attendance_pct if r[2].attendance_pct is not None else 101)


def by_student(course_id: str | None = None,
               since: date | None = None) -> list[tuple[Student, AttendanceSummary]]:
    """``(student, summary)`` per learner, worst attendance first."""
    with session():
        summaries = repo.summaries_by_student(course_id=course_id, date_from=since)
        learners = {
            s.student_id: s for s in student_repo.list_students(course_id=course_id)
        }
    rows = [
        (learners[sid], summary)
        for sid, summary in summaries.items() if sid in learners
    ]
    return sorted(
        rows, key=lambda r: r[1].attendance_pct if r[1].attendance_pct is not None else 101
    )


def at_risk(threshold_pct: float = ATTENDANCE_AT_RISK_PCT,
            course_id: str | None = None) -> list[tuple[Student, AttendanceSummary]]:
    """Learners below the at-risk threshold, worst first."""
    return [
        (student, summary) for student, summary in by_student(course_id=course_id)
        if summary.attendance_pct is not None and summary.attendance_pct < threshold_pct
    ]


def below_target(course_id: str | None = None) -> list[tuple[Student, AttendanceSummary]]:
    return at_risk(ATTENDANCE_TARGET_PCT, course_id)


def recent_absences(days: int = 7) -> list[AttendanceRecord]:
    return repo.recent_absences(days)


def weekly_trend(course_id: str | None = None,
                 weeks: int = 8) -> list[tuple[str, float | None]]:
    """Attendance percentage per week for the last ``weeks``, oldest first.

    Weeks are anchored to Monday so the buckets line up with a college week
    rather than sliding with whatever day the report is run.
    """
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    trend: list[tuple[str, float | None]] = []
    with session():
        for i in range(weeks - 1, -1, -1):
            start = monday - timedelta(weeks=i)
            end = start + timedelta(days=6)
            counts: dict[str, int] = {}
            for record in repo.list_marks(
                course_id=course_id, date_from=start, date_to=end
            ):
                counts[record.mark] = counts.get(record.mark, 0) + 1
            from education_system.systems.fe_college.domain.students.attendance import (
                summary_from_counts,
            )
            trend.append((start.isoformat(), summary_from_counts(counts).attendance_pct))
    return trend


__all__ = [
    "Register",
    "RegisterRow",
    "at_risk",
    "below_target",
    "build_register",
    "by_course",
    "by_student",
    "college",
    "for_course",
    "for_student",
    "mark_one",
    "marks",
    "recent_absences",
    "register_dates",
    "save_register",
    "weekly_trend",
]
