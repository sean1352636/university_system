"""CLI handlers for alumni in the Secondary School System."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.secondary.domain.learners.alumni import (
    alumni as data,
)
from education_system.systems.secondary.domain.learners.alumni.alumni import (
    STATUSES,
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


def _print_table(rows: list[data.Alumnus]) -> None:
    if not rows:
        print("  (no alumni)")
        return
    print(f"  {'ID':<12} {'Left':<10} {'Yr':<3} {'Name':<26} "
          f"{'Status':<9} {'Pupil':<10} {'Destination':<24}")
    print(f"  {'-'*12} {'-'*10} {'-'*3} {'-'*26} {'-'*9} {'-'*10} {'-'*24}")
    for a in rows:
        print(f"  {a.alumni_id:<12} {(a.leaving_date or '-'):<10} "
              f"{a.year_left:<3} {a.full_name[:26]:<26} "
              f"{a.status:<9} {(a.pupil_id or '-'):<10} "
              f"{(a.destination or '-')[:24]:<24}")


def _print_detail(a: data.Alumnus) -> None:
    print(f"\n  ── Alumnus {a.alumni_id} ──")
    print(f"  Name:            {a.full_name}")
    print(f"  Date of birth:   {a.date_of_birth or '-'}")
    print(f"  Year left:       {a.year_left}")
    print(f"  Leaving date:    {a.leaving_date or '-'}")
    print(f"  Status:          {a.status}")
    print(f"  Pupil ID:        {a.pupil_id or '-'}")
    print(f"  Current email:   {a.current_email or '-'}")
    print(f"  Current phone:   {a.current_phone or '-'}")
    print(f"  Destination:     {a.destination or '-'}")
    print(f"  Employer:        {a.employer or '-'}")
    print(f"  Notes:           {a.notes or '-'}")


def _collect_fields(existing: data.Alumnus | None = None) -> dict[str, str]:
    def ask(label: str, current: str | None = None) -> str:
        suffix = f" [{current}]" if current else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (current or "")
    f: dict[str, str] = {}
    f["first_name"]    = ask("First name",
                             existing.first_name if existing else None)
    f["last_name"]     = ask("Last name",
                             existing.last_name  if existing else None)
    f["date_of_birth"] = ask("Date of birth (YYYY-MM-DD)",
                             existing.date_of_birth if existing else None)
    f["year_left"]     = ask(
        f"Year left ({'/'.join(YEAR_GROUPS)})",
        existing.year_left if existing else None,
    )
    f["leaving_date"]  = ask("Leaving date (YYYY-MM-DD)",
                             existing.leaving_date if existing else None)
    f["pupil_id"]      = ask("Pupil ID (optional)",
                             existing.pupil_id if existing else None)
    f["current_email"] = ask("Current email",
                             existing.current_email if existing else None)
    f["current_phone"] = ask("Current phone",
                             existing.current_phone if existing else None)
    f["destination"]   = ask("Destination (university / college / ...)",
                             existing.destination if existing else None)
    f["employer"]      = ask("Employer",
                             existing.employer if existing else None)
    f["status"]        = ask(
        f"Status ({'/'.join(STATUSES)})",
        existing.status if existing else "active",
    )
    f["notes"]         = ask("Notes",
                             existing.notes if existing else None)
    return f


@_safe
def open_alumni() -> None:
    logger.debug("CLI: open_alumni")
    while True:
        counts = data.status_counts()
        total = sum(counts.values())
        print("\n  ── Alumni ──")
        print(f"  Total: {total}   "
              + "   ".join(f"{s}: {counts[s]}" for s in STATUSES))
        print("\n   1) New alumnus")
        print("   2) List alumni")
        print("   3) Search alumni")
        print("   4) View alumnus")
        print("   5) Edit alumnus")
        print("   6) Set status")
        print("   7) Promote pupil to alumnus")
        print("   8) Delete alumnus")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _new_alumnus,
            "2": _list_alumni,
            "3": _search_alumni,
            "4": _view_alumnus,
            "5": _edit_alumnus,
            "6": _set_status,
            "7": _promote_pupil,
            "8": _delete_alumnus,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _new_alumnus() -> None:
    logger.debug("CLI: alumni new")
    print("\n  ── New Alumnus ──")
    fields = _collect_fields()
    a = data.create_alumnus(fields)
    print(f"\n  Created alumnus {a.alumni_id} for "
          f"{a.full_name} (year left {a.year_left})")


@_safe
def _list_alumni() -> None:
    logger.debug("CLI: alumni list")
    print("\n  ── List Alumni ──")
    print(f"  Status filter ({'/'.join(STATUSES)}) — blank for all.")
    status = _prompt("  Status: ") or None
    print(f"  Year-left filter ({'/'.join(YEAR_GROUPS)}) — blank for all.")
    year = _prompt("  Year: ") or None
    rows = data.list_alumni(status=status, year_left=year)
    print(f"\n  {len(rows)} alumnus(i):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _search_alumni() -> None:
    q = _prompt("  Search (name / ID / email / destination / employer): ")
    if not q:
        return
    rows = data.search_alumni(q)
    print(f"\n  {len(rows)} match(es):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view_alumnus() -> None:
    aid = _prompt("  Alumni ID: ")
    if not aid:
        return
    a = data.get_alumnus(aid)
    if a is None:
        print("  No alumnus with that ID.")
        return
    _print_detail(a)
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit_alumnus() -> None:
    aid = _prompt("  Alumni ID: ")
    if not aid:
        return
    existing = data.get_alumnus(aid)
    if existing is None:
        print("  No alumnus with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_fields(existing)
    a = data.update_alumnus(aid, fields)
    print(f"\n  Updated alumnus {a.alumni_id} ({a.full_name})")


@_safe
def _set_status() -> None:
    aid = _prompt("  Alumni ID: ")
    if not aid:
        return
    a = data.get_alumnus(aid)
    if a is None:
        print("  No alumnus with that ID.")
        return
    print(f"  Current status: {a.status}")
    print(f"  Allowed: {', '.join(STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    a = data.set_status(aid, new)
    print(f"  Status now: {a.status}")


@_safe
def _promote_pupil() -> None:
    pid = _prompt("  Pupil ID to promote: ")
    if not pid:
        return
    print("  Optional extras (blank to skip):")
    extras: dict[str, str] = {}
    for key, label in [
        ("leaving_date",  "Leaving date (YYYY-MM-DD)"),
        ("current_email", "Current email"),
        ("destination",   "Destination"),
        ("employer",      "Employer"),
        ("notes",         "Notes"),
    ]:
        v = _prompt(f"  {label}: ")
        if v:
            extras[key] = v
    a = data.promote_from_pupil(pid, extras=extras or None)
    print(f"\n  Promoted pupil {pid} -> alumnus {a.alumni_id} "
          f"({a.full_name})")


@_safe
def _delete_alumnus() -> None:
    aid = _prompt("  Alumni ID: ")
    if not aid:
        return
    existing = data.get_alumnus(aid)
    if existing is None:
        print("  No alumnus with that ID.")
        return
    confirm = _prompt(
        f"  Delete alumnus {aid} ({existing.full_name})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_alumnus(aid):
        print(f"  Deleted alumnus {aid}.")
    else:
        print("  Could not delete.")


_DISPATCH = {"Alumni": open_alumni}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching alumni CLI label: %s", label)
    handler()
    return True
