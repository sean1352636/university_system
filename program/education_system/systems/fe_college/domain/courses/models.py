"""Courses — the qualifications a learner enrols onto.

A course here is a *deliverable instance*: "BTEC Level 3 Business, 2025/26,
full-time, taught at the main campus". The qualification it leads to
(:mod:`qualifications`) and the units it is built from (:mod:`modules`) are
modelled separately, because the same qualification runs year after year with
a different course code, leader and capacity each time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.config import (
    CURRICULUM_AREAS,
    MODES_OF_STUDY,
    QUALIFICATION_LEVELS,
    QUALIFICATION_TYPES,
)
from education_system.systems.fe_college.domain.staff.departments import department_for
from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

COURSE_STATUSES = ("planned", "recruiting", "running", "full", "cancelled", "archived")

# Statuses where a learner may still be enrolled onto the course.
ENROLLABLE_STATUSES = ("recruiting", "running")


@dataclass
class Course:
    """One deliverable course instance for one academic year."""

    course_id: str
    title: str
    qualification_type: str
    level: str = "3"
    curriculum_area: str = ""
    academic_year: str = ""
    mode_of_study: str = "Full-time"
    status: str = "recruiting"
    course_leader: str = ""          # staff_id
    awarding_body: str = ""
    guided_learning_hours: int = 0
    duration_weeks: int = 0
    capacity: int = 0
    enrolled: int = 0                # derived; populated by the repository
    start_date: date | None = None
    end_date: date | None = None
    campus: str = "Main Campus"
    fee: float = 0.0
    description: str = ""
    created_at: str = ""

    # ── Derived ────────────────────────────────────────────────────────────

    @property
    def department(self) -> str:
        return department_for(self.curriculum_area)

    @property
    def display_name(self) -> str:
        return f"{self.course_id} — {self.title}"

    @property
    def places_remaining(self) -> int | None:
        """Free places, or None when the course has no capacity set."""
        if self.capacity <= 0:
            return None
        return max(0, self.capacity - self.enrolled)

    @property
    def fill_pct(self) -> float | None:
        if self.capacity <= 0:
            return None
        return round(self.enrolled / self.capacity * 100, 1)

    @property
    def is_full(self) -> bool:
        return self.capacity > 0 and self.enrolled >= self.capacity

    @property
    def is_enrollable(self) -> bool:
        return self.status in ENROLLABLE_STATUSES and not self.is_full

    @property
    def viability(self) -> str:
        """Recruitment health, as shown on the admin courses screen.

        Colleges cancel courses that under-recruit, so "how full is it" is the
        first question asked of every course before the year starts.
        """
        pct = self.fill_pct
        if self.status in ("cancelled", "archived"):
            return self.status
        if pct is None:
            return "no capacity set"
        if pct >= 100:
            return "full"
        if pct >= 75:
            return "healthy"
        if pct >= 40:
            return "recruiting"
        return "at risk"

    # ── Rules ──────────────────────────────────────────────────────────────

    def validate(self) -> None:
        if not self.course_id.strip():
            raise ValidationError("Course code is required")
        if not self.title.strip():
            raise ValidationError("Course title is required")
        if self.qualification_type not in QUALIFICATION_TYPES:
            raise ValidationError(f"Unknown qualification type '{self.qualification_type}'")
        if self.level not in QUALIFICATION_LEVELS:
            raise ValidationError(
                f"Unknown level '{self.level}' — expected one of {', '.join(QUALIFICATION_LEVELS)}"
            )
        if self.curriculum_area and self.curriculum_area not in CURRICULUM_AREAS:
            raise ValidationError(f"Unknown curriculum area '{self.curriculum_area}'")
        if self.mode_of_study not in MODES_OF_STUDY:
            raise ValidationError(f"Unknown mode of study '{self.mode_of_study}'")
        if self.status not in COURSE_STATUSES:
            raise ValidationError(f"Unknown course status '{self.status}'")
        if self.capacity < 0:
            raise ValidationError("Capacity cannot be negative")
        if self.guided_learning_hours < 0:
            raise ValidationError("Guided learning hours cannot be negative")
        if self.duration_weeks < 0:
            raise ValidationError("Duration cannot be negative")
        if self.fee < 0:
            raise ValidationError("Course fee cannot be negative")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("Course end date cannot be before its start date")

    def to_row(self) -> dict:
        return {
            "course_id": self.course_id.strip().upper(),
            "title": self.title.strip(),
            "qualification_type": self.qualification_type,
            "level": self.level,
            "curriculum_area": self.curriculum_area,
            "academic_year": self.academic_year.strip(),
            "mode_of_study": self.mode_of_study,
            "status": self.status,
            "course_leader": optional_ref(self.course_leader),
            "awarding_body": self.awarding_body.strip(),
            "guided_learning_hours": int(self.guided_learning_hours),
            "duration_weeks": int(self.duration_weeks),
            "capacity": int(self.capacity),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "campus": self.campus.strip(),
            "fee": float(self.fee),
            "description": self.description.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Course":
        d = dict(row)
        return cls(
            course_id=d.get("course_id") or "",
            title=d.get("title") or "",
            qualification_type=d.get("qualification_type") or QUALIFICATION_TYPES[0],
            level=str(d.get("level") or "3"),
            curriculum_area=d.get("curriculum_area") or "",
            academic_year=d.get("academic_year") or "",
            mode_of_study=d.get("mode_of_study") or "Full-time",
            status=d.get("status") or "recruiting",
            course_leader=d.get("course_leader") or "",
            awarding_body=d.get("awarding_body") or "",
            guided_learning_hours=int(d.get("guided_learning_hours") or 0),
            duration_weeks=int(d.get("duration_weeks") or 0),
            capacity=int(d.get("capacity") or 0),
            enrolled=int(d.get("enrolled") or 0),
            start_date=parse_date(d.get("start_date")),
            end_date=parse_date(d.get("end_date")),
            campus=d.get("campus") or "Main Campus",
            fee=float(d.get("fee") or 0),
            description=d.get("description") or "",
            created_at=d.get("created_at") or "",
        )


__all__ = ["COURSE_STATUSES", "ENROLLABLE_STATUSES", "Course"]
