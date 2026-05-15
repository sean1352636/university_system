"""CLI flow for the Primary School User Management module.

Roles- and access-focused complement to the User Accounts CLI:

* show the access matrix (per system × role)
* show role distribution for the secondary-school system
* list admins / users without access / locked / inactive
* bulk grant or revoke a role across multiple users
* bulk activate / deactivate
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from education_system.shared.auth.role_manager import ROLE_HIERARCHY
from education_system.primarysch_system.modules.domain.user_management import user_management as data
from education_system.primarysch_system.modules.shared.user_accounts import (
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


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick(label: str, options: list[str],
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


def _parse_ids(raw: str) -> list[int]:
    """Accept comma- and/or space-separated user IDs."""
    parts = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
    ids: list[int] = []
    for p in parts:
        try:
            ids.append(int(p))
        except ValueError:
            raise UserAccountError(f"'{p}' is not a number") from None
    return ids


# ── Print helpers ──────────────────────────────────────────────────

def _print_users(rows: list[UserRow]) -> None:
    if not rows:
        print("\n  (no users)")
        return
    print()
    print(f"  {'ID':>4}  {'Username':<18}  {'Display':<22}  "
          f"{'Secondary-school':<12}  {'Active':<6}  {'Locked':<6}")
    print("  " + "-" * 78)
    for u in rows:
        role = u.role_for(SYSTEM_KEY) or "—"
        active = "yes" if u.is_active else "no"
        locked = "yes" if u.is_locked else "no"
        display = (u.display_name or "")[:22]
        print(f"  {u.id:>4}  {u.username[:18]:<18}  {display:<22}  "
              f"{role:<12}  {active:<6}  {locked:<6}")
    print(f"\n  {len(rows)} user(s).")


# ── Flows ──────────────────────────────────────────────────────────

def show_access_matrix(auth: Any) -> None:
    print("\n═══ Access Matrix ═══")
    m = data.access_matrix(auth)
    if not m.systems:
        print("  (no system access records yet)")
        _pause()
        return
    print(f"\n  {'System':<14}  {'Users':>6}  Role breakdown")
    print("  " + "-" * 66)
    for s in m.systems:
        breakdown = ", ".join(
            f"{r}:{n}" for r, n in sorted(s.by_role.items(),
                                            key=lambda kv: -kv[1]))
        print(f"  {s.system_key:<14}  {s.users:>6}  {breakdown}")
    print(f"\n  Users with no secondary-school access: "
          f"{len(m.users_without_sixthform)}")
    _pause()


def show_role_distribution(auth: Any) -> None:
    print("\n═══ Secondary-School Role Distribution ═══\n")
    counts = data.role_distribution(auth, SYSTEM_KEY)
    print(f"  {'Role':<22}  {'Users':>6}")
    print("  " + "-" * 32)
    for role in sorted(ROLE_HIERARCHY.keys(),
                         key=lambda r: -ROLE_HIERARCHY[r]):
        print(f"  {role:<22}  {counts.get(role, 0):>6}")
    _pause()


def list_admins_flow(auth: Any) -> None:
    print("\n═══ Secondary-School Admins ═══")
    _print_users(data.list_admins(auth))
    _pause()


def list_without_access_flow(auth: Any) -> None:
    print("\n═══ Users without secondary-school access ═══")
    _print_users(data.list_without_access(auth))
    _pause()


def list_locked_flow(auth: Any) -> None:
    print("\n═══ Locked Users ═══")
    _print_users(data.list_locked(auth))
    _pause()


def list_inactive_flow(auth: Any) -> None:
    print("\n═══ Inactive Users ═══")
    _print_users(data.list_inactive(auth))
    _pause()


def bulk_grant_flow(auth: Any) -> None:
    print("\n═══ Bulk Grant Role ═══")
    try:
        ids_raw = _input("User IDs (comma or space separated)",
                          allow_empty=False)
        ids = _parse_ids(ids_raw)
        system_key = _input("System key", default=SYSTEM_KEY)
        role = _pick("Role", list(ROLE_HIERARCHY.keys()),
                      default=DEFAULT_ROLE)
    except (UserAccountError, _UserAbort) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    try:
        result = data.bulk_grant(auth, ids, system_key, role)
    except Exception as e:
        logger.exception("bulk_grant crashed")
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Granted '{role}' on '{system_key}' to "
          f"{len(result.succeeded)} user(s).")
    if result.failed:
        print(f"  ✗ {len(result.failed)} failed:")
        for uid, msg in result.failed:
            print(f"    - #{uid}: {msg}")
    _pause()


def bulk_revoke_flow(auth: Any) -> None:
    print("\n═══ Bulk Revoke System Access ═══")
    try:
        ids_raw = _input("User IDs (comma or space separated)",
                          allow_empty=False)
        ids = _parse_ids(ids_raw)
        system_key = _input("System key", default=SYSTEM_KEY)
    except (UserAccountError, _UserAbort) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    confirm = _input(
        f"Revoke access on '{system_key}' for {len(ids)} user(s)? "
        f"Type 'yes' to confirm", default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        result = data.bulk_revoke(auth, ids, system_key)
    except Exception as e:
        logger.exception("bulk_revoke crashed")
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Revoked on '{system_key}' for "
          f"{len(result.succeeded)} user(s).")
    if result.failed:
        print(f"  ✗ {len(result.failed)} failed:")
        for uid, msg in result.failed:
            print(f"    - #{uid}: {msg}")
    _pause()


def bulk_active_flow(auth: Any) -> None:
    print("\n═══ Bulk Activate / Deactivate ═══")
    try:
        ids_raw = _input("User IDs (comma or space separated)",
                          allow_empty=False)
        ids = _parse_ids(ids_raw)
        choice = _pick("Action", ["Activate", "Deactivate"])
    except (UserAccountError, _UserAbort) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    active = (choice == "Activate")
    try:
        result = data.bulk_set_active(auth, ids, active)
    except Exception as e:
        logger.exception("bulk_set_active crashed")
        print(f"\n  ✗ {e}")
        _pause()
        return
    verb = "Activated" if active else "Deactivated"
    print(f"\n  ✓ {verb} {len(result.succeeded)} user(s).")
    if result.failed:
        print(f"  ✗ {len(result.failed)} failed:")
        for uid, msg in result.failed:
            print(f"    - #{uid}: {msg}")
    _pause()


def summary_flow(auth: Any) -> None:
    print("\n═══ User Management Summary ═══")
    try:
        snap = data.snapshot(auth)
    except Exception as e:
        logger.exception("user management snapshot failed")
        print(f"\n  ✗ {e}")
        _pause()
        return
    s = snap.summary
    print(f"\n  Total users           : {s.total}")
    print(f"  Active                : {s.active}")
    print(f"  Inactive              : {s.inactive}")
    print(f"  Locked                : {s.locked}")
    print(f"  Secondary-school users      : {s.secondary_school_users}")
    print(f"  Secondary-school admins     : {snap.admins}")
    print(f"  Recent logins (7d)    : {s.recent_logins_7d}")
    print("\n  Secondary-school roles:")
    for role, n in snap.role_distribution_sixthform.items():
        if n:
            print(f"    {role:<22}  {n:>4}")
    print("\n  Per-system users:")
    for sa in snap.matrix.systems:
        print(f"    {sa.system_key:<14}  {sa.users:>4}")
    _pause()


# ── Submenu dispatch ───────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[Any], None]]] = [
    ("Summary",                       summary_flow),
    ("Access Matrix",                 show_access_matrix),
    ("Secondary-school Role Distribution",  show_role_distribution),
    ("List Admins",                   list_admins_flow),
    ("Users without secondary-school access", list_without_access_flow),
    ("List Locked",                   list_locked_flow),
    ("List Inactive",                 list_inactive_flow),
    ("Bulk Grant Role",               bulk_grant_flow),
    ("Bulk Revoke Access",            bulk_revoke_flow),
    ("Bulk Activate / Deactivate",    bulk_active_flow),
]


def run(auth: Any) -> None:
    while True:
        print("\n── User Management ──")
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
            logger.exception("User Management CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str, auth=None) -> bool:
    if label != "User Management":
        return False
    if auth is None:
        print("\n  ✗ User Management needs an active session.")
        _pause()
        return True
    try:
        run(auth)
    except Exception as e:
        logger.exception("User Management CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
