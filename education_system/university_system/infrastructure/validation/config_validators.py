"""
Configuration File Validators

Validates the structure and values of JSON configuration files
(email_config.json, api_server_config.json, sms_config.json) so that
misconfigurations are caught early rather than causing silent runtime
failures.
"""

import re
from typing import Any, Dict, List

from education_system.university_system.infrastructure.validation.validators import ValidationResult

# Re-usable email pattern (same as Validators.EMAIL_PATTERN)
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}
_VALID_SMS_PROVIDERS = {"twilio", "aws_sns", "email_gateway", "mock"}
_VALID_JWT_ALGORITHMS = {"HS256", "HS384", "HS512"}


def _check_type(errors: List[str], config: dict, key: str, expected_type: type,
                label: str | None = None) -> Any | None:
    """If *key* exists in *config*, verify its type and return the value."""
    if key not in config:
        return None
    value = config[key]
    if not isinstance(value, expected_type):
        errors.append(
            f"'{label or key}' must be {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )
        return None
    return value


def _check_port(errors: List[str], value: Any, key: str = "port") -> None:
    """Validate that *value* is an int in [1, 65535]."""
    if not isinstance(value, int):
        errors.append(f"'{key}' must be int, got {type(value).__name__}")
        return
    if value < 1 or value > 65535:
        errors.append(f"'{key}' must be between 1 and 65535, got {value}")


# -- Public validators -------------------------------------------------------

def validate_email_config(config: dict) -> ValidationResult:
    """Validate the contents of ``email_config.json``.

    Required keys: ``smtp_server`` (str), ``smtp_port`` (int, 1-65535),
    ``sender_email`` (valid email format).

    Optional keys are type-checked when present.
    """
    errors: List[str] = []

    # --- required keys ---
    for key in ("smtp_server", "smtp_port", "sender_email"):
        if key not in config:
            errors.append(f"Missing required key '{key}'")

    if "smtp_server" in config and not isinstance(config["smtp_server"], str):
        errors.append("'smtp_server' must be str")

    if "smtp_port" in config:
        _check_port(errors, config["smtp_port"], "smtp_port")

    if "sender_email" in config:
        if not isinstance(config["sender_email"], str):
            errors.append("'sender_email' must be str")
        elif not _EMAIL_RE.match(config["sender_email"]):
            errors.append(f"'sender_email' is not a valid email address")

    # --- optional keys ---
    if "use_tls" in config and not isinstance(config["use_tls"], bool):
        errors.append("'use_tls' must be bool")

    if "max_retries" in config:
        v = config["max_retries"]
        if not isinstance(v, int):
            errors.append("'max_retries' must be int")
        elif v < 0:
            errors.append("'max_retries' must be >= 0")

    if "send_delay" in config:
        v = config["send_delay"]
        if not isinstance(v, (int, float)):
            errors.append("'send_delay' must be a number")
        elif v < 0:
            errors.append("'send_delay' must be >= 0")

    if "log_level" in config:
        v = config["log_level"]
        if not isinstance(v, str):
            errors.append("'log_level' must be str")
        elif v.upper() not in _VALID_LOG_LEVELS:
            errors.append(
                f"'log_level' must be one of {sorted(_VALID_LOG_LEVELS)}, got '{v}'"
            )

    if "attachment_size_limit" in config:
        v = config["attachment_size_limit"]
        if not isinstance(v, int):
            errors.append("'attachment_size_limit' must be int")
        elif v <= 0:
            errors.append("'attachment_size_limit' must be > 0")

    return ValidationResult(
        is_valid=len(errors) == 0,
        value=config,
        errors=errors,
        field="email_config",
    )


def validate_api_config(config: dict) -> ValidationResult:
    """Validate the contents of ``api_server_config.json``.

    Required keys: ``host`` (str), ``port`` (int, 1-65535).
    """
    errors: List[str] = []

    # --- required keys ---
    for key in ("host", "port"):
        if key not in config:
            errors.append(f"Missing required key '{key}'")

    if "host" in config and not isinstance(config["host"], str):
        errors.append("'host' must be str")

    if "port" in config:
        _check_port(errors, config["port"])

    # --- optional top-level booleans ---
    for key in ("debug", "ssl_enabled"):
        if key in config and not isinstance(config[key], bool):
            errors.append(f"'{key}' must be bool")

    # --- nested: rate_limiting ---
    rl = config.get("rate_limiting")
    if rl is not None:
        if not isinstance(rl, dict):
            errors.append("'rate_limiting' must be a dict")
        else:
            if "enabled" in rl and not isinstance(rl["enabled"], bool):
                errors.append("'rate_limiting.enabled' must be bool")
            if "requests_per_minute" in rl:
                v = rl["requests_per_minute"]
                if not isinstance(v, int):
                    errors.append("'rate_limiting.requests_per_minute' must be int")
                elif v <= 0:
                    errors.append("'rate_limiting.requests_per_minute' must be > 0")

    # --- optional: max_content_length ---
    if "max_content_length" in config:
        v = config["max_content_length"]
        if not isinstance(v, int):
            errors.append("'max_content_length' must be int")
        elif v <= 0:
            errors.append("'max_content_length' must be > 0")

    # --- nested: jwt ---
    jwt = config.get("jwt")
    if jwt is not None:
        if not isinstance(jwt, dict):
            errors.append("'jwt' must be a dict")
        else:
            if "algorithm" in jwt:
                v = jwt["algorithm"]
                if not isinstance(v, str):
                    errors.append("'jwt.algorithm' must be str")
                elif v not in _VALID_JWT_ALGORITHMS:
                    errors.append(
                        f"'jwt.algorithm' must be one of {sorted(_VALID_JWT_ALGORITHMS)}, got '{v}'"
                    )

    return ValidationResult(
        is_valid=len(errors) == 0,
        value=config,
        errors=errors,
        field="api_config",
    )


def validate_sms_config(config: dict) -> ValidationResult:
    """Validate the contents of ``sms_config.json``.

    All keys are optional.  Provider names, when present, must be one of
    the recognised provider identifiers.
    """
    errors: List[str] = []

    for key in ("primary_provider", "fallback_provider"):
        if key in config:
            v = config[key]
            if v is None:
                continue  # null is acceptable for fallback
            if not isinstance(v, str):
                errors.append(f"'{key}' must be str or null")
            elif v not in _VALID_SMS_PROVIDERS:
                errors.append(
                    f"'{key}' must be one of {sorted(_VALID_SMS_PROVIDERS)}, got '{v}'"
                )

    return ValidationResult(
        is_valid=len(errors) == 0,
        value=config,
        errors=errors,
        field="sms_config",
    )
