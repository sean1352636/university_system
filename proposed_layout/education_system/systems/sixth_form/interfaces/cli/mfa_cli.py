"""CLI flow for email-based Multi-Factor Authentication."""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.interfaces.mfa import (
    CODE_TTL_MINUTES,
    MFASetupError,
    confirm_code,
    disable,
    get_email,
    is_enabled,
    send_code,
)

logger = logging.getLogger(__name__)


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _read(prompt: str) -> str:
    try:
        return input(f"  {prompt}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def _enable_flow(auth) -> None:
    current = get_email(auth)
    if current:
        print(f"\n  Current MFA email: {current}")
        print("  Press Enter to keep it, or type a new address.")
    email = _read("Email address") or current or ""
    if not email:
        print("\n  Cancelled — no email provided.")
        return
    print(f"\n  Sending a verification code to {email}…")
    try:
        send_code(auth, email)
    except MFASetupError as e:
        print(f"\n  ✗ {e}")
        return
    print(f"  ✓ Code sent. It will expire in {CODE_TTL_MINUTES} minutes.")
    while True:
        code = _read("Enter the 6-digit code (blank to cancel)")
        if not code:
            print("\n  Cancelled.")
            return
        try:
            ok = confirm_code(auth, code)
        except MFASetupError as e:
            print(f"\n  ✗ {e}")
            return
        if ok:
            print("\n  ✓ MFA enabled. Codes will be sent to this address "
                  "when MFA is required.")
            return
        print("  ✗ That code didn't match — try again.")


def _disable_flow(auth) -> None:
    confirm = _read("Type 'disable' to turn MFA off")
    if confirm.lower() != "disable":
        print("\n  Cancelled.")
        return
    try:
        disable(auth)
    except MFASetupError as e:
        print(f"\n  ✗ {e}")
        return
    print("\n  ✓ MFA disabled.")


def run(auth) -> None:
    while True:
        print("\n═══ Multi-Factor Authentication (Email) ═══")
        try:
            enabled = is_enabled(auth)
        except MFASetupError as e:
            print(f"  ✗ {e}")
            _pause()
            return
        email = get_email(auth)
        status = "ENABLED" if enabled else "disabled"
        print(f"  Status: {status}")
        if email:
            print(f"  Email:  {email}")
        if enabled:
            print("\n  1) Re-verify / change email")
            print("  2) Disable MFA")
            print("  0) Back")
        else:
            print("\n  1) Enable MFA (send a code to my email)")
            print("  0) Back")
        choice = _read("Select")
        if choice == "0" or choice == "":
            return
        if choice == "1":
            _enable_flow(auth)
            _pause()
            continue
        if enabled and choice == "2":
            _disable_flow(auth)
            _pause()
            continue
        print("  Invalid selection.")


def dispatch(label: str, auth=None) -> bool:
    if label != "Multi-Factor Authentication":
        return False
    if auth is None:
        print("\n  ✗ MFA needs an active session.")
        _pause()
        return True
    try:
        run(auth)
    except Exception as e:
        logger.exception("MFA CLI handler crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
