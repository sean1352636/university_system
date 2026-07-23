"""Universal CLI login for the Education System.

Authenticates users against the shared auth database, then presents
the list of systems they have access to.  The chosen system and the
user's role in that system are returned to the caller.
"""

import getpass
import logging

from education_system.shared.auth.core import UserAuth
from education_system.shared.auth.defaults import SYSTEMS
from education_system.shared.auth.exceptions import AuthError

logger = logging.getLogger(__name__)


def _print_header(title: str):
    print(f"\n{'=' * 54}")
    print(f"  {title}")
    print(f"{'=' * 54}")


def _cli_force_password_change(user_info: dict, auth) -> bool:
    """Prompt the user to change their expired password in the CLI.

    Returns True if the password was changed successfully, False otherwise.
    """
    print("  Min 12 chars, uppercase, lowercase, digit, special char.\n")

    for _ in range(3):
        current_pw = getpass.getpass("  Current password: ")
        new_pw = getpass.getpass("  New password:     ")
        confirm_pw = getpass.getpass("  Confirm password: ")

        if new_pw != confirm_pw:
            print("\n  Passwords do not match. Try again.\n")
            continue

        try:
            auth.change_password(user_info["id"], current_pw, new_pw)
            print("\n  Password changed successfully!")
            # Re-login with new password to refresh session
            try:
                new_info = auth.login(user_info["username"], new_pw)
                # Update user_info in place
                user_info.update(new_info)
            except AuthError:
                print("  Please log in again with your new password.")
                return False
            return True
        except AuthError as exc:
            print(f"\n  Error: {exc}\n")

    print("\n  Too many failed attempts.")
    return False


def cli_login_prompt(auth: UserAuth | None = None) -> tuple[dict, UserAuth] | None:
    """Authenticate a user against the shared auth database.

    Shows the unified "Education System - Login" header, handles MFA
    (email OTP + TOTP/recovery), and returns ``(user_info, auth)`` on
    success, or ``None`` on failure.

    If *auth* is provided it is reused; otherwise a new ``UserAuth()``
    is created against the default shared auth database.
    """
    if auth is None:
        auth = UserAuth()

    _print_header("Education System - Login")
    print()
    print("  Default: superadmin / SuperAdmin@123")
    print()

    user_info = None
    for attempt in range(3):
        username = input("  Username: ").strip()
        password = getpass.getpass("  Password: ")

        if not username or not password:
            print("\n  Please enter both username and password.")
            continue

        try:
            user_info = auth.login(username, password)
        except AuthError as exc:
            print(f"\n  Error: {exc}")
            if attempt < 2:
                print("  Please try again.\n")
            continue

        # Handle MFA challenge (email OTP + TOTP/recovery fallback)
        if user_info.get("mfa_required"):
            from education_system.shared.cli.mfa_cli import cli_mfa_verify
            mfa_result = cli_mfa_verify(user_info["user_id"], auth)
            if mfa_result is None:
                continue
            user_info = mfa_result

        # Handle forced password change
        if user_info.get("password_expired") or user_info.get("must_change_password"):
            if user_info.get("must_change_password"):
                print("\n  This account still uses a default demo password. "
                      "You must set a new password before continuing.")
            else:
                print("\n  Your password has expired. You must set a new password.")
            if not _cli_force_password_change(user_info, auth):
                continue
            # Re-login with new credentials handled inside helper

        break  # login succeeded
    else:
        print("\n  Too many failed attempts.")
        return None

    if user_info is None:
        return None

    return user_info, auth


def universal_cli_login(
    auth_db_path: str | None = None,
    target_system: str | None = None,
) -> tuple[dict, str, str, UserAuth] | None:
    """Authenticate a user and let them pick a system.

    Returns ``(user_info, system_key, system_role, auth)`` on success,
    or ``None`` if the user cancels or exhausts their login attempts.
    """
    result = cli_login_prompt(UserAuth(auth_db_path))
    if result is None:
        return None

    user_info, auth = result

    # ── System selection ──────────────────────────────────────────
    systems = user_info.get("systems", [])

    if not systems:
        print("\n  Your account does not have access to any systems.")
        print("  Please contact an administrator.")
        return None

    if target_system:
        for sys_info in systems:
            if sys_info["system_key"] == target_system:
                display = user_info.get("display_name", user_info.get("username", "User"))
                print(f"\n  Welcome, {display}!")
                print(f"  Launching {SYSTEMS.get(target_system, target_system.title())}...")
                return user_info, target_system, sys_info["role"], auth

        print(
            f"\n  Your account does not have access to "
            f"{SYSTEMS.get(target_system, target_system.title())}."
        )
        auth.logout()
        return None

    # Single system — auto-select
    if len(systems) == 1:
        sys_info = systems[0]
        display = user_info.get("display_name", user_info.get("username", "User"))
        print(f"\n  Welcome, {display}!")
        print(f"  System: {SYSTEMS.get(sys_info['system_key'], sys_info['system_key'])}")
        print(f"  Role:   {sys_info['role']}")
        return user_info, sys_info["system_key"], sys_info["role"], auth

    # Check if user is superadmin (admin in all 4 systems)
    admin_keys = {s["system_key"] for s in systems if s.get("role") == "admin"}
    is_superadmin = admin_keys >= {"university", "college", "school", "primary"}

    display = user_info.get("display_name", user_info.get("username", "User"))

    # Superadmin — go straight to dashboard
    if is_superadmin:
        print(f"\n  Welcome, {display}!")
        print("  Launching Super Admin Dashboard...")
        return user_info, "__superadmin__", "admin", auth

    # Multiple systems — let the user pick
    print(f"\n  Welcome, {display}!")
    print("\n  ── Select System ──\n")

    for idx, sys_info in enumerate(systems, 1):
        key = sys_info["system_key"]
        role = sys_info["role"]
        label = SYSTEMS.get(key, key.title())
        print(f"  [{idx}] {label} ({role})")

    print("  [0] Cancel")
    print()

    choice = input("  Select system: ").strip()
    if choice == "0":
        auth.logout()
        return None

    if is_superadmin and choice.lower() == "s":
        return user_info, "__superadmin__", "admin", auth

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(systems):
            picked = systems[idx]
            print(f"\n  Launching {SYSTEMS.get(picked['system_key'], picked['system_key'])}...")
            return user_info, picked["system_key"], picked["role"], auth
    except (ValueError, IndexError):
        pass

    print("\n  Invalid selection.")
    auth.logout()
    return None
