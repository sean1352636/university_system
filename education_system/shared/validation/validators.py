"""Common input validation utilities shared across all education subsystems.

These validators cover generic patterns (email, date, non-empty, etc.) that
are identical across college, secondary, and primary school systems.  Each
subsystem should import these and add its own domain-specific validators
(e.g. validate_student_id, validate_gcse_grade).
"""

import re
from datetime import datetime

from education_system.shared.auth.exceptions import ValidationError


def validate_email(email: str) -> str:
    """Validate and return a normalized email address."""
    if not email:
        raise ValidationError("Email is required.")
    email = email.strip()
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise ValidationError(f"Invalid email format: {email}")
    return email.lower()


def validate_non_empty(value, field_name: str) -> str:
    """Validate that a value is a non-empty string after stripping."""
    if not value or not str(value).strip():
        raise ValidationError(f"{field_name} is required and cannot be empty.")
    return str(value).strip()


def validate_date(date_str: str, fmt: str = "%Y-%m-%d") -> str:
    """Validate a date string and return it normalized."""
    if not date_str:
        raise ValidationError("Date is required.")
    date_str = date_str.strip()
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
