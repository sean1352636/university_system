"""Who is signed in, for windows that may run in-process or as a subprocess.

The university main GUI launches some feature windows in their own process
and passes the session through ``EDU_AUTH_*`` environment variables. A window
opened in-process is handed the auth object instead. ``session_user`` reads
whichever is present so the window code does not care which way it opened.
"""

from __future__ import annotations

import os
from typing import Any

STAFF_ROLES = ("admin", "staff")


def session_user(auth: Any = None) -> dict[str, Any] | None:
    """The logged-in user from ``auth.current_user`` or the EDU_AUTH_* env vars."""
    user = getattr(auth, "current_user", None)
    if user:
        return dict(user)
    username = os.environ.get("EDU_AUTH_USERNAME") or ""
    if not username:
        return None
    return {
        "username": username,
        "role": os.environ.get("EDU_AUTH_ROLE") or "",
        "id": os.environ.get("EDU_AUTH_USER_ID") or None,
        "email": os.environ.get("EDU_AUTH_EMAIL") or "",
    }


def is_staff(user: dict[str, Any] | None) -> bool:
    return bool(user) and str(user.get("role", "")).lower() in STAFF_ROLES


def actor_name(user: dict[str, Any] | None, fallback: str = "gui") -> str:
    """The identifier written into ``created_by``/``actor_id`` columns."""
    user = user or {}
    return str(user.get("username") or user.get("id") or fallback)


__all__ = ["STAFF_ROLES", "session_user", "is_staff", "actor_name"]
