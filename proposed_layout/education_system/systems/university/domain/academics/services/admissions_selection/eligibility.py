"""Grade-gating: which courses a tariff qualifies for."""

from __future__ import annotations

from education_system.systems.university.domain.academics.services.admissions_selection.course_catalogue import (
    list_active_courses,
)


def is_eligible(course: dict, tariff: int) -> bool:
    """True if the applicant's tariff meets the course's entry requirement."""
    return int(tariff) >= int(course.get("min_tariff", 0) or 0)


def eligible_courses(tariff: int) -> list[dict]:
    """Active courses the applicant qualifies for, given their UCAS tariff."""
    return [c for c in list_active_courses() if is_eligible(c, tariff)]
