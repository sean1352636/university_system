"""CLI handlers for classes in the Primary School System."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.primary.domain.academics.classes import (
    classes as data,
)
from education_system.systems.primary.domain.academics.classes.classes import (
    SchoolClass,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
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


def _print_table(rows: list[SchoolClass]) -> None:
    if not rows:
        print("  (no classes)")
        return
    print(f"  {'ID':<5} {'Name':<20} {'Year':<5} {'Teacher':<22} "
          f"{'Room':<10} {'Cap':<4} {'Active':<6}")
    print(f"  {'-'*5} {'-'*20} {'-'*5} {'-'*22} {'-'*10} {'-'*4} {'-'*6}")
    for c in rows:
        print(f"  {c.class_id:<5} {c.name[:20]:<20} {c.year_group:<5} "
              f"{(c.teacher or '-')[:22]:<22} {(c.room or '-')[:10]:<10} "
              f"{str(c.capacity or '-'):<4} {'yes' if c.is_active else 'no':<6}")


def _print_counts() -> None:
    c = data.counts()
    print(f"  Total: {c['total']}   Active: {c['active']}   "
          f"Inactive: {c['inactive']}")


@_safe
def open_classes() -> None:
    logger.debug("CLI: open_classes")
    while True:
        print("\n  -- Classes --")
        _print_counts()
        print("\n   1) List all classes")
        print("   2) Filter by year group")
        print("   3) View class (with pupils)")
        print("   4) Add class")
        print("   5) Update class")
        print("   6) Toggle active")
        print("   7) Delete class")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_all,
            "2": _list_by_year,
            "3": _view,
            "4": _add,
            "5": _update,
            "6": _toggle,
            "7": _delete,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _list_all() -> None:
    rows = data.list_all()
    print(f"\n  {len(rows)} class(es):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_by_year() -> None:
    print(f"  Year groups: {', '.join(YEAR_GROUPS)}")
    yg = _prompt("  Year: ")
    if not yg:
        return
    rows = data.list_all(year_group=yg)
    print(f"\n  Year {yg}: {len(rows)} class(es)")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view() -> None:
    raw = _prompt("  Class ID: ")
    if not raw:
        return
    if not raw.isdigit():
        print("  Class ID must be an integer.")
        return
    cls = data.get(int(raw))
    if cls is None:
        print(f"  No class #{raw}")
        return
    print(f"\n  -- Class {cls.name} (#{cls.class_id}) --")
    print(f"  Year:     {cls.year_group}")
    print(f"  Teacher:  {cls.teacher or '-'}")
    print(f"  Room:     {cls.room or '-'}")
    print(f"  Capacity: {cls.capacity or '-'}")
    print(f"  Active:   {'yes' if cls.is_active else 'no'}")
    print(f"  Notes:    {cls.notes or '-'}")
    pupils = data.pupils_in_class(cls.name)
    print(f"\n  Pupils ({len(pupils)}):")
    if not pupils:
        print("    (none)")
    else:
        for p in pupils:
            print(f"    - {p.pupil_id}  {p.full_name}  (year {p.year_group})")
    if cls.capacity and len(pupils) > cls.capacity:
        print(f"\n  WARNING: enrolment {len(pupils)} exceeds capacity {cls.capacity}")
    _prompt("\n  Press Enter to continue...")


def _collect(defaults: dict | None = None) -> dict:
    d = defaults or {}
    print(f"  (Year groups: {', '.join(YEAR_GROUPS)})")
    out: dict = {}
    out["name"]       = _prompt(f"  Name [{d.get('name','')}]: ") or d.get("name", "")
    out["year_group"] = _prompt(f"  Year group [{d.get('year_group','')}]: ") or d.get("year_group", "")
    out["teacher"]    = _prompt(f"  Teacher [{d.get('teacher','')}]: ") or d.get("teacher", "")
    out["room"]       = _prompt(f"  Room [{d.get('room','')}]: ") or d.get("room", "")
    cap_default = "" if d.get("capacity") in (None, "") else str(d["capacity"])
    out["capacity"]   = _prompt(f"  Capacity [{cap_default}]: ") or cap_default
    out["notes"]      = _prompt(f"  Notes [{d.get('notes','')}]: ") or d.get("notes", "")
    return out


@_safe
def _add() -> None:
    print("\n  -- Add Class --")
    payload = _collect()
    rec = data.create(payload)
    print(f"  Created class #{rec.class_id} {rec.name}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _update() -> None:
    raw = _prompt("  Class ID to update: ")
    if not raw or not raw.isdigit():
        return
    existing = data.get(int(raw))
    if existing is None:
        print(f"  No class #{raw}")
        return
    defaults = {
        "name": existing.name,
        "year_group": existing.year_group,
        "teacher": existing.teacher or "",
        "room": existing.room or "",
        "capacity": existing.capacity,
        "notes": existing.notes or "",
    }
    payload = _collect(defaults)
    rec = data.update(int(raw), payload)
    print(f"  Updated class #{rec.class_id} {rec.name}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _toggle() -> None:
    raw = _prompt("  Class ID: ")
    if not raw or not raw.isdigit():
        return
    rec = data.toggle_active(int(raw))
    print(f"  Class #{rec.class_id} {rec.name} -> "
          f"{'active' if rec.is_active else 'inactive'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    raw = _prompt("  Class ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete class #{raw}? Type 'DELETE' to confirm: ")
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    ok = data.delete(int(raw))
    if ok:
        print(f"  Deleted class #{raw}.")
    else:
        print(f"  No class #{raw}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Classes": open_classes}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching classes CLI label: %s", label)
    handler()
    return True
