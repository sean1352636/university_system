"""Terminal input and output helpers for the apprenticeships CLI.

The rest of the platform copies this quartet of helpers into every
``*_cli.py``. With eleven command modules here that would be eleven
copies to keep in step, so this system keeps one.

Two conventions the command modules rely on: typing ``cancel`` at any
prompt aborts the whole flow by raising :class:`Abort`, and end-of-file
does the same — which means these commands degrade sensibly when stdin
is a pipe rather than a person.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.services import preferences

logger = logging.getLogger(__name__)

EMPTY = config.EMPTY_CELL

TICK = "✓"
CROSS = "✗"


class Abort(Exception):
    """The user cancelled the current flow."""


# ═════════════════════════════════════════════════════════════════════
# Input
# ═════════════════════════════════════════════════════════════════════

def ask(
    prompt: str,
    *,
    default: str = "",
    required: bool = False,
) -> str:
    """Read a line. ``cancel`` aborts, blank takes the default."""
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            raw = input(f"  {prompt}{suffix}: ")
        except (EOFError, KeyboardInterrupt):
            print()
            raise Abort from None
        text = raw.strip()
        if text.lower() == "cancel":
            raise Abort
        if not text:
            if default:
                return default
            if required:
                print("    This is required (or type 'cancel').")
                continue
            return ""
        return text


def ask_int(prompt: str, *, default: int | None = None, required: bool = False) -> int | None:
    while True:
        raw = ask(prompt, default="" if default is None else str(default), required=required)
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            print("    Enter a whole number.")


def ask_float(prompt: str, *, default: float | None = None, required: bool = False) -> float | None:
    while True:
        raw = ask(prompt, default="" if default is None else str(default), required=required)
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            print("    Enter a number.")


def ask_yes_no(prompt: str, *, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = ask(f"{prompt} ({hint})")
    if not raw:
        return default
    return raw.lower().startswith("y")


def choose(
    label: str,
    options: Sequence[Any],
    *,
    render: Callable[[Any], str] = str,
    allow_blank: bool = False,
) -> Any:
    """Pick one item from a numbered list."""
    if not options:
        print(f"\n  (no {label.lower()} available)")
        if allow_blank:
            return None
        raise Abort
    print(f"\n  {label}:")
    for index, option in enumerate(options, 1):
        print(f"    {index:>3}) {render(option)}")
    if allow_blank:
        print("      0) None")
    while True:
        raw = ask(f"Select 1-{len(options)}")
        if not raw and allow_blank:
            return None
        if raw == "0" and allow_blank:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("    Invalid selection.")


def choose_value(label: str, values: Sequence[str], *, default: str | None = None) -> str:
    """Pick one string from a closed set such as a status list."""
    print(f"\n  {label}:")
    for index, value in enumerate(values, 1):
        marker = " *" if value == default else "  "
        print(f"   {marker}{index:>2}) {value}")
    while True:
        raw = ask(f"Select 1-{len(values)}", default=default or "")
        if raw in values:
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(values):
            return values[int(raw) - 1]
        print("    Invalid selection.")


def pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


# ═════════════════════════════════════════════════════════════════════
# Output
# ═════════════════════════════════════════════════════════════════════

def title(text: str) -> None:
    print(f"\n═══ {text} ═══")


def rule(width: int = 78) -> None:
    print("  " + "-" * width)


def ok(message: str) -> None:
    print(f"\n  {TICK} {message}")


def fail(message: str) -> None:
    print(f"\n  {CROSS} {message}")


def note(message: str) -> None:
    print(f"  {message}")


def cell(value: Any) -> str:
    """Render a value for a table cell.

    The one place every CLI cell passes through, which is why the date
    preference is applied here rather than at each call site — and why
    ``format_date`` has to leave anything that is not an ISO date
    exactly as it found it.
    """
    if value is None or value == "":
        return EMPTY
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:,.1f}"
    return str(preferences.format_date(value))


def table(
    columns: Sequence[tuple[str, int]],
    rows: Sequence[Any],
    to_values: Callable[[Any], Sequence[Any]],
    *,
    noun: str = "row",
    empty: str | None = None,
) -> None:
    """Print a fixed-width table.

    *columns* are ``(heading, width)``; a negative width right-aligns
    the column, which is what numbers want. Values longer than their
    column are truncated rather than wrapped — a table that keeps its
    shape is easier to scan than one that preserves every character.

    Long tables stop at the user's rows-per-table preference and say how
    many were held back. Scrolling a thousand rows off the top of a
    terminal loses them; a footer that names the number does not.
    """
    if not rows:
        print(f"\n  ({empty or f'no {noun}s'})")
        return

    limit = preferences.rows_per_page()
    shown = rows[:limit] if 0 < limit < len(rows) else rows

    header = "  " + "  ".join(
        f"{name[:abs(width)]:>{abs(width)}}" if width < 0 else f"{name[:width]:<{width}}"
        for name, width in columns
    )
    print()
    print(header)
    rule(len(header))
    for row in shown:
        values = to_values(row)
        line = "  " + "  ".join(
            f"{cell(value)[:abs(width)]:>{abs(width)}}"
            if width < 0
            else f"{cell(value)[:width]:<{width}}"
            for (_, width), value in zip(columns, values, strict=False)
        )
        print(line)
    rule(len(header))
    plural = noun if len(rows) == 1 else f"{noun}s"
    if len(shown) < len(rows):
        print(f"  Showing {len(shown)} of {len(rows)} {plural} "
              f"— raise 'Rows per table' in Settings to see more.")
    else:
        print(f"  {len(rows)} {plural}.")


def details(pairs: Sequence[tuple[str, Any]]) -> None:
    """Print a label/value block for a single record."""
    if not pairs:
        return
    width = max(len(label) for label, _ in pairs)
    print()
    for label, value in pairs:
        print(f"  {label:<{width}}  {cell(value)}")


def bar(percent: float, *, width: int = 24) -> str:
    """A text progress bar, for the off-the-job and portfolio screens."""
    filled = int(max(0.0, min(100.0, percent)) / 100 * width)
    return "[" + "#" * filled + "." * (width - filled) + f"] {percent:5.1f}%"


def money(amount: float | None) -> str:
    if amount is None:
        return EMPTY
    return f"{config.CURRENCY_SYMBOL}{amount:,.2f}"


# ═════════════════════════════════════════════════════════════════════
# Menus
# ═════════════════════════════════════════════════════════════════════

def run_menu(heading: str, entries: Sequence[tuple[str, Callable[[], None]]]) -> None:
    """A numbered submenu loop.

    Each handler runs inside the loop's own error handling: a crash in
    one command prints and returns to the menu rather than dropping the
    user out of the whole CLI.
    """
    while True:
        print(f"\n── {heading} ──")
        for index, (label, _) in enumerate(entries, 1):
            print(f"  {index:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(entries)):
            print("  Invalid selection.")
            continue
        _, handler = entries[int(choice) - 1]
        run_action(handler)


def run_action(handler: Callable[[], None]) -> None:
    """Run one command, turning refusals into readable messages."""
    from education_system.systems.apprenticeships.domain.apprentices.models import (
        ValidationError,
    )
    from education_system.systems.apprenticeships.services.access import PermissionDenied

    try:
        handler()
    except Abort:
        print("\n  Cancelled.")
    except PermissionDenied as exc:
        fail(str(exc))
        pause()
    except ValidationError as exc:
        fail(str(exc))
        pause()
    except Exception as exc:
        logger.exception("Apprenticeships CLI command failed")
        fail(f"Unexpected error: {exc}")
        pause()
