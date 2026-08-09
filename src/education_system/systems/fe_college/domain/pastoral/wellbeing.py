"""Wellbeing check-ins and the risk picture built from them.

The check-in itself is deliberately light — a mood score and a short note —
because anything heavier does not get filled in. The value is in the trend: a
falling score across several check-ins is the signal a tutor acts on, and that
is computed here rather than eyeballed off a list.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.domain.students.models import (
    ValidationError,
    parse_date,
)

# 1 (struggling) to 5 (thriving).
MOOD_SCALE = (1, 2, 3, 4, 5)

MOOD_LABELS = {
    1: "Struggling",
    2: "Low",
    3: "OK",
    4: "Good",
    5: "Thriving",
}

CHECKIN_SOURCES = ("Self", "Tutorial", "Staff observation", "Survey")

# A score at or below this prompts a wellbeing follow-up.
CONCERN_THRESHOLD = 2


@dataclass
class WellbeingCheckIn:
    """One wellbeing data point for a learner."""

    checkin_id: int | None
    student_id: str
    mood: int
    checked_on: date | None = None
    source: str = "Self"
    note: str = ""
    recorded_by: str = ""
    follow_up_needed: bool = False

    @property
    def label(self) -> str:
        return MOOD_LABELS.get(self.mood, str(self.mood))

    @property
    def is_concern(self) -> bool:
        return self.mood <= CONCERN_THRESHOLD

    def validate(self) -> None:
        if not self.student_id.strip():
            raise ValidationError("A wellbeing check-in needs a student")
        if self.mood not in MOOD_SCALE:
            raise ValidationError(
                f"Mood must be between {MOOD_SCALE[0]} and {MOOD_SCALE[-1]}"
            )
        if self.source not in CHECKIN_SOURCES:
            raise ValidationError(f"Unknown check-in source '{self.source}'")
        if self.checked_on and self.checked_on > date.today():
            raise ValidationError("A check-in cannot be dated in the future")

    def to_row(self) -> dict:
        return {
            "student_id": self.student_id.strip(),
            "mood": int(self.mood),
            "checked_on": self.checked_on.isoformat() if self.checked_on else None,
            "source": self.source,
            "note": self.note.strip(),
            "recorded_by": self.recorded_by.strip(),
            "follow_up_needed": 1 if self.follow_up_needed else 0,
        }

    @classmethod
    def from_row(cls, row) -> "WellbeingCheckIn":
        d = dict(row)
        return cls(
            checkin_id=d.get("checkin_id"),
            student_id=d.get("student_id") or "",
            mood=int(d.get("mood") or 3),
            checked_on=parse_date(d.get("checked_on")),
            source=d.get("source") or "Self",
            note=d.get("note") or "",
            recorded_by=d.get("recorded_by") or "",
            follow_up_needed=bool(d.get("follow_up_needed")),
        )


@dataclass(frozen=True)
class WellbeingTrend:
    """A learner's wellbeing picture over their recent check-ins."""

    checkins: int = 0
    average: float | None = None
    latest: int | None = None
    direction: str = "no data"
    needs_follow_up: bool = False


def trend(checkins: list[WellbeingCheckIn], window: int = 5) -> WellbeingTrend:
    """Summarise the most recent ``window`` check-ins, newest first.

    Direction compares the newer half against the older half rather than just
    the last two points, so a single bad day doesn't read as a decline.
    """
    recent = [c for c in checkins if c.checked_on is not None]
    recent.sort(key=lambda c: c.checked_on, reverse=True)
    recent = recent[:window]
    if not recent:
        return WellbeingTrend()

    scores = [c.mood for c in recent]
    average = round(sum(scores) / len(scores), 1)
    latest = scores[0]

    direction = "steady"
    if len(scores) >= 4:
        half = len(scores) // 2
        newer = sum(scores[:half]) / half
        older = sum(scores[half:]) / (len(scores) - half)
        if newer - older >= 0.5:
            direction = "improving"
        elif older - newer >= 0.5:
            direction = "declining"

    return WellbeingTrend(
        checkins=len(recent),
        average=average,
        latest=latest,
        direction=direction,
        needs_follow_up=(
            latest <= CONCERN_THRESHOLD
            or direction == "declining"
            or any(c.follow_up_needed for c in recent)
        ),
    )


__all__ = [
    "CHECKIN_SOURCES",
    "CONCERN_THRESHOLD",
    "MOOD_LABELS",
    "MOOD_SCALE",
    "WellbeingCheckIn",
    "WellbeingTrend",
    "trend",
]
