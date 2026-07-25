"""CLI flow for Sessions & Bookings (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.operations.sessions import sessions as data
from education_system.systems.nursery.domain.operations.sessions.sessions import (
    BOOKING_KINDS,
    CLOSURE_TYPES,
    FUNDING_TYPES,
    SESSION_TYPES,
    WEEKDAYS,
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
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _ask(label: str, current=None) -> str:
    cur = "" if current is None else str(current)
    suffix = f" [{cur}]" if cur else ""
    v = _prompt(f"  {label}{suffix}: ")
    return v if v else cur


def _ask_bool(label: str, current: bool | None) -> str:
    cur = "" if current is None else ("y" if current else "n")
    suffix = f" [{cur}]" if cur else ""
    v = _prompt(f"  {label} (y/n){suffix}: ").lower()
    return v if v else cur


def _show_children() -> None:
    try:
        choices = data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return
    if choices:
        print("  Children:")
        for _id, label in choices:
            print(f"    {label}")


def _yn(flag: bool) -> str:
    return "Yes" if flag else "No"


# ── Day view ─────────────────────────────────────────────────────────────────

def _print_day(day: str) -> None:
    s = data.summary(day)
    print(f"\n  ── Sessions on {s['date']} ──")
    if s["closed"]:
        print("  SETTING CLOSED — " + ", ".join(s["closure_names"]))
        return
    print(f"  Children booked: {s['booked_children']}   "
          f"Sessions: {s['booked_sessions']}   Extras: {s['extras']}   "
          f"Cancellations: {s['cancellations']}   "
          f"Hours: {s['booked_hours']}")
    sessions = data.day_sessions(day)
    if not sessions:
        print("  (nobody booked in)")
    else:
        print(f"  {'Child':<24} {'Session':<9} {'Times':<14} {'Room':<16} "
              f"{'Source'}")
        print(f"  {'-'*24} {'-'*9} {'-'*14} {'-'*16} {'-'*10}")
        for x in sessions:
            times = f"{x.start_time or '-'}–{x.end_time or '-'}"
            print(f"  {(x.child_name or x.pupil_id)[:24]:<24} "
                  f"{x.session_type:<9} {times:<14} "
                  f"{(x.room or '-')[:16]:<16} {x.source}")
    rooms = data.room_day_capacity(day)
    if rooms:
        print("\n  Capacity:")
        for r in rooms:
            flag = "  OVER CAPACITY" if r.over_capacity else ""
            cap = r.capacity if r.capacity else "-"
            print(f"    {r.room[:20]:<20} {r.booked} / {cap}{flag}")


@_safe
def open_manager() -> None:
    logger.debug("CLI: sessions open_manager")
    day = data._today()
    while True:
        _print_day(day)
        print("\n   D) Change date    P) Weekly patterns    B) Extras & "
              "cancellations")
        print("   C) Closures & holidays    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "d":
            day = _prompt("  Date (YYYY-MM-DD): ") or day
        elif choice == "p":
            open_patterns()
        elif choice == "b":
            open_bookings()
        elif choice == "c":
            open_closures()
        else:
            print("  Invalid selection.")


# ── Contracted weekly patterns ───────────────────────────────────────────────

def _print_patterns(rows: list[data.BookingPattern]) -> None:
    if not rows:
        print("  (no contracted patterns)")
        return
    print(f"  {'ID':<8} {'Child':<22} {'Day':<10} {'Session':<9} {'Times':<14} "
          f"{'Room':<14} {'Funding':<8} {'From':<11} {'To':<11} {'Status'}")
    print(f"  {'-'*8} {'-'*22} {'-'*10} {'-'*9} {'-'*14} {'-'*14} {'-'*8} "
          f"{'-'*11} {'-'*11} {'-'*7}")
    for p in rows:
        times = f"{p.start_time or '-'}–{p.end_time or '-'}"
        print(f"  {p.pattern_id:<8} {(p.child_name or p.pupil_id)[:22]:<22} "
              f"{p.weekday_name:<10} {p.session_type:<9} {times:<14} "
              f"{(p.room or '-')[:14]:<14} {p.funding:<8} {p.start_date:<11} "
              f"{(p.end_date or '-'):<11} {p.status}")


@_safe
def open_patterns() -> None:
    while True:
        print("\n  ── Contracted Weekly Patterns ──")
        _print_patterns(data.list_patterns())
        print("\n   A) Add    E) Edit    N) End a pattern    D) Delete")
        print("   C) Patterns for a child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add_pattern()
        elif choice == "e":
            open_edit_pattern()
        elif choice == "n":
            open_end_pattern()
        elif choice == "d":
            open_delete_pattern()
        elif choice == "c":
            pid = _prompt("  Child ID: ")
            _print_patterns(data.list_patterns(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


def _collect_pattern(existing: data.BookingPattern | None = None,
                     *, pupil_id: str | None = None) -> dict[str, str]:
    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    days = ", ".join(f"{i}={n[:3]}" for i, n in enumerate(WEEKDAYS))
    fields["weekday"] = _ask(f"Weekday ({days})",
                             existing.weekday if existing else None)
    fields["session_type"] = _ask(f"Session ({'/'.join(SESSION_TYPES)})",
                                  existing.session_type if existing else "all-day")
    fields["start_time"] = _ask("Start time (HH:MM, blank = default)",
                                existing.start_time if existing else None)
    fields["end_time"] = _ask("End time (HH:MM, blank = default)",
                              existing.end_time if existing else None)
    fields["room"] = _ask("Room (blank = the child's own room)",
                          existing.room if existing else None)
    fields["funding"] = _ask(f"Funding ({'/'.join(FUNDING_TYPES)})",
                             existing.funding if existing else "funded")
    fields["start_date"] = _ask("Start date (YYYY-MM-DD)",
                                existing.start_date if existing else data._today())
    fields["end_date"] = _ask("End date (blank = open-ended)",
                              existing.end_date if existing else None)
    fields["status"] = _ask("Status (active/ended)",
                            existing.status if existing else "active")
    fields["notes"] = _ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_add_pattern() -> None:
    print("\n  ── Add Contracted Session ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    p = data.create_pattern(_collect_pattern(pupil_id=pid))
    print(f"\n  Added pattern {p.pattern_id} — {p.child_name or pid} every "
          f"{p.weekday_name} ({p.session_type}).")


@_safe
def open_edit_pattern() -> None:
    pid = _prompt("  Pattern ID: ")
    if not pid:
        print("  Cancelled.")
        return
    existing = data.get_pattern(pid)
    if existing is None:
        print("  No pattern with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    p = data.update_pattern(pid, _collect_pattern(existing))
    print(f"\n  Updated pattern {p.pattern_id}.")


@_safe
def open_end_pattern() -> None:
    pid = _prompt("  Pattern ID to end: ")
    if not pid:
        print("  Cancelled.")
        return
    day = _prompt("  Last day (YYYY-MM-DD, blank = today): ")
    p = data.end_pattern(pid, day or None)
    print(f"  Pattern {p.pattern_id} ended on {p.end_date}.")


@_safe
def open_delete_pattern() -> None:
    pid = _prompt("  Pattern ID to delete: ")
    if not pid:
        print("  Cancelled.")
        return
    existing = data.get_pattern(pid)
    if existing is None:
        print("  No pattern with that ID.")
        return
    if _prompt(f"  Delete {existing.weekday_name} {existing.session_type} for "
               f"{existing.child_name or existing.pupil_id}? (y/N): "
               ).lower() != "y":
        print("  Cancelled.")
        return
    print(f"  Deleted pattern {pid}." if data.delete_pattern(pid)
          else "  Could not delete (already removed?).")


# ── Extras & cancellations ───────────────────────────────────────────────────

def _print_bookings(rows: list[data.SessionBooking]) -> None:
    if not rows:
        print("  (no ad-hoc bookings or cancellations)")
        return
    print(f"  {'ID':<8} {'Child':<22} {'Date':<11} {'Session':<9} {'Kind':<13} "
          f"{'Charge':<7} {'Status':<10} {'Reason'}")
    print(f"  {'-'*8} {'-'*22} {'-'*11} {'-'*9} {'-'*13} {'-'*7} {'-'*10} "
          f"{'-'*20}")
    for b in rows:
        print(f"  {b.booking_id:<8} {(b.child_name or b.pupil_id)[:22]:<22} "
              f"{b.session_date:<11} {b.session_type:<9} {b.kind:<13} "
              f"{_yn(b.chargeable):<7} {b.status:<10} {(b.reason or '-')[:24]}")


@_safe
def open_bookings() -> None:
    while True:
        print("\n  ── Extra Sessions & Cancellations ──")
        _print_bookings(data.list_bookings())
        print("\n   A) Add    E) Edit    D) Delete    C) For a child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add_booking()
        elif choice == "e":
            open_edit_booking()
        elif choice == "d":
            open_delete_booking()
        elif choice == "c":
            pid = _prompt("  Child ID: ")
            _print_bookings(data.list_bookings(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


def _collect_booking(existing: data.SessionBooking | None = None,
                     *, pupil_id: str | None = None) -> dict[str, str]:
    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["session_date"] = _ask("Date (YYYY-MM-DD)",
                                  existing.session_date if existing else data._today())
    fields["session_type"] = _ask(f"Session ({'/'.join(SESSION_TYPES)})",
                                  existing.session_type if existing else "all-day")
    fields["kind"] = _ask(f"Kind ({'/'.join(BOOKING_KINDS)})",
                          existing.kind if existing else "extra")
    fields["start_time"] = _ask("Start time (HH:MM, blank = default)",
                                existing.start_time if existing else None)
    fields["end_time"] = _ask("End time (HH:MM, blank = default)",
                              existing.end_time if existing else None)
    fields["room"] = _ask("Room", existing.room if existing else None)
    fields["chargeable"] = _ask_bool("Chargeable?",
                                     existing.chargeable if existing else None)
    fields["notice_days"] = _ask("Notice given (days)",
                                 existing.notice_days if existing else None)
    fields["reason"] = _ask("Reason", existing.reason if existing else None)
    fields["status"] = _ask("Status (confirmed/requested/declined)",
                            existing.status if existing else "confirmed")
    fields["notes"] = _ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_add_booking() -> None:
    print("\n  ── Add Extra Session / Cancellation ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    b = data.create_booking(_collect_booking(pupil_id=pid))
    print(f"\n  Logged {b.kind} {b.booking_id} for "
          f"{b.child_name or pid} on {b.session_date} ({b.session_type}).")


@_safe
def open_edit_booking() -> None:
    bid = _prompt("  Booking ID: ")
    if not bid:
        print("  Cancelled.")
        return
    existing = data.get_booking(bid)
    if existing is None:
        print("  No booking with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    b = data.update_booking(bid, _collect_booking(existing))
    print(f"\n  Updated booking {b.booking_id}.")


@_safe
def open_delete_booking() -> None:
    bid = _prompt("  Booking ID to delete: ")
    if not bid:
        print("  Cancelled.")
        return
    if data.get_booking(bid) is None:
        print("  No booking with that ID.")
        return
    if _prompt(f"  Delete booking {bid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    print(f"  Deleted booking {bid}." if data.delete_booking(bid)
          else "  Could not delete (already removed?).")


# ── Closures ─────────────────────────────────────────────────────────────────

def _print_closures(rows: list[data.Closure]) -> None:
    if not rows:
        print("  (no closures recorded)")
        return
    print(f"  {'ID':<8} {'Name':<26} {'From':<11} {'To':<11} {'Type':<13} "
          f"{'Scope':<16} {'Charged'}")
    print(f"  {'-'*8} {'-'*26} {'-'*11} {'-'*11} {'-'*13} {'-'*16} {'-'*7}")
    for c in rows:
        scope = c.room or "whole setting"
        print(f"  {c.closure_id:<8} {c.name[:26]:<26} {c.start_date:<11} "
              f"{c.end_date:<11} {c.closure_type:<13} {scope[:16]:<16} "
              f"{_yn(c.chargeable)}")


@_safe
def open_closures() -> None:
    while True:
        print("\n  ── Closures & Holidays ──")
        _print_closures(data.list_closures())
        print("\n   A) Add    E) Edit    D) Delete    U) Upcoming only    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add_closure()
        elif choice == "e":
            open_edit_closure()
        elif choice == "d":
            open_delete_closure()
        elif choice == "u":
            _print_closures(data.list_closures(date_from=data._today()))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


def _collect_closure(existing: data.Closure | None = None) -> dict[str, str]:
    fields: dict[str, str] = {}
    fields["name"] = _ask("Name", existing.name if existing else None)
    fields["start_date"] = _ask("First closed day (YYYY-MM-DD)",
                                existing.start_date if existing else None)
    fields["end_date"] = _ask("Last closed day (blank = same day)",
                              existing.end_date if existing else None)
    fields["closure_type"] = _ask(f"Type ({'/'.join(CLOSURE_TYPES)})",
                                  existing.closure_type if existing else "holiday")
    fields["room"] = _ask("Room (blank = whole setting)",
                          existing.room if existing else None)
    fields["chargeable"] = _ask_bool("Still charged to parents?",
                                     existing.chargeable if existing else None)
    fields["notes"] = _ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_add_closure() -> None:
    print("\n  ── Add Closure ──")
    c = data.create_closure(_collect_closure())
    print(f"\n  Added closure {c.closure_id} — {c.name} "
          f"({c.start_date} to {c.end_date}).")


@_safe
def open_edit_closure() -> None:
    cid = _prompt("  Closure ID: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_closure(cid)
    if existing is None:
        print("  No closure with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    c = data.update_closure(cid, _collect_closure(existing))
    print(f"\n  Updated closure {c.closure_id}.")


@_safe
def open_delete_closure() -> None:
    cid = _prompt("  Closure ID to delete: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_closure(cid)
    if existing is None:
        print("  No closure with that ID.")
        return
    if _prompt(f"  Delete {existing.name} ({cid})? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    print(f"  Deleted closure {cid}." if data.delete_closure(cid)
          else "  Could not delete (already removed?).")


_DISPATCH = {"Sessions & Bookings": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching sessions CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
