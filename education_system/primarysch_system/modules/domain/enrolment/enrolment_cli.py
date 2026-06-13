"""CLI handlers for year-group enrolment in the Primary School System."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.primarysch_system.modules.domain.enrolment import (
    enrolment as data,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
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


def _print_pupils(rows) -> None:
    if not rows:
        print("  (none)")
        return
    print(f"  {'ID':<10} {'Class':<8} {'Name':<28} {'SEND'}")
    print(f"  {'-'*10} {'-'*8} {'-'*28} {'-'*5}")
    for p in rows:
        print(f"  {p.pupil_id:<10} {(p.class_name or '-'):<8} "
              f"{p.full_name[:28]:<28} {p.send_status or '-'}")


@_safe
def open_enrolment() -> None:
    logger.debug("CLI: open_enrolment")
    while True:
        roll = data.roll_by_year()
        total = sum(len(v) for v in roll.values())
        print("\n  ── Year Group Enrolment ──")
        print(f"  Total on roll: {total}")
        for y in YEAR_GROUPS:
            print(f"   Year {y:>2}: {len(roll[y]):>3} pupil(s)")
        print("\n   1) View roll for a year group")
        print("   2) Move a pupil to another year")
        print("   3) Promote everyone in a year (year-end)")
        print("   4) List leavers (Year 6)")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _view_year_roll,
            "2": _move_pupil,
            "3": _promote_year,
            "4": _show_leavers,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _view_year_roll() -> None:
    yg = _prompt(f"  Year group ({'/'.join(YEAR_GROUPS)}): ")
    if yg not in YEAR_GROUPS:
        print(f"  Year must be one of {', '.join(YEAR_GROUPS)}.")
        return
    roll = data.roll_by_year()
    pupils = roll[yg]
    print(f"\n  Year {yg}: {len(pupils)} pupil(s)")
    _print_pupils(pupils)
    _prompt("\n  Press Enter to continue...")


@_safe
def _move_pupil() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    new_year = _prompt(f"  New year group ({'/'.join(YEAR_GROUPS)}): ")
    new_class_input = _prompt("  New class (blank to keep): ")
    new_class = new_class_input if new_class_input else None
    p = data.move_pupil(pid, new_year, new_class=new_class)
    print(f"\n  Moved {p.full_name} to year {p.year_group} "
          f"(class {p.class_name or '-'})")


@_safe
def _promote_year() -> None:
    yg = _prompt(f"  Promote from year ({'/'.join(YEAR_GROUPS)}): ")
    if yg not in YEAR_GROUPS:
        print(f"  Year must be one of {', '.join(YEAR_GROUPS)}.")
        return
    preview = data.promote_year(yg, dry_run=True)
    to_y = preview["to_year"]
    leavers = preview["leavers"]
    pupils = preview["pupils"]
    if to_y is None:
        print(f"\n  Year {yg} is the final year — promoting would "
              f"produce {len(leavers)} leaver(s):")
        _print_pupils(leavers)
        print("\n  Leavers must be deleted manually from the pupil directory.")
        _prompt("\n  Press Enter to continue...")
        return
    print(f"\n  About to move {preview['count']} pupil(s) "
          f"from year {yg} to year {to_y}:")
    _print_pupils(pupils)
    if _prompt(f"\n  Proceed? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    result = data.promote_year(yg)
    print(f"  Promoted {result['count']} pupil(s) from year {yg} "
          f"to year {to_y}.")


@_safe
def _show_leavers() -> None:
    rows = data.leavers()
    print(f"\n  ── Leavers (Year {data.FINAL_YEAR}) ──  {len(rows)} pupil(s)")
    _print_pupils(rows)
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Year Group Enrolment": open_enrolment}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching enrolment CLI label: %s", label)
    handler()
    return True
