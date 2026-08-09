"""The apprenticeships CLI shell.

Mirrors the GUI: one signed-in actor, a role-derived menu tree, and a
loop that hands control back to the launcher rather than calling
``sys.exit`` — switching interface, switching system and logging out are
all requests the launcher's dispatcher consumes.
"""

from __future__ import annotations

import importlib
import logging

from education_system.platform import branding
from education_system.systems.apprenticeships import SYSTEM_NAME, VERSION
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.menus import menu_for
from education_system.systems.apprenticeships.services import preferences
from education_system.systems.apprenticeships.services.access import Actor, resolve

logger = logging.getLogger(__name__)

_COMMAND_PACKAGE = "education_system.systems.apprenticeships.interfaces.cli.commands"


def _dispatch(target: str, actor: Actor) -> None:
    """Run ``module:function`` from the commands package.

    An import or attribute error here is a wiring mistake, not something
    the user can fix, so it is logged with a traceback and reported as a
    single line rather than dumped to the terminal.
    """
    module_name, _, function_name = target.partition(":")
    try:
        module = importlib.import_module(f"{_COMMAND_PACKAGE}.{module_name}")
        handler = getattr(module, function_name)
    except (ImportError, AttributeError) as exc:
        logger.exception("Could not load CLI command %s", target)
        prompts.fail(f"This command is unavailable ({exc}).")
        prompts.pause()
        return
    prompts.run_action(lambda: handler(actor))


def _category_menu(category: str, items: list[tuple[str, str]], actor: Actor) -> None:
    while True:
        print(f"\n── {category} ──")
        for index, (label, _) in enumerate(items, 1):
            print(f"  {index:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
            print("  Invalid selection.")
            continue
        _dispatch(items[int(choice) - 1][1], actor)


def _main_menu(auth, actor: Actor) -> None:
    from education_system import switch
    from education_system.launcher.roles import is_superadmin
    from education_system.launcher.system_switch import pick_system_cli

    user = getattr(auth, "current_user", None) or {}
    show_switch = is_superadmin(user)
    # Never empty: menu_for always appends the shared System group, so an
    # unrecognised role lands on something it can read rather than a
    # dead end.
    tree = menu_for(actor.role)

    while True:
        print(f"\n=== {SYSTEM_NAME} ===")
        print(f"Signed in: {actor.name} — {actor.role_label}")
        for index, (category, _) in enumerate(tree, 1):
            print(f"  {index:2d}) {category}")
        print("   G) Switch to GUI")
        if show_switch:
            print("   S) Switch System")
        print("   L) Logout (return to login)")
        print("   Q) Shut down")

        try:
            choice = input("Select: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            choice = "q"

        if choice == "g":
            switch.request_switch("apprenticeships", "gui")
            return
        if choice == "s" and show_switch:
            target = pick_system_cli(user, "apprenticeships")
            if target:
                switch.request_switch(target, "cli")
                return
            continue
        if choice == "l":
            _logout(auth)
            switch.request_logout("cli")
            return
        if choice == "q":
            if not prompts.ask_yes_no(f"Shut down the {SYSTEM_NAME}?"):
                continue
            _logout(auth)
            switch.request_exit()
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(tree)):
            print("Invalid selection.")
            continue

        category, items = tree[int(choice) - 1]
        _category_menu(category, items, actor)


def _logout(auth) -> None:
    try:
        auth.logout()
    except Exception:
        logger.debug("Logout call failed", exc_info=True)


def run_authenticated(auth, actor: Actor | None = None) -> int:
    """Run the shell for an already-resolved session."""
    resolved = actor or resolve(getattr(auth, "current_user", None))
    _main_menu(auth, resolved)
    return 0


def run(user_info=None, role=None, shared_auth=None) -> int:
    """Launch the CLI for an already-authenticated session.

    Called by the launcher after the universal login. There is no
    per-system login — an unauthenticated call is a caller bug.
    """
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        logger.error("Apprenticeships CLI invoked without a shared_auth session")
        raise RuntimeError(
            "The apprenticeships CLI must be launched via run.py — "
            "no standalone login is available."
        )
    branding.set_system_name(SYSTEM_NAME)
    actor = resolve(user_info or shared_auth.current_user, role)
    # Loaded once here rather than per table: ``prompts.cell`` and
    # ``prompts.table`` read them thousands of times a screen and have no
    # actor to hand.
    preferences.activate(actor.username)
    logger.info(
        "Apprenticeships CLI starting for user=%s role=%s (v%s)",
        actor.username, actor.role, VERSION,
    )
    return run_authenticated(shared_auth, actor)


if __name__ == "__main__":
    print("Launch via: python run.py --apprenticeships --cli")
    raise SystemExit(2)
