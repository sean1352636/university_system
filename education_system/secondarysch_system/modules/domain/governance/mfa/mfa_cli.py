"""CLI handlers for Multi-Factor Authentication in the Secondary School System.

Uses the shared ``EmailMFAService`` — codes are 6-digit numerics delivered
to the user's email address. The user can register or change the address
before requesting a code.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.secondarysch_system import SYSTEM_NAME
from education_system.shared.auth.email_mfa import EmailMFAService
from education_system.shared.auth.exceptions import MFAError

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except MFAError as e:
            print(f"  MFA error: {e}")
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _user_context(auth) -> tuple[int, str, str | None]:
    """Return ``(user_id, username, email_on_file)`` for the signed-in user."""
    if auth is None or not getattr(auth, "current_user", None):
        raise MFAError("Not signed in.")
    cu = auth.current_user
    uid = cu.get("user_id") or cu.get("id")
    if uid is None:
        raise MFAError("Cannot find your user id in this session.")
    return int(uid), cu.get("username", "?"), cu.get("email") or None


@_safe
def open_mfa(*, auth=None) -> None:
    logger.debug("CLI: open_mfa")
    uid, username, default_email = _user_context(auth)
    svc = EmailMFAService()
    while True:
        enabled = svc.is_enabled(uid)
        on_file = svc.get_email(uid)
        print("\n  ── Multi-Factor Authentication ──")
        print(f"  Signed in: {username} (user_id={uid})")
        print(f"  Status:    {'ENABLED' if enabled else 'disabled'}")
        print(f"  Email:     {on_file or '(not set)'}")
        if default_email and not on_file:
            print(f"  (Account email on file: {default_email})")
        print()
        print("   1) Set / change MFA email")
        print("   2) Send verification code")
        print("   3) Enter code to enable / verify")
        print("   4) Disable MFA")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": lambda: _set_email(svc, uid, default_email),
            "2": lambda: _send_code(svc, uid, username),
            "3": lambda: _verify_code(svc, uid),
            "4": lambda: _disable(svc, uid),
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _set_email(svc: EmailMFAService, uid: int,
               default_email: str | None) -> None:
    print("\n  ── Set MFA email ──")
    current = svc.get_email(uid)
    if current:
        print(f"  Currently: {current}")
    suggestion = current or default_email
    suffix = f" [{suggestion}]" if suggestion else ""
    new = _prompt(f"  Email address{suffix}: ")
    if not new and suggestion:
        new = suggestion
    if not new:
        print("  Cancelled.")
        return
    email = svc.set_email(uid, new)
    print(f"\n  MFA email set to {email}.")
    print("  Send a code (option 2) and verify it (option 3) to enable.")


@_safe
def _send_code(svc: EmailMFAService, uid: int, username: str) -> None:
    print("\n  ── Send code ──")
    current = svc.get_email(uid)
    if current:
        print(f"  Code will be sent to: {current}")
        override = _prompt(
            "  Press Enter to use this address, or type a different one: ")
    else:
        override = _prompt(
            "  No MFA email on file. Enter address to send code to: ")
        if not override:
            print("  Cancelled.")
            return
    result = svc.send_code(uid,
                           override_email=override or None,
                           username=username,
                           system_name=SYSTEM_NAME)
    # send_code either succeeded (returns sent_to) or raised MFAError.
    print(f"\n  Code sent to {result['sent_to']}. "
          "Check your inbox (and spam folder).")
    print("  Enter the code with option 3 to verify and enable MFA.")


@_safe
def _verify_code(svc: EmailMFAService, uid: int) -> None:
    print("\n  ── Enter code ──")
    code = _prompt("  Code: ")
    if not code:
        print("  Cancelled.")
        return
    if svc.verify_code(uid, code):
        if svc.is_enabled(uid):
            print("\n  ✓ Code verified. MFA is enabled on your account.")
        else:
            print("\n  ✓ Code verified.")


@_safe
def _disable(svc: EmailMFAService, uid: int) -> None:
    if not svc.is_enabled(uid) and svc.get_email(uid) is None:
        print("  MFA is not set up — nothing to disable.")
        return
    confirm = _prompt("  Really disable MFA on your account? (y/N): ").lower()
    if confirm != "y":
        print("  Cancelled.")
        return
    if svc.disable(uid):
        print("  MFA disabled.")
    else:
        print("  Nothing to do.")


_DISPATCH = {"Multi-Factor Authentication": open_mfa}


def dispatch(label: str, *, auth=None) -> bool:
    """Dispatch ``label`` to the matching handler.

    Unlike the other domain modules, MFA needs the auth session so it
    can resolve the current ``user_id``. The caller threads ``auth``
    through from the main menu.
    """
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching MFA CLI label: %s", label)
    handler(auth=auth)
    return True
