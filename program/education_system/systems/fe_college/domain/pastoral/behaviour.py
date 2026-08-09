"""Behaviour records — praise and concerns logged against a learner.

An FE college runs a staged disciplinary process. The stage a learner is at is
derived from their live records rather than stored, so it can never be stale:
add a warning and the stage moves immediately.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from education_system.systems.fe_college.config import BEHAVIOUR_TYPES
from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

# Points carried by each record type. Praise is negative so a learner's net
# score reflects both sides of their conduct rather than concerns alone.
BEHAVIOUR_POINTS = {
    "Praise": -1,
    "Concern": 1,
    "Warning": 3,
    "Formal Warning": 6,
    "Suspension": 12,
}

# Records older than this stop counting towards the disciplinary stage.
BEHAVIOUR_WINDOW_DAYS = 180

# Net points at which each stage of the process is reached.
STAGE_THRESHOLDS = (
    (0, "No concerns"),
    (3, "Informal support"),
    (6, "Stage 1 — cause for concern"),
    (12, "Stage 2 — formal warning"),
    (20, "Stage 3 — disciplinary panel"),
)


@dataclass
class BehaviourRecord:
    """One praise or concern entry."""

    record_id: int | None
    student_id: str
    behaviour_type: str
    summary: str
    logged_by: str = ""              # staff_id
    logged_on: date | None = None
    course_id: str = ""
    detail: str = ""
    action_taken: str = ""
    parent_informed: bool = False

    @property
    def points(self) -> int:
        return BEHAVIOUR_POINTS.get(self.behaviour_type, 0)

    @property
    def is_positive(self) -> bool:
        return self.behaviour_type == "Praise"

    def is_current(self, on: date | None = None) -> bool:
        """Whether this record still counts towards the disciplinary stage."""
        if self.logged_on is None:
            return False
        return (on or date.today()) - self.logged_on <= timedelta(days=BEHAVIOUR_WINDOW_DAYS)

    def validate(self) -> None:
        if not self.student_id.strip():
            raise ValidationError("A behaviour record needs a student")
        if self.behaviour_type not in BEHAVIOUR_TYPES:
            raise ValidationError(f"Unknown behaviour type '{self.behaviour_type}'")
        if not self.summary.strip():
            raise ValidationError("A behaviour record needs a summary")
        if not self.logged_by.strip():
            raise ValidationError("A behaviour record must record who logged it")
        if self.behaviour_type in ("Formal Warning", "Suspension") and not self.action_taken.strip():
            raise ValidationError(
                f"A {self.behaviour_type.lower()} must record the action taken"
            )
        if self.logged_on and self.logged_on > date.today():
            raise ValidationError("A behaviour record cannot be dated in the future")

    def to_row(self) -> dict:
        return {
            "student_id": self.student_id.strip(),
            "behaviour_type": self.behaviour_type,
            "summary": self.summary.strip(),
            "logged_by": optional_ref(self.logged_by),
            "logged_on": self.logged_on.isoformat() if self.logged_on else None,
            "course_id": self.course_id.strip().upper(),
            "detail": self.detail.strip(),
            "action_taken": self.action_taken.strip(),
            "parent_informed": 1 if self.parent_informed else 0,
        }

    @classmethod
    def from_row(cls, row) -> "BehaviourRecord":
        d = dict(row)
        return cls(
            record_id=d.get("record_id"),
            student_id=d.get("student_id") or "",
            behaviour_type=d.get("behaviour_type") or "Concern",
            summary=d.get("summary") or "",
            logged_by=d.get("logged_by") or "",
            logged_on=parse_date(d.get("logged_on")),
            course_id=d.get("course_id") or "",
            detail=d.get("detail") or "",
            action_taken=d.get("action_taken") or "",
            parent_informed=bool(d.get("parent_informed")),
        )


def net_points(records: list[BehaviourRecord], on: date | None = None) -> int:
    """Net behaviour points inside the rolling window, floored at zero."""
    return max(0, sum(r.points for r in records if r.is_current(on)))


def disciplinary_stage(records: list[BehaviourRecord], on: date | None = None) -> str:
    """The stage a learner has reached, from their current records."""
    points = net_points(records, on)
    stage = STAGE_THRESHOLDS[0][1]
    for threshold, label in STAGE_THRESHOLDS:
        if points >= threshold:
            stage = label
    return stage


__all__ = [
    "BEHAVIOUR_POINTS",
    "BEHAVIOUR_WINDOW_DAYS",
    "STAGE_THRESHOLDS",
    "BehaviourRecord",
    "disciplinary_stage",
    "net_points",
]
