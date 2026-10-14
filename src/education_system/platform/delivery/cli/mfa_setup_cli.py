"""Multi-Factor Authentication enrolment CLI, shared by every system.

The command-line counterpart of
``platform/delivery/gui/mfa_setup_gui.py``: same shared multi-method
:class:`MFAService`, same shared ``auth.db`` store, so a second factor
enrolled in the GUI shows up here and vice versa.

Replaced four per-system copies — three byte-identical 177-line email-only
menus (primary, secondary, nursery) and the sixth form's own, which drove a
bespoke SMTP module of its own. All four could only offer email codes; this
offers an authenticator app, email, SMS and recovery codes.

Not to be confused with ``platform/delivery/cli/mfa_cli.py``, which is the
*login challenge* (``cli_mfa_verify``) rather than enrolment.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system import paths
from education_system.platform.identity.auth.mfa import MFAService

logger = logging.getLogger(__name__)

__all__ = ["dispatch", "open_mfa", "run"]

MENU_LABEL = "Multi-Factor Authentication"


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - CLI boundary
            logger.exception("%s failed", func.__name__)
            print(f"\n  Error: {exc}")
            print("  See logs for details.")
    return wrapper


def _session(auth: Any) -> dict:
    if isinstance(auth, dict):
        return auth
    return getattr(auth, "current_user", None) or {}


def _user_context(auth: Any) -> tuple[int, str]:
    """Return ``(shared_auth_user_id, username)`` for the signed-in user.

    ``shared_auth_id`` is read first and that order matters: this CLI
    writes to the shared ``auth.db``, and a system-local ``user_id`` would
    enrol whichever account happens to hold that number there.
    """
    cu = _session(auth)
    uid = cu.get("shared_auth_id") or cu.get("id") or cu.get("user_id")
    username = cu.get("username")
    if uid is None or not username:
        raise RuntimeError("Not signed in — please sign in again.")
    return int(uid), username


def _service() -> MFAService:
    return MFAService(str(paths.PLATFORM_AUTH_DB))


def _report(result: dict | None, ok: str) -> bool:
    """Print the outcome of a service call. Returns True on success."""
    if result and result.get("success"):
        print(f"\n  ✓ {ok}")
        return True
    print(f"\n  ✗ {(result or {}).get('error') or 'Operation failed.'}")
    return False


# ── enrolment flows ──────────────────────────────────────────────────

@_safe
def _setup_totp(svc: MFAService, uid: int, username: str) -> None:
    print("\n  ── Authenticator app ──")
    result = svc.setup_totp(uid, username)
    if not result.get("success"):
        print(f"\n  ✗ {result.get('error')}")
        return
    print("\n  Add this secret to your authenticator app:")
    print(f"    {result['secret']}")
    print("\n  Or use the provisioning URI:")
    print(f"    {result.get('provisioning_uri', '')}")
    codes = result.get("recovery_codes") or []
    if codes:
        print("\n  Recovery codes — save these now, they are shown once:")
        for code in codes:
            print(f"    {code}")
    code = _prompt("\n  Enter the 6-digit code from your app to confirm: ")
    if not code:
        print("  Cancelled — the secret is stored but unconfirmed.")
        return
    _report(svc.verify_totp(uid, code), "Authenticator app confirmed.")


@_safe
def _setup_email(svc: MFAService, uid: int) -> None:
    print("\n  ── Email codes ──")
    email = _prompt("  Email address to send codes to: ")
    if not email or "@" not in email:
        print("  Cancelled — a valid email address is required.")
        return
    result = svc.generate_email_otp(uid, email, allow_new_identifier=True)
    if not result.get("success"):
        print(f"\n  ✗ {result.get('error')}")
        return
    if result.get("email_failed") and result.get("code"):
        print(f"\n  ⚠ Email delivery failed. Your code is: {result['code']}")
    else:
        print(f"\n  Code sent to {email}. Check your inbox and spam folder.")
    code = _prompt("  Enter the 6-digit code: ")
    if not code:
        print("  Cancelled.")
        return
    if _report(svc.verify_email_otp(uid, code), "Email verified."):
        _report(svc.update_mfa_method(uid, "email", email),
                f"Email codes enabled for {email}.")


@_safe
def _setup_sms(svc: MFAService, uid: int) -> None:
    print("\n  ── SMS codes ──")
    phone = _prompt("  Mobile number to send codes to: ")
    if not phone:
        print("  Cancelled.")
        return
    result = svc.generate_sms_otp(uid, phone, allow_new_identifier=True)
    if not result.get("success"):
        print(f"\n  ✗ {result.get('error')}")
        return
    print(f"\n  Code sent to {phone}.")
    code = _prompt("  Enter the 6-digit code: ")
    if not code:
        print("  Cancelled.")
        return
    if _report(svc.verify_sms_otp(uid, code), "Mobile number verified."):
        _report(svc.update_mfa_method(uid, "sms", phone),
                f"SMS codes enabled for {phone}.")


@_safe
def _recovery_codes(svc: MFAService, uid: int) -> None:
    print("\n  ── Recovery codes ──")
    print("  Generating a new set invalidates any previous codes.")
    if _prompt("  Continue? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    result = svc.generate_recovery_codes(uid)
    if not result.get("success"):
        print(f"\n  ✗ {result.get('error')}")
        return
    print("\n  Save these now — they are shown once:")
    for code in result.get("codes", []):
        print(f"    {code}")


@_safe
def _disable(svc: MFAService, uid: int) -> None:
    print("\n  ── Disable MFA ──")
    print("  Your enrolled methods are retained so you can re-enable later.")
    if _prompt("  Really disable MFA on your account? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    _report(svc.disable_mfa(uid), "MFA disabled.")


# ── menu ─────────────────────────────────────────────────────────────

def _print_status(svc: MFAService, uid: int, username: str) -> None:
    print("\n  ── Multi-Factor Authentication ──")
    print(f"  Signed in: {username} (shared account {uid})")
    status = svc.get_mfa_status(uid) or {}
    enabled = status.get("mfa_enabled")
    print(f"  Status:    {'ENABLED' if enabled else 'disabled'}")
    methods = (svc.get_user_mfa_methods(uid) or {}).get("methods") or []
    if methods:
        print("  Methods:")
        for method in methods:
            if isinstance(method, dict):
                kind = str(method.get("type") or method.get("method_type") or "?").upper()
                print(f"    • {kind}")
    else:
        print("  Methods:   (none enrolled)")


@_safe
def open_mfa(*, auth: Any = None) -> None:
    """Interactive MFA enrolment menu for the signed-in user."""
    try:
        uid, username = _user_context(auth)
    except RuntimeError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return

    svc = _service()
    actions = {
        "1": lambda: _setup_totp(svc, uid, username),
        "2": lambda: _setup_email(svc, uid),
        "3": lambda: _setup_sms(svc, uid),
        "4": lambda: _recovery_codes(svc, uid),
        "5": lambda: _disable(svc, uid),
    }

    while True:
        _print_status(svc, uid, username)
        print()
        print("   1) Set up an authenticator app")
        print("   2) Set up email codes")
        print("   3) Set up SMS codes")
        print("   4) Generate recovery codes")
        print("   5) Disable MFA")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()
        _pause()


def run(auth: Any = None) -> None:
    """Entry point matching the systems that call ``run(auth)``."""
    open_mfa(auth=auth)


def dispatch(label: str, auth: Any = None) -> bool:
    """Handle the MFA menu label; return True if handled."""
    if label != MENU_LABEL:
        return False
    open_mfa(auth=auth)
    return True
