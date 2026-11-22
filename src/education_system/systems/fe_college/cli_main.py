"""CLI entry point for the FE College System.

Mirrors the GUI: the menu is built from the signed-in user's view (admin, staff
or learner), and every action goes through the same
:class:`~education_system.systems.fe_college.services.session.CollegeSession`
the windows use — so the two interfaces cannot disagree about what a user may
do or what a number means.

Top-level keys follow the convention the other systems' CLIs use: G to switch
to the GUI, S to switch system (superadmins), L to log out, Q to shut down.
"""

from __future__ import annotations

import logging

from education_system.platform.delivery.cli.cli_helpers import idle_session
from education_system.systems.fe_college import SYSTEM_NAME, SYSTEM_SLUG
from education_system.systems.fe_college.config import COLLEGE_NAME
from education_system.systems.fe_college.interfaces.cli import menus
from education_system.systems.fe_college.interfaces.cli import shell as sh
from education_system.systems.fe_college.services.session import CollegeSession

logger = logging.getLogger(__name__)


def _run_command(ctl: CollegeSession, label: str, path: str) -> None:
    """Resolve and run one menu item."""
    command = menus.resolve(path)
    if command is None:
        sh.error(f"'{label}' is unavailable — see the application log.")
        sh.pause()
        return
    sh.run_action(lambda: command(ctl), label)
    sh.pause()


def _submenu(ctl: CollegeSession, section: str,
             items: list[tuple[str, str]]) -> None:
    while True:
        sh.section(section)
        for i, (label, _path) in enumerate(items, 1):
            print(f"   {i:2d}) {label}")
        print("    0) Back")
        choice = sh.prompt("Select")
        if choice is sh.CANCEL or choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
            sh.error("Invalid selection.")
            continue
        label, path = items[int(choice) - 1]
        logger.debug("FE College CLI dispatch: %s / %s -> %s", section, label, path)
        _run_command(ctl, label, path)


def _search(ctl: CollegeSession) -> None:
    """Jump straight to a command by name."""
    query = sh.prompt("Search commands")
    if query is sh.CANCEL or not query:
        return
    matches = [
        (label, path) for label, path in menus.all_commands(ctl.view)
        if query.lower() in label.lower()
    ]
    if not matches:
        sh.note("Nothing matches.")
        return
    if len(matches) == 1:
        _run_command(ctl, *matches[0])
        return
    chosen = sh.choose("Which one?", [label for label, _p in matches])
    if chosen is sh.CANCEL:
        return
    _run_command(ctl, *matches[[m[0] for m in matches].index(chosen)])


def _logout(auth) -> None:
    """Sign out and return to login: the L key and the idle timeout both end here."""
    from education_system import switch as _switch
    try:
        auth.logout()
    except Exception:
        logger.debug("Logout raised; returning to login anyway", exc_info=True)
    _switch.request_logout("cli")


def _main_menu(ctl: CollegeSession, auth) -> None:
    from education_system import switch as _switch
    from education_system.launcher.roles import is_superadmin
    from education_system.launcher.system_switch import pick_system_cli

    user = ctl.session_user
    show_switch = is_superadmin(user)
    sections = menus.sections(ctl.view)

    while True:
        sh.header(f"{SYSTEM_NAME} — {COLLEGE_NAME}", ctl.subtitle())
        if not (ctl.identity.staff or ctl.identity.student):
            sh.warn(
                "This account has no matching college record, so most screens "
                "will be empty. Use Account → Link a college record."
            )
        for i, (section, _items) in enumerate(sections, 1):
            print(f"   {i:2d}) {section}")
        print("    /) Search commands")
        print("    G) Switch to the GUI")
        if show_switch:
            print("    S) Switch system")
        print("    L) Logout")
        print("    Q) Shut down")

        choice = sh.prompt("Select")
        if choice is sh.CANCEL:
            choice = "q"
        key = choice.strip().lower()

        if key == "/":
            _search(ctl)
            continue
        if key == "g":
            _switch.request_switch(SYSTEM_SLUG, "gui")
            return
        if key == "s" and show_switch:
            target = pick_system_cli(user, SYSTEM_SLUG)
            if target:
                _switch.request_switch(target, "cli")
                return
            continue
        if key == "l":
            _logout(auth)
            return
        if key == "q":
            if not sh.confirm(f"Shut down the {SYSTEM_NAME}?"):
                continue
            try:
                auth.logout()
            except Exception:
                logger.debug("Logout raised during shutdown", exc_info=True)
            _switch.request_exit()
            return

        if not key.isdigit() or not (1 <= int(key) <= len(sections)):
            sh.error("Invalid selection.")
            continue
        section, items = sections[int(key) - 1]
        _submenu(ctl, section, items)


def run_authenticated(auth, user_info=None, role: str = "student") -> int:
    """Run the shell for an already-authenticated session."""
    ctl = CollegeSession(user_info or getattr(auth, "current_user", {}), role)
    with idle_session(lambda: _logout(auth)):
        _main_menu(ctl, auth)
    return 0


def run(user_info=None, role=None, shared_auth=None) -> int:
    """Launcher entry point for the FE College CLI."""
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        logger.error("FE College CLI invoked without a shared_auth session")
        raise RuntimeError(
            "The FE College CLI must be launched via python -m education_system — "
            "no standalone login is available."
        )
    current = shared_auth.current_user or {}
    logger.info("FE College CLI starting for user=%s role=%s",
                current.get("username"), role)

    from education_system.systems.fe_college.infrastructure.persistence import schema
    schema.bootstrap()

    resolved_role = role
    if not resolved_role:
        for entry in (user_info or current).get("systems", []):
            if entry.get("system_key") == SYSTEM_SLUG:
                resolved_role = entry.get("role")
                break
    result = run_authenticated(shared_auth, user_info or current,
                               resolved_role or "student")
    logger.info("FE College CLI exited for user=%s", current.get("username"))
    return result


if __name__ == "__main__":
    print("Launch via: python -m education_system --fecollege --cli")
    raise SystemExit(2)
