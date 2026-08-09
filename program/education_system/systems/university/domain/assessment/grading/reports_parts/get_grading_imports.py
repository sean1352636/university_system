"""Extracted function implementation."""

from .. import reports_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _get_grading_imports():
    from education_system.systems.university.domain.assessment.grading.common_utilities import select_assessment
    from education_system.systems.university.domain.assessment.grading.grade_calculation import calculate_student_gpa, GRADE_SYSTEMS
    return select_assessment, calculate_student_gpa, GRADE_SYSTEMS
