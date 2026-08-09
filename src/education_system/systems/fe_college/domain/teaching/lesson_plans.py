"""Lesson plans — what a lecturer intends to teach in one session.

Kept lightweight on purpose: the plan carries objectives, activities and the
differentiation notes an observer looks for, and links to the timetable session
it belongs to. Anything heavier goes unused in practice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

PLAN_STATUSES = ("draft", "ready", "delivered", "archived")


@dataclass
class LessonPlan:
    """A plan for one taught session."""

    plan_id: int | None
    course_id: str
    title: str
    teacher_id: str = ""
    group_id: str = ""
    unit_id: str = ""
    session_id: int | None = None
    lesson_date: date | None = None
    status: str = "draft"
    objectives: str = ""
    activities: str = ""
    resources: str = ""
    differentiation: str = ""
    assessment: str = ""
    homework: str = ""
    evaluation: str = ""
    created_at: str = ""

    @property
    def objective_list(self) -> tuple[str, ...]:
        return tuple(o.strip() for o in self.objectives.splitlines() if o.strip())

    @property
    def is_deliverable(self) -> bool:
        return self.status in ("ready", "delivered")

    def validate(self) -> None:
        if not self.course_id.strip():
            raise ValidationError("A lesson plan must belong to a course")
        if not self.title.strip():
            raise ValidationError("Lesson plan title is required")
        if self.status not in PLAN_STATUSES:
            raise ValidationError(f"Unknown lesson-plan status '{self.status}'")
        if self.status in ("ready", "delivered") and not self.objectives.strip():
            raise ValidationError("A plan cannot be marked ready without learning objectives")
        if self.status == "delivered" and self.lesson_date is None:
            raise ValidationError("A delivered lesson must record the date it was taught")

    def to_row(self) -> dict:
        return {
            "course_id": self.course_id.strip().upper(),
            "title": self.title.strip(),
            "teacher_id": optional_ref(self.teacher_id),
            "group_id": optional_ref(self.group_id.upper()),
            "unit_id": self.unit_id.strip().upper(),
            "session_id": self.session_id,
            "lesson_date": self.lesson_date.isoformat() if self.lesson_date else None,
            "status": self.status,
            "objectives": self.objectives.strip(),
            "activities": self.activities.strip(),
            "resources": self.resources.strip(),
            "differentiation": self.differentiation.strip(),
            "assessment": self.assessment.strip(),
            "homework": self.homework.strip(),
            "evaluation": self.evaluation.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "LessonPlan":
        d = dict(row)
        return cls(
            plan_id=d.get("plan_id"),
            course_id=d.get("course_id") or "",
            title=d.get("title") or "",
            teacher_id=d.get("teacher_id") or "",
            group_id=d.get("group_id") or "",
            unit_id=d.get("unit_id") or "",
            session_id=d.get("session_id"),
            lesson_date=parse_date(d.get("lesson_date")),
            status=d.get("status") or "draft",
            objectives=d.get("objectives") or "",
            activities=d.get("activities") or "",
            resources=d.get("resources") or "",
            differentiation=d.get("differentiation") or "",
            assessment=d.get("assessment") or "",
            homework=d.get("homework") or "",
            evaluation=d.get("evaluation") or "",
            created_at=d.get("created_at") or "",
        )


__all__ = ["PLAN_STATUSES", "LessonPlan"]
