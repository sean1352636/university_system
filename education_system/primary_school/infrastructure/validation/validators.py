"""Input validation utilities for the Primary School Management System."""

from education_system.primary_school.core.exceptions import ValidationError
from education_system.shared.auth.exceptions import ValidationError as _SharedValidationError
from education_system.shared.validation import validators as _shared


def _wrap(fn):
    """Wrap a shared validator so it raises the primary-specific ValidationError."""
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

from education_system.primary_school.core.defaults import YEAR_GROUPS


def validate_pupil_id(pupil_id: str) -> str:
    """Validate a pupil ID matches the expected format (PRI0001)."""
    import re
    pupil_id = pupil_id.strip()
    if not re.match(r"^PRI\d{4}$", pupil_id):
        raise ValidationError(f"Invalid pupil ID format: {pupil_id} (expected PRI0001)")
    return pupil_id


def validate_year_group(year_group: str) -> str:
    """Validate a year group is within the primary range."""
    year_group = year_group.strip()
    if year_group not in YEAR_GROUPS:
        raise ValidationError(
            f"Invalid year group: {year_group}. Must be one of: {', '.join(YEAR_GROUPS)}"
        )
    return year_group


def validate_assessment_level(level: str) -> str:
    """Validate an assessment level descriptor."""
    valid = {"Emerging", "Developing", "Expected", "Greater Depth", "Exceeding"}
    level = level.strip()
    if level not in valid:
        raise ValidationError(f"Invalid assessment level: {level}")
    return level
