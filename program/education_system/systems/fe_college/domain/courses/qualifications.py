"""Qualifications — the regulated awards courses lead to.

Distinct from :mod:`models.Course`: a qualification is the awarding body's
product ("Pearson BTEC Level 3 National Extended Diploma in Business"), stable
across years, while a course is one delivery of it. Keeping them apart is what
lets achievement rates be compared year on year.
"""

from __future__ import annotations

from dataclasses import dataclass

from education_system.systems.fe_college.config import (
    QUALIFICATION_LEVELS,
    QUALIFICATION_TYPES,
)
from education_system.systems.fe_college.domain.students.grades import grades_for
from education_system.systems.fe_college.domain.students.models import ValidationError

AWARDING_BODIES = (
    "Pearson",
    "City & Guilds",
    "NCFE / CACHE",
    "AQA",
    "OCR",
    "Highfield",
    "Institute for Apprenticeships",
    "Open College Network",
)

# Total credit a full qualification of each size requires. Used to pre-fill the
# course form and to sanity-check that a course's units add up.
QUALIFICATION_SIZES = {
    "Award": 12,
    "Certificate": 30,
    "Subsidiary Diploma": 60,
    "Diploma": 120,
    "Extended Diploma": 180,
}


@dataclass
class Qualification:
    """A regulated qualification offered by the college."""

    qan: str                          # Qualification Accreditation Number
    title: str
    qualification_type: str
    level: str = "3"
    awarding_body: str = "Pearson"
    size: str = "Diploma"
    total_credits: int = 0
    is_active: bool = True

    @property
    def valid_grades(self) -> tuple[str, ...]:
        return grades_for(self.qualification_type)

    @property
    def display_name(self) -> str:
        return f"{self.awarding_body} {self.qualification_type} {self.title}"

    def validate(self) -> None:
        if not self.qan.strip():
            raise ValidationError("Qualification Accreditation Number is required")
        if not self.title.strip():
            raise ValidationError("Qualification title is required")
        if self.qualification_type not in QUALIFICATION_TYPES:
            raise ValidationError(f"Unknown qualification type '{self.qualification_type}'")
        if self.level not in QUALIFICATION_LEVELS:
            raise ValidationError(f"Unknown level '{self.level}'")
        if self.awarding_body not in AWARDING_BODIES:
            raise ValidationError(f"Unknown awarding body '{self.awarding_body}'")
        if self.size not in QUALIFICATION_SIZES:
            raise ValidationError(
                f"Unknown size '{self.size}' — expected one of {', '.join(QUALIFICATION_SIZES)}"
            )
        if self.total_credits < 0:
            raise ValidationError("Total credits cannot be negative")

    def expected_credits(self) -> int:
        """Credits this qualification size normally requires."""
        return self.total_credits or QUALIFICATION_SIZES.get(self.size, 0)

    def to_row(self) -> dict:
        return {
            "qan": self.qan.strip(),
            "title": self.title.strip(),
            "qualification_type": self.qualification_type,
            "level": self.level,
            "awarding_body": self.awarding_body,
            "size": self.size,
            "total_credits": int(self.expected_credits()),
            "is_active": 1 if self.is_active else 0,
        }

    @classmethod
    def from_row(cls, row) -> "Qualification":
        d = dict(row)
        return cls(
            qan=d.get("qan") or "",
            title=d.get("title") or "",
            qualification_type=d.get("qualification_type") or QUALIFICATION_TYPES[0],
            level=str(d.get("level") or "3"),
            awarding_body=d.get("awarding_body") or AWARDING_BODIES[0],
            size=d.get("size") or "Diploma",
            total_credits=int(d.get("total_credits") or 0),
            is_active=bool(d.get("is_active", 1)),
        )


__all__ = ["AWARDING_BODIES", "QUALIFICATION_SIZES", "Qualification"]
