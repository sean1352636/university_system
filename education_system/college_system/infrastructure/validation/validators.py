"""Input validation utilities for the Sixth Form College system."""

from education_system.college_system.core.exceptions import ValidationError
from education_system.shared.auth.exceptions import ValidationError as _SharedValidationError
from education_system.shared.validation import validators as _shared


def _wrap(fn):
    """Wrap a shared validator so it raises the college-specific ValidationError."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except _SharedValidationError as exc:
            raise ValidationError(str(exc)) from exc
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


validate_email = _wrap(_shared.validate_email)
validate_non_empty = _wrap(_shared.validate_non_empty)
validate_date = _wrap(_shared.validate_date)
validate_grade_score = _wrap(_shared.validate_grade_score)
validate_positive_int = _wrap(_shared.validate_positive_int)
validate_day_of_week = _wrap(_shared.validate_day_of_week)
validate_time = _wrap(_shared.validate_time)
validate_time_range = _wrap(_shared.validate_time_range)


def validate_student_id(student_id: str) -> str:
    """Validate student ID format (e.g., SFC0001)."""
    import re
    if not student_id:
        raise ValidationError("Student ID is required.")
    pattern = r"^SFC\d{4,}$"
    if not re.match(pattern, student_id):
        raise ValidationError(f"Invalid student ID format: {student_id}. Expected format: SFC0001")
    return student_id.upper()


def validate_year_group(year_group: str) -> str:
    """Validate year group (12 or 13)."""
    from education_system.college_system.infrastructure.database.constants import YEAR_GROUPS
    if year_group not in YEAR_GROUPS:
        raise ValidationError(f"Invalid year group: {year_group}. Must be one of: {', '.join(YEAR_GROUPS)}")
    return year_group


def validate_term(term: str) -> str:
    """Validate term (Autumn, Spring, Summer)."""
    from education_system.college_system.infrastructure.database.constants import TERMS
    if term not in TERMS:
        raise ValidationError(f"Invalid term: {term}. Must be one of: {', '.join(TERMS)}")
    return term


def validate_qualification_type(qual_type: str) -> str:
    """Validate qualification type."""
    from education_system.college_system.infrastructure.database.constants import QUALIFICATION_TYPES
    if qual_type not in QUALIFICATION_TYPES:
        raise ValidationError(f"Invalid qualification type: {qual_type}. Must be one of: {', '.join(QUALIFICATION_TYPES)}")
    return qual_type


def validate_alevel_grade(grade: str) -> str:
    """Validate an A-Level grade letter."""
    from education_system.college_system.infrastructure.database.constants import GRADE_SCALE
    if grade not in GRADE_SCALE:
        raise ValidationError(f"Invalid grade: {grade}. Must be one of: {', '.join(GRADE_SCALE.keys())}")
    return grade


def validate_course_code(code: str) -> str:
    """Validate course code format (e.g., CS101, MATH201)."""
    import re
    if not code:
        raise ValidationError("Course code is required.")
    pattern = r"^[A-Z]{2,5}\d{3,4}$"
    if not re.match(pattern, code.upper()):
        raise ValidationError(f"Invalid course code format: {code}. Expected format: CS101")
    return code.upper()
