"""Input validation utilities for the Primary School Management System."""

import re

from education_system.primary_school.core.exceptions import ValidationError
from education_system.primary_school.core.defaults import YEAR_GROUPS


def validate_non_empty(value, field_name: str) -> str:
    """Ensure a value is a non-empty string after stripping whitespace."""
    if not value or not str(value).strip():
        raise ValidationError(f"{field_name} is required and cannot be empty")
    return str(value).strip()


def validate_email(email: str) -> str:
    """Validate an email address format."""
    email = email.strip()
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise ValidationError(f"Invalid email address: {email}")
    return email


def validate_pupil_id(pupil_id: str) -> str:
    """Validate a pupil ID matches the expected format (PRI0001)."""
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


def validate_date(date_str: str) -> str:
    """Validate a date string is in YYYY-MM-DD format."""
    date_str = date_str.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise ValidationError(f"Invalid date format: {date_str} (expected YYYY-MM-DD)")
    return date_str
