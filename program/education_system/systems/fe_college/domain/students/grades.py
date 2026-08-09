"""Grades and the rules for comparing them across qualification families.

A BTEC "Merit" and a GCSE "5" are not comparable as strings, so every scale is
given an ordinal rank. Ranking lets the system answer the two questions the
reports actually ask — "is this an achievement?" and "is the learner above or
below their target?" — without hard-coding one qualification's vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass

from education_system.systems.fe_college.config import (
    GRADE_SCALES,
    PASSING_GRADES,
    QUALIFICATION_GRADE_SCALE,
)
from education_system.systems.fe_college.domain.students.models import ValidationError

# Scale name -> {grade: rank}, where a *higher* rank is a better grade. Each
# scale is stored best-first in config, so the rank is its reversed index.
_RANKS: dict[str, dict[str, int]] = {
    scale: {grade: len(grades) - i - 1 for i, grade in enumerate(grades)}
    for scale, grades in GRADE_SCALES.items()
}


def scale_for(qualification_type: str) -> str:
    """Return the grade-scale key governing a qualification type."""
    return QUALIFICATION_GRADE_SCALE.get(qualification_type, "Short Course")


def grades_for(qualification_type: str) -> tuple[str, ...]:
    """The valid grades for a qualification type, best first."""
    return GRADE_SCALES.get(scale_for(qualification_type), ("Pass", "Fail"))


def validate_grade(grade: str, qualification_type: str) -> None:
    """Raise ValidationError if ``grade`` isn't valid for the qualification."""
    if not grade:
        return  # Ungraded is legitimate — the unit may not be marked yet.
    valid = grades_for(qualification_type)
    if grade not in valid:
        raise ValidationError(
            f"'{grade}' is not a valid {qualification_type} grade — "
            f"expected one of {', '.join(valid)}"
        )


def rank(grade: str, qualification_type: str) -> int | None:
    """Ordinal rank of a grade within its scale; None if unrecognised."""
    return _RANKS.get(scale_for(qualification_type), {}).get(grade)


def is_pass(grade: str) -> bool:
    """Whether a grade counts as an achievement for pass-rate reporting."""
    return grade in PASSING_GRADES


def compare_to_target(actual: str, target: str, qualification_type: str) -> int | None:
    """Return >0 above target, 0 on target, <0 below target, None if unknown.

    The magnitude is the number of grade steps, which the reports use to
    distinguish "just short" from "badly off track".
    """
    a, t = rank(actual, qualification_type), rank(target, qualification_type)
    if a is None or t is None:
        return None
    return a - t


@dataclass(frozen=True)
class GradeOutcome:
    """A learner's achieved grade against their target for one course."""

    student_id: str
    course_id: str
    qualification_type: str
    target_grade: str = ""
    predicted_grade: str = ""
    actual_grade: str = ""

    @property
    def achieved(self) -> bool:
        return bool(self.actual_grade) and is_pass(self.actual_grade)

    @property
    def variance(self) -> int | None:
        """Grade steps between the achieved (or predicted) grade and target."""
        grade = self.actual_grade or self.predicted_grade
        if not grade or not self.target_grade:
            return None
        return compare_to_target(grade, self.target_grade, self.qualification_type)

    @property
    def status(self) -> str:
        """Human-readable position against target, for the reports and GUI."""
        v = self.variance
        if v is None:
            return "not yet graded" if not self.actual_grade else "no target set"
        if v > 0:
            return f"above target (+{v})"
        if v == 0:
            return "on target"
        return f"below target ({v})"


def pass_rate(grades: list[str]) -> float | None:
    """Share of awarded grades that are passes, or None if none awarded."""
    awarded = [g for g in grades if g]
    if not awarded:
        return None
    return round(sum(1 for g in awarded if is_pass(g)) / len(awarded) * 100, 1)


def high_grade_rate(grades: list[str]) -> float | None:
    """Share of awarded grades at Distinction/Merit (or GCSE 7+) level.

    This is the "high grades" measure colleges report alongside the headline
    pass rate; a 100% pass rate made entirely of bare passes is a different
    story from one built on distinctions.
    """
    awarded = [g for g in grades if g]
    if not awarded:
        return None
    high = {"Distinction*", "Distinction", "Merit", "9", "8", "7", "A*", "A", "B"}
    return round(sum(1 for g in awarded if g in high) / len(awarded) * 100, 1)


__all__ = [
    "GradeOutcome",
    "compare_to_target",
    "grades_for",
    "high_grade_rate",
    "is_pass",
    "pass_rate",
    "rank",
    "scale_for",
    "validate_grade",
]
