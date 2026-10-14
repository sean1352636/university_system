"""Shared helpers for the Finance Operations CLI package.

Everything here is interface plumbing only (prompts, tables, the menu loop);
all business rules stay in ``finance.domain.operations_service``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from education_system.systems.university.infrastructure.i18n import get_text

logger = logging.getLogger(__name__)

MenuOption = tuple[str, Callable[[], None]]


def t(key: str, default: str, **kwargs: Any) -> str:
    """Translate a ``finance.operations.*`` key, falling back to the English default.

    ``get_text`` only formats placeholders in a *translated* string; the
    English default is returned verbatim, so it is formatted here.
    """
    text = get_text(f"finance.operations.{key}", default=default, **kwargs)
    if text == default and kwargs:
        try:
            return default.format(**kwargs)
        except (KeyError, IndexError):
            return default
    return text


@dataclass
class OpsContext:
    """What every sub-menu needs: the domain service and who is acting."""

    service: Any
    username: str


def current_username(auth) -> str:
    """Best-effort username from the CLI auth object (mirrors the GUI's ``_ops_user``)."""
    try:
        user = getattr(auth, "current_user", None)
        if isinstance(user, dict):
            return str(user.get("username") or user.get("email") or user.get("name") or "cli-user")
        if user is not None:
            name = getattr(user, "username", None) or getattr(user, "email", None)
            if name:
                return str(name)
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
    return "cli-user"


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #
def prompt_text(label: str, default: str = "", *, required: bool = False) -> str:
    """Read a line; blank returns ``default``. Loops while a required value is blank."""
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{label}{suffix}: ").strip() or default
        if value or not required:
            return value
        print(t("value_required", default="A value is required."))


def prompt_int(label: str, *, required: bool = True) -> Optional[int]:
    while True:
        raw = input(f"{label}: ").strip()
        if not raw:
            if not required:
                return None
            print(t("value_required", default="A value is required."))
            continue
        try:
            return int(raw)
        except ValueError:
            print(t("whole_number", default="Please enter a whole number."))


def prompt_float(label: str, *, required: bool = True, default: Optional[float] = None) -> Optional[float]:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{label}{suffix}: ").strip()
        if not raw:
            if default is not None:
                return default
            if not required:
                return None
            print(t("value_required", default="A value is required."))
            continue
        try:
            return float(raw)
        except ValueError:
            print(t("number", default="Please enter a number."))


def prompt_choice(label: str, choices: Sequence[str], default: str = "") -> str:
    """Read one of ``choices`` (case-insensitive); blank returns ``default`` if set."""
    options = " / ".join(choices)
    suffix = f" [{default}]" if default else ""
    while True:
        raw = input(f"{label} ({options}){suffix}: ").strip().lower() or default
        if raw in choices:
            return raw
        print(t("choose_one_of", default="Please choose one of: {options}", options=options))


def pause() -> None:
    try:
        input("\n" + t("press_enter", default="Press Enter to continue..."))
    except EOFError:
        print()


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def _cell(value: Any, width: int = 28) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:,.2f}"
    text = str(value)
    return text if len(text) <= width else text[: width - 1] + "…"


def print_table(rows: Sequence[dict], columns: Sequence[str], empty: str) -> None:
    """Print ``rows`` as a fixed-width table of ``columns`` (same columns as the GUI tabs)."""
    if not rows:
        print("\n" + empty)
        return
    headers = [c.replace("_", " ").title() for c in columns]
    cells = [[_cell(r.get(c)) for c in columns] for r in rows]
    widths = [max(len(h), *(len(row[i]) for row in cells)) for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print("\n" + line)
    print("-" * len(line))
    for row in cells:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    print(t("row_count", default="{count} row(s)", count=len(rows)))


def print_record(record: Optional[dict], title: str, not_found: str) -> None:
    if not record:
        print("\n" + not_found)
        return
    print(f"\n--- {title} ---")
    for key, value in record.items():
        print(f"  {key:<20}: {_cell(value, width=70) if value is not None else '-'}")


def money(value: Any) -> str:
    return f"£{float(value or 0):,.2f}"


def ok(message: str) -> None:
    print("\n✓ " + message)


def fail(message: str) -> None:
    print("\n✗ " + message)


# --------------------------------------------------------------------------- #
# Menu loop
# --------------------------------------------------------------------------- #
def _run_action(action: Callable[[], None]) -> None:
    try:
        action()
    except (KeyboardInterrupt, EOFError):
        print("\n" + t("cancelled", default="Cancelled."))
    except Exception as error:  # keep the menu resilient, like the GUI's error dialogs
        logger.debug("Finance operations action failed", exc_info=True)
        fail(str(error))


def run_menu(title: str, options: Sequence[MenuOption], *, pause_after: bool = True) -> None:
    """Numbered menu loop with ``0. Return``; each option is ``(label, callable)``.

    ``pause_after=False`` is for navigation menus whose options are themselves
    menus — pausing there would swallow the user's next keystroke.
    """
    return_label = t("return", default="0. Return")
    while True:
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60)
        for number, (label, _action) in enumerate(options, start=1):
            print(f"{number}. {label}")
        print(return_label)
        print("=" * 60)
        try:
            choice = input(t("enter_choice", default="Enter your choice: ")).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not 1 <= int(choice) <= len(options):
            print(t("invalid_choice", default="❌ Invalid choice."))
            continue
        _run_action(options[int(choice) - 1][1])
        if pause_after:
            pause()
