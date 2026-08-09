"""Curriculum departments — how a college groups its provision and its staff.

A department owns a set of curriculum areas and has a manager. Courses inherit
their department from their curriculum area, so reporting can roll up from a
single course to the whole department without a second mapping table.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from education_system.systems.fe_college.config import CURRICULUM_AREAS
from education_system.systems.fe_college.domain.students.models import ValidationError

# The default departmental structure a college is seeded with. Each entry maps
# a department to the curriculum areas it owns; every area must appear exactly
# once so ``department_for`` is unambiguous.
DEFAULT_DEPARTMENTS: dict[str, tuple[str, ...]] = {
    "Business & Computing": ("Business & Professional", "Computing & Digital"),
    "Construction & Engineering": (
        "Construction & Built Environment",
        "Engineering & Motor Vehicle",
    ),
    "Creative & Service Industries": (
        "Creative Arts & Media",
        "Hair, Beauty & Wellbeing",
        "Hospitality & Catering",
    ),
    "Health, Care & Science": ("Health & Social Care", "Science"),
    "Public Services & Sport": ("Public Services & Sport",),
    "Foundation & Essential Skills": ("English & Maths", "Foundation Learning"),
}

# Reverse index, built once at import: curriculum area -> owning department.
_AREA_TO_DEPARTMENT: dict[str, str] = {
    area: dept for dept, areas in DEFAULT_DEPARTMENTS.items() for area in areas
}

DEPARTMENTS: tuple[str, ...] = tuple(DEFAULT_DEPARTMENTS)


def department_for(curriculum_area: str) -> str:
    """The department owning a curriculum area, or '' if it isn't mapped."""
    return _AREA_TO_DEPARTMENT.get(curriculum_area, "")


def areas_in(department: str) -> tuple[str, ...]:
    """Curriculum areas owned by a department."""
    return DEFAULT_DEPARTMENTS.get(department, ())


def unmapped_areas() -> tuple[str, ...]:
    """Curriculum areas with no owning department.

    Empty in the shipped configuration; a college that adds an area to
    ``config.CURRICULUM_AREAS`` without assigning it here will see it listed on
    the admin reports screen rather than having it silently vanish from
    departmental roll-ups.
    """
    return tuple(a for a in CURRICULUM_AREAS if a not in _AREA_TO_DEPARTMENT)


@dataclass
class Department:
    """A curriculum department with its manager and headcount."""

    name: str
    manager_staff_id: str = ""
    curriculum_areas: tuple[str, ...] = ()
    staff_count: int = 0
    course_count: int = 0
    student_count: int = 0

    def validate(self) -> None:
        if not self.name.strip():
            raise ValidationError("Department needs a name")
        unknown = [a for a in self.curriculum_areas if a not in CURRICULUM_AREAS]
        if unknown:
            raise ValidationError(f"Unknown curriculum area(s): {', '.join(unknown)}")

    @classmethod
    def default(cls, name: str) -> "Department":
        return cls(name=name, curriculum_areas=areas_in(name))


__all__ = [
    "DEFAULT_DEPARTMENTS",
    "DEPARTMENTS",
    "Department",
    "areas_in",
    "department_for",
    "unmapped_areas",
]
