"""Input validation utilities for the Secondary School system."""

from education_system.secondary_school.core.exceptions import ValidationError
from education_system.shared.auth.exceptions import ValidationError as _SharedValidationError
from education_system.shared.validation import validators as _shared


def _wrap(fn):
    """Wrap a shared validator so it raises the secondary-specific ValidationError."""
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
    """Validate student ID format (e.g., SEC0001)."""
    import re
    student_id = student_id.strip().upper()
    if not re.match(r'^SEC\d{4}$', student_id):
        raise ValidationError(f"Invalid student ID format: {student_id}")
    return student_id


def validate_year_group(year_group: str) -> str:
    """Validate year group is 7-11."""
    from education_system.secondary_school.infrastructure.database.constants import YEAR_GROUPS
    if year_group not in YEAR_GROUPS:
        raise ValidationError(f"Year group must be one of: {', '.join(YEAR_GROUPS)}")
    return year_group


def validate_gcse_grade(grade: str) -> str:
    """Validate GCSE grade (9-1 or U)."""
    valid = {"9", "8", "7", "6", "5", "4", "3", "2", "1", "U"}
    if grade not in valid:
        raise ValidationError(f"Invalid GCSE grade: {grade}. Must be 9-1 or U.")
    return grade
