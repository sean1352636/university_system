"""Shared CLI helper functions used by all education subsystem CLIs.

Provides consistent menu display, user input, and sub-menu execution
so each system's cli_main.py only needs to define its menu structure.
"""

import logging

logger = logging.getLogger(__name__)


def print_header(title: str, width: int = 55):
    """Print a decorated section header."""
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


def print_menu(options: list[tuple[str, str]]):
    """Print a numbered menu.

    Parameters
    ----------
    options:
        List of ``(key, label)`` tuples.  If *key* is empty the line
        is printed as a section header.
    """
    for key, label in options:
        if not key:
            print(f"\n  {label}")
        else:
            print(f"  [{key}] {label}")
    print()


def get_choice(prompt: str = "Select option: ") -> str:
    """Prompt the user and return their stripped input."""
    return input(prompt).strip()


def run_submenu(auth, title, items):
    """Generic sub-menu loop.

    Parameters
    ----------
    auth:
        The auth object passed through to each menu action.
    title:
        Header text displayed at the top of the sub-menu.
    items:
        List of ``(key, label, callable)`` tuples.  The callable
        receives *auth* as its sole argument.
    """
    while True:
        print_header(title)
        options = [(k, lbl) for k, lbl, _ in items]
        options.append(("0", "Back"))
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        matched = False
        for k, _, func in items:
            if choice == k:
                func(auth)
                matched = True
                break
        if not matched:
            print("\n  Invalid option. Please try again.")


def login_prompt(auth) -> bool:
    """Show the shared login prompt.

    Returns ``True`` on success, ``False`` on failure.
    """
    from education_system.shared.cli.login_cli import cli_login_prompt
    result = cli_login_prompt(auth)
    if result is None:
        return False
    user_info, _ = result
    display = user_info.get("display_name", user_info.get("username", "User"))
    print(f"\n  Welcome, {display}!")
    logger.info("CLI login: user '%s'", user_info["username"])
    return True
