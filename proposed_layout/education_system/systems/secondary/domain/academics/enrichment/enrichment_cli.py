"""CLI handlers for enrichment / clubs."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.secondary.domain.academics.enrichment import (
    enrichment as data,
)
from education_system.systems.secondary.domain.academics.enrichment.enrichment import (
    CLUB_CATEGORIES, DAYS_OF_WEEK, MEMBERSHIP_STATUSES,
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


def _print_clubs(rows: list[data.Club]) -> None:
    if not rows:
        print("  (no clubs)")
        return
    print(f"  {'ID':<4} {'Name':<26} {'Cat':<10} {'Day':<4} "
          f"{'Time':<13} {'Room':<8} {'Leader':<16} "
          f"{'Cap':<5} {'Yrs':<14} {'Active':<6}")
    print(f"  {'-'*4} {'-'*26} {'-'*10} {'-'*4} {'-'*13} {'-'*8} "
          f"{'-'*16} {'-'*5} {'-'*14} {'-'*6}")
    for c in rows:
        timestr = ("-" if not c.start_time
                   else f"{c.start_time}-{c.end_time or '?'}")
        print(f"  {c.club_id:<4} {c.name[:26]:<26} "
              f"{c.category[:10]:<10} {(c.day_of_week or '-'):<4} "
              f"{timestr:<13} {(c.room or '-')[:8]:<8} "
              f"{(c.leader or '-')[:16]:<16} "
              f"{(str(c.max_capacity) if c.max_capacity else '-'):<5} "
              f"{(c.eligible_years or 'all')[:14]:<14} "
              f"{('Y' if c.is_active else 'N'):<6}")


def _print_memberships(rows: list[data.ClubMembership]) -> None:
    if not rows:
        print("  (no memberships)")
        return
    print(f"  {'ID':<5} {'Pupil':<12} {'Joined':<10} {'Status':<10} "
          f"{'Club':<24} {'Notes':<24}")
    print(f"  {'-'*5} {'-'*12} {'-'*10} {'-'*10} {'-'*24} {'-'*24}")
    for m in rows:
        print(f"  {m.membership_id:<5} {m.pupil_id:<12} "
              f"{m.joined_date:<10} {m.status:<10} "
              f"{(m.club_name or '-')[:24]:<24} "
              f"{(m.notes or '-')[:24]:<24}")


@_safe
def open_enrichment() -> None:
    logger.debug("CLI: open_enrichment")
    while True:
        o = data.overview()
        print("\n  ── Enrichment & Clubs ──")
        print(f"  Clubs: {o['total']}   active: {o['active']}   "
              f"active memberships: {o['active_memberships']}")
        print("\n   1) New club")
        print("   2) List clubs")
        print("   3) Edit club")
        print("   4) Toggle club active")
        print("   5) Club summary + memberships")
        print("   6) Pupil club history")
        print("   7) Add pupil to a club")
        print("   8) Set membership status")
        print("   9) Delete membership")
        print("  10) Delete club")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new_club, "2": _list_clubs, "3": _edit_club,
            "4": _toggle_club, "5": _club_summary,
            "6": _pupil_history, "7": _join, "8": _set_status,
            "9": _delete_membership, "10": _delete_club,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect_club(existing: data.Club | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")

    f: dict[str, Any] = {}
    f["name"]        = ask("Name", existing.name if existing else None)
    f["category"]    = ask(f"Category ({'/'.join(CLUB_CATEGORIES)})",
                            existing.category if existing else "Other")
    f["description"] = ask("Description",
                            existing.description if existing else None)
    f["day_of_week"] = ask(f"Day ({'/'.join(DAYS_OF_WEEK)}, blank ok)",
                            existing.day_of_week if existing else None)
    f["start_time"]  = ask("Start time (HH:MM)",
                            existing.start_time if existing else None)
    f["end_time"]    = ask("End time (HH:MM)",
                            existing.end_time if existing else None)
    f["room"]        = ask("Room",
                            existing.room if existing else None)
    f["leader"]      = ask("Leader",
                            existing.leader if existing else None)
    f["max_capacity"] = ask("Max capacity (blank for no limit)",
                             existing.max_capacity if existing else None)
    f["eligible_years"] = ask(
        "Eligible years (comma-separated, blank = all)",
        existing.eligible_years if existing else None)
    if existing:
        act = ask("Active? (y/n)",
                  "y" if existing.is_active else "n")
        f["is_active"] = act.lower().startswith("y")
    f["notes"] = ask("Notes", existing.notes if existing else None)
    return f


@_safe
def _new_club() -> None:
    print("\n  ── New Club ──")
    fields = _collect_club()
    c = data.create_club(fields)
    print(f"  Created club #{c.club_id} {c.name}")


@_safe
def _list_clubs() -> None:
    only = _prompt("  Active only? (y/N): ").lower().startswith("y")
    cat = _prompt(
        f"  Category ({'/'.join(CLUB_CATEGORIES)}, blank): ") or None
    day = _prompt(
        f"  Day ({'/'.join(DAYS_OF_WEEK)}, blank): ") or None
    rows = data.list_clubs(active_only=only, category=cat,
                            day_of_week=day)
    print(f"\n  {len(rows)} club(s):")
    _print_clubs(rows)
    _prompt("\n  Press Enter to continue...")


def _ask_club_id() -> int | None:
    raw = _prompt("  Club ID: ")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print("  Club ID must be a number.")
        return None


@_safe
def _edit_club() -> None:
    cid = _ask_club_id()
    if cid is None:
        return
    existing = data.get_club(cid)
    if existing is None:
        print("  No club with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_club(existing)
    c = data.update_club(cid, fields)
    print(f"  Updated club #{c.club_id} (active={c.is_active})")


@_safe
def _toggle_club() -> None:
    cid = _ask_club_id()
    if cid is None:
        return
    c = data.toggle_active(cid)
    print(f"  {c.name} is now "
          f"{'active' if c.is_active else 'inactive'}.")


@_safe
def _club_summary() -> None:
    cid = _ask_club_id()
    if cid is None:
        return
    s = data.club_summary(cid)
    c = s["club"]
    print(f"\n  ── {c.name} ──")
    print(f"  Category: {c.category}    Day: {c.day_of_week or '-'}    "
          f"Time: {c.start_time or '-'}–{c.end_time or '-'}")
    print(f"  Leader: {c.leader or '-'}    Room: {c.room or '-'}    "
          f"Eligible years: {c.eligible_years or 'all'}")
    print(f"  Total memberships: {s['total']}    "
          f"Active: {s['active']}    "
          f"Capacity: {s['capacity'] if s['capacity'] is not None else '-'}    "
          f"Spaces: {s['spaces'] if s['spaces'] is not None else '-'}")
    print("  By status: "
          + "   ".join(f"{k}: {v}" for k, v in s["by_status"].items()))
    rows = data.list_memberships(cid)
    print("\n  Members:")
    _print_memberships(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _pupil_history() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    status = _prompt(
        f"  Status ({'/'.join(MEMBERSHIP_STATUSES)}, blank): ") or None
    rows = data.memberships_for_pupil(pid, status=status)
    print(f"\n  {len(rows)} membership(s) for {pid}:")
    _print_memberships(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _join() -> None:
    cid = _ask_club_id()
    if cid is None:
        return
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    jdate = _prompt("  Joined date (YYYY-MM-DD, blank = today): ") or None
    notes = _prompt("  Notes (blank ok): ") or None
    m = data.join_club(cid, pid, joined_date=jdate, notes=notes)
    print(f"  Membership #{m.membership_id}: {m.pupil_id} -> "
          f"{m.club_name} ({m.status})")


@_safe
def _set_status() -> None:
    raw = _prompt("  Membership ID: ")
    if not raw:
        return
    try:
        mid = int(raw)
    except ValueError:
        print("  Membership ID must be a number.")
        return
    m = data.get_membership(mid)
    if m is None:
        print("  No membership with that ID.")
        return
    print(f"  Current: {m.status}")
    print(f"  Allowed: {', '.join(MEMBERSHIP_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    m = data.set_membership_status(mid, new)
    print(f"  Status now: {m.status}")


@_safe
def _delete_membership() -> None:
    raw = _prompt("  Membership ID: ")
    if not raw:
        return
    try:
        mid = int(raw)
    except ValueError:
        print("  Membership ID must be a number.")
        return
    m = data.get_membership(mid)
    if m is None:
        print("  No membership with that ID.")
        return
    confirm = _prompt(
        f"  Delete membership of {m.pupil_id} from "
        f"{m.club_name}? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_membership(mid)
    print(f"  Deleted membership #{mid}.")


@_safe
def _delete_club() -> None:
    cid = _ask_club_id()
    if cid is None:
        return
    c = data.get_club(cid)
    if c is None:
        print("  No club with that ID.")
        return
    confirm = _prompt(
        f"  Delete club {c.name} and all its memberships? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_club(cid):
        print(f"  Deleted club #{cid}.")


_DISPATCH = {"Enrichment & Clubs": open_enrichment}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching enrichment CLI label: %s", label)
    handler()
    return True
