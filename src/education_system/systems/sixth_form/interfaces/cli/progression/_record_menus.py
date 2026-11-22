"""Shared terminal helpers for the progression record menus.

The CLI twin of ``interfaces/gui/progression/_record_tabs.py``. The same
``(key, label, kind, choices)`` field specs drive a prompt-per-field form
here, so a screen and its menu ask for the same things.

Typing ``cancel`` (or Ctrl-D / Ctrl-C) at any prompt raises
:class:`UserAbort`; :func:`run_menu` catches it and returns to the menu.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Iterable, Sequence

logger = logging.getLogger(__name__)

FieldSpec = tuple


class UserAbort(Exception):
    """The user cancelled the current flow."""


def ask(prompt: str, *, default: str = "", required: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            raw = input(f"  {prompt}{suffix}: ")
        except (EOFError, KeyboardInterrupt):
            print()
            raise UserAbort from None
        value = raw.strip()
        if value.lower() == "cancel":
            raise UserAbort
        if not value:
            value = default
        if required and not value:
            print("    A value is required (or 'cancel').")
            continue
        return value


def ask_int(prompt: str, *, default: int | None = None) -> int | None:
    while True:
        raw = ask(prompt, default="" if default is None else str(default))
        if not raw:
            return None
        if raw.lstrip("-").isdigit():
            return int(raw)
        print("    Enter a whole number.")


def ask_yes(prompt: str, *, default: bool = False) -> bool:
    raw = ask(f"{prompt} (y/n)", default="y" if default else "n").lower()
    return raw in ("y", "yes", "1", "true")


def choose(label: str, options: Sequence[str], *,
           default: str | None = None, allow_blank: bool = False) -> str:
    opts = [str(o) for o in options]
    print(f"\n  {label}:")
    if allow_blank:
        print("     0) (none)")
    for i, opt in enumerate(opts, 1):
        mark = "*" if opt == default else " "
        print(f"    {mark}{i:>2}) {opt}")
    while True:
        raw = ask("Pick", default=default or "")
        if default and raw == default:
            return default
        if allow_blank and raw in ("0", ""):
            return ""
        if raw.isdigit() and 1 <= int(raw) <= len(opts):
            return opts[int(raw) - 1]
        if raw in opts:
            return raw
        print(f"    Enter 1..{len(opts)} (or 'cancel').")


def ask_long(label: str, *, current: str | None = None) -> str:
    """Multi-line entry ended by a line containing only END. An empty
    first line keeps *current*."""
    print(f"\n  {label}")
    if current:
        print("  Current text:")
        for line in current.splitlines():
            print(f"    | {line}")
        print("  (press Enter on the first line to keep it)")
    print("  Type or paste the text; finish with END on its own line.")
    lines: list[str] = []
    while True:
        try:
            line = input("  > " if not lines else "    ")
        except (EOFError, KeyboardInterrupt):
            print()
            raise UserAbort from None
        if not lines and line.strip().lower() == "cancel":
            raise UserAbort
        if not lines and not line.strip() and current is not None:
            return current
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _choices(spec: FieldSpec) -> list[str]:
    raw = spec[3] if len(spec) > 3 else ()
    if callable(raw):
        raw = raw()
    return [str(c) for c in (raw or ())]


def form(fields: Sequence[FieldSpec],
         initial: dict[str, Any] | None = None) -> dict[str, Any]:
    """Prompt for each field; Enter keeps the current value."""
    initial = initial or {}
    out: dict[str, Any] = {}
    for spec in fields:
        key, label, kind = spec[0], spec[1], spec[2]
        current = initial.get(key)
        if kind == "readonly":
            print(f"  {label}: {current if current is not None else '—'}")
            continue
        if kind == "bool":
            out[key] = ask_yes(label, default=bool(current) and
                               str(current).lower() not in ("0", "no", "false"))
        elif kind == "choice":
            opts = _choices(spec)
            out[key] = choose(label, opts,
                              default=str(current) if current else None,
                              allow_blank=True)
        elif kind == "longtext":
            out[key] = ask_long(label, current=None if current is None else str(current))
        else:
            hint = " (YYYY-MM-DD)" if kind == "date" else ""
            out[key] = ask(f"{label}{hint}",
                           default="" if current is None else str(current))
    return out


def print_table(rows: Iterable[dict[str, Any]],
                columns: Sequence[tuple[str, str, int]]) -> int:
    """Print dict rows under fixed-width columns; returns the row count."""
    rows = list(rows)
    header = "  " + " ".join(f"{title:<{width}}" for _k, title, width in columns)
    print(header)
    print("  " + "─" * (len(header) - 2))
    for row in rows:
        cells = []
        for key, _title, width in columns:
            value = row.get(key)
            text = "" if value is None else (
                ("Yes" if value else "No") if isinstance(value, bool) else str(value))
            cells.append(f"{text[:width]:<{width}}")
        print("  " + " ".join(cells))
    if not rows:
        print("  (none)")
    print(f"\n  {len(rows)} row(s)")
    return len(rows)


def pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        print()


def pick_student() -> str:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    while True:
        raw = ask("Student ID (or part of a name)", required=True)
        if _students.get_student(raw):
            return raw
        hits = _students.search_students(raw)
        if not hits:
            print("    No match.")
            continue
        if len(hits) == 1:
            print(f"    → {hits[0].student_id} {hits[0].full_name}")
            return hits[0].student_id
        label = choose("Which student", [f"{s.student_id} — {s.full_name}"
                                          for s in hits[:20]])
        return label.split(" — ")[0]


def pick_row(rows: Sequence[dict[str, Any]], key: str, label: str) -> dict[str, Any] | None:
    """Ask for a row by its key value; None when there are no rows."""
    if not rows:
        print("  Nothing to pick from.")
        return None
    by_key = {str(r[key]): r for r in rows}
    while True:
        raw = ask(label, required=True)
        if raw in by_key:
            return by_key[raw]
        print("    Not one of the listed ids.")


def guarded(handler: Callable[[], None]) -> Callable[[], None]:
    """Wrap a handler for an existing menu loop that does not know about
    :class:`UserAbort` or validation errors, so those read as "Cancelled"
    and a plain message rather than "Unexpected error"."""
    def run() -> None:
        try:
            handler()
        except UserAbort:
            print("\n  Cancelled.")
        except ValueError as exc:
            print(f"\n  ✗ {exc}")
            pause()
    run.__name__ = getattr(handler, "__name__", "handler")
    run.__doc__ = handler.__doc__
    return run


def run_menu(title: str,
             items: Sequence[tuple[str, Callable[[], None]]]) -> None:
    """Numbered menu loop with a shared error boundary."""
    while True:
        print(f"\n── {title} ──")
        for i, (label, _h) in enumerate(items, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            raw = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if raw == "0":
            return
        if not raw.isdigit() or not (1 <= int(raw) <= len(items)):
            print("  Invalid selection.")
            continue
        _label, handler = items[int(raw) - 1]
        try:
            handler()
        except UserAbort:
            print("\n  Cancelled.")
        except ValueError as exc:
            print(f"\n  ✗ {exc}")
            pause()
        except Exception as exc:
            logger.exception("%s handler crashed", title)
            print(f"\n  ✗ Unexpected error: {exc}")
            pause()


__all__ = ["UserAbort", "ask", "ask_long", "ask_int", "ask_yes", "choose", "form",
           "print_table", "pause", "pick_student", "pick_row", "guarded",
           "run_menu"]
