"""CLI handlers for clubs / activities."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.primarysch_system.modules.domain.clubs import (
    clubs as data,
)
from education_system.primarysch_system.modules.domain.clubs.clubs import (
    Club, DAYS_OF_WEEK, MEMBERSHIP_STATUSES,
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


def _print_counts() -> None:
    c = data.counts()
    print(f"  Clubs: {c['total']}   Active: {c['active']}   "
          f"Inactive: {c['inactive']}   Active members: {c['active_members']}")


def _print_table(rows: list[Club]) -> None:
    if not rows:
        print("  (no clubs)")
        return
    print(f"  {'ID':<4} {'Name':<22} {'Day':<10} {'Time':<13} "
          f"{'Years':<14} {'Lead':<18} {'Cap':<4} {'Act':<4}")
    print(f"  {'-'*4} {'-'*22} {'-'*10} {'-'*13} {'-'*14} {'-'*18} "
          f"{'-'*4} {'-'*4}")
    for c in rows:
        time = ""
        if c.start_time or c.end_time:
            time = f"{c.start_time or '?'}–{c.end_time or '?'}"
        yrs = c.year_groups or "any"
        cap = "-" if c.max_members is None else str(c.max_members)
        print(f"  {c.club_id:<4} {c.name[:22]:<22} {(c.day_of_week or '-'):<10} "
              f"{time[:13]:<13} {yrs[:14]:<14} "
              f"{(c.lead_staff or '-')[:18]:<18} {cap:<4} "
              f"{'yes' if c.is_active else 'no':<4}")


@_safe
def open_clubs() -> None:
    logger.debug("CLI: open_clubs")
    while True:
        print("\n  -- Clubs & Activities --")
        _print_counts()
        print("\n   1) List all clubs")
        print("   2) Filter by day / active")
        print("   3) View club + members")
        print("   4) Add club")
        print("   5) Update club")
        print("   6) Toggle active")
        print("   7) Delete club")
        print("   8) Add member to club")
        print("   9) Change member status")
        print("  10) Remove membership")
        print("  11) Clubs for a pupil")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_all,
            "2": _list_filtered,
            "3": _view,
            "4": _add,
            "5": _update,
            "6": _toggle,
            "7": _delete,
            "8": _add_member,
            "9": _change_status,
            "10": _remove_member,
            "11": _pupil_clubs,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _list_all() -> None:
    rows = data.list_all()
    print(f"\n  {len(rows)} club(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_filtered() -> None:
    print(f"  Days: {', '.join(DAYS_OF_WEEK)} (blank for any)")
    day = _prompt("  Day: ").strip() or None
    active_only = _prompt("  Active only? (y/N): ").lower() == "y"
    rows = data.list_all(day_of_week=day, active_only=active_only)
    print(f"\n  {len(rows)} club(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view() -> None:
    raw = _prompt("  Club ID: ")
    if not raw or not raw.isdigit():
        return
    cid = int(raw)
    cls = data.get(cid)
    if cls is None:
        print(f"  No club #{raw}")
        return
    print(f"\n  -- Club #{cls.club_id} {cls.name} --")
    print(f"  Description:  {cls.description or '-'}")
    print(f"  Day / time:   {(cls.day_of_week or '-')} "
          f"{(cls.start_time or '')}–{(cls.end_time or '')}")
    print(f"  Location:     {cls.location or '-'}")
    print(f"  Lead staff:   {cls.lead_staff or '-'}")
    print(f"  Year groups:  {cls.year_groups or 'any'}")
    print(f"  Max members:  {cls.max_members if cls.max_members else '-'}")
    print(f"  Active:       {'yes' if cls.is_active else 'no'}")
    print(f"  Notes:        {cls.notes or '-'}")
    members = data.list_members(cid)
    active_n = sum(1 for _, m in members if m.status == "active")
    print(f"\n  Members ({len(members)}, {active_n} active):")
    if not members:
        print("    (none)")
    else:
        print(f"    {'M#':<5} {'Pupil ID':<10} {'Name':<26} "
              f"{'Year':<5} {'Joined':<11} {'Status':<10}")
        for p, m in members:
            print(f"    {m.membership_id:<5} {p.pupil_id:<10} "
                  f"{p.full_name[:26]:<26} {p.year_group:<5} "
                  f"{m.joined_on:<11} {m.status:<10}")
    if cls.max_members is not None and active_n > cls.max_members:
        print(f"\n  WARNING: active members {active_n} exceed cap {cls.max_members}")
    _prompt("\n  Press Enter to continue...")


def _collect(defaults: dict | None = None) -> dict:
    d = defaults or {}
    print(f"  (Days: {', '.join(DAYS_OF_WEEK)})")
    print(f"  (Year groups: {', '.join(YEAR_GROUPS)} — comma-separated, blank for any)")
    out: dict = {}
    out["name"]        = _prompt(f"  Name [{d.get('name','')}]: ") or d.get("name", "")
    out["description"] = _prompt(f"  Description [{d.get('description','')}]: ") or d.get("description", "")
    out["day_of_week"] = _prompt(f"  Day [{d.get('day_of_week','')}]: ") or d.get("day_of_week", "")
    out["start_time"]  = _prompt(f"  Start time HH:MM [{d.get('start_time','')}]: ") or d.get("start_time", "")
    out["end_time"]    = _prompt(f"  End time HH:MM [{d.get('end_time','')}]: ") or d.get("end_time", "")
    out["location"]    = _prompt(f"  Location [{d.get('location','')}]: ") or d.get("location", "")
    out["lead_staff"]  = _prompt(f"  Lead staff [{d.get('lead_staff','')}]: ") or d.get("lead_staff", "")
    out["year_groups"] = _prompt(f"  Year groups [{d.get('year_groups','')}]: ") or d.get("year_groups", "")
    cap_default = "" if d.get("max_members") in (None, "") else str(d["max_members"])
    out["max_members"] = _prompt(f"  Max members [{cap_default}]: ") or cap_default
    out["notes"]       = _prompt(f"  Notes [{d.get('notes','')}]: ") or d.get("notes", "")
    return out


@_safe
def _add() -> None:
    print("\n  -- Add Club --")
    payload = _collect()
    rec = data.create(payload)
    print(f"  Created club #{rec.club_id} {rec.name}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _update() -> None:
    raw = _prompt("  Club ID to update: ")
    if not raw or not raw.isdigit():
        return
    existing = data.get(int(raw))
    if existing is None:
        print(f"  No club #{raw}")
        return
    defaults = {
        "name": existing.name,
        "description": existing.description or "",
        "day_of_week": existing.day_of_week or "",
        "start_time": existing.start_time or "",
        "end_time": existing.end_time or "",
        "location": existing.location or "",
        "lead_staff": existing.lead_staff or "",
        "year_groups": existing.year_groups or "",
        "max_members": existing.max_members,
        "notes": existing.notes or "",
    }
    payload = _collect(defaults)
    rec = data.update(int(raw), payload)
    print(f"  Updated club #{rec.club_id} {rec.name}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _toggle() -> None:
    raw = _prompt("  Club ID: ")
    if not raw or not raw.isdigit():
        return
    rec = data.toggle_active(int(raw))
    print(f"  Club #{rec.club_id} {rec.name} -> "
          f"{'active' if rec.is_active else 'inactive'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    raw = _prompt("  Club ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete club #{raw}? Type 'DELETE' to confirm "
                     f"(memberships cascade): ")
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    ok = data.delete(int(raw))
    print(f"  {'Deleted' if ok else 'No such club'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _add_member() -> None:
    raw = _prompt("  Club ID: ")
    if not raw or not raw.isdigit():
        return
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    joined = _prompt("  Joined on YYYY-MM-DD (blank for today): ")
    notes = _prompt("  Notes (optional): ")
    m = data.add_member(int(raw), pid,
                        joined_on=joined or None,
                        notes=notes or None)
    print(f"  Added pupil {pid} to club #{raw} (membership #{m.membership_id})")
    _prompt("\n  Press Enter to continue...")


@_safe
def _change_status() -> None:
    raw = _prompt("  Membership ID: ")
    if not raw or not raw.isdigit():
        return
    print(f"  Statuses: {', '.join(MEMBERSHIP_STATUSES)}")
    new = _prompt("  New status: ").strip().lower()
    if not new:
        return
    m = data.set_member_status(int(raw), new)
    print(f"  Membership #{m.membership_id} -> {m.status}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _remove_member() -> None:
    raw = _prompt("  Membership ID to remove: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Remove membership #{raw}? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    ok = data.remove_member(int(raw))
    print(f"  {'Removed' if ok else 'No such membership'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _pupil_clubs() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    rows = data.list_clubs_for_pupil(pid)
    print(f"\n  {len(rows)} club(s) for pupil {pid}:")
    if not rows:
        print("    (none)")
    else:
        for c, m in rows:
            print(f"    #{c.club_id:<3} {c.name[:24]:<24} "
                  f"joined {m.joined_on}  ({m.status})")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Clubs & Activities": open_clubs}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching clubs CLI label: %s", label)
    handler()
    return True
