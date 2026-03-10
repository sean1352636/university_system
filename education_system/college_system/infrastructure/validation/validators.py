"""Input validation utilities."""

import re
from datetime import datetime

from education_system.college_system.core.exceptions import ValidationError


def validate_email(email: str) -> str:
    """Validate and return a normalized email address."""
    if not email:
        raise ValidationError("Email is required.")
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise ValidationError(f"Invalid email format: {email}")
    return email.lower().strip()


def validate_student_id(student_id: str) -> str:
    """Validate student ID format (e.g., SFC0001)."""
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
    if not code:
        raise ValidationError("Course code is required.")
    pattern = r"^[A-Z]{2,5}\d{3,4}$"
    if not re.match(pattern, code.upper()):
        raise ValidationError(f"Invalid course code format: {code}. Expected format: CS101")
    return code.upper()


def validate_date(date_str: str, fmt: str = "%Y-%m-%d") -> str:
    """Validate a date string and return it normalized."""
    if not date_str:
        raise ValidationError("Date is required.")
    try:
        datetime.strptime(date_str, fmt)
        return date_str
    except ValueError:
        raise ValidationError(f"Invalid date format: {date_str}. Expected: {fmt}")


def validate_grade_score(score: float) -> float:
    """Validate a grade score is between 0 and 100."""
    try:
        score = float(score)
    except (TypeError, ValueError):
        raise ValidationError(f"Invalid score: {score}. Must be a number.")

    if score < 0 or score > 100:
        raise ValidationError(f"Score must be between 0 and 100, got {score}.")
    return score


def validate_non_empty(value: str, field_name: str) -> str:
    """Validate that a string value is not empty."""
    if not value or not value.strip():
        raise ValidationError(f"{field_name} cannot be empty.")
    return value.strip()


def validate_positive_int(value, field_name: str) -> int:
    """Validate that a value is a positive integer."""
    try:
        val = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a positive integer.")
    if val <= 0:
        raise ValidationError(f"{field_name} must be a positive integer.")
    return val


_VALID_DAYS = {"Mon", "Tue", "Wed", "Thu", "Fri"}


def validate_day_of_week(day: str) -> str:
    """Validate a day-of-week string (Mon-Fri)."""
    if not day:
        raise ValidationError("Day of week is required.")
    day = day.strip().capitalize()[:3]
    if day not in _VALID_DAYS:
        raise ValidationError(f"Invalid day of week: {day}. Must be one of: {', '.join(sorted(_VALID_DAYS))}")
    return day


def validate_time(time_str: str) -> str:
    """Validate a time string in HH:MM format."""
    if not time_str:
        raise ValidationError("Time is required.")
    time_str = time_str.strip()
    if not re.match(r"^\d{2}:\d{2}$", time_str):
        raise ValidationError(f"Invalid time format: {time_str}. Expected HH:MM.")
    hours, minutes = time_str.split(":")
    if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
        raise ValidationError(f"Invalid time value: {time_str}.")
    return time_str


def validate_time_range(start: str, end: str) -> tuple[str, str]:
    """Validate that start time is before end time."""
    start = validate_time(start)
    end = validate_time(end)
    if start >= end:
        raise ValidationError(f"Start time ({start}) must be before end time ({end}).")
    return start, end
