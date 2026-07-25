"""CLI flows for Secondary School User Accounts admin."""

from __future__ import annotations

import getpass
import logging
from typing import Any, Callable
from education_system.systems.secondary.interfaces import user_accounts as data
from education_system.systems.secondary.interfaces.user_accounts import (
    DEFAULT_ROLE,
    ROLES,
    SYSTEM_KEY,
    UserAccountError,
    UserRow,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _password(prompt: str) -> str:
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


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel').")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _yes_no(prompt: str, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)", default="y" if default else "n")
    return raw.lower() in ("y", "yes")


# ── Print helpers ──────────────────────────────────────────────────

def _systems_str(u: UserRow) -> str:
    if not u.systems:
        return "—"
    return ", ".join(f"{s['system_key']}:{s['role']}"
                       for s in u.systems)


def _print_users(rows: list[UserRow]) -> None:
    if not rows:
        print("\n  (no users)")
        return
    print()
    print(f"  {'#':>4}  {'Username':<18}  {'Display':<22}  "
          f"{'Email':<26}  {'Active':<6}  {'Locked':<6}  Systems")
    print("  " + "-" * 130)
    for u in rows:
        print(f"  {u.id:>4}  {u.username[:18]:<18}  "
              f"{(u.display_name or '—')[:22]:<22}  "
              f"{(u.email or '—')[:26]:<26}  "
              f"{('Y' if u.is_active else 'N'):<6}  "
              f"{('Y' if u.is_locked else 'N'):<6}  "
              f"{_systems_str(u)[:60]}")
    print(f"\n  {len(rows)} user(s).")


# ── Flows ──────────────────────────────────────────────────────────

def list_all(auth: Any) -> None:
    print("\n═══ All Users ═══")
    _print_users(data.list_users(auth))
    _row_action_loop(auth)


def list_sixthform(auth: Any) -> None:
    print("\n═══ Secondary-School Users ═══")
    _print_users(data.list_users(auth, system_key=SYSTEM_KEY))
    _row_action_loop(auth)


def list_locked(auth: Any) -> None:
    print("\n═══ Locked Users ═══")
    _print_users(data.list_users(auth, locked_only=True))
    _row_action_loop(auth)


def filter_users(auth: Any) -> None:
    print("\n═══ Filter Users ═══")
    try:
        q = _input("Search (username / name / email)") or None
        role = _input(f"Role ({'/'.join(ROLES)}, blank=skip)") or None
        sixth = _yes_no("Secondary-school only?", default=True)
        active = _yes_no("Active only?", default=False)
        locked = _yes_no("Locked only?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_users(
            auth, query=q, role=role,
            system_key=SYSTEM_KEY if sixth else None,
            active_only=active, locked_only=locked)
    except UserAccountError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_users(rows)
    _row_action_loop(auth)


def view_user(auth: Any, user_id: int | None = None) -> None:
    print("\n═══ View User ═══")
    try:
        uid = user_id if user_id is not None else int(
            _input("User ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    u = data.get_user(auth, uid)
    if u is None:
        print(f"  ✗ No user #{uid}")
        _pause()
        return
    print()
    print(f"    User ID         : #{u.id}")
    print(f"    Username        : {u.username}")
    print(f"    Display name    : {u.display_name or '—'}")
    print(f"    Email           : {u.email or '—'}")
    print(f"    Active          : {'Yes' if u.is_active else 'No'}")
    print(f"    Locked          : "
          f"{'Yes (until ' + u.locked_until + ')' if u.is_locked else 'No'}")
    print(f"    Failed attempts : {u.failed_login_attempts}")
    print(f"    Created at      : {u.created_at}")
    print(f"    Updated at      : {u.updated_at}")
    print(f"    Last login      : {u.last_login or '—'}")
    print(f"    Pwd changed at  : {u.password_changed_at or '—'}")
    if u.systems:
        print("\n    System access:")
        for s in u.systems:
            print(f"      {s['system_key']:<14} → {s['role']}")
    else:
        print("\n    System access: (none)")
    _pause()


def new_user(auth: Any) -> None:
    print("\n═══ New User ═══")
    try:
        username = _input("Username", allow_empty=False)
        display = _input("Display name (optional)")
        email = _input("Email (optional)")
        role = _pick_from("Secondary-school role", list(ROLES),
                            default=DEFAULT_ROLE)
        also_other = _yes_no(
            "Grant access in any other system too?", default=False)
        other_pairs: list[tuple[str, str]] = []
        while also_other:
            sk = _input("Other system key (or blank to stop)")
            if not sk:
                break
            other_role = _pick_from(f"Role for '{sk}'",
                                       list(ROLES), default=DEFAULT_ROLE)
            other_pairs.append((sk, other_role))
            also_other = _yes_no("Another system?", default=False)
        print("  (password is not echoed)")
        p1 = _password("Password")
        p2 = _password("Confirm password")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if p1 != p2:
        print("\n  ✗ Passwords don't match.")
        _pause()
        return
    try:
        u = data.create_user(
            auth, username=username, password=p1,
            display_name=display, email=email,
            role=role)
        for sk, r in other_pairs:
            data.grant_role(auth, u.id, sk, r)
    except UserAccountError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created user #{u.id} ({u.username}).")
    _pause()


def edit_profile(auth: Any, user_id: int | None = None) -> None:
    print("\n═══ Edit Profile ═══")
    try:
        uid = user_id if user_id is not None else int(
            _input("User ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_user(auth, uid)
    if existing is None:
        print(f"  ✗ No user #{uid}")
        _pause()
        return
    try:
        display = _input("Display name",
                            default=existing.display_name or "")
        email = _input("Email", default=existing.email or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_profile(auth, uid,
                              display_name=display, email=email)
    except UserAccountError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated profile for {existing.username}")
    _pause()


def reset_password_flow(auth: Any,
                            user_id: int | None = None) -> None:
    print("\n═══ Admin Reset Password ═══")
    print("  Sets a new password without needing the old one.")
    try:
        uid = user_id if user_id is not None else int(
            _input("User ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_user(auth, uid)
    if existing is None:
        print(f"  ✗ No user #{uid}")
        _pause()
        return
    print(f"  Resetting password for: {existing.username}")
    p1 = _password("New password")
    p2 = _password("Confirm")
    if p1 != p2:
        print("\n  ✗ Passwords don't match.")
        _pause()
        return
    try:
        data.admin_reset_password(auth, uid, p1)
    except UserAccountError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Password reset. Active sessions for "
          f"{existing.username} have been invalidated.")
    _pause()


def lock_flow(auth: Any, user_id: int | None = None) -> None:
    print("\n═══ Lock User ═══")
    try:
        uid = user_id if user_id is not None else int(
            _input("User ID", allow_empty=False))
        mins = int(_input("Lock duration in minutes",
                              default="60"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        u = data.lock_user(auth, uid, mins)
    except UserAccountError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Locked {u.username} until {u.locked_until}")
    _pause()


def unlock_flow(auth: Any, user_id: int | None = None) -> None:
    print("\n═══ Unlock User ═══")
    try:
        uid = user_id if user_id is not None else int(
            _input("User ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        u = data.unlock_user(auth, uid)
    except UserAccountError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Unlocked {u.username}.")
    _pause()


def toggle_active_flow(auth: Any,
                         user_id: int | None = None) -> None:
    print("\n═══ Activate / Deactivate ═══")
    try:
        uid = user_id if user_id is not None else int(
            _input("User ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_user(auth, uid)
    if existing is None:
        print(f"  ✗ No user #{uid}")
        _pause()
        return
    new_state = not existing.is_active
    if not _yes_no(
            f"{'Activate' if new_state else 'Deactivate'} "
            f"{existing.username}?", default=False):
        print("\n  Cancelled.")
        return
    try:
        data.set_active(auth, uid, new_state)
    except UserAccountError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {existing.username} → "
          f"{'active' if new_state else 'inactive'}")
    _pause()


def grant_role_flow(auth: Any,
                       user_id: int | None = None) -> None:
    print("\n═══ Grant Role ═══")
    try:
        uid = user_id if user_id is not None else int(
            _input("User ID", allow_empty=False))
        system = _input("System key", default=SYSTEM_KEY,
                            allow_empty=False)
        role = _pick_from("Role", list(ROLES), default=DEFAULT_ROLE)
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        data.grant_role(auth, uid, system, role)
    except UserAccountError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Granted {role} on {system}.")
    _pause()


def revoke_role_flow(auth: Any,
                        user_id: int | None = None) -> None:
    print("\n═══ Revoke Role ═══")
    try:
        uid = user_id if user_id is not None else int(
            _input("User ID", allow_empty=False))
        system = _input("System key", default=SYSTEM_KEY,
                            allow_empty=False)
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if not _yes_no(f"Revoke access to '{system}' for user #{uid}?",
                    default=False):
        print("\n  Cancelled.")
        return
    try:
        data.revoke_role(auth, uid, system)
    except UserAccountError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Revoked access to {system}.")
    _pause()


def delete_user_flow(auth: Any,
                        user_id: int | None = None) -> None:
    print("\n═══ Delete User ═══")
    print("  ⚠ This is irreversible. Sessions, MFA secrets, and "
          "history are also removed.")
    try:
        uid = user_id if user_id is not None else int(
            _input("User ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_user(auth, uid)
    if existing is None:
        print(f"  ✗ No user #{uid}")
        _pause()
        return
    if _input(f"Delete user {existing.username!r}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_user(auth, uid):
            print(f"\n  ✓ Deleted {existing.username}")
    except UserAccountError as e:
        print(f"\n  ✗ {e}")
    _pause()


def summary_flow(auth: Any) -> None:
    print("\n═══ User Accounts Summary ═══")
    s = data.summary(auth)
    print(f"\n  Total users           : {s.total}")
    print(f"  Active                : {s.active}")
    print(f"  Inactive              : {s.inactive}")
    print(f"  Locked (right now)    : {s.locked}")
    print(f"  Secondary-school users      : {s.sixth_form_users}")
    print(f"  Logins in last 7 days : {s.recent_logins_7d}")
    print("\n  By role in secondary-school:")
    for r in ROLES:
        n = s.by_role_in_sixthform.get(r, 0)
        if n:
            print(f"    {r:<20} : {n}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop(auth: Any) -> None:
    print()
    print("  Actions:  V) View   E) Edit profile   R) Reset password   "
          "L) Lock   U) Unlock   T) Toggle active   "
          "G) Grant role   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "r", "l", "u", "t", "g", "d"):
            print("    Pick V, E, R, L, U, T, G, D, or Enter.")
            continue
        try:
            raw = _input("User ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            uid = int(raw)
        except ValueError:
            print("    User ID must be a whole number.")
            continue
        if choice == "v":
            view_user(auth, uid)
        elif choice == "e":
            edit_profile(auth, uid)
        elif choice == "r":
            reset_password_flow(auth, uid)
        elif choice == "l":
            lock_flow(auth, uid)
        elif choice == "u":
            unlock_flow(auth, uid)
        elif choice == "t":
            toggle_active_flow(auth, uid)
        elif choice == "g":
            grant_role_flow(auth, uid)
        elif choice == "d":
            delete_user_flow(auth, uid)
        return


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[Any], None]]] = [
    ("Secondary-School Users",      list_sixthform),
    ("All Users",             list_all),
    ("Locked Users",          list_locked),
    ("Filter / Search",       filter_users),
    ("View User",             view_user),
    ("New User",              new_user),
    ("Edit Profile",          edit_profile),
    ("Reset Password",        reset_password_flow),
    ("Lock User",             lock_flow),
    ("Unlock User",           unlock_flow),
    ("Activate / Deactivate", toggle_active_flow),
    ("Grant Role",            grant_role_flow),
    ("Revoke Role",           revoke_role_flow),
    ("Delete User",           delete_user_flow),
    ("Summary",               summary_flow),
]


def run(auth: Any) -> None:
    while True:
        print("\n── User Accounts ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _, handler = _MENU[int(choice) - 1]
        try:
            handler(auth)
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("User-accounts CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str, auth=None) -> bool:
    if label != "User Accounts":
        return False
    if auth is None:
        print("\n  ✗ User Accounts needs an active session.")
        _pause()
        return True
    try:
        run(auth)
    except Exception as e:
        logger.exception("User-accounts CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
