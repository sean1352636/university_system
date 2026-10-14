"""CLI flow for Staff Rota (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.staff.rota import rota as data
from education_system.systems.nursery.domain.staff.rota.rota import (
    STATUSES,
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


def _print_table(rows: list[data.Shift]) -> None:
    if not rows:
        print("  (no shifts)")
        return
    print(f"  {'ID':<8} {'Date':<12} {'Time':<14} {'Staff':<22} "
          f"{'Room':<14} {'Status'}")
    print(f"  {'-'*8} {'-'*12} {'-'*14} {'-'*22} {'-'*14} {'-'*9}")
    for s in rows:
        print(f"  {s.shift_id:<8} {(s.shift_date or '-'):<12} {s.time_span:<14} "
              f"{(s.staff_name or '-')[:22]:<22} {(s.room or '-')[:14]:<14} "
              f"{s.status}")


def _print_detail(s: data.Shift) -> None:
    print(f"\n  ── Shift {s.shift_id} ──")
    print(f"  Staff:    {s.staff_name or '-'} ({s.staff_id})")
    print(f"  Date:     {s.shift_date or '-'}")
    print(f"  Time:     {s.time_span}")
    print(f"  Room:     {s.room or '-'}")
    print(f"  Role:     {s.role or '-'}")
    print(f"  Status:   {s.status}")
    print(f"  Notes:    {s.notes or '-'}")


def _show_staff() -> None:
    try:
        choices = data.list_staff_choices()
    except Exception:
        logger.exception("Could not load staff choices")
        return
    if choices:
        print("  Staff:")
        for _id, label in choices:
            print(f"    {label}")


def _collect_fields(existing: data.Shift | None = None,
                    *, staff_id: str | None = None) -> dict[str, str]:
    def ask(label: str, current=None) -> str:
        cur = "" if current is None else str(current)
        suffix = f" [{cur}]" if cur else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else cur

    rooms = data.list_room_choices()
    fields: dict[str, str] = {}
    if staff_id is not None:
        fields["staff_id"] = staff_id
    fields["shift_date"] = ask("Shift date (YYYY-MM-DD)",
                               existing.shift_date if existing else None)
    fields["start_time"] = ask("Start time (HH:MM)",
                               existing.start_time if existing else None)
    fields["end_time"]   = ask("End time (HH:MM)",
                               existing.end_time if existing else None)
    if rooms:
        print("  Rooms: " + ", ".join(rooms))
    fields["room"]       = ask("Room", existing.room if existing else None)
    fields["role"]       = ask("Role on shift", existing.role if existing else None)
    fields["status"]     = ask(f"Status ({'/'.join(STATUSES)})",
                               existing.status if existing else "scheduled")
    fields["notes"]      = ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_manager() -> None:
    logger.debug("CLI: rota open_manager")
    date_filter = ""
    while True:
        scope = f"date {date_filter}" if date_filter else "all dates"
        print(f"\n  ── Staff Rota ({scope}) ──")
        rows = data.list_shifts(shift_date=date_filter or None)
        _print_table(rows)
        print("\n   A) Add    V) View    E) Edit    D) Delete")
        print("   S) Set status    F) Filter by date    X) Clear filter    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add()
        elif choice == "v":
            sid = _prompt("  Shift ID: ")
            s = data.get_shift(sid)
            if s is None:
                print("  No shift with that ID.")
            else:
                _print_detail(s)
                _prompt("  Press Enter to continue...")
        elif choice == "e":
            open_edit()
        elif choice == "d":
            open_delete()
        elif choice == "s":
            open_set_status()
        elif choice == "f":
            dates = data.list_dates()
            if dates:
                print("  Dates with shifts: " + ", ".join(dates))
            date_filter = _prompt("  Date (YYYY-MM-DD): ")
        elif choice == "x":
            date_filter = ""
        else:
            print("  Invalid selection.")


@_safe
def open_add() -> None:
    print("\n  ── Add Shift ──")
    _show_staff()
    sid = _prompt("  Staff ID: ")
    if not sid:
        print("  Cancelled.")
        return
    fields = _collect_fields(staff_id=sid)
    s = data.create_shift(fields)
    print(f"\n  Added shift {s.shift_id} for {s.staff_name} "
          f"on {s.shift_date or '(date TBC)'} ({s.time_span}).")


@_safe
def open_edit() -> None:
    sid = _prompt("  Shift ID: ")
    if not sid:
        print("  Cancelled.")
        return
    existing = data.get_shift(sid)
    if existing is None:
        print("  No shift with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    fields = _collect_fields(existing)
    s = data.update_shift(sid, fields)
    print(f"\n  Updated shift {s.shift_id}.")


@_safe
def open_delete() -> None:
    sid = _prompt("  Shift ID to delete: ")
    if not sid:
        print("  Cancelled.")
        return
    if data.get_shift(sid) is None:
        print("  No shift with that ID.")
        return
    if _prompt(f"  Delete shift {sid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_shift(sid):
        print(f"  Deleted shift {sid}.")
    else:
        print("  Could not delete (already removed?).")


@_safe
def open_set_status() -> None:
    sid = _prompt("  Shift ID: ")
    if not sid:
        print("  Cancelled.")
        return
    if data.get_shift(sid) is None:
        print("  No shift with that ID.")
        return
    status = _prompt(f"  New status ({'/'.join(STATUSES)}): ").lower()
    s = data.set_status(sid, status)
    print(f"  Shift {s.shift_id} is now {s.status}.")


_DISPATCH = {"Staff Rota": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching rota CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
