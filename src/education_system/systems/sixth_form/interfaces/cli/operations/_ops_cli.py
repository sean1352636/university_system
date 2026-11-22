"""Shared terminal helpers for the small operations menus (lockers,
parking, catering, ID cards) — same prompts and menu loop as the
visitors CLI."""

from __future__ import annotations

import logging
from typing import Any, Callable, Sequence

logger = logging.getLogger(__name__)


class UserAbort(Exception):
    pass


def ask(prompt: str, *, default: str = "", required: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            raw = input(f"  {prompt}{suffix}: ")
        except (EOFError, KeyboardInterrupt):
            print()
            raise UserAbort
        s = raw.strip()
        if s.lower() == "cancel":
            raise UserAbort
        if not s and default:
            return default
        if not s and required:
            print("    Value is required.")
            continue
        return s


def ask_int(prompt: str, *, default: int | None = None) -> int:
    while True:
        s = ask(prompt, default="" if default is None else str(default),
                required=default is None)
        try:
            return int(s)
        except ValueError:
            print("    Enter a whole number.")


def yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = ask(f"{prompt} (y/n)", default="y" if default else "n").lower()
    return raw in ("y", "yes")


def pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def choose(prompt: str, options: Sequence[str], *,
           default: str | None = None, allow_blank: bool = False
           ) -> str | None:
    """Numbered pick from ``options``; returns the option text."""
    if not options:
        print("    (nothing to choose from)")
        return None
    for i, o in enumerate(options, 1):
        print(f"    {i:>2}) {o}")
    while True:
        dflt = ""
        if default in options:
            dflt = str(list(options).index(default) + 1)
        s = ask(prompt, default=dflt, required=not allow_blank)
        if not s and allow_blank:
            return None
        if s.isdigit() and 1 <= int(s) <= len(options):
            return options[int(s) - 1]
        for o in options:
            if s.lower() == o.lower():
                return o
        print("    Pick a number from the list.")


def choose_many(prompt: str, options: Sequence[str],
                current: Sequence[str] = ()) -> list[str]:
    """Comma-separated numbers; blank keeps ``current``."""
    for i, o in enumerate(options, 1):
        mark = "*" if o in current else " "
        print(f"    {i:>2}){mark} {o}")
    s = ask(f"{prompt} (numbers, comma-separated; '-' for none)",
            default="")
    if not s:
        return list(current)
    if s.strip() == "-":
        return []
    out: list[str] = []
    for part in s.split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= len(options):
            out.append(options[int(part) - 1])
    return out


def table(headers: Sequence[str], rows: list[Sequence[Any]]) -> None:
    if not rows:
        print("\n  (none)")
        return
    cells = [[("" if v is None else str(v)) for v in r] for r in rows]
    widths = [min(32, max(len(h), *(len(r[i]) for r in cells)))
              for i, h in enumerate(headers)]
    print()
    print("  " + "  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  " + "  ".join("─" * w for w in widths))
    for r in cells:
        print("  " + "  ".join(v[:w].ljust(w) for v, w in zip(r, widths)))
    print(f"\n  {len(rows)} row(s)")


def pick_student() -> str:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    q = ask("Student id or name", required=True).lower()
    hits = [s for s in _students.list_students()
            if q == s.student_id.lower() or q in s.full_name.lower()]
    if not hits:
        raise ValueError(f"No student matches '{q}'")
    if len(hits) == 1:
        print(f"    → {hits[0].student_id} {hits[0].full_name}")
        return hits[0].student_id
    label = choose("Which student", [f"{s.student_id} — {s.full_name}"
                                     for s in hits[:30]])
    return (label or "").split(" — ")[0]


def pick_staff() -> str:
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    q = ask("Staff id or name", required=True).lower()
    hits = [s for s in _staff.list_staff()
            if q == s.staff_id.lower() or q in s.full_name.lower()]
    if not hits:
        raise ValueError(f"No staff member matches '{q}'")
    if len(hits) == 1:
        print(f"    → {hits[0].staff_id} {hits[0].full_name}")
        return hits[0].staff_id
    label = choose("Which staff member", [f"{s.staff_id} — {s.full_name}"
                                          for s in hits[:30]])
    return (label or "").split(" — ")[0]


def run_menu(title: str, menu: list[tuple[str, Callable[[], None]]]) -> None:
    while True:
        print(f"\n── {title} ──")
        for i, (label, _) in enumerate(menu, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
                print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(menu)):
            print("  Invalid selection.")
            continue
        label, handler = menu[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except UserAbort:
            print("\n  Cancelled.")
        except (ValueError, PermissionError) as e:
            print(f"\n  ✗ {e}")
            pause()
        except Exception as e:  # noqa: BLE001
            logger.exception("%s CLI crashed", title)
            print(f"\n  ✗ Unexpected error: {e}")
            pause()
