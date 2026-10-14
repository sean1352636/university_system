"""API server configuration loader.

Loads settings from api_server_config.json with sensible defaults.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import secrets
from typing import Any, Optional

from education_system import paths
from education_system.platform.delivery.api.security_headers import is_development

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = str(paths.UNIVERSITY_CONFIG_DIR / "api_server_config.json")

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
    """Recursively merge *override* into *base*, returning a new dict.

    ``copy.deepcopy`` rather than ``dict.copy()``: a shallow copy leaves the
    nested dicts aliased to ``_DEFAULTS``, so anything writing to
    ``config["jwt"]`` mutated the module-level defaults for the rest of the
    process. That made a per-process value look stable and hid it in testing.
    """
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _resolve_jwt_secret(configured: str | None) -> str:
    """Return the JWT signing secret, or refuse to start without one.

    Order of precedence: an explicit value in the config file, then
    ``JWT_SECRET_KEY``, then ``API_SECRET_KEY``. ``JWT_SECRET_KEY`` is
    preferred because it is the variable the shared auth layer reads
    (``platform.delivery.api.auth._load_or_create_jwt_secret``); resolving the
    same variable here keeps this server's Flask ``SECRET_KEY`` and its JWT
    signing key in agreement instead of drifting apart.

    Previously this fell back to an unconditional ``secrets.token_hex(32)``,
    which meant every worker signed tokens with a different key and every
    restart invalidated every session — and, because the value was always
    truthy, ``init_auth`` never reached the platform's fail-closed guard. The
    guard is enforced here instead, before a Flask app is built at all.
    """
    if configured:
        return configured
    for var in ("JWT_SECRET_KEY", "API_SECRET_KEY"):
        value = os.getenv(var)
        if value:
            return value
    if is_development():
        logger.warning(
            "No JWT_SECRET_KEY set; generated an ephemeral development secret. "
            "Sessions will not survive a restart and will not be shared across "
            "workers. Set JWT_SECRET_KEY before deploying."
        )
        return secrets.token_hex(32)
    raise RuntimeError(
        "JWT_SECRET_KEY (or API_SECRET_KEY) must be set in production. A "
        "randomly generated per-process key signs tokens that every other "
        "worker rejects and invalidates every session on restart."
    )


def load_config(path: Optional[str] = None) -> dict[str, Any]:
    """Load API configuration from JSON file, merged with defaults.

    If no config file exists a default configuration is returned. The JWT
    secret comes from the config file or the environment; in production a
    missing secret raises rather than being invented.
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

    # Resolve the JWT secret. Fail-closed in production — see
    # _resolve_jwt_secret. `config` is a deep copy, so this no longer writes
    # through to the module-level defaults.
    jwt_cfg = config.setdefault("jwt", {})
    jwt_cfg["secret_key"] = _resolve_jwt_secret(jwt_cfg.get("secret_key"))

    return config
