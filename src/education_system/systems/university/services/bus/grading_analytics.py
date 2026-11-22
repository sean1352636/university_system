"""Port onto Assessment's grading analytics for other slices.

Academics' Grade Tracking analytics tabs (competency attainment, grade
curves) read these; the slice rules keep Academics from importing
Assessment's domain directly. Read-only, and the same functions the
Assessment screens use (``assessment/domain/grading/competency_data`` and
``curve_analysis_data``).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _competency():
    from education_system.systems.university.domains.assessment.domain.grading import (
        competency_data,
    )
    return competency_data


def _curves():
    from education_system.systems.university.domains.assessment.domain.grading import (
        curve_analysis_data,
    )
    return curve_analysis_data


# ------------------------------------------------------------- competencies

def list_competencies(category: Optional[str] = None) -> List[Dict[str, Any]]:
    return _competency().list_competencies(category)


def competency_levels(competency_id: Optional[int] = None) -> List[Dict[str, Any]]:
    return _competency().competency_levels(competency_id)


def student_attainment(student_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return _competency().student_attainment(student_id)


def attainment_summary() -> Dict[str, int]:
    return _competency().attainment_summary()


# ------------------------------------------------------------------- curves

def grade_distribution_overall() -> Dict[str, List[Dict[str, Any]]]:
    return _curves().grade_distribution_overall()


def grade_distribution_by_course() -> Dict[str, List[Dict[str, Any]]]:
    return _curves().grade_distribution_by_course()


def grade_distribution_by_module_type() -> Dict[str, List[Dict[str, Any]]]:
    return _curves().grade_distribution_by_module_type()


def performance_by_course() -> List[Dict[str, Any]]:
    return _curves().performance_by_course()


def performance_by_module_type() -> List[Dict[str, Any]]:
    return _curves().performance_by_module_type()


def grade_trend_by_period() -> List[Dict[str, Any]]:
    return _curves().grade_trend_by_period()


def curve_preview(*args, **kwargs):
    return _curves().curve_preview(*args, **kwargs)
