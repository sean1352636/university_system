"""Change-password helper for the Nursery System — moved to the platform.

The implementation is now
``education_system.platform.identity.auth.change_password``; four
byte-identical per-system copies were collapsed into it. This module
stays as a re-export so existing imports keep resolving.
"""

from __future__ import annotations

from education_system.platform.identity.auth.change_password import (  # noqa: F401
    ChangePasswordError,
    change_password,
    current_user_id,
    current_username,
)

__all__ = [
    "ChangePasswordError",
    "change_password",
    "current_user_id",
    "current_username",
]
