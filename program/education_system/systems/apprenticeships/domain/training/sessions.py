"""Training sessions and their registers.

A session is a scheduled block of delivery — a taught day, a workshop, a
webinar. Marking the register is not just attendance-taking: a present
apprentice earns off-the-job hours from it, so the register is the main
way hours get into the log without anyone typing them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

DELIVERY_MODES: tuple[str, ...] = (
    "Classroom", "Workshop", "Online live", "Online self-paced",
    "Workplace", "Day release", "Block release",
)

SESSION_STATUSES: tuple[str, ...] = ("Scheduled", "Delivered", "Cancelled")

ATTENDANCE_STATUSES: tuple[str, ...] = ("Present", "Late", "Absent", "Excused")

# Which attendance states earn off-the-job hours. A late arrival earns
# whatever the register records; an authorised absence earns nothing but
# is not held against the apprentice.
HOURS_EARNING_STATUSES: frozenset[str] = frozenset({"Present", "Late"})


@dataclass
class TrainingSession:
    """One scheduled block of training delivery."""

    session_id: int
    title: str
    session_date: str
    programme_id: int | None = None
    start_time: str | None = None
    end_time: str | None = None
    delivery_mode: str = "Classroom"
    location: str | None = None
    trainer_id: int | None = None
    capacity: int | None = None
    otj_hours: float = 0.0
    ksb_codes: str | None = None
    notes: str | None = None
    status: str = "Scheduled"
    created_at: str = ""
    # Filled by the join on list screens.
    programme_title: str | None = None
    trainer_name: str | None = None
    attendee_count: int = 0

    @property
    def is_full(self) -> bool:
        return self.capacity is not None and self.attendee_count >= self.capacity

    @property
    def places_left(self) -> int | None:
        if self.capacity is None:
            return None
        return max(0, self.capacity - self.attendee_count)

    @property
    def when(self) -> str:
        if self.start_time and self.end_time:
            return f"{self.session_date} {self.start_time}–{self.end_time}"
        if self.start_time:
            return f"{self.session_date} {self.start_time}"
        return self.session_date


@dataclass
class SessionAttendance:
    """One apprentice's mark on one register."""

    attendance_id: int
    session_id: int
    apprentice_id: int
    status: str = "Present"
    otj_hours: float = 0.0
    notes: str | None = None
    recorded_at: str = ""
    # Filled by the join.
    apprentice_name: str = ""

    @property
    def earned_hours(self) -> bool:
        return self.status in HOURS_EARNING_STATUSES and self.otj_hours > 0


@dataclass
class TrainingPlanItem:
    """A planned block of learning in an apprentice's training plan.

    The training plan is the commitment: what will be delivered, when,
    and which KSBs it covers. Sessions deliver against it.
    """

    item_id: int
    apprentice_id: int
    title: str
    description: str | None = None
    planned_start: str | None = None
    planned_end: str | None = None
    planned_hours: float = 0.0
    ksb_codes: str | None = None
    delivery_mode: str | None = None
    status: str = "Planned"
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_done(self) -> bool:
        return self.status == "Complete"


@dataclass
class AttendanceSummary:
    """An apprentice's attendance record across all sessions."""

    apprentice_id: int
    present: int = 0
    late: int = 0
    absent: int = 0
    excused: int = 0
    records: list[SessionAttendance] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.present + self.late + self.absent + self.excused

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


def validate_delivery_mode(value: str | None) -> str:
    """Check a delivery mode against the recognised list."""
    cleaned = (value or "Classroom").strip()
    if cleaned not in DELIVERY_MODES:
        allowed = ", ".join(DELIVERY_MODES)
        raise ValidationError(f"Delivery mode must be one of: {allowed}")
    return cleaned


def validate_attendance_status(value: str | None) -> str:
    """Check an attendance mark."""
    cleaned = (value or "Present").strip().title()
    if cleaned not in ATTENDANCE_STATUSES:
        allowed = ", ".join(ATTENDANCE_STATUSES)
        raise ValidationError(f"Attendance status must be one of: {allowed}")
    return cleaned


def validate_session_status(value: str | None) -> str:
    """Check a session status."""
    cleaned = (value or "Scheduled").strip().title()
    if cleaned not in SESSION_STATUSES:
        allowed = ", ".join(SESSION_STATUSES)
        raise ValidationError(f"Session status must be one of: {allowed}")
    return cleaned


def hours_for_mark(status: str, session_hours: float) -> float:
    """Default off-the-job hours a register mark earns.

    Present earns the full session; late earns half, which is a
    deliberately blunt rule the tutor can override on the register rather
    than a pretence at minute-accurate tracking.
    """
    if status == "Present":
        return round(session_hours, 2)
    if status == "Late":
        return round(session_hours / 2, 2)
    return 0.0
