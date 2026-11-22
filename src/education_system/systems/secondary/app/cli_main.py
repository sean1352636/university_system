"""Terminal main menu for the Secondary School System.

Same structure as the GUI: a numbered list of categories, each opening a
sub-menu of features. The catalogue comes from :mod:`app.routing` and is
filtered by :mod:`core.permissions.access`, exactly as the GUI sidebar is. An entry runs
the menu its area registered for the key (``MENUS`` in
``modules/<module>/cli/__init__.py``, see :mod:`ui.cli.menus.menus`); the few that are
not a module's (password, MFA, About) are in :data:`_HANDLERS`. Anything
else prints a "not built yet" notice.

Launched only by the unified launcher after the shared login.
"""

from __future__ import annotations

import logging
from typing import Callable

from education_system.platform.delivery.cli.cli_helpers import idle_session
from education_system.systems.secondary import SYSTEM_KEY, SYSTEM_NAME
from education_system.systems.secondary.app import bootstrap
from education_system.systems.secondary.core.permissions import access
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.app import routing as menu
from education_system.systems.secondary.ui.cli.menus import menus

logger = logging.getLogger(__name__)

VERSION = "0.1.0"


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except EOFError:
        return "q"


def _pause() -> None:
    _prompt("\n  Press Enter to continue...")


# ── Built entries ────────────────────────────────────────────────────

def _change_password(auth, _principal) -> None:
    from education_system.platform.delivery.cli import change_password_cli
    change_password_cli.run(auth)


def _mfa(auth, _principal) -> None:
    from education_system.platform.delivery.cli.mfa_setup_cli import open_mfa
    open_mfa(auth=auth)


def _about(_auth, principal: access.Principal) -> None:
    print(f"\n═══ {SYSTEM_NAME} ═══")
    print(f"  Version:      {VERSION}")
    print("  Covers:       Years 7–11 (Key Stages 3 and 4)")
    print(f"  Signed in as: {principal.username or '—'}")
    print(f"  Role:         {principal.role or '—'}")
    _pause()


#: Entries that are not a module's menu. Everything else is found through
#: the modules' ``MENUS`` (see :mod:`ui.cli.menus.menus`).
_HANDLERS: dict[str, Callable[[object, access.Principal], None]] = {
    "change_password": _change_password,
    "mfa": _mfa,
    "about": _about,
}


def _handler_for(key: str) -> Callable[[object, access.Principal], None] | None:
    if key in _HANDLERS:
        return _HANDLERS[key]
    if menus.registry().get(key) is None:
        return None
    return lambda _auth, principal: menus.find(key)(principal)


def _open(key: str, label: str, auth, principal: access.Principal) -> None:
    if not principal.can_open(label):
        logger.warning("Refused %s for user=%s role=%s",
                       label, principal.username, principal.role)
        activity_log.record("menu.open", target=label, outcome="denied")
        print(f"\n  {principal.denied_message(label)}")
        return
    handler = _handler_for(key)
    if handler is None:
        activity_log.record("menu.open", target=label, outcome="not_built")
        print(f"\n  {label} hasn't been built yet in the new {SYSTEM_NAME}.")
        _pause()
        return
    activity_log.record("menu.open", target=label)
    try:
        handler(auth, principal)
    except Exception as e:  # noqa: BLE001 - keep the menu alive, log the cause
        logger.exception("Secondary CLI: %s failed", label)
        activity_log.record("error", target=label, outcome="error", error=type(e).__name__)
        print(f"\n  {label} could not be opened: {e}")
        _pause()


# ── Menus ────────────────────────────────────────────────────────────

def _submenu(category: str, items: list[tuple[str, str]], auth,
             principal: access.Principal) -> None:
    while True:
        print(f"\n── {category} ──")
        for i, (label, _key) in enumerate(items, 1):
            print(f"  {i:2d}) {label}")
        print("   0) Back")
        choice = _prompt("Select: ")
        if choice == "0" or choice.lower() == "q":
            return
        if not choice.isdigit() or not 1 <= int(choice) <= len(items):
            print("Invalid selection.")
            continue
        label, key = items[int(choice) - 1]
        _open(key, label, auth, principal)


def _logout(auth, reason: str = "logout") -> None:
    from education_system import switch as _switch
    activity_log.end_session(reason)
    try:
        auth.logout()
    except Exception:
        logger.exception("Logout failed")
    _switch.request_logout("cli")


def _main_menu(auth, principal: access.Principal) -> None:
    from education_system import switch as _switch
    from education_system.launcher.roles import is_superadmin
    from education_system.launcher.system_switch import pick_system_cli

    user = auth.current_user or {}
    show_system_switch = is_superadmin(user)
    categories = access.visible_categories(principal, menu.CATEGORIES)
    from education_system.systems.secondary.modules.portals.domain import portal_accounts
    try:
        has_children = portal_accounts.has_children(principal)
    except Exception:  # noqa: BLE001 - never stops the menu
        logger.exception("Parent link check failed")
        has_children = False
    while True:
        print(f"\n=== {SYSTEM_NAME} ===")
        print(f"Signed in: {principal.username or '?'} ({principal.role or 'no role'})")
        for i, (cat, _items) in enumerate(categories, 1):
            print(f"  {i:2d}) {cat}")
        print("   M) My Day (staff portal)")
        if has_children:
            print("   P) Parent portal (your children here)")
        print("   G) Switch to GUI")
        if show_system_switch:
            print("   S) Switch System")
        print("   L) Logout (return to login)")
        print("   Q) Shut down")
        choice = _prompt("Select: ").lower()
        if choice == "m":
            _open("staff_portal", "Staff Portal", auth, principal)
            continue
        if choice == "p" and has_children:
            from education_system.systems.secondary.modules.portals.cli import portal_cli
            if portal_cli.menu(auth, principal) == "logout":
                _logout(auth)
                return
            continue
        if choice == "g":
            activity_log.end_session("switch_to_gui")
            _switch.request_switch(SYSTEM_KEY, "gui")
            return
        if choice == "s" and show_system_switch:
            target = pick_system_cli(user, SYSTEM_KEY)
            if target:
                activity_log.end_session(f"switch_system:{target}")
                _switch.request_switch(target, "cli")
                return
            continue
        if choice == "l":
            _logout(auth)
            return
        if choice == "q":
            if _prompt(f"Shut down the {SYSTEM_NAME}? (y/N): ").lower() != "y":
                continue
            activity_log.end_session("shutdown")
            try:
                auth.logout()
            except Exception:
                logger.exception("Logout failed")
            _switch.request_exit()
            return
        if not choice.isdigit() or not 1 <= int(choice) <= len(categories):
            print("Invalid selection.")
            continue
        cat, items = categories[int(choice) - 1]
        activity_log.record("menu.category", target=cat)
        _submenu(cat, items, auth, principal)


def run_authenticated(auth, role: str | None = None) -> int:
    """Run the menu for an already-signed-in session (also the GUI → CLI path)."""
    principal = bootstrap.start_session(auth, role, "cli")
    if not principal.is_staff:
        if principal.is_student or principal.is_parent:
            return _run_portal(auth, principal)
        else:
            print(f"\n  The {SYSTEM_NAME} staff menu is only for school staff.")
            print(f"  Your account is signed in as '{principal.role or 'no role'}'.\n")
        logger.warning("Refusing secondary staff CLI for user=%s role=%s",
                       principal.username, principal.role)
        activity_log.end_session("refused_not_staff")
        return 0
    for rolled in bootstrap.roll_year_if_due(principal):
        print(f"\n  ★ {rolled.summary()}")
    with idle_session(lambda: _logout(auth, "idle_timeout")):
        _main_menu(auth, principal)
    return 0


def _run_portal(auth, principal: access.Principal) -> int:
    """Pupils and parents get their portal instead of the staff menu."""
    from education_system import switch as _switch
    from education_system.systems.secondary.modules.portals.cli import portal_cli
    outcome = "idle"   # stays so if the idle timeout ends the block (already logged out)
    with idle_session(lambda: _logout(auth, "idle_timeout")):
        outcome = portal_cli.menu(auth, principal)
    if outcome == "idle":
        return 0
    if outcome == "gui":
        activity_log.end_session("switch_to_gui")
        _switch.request_switch(SYSTEM_KEY, "gui")
    elif outcome == "quit":
        activity_log.end_session("shutdown")
        try:
            auth.logout()
        except Exception:
            logger.exception("Logout failed")
        _switch.request_exit()
    else:
        _logout(auth)
    return 0


def run(user_info=None, role=None, shared_auth=None) -> int:
    """Entry point from the unified launcher after the shared login."""
    bootstrap.require_shared_session(shared_auth, "cli")
    logger.info("Secondary CLI starting for user=%s role=%s",
                (shared_auth.current_user or {}).get("username"), role)
    return run_authenticated(shared_auth, role)


if __name__ == "__main__":
    print("Launch via: python -m education_system --secondary --cli")
    raise SystemExit(2)
