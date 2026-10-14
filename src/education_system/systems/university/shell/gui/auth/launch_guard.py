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

Whatever the source, the resolved session is published into
``shared_context`` (see ``_publish_session``) so that the many modules which
reach for ``get_auth().current_user`` at call time work in a subprocess
launch too — previously only the in-process launcher ever populated it, so a
child GUI could show a correct user everywhere it was handed ``auth``
explicitly while any get_auth() consumer inside it behaved as logged out.
"""

from __future__ import annotations

from education_system.systems.university.infrastructure.i18n import get_text as _t

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


def _session_from_env(user: dict) -> Optional[dict]:
    """Build a full university session dict from the ``EDU_AUTH_*`` bundle.

    The env bundle carries only identity, not permissions or the local
    ``student_id``; ``build_session_user`` resolves those from the username
    the same way the launcher and the CLI do, so a child process ends up with
    the session its parent had rather than a thinner look-alike.
    """
    username = user.get("username") or ""
    if not username:
        return None
    try:
        from education_system.systems.university.infrastructure.auth.session_user import (
            build_session_user,
        )
    except Exception:
        logger.debug("session_user unavailable; publishing env session as-is", exc_info=True)
        return None
    try:
        return build_session_user(
            {
                "username": username,
                # Preferred over the university-local id in the bundle: this is
                # the auth.db id the cross-system feeds key off.
                "user_id": os.environ.get("EDU_AUTH_SHARED_ID") or user.get("id"),
                "display_name": os.environ.get("EDU_AUTH_DISPLAY_NAME") or username,
                "email": user.get("email", ""),
                "systems": [],
            },
            user.get("role") or "",
        )
    except Exception:
        logger.debug("Could not build session user from env bundle", exc_info=True)
        return None


def _publish_session(user: dict) -> None:
    """Make *user* the process-wide auth session if nothing else has.

    Never overwrites a session that is already in place: an in-process launch
    already holds the real logged-in instance, and replacing it would swap the
    live object out from under everything holding a reference to it.
    """
    try:
        from education_system.systems.university.infrastructure import shared_context
    except Exception:
        logger.debug("shared_context unavailable; session not published", exc_info=True)
        return

    try:
        auth = shared_context.get_auth()
    except Exception:
        try:
            auth = shared_context.initialize_auth()
        except Exception:
            logger.debug("Could not initialise auth to publish session", exc_info=True)
            return

    if auth is None or isinstance(getattr(auth, "current_user", None), dict):
        return

    session = _session_from_env(user) or user
    try:
        auth.current_user = session
        from datetime import datetime
        if hasattr(auth, "last_activity"):
            auth.last_activity = datetime.now()
    except Exception:
        logger.debug("Could not attach session to the auth instance", exc_info=True)
        return

    logger.info(
        "Published session for %s into shared_context (subprocess launch)",
        session.get("username") or session.get("id"),
    )


def _show_login_error(module_name: str) -> None:
    """Show a Tk error dialog, with a console fallback."""
    msg = (
        f"{module_name} can only be launched from the main university\n"
        "system GUI after you have logged in.\n\n"
        "Start the launcher with:  python -m education_system --university --gui"
    )
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(_t('gui.shell.auth.launch_guard.dialogs.login_required', default="Login required"), msg)
        try:
            root.destroy()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
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
        _publish_session(user)
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
