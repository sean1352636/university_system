"""Standalone-launch auth guard for domain GUIs.

Domain GUIs that expose a ``main()`` / ``if __name__ == '__main__'`` entry
point must refuse to run unless the caller has gone through the unified
launcher's login flow. The launcher spawns child GUIs with a populated
``EDU_AUTH_*`` env-var bundle; in-process launches initialise the global
auth singleton.

Call ``require_launcher_auth()`` at the top of ``main()``. If no
authenticated user is resolvable, this shows a Tk error dialog (when a
display is available) and returns ``None`` — the caller MUST exit.

Resolution order:
  1. ``EDU_AUTH_USER_ID`` / ``EDU_AUTH_USERNAME`` env vars (launcher subprocess)
  2. ``infrastructure.auth.get_global_auth().current_user`` (in-process)
  3. ``infrastructure.shared_context.get_auth().current_user`` (in-process)
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def _from_env() -> Optional[dict]:
    user_id = os.environ.get("EDU_AUTH_USER_ID") or ""
    username = os.environ.get("EDU_AUTH_USERNAME") or ""
    if not (user_id or username):
        return None
    perms_raw = os.environ.get("EDU_AUTH_PERMISSIONS") or ""
    return {
        "id": user_id or None,
        "user_id": user_id or None,
        "username": username,
        "role": os.environ.get("EDU_AUTH_ROLE") or "",
        "email": os.environ.get("EDU_AUTH_EMAIL") or "",
        "permissions": [p for p in perms_raw.split(",") if p],
    }


def _from_global_auth() -> Optional[dict]:
    try:
        from education_system.systems.university.infrastructure.auth import (
            get_global_auth,
        )
    except Exception:
        return None
    try:
        ga = get_global_auth()
        cu = getattr(ga, "current_user", None) if ga else None
        return cu if cu else None
    except Exception:
        return None


def _from_shared_context() -> Optional[dict]:
    try:
        from education_system.systems.university.infrastructure.shared_context import (
            get_auth,
        )
    except Exception:
        return None
    try:
        auth = get_auth()
        cu = getattr(auth, "current_user", None) if auth else None
        return cu if cu else None
    except Exception:
        return None


def _show_login_error(module_name: str) -> None:
    """Show a Tk error dialog, with a console fallback."""
    msg = (
        f"{module_name} can only be launched from the main university\n"
        "system GUI after you have logged in.\n\n"
        "Start the launcher with:  python run.py --university --gui"
    )
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Login required", msg)
        try:
            root.destroy()
        except Exception:
            pass
    except Exception:
        # No display, or Tk failed to start — fall back to stderr.
        sys.stderr.write("Login required: " + msg + "\n")


def require_launcher_auth(module_name: str = "This module") -> Optional[dict]:
    """Return the authenticated user, or None after showing an error.

    Callers MUST treat a None return as a hard exit:

        user = require_launcher_auth("Events GUI")
        if user is None:
            return
    """
    user = _from_env() or _from_global_auth() or _from_shared_context()
    if user:
        logger.info(
            "Auth gate passed for %s: user=%s role=%s",
            module_name,
            user.get("username") or user.get("id"),
            user.get("role") or "",
        )
        return user
    logger.warning("Auth gate refused standalone launch of %s", module_name)
    _show_login_error(module_name)
    return None
