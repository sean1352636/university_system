"""Shared base API configuration for all system APIs."""

import os
import secrets


def _secret_key() -> str:
    """Persistent key in production; ephemeral only in development.

    The old unconditional ``token_hex`` fallback silently minted a new key
    per worker and per restart, invalidating every signed session with no
    error. Production must fail at startup instead.
    """
    key = os.getenv("API_SECRET_KEY")
    if key:
        return key
    app_env = os.getenv("APP_ENV", "production").strip().lower()
    if app_env in ("development", "dev", "local", "test", "testing"):
        return secrets.token_hex(32)
    raise RuntimeError(
        "API_SECRET_KEY must be set in production; a random per-process key "
        "invalidates sessions on every restart and differs across workers."
    )


class _LazySecretKey:
    """Resolve SECRET_KEY on access, not at import.

    Evaluating at import time would (a) bake in one ephemeral key per process
    as the old code did, and (b), with the fail-closed check, crash the import
    itself in production. A descriptor defers resolution to config-load time,
    when an app is actually being built.
    """

    def __get__(self, obj, objtype=None):
        return _secret_key()


class BaseAPIConfig:
    """Base configuration shared by all system API servers."""
    JWT_EXPIRY_HOURS = 24
    JSON_SORT_KEYS = False
    DEBUG = os.getenv("API_DEBUG", "false").lower() == "true"
    SECRET_KEY = _LazySecretKey()
