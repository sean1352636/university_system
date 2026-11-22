"""Console plumbing for the research office menus: running a rule in its own
transaction, prompting, and printing tables and records."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class Back(Exception):
    """Leave the current menu (input ran out, or the user typed ``0``)."""


def run(fn, *args, write=False, **kwargs):
    """``fn(conn, *args, **kwargs)`` in its own transaction. ``None`` means it
    was refused or failed (already printed); a write returning nothing
    gives ``True``. E-mails a write returns are sent after the commit."""
    from education_system.systems.university.application.teaching import (
        occurrences as timetable_occurrences,
    )
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(row_factory=False)
    try:
        result = fn(conn, *args, **kwargs)
        if write:
            conn.commit()
    except (ValueError, PermissionError) as exc:
        conn.rollback()
        print(f"  ✗ {exc}")
        return None
    except Exception as exc:
        conn.rollback()
        logger.exception("research office action failed: %s", getattr(fn, "__name__", fn))
        print(f"  ✗ That did not work: {exc}")
        return None
    finally:
        conn.close()
    if write:
        emails = result.get("emails") if isinstance(result, dict) else (
            result if _emails(result) else None)
        if emails:
            timetable_occurrences.send_emails(emails)
    return True if result is None else result


def write(fn, *args, done="Done.", **kwargs):
    result = run(fn, *args, write=True, **kwargs)
    if result is not None and done:
        print(f"  ✓ {done}")
    return result


def _emails(result) -> bool:
    return isinstance(result, list) and bool(result) and all(
        isinstance(e, tuple) and len(e) == 3 and "@" in str(e[0]) for e in result)


# ── prompts ─────────────────────────────────────────────────────────────


def ask(prompt, default="", required=False) -> str:
    while True:
        try:
            value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
        except EOFError:
            raise Back() from None
        value = value or str(default or "")
        if value or not required:
            return value
        print("  This is required.")


def ask_int(prompt, required=True) -> int | None:
    while True:
        value = ask(prompt, required=required)
        if not value:
            return None
        if value.isdigit():
            return int(value)
        print("  Enter a number.")


def ask_yes(prompt, default=False) -> bool:
    value = ask(f"{prompt} (y/n)", "y" if default else "n").lower()
    return value.startswith("y")


def ask_choice(prompt, options, required=True, default=None):
    """Pick one of ``options`` (values, or ``(value, label)`` pairs) by number."""
    pairs = [o if isinstance(o, tuple) else (o, str(o).replace("_", " ")) for o in options]
    for n, (_value, label) in enumerate(pairs, 1):
        print(f"   {n}. {label}")
    while True:
        value = ask(prompt, default or "", required=required)
        if not value:
            return None
        if value.isdigit() and 1 <= int(value) <= len(pairs):
            return pairs[int(value) - 1][0]
        for v, label in pairs:
            if value.lower() in (str(v).lower(), label.lower()):
                return v
        print("  Pick one of the numbers above.")


def form(fields, edit=False) -> dict:
    """``fields``: ``(key, label)``, ``(key, label, choices)`` or
    ``(key, label, "yes")``. When editing, blank answers are left out."""
    out = {}
    for spec in fields:
        key, label, *kind = spec
        kind = kind[0] if kind else None
        if kind == "yes":
            if edit and not ask_yes(f"Change '{label}'?"):
                continue
            out[key] = ask_yes(label)
        elif kind:
            value = ask_choice(label, kind, required=False)
            if value is not None or not edit:
                out[key] = value
        else:
            value = ask(label)
            if value or not edit:
                out[key] = value or None
    return out


# ── output ──────────────────────────────────────────────────────────────


def _cell(value) -> str:
    if value is None or value == "":
        return "—"
    return str(value).replace("\n", " ")


def table(rows, columns) -> None:
    """``columns``: ``[(key, heading, width), …]``."""
    if not rows:
        print("  Nothing to show.")
        return
    header = " ".join(f"{h:<{w}}" for _k, h, w in columns)
    print("\n" + header)
    print("-" * len(header))
    for row in rows:
        print(" ".join(f"{_cell(row.get(k))[:w - 1]:<{w}}" for k, _h, w in columns))


def show(title, record, keys) -> None:
    """Print ``title`` then ``label: value`` for each ``(key, label)``."""
    print(f"\n{title}\n" + "=" * min(len(title), 70))
    for key, label in keys:
        print(f"  {label:<26}{_cell(record.get(key))}")


def section(heading, rows, columns) -> None:
    print(f"\n{heading}")
    table(rows, columns)


def history(rows) -> None:
    section("History", rows, [("at", "When", 20), ("actor", "Who", 16), ("action", "What", 24),
                              ("detail", "Detail", 40)])


def money(value) -> str:
    try:
        return f"£{float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return str(value)


# ── menus ───────────────────────────────────────────────────────────────


def menu(title, actions, who) -> None:
    """Loop over ``actions`` (``[(label, fn(who))]``) until ``0`` or no input."""
    while True:
        print(f"\n{title}\n" + "=" * 50)
        for n, (label, _fn) in enumerate(actions, 1):
            print(f"  {n:>2}. {label}")
        print("   0. Back")
        try:
            choice = ask("Select")
        except Back:
            return
        if choice == "0":
            return
        if not choice.isdigit() or not 1 <= int(choice) <= len(actions):
            print("  Invalid choice.")
            continue
        try:
            actions[int(choice) - 1][1](who)
        except Back:
            return
        except KeyboardInterrupt:
            print("\n  Cancelled.")
