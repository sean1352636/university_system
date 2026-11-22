"""Console plumbing shared by the alumni menus.

:func:`run` runs one rule from ``university/application/alumni/`` in its
own transaction: commit on success; a refusal (``ValueError`` /
``PermissionError``) is rolled back and printed; e-mails a write returns are
sent after the commit.
"""

from __future__ import annotations

import os

from education_system.systems.university.application.teaching import (
    occurrences as timetable_occurrences,
)
from education_system.systems.university.infrastructure.database.db import get_connection

SUBMENU = "submenu"


def _emails(result):
    if isinstance(result, dict):
        return result.get("emails") or []
    if isinstance(result, list) and result and all(
            isinstance(e, tuple) and len(e) == 3 and "@" in str(e[0]) for e in result):
        return result
    return []


def run(fn, *args, write=True, **kwargs):
    """``fn(conn, *args, **kwargs)``; ``None`` when refused or failed."""
    conn = get_connection(row_factory=False)
    try:
        result = fn(conn, *args, **kwargs)
        if write:
            conn.commit()
    except (ValueError, PermissionError) as exc:
        conn.rollback()
        print(f"\n❌ {exc}")
        return None
    except Exception as exc:
        conn.rollback()
        print(f"\n❌ That did not work: {exc}")
        return None
    finally:
        conn.close()
    emails = _emails(result) if write else []
    if emails:
        timetable_occurrences.send_emails(emails)
    return True if result is None else result


def read(fn, *args, **kwargs):
    """A read rule (commits only what ``ensure()`` may have created)."""
    return run(fn, *args, write=True, **kwargs)


def ask(label, default="") -> str:
    suffix = f" [{default}]" if default not in ("", None) else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or ("" if default is None else str(default))


def ask_int(label, default=None):
    raw = ask(label, "" if default is None else default)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print("  Enter a whole number.")
        return None


def ask_choice(label, choices, default=""):
    joined = "/".join(choices)
    while True:
        value = ask(f"{label} ({joined})", default).lower()
        if value in choices:
            return value
        if not value:
            return ""
        print(f"  Choose one of: {joined}")


def confirm(label) -> bool:
    return input(f"{label} (y/n): ").strip().lower() in ("y", "yes")


def section(title) -> None:
    print(f"\n{'─' * 70}\n  {title}\n{'─' * 70}")


def table(rows, columns) -> None:
    """``columns``: ``[(key, heading, width)]``."""
    if not rows:
        print("\n  Nothing to show.")
        return
    print("\n  " + "".join(f"{h:<{w}}" for _, h, w in columns))
    print("  " + "-" * sum(w for _, _, w in columns))
    for row in rows:
        cells = []
        for key, _, width in columns:
            value = row.get(key)
            text = "—" if value in (None, "") else str(value)
            cells.append(f"{text[:width - 1]:<{width}}")
        print("  " + "".join(cells))
    print(f"\n  {len(rows)} row(s).")


def show(pairs) -> None:
    for label, value in pairs:
        print(f"  {label + ':':<26} {value if value not in (None, '') else '—'}")


def menu(title, items) -> str:
    """Loop over ``items`` (``[(label, handler)]``) until 0."""
    while True:
        section(title)
        for n, (label, _) in enumerate(items, 1):
            print(f"  {n:>2}. {label}")
        print("   0. Back")
        choice = input("\n👉 Choice: ").strip()
        if choice in ("0", ""):
            return SUBMENU
        if not choice.isdigit() or not 1 <= int(choice) <= len(items):
            print("  Invalid choice.")
            continue
        try:
            result = items[int(choice) - 1][1]()
        except (KeyboardInterrupt, EOFError):
            raise
        except Exception as exc:     # a menu action never ends the session
            print(f"\n❌ Error: {exc}")
            result = None
        if result != SUBMENU:
            input("\nPress Enter to continue...")


def write_file(path, content) -> bool:
    try:
        with open(os.path.expanduser(path), "w", encoding="utf-8") as fh:
            fh.write(content)
        return True
    except OSError as exc:
        print(f"  Could not write file: {exc}")
        return False


def yes_no(value) -> str:
    return "yes" if value else "no"
