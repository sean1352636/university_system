"""Shared CLI helper functions used by all education subsystem CLIs.

Provides consistent menu display, user input, and sub-menu execution
so each system's cli_main.py only needs to define its menu structure.

Also provides an optional idle/inactivity timeout: any system that calls
:func:`enable_idle_timeout` after login will get auto-logged-out if the
user doesn't respond at the menu prompt within the configured window.
"""

import logging
import signal
import sys

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Idle timeout
# ---------------------------------------------------------------------------

class _IdleTimeoutSignal(Exception):
    """Internal exception raised by the SIGALRM handler when input times out."""


_idle_state = {
    "minutes": 0,
    "on_timeout": None,
    "fired": False,
}


def enable_idle_timeout(minutes: int, on_timeout=None) -> None:
    """Enable an idle/inactivity timeout for subsequent :func:`get_choice` calls.

    When the user does not respond to a menu prompt within *minutes* minutes,
    a warning is printed, *on_timeout* (if any) is invoked, and the process
    exits cleanly.

    On platforms without ``signal.SIGALRM`` (e.g. Windows) this is a no-op.
    """
    _idle_state["minutes"] = max(0, int(minutes))
    _idle_state["on_timeout"] = on_timeout
    _idle_state["fired"] = False


def disable_idle_timeout() -> None:
    """Cancel any active idle timeout."""
    _idle_state["minutes"] = 0
    _idle_state["on_timeout"] = None
    _idle_state["fired"] = False


def _idle_alarm_handler(_signum, _frame):
    raise _IdleTimeoutSignal()


def _input_with_idle_timeout(prompt: str) -> str:
    """Wrapper around :func:`input` that respects the idle timeout."""
    minutes = _idle_state["minutes"]
    if minutes <= 0 or _idle_state["fired"] or not hasattr(signal, "SIGALRM"):
        return input(prompt)

    old_handler = signal.signal(signal.SIGALRM, _idle_alarm_handler)
    signal.alarm(minutes * 60)
    try:
        return input(prompt)
    except _IdleTimeoutSignal:
        _idle_state["fired"] = True
        print(f"\n\n  ⚠ Logged out after {minutes} minutes of inactivity.")
        cb = _idle_state["on_timeout"]
        if cb:
            try:
                cb()
            except Exception:
                logger.exception("Idle-timeout callback raised")
        sys.exit(0)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def print_header(title: str, width: int = 55):
    """Print a decorated section header."""
    print(f"\n{'=' * width}")
    print(f"  {title}")  # lgtm[py/clear-text-logging-sensitive-data]
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
    """Prompt the user and return their stripped input.

    If an idle timeout has been enabled via :func:`enable_idle_timeout`,
    waiting longer than the configured window at this prompt will trigger
    an automatic logout.
    """
    return _input_with_idle_timeout(prompt).strip()


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
    print(f"\n  Welcome, {display}!")  # lgtm[py/clear-text-logging-sensitive-data]
    logger.info("CLI login: user '%s'", user_info["username"])  # lgtm[py/clear-text-logging-sensitive-data]
    return True
