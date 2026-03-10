"""API request validation helpers."""

from flask import request

from education_system.primary_school.core.exceptions import ValidationError


def get_json_body() -> dict:
    """Get and validate that the request body is JSON."""
    data = request.get_json(silent=True)
    if data is None:
        raise ValidationError("Request body must be valid JSON.")
    return data


def require_fields(data: dict, *fields: str) -> None:
    """Validate that required fields are present in the data dict."""
    missing = [f for f in fields if f not in data or data[f] is None]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")
