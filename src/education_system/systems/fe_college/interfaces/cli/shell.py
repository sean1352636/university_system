"""Terminal building blocks for the FE College CLI.

The same role as ``interfaces/gui/widgets.py``, for a terminal: headers,
tables, prompts and forms, so each command module is about its own job rather
than about column widths and input validation.

Two conventions run through everything here:

* every prompt returns a sentinel on EOF/Ctrl-C rather than raising, so a
  piped or interrupted session unwinds cleanly instead of dumping a traceback;
* nothing prints raw ``None`` — a missing value renders as an em dash, the
  same as the GUI.
"""

from __future__ import annotations

import shutil
import textwrap
from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

# Returned by the prompts when the user backs out (0, blank, Ctrl-C, EOF).
CANCEL = object()

DASH = "—"


def width() -> int:
    """Usable terminal width, clamped to something readable."""
    return max(72, min(shutil.get_terminal_size((100, 24)).columns, 160))


# ── Output ──────────────────────────────────────────────────────────────────

def header(title: str, subtitle: str = "") -> None:
    line = "=" * min(width(), 78)
    print()
    print(line)
    print(f"  {title}")
    if subtitle:
        for wrapped in textwrap.wrap(subtitle, width=min(width(), 78) - 4):
            print(f"  {wrapped}")
    print(line)


def section(title: str) -> None:
    print()
    print(f"── {title} " + "─" * max(0, min(width(), 78) - len(title) - 4))


def note(message: str) -> None:
    for wrapped in textwrap.wrap(message, width=min(width(), 78)):
        print(f"  {wrapped}")


def warn(message: str) -> None:
    print(f"  ! {message}")


def error(message: str) -> None:
    print(f"  ✗ {message}")


def success(message: str) -> None:
    print(f"  ✓ {message}")


def blank() -> None:
    print()


def fmt(value: Any) -> str:
    """Render a cell value: never a bare ``None``, never a raw bool."""
    if value is None or value == "":
        return DASH
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def pct(value: float | None) -> str:
    return f"{value:.1f}%" if value is not None else DASH


def money(value: float | None) -> str:
    return f"£{value:,.2f}" if value is not None else DASH


def table(columns: Sequence[tuple[str, str]], rows: Sequence[dict],
          *, empty: str = "Nothing to show.", limit: int | None = None) -> None:
    """Print rows as an aligned table.

    ``columns`` is ``(key, heading)``. Widths are measured from the data so a
    column of short codes doesn't get the same space as one of course titles,
    then scaled down if the total would overflow the terminal.
    """
    if not rows:
        note(empty)
        return

    shown = rows[:limit] if limit else rows
    widths = {}
    for key, heading in columns:
        longest = max((len(fmt(r.get(key))) for r in shown), default=0)
        widths[key] = max(len(heading), longest)

    # Scale back the widest columns if the line would wrap.
    available = width() - 2 - 2 * (len(columns) - 1)
    while sum(widths.values()) > available and max(widths.values()) > 8:
        widest = max(widths, key=lambda k: widths[k])
        widths[widest] -= 1

    def render(values: Sequence[str]) -> str:
        return "  ".join(
            v[:widths[key]].ljust(widths[key])
            for (key, _h), v in zip(columns, values)
        ).rstrip()

    print()
    print("  " + render([h for _k, h in columns]))
    print("  " + "  ".join("-" * widths[k] for k, _h in columns))
    for row in shown:
        print("  " + render([fmt(row.get(k)) for k, _h in columns]))
    if limit and len(rows) > limit:
        print(f"  … and {len(rows) - limit} more")
    print(f"  ({len(rows)} row{'' if len(rows) == 1 else 's'})")


def key_values(pairs: Sequence[tuple[str, Any]], indent: str = "  ") -> None:
    """Print aligned label/value lines."""
    if not pairs:
        return
    label_width = max(len(label) for label, _v in pairs)
    for label, value in pairs:
        print(f"{indent}{label.ljust(label_width)} : {fmt(value)}")


def bullet_list(items: Sequence[str], empty: str = "None") -> None:
    if not items:
        note(empty)
        return
    for item in items:
        for i, wrapped in enumerate(
            textwrap.wrap(item, width=min(width(), 78) - 4) or [""]
        ):
            print(f"  {'•' if i == 0 else ' '} {wrapped}")


# ── Input ───────────────────────────────────────────────────────────────────

def prompt(message: str, default: str = "") -> Any:
    """Read a line. Returns CANCEL on EOF/Ctrl-C."""
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {message}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return CANCEL
    return raw or default


def confirm(message: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = prompt(f"{message} ({hint})")
    if answer is CANCEL:
        return False
    if not answer:
        return default
    return answer.strip().lower().startswith("y")


def pause() -> None:
    try:
        input("\n  Press Enter to continue… ")
    except (EOFError, KeyboardInterrupt):
        print()


def choose(message: str, options: Sequence[str], *,
           allow_blank: bool = False) -> Any:
    """Numbered picker. Returns the chosen string, or CANCEL."""
    if not options:
        note("There is nothing to choose from.")
        return CANCEL
    print()
    for i, option in enumerate(options, 1):
        print(f"   {i:2d}) {option}")
    if allow_blank:
        print("    -) leave blank")
    print("    0) cancel")
    while True:
        raw = prompt(message)
        if raw is CANCEL or raw == "0":
            return CANCEL
        if allow_blank and raw == "-":
            return ""
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        error(f"Enter a number between 1 and {len(options)}.")


def choose_object(message: str, items: Sequence[Any],
                  label: Callable[[Any], str]) -> Any:
    """Numbered picker over objects, returning the object itself."""
    if not items:
        note("There is nothing to choose from.")
        return CANCEL
    chosen = choose(message, [label(item) for item in items])
    if chosen is CANCEL:
        return CANCEL
    return items[[label(i) for i in items].index(chosen)]


def ask_int(message: str, default: int | None = None) -> Any:
    while True:
        raw = prompt(message, "" if default is None else str(default))
        if raw is CANCEL:
            return CANCEL
        if not raw:
            return default if default is not None else 0
        try:
            return int(raw)
        except ValueError:
            error("Enter a whole number.")


def ask_float(message: str, default: float | None = None) -> Any:
    while True:
        raw = prompt(message, "" if default is None else str(default))
        if raw is CANCEL:
            return CANCEL
        if not raw:
            return default if default is not None else 0.0
        try:
            return float(raw)
        except ValueError:
            error("Enter a number.")


def ask_date(message: str, default: date | None = None,
             allow_blank: bool = True) -> Any:
    """Read an ISO date. Accepts 'today' as a shorthand."""
    hint = default.isoformat() if default else ("blank" if allow_blank else "")
    while True:
        raw = prompt(f"{message} (YYYY-MM-DD)", hint)
        if raw is CANCEL:
            return CANCEL
        if not raw or raw == "blank":
            if allow_blank:
                return default
            error("A date is required.")
            continue
        if raw.lower() == "today":
            return date.today()
        try:
            return date.fromisoformat(raw)
        except ValueError:
            error("Enter the date as YYYY-MM-DD, or 'today'.")


def ask_bool(message: str, default: bool = False) -> Any:
    answer = prompt(f"{message} (y/n)", "y" if default else "n")
    if answer is CANCEL:
        return CANCEL
    return answer.strip().lower().startswith("y")


def form(title: str, fields: Sequence[tuple], initial: dict | None = None) -> Any:
    """Prompt through a list of fields, returning a dict (or CANCEL).

    Field specs match the GUI's :class:`FormDialog` — ``(key, label, kind,
    options)`` with kinds ``text``, ``choice``, ``int``, ``float``, ``date``,
    ``bool`` — so a screen and its command describe the same form once.
    """
    initial = initial or {}
    section(title)
    note("Enter 0 at any prompt to cancel.")
    collected: dict = {}
    for spec in fields:
        key, label, kind = spec[0], spec[1], spec[2]
        options = spec[3] if len(spec) > 3 else None
        current = initial.get(key)

        if kind == "section":
            section(label)
            continue
        if kind == "choice":
            value = choose(label, list(options or []), allow_blank=True)
        elif kind == "int":
            value = ask_int(label, current if isinstance(current, int) else None)
        elif kind == "float":
            value = ask_float(label, current if isinstance(current, (int, float)) else None)
        elif kind == "date":
            value = ask_date(label, current if isinstance(current, date) else None)
        elif kind == "bool":
            value = ask_bool(label, bool(current))
        else:
            value = prompt(label, "" if current is None else str(current))

        if value is CANCEL:
            note("Cancelled.")
            return CANCEL
        collected[key] = value
    return collected


def run_action(action: Callable[[], None], label: str) -> None:
    """Run a command, turning any failure into a message rather than a crash.

    One broken command must not drop the user out of the shell — they may be
    mid-way through something else.
    """
    import logging

    try:
        action()
    except KeyboardInterrupt:
        print()
        note("Cancelled.")
    except Exception as exc:  # noqa: BLE001 - the CLI is the last line of defence
        logging.getLogger(__name__).exception("FE College CLI action failed: %s", label)
        error(f"{label} failed: {exc}")
        note("The details are in the application log.")


__all__ = [
    "CANCEL",
    "DASH",
    "ask_bool",
    "ask_date",
    "ask_float",
    "ask_int",
    "blank",
    "bullet_list",
    "choose",
    "choose_object",
    "confirm",
    "error",
    "fmt",
    "form",
    "header",
    "key_values",
    "money",
    "note",
    "pause",
    "pct",
    "prompt",
    "run_action",
    "section",
    "success",
    "table",
    "warn",
    "width",
]
