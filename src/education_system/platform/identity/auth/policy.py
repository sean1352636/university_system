"""Sign-in policy values an administrator can change (``auth_settings``),
read where they are enforced. A key that isn't stored, can't be read or is
out of range gives the built-in default (:mod:`defaults`), so nothing
changes until someone saves a value."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

#: key -> (lowest, highest) accepted. Values outside fall back to the default.
POLICY_LIMITS: dict[str, tuple[int, int]] = {
    "max_login_attempts": (1, 20),
    "lockout_minutes": (1, 1440),
    "session_timeout_minutes": (5, 1440),
    "password_max_age_days": (1, 3650),
}

#: Built-in password age (days) when no policy is stored.
DEFAULT_PASSWORD_MAX_AGE_DAYS = 90


def policy_int(conn: Any, key: str, default: int) -> int:
    """The stored whole-number policy *key* read on *conn*, else *default*."""
    lo, hi = POLICY_LIMITS[key]
    try:
        row = conn.execute("SELECT value FROM auth_settings WHERE key = ?", (key,)).fetchone()
    except Exception:  # noqa: BLE001 - no settings table yet: the built-in default
        return default
    if row is None:
        return default
    try:
        value = int(str(row[0]).strip())
    except ValueError:
        logger.warning("Sign-in policy %s has a bad stored value - using %s", key, default)
        return default
    if not lo <= value <= hi:
        logger.warning("Sign-in policy %s=%s is out of range - using %s", key, value, default)
        return default
    return value


__all__ = ["DEFAULT_PASSWORD_MAX_AGE_DAYS", "POLICY_LIMITS", "policy_int"]
