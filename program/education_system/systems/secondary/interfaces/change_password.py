"""Change-password helper for the Secondary School System.

Thin wrapper over the shared auth ``UserAuth.change_password()`` that:

* resolves the *current* user id from the shared session
* surfaces validation problems as a typed ``ChangePasswordError``
* doesn't store anything itself (the shared auth layer owns the
  ``users`` + ``password_history`` tables and password policy)

Used by ``change_password_cli`` (CLI) and ``change_password_views``
(GUI). The actual hashing, history check, and strength policy live
in ``shared/auth/core.py``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ChangePasswordError(ValueError):
    pass


def _current_user_id(auth: Any) -> int:
    """Resolve the currently-signed-in user's id from the shared
    auth session. Raises if no session."""
    cu = getattr(auth, "current_user", None) or {}
    uid = cu.get("id") or cu.get("user_id")
    if uid is None:
        raise ChangePasswordError(
            "No active session — please sign in again.")
    try:
        return int(uid)
    except (TypeError, ValueError):
        raise ChangePasswordError(
            "Active session has no usable user id.") from None


def change_password(
    auth: Any,
    *,
    current_password: str,
    new_password: str,
    confirm_password: str,
) -> None:
    """Validate inputs locally, then delegate to ``auth.change_password``.

    Raises ``ChangePasswordError`` for any user-visible problem
    (mismatch, empty fields, wrong current password, weak password,
    reuse). Logs at INFO on success.
    """
    if not current_password:
        raise ChangePasswordError("Current password is required.")
    if not new_password:
        raise ChangePasswordError("New password is required.")
    if not confirm_password:
        raise ChangePasswordError(
            "Please confirm the new password.")
    if new_password != confirm_password:
        raise ChangePasswordError(
            "New password and confirmation don't match.")
    if new_password == current_password:
        raise ChangePasswordError(
            "New password must differ from the current one.")

    uid = _current_user_id(auth)
    try:
        auth.change_password(uid, current_password, new_password)
    except Exception as e:
        # Shared auth raises AuthError for "wrong password", strength,
        # history-reuse. Re-wrap so callers don't need to import it.
        raise ChangePasswordError(str(e)) from e

    logger.info("Password changed for user_id=%d (sixth-form)", uid)


def current_username(auth: Any) -> str:
    cu = getattr(auth, "current_user", None) or {}
    return cu.get("username") or "(unknown)"
