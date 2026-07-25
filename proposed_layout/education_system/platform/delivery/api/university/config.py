"""API server configuration loader.

Loads settings from api_server_config.json with sensible defaults.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from typing import Any, Optional

from education_system.systems.university.infrastructure import paths

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = str(paths.CONFIG_DIR / "api_server_config.json")

_DEFAULTS = {
    "host": "localhost",
    "port": 5000,
    "debug": False,
    "ssl_enabled": False,
    "max_content_length": 16 * 1024 * 1024,  # 16 MB
    "rate_limiting": {"enabled": True, "requests_per_minute": 100},
    "jwt": {
        "secret_key": None,
        "access_token_expires_minutes": 30,
        "refresh_token_expires_days": 7,
        "algorithm": "HS256",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*, returning a new dict."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: Optional[str] = None) -> dict[str, Any]:
    """Load API configuration from JSON file, merged with defaults.

    If no config file exists a default configuration is returned.
    A random JWT secret is generated when none is configured.
    """
    config_path = path or _DEFAULT_CONFIG_PATH
    file_config: dict[str, Any] = {}

    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                file_config = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load API config from %s: %s", config_path, exc)

    config = _deep_merge(_DEFAULTS, file_config)

    # Validate merged config
    from education_system.systems.university.infrastructure.validation.config_validators import validate_api_config
    result = validate_api_config(config)
    if not result.is_valid:
        logger.warning("API config validation warnings: %s", result.error_message)

    # Guarantee a JWT secret exists
    jwt_cfg = config.setdefault("jwt", {})
    if not jwt_cfg.get("secret_key"):
        jwt_cfg["secret_key"] = secrets.token_hex(32)
        logger.info("Generated random JWT secret (not persisted)")

    return config
