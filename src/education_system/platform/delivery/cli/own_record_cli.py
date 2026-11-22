"""Terminal helpers shared by the student and parent own-record menus."""

from __future__ import annotations

import logging
from typing import Any, Callable, Sequence

from education_system.platform.cross_system.own_record_access import OwnRecordError

logger = logging.getLogger(__name__)

LOAD_FAILED = ("These records could not be loaded just now. Please try again, or "
               "contact the school office if it keeps happening.")


def prompt(message: str) -> str:
    try:
        return input(message).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def guarded(title: str, draw: Callable[[], None]) -> None:
    """Run a screen; a refused or unlinked record prints its message and nothing else."""
    print(f"\n── {title} ──")
    try:
        draw()
    except OwnRecordError as refused:
        print(f"  {refused}")
    except ValueError as invalid:
        print(f"  {invalid}")
    except Exception:
        logger.exception("Own-record screen %s failed", title)
        print(f"  {LOAD_FAILED}")
    prompt("  Press Enter to continue...")


def print_table(columns: Sequence[tuple[str, int]], rows: Sequence[Sequence[Any]],
                *, empty: str, numbered: bool = False) -> None:
    """Print ``(heading, width)`` columns, or *empty* if there are no rows."""
    if not rows:
        print(f"  {empty}")
        return
    lead = "     " if numbered else "  "
    print(lead + " ".join(f"{h:<{w}.{w}}" for h, w in columns))
    for i, row in enumerate(rows, 1):
        lead = f"  {i:>2}) " if numbered else "  "
        print(lead + " ".join(
            f"{'' if v is None else str(v):<{w}.{w}}" for v, (_h, w) in zip(row, columns)))


def pick(rows: Sequence[Any], message: str = "  Select # (blank to cancel): ") -> Any:
    """The chosen row, or None. Only rows already listed can be chosen."""
    answer = prompt(message)
    if answer.isdigit() and 1 <= int(answer) <= len(rows):
        return rows[int(answer) - 1]
    if answer:
        print("  Invalid selection.")
    return None


def choose_child(children: Sequence[Any]) -> str | None:
    """A parent's choice between their own linked children, by list position.

    A pupil id is never typed: the id comes from the list, and the read layer
    checks it again on every read.
    """
    if not children:
        return None
    if len(children) == 1:
        print(f"  Child: {children[0].name}")
        return children[0].pupil_id
    for i, child in enumerate(children, 1):
        print(f"  {i:>2}) {child.name} (Year {child.year_group})")
    chosen = pick(children, "  Choose a child: ")
    return chosen.pupil_id if chosen else None
