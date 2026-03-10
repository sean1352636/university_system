"""Input validation utilities."""

import re
from education_system.secondary_school.core.exceptions import ValidationError


def validate_non_empty(value: str, field_name: str) -> str:
    """Validate that a string is non-empty after stripping."""
    if not value or not value.strip():
        raise ValidationError(f"{field_name} cannot be empty.")
    return value.strip()


def validate_email(email: str) -> str:
    """Validate email format."""
    email = email.strip()
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValidationError(f"Invalid email format: {email}")
    return email


def validate_student_id(student_id: str) -> str:
    """Validate student ID format (e.g., SEC0001)."""
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
