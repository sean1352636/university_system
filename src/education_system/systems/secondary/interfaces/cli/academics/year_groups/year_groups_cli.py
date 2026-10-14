"""CLI handlers for year-group configuration."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.secondary.domain.academics.year_groups import (
    year_groups as data,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_table(rows: list[data.YearGroup], counts: dict[str, int]) -> None:
    print(f"  {'Year':<5} {'Head of Year':<24} {'Capacity':<9} "
          f"{'Pupils':<7} {'Notes':<30}")
    print(f"  {'-'*5} {'-'*24} {'-'*9} {'-'*7} {'-'*30}")
    for y in rows:
        cap = str(y.capacity) if y.capacity is not None else "-"
        pupils = counts.get(y.year_group, 0)
        notes = (y.notes or "")[:30]
        print(f"  {y.year_group:<5} {(y.head_of_year or '-'):<24} "
              f"{cap:<9} {pupils:<7} {notes:<30}")


@_safe
def open_year_groups() -> None:
    logger.debug("CLI: open_year_groups")
    while True:
        rows = data.list_all()
        counts = data.pupil_counts()
        print("\n  ── Year Groups ──")
        _print_table(rows, counts)
        print("\n   1) Edit year group")
        print("   2) Clear configuration")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        if choice == "1":
            _edit()
        elif choice == "2":
            _clear()
        else:
            print("  Invalid selection.")


@_safe
def _edit() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}): ")
    if not yg:
        return
    if yg not in YEAR_GROUPS:
        print(f"  Invalid year. Must be one of {', '.join(YEAR_GROUPS)}")
        return
    existing = data.get(yg)
    cur_head = existing.head_of_year if existing else None
    cur_cap = str(existing.capacity) if existing and existing.capacity is not None else None
    cur_notes = existing.notes if existing else None

    def ask(label: str, current: str | None) -> str:
        suffix = f" [{current}]" if current else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (current or "")

    head = ask("Head of year", cur_head)
    cap = ask("Capacity", cur_cap)
    notes = ask("Notes", cur_notes)
    rec = data.upsert({
        "year_group":   yg,
        "head_of_year": head,
        "capacity":     cap,
        "notes":        notes,
    })
    print(f"  Saved Year {rec.year_group} "
          f"(head: {rec.head_of_year or '-'}, "
          f"capacity: {rec.capacity if rec.capacity is not None else '-'})")


@_safe
def _clear() -> None:
    yg = _prompt(f"  Year to clear ({'/'.join(YEAR_GROUPS)}): ")
    if not yg:
        return
    if data.delete(yg):
        print(f"  Cleared Year {yg} configuration.")
    else:
        print(f"  No configuration stored for Year {yg}.")


_DISPATCH = {"Year Groups": open_year_groups}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching year_groups CLI label: %s", label)
    handler()
    return True
