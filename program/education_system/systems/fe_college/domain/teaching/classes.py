"""Class groups — a teaching group taken from a course cohort.

A course with 60 learners is taught in three groups of 20; the register, the
timetable and the marking screen all work at group level, not course level.
"""

from __future__ import annotations

from dataclasses import dataclass

from education_system.systems.fe_college.domain.students.models import (
    ValidationError,
    optional_ref,
)


@dataclass
class ClassGroup:
    """One teaching group within a course."""

    group_id: str
    course_id: str
    name: str
    teacher_id: str = ""
    academic_year: str = ""
    capacity: int = 0
    members: int = 0             # derived; populated by the repository
    room: str = ""
    notes: str = ""

    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.course_id})"

    @property
    def places_remaining(self) -> int | None:
        if self.capacity <= 0:
            return None
        return max(0, self.capacity - self.members)

    @property
    def is_full(self) -> bool:
        return self.capacity > 0 and self.members >= self.capacity

    def validate(self) -> None:
        if not self.group_id.strip():
            raise ValidationError("Class group needs a code")
        if not self.course_id.strip():
            raise ValidationError("A class group must belong to a course")
        if not self.name.strip():
            raise ValidationError("Class group needs a name")
        if self.capacity < 0:
            raise ValidationError("Capacity cannot be negative")

    def to_row(self) -> dict:
        return {
            "group_id": self.group_id.strip().upper(),
            "course_id": self.course_id.strip().upper(),
            "name": self.name.strip(),
            "teacher_id": optional_ref(self.teacher_id),
            "academic_year": self.academic_year.strip(),
            "capacity": int(self.capacity),
            "room": self.room.strip(),
            "notes": self.notes.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "ClassGroup":
        d = dict(row)
        return cls(
            group_id=d.get("group_id") or "",
            course_id=d.get("course_id") or "",
            name=d.get("name") or "",
            teacher_id=d.get("teacher_id") or "",
            academic_year=d.get("academic_year") or "",
            capacity=int(d.get("capacity") or 0),
            members=int(d.get("members") or 0),
            room=d.get("room") or "",
            notes=d.get("notes") or "",
        )


__all__ = ["ClassGroup"]
