"""CLI flow for Change Password, shared by every system.

Validation lives in ``platform/identity/auth/change_password.py``; this
module is only the prompting and printing. It replaced four identical
per-system copies (primary, secondary, nursery, sixth_form).
"""

from __future__ import annotations

import getpass
import logging

from education_system.platform.identity.auth.change_password import (
    ChangePasswordError,
    change_password,
    current_username,
)

logger = logging.getLogger(__name__)

__all__ = ["dispatch", "run"]


def _read_password(prompt: str) -> str:
    """Use ``getpass`` so the password isn't echoed."""
    try:
        return getpass.getpass(f"  {prompt}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def run(auth) -> None:
    """Prompt for the three passwords and apply the change."""
    print("\n═══ Change Password ═══")
    print(f"  Signed in as: {current_username(auth)}")
    print("  (passwords are not echoed; type 'cancel' for the "
          "current password to abort)")
    cur = _read_password("Current password")
    if cur.strip().lower() == "cancel":
        print("\n  Cancelled.")
        return
    new1 = _read_password("New password")
    new2 = _read_password("Confirm new password")
    try:
        change_password(
            auth,
            current_password=cur,
            new_password=new1,
            confirm_password=new2,
        )
    except ChangePasswordError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("Change-password crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print("\n  ✓ Password changed. You may need to sign in again on "
          "other devices.")
    _pause()


def dispatch(label: str, auth=None) -> bool:
    """Handle the ``"Change Password"`` menu label; return True if handled."""
    if label != "Change Password":
        return False
    if auth is None:
        print("\n  ✗ Change Password needs an active session.")
        _pause()
        return True
    try:
        run(auth)
    except Exception as e:
        logger.exception("Change-password CLI handler crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
