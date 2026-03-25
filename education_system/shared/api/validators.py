"""Shared API request validation helpers for all system APIs."""

import re
from datetime import datetime

from flask import request


class APIValidationError(ValueError):
    """Base validation error for the API layer."""
    pass


def get_json_body() -> dict:
    """Get and validate that the request body is JSON."""
    data = request.get_json(silent=True)
    if data is None:
        raise APIValidationError("Request body must be valid JSON.")
    return data


def require_fields(data: dict, *fields: str) -> None:
    """Validate that required fields are present in the data dict."""
    missing = [f for f in fields if f not in data or data[f] is None]
    if missing:
        raise APIValidationError(f"Missing required fields: {', '.join(missing)}")


def validate_email(email: str) -> None:
    """Validate that *email* looks like a valid email address.

    Raises ``ValueError`` if the format is invalid.
    """
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        raise ValueError(f"Invalid email format: {email}")


def validate_date(date_str: str, fmt: str = "%Y-%m-%d") -> datetime:
    """Parse *date_str* according to *fmt* and return the datetime object.

    Raises ``ValueError`` if the string does not match the expected format.
    """
    try:
        return datetime.strptime(date_str, fmt)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Invalid date '{date_str}'. Expected format: {fmt}"
        ) from exc


def validate_date_range(start: str, end: str, fmt: str = "%Y-%m-%d") -> None:
    """Ensure *start* date is on or before *end* date.

    Raises ``ValueError`` if *start* is after *end* or either date is invalid.
    """
    start_dt = validate_date(start, fmt)
    end_dt = validate_date(end, fmt)
    if start_dt > end_dt:
        raise ValueError(
            f"Start date ({start}) must be on or before end date ({end})"
        )


def validate_phone(phone: str) -> None:
    """Basic phone number validation.

    Allows digits, spaces, ``+``, ``-``, and parentheses.
    The cleaned number must be between 7 and 15 characters long.

    Raises ``ValueError`` if the phone number is invalid.
    """
    cleaned = re.sub(r"[\s\-\(\)\+]", "", phone)
    if not cleaned.isdigit():
        raise ValueError(
            f"Invalid phone number: {phone}. "
            "Only digits, spaces, +, -, and parentheses are allowed."
        )
    if not (7 <= len(cleaned) <= 15):
        raise ValueError(
            f"Invalid phone number: {phone}. "
            "Must contain between 7 and 15 digits."
        )


def validate_string_length(
    value: str, field_name: str, min_len: int = 1, max_len: int = 500
) -> None:
    """Validate that *value* length is within [*min_len*, *max_len*].

    Raises ``ValueError`` if the length is out of bounds.
    """
    length = len(value)
    if length < min_len or length > max_len:
        raise ValueError(
            f"'{field_name}' must be between {min_len} and {max_len} "
            f"characters long (got {length})."
        )


def validate_enum(value, field_name: str, allowed) -> None:
    """Check that *value* is in the *allowed* set.

    Raises ``ValueError`` if the value is not allowed.
    """
    if value not in allowed:
        raise ValueError(
            f"Invalid value for '{field_name}': {value!r}. "
            f"Must be one of: {', '.join(str(a) for a in sorted(allowed))}"
        )


def validate_positive_int(value, field_name: str) -> int:
    """Validate that *value* is a positive integer.

    Raises ``ValueError`` if the value is not a positive integer.
    """
    try:
        int_val = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"'{field_name}' must be a positive integer, got: {value!r}"
        ) from exc
    if int_val <= 0:
        raise ValueError(
            f"'{field_name}' must be a positive integer, got: {int_val}"
        )
    return int_val
