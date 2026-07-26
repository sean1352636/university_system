"""Shared validation utilities."""

from education_system.platform.identity.auth.exceptions import ValidationError
from education_system.platform.kernel.validation.validators import (
    validate_email,
    validate_non_empty,
    validate_date,
    validate_grade_score,
    validate_positive_int,
    validate_day_of_week,
    validate_time,
    validate_time_range,
)

__all__ = [
    "ValidationError",
    "validate_email",
    "validate_non_empty",
    "validate_date",
    "validate_grade_score",
    "validate_positive_int",
    "validate_day_of_week",
    "validate_time",
    "validate_time_range",
]
