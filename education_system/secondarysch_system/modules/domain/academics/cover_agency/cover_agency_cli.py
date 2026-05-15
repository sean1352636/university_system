"""CLI handlers for cover-agency staff and bookings."""

from __future__ import annotations

import datetime as _dt
import functools
import logging
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.academics.cover_agency import (
    cover_agency as data,
)
from education_system.secondarysch_system.modules.domain.academics.cover_agency.cover_agency import (
    BOOKING_STATUSES, MIN_PERIOD, MAX_PERIOD,
)
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
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


def _today() -> str:
    return _dt.date.today().isoformat()


def _print_staff(rows: list[data.AgencyStaff]) -> None:
    if not rows:
        print("  (no staff)")
        return
    print(f"  {'ID':<4} {'Name':<22} {'Agency':<18} {'Role':<14} "
          f"{'Rate':<7} {'DBS':<4} {'Active':<6}")
    print(f"  {'-'*4} {'-'*22} {'-'*18} {'-'*14} {'-'*7} {'-'*4} {'-'*6}")
    for s in rows:
        rate = f"£{s.hourly_rate:.2f}" if s.hourly_rate is not None else "-"
        print(f"  {s.staff_id:<4} {s.full_name[:22]:<22} "
              f"{(s.agency_name or '-')[:18]:<18} "
              f"{(s.role or '-')[:14]:<14} {rate:<7} "
              f"{('Y' if s.dbs_cleared else 'N'):<4} "
              f"{('Y' if s.is_active else 'N'):<6}")


def _print_bookings(rows: list[data.AgencyBooking]) -> None:
    if not rows:
        print("  (no bookings)")
        return
    print(f"  {'ID':<4} {'Date':<10} {'P':<2} {'Staff':<22} "
          f"{'Agency':<18} {'Cov#':<5} {'Rate':<7} {'Status':<10}")
    print(f"  {'-'*4} {'-'*10} {'-'*2} {'-'*22} {'-'*18} {'-'*5} {'-'*7} "
          f"{'-'*10}")
    for b in rows:
        rate = f"£{b.rate_charged:.2f}" if b.rate_charged is not None else "-"
        print(f"  {b.booking_id:<4} {b.date:<10} {b.period:<2} "
              f"{(b.staff_name or '?')[:22]:<22} "
              f"{(b.agency_name or '-')[:18]:<18} "
              f"{(str(b.cover_id) if b.cover_id else '-'):<5} "
              f"{rate:<7} {b.status:<10}")


@_safe
def open_cover_agency() -> None:
    logger.debug("CLI: open_cover_agency")
    while True:
        s = data.staff_summary()
        print("\n  ── Cover Agency ──")
        print(f"  Staff: {s['total']}  active: {s['active']}  "
              f"DBS-cleared: {s['dbs']}  agencies: {s['agencies']}")
        print("  Bookings: "
              + "   ".join(f"{k}: {v}" for k, v in s["bookings"].items()))
        print("\n  Staff")
        print("    1) Add staff")
        print("    2) List staff")
        print("    3) Edit staff")
        print("    4) Toggle active")
        print("    5) Delete staff")
        print("  Bookings")
        print("    6) New booking")
        print("    7) List bookings")
        print("    8) Set booking status")
        print("    9) Delete booking")
        print("    0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new_staff,
            "2": _list_staff,
            "3": _edit_staff,
            "4": _toggle_staff,
            "5": _delete_staff,
            "6": _new_booking,
            "7": _list_bookings,
            "8": _set_booking_status,
            "9": _delete_booking,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect_staff(existing: data.AgencyStaff | None = None
                   ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")

    f: dict[str, Any] = {}
    f["full_name"]     = ask("Full name",
                              existing.full_name if existing else None)
    f["agency_name"]   = ask("Agency",
                              existing.agency_name if existing else None)
    f["role"]          = ask("Role (e.g. Cover supervisor)",
                              existing.role if existing else None)
    f["hourly_rate"]   = ask("Hourly rate (£)",
                              existing.hourly_rate if existing else None)
    f["contact_email"] = ask("Contact email",
                              existing.contact_email if existing else None)
    f["contact_phone"] = ask("Contact phone",
                              existing.contact_phone if existing else None)
    dbs = ask("DBS cleared? (y/n)",
              "y" if existing and existing.dbs_cleared else "n")
    f["dbs_cleared"] = dbs.lower().startswith("y")
    if existing:
        act = ask("Active? (y/n)",
                  "y" if existing.is_active else "n")
        f["is_active"] = act.lower().startswith("y")
    else:
        f["is_active"] = True
    f["notes"] = ask("Notes", existing.notes if existing else None)
    return f


@_safe
def _new_staff() -> None:
    print("\n  ── Add Agency Staff ──")
    fields = _collect_staff()
    rec = data.create_staff(fields)
    print(f"  Added staff #{rec.staff_id} {rec.full_name} "
          f"({rec.agency_name or '-'}, DBS={rec.dbs_cleared})")


@_safe
def _list_staff() -> None:
    only_active = _prompt("  Active only? (y/N): ").lower().startswith("y")
    agency = _prompt("  Agency (blank for all): ") or None
    rows = data.list_staff(active_only=only_active, agency_name=agency)
    print(f"\n  {len(rows)} staff member(s):")
    _print_staff(rows)
    _prompt("\n  Press Enter to continue...")


def _ask_staff_id() -> int | None:
    raw = _prompt("  Staff ID: ")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print("  Staff ID must be a number.")
        return None


@_safe
def _edit_staff() -> None:
    sid = _ask_staff_id()
    if sid is None:
        return
    existing = data.get_staff(sid)
    if existing is None:
        print("  No staff with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_staff(existing)
    rec = data.update_staff(sid, fields)
    print(f"  Updated staff #{rec.staff_id} {rec.full_name} "
          f"(active={rec.is_active})")


@_safe
def _toggle_staff() -> None:
    sid = _ask_staff_id()
    if sid is None:
        return
    rec = data.toggle_active(sid)
    print(f"  {rec.full_name} is now "
          f"{'active' if rec.is_active else 'inactive'}.")


@_safe
def _delete_staff() -> None:
    sid = _ask_staff_id()
    if sid is None:
        return
    existing = data.get_staff(sid)
    if existing is None:
        print("  No staff with that ID.")
        return
    confirm = _prompt(
        f"  Delete staff #{sid} {existing.full_name}? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_staff(sid):
        print(f"  Deleted staff #{sid}.")


def _collect_booking(existing: data.AgencyBooking | None = None
                     ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")

    f: dict[str, Any] = {}
    if not existing:
        print("  Active DBS-cleared staff:")
        for s in data.list_staff(active_only=True):
            if s.dbs_cleared:
                print(f"    #{s.staff_id:<4} {s.full_name} "
                      f"({s.agency_name or '-'})")
    f["staff_id"]     = ask("Staff ID",
                             existing.staff_id if existing else None)
    f["date"]         = ask("Date (YYYY-MM-DD)",
                             existing.date if existing else _today())
    f["period"]       = ask(f"Period ({MIN_PERIOD}-{MAX_PERIOD})",
                             existing.period if existing else None)
    f["cover_id"]     = ask("Cover arrangement ID (blank ok)",
                             existing.cover_id if existing else None)
    f["rate_charged"] = ask("Rate charged (£, blank ok)",
                             existing.rate_charged if existing else None)
    f["status"]       = ask(f"Status ({'/'.join(BOOKING_STATUSES)})",
                             existing.status if existing else "Booked")
    f["notes"]        = ask("Notes",
                             existing.notes if existing else None)
    return f


@_safe
def _new_booking() -> None:
    print("\n  ── New Booking ──")
    fields = _collect_booking()
    b = data.create_booking(fields)
    print(f"  Booked #{b.booking_id}: {b.staff_name} on "
          f"{b.date} P{b.period} status={b.status}")


@_safe
def _list_bookings() -> None:
    date = _prompt("  Date (YYYY-MM-DD, blank for all): ") or None
    sid_raw = _prompt("  Staff ID (blank for all): ")
    staff_id = None
    if sid_raw:
        try:
            staff_id = int(sid_raw)
        except ValueError:
            print("  Staff ID must be a number.")
            return
    print(f"  Status ({'/'.join(BOOKING_STATUSES)}) or blank.")
    status = _prompt("  Status: ") or None
    rows = data.list_bookings(date=date, staff_id=staff_id, status=status)
    print(f"\n  {len(rows)} booking(s):")
    _print_bookings(rows)
    _prompt("\n  Press Enter to continue...")


def _ask_booking_id() -> int | None:
    raw = _prompt("  Booking ID: ")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print("  Booking ID must be a number.")
        return None


@_safe
def _set_booking_status() -> None:
    bid = _ask_booking_id()
    if bid is None:
        return
    b = data.get_booking(bid)
    if b is None:
        print("  No booking with that ID.")
        return
    print(f"  Current: {b.status}")
    print(f"  Allowed: {', '.join(BOOKING_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    b = data.set_booking_status(bid, new)
    print(f"  Status now: {b.status}")


@_safe
def _delete_booking() -> None:
    bid = _ask_booking_id()
    if bid is None:
        return
    b = data.get_booking(bid)
    if b is None:
        print("  No booking with that ID.")
        return
    confirm = _prompt(
        f"  Delete booking #{bid} ({b.staff_name} on "
        f"{b.date} P{b.period})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_booking(bid):
        print(f"  Deleted booking #{bid}.")


_DISPATCH = {"Cover Agency": open_cover_agency}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching cover_agency CLI label: %s", label)
    handler()
    return True
