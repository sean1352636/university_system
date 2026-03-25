"""Request payload validation using JSON Schema.

Medium Priority #5: Structured request validation beyond basic field checks.

Usage in route handlers:
    from education_system.shared.api.request_validator import validate_payload

    @app.route("/api/v1/college/students", methods=["POST"])
    def create_student():
        data = validate_payload(request, CREATE_STUDENT_SCHEMA)
        ...

Schemas can also be registered centrally and looked up by name:
    register_schema("create_student", CREATE_STUDENT_SCHEMA)
    data = validate_payload(request, "create_student")
"""

import re
from datetime import datetime

from flask import request as _request


class PayloadValidationError(ValueError):
    """Raised when a request payload fails schema validation."""

    def __init__(self, message: str, errors: list[dict] | None = None):
        super().__init__(message)
        self.errors = errors or []


# ── Schema registry ──────────────────────────────────────────────────────

_schemas: dict[str, dict] = {}


def register_schema(name: str, schema: dict) -> None:
    """Register a named schema for later lookup."""
    _schemas[name] = schema


def get_schema(name: str) -> dict:
    """Retrieve a registered schema by name."""
    if name not in _schemas:
        raise KeyError(f"No schema registered with name: {name}")
    return _schemas[name]


# ── Validation engine ────────────────────────────────────────────────────

_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}

_FORMAT_CHECKS = {
    "email": lambda v: bool(re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", v)),
    "date": lambda v: _is_date(v, "%Y-%m-%d"),
    "datetime": lambda v: _is_date(v, "%Y-%m-%dT%H:%M:%S") or _is_date(v, "%Y-%m-%d %H:%M:%S"),
    "phone": lambda v: bool(re.match(r"^[\d\s\+\-\(\)]{7,20}$", v)),
}


def _is_date(value: str, fmt: str) -> bool:
    try:
        datetime.strptime(value, fmt)
        return True
    except (ValueError, TypeError):
        return False


def _validate_field(value, field_name: str, rules: dict) -> list[dict]:
    """Validate a single field against its schema rules."""
    errors = []

    # Type check
    expected_type = rules.get("type")
    if expected_type and expected_type in _TYPE_CHECKS:
        if not _TYPE_CHECKS[expected_type](value):
            errors.append({"field": field_name, "error": f"Expected type '{expected_type}'"})
            return errors  # Skip further checks if type is wrong

    # String constraints
    if isinstance(value, str):
        min_len = rules.get("minLength")
        max_len = rules.get("maxLength")
        if min_len is not None and len(value) < min_len:
            errors.append({"field": field_name, "error": f"Must be at least {min_len} characters"})
        if max_len is not None and len(value) > max_len:
            errors.append({"field": field_name, "error": f"Must be at most {max_len} characters"})
        pattern = rules.get("pattern")
        if pattern and not re.match(pattern, value):
            errors.append({"field": field_name, "error": f"Does not match pattern: {pattern}"})
        fmt = rules.get("format")
        if fmt and fmt in _FORMAT_CHECKS and not _FORMAT_CHECKS[fmt](value):
            errors.append({"field": field_name, "error": f"Invalid {fmt} format"})

    # Numeric constraints
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = rules.get("minimum")
        maximum = rules.get("maximum")
        if minimum is not None and value < minimum:
            errors.append({"field": field_name, "error": f"Must be >= {minimum}"})
        if maximum is not None and value > maximum:
            errors.append({"field": field_name, "error": f"Must be <= {maximum}"})

    # Enum
    enum_values = rules.get("enum")
    if enum_values is not None and value not in enum_values:
        errors.append({"field": field_name, "error": f"Must be one of: {', '.join(str(v) for v in enum_values)}"})

    # Array constraints
    if isinstance(value, list):
        min_items = rules.get("minItems")
        max_items = rules.get("maxItems")
        if min_items is not None and len(value) < min_items:
            errors.append({"field": field_name, "error": f"Must have at least {min_items} items"})
        if max_items is not None and len(value) > max_items:
            errors.append({"field": field_name, "error": f"Must have at most {max_items} items"})
        # Validate array items if schema provided
        items_schema = rules.get("items")
        if items_schema:
            for i, item in enumerate(value):
                errors.extend(_validate_field(item, f"{field_name}[{i}]", items_schema))

    # Nested object
    if isinstance(value, dict) and "properties" in rules:
        errors.extend(_validate_object(value, rules, prefix=field_name))

    return errors


def _validate_object(data: dict, schema: dict, prefix: str = "") -> list[dict]:
    """Validate a dict against an object schema."""
    errors = []
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    # Check required fields
    for field in required:
        if field not in data or data[field] is None:
            full_name = f"{prefix}.{field}" if prefix else field
            errors.append({"field": full_name, "error": "Required field is missing"})

    # Validate each present field
    for field, rules in properties.items():
        if field in data and data[field] is not None:
            full_name = f"{prefix}.{field}" if prefix else field
            errors.extend(_validate_field(data[field], full_name, rules))

    # Check for unknown fields if additionalProperties is False
    if schema.get("additionalProperties") is False:
        unknown = set(data.keys()) - set(properties.keys())
        for field in unknown:
            full_name = f"{prefix}.{field}" if prefix else field
            errors.append({"field": full_name, "error": "Unknown field"})

    return errors


def validate_payload(req=None, schema=None) -> dict:
    """Validate the JSON request body against a schema.

    Args:
        req: Flask request object (defaults to current request)
        schema: A schema dict or a registered schema name string

    Returns:
        The validated data dict

    Raises:
        PayloadValidationError: If validation fails
    """
    if req is None:
        req = _request

    data = req.get_json(silent=True)
    if data is None:
        raise PayloadValidationError("Request body must be valid JSON")

    if schema is None:
        return data

    if isinstance(schema, str):
        schema = get_schema(schema)

    errors = _validate_object(data, schema)
    if errors:
        raise PayloadValidationError(
            f"Validation failed: {len(errors)} error(s)",
            errors=errors,
        )

    return data


# ── Common reusable schema fragments ────────────────────────────────────

EMAIL_FIELD = {"type": "string", "format": "email", "maxLength": 255}
DATE_FIELD = {"type": "string", "format": "date"}
PHONE_FIELD = {"type": "string", "format": "phone", "maxLength": 20}
NAME_FIELD = {"type": "string", "minLength": 1, "maxLength": 200}
ID_FIELD = {"type": "integer", "minimum": 1}
PAGINATION_PARAMS = {
    "page": {"type": "integer", "minimum": 1},
    "per_page": {"type": "integer", "minimum": 1, "maximum": 100},
}
