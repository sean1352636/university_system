"""Units (modules) — the assessable components a course is built from.

BTEC and T-Level qualifications are unit-based: a learner passes individual
units and the overall grade is aggregated from them. Units carry a credit value
and a mandatory/optional flag, which together decide whether a learner has
enough credit to be awarded the qualification.
"""

from __future__ import annotations

from dataclasses import dataclass

from education_system.systems.fe_college.domain.students.grades import is_pass
from education_system.systems.fe_college.domain.students.models import ValidationError

UNIT_TYPES = ("Mandatory", "Optional", "Specialist", "Synoptic")

# Assessment methods an FE unit is graded by; the marking screen filters
# internally-assessed units (a lecturer marks these) from externally-assessed
# ones (the awarding body does).
ASSESSMENT_METHODS = (
    "Internal — portfolio",
    "Internal — assignment",
    "Internal — observation",
    "External — examination",
    "External — set task",
)

INTERNALLY_ASSESSED = tuple(m for m in ASSESSMENT_METHODS if m.startswith("Internal"))


@dataclass
class Unit:
    """One assessable unit within a course."""

    unit_id: str
    course_id: str
    title: str
    unit_type: str = "Mandatory"
    credits: int = 10
    guided_learning_hours: int = 60
    assessment_method: str = "Internal — assignment"
    sequence: int = 0
    description: str = ""

    @property
    def is_mandatory(self) -> bool:
        return self.unit_type in ("Mandatory", "Synoptic")

    @property
    def is_internally_assessed(self) -> bool:
        return self.assessment_method in INTERNALLY_ASSESSED

    @property
    def display_name(self) -> str:
        return f"{self.unit_id} — {self.title}"

    def validate(self) -> None:
        if not self.unit_id.strip():
            raise ValidationError("Unit code is required")
        if not self.course_id.strip():
            raise ValidationError("A unit must belong to a course")
        if not self.title.strip():
            raise ValidationError("Unit title is required")
        if self.unit_type not in UNIT_TYPES:
            raise ValidationError(f"Unknown unit type '{self.unit_type}'")
        if self.assessment_method not in ASSESSMENT_METHODS:
            raise ValidationError(f"Unknown assessment method '{self.assessment_method}'")
        if self.credits <= 0:
            raise ValidationError("A unit must be worth at least one credit")
        if self.guided_learning_hours < 0:
            raise ValidationError("Guided learning hours cannot be negative")

    def to_row(self) -> dict:
        return {
            "unit_id": self.unit_id.strip().upper(),
            "course_id": self.course_id.strip().upper(),
            "title": self.title.strip(),
            "unit_type": self.unit_type,
            "credits": int(self.credits),
            "guided_learning_hours": int(self.guided_learning_hours),
            "assessment_method": self.assessment_method,
            "sequence": int(self.sequence),
            "description": self.description.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Unit":
        d = dict(row)
        return cls(
            unit_id=d.get("unit_id") or "",
            course_id=d.get("course_id") or "",
            title=d.get("title") or "",
            unit_type=d.get("unit_type") or "Mandatory",
            credits=int(d.get("credits") or 0),
            guided_learning_hours=int(d.get("guided_learning_hours") or 0),
            assessment_method=d.get("assessment_method") or ASSESSMENT_METHODS[0],
            sequence=int(d.get("sequence") or 0),
            description=d.get("description") or "",
        )


@dataclass(frozen=True)
class CreditProgress:
    """A learner's credit position on one course."""

    credits_achieved: int = 0
    credits_required: int = 0
    mandatory_outstanding: tuple[str, ...] = ()

    @property
    def pct(self) -> float | None:
        if self.credits_required <= 0:
            return None
        return round(min(100.0, self.credits_achieved / self.credits_required * 100), 1)

    @property
    def can_be_awarded(self) -> bool:
        """Enough credit *and* every mandatory unit passed.

        Both conditions matter: a learner can pass optional units to the credit
        total and still be short a mandatory one, which does not qualify.
        """
        return (
            self.credits_required > 0
            and self.credits_achieved >= self.credits_required
            and not self.mandatory_outstanding
        )


def credit_progress(units: list[Unit], grades: dict[str, str]) -> CreditProgress:
    """Compute credit achieved against required from unit grades.

    ``grades`` maps ``unit_id`` to the awarded grade; a missing or blank entry
    means the unit is not yet passed.
    """
    required = sum(u.credits for u in units)
    achieved = sum(u.credits for u in units if is_pass(grades.get(u.unit_id, "")))
    outstanding = tuple(
        u.unit_id for u in units
        if u.is_mandatory and not is_pass(grades.get(u.unit_id, ""))
    )
    return CreditProgress(
        credits_achieved=achieved,
        credits_required=required,
        mandatory_outstanding=outstanding,
    )


__all__ = [
    "ASSESSMENT_METHODS",
    "INTERNALLY_ASSESSED",
    "UNIT_TYPES",
    "CreditProgress",
    "Unit",
    "credit_progress",
]
