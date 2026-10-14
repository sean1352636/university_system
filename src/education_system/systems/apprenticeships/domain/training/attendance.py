"""Attendance: absence reasons, and what an apprentice's register marks add up to.

A mark is made on one session's register (see :mod:`sessions`). Excused
is an authorised absence and Absent an unauthorised one, and either
carries a reason. This module judges the pattern the marks make: the
attendance rate, its RAG rating, and whether it needs following up.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.training.sessions import SessionAttendance

# The marks that are absences, and so carry a reason.
ABSENCE_MARKS: frozenset[str] = frozenset({"Absent", "Excused"})

SICKNESS_REASON = "Sickness"


@dataclass
class AttendanceSummary:
    """An apprentice's attendance record across all sessions."""

    apprentice_id: int
    present: int = 0
    late: int = 0
    absent: int = 0
    excused: int = 0
    # Absences of either kind with sickness as the reason.
    sickness: int = 0
    # Newest first, as the register history is shown.
    records: list[SessionAttendance] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.present + self.late + self.absent + self.excused

    @property
    def authorised(self) -> int:
        return self.excused

    @property
    def unauthorised(self) -> int:
        return self.absent

    @property
    def attendance_rate(self) -> float:
        """Share of sessions attended, counting late as attended.

        Excused absences are excluded from the denominator — penalising
        an apprentice for authorised leave would make the figure useless
        for spotting genuine disengagement.
        """
        countable = self.present + self.late + self.absent
        if countable == 0:
            return 0.0
        return round((self.present + self.late) / countable * 100, 1)

    @property
    def punctuality_rate(self) -> float:
        attended = self.present + self.late
        if attended == 0:
            return 0.0
        return round(self.present / attended * 100, 1)

    @property
    def is_rated(self) -> bool:
        """Enough marked sessions for the rate to mean something."""
        return self.present + self.late + self.absent >= config.ATTENDANCE_MIN_SESSIONS

    @property
    def rag(self) -> str | None:
        """Green, Amber or Red against the configured lines; None until rated."""
        if not self.is_rated:
            return None
        if self.attendance_rate >= config.ATTENDANCE_TARGET_PERCENT:
            return "Green"
        if self.attendance_rate >= config.ATTENDANCE_CONCERN_PERCENT:
            return "Amber"
        return "Red"

    @property
    def consecutive_unauthorised(self) -> int:
        """Unauthorised absences in a row, counting back from the latest mark."""
        run = 0
        for record in self.records:
            if record.status != "Absent":
                break
            run += 1
        return run

    @property
    def is_concern(self) -> bool:
        """Does this attendance need someone to follow it up?"""
        return (
            self.rag == "Red"
            or self.consecutive_unauthorised >= config.ATTENDANCE_CONSECUTIVE_ABSENCE_ALERT
        )

    @property
    def concern_reason(self) -> str | None:
        """Why this record is flagged, in words a tutor can act on."""
        run = self.consecutive_unauthorised
        if run >= config.ATTENDANCE_CONSECUTIVE_ABSENCE_ALERT:
            return f"{run} unauthorised absences in a row"
        if self.rag == "Red":
            return (
                f"Attendance {self.attendance_rate:.1f}%, below "
                f"{config.ATTENDANCE_CONCERN_PERCENT:.0f}%"
            )
        return None


def summarise(apprentice_id: int, records: Sequence[SessionAttendance]) -> AttendanceSummary:
    """Count one apprentice's marks, keeping the marks themselves.

    Counted off the one list the caller is shown anyway, so the headline
    figures and the rows beneath them cannot disagree.
    """
    counts = {"Present": 0, "Late": 0, "Absent": 0, "Excused": 0}
    sickness = 0
    for record in records:
        if record.status in counts:
            counts[record.status] += 1
        if record.status in ABSENCE_MARKS and record.absence_reason == SICKNESS_REASON:
            sickness += 1
    return AttendanceSummary(
        apprentice_id=apprentice_id,
        present=counts["Present"],
        late=counts["Late"],
        absent=counts["Absent"],
        excused=counts["Excused"],
        sickness=sickness,
        records=list(records),
    )


def validate_absence_reason(mark: str, reason: str | None) -> str | None:
    """The reason to store with a mark, or None for a mark that is not an absence.

    A reason on an attendance mark is dropped rather than refused, so a
    tutor correcting Absent to Present need not clear the field first.
    Authorising an absence is a judgement, so Excused needs a real reason;
    an unauthorised absence may be unexplained.
    """
    if mark not in ABSENCE_MARKS:
        return None
    text = (reason or "").strip()
    if not text:
        if mark == "Excused":
            raise ValidationError("An excused absence needs a reason")
        return config.UNEXPLAINED_ABSENCE_REASON
    match = next((r for r in config.ABSENCE_REASONS if r.casefold() == text.casefold()), None)
    if match is None:
        allowed = ", ".join(config.ABSENCE_REASONS)
        raise ValidationError(f"Absence reason must be one of: {allowed}")
    if mark == "Excused" and match == config.UNEXPLAINED_ABSENCE_REASON:
        raise ValidationError(
            "An absence with no reason given cannot be excused — mark it Absent instead"
        )
    return match
