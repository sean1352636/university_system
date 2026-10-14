"""Change-password orchestration shared by every system.

Thin wrapper over the shared auth ``UserAuth.change_password()`` that:

* resolves the *current* user id from the shared session
* surfaces validation problems as a typed :class:`ChangePasswordError`
* doesn't store anything itself (the shared auth layer owns the
  ``users`` + ``password_history`` tables and the password policy)

This module is UI-free on purpose: it is the single validation layer
behind both ``platform/delivery/cli/change_password_cli.py`` and
``platform/delivery/gui/change_password_gui.py``. Hashing, history
checks and strength policy live in ``password_manager.py`` and
``core.py``.

It replaced four byte-identical per-system copies (primary, secondary,
nursery, sixth_form), which had drifted only in their log messages —
every copy logged ``(sixth-form)`` regardless of the system it was in.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "ChangePasswordError",
    "change_password",
    "current_user_id",
    "current_username",
]


class ChangePasswordError(ValueError):
    """A user-visible problem with a change-password attempt."""


def _session(auth: Any) -> dict:
    if isinstance(auth, dict):
        return auth
    return getattr(auth, "current_user", None) or {}


def current_user_id(auth: Any) -> int:
    """Resolve the signed-in user's **shared auth** id.

    ``shared_auth_id`` is checked first and that order is load-bearing:
    the university launcher rewrites ``current_user["user_id"]`` to a
    system-local record id and stashes the real ``auth.db`` id under
    ``shared_auth_id``. Reading ``user_id`` first would hand
    ``auth.change_password`` the wrong account on the university.

    Raises:
        ChangePasswordError: if there is no usable session.
    """
    cu = _session(auth)
    uid = cu.get("shared_auth_id") or cu.get("id") or cu.get("user_id")
    if uid is None:
        raise ChangePasswordError("No active session — please sign in again.")
    try:
        return int(uid)
    except (TypeError, ValueError):
        raise ChangePasswordError("Active session has no usable user id.") from None


def change_password(
    auth: Any,
    *,
    current_password: str,
    new_password: str,
    confirm_password: str,
) -> None:
    """Validate inputs locally, then delegate to ``auth.change_password``.

    Raises:
        ChangePasswordError: for any user-visible problem (empty field,
            mismatch, unchanged password, wrong current password, weak
            password, reuse of a recent password).
    """
    if not current_password:
        raise ChangePasswordError("Current password is required.")
    if not new_password:
        raise ChangePasswordError("New password is required.")
    if not confirm_password:
        raise ChangePasswordError("Please confirm the new password.")
    if new_password != confirm_password:
        raise ChangePasswordError("New password and confirmation don't match.")
    if new_password == current_password:
        raise ChangePasswordError("New password must differ from the current one.")

    uid = current_user_id(auth)
    if not hasattr(auth, "change_password"):
        raise ChangePasswordError("No shared account session is available.")
    try:
        auth.change_password(uid, current_password, new_password)
    except ChangePasswordError:
        raise
    except Exception as e:
        # Shared auth raises AuthError for "wrong password", strength and
        # history-reuse. Re-wrap so callers don't need to import it.
        raise ChangePasswordError(str(e)) from e

    logger.info("Password changed for user_id=%d", uid)


def current_username(auth: Any) -> str:
    """The signed-in username, or ``"(unknown)"`` with no session."""
    return _session(auth).get("username") or "(unknown)"
