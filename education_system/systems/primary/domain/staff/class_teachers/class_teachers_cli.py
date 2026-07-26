"""CLI handlers for class teacher assignments."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.primary.domain.staff.class_teachers import (
    class_teachers as data,
)
from education_system.systems.primary.domain.staff.class_teachers.class_teachers import (
    ROLES,
)
from education_system.systems.primary.domain.academics.classes import (
    classes as classes_data,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError,
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


def _print_table(rows: list[tuple]) -> None:
    if not rows:
        print("  (no assignments)")
        return
    print(f"  {'#':<5} {'Class':<20} {'Yr':<5} {'AcYr':<9} "
          f"{'Role':<18} {'Staff':<24} {'P':<2}")
    print(f"  {'-'*5} {'-'*20} {'-'*5} {'-'*9} {'-'*18} {'-'*24} {'-'*2}")
    for a, cls in rows:
        cname = cls.name if cls else f"#{a.class_id}"
        cyr = cls.year_group if cls else "-"
        print(f"  {a.assignment_id:<5} {cname[:20]:<20} {cyr:<5} "
              f"{a.academic_year:<9} {a.role[:18]:<18} "
              f"{a.staff_name[:24]:<24} {'*' if a.is_primary else ' ':<2}")


@_safe
def open_class_teachers() -> None:
    logger.debug("CLI: open_class_teachers")
    while True:
        print("\n  -- Class Teachers --")
        years = data.known_years()
        if years:
            print(f"  Years recorded: {', '.join(years)}")
        c = data.counts()
        print(f"  Assignments: {c['total']}   "
              f"Primary class teachers: {c['primary']}   "
              f"Distinct staff: {c['staff']}")
        print("\n   1) List all assignments")
        print("   2) Filter assignments")
        print("   3) Show all for a class")
        print("   4) Show all for a staff member")
        print("   5) Create assignment")
        print("   6) Update assignment")
        print("   7) Mark as primary")
        print("   8) Delete assignment")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_all,
            "2": _list_filtered,
            "3": _by_class,
            "4": _by_staff,
            "5": _create,
            "6": _update,
            "7": _set_primary,
            "8": _delete,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _list_all() -> None:
    rows = data.list_assignments()
    print(f"\n  {len(rows)} assignment(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_filtered() -> None:
    ay = _prompt("  Academic year (blank for any): ").strip() or None
    print(f"  Roles: {', '.join(ROLES)} (blank for any)")
    role = _prompt("  Role: ").strip() or None
    name = _prompt("  Staff name contains (blank for any): ").strip() or None
    cls_raw = _prompt("  Class ID (blank for any): ").strip()
    cid: int | None = None
    if cls_raw:
        if not cls_raw.isdigit():
            print("  Class ID must be an integer.")
            return
        cid = int(cls_raw)
    rows = data.list_assignments(class_id=cid, academic_year=ay,
                                 role=role, staff_name=name)
    print(f"\n  {len(rows)} assignment(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _by_class() -> None:
    raw = _prompt("  Class ID: ")
    if not raw or not raw.isdigit():
        return
    ay = _prompt("  Academic year (blank for any): ").strip() or None
    rows = data.list_for_class(int(raw), academic_year=ay)
    cls = classes_data.get(int(raw))
    cname = cls.name if cls else f"#{raw}"
    print(f"\n  {len(rows)} assignment(s) for class {cname}:")
    if not rows:
        print("    (none)")
    else:
        for a in rows:
            print(f"    #{a.assignment_id} {a.academic_year} {a.role:<18} "
                  f"{a.staff_name}   {'*primary' if a.is_primary else ''}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _by_staff() -> None:
    name = _prompt("  Staff name (or fragment): ")
    if not name:
        return
    rows = data.list_for_staff(name)
    print(f"\n  {len(rows)} assignment(s) matching {name!r}:")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


def _collect(defaults: dict | None = None) -> dict:
    d = defaults or {}
    print(f"  (Roles: {', '.join(ROLES)})")
    out: dict = {}
    cid_def = "" if d.get("class_id") in (None, "") else str(d["class_id"])
    out["class_id"]      = _prompt(f"  Class ID [{cid_def}]: ") or cid_def
    out["staff_name"]    = _prompt(f"  Staff name [{d.get('staff_name','')}]: ") or d.get("staff_name", "")
    out["staff_id"]      = _prompt(f"  Staff ID (optional) [{d.get('staff_id','')}]: ") or d.get("staff_id", "")
    out["academic_year"] = _prompt(f"  Academic year [{d.get('academic_year','')}]: ") or d.get("academic_year", "")
    out["role"]          = _prompt(f"  Role [{d.get('role','Class Teacher')}]: ") or d.get("role", "Class Teacher")
    prim_def = "y" if d.get("is_primary") else "n"
    prim = _prompt(f"  Primary class teacher? (y/n) [{prim_def}]: ") or prim_def
    out["is_primary"]    = prim.lower() == "y"
    out["start_date"]    = _prompt(f"  Start date YYYY-MM-DD [{d.get('start_date','')}]: ") or d.get("start_date", "")
    out["end_date"]      = _prompt(f"  End date YYYY-MM-DD [{d.get('end_date','')}]: ") or d.get("end_date", "")
    out["notes"]         = _prompt(f"  Notes [{d.get('notes','')}]: ") or d.get("notes", "")
    return out


@_safe
def _create() -> None:
    print("\n  -- Create Assignment --")
    payload = _collect()
    rec = data.create(payload)
    print(f"  Created assignment #{rec.assignment_id}: "
          f"{rec.staff_name} -> class #{rec.class_id} as {rec.role}"
          + (" (primary)" if rec.is_primary else ""))
    _prompt("\n  Press Enter to continue...")


@_safe
def _update() -> None:
    raw = _prompt("  Assignment ID to update: ")
    if not raw or not raw.isdigit():
        return
    existing = data.get(int(raw))
    if existing is None:
        print(f"  No assignment #{raw}")
        return
    defaults = {
        "class_id": existing.class_id,
        "staff_name": existing.staff_name,
        "staff_id": existing.staff_id or "",
        "academic_year": existing.academic_year,
        "role": existing.role,
        "is_primary": existing.is_primary,
        "start_date": existing.start_date or "",
        "end_date": existing.end_date or "",
        "notes": existing.notes or "",
    }
    payload = _collect(defaults)
    rec = data.update(int(raw), payload)
    print(f"  Updated assignment #{rec.assignment_id}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _set_primary() -> None:
    raw = _prompt("  Assignment ID to mark primary: ")
    if not raw or not raw.isdigit():
        return
    rec = data.set_primary(int(raw))
    print(f"  Assignment #{rec.assignment_id} is now primary for "
          f"class #{rec.class_id} in {rec.academic_year}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    raw = _prompt("  Assignment ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete assignment #{raw}? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    ok = data.delete(int(raw))
    print(f"  {'Deleted' if ok else 'No such assignment'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Class Teachers": open_class_teachers}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching class_teachers CLI label: %s", label)
    handler()
    return True
