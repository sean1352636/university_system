"""CLI handlers for leavers in the Primary School System."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.primarysch_system.modules.domain.pupils.leavers import (
    leavers as data,
)
from education_system.primarysch_system.modules.domain.pupils.leavers.leavers import (
    Leaver, STATUSES,
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


def _print_table(rows: list[Leaver]) -> None:
    if not rows:
        print("  (no leavers)")
        return
    print(f"  {'Leaver ID':<11} {'Name':<24} {'Year':<5} "
          f"{'Left':<11} {'Destination':<22} {'Status':<8}")
    print(f"  {'-'*11} {'-'*24} {'-'*5} {'-'*11} {'-'*22} {'-'*8}")
    for r in rows:
        print(f"  {r.leaver_id:<11} {r.full_name[:24]:<24} "
              f"{r.year_left:<5} {(r.leaving_date or '-'):<11} "
              f"{(r.destination_school or '-')[:22]:<22} {r.status:<8}")


def _print_counts() -> None:
    c = data.status_counts()
    total = sum(c.values())
    print(f"  Total: {total}   "
          + "   ".join(f"{s.title()}: {c[s]}" for s in STATUSES))


@_safe
def open_leavers() -> None:
    logger.debug("CLI: open_leavers")
    while True:
        print("\n  -- Leavers --")
        _print_counts()
        print("\n   1) List all leavers")
        print("   2) Filter by status / year")
        print("   3) Search leavers")
        print("   4) View leaver details")
        print("   5) Add leaver (manual entry)")
        print("   6) Promote pupil to leaver")
        print("   7) Update leaver")
        print("   8) Change status")
        print("   9) Delete leaver")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_all,
            "2": _list_filtered,
            "3": _search,
            "4": _view,
            "5": _add,
            "6": _promote,
            "7": _update,
            "8": _change_status,
            "9": _delete,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _list_all() -> None:
    rows = data.list_leavers()
    print(f"\n  {len(rows)} leaver(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_filtered() -> None:
    print(f"  Statuses: {', '.join(STATUSES)} (or blank)")
    status = _prompt("  Status: ").strip().lower() or None
    print(f"  Year groups: {', '.join(YEAR_GROUPS)} (or blank)")
    yl = _prompt("  Year left: ").strip() or None
    rows = data.list_leavers(status=status, year_left=yl)
    print(f"\n  {len(rows)} leaver(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _search() -> None:
    q = _prompt("  Search term: ")
    if not q:
        return
    rows = data.search_leavers(q)
    print(f"\n  {len(rows)} match(es):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view() -> None:
    lid = _prompt("  Leaver ID: ")
    if not lid:
        return
    rec = data.get_leaver(lid)
    if rec is None:
        print(f"  No leaver with id {lid}")
        return
    print(f"\n  -- Leaver {rec.leaver_id} --")
    print(f"  Name:          {rec.full_name}")
    print(f"  Pupil ID:      {rec.pupil_id or '-'}")
    print(f"  DOB:           {rec.date_of_birth or '-'}")
    print(f"  Year left:     {rec.year_left}")
    print(f"  Leaving date:  {rec.leaving_date or '-'}")
    print(f"  Destination:   {rec.destination_school or '-'}")
    print(f"  Email:         {rec.current_email or '-'}")
    print(f"  Parent phone:  {rec.parent_phone or '-'}")
    print(f"  Reason:        {rec.reason or '-'}")
    print(f"  Status:        {rec.status}")
    print(f"  Notes:         {rec.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


def _collect_fields(defaults: dict | None = None) -> dict:
    d = defaults or {}
    print(f"  (Year groups: {', '.join(YEAR_GROUPS)})")
    out: dict = {}
    out["first_name"] = _prompt(f"  First name [{d.get('first_name','')}]: ") or d.get("first_name", "")
    out["last_name"]  = _prompt(f"  Last name  [{d.get('last_name','')}]: ")  or d.get("last_name", "")
    out["year_left"]  = _prompt(f"  Year left  [{d.get('year_left','')}]: ")  or d.get("year_left", "")
    out["date_of_birth"] = _prompt(f"  DOB YYYY-MM-DD [{d.get('date_of_birth','')}]: ") or d.get("date_of_birth", "")
    out["leaving_date"]  = _prompt(f"  Leaving date YYYY-MM-DD [{d.get('leaving_date','')}]: ") or d.get("leaving_date", "")
    out["destination_school"] = _prompt(f"  Destination school [{d.get('destination_school','')}]: ") or d.get("destination_school", "")
    out["current_email"] = _prompt(f"  Email [{d.get('current_email','')}]: ") or d.get("current_email", "")
    out["parent_phone"]  = _prompt(f"  Parent phone [{d.get('parent_phone','')}]: ") or d.get("parent_phone", "")
    out["reason"]        = _prompt(f"  Reason [{d.get('reason','')}]: ") or d.get("reason", "")
    out["status"]        = _prompt(f"  Status active/inactive [{d.get('status','active')}]: ") or d.get("status", "active")
    out["notes"]         = _prompt(f"  Notes [{d.get('notes','')}]: ") or d.get("notes", "")
    out["pupil_id"]      = _prompt(f"  Pupil ID (optional) [{d.get('pupil_id','')}]: ") or d.get("pupil_id", "")
    return out


@_safe
def _add() -> None:
    print("\n  -- Add Leaver (manual entry) --")
    payload = _collect_fields()
    rec = data.create_leaver(payload)
    print(f"  Created leaver {rec.leaver_id} for {rec.full_name}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _promote() -> None:
    print("\n  -- Promote Pupil to Leaver --")
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    dest = _prompt("  Destination school (optional): ")
    email = _prompt("  Current email (optional): ")
    reason = _prompt("  Reason (optional): ")
    notes = _prompt("  Notes (optional): ")
    leaving_date = _prompt("  Leaving date YYYY-MM-DD (blank for today): ")
    confirm = _prompt(
        f"  Promote pupil {pid} to leaver and delete pupil record? (y/N): "
    )
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    extras = {
        "destination_school": dest,
        "current_email": email,
        "reason": reason,
        "notes": notes,
        "leaving_date": leaving_date,
    }
    rec = data.promote_from_pupil(pid, extras=extras)
    print(f"  Created leaver {rec.leaver_id} for {rec.full_name}; "
          f"pupil {pid} removed.")
    _prompt("\n  Press Enter to continue...")


@_safe
def _update() -> None:
    lid = _prompt("  Leaver ID to update: ")
    if not lid:
        return
    existing = data.get_leaver(lid)
    if existing is None:
        print(f"  No leaver with id {lid}")
        return
    defaults = {
        "first_name": existing.first_name,
        "last_name": existing.last_name,
        "year_left": existing.year_left,
        "date_of_birth": existing.date_of_birth or "",
        "leaving_date": existing.leaving_date or "",
        "destination_school": existing.destination_school or "",
        "current_email": existing.current_email or "",
        "parent_phone": existing.parent_phone or "",
        "reason": existing.reason or "",
        "status": existing.status,
        "notes": existing.notes or "",
        "pupil_id": existing.pupil_id or "",
    }
    payload = _collect_fields(defaults)
    rec = data.update_leaver(lid, payload)
    print(f"  Updated leaver {rec.leaver_id} ({rec.full_name})")
    _prompt("\n  Press Enter to continue...")


@_safe
def _change_status() -> None:
    lid = _prompt("  Leaver ID: ")
    if not lid:
        return
    print(f"  Statuses: {', '.join(STATUSES)}")
    new = _prompt("  New status: ").strip().lower()
    if not new:
        return
    rec = data.set_status(lid, new)
    print(f"  Leaver {rec.leaver_id} -> {rec.status}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    lid = _prompt("  Leaver ID to delete: ")
    if not lid:
        return
    confirm = _prompt(f"  Delete leaver {lid}? Type 'DELETE' to confirm: ")
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    ok = data.delete_leaver(lid)
    if ok:
        print(f"  Deleted leaver {lid}.")
    else:
        print(f"  No leaver with id {lid}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Leavers": open_leavers}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching leavers CLI label: %s", label)
    handler()
    return True
