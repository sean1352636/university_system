"""Attendance marks and the rates derived from them.

The college's headline figures are two different numbers and conflating them
is the classic reporting bug:

* **attendance** — marks where the learner was in the room (present or late).
* **punctuality** — of those attended sessions, the share that were on time.

Both are computed here so the dashboards, the CLI report and the register
screen can never disagree.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.config import (
    ATTENDANCE_AT_RISK_PCT,
    ATTENDANCE_CONCERN_PCT,
    ATTENDANCE_MARKS,
    ATTENDANCE_TARGET_PCT,
    ATTENDING_MARKS,
)
from education_system.systems.fe_college.domain.students.models import (
    ValidationError,
    parse_date,
)

MARK_LABELS = {
    "present": "Present",
    "late": "Late",
    "authorised": "Authorised absence",
    "unauthorised": "Unauthorised absence",
    "excused": "Excused (college activity)",
}


@dataclass
class AttendanceRecord:
    """One mark for one learner in one session."""

    record_id: int | None
    student_id: str
    course_id: str
    session_date: date | None
    period: str = ""
    mark: str = "present"
    minutes_late: int = 0
    recorded_by: str = ""
    note: str = ""

    @property
    def attended(self) -> bool:
        return self.mark in ATTENDING_MARKS

    @property
    def label(self) -> str:
        return MARK_LABELS.get(self.mark, self.mark)

    def validate(self) -> None:
        if not self.student_id.strip():
            raise ValidationError("Attendance mark needs a student")
        if not self.course_id.strip():
            raise ValidationError("Attendance mark needs a course")
        if self.session_date is None:
            raise ValidationError("Attendance mark needs a session date")
        if self.mark not in ATTENDANCE_MARKS:
            raise ValidationError(
                f"Unknown mark '{self.mark}' — expected one of {', '.join(ATTENDANCE_MARKS)}"
            )
        if self.minutes_late < 0:
            raise ValidationError("Minutes late cannot be negative")
        if self.mark != "late" and self.minutes_late:
            raise ValidationError("Minutes late only applies to a 'late' mark")
        if self.session_date > date.today():
            raise ValidationError("Cannot mark a register for a future date")

    def to_row(self) -> dict:
        return {
            "student_id": self.student_id.strip(),
            "course_id": self.course_id.strip(),
            "session_date": self.session_date.isoformat() if self.session_date else None,
            "period": self.period.strip(),
            "mark": self.mark,
            "minutes_late": int(self.minutes_late),
            "recorded_by": self.recorded_by.strip(),
            "note": self.note.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "AttendanceRecord":
        d = dict(row)
        return cls(
            record_id=d.get("record_id"),
            student_id=d.get("student_id") or "",
            course_id=d.get("course_id") or "",
            session_date=parse_date(d.get("session_date")),
            period=d.get("period") or "",
            mark=d.get("mark") or "present",
            minutes_late=int(d.get("minutes_late") or 0),
            recorded_by=d.get("recorded_by") or "",
            note=d.get("note") or "",
        )


@dataclass(frozen=True)
class AttendanceSummary:
    """Aggregated marks for a learner, course or cohort."""

    total: int = 0
    present: int = 0
    late: int = 0
    authorised: int = 0
    unauthorised: int = 0
    excused: int = 0

    @property
    def attended(self) -> int:
        return self.present + self.late

    @property
    def absent(self) -> int:
        return self.authorised + self.unauthorised

    @property
    def attendance_pct(self) -> float | None:
        """Share of sessions attended, or None when there are no marks yet.

        ``excused`` sessions (trips, exams, college activities) are removed
        from the denominator rather than counted as an absence — marking a
        learner down for attending a college event would be perverse.
        """
        denominator = self.total - self.excused
        if denominator <= 0:
            return None
        return round(self.attended / denominator * 100, 1)

    @property
    def punctuality_pct(self) -> float | None:
        """Share of *attended* sessions that were on time."""
        if self.attended <= 0:
            return None
        return round(self.present / self.attended * 100, 1)

    @property
    def band(self) -> str:
        """Traffic-light band the dashboards colour against."""
        pct = self.attendance_pct
        if pct is None:
            return "no data"
        if pct >= ATTENDANCE_TARGET_PCT:
            return "on target"
        if pct >= ATTENDANCE_CONCERN_PCT:
            return "below target"
        if pct >= ATTENDANCE_AT_RISK_PCT:
            return "concern"
        return "at risk"


def summarise(records) -> AttendanceSummary:
    """Aggregate an iterable of records (or mark-strings) into a summary."""
    counts = dict.fromkeys(ATTENDANCE_MARKS, 0)
    total = 0
    for r in records:
        mark = r if isinstance(r, str) else getattr(r, "mark", None) or dict(r).get("mark")
        if mark not in counts:
            continue
        counts[mark] += 1
        total += 1
    return AttendanceSummary(
        total=total,
        present=counts["present"],
        late=counts["late"],
        authorised=counts["authorised"],
        unauthorised=counts["unauthorised"],
        excused=counts["excused"],
    )


def summary_from_counts(counts: dict[str, int]) -> AttendanceSummary:
    """Build a summary from a ``{mark: count}`` mapping (a GROUP BY result)."""
    known = {m: int(counts.get(m, 0)) for m in ATTENDANCE_MARKS}
    return AttendanceSummary(total=sum(known.values()), **known)


__all__ = [
    "MARK_LABELS",
    "AttendanceRecord",
    "AttendanceSummary",
    "summarise",
    "summary_from_counts",
]
