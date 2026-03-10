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

        break  # login succeeded
    else:
        print("\n  Too many failed attempts.")
        return None

    if user_info is None:
        return None

    return user_info, auth


def universal_cli_login(auth_db_path: str | None = None) -> tuple[dict, str, str, UserAuth] | None:
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

    # Single system — auto-select
    if len(systems) == 1:
        sys_info = systems[0]
        display = user_info.get("display_name", user_info.get("username", "User"))
        print(f"\n  Welcome, {display}!")
        print(f"  System: {SYSTEMS.get(sys_info['system_key'], sys_info['system_key'])}")
        print(f"  Role:   {sys_info['role']}")
        return user_info, sys_info["system_key"], sys_info["role"], auth

    # Multiple systems — let the user pick
    display = user_info.get("display_name", user_info.get("username", "User"))
    print(f"\n  Welcome, {display}!")
    print("\n  ── Select System ──\n")

    for idx, sys_info in enumerate(systems, 1):
        key = sys_info["system_key"]
        role = sys_info["role"]
        label = SYSTEMS.get(key, key.title())
        print(f"  [{idx}] {label} ({role})")

    print(f"  [0] Cancel")
    print()

    choice = input("  Select system: ").strip()
    if choice == "0":
        auth.logout()
        return None

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
