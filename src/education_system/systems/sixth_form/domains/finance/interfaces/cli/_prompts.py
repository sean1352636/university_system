"""Shared prompt helpers for the newer finance / GDPR terminal menus.

The older sixth-form CLIs each carry their own copy of these helpers;
the menus added for bursary payments, free meals, trip refunds, fee
rules, budgets and GDPR tooling share this one. Every handler is wrapped
with :func:`handler`, so a "cancel" or a validation error comes back to
the calling menu as a message rather than a traceback.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Iterable, Sequence

logger = logging.getLogger(__name__)

CURRENCY_SYMBOL = "£"


class Abort(Exception):
    """The user typed 'cancel' or pressed Ctrl-D/Ctrl-C at a prompt."""


def ask(prompt: str, *, default: str = "", required: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            raw = input(f"  {prompt}{suffix}: ")
        except (EOFError, KeyboardInterrupt):
            print()
            raise Abort from None
        s = raw.strip()
        if s.lower() == "cancel":
            raise Abort
        if not s and default:
            return default
        if s or not required:
            return s
        print("    Value is required (or 'cancel').")


def ask_int(prompt: str, *, default: int | None = None,
            required: bool = True) -> int | None:
    while True:
        raw = ask(prompt, default="" if default is None else str(default),
                  required=required)
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            print("    Enter a whole number.")


def ask_money(prompt: str, *, default: float | None = None,
              required: bool = True) -> float | None:
    while True:
        raw = ask(prompt, default="" if default is None else f"{default:.2f}",
                  required=required)
        if not raw:
            return None
        try:
            return round(float(raw.replace(CURRENCY_SYMBOL, "")
                               .replace(",", "")), 2)
        except ValueError:
            print("    Enter an amount, e.g. 125.50")


def yes_no(prompt: str, default: bool = False) -> bool:
    raw = ask(f"{prompt} (y/n)", default="y" if default else "n")
    return raw.lower() in ("y", "yes")


def pick(label: str, options: Sequence[str], *, default: str | None = None,
         allow_none: bool = False) -> str | None:
    print(f"\n  {label}:")
    if allow_none:
        print("      0) (none)")
    for i, opt in enumerate(options, 1):
        print(f"    {'*' if opt == default else ' '}{i:>2}) {opt}")
    while True:
        raw = ask(f"Pick #1..{len(options)}",
                  default=str(options.index(default) + 1)
                  if default in options else "")
        if allow_none and raw in ("0", ""):
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print(f"    Enter a number 1..{len(options)} (or 'cancel').")


def pick_student() -> str:
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    rows = students.list_students()
    if not rows:
        print("    No students.")
        raise Abort
    while True:
        raw = ask("Student ID (or part of a name, '?' to list)", required=True)
        if raw == "?":
            for s in rows:
                print(f"    {s.student_id:<10} {s.full_name}")
            continue
        exact = next((s for s in rows if s.student_id.lower() == raw.lower()),
                     None)
        if exact:
            return exact.student_id
        hits = [s for s in rows if raw.lower() in s.full_name.lower()]
        if len(hits) == 1:
            return hits[0].student_id
        if hits:
            for s in hits[:20]:
                print(f"    {s.student_id:<10} {s.full_name}")
            print("    Several match — type the ID.")
        else:
            print("    No matching student.")


def money(v: Any) -> str:
    try:
        x = float(v or 0)
    except (TypeError, ValueError):
        return "—"
    return f"{'-' if x < 0 else ''}{CURRENCY_SYMBOL}{abs(x):,.2f}"


def table(headers: Sequence[str], rows: Iterable[Sequence[Any]],
          *, empty: str = "(nothing to show)") -> None:
    rows = [["" if c is None else str(c) for c in r] for r in rows]
    if not rows:
        print(f"\n  {empty}")
        return
    widths = [max(len(h), *(len(r[i]) for r in rows))
              for i, h in enumerate(headers)]
    widths = [min(w, 40) for w in widths]
    print()
    print("  " + "  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  " + "-" * (sum(widths) + 2 * (len(widths) - 1)))
    for r in rows:
        print("  " + "  ".join(c[:w].ljust(w) for c, w in zip(r, widths)))


def pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def handler(fn: Callable[[], None]) -> Callable[[], None]:
    """Run a menu action; report cancels and validation errors."""
    @functools.wraps(fn)
    def run() -> None:
        try:
            fn()
        except Abort:
            print("\n  Cancelled.")
            return
        except PermissionError as exc:        # access.AccessDenied
            print(f"\n  ✗ {exc}")
        except ValueError as exc:             # every ValidationError here
            print(f"\n  ✗ {exc}")
        pause()
    return run


def menu(title: str, items: Sequence[tuple[str, Callable[[], None]]]) -> None:
    """A numbered submenu loop (0 = back)."""
    while True:
        print(f"\n── {title} ──")
        for i, (label, _fn) in enumerate(items, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not 1 <= int(choice) <= len(items):
            print("  Invalid selection.")
            continue
        try:
            items[int(choice) - 1][1]()
        except Exception as exc:  # noqa: BLE001 - keep the menu alive
            logger.exception("%s menu action failed", title)
            print(f"\n  ✗ Unexpected error: {exc}")
            pause()
