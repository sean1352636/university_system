"""CLI handlers for house points."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.primarysch_system.modules.domain.house_points import (
    house_points as data,
)
from education_system.primarysch_system.modules.domain.house_points.house_points import (
    POINTS_MAX, POINTS_MIN,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
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


def _print_houses(rows: list) -> None:
    if not rows:
        print("  (no houses)")
        return
    print(f"  {'ID':<4} {'Name':<20} {'Colour':<14} {'Active':<6} {'Motto':<30}")
    print(f"  {'-'*4} {'-'*20} {'-'*14} {'-'*6} {'-'*30}")
    for h in rows:
        print(f"  {h.house_id:<4} {h.name[:20]:<20} {(h.colour or '-'):<14} "
              f"{'yes' if h.is_active else 'no':<6} "
              f"{(h.motto or '-')[:30]:<30}")


def _print_leaderboard(totals: list[tuple]) -> None:
    if not totals:
        print("  (no houses)")
        return
    print(f"  {'Rank':<5} {'House':<20} {'Total':<8}")
    print(f"  {'-'*5} {'-'*20} {'-'*8}")
    for rank, (h, total) in enumerate(totals, 1):
        print(f"  {rank:<5} {h.name[:20]:<20} {total:+d}")


def _print_awards(rows: list[tuple]) -> None:
    if not rows:
        print("  (no awards)")
        return
    print(f"  {'#':<6} {'Date':<11} {'House':<14} {'Pupil':<10} "
          f"{'Pts':<5} {'By':<18} {'Reason':<26}")
    print(f"  {'-'*6} {'-'*11} {'-'*14} {'-'*10} {'-'*5} {'-'*18} {'-'*26}")
    for a, house, _pupil in rows:
        hname = house.name if house else f"#{a.house_id}"
        print(f"  {a.award_id:<6} {a.awarded_on:<11} {hname[:14]:<14} "
              f"{(a.pupil_id or '-'):<10} {a.points:+5d} "
              f"{(a.awarded_by or '-')[:18]:<18} "
              f"{(a.reason or '-')[:26]:<26}")


@_safe
def open_house_points() -> None:
    logger.debug("CLI: open_house_points")
    while True:
        print("\n  -- House Points --")
        try:
            totals = data.house_totals()
        except Exception:
            totals = []
        if totals:
            print("  Leaderboard:")
            _print_leaderboard(totals)
        print("\n   1) List houses")
        print("   2) Create house")
        print("   3) Update house")
        print("   4) Toggle house active")
        print("   5) Delete house")
        print("   6) Award points")
        print("   7) List recent awards")
        print("   8) Filter awards")
        print("   9) Pupil leaderboard")
        print("  10) Pupil total")
        print("  11) Update award")
        print("  12) Delete award")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_houses,
            "2": _create_house,
            "3": _update_house,
            "4": _toggle_house,
            "5": _delete_house,
            "6": _award,
            "7": _list_awards,
            "8": _filter_awards,
            "9": _pupil_leaderboard,
            "10": _pupil_total,
            "11": _update_award,
            "12": _delete_award,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _list_houses() -> None:
    rows = data.list_houses()
    print(f"\n  {len(rows)} house(s):")
    _print_houses(rows)
    _prompt("\n  Press Enter to continue...")


def _collect_house(defaults: dict | None = None) -> dict:
    d = defaults or {}
    out: dict = {}
    out["name"]   = _prompt(f"  Name [{d.get('name','')}]: ") or d.get("name", "")
    out["colour"] = _prompt(f"  Colour [{d.get('colour','')}]: ") or d.get("colour", "")
    out["motto"]  = _prompt(f"  Motto [{d.get('motto','')}]: ") or d.get("motto", "")
    out["notes"]  = _prompt(f"  Notes [{d.get('notes','')}]: ") or d.get("notes", "")
    return out


@_safe
def _create_house() -> None:
    print("\n  -- Create House --")
    payload = _collect_house()
    rec = data.create_house(payload)
    print(f"  Created house #{rec.house_id} {rec.name}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _update_house() -> None:
    raw = _prompt("  House ID to update: ")
    if not raw or not raw.isdigit():
        return
    existing = data.get_house(int(raw))
    if existing is None:
        print(f"  No house #{raw}")
        return
    defaults = {
        "name": existing.name,
        "colour": existing.colour or "",
        "motto": existing.motto or "",
        "notes": existing.notes or "",
    }
    payload = _collect_house(defaults)
    rec = data.update_house(int(raw), payload)
    print(f"  Updated house #{rec.house_id} {rec.name}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _toggle_house() -> None:
    raw = _prompt("  House ID to toggle: ")
    if not raw or not raw.isdigit():
        return
    rec = data.toggle_house_active(int(raw))
    print(f"  House #{rec.house_id} {rec.name} -> "
          f"{'active' if rec.is_active else 'inactive'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete_house() -> None:
    raw = _prompt("  House ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete house #{raw}? Type 'DELETE' to confirm: ")
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    ok = data.delete_house(int(raw))
    print(f"  {'Deleted' if ok else 'No such house'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


def _collect_award(defaults: dict | None = None) -> dict:
    d = defaults or {}
    print(f"  (Points range: {POINTS_MIN} to {POINTS_MAX}; non-zero)")
    out: dict = {}
    hid_def = "" if d.get("house_id") in (None, "") else str(d["house_id"])
    out["house_id"]   = _prompt(f"  House ID [{hid_def}]: ") or hid_def
    out["pupil_id"]   = _prompt(f"  Pupil ID (optional) [{d.get('pupil_id','')}]: ") or d.get("pupil_id", "")
    pts_def = "" if d.get("points") in (None, "") else str(d["points"])
    out["points"]     = _prompt(f"  Points [{pts_def}]: ") or pts_def
    out["reason"]     = _prompt(f"  Reason [{d.get('reason','')}]: ") or d.get("reason", "")
    out["awarded_by"] = _prompt(f"  Awarded by [{d.get('awarded_by','')}]: ") or d.get("awarded_by", "")
    out["awarded_on"] = _prompt(f"  Awarded on YYYY-MM-DD (blank for today) [{d.get('awarded_on','')}]: ") or d.get("awarded_on", "")
    out["notes"]      = _prompt(f"  Notes [{d.get('notes','')}]: ") or d.get("notes", "")
    return out


@_safe
def _award() -> None:
    print("\n  -- Award Points --")
    payload = _collect_award()
    rec = data.award_points(payload)
    print(f"  Award #{rec.award_id}: {rec.points:+d} to house #{rec.house_id}"
          + (f" (pupil {rec.pupil_id})" if rec.pupil_id else ""))
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_awards() -> None:
    rows = data.list_awards(limit=50)
    print(f"\n  {len(rows)} recent award(s):")
    _print_awards(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _filter_awards() -> None:
    hid_raw = _prompt("  House ID (blank for any): ").strip()
    hid: int | None = None
    if hid_raw:
        if not hid_raw.isdigit():
            print("  House ID must be an integer.")
            return
        hid = int(hid_raw)
    pid = _prompt("  Pupil ID (blank for any): ").strip() or None
    by = _prompt("  Awarded by contains (blank for any): ").strip() or None
    fr = _prompt("  From date YYYY-MM-DD (blank): ").strip() or None
    to = _prompt("  To date YYYY-MM-DD (blank): ").strip() or None
    rows = data.list_awards(house_id=hid, pupil_id=pid, awarded_by=by,
                            from_date=fr, to_date=to, limit=200)
    print(f"\n  {len(rows)} award(s):")
    _print_awards(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _pupil_leaderboard() -> None:
    hid_raw = _prompt("  Limit to house ID (blank for all): ").strip()
    hid: int | None = None
    if hid_raw:
        if not hid_raw.isdigit():
            print("  House ID must be an integer.")
            return
        hid = int(hid_raw)
    lim_raw = _prompt("  Top N (blank for 20): ").strip()
    limit = int(lim_raw) if lim_raw.isdigit() else 20
    rows = data.pupil_totals(house_id=hid, limit=limit)
    print(f"\n  Top {len(rows)} pupil(s):")
    if not rows:
        print("    (none)")
    else:
        print(f"  {'Rank':<5} {'Pupil ID':<10} {'Total':<6} {'Awards':<6}")
        print(f"  {'-'*5} {'-'*10} {'-'*6} {'-'*6}")
        for rank, (pid, total, n) in enumerate(rows, 1):
            print(f"  {rank:<5} {pid:<10} {total:+5d}   {n:<6}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _pupil_total() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    total = data.pupil_total(pid)
    print(f"  Pupil {pid} total: {total:+d}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _update_award() -> None:
    raw = _prompt("  Award ID to update: ")
    if not raw or not raw.isdigit():
        return
    existing = data.get_award(int(raw))
    if existing is None:
        print(f"  No award #{raw}")
        return
    defaults = {
        "house_id": existing.house_id,
        "pupil_id": existing.pupil_id or "",
        "points": existing.points,
        "reason": existing.reason or "",
        "awarded_by": existing.awarded_by or "",
        "awarded_on": existing.awarded_on,
        "notes": existing.notes or "",
    }
    payload = _collect_award(defaults)
    rec = data.update_award(int(raw), payload)
    print(f"  Updated award #{rec.award_id}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete_award() -> None:
    raw = _prompt("  Award ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete award #{raw}? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    ok = data.delete_award(int(raw))
    print(f"  {'Deleted' if ok else 'No such award'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"House Points": open_house_points}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching house_points CLI label: %s", label)
    handler()
    return True
