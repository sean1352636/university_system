"""CLI flows for Room & Resource Booking."""

from __future__ import annotations

import logging
from typing import Callable

from education_system.sixthform_system.modules.domain.academics.room_booking import (
    room_booking as data,
)
from education_system.sixthform_system.modules.domain.academics.room_booking.room_booking import (
    BOOKING_STATUSES,
    Booking,
    ClashError,
    DEFAULT_BOOKING_STATUS,
    DEFAULT_RESOURCE_TYPE,
    RESOURCE_TYPES,
    Resource,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Input helpers ────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


def _multiline(prompt: str, *, default: str = "") -> str:
    print(f"\n  {prompt} (end with '.'; ENTER for default)")
    if default:
        for line in default.splitlines():
            print(f"    | {line}")
    lines: list[str] = []
    try:
        while True:
            ln = input("  > ")
            if ln.strip() == ".":
                break
            if not lines and not ln:
                return default
            lines.append(ln)
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    return "\n".join(lines)


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt or '(none)'}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number.")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_resource(*, active_only: bool = False) -> Resource:
    rows = data.list_resources(active_only=active_only)
    if not rows:
        print("    No resources. Add one first.")
        raise _UserAbort
    print("\n  Resources:")
    for i, r in enumerate(rows, 1):
        flag = " " if r.active else "x"
        cap = f"cap {r.capacity}" if r.capacity else "—"
        print(f"   {flag}{i:>3}) #{r.resource_id:<4}  "
              f"{r.name[:30]:<30}  {r.resource_type[:14]:<14}  {cap}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows if r.resource_id == n), None)
            if match:
                return match
        print("    No matching resource.")


def _pick_booking() -> Booking:
    rows = data.list_bookings()
    if not rows:
        print("    No bookings yet.")
        raise _UserAbort
    resources = {r.resource_id: r.name for r in data.list_resources()}
    print("\n  Bookings:")
    for i, b in enumerate(rows, 1):
        rname = resources.get(b.resource_id, "?")
        print(f"    {i:>3}) #{b.booking_id:<4}  {b.booking_date}  "
              f"{b.start_time}-{b.end_time}  {rname[:24]:<24}  "
              f"by {b.booked_by[:14]:<14}  [{b.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows if r.booking_id == n), None)
            if match:
                return match
        print("    No matching booking.")


# ── Rendering ────────────────────────────────────────────────────

def _print_resource_table(rows: list[Resource]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<32}  {'Type':<16}  "
          f"{'Cap':>5}  {'Location':<20}  Active")
    print("  " + "-" * 100)
    for r in rows:
        print(f"  {r.resource_id:>4}  {r.name[:32]:<32}  "
              f"{r.resource_type:<16}  "
              f"{r.capacity or '—':>5}  "
              f"{(r.location or '—')[:20]:<20}  "
              f"{'yes' if r.active else 'no'}")
    print(f"\n  {len(rows)} resource(s).")


def _print_booking_table(rows: list[data.BookingRow]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10} {'Start':<5} {'End':<5}  "
          f"{'Resource':<24}  {'Type':<14}  "
          f"{'Booked by':<14}  {'Purpose':<28}  Status")
    print("  " + "-" * 130)
    for r in rows:
        b = r.booking
        print(f"  {b.booking_id:>4}  {b.booking_date:<10} "
              f"{b.start_time:<5} {b.end_time:<5}  "
              f"{r.resource_name[:24]:<24}  "
              f"{r.resource_type[:14]:<14}  "
              f"{b.booked_by[:14]:<14}  "
              f"{b.purpose[:28]:<28}  {b.status}")
    print(f"\n  {len(rows)} booking(s).")


def _print_booking_full(b: Booking) -> None:
    res = data.get_resource(b.resource_id)
    print()
    print(f"    #{b.booking_id}")
    print(f"    Resource         : #{b.resource_id}  "
          f"{res.name if res else '(unknown)'}"
          f"  ({res.resource_type if res else '?'})")
    print(f"    Date / time      : {b.booking_date}  "
          f"{b.start_time}-{b.end_time}")
    print(f"    Booked by        : {b.booked_by}")
    print(f"    Purpose          : {b.purpose}")
    print(f"    Attendees        : "
          f"{b.attendee_count if b.attendee_count is not None else '—'}")
    print(f"    Status           : {b.status}")
    if b.notes:
        print("\n    Notes:")
        for line in b.notes.splitlines():
            print(f"      {line}")


# ── Resource flows ───────────────────────────────────────────────

def list_resources_flow() -> None:
    print("\n═══ Resources ═══")
    _print_resource_table(data.list_resources())
    _pause()


def add_resource() -> None:
    print("\n═══ Add Resource ═══")
    try:
        name = _input("Resource name", allow_empty=False)
        rtype = _pick_from("Type", list(RESOURCE_TYPES),
                              default=DEFAULT_RESOURCE_TYPE)
        cap = _input("Capacity (blank for n/a)")
        location = _input("Location (e.g. building/floor)")
        notes = _multiline("Notes (optional)")
        r = data.create_resource({
            "name": name, "resource_type": rtype,
            "capacity": cap, "location": location,
            "notes": notes, "active": True,
        })
        print(f"\n  ✓ Created resource #{r.resource_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("add_resource failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def edit_resource() -> None:
    print("\n═══ Edit Resource ═══")
    try:
        r = _pick_resource()
        name = _input("Resource name", default=r.name, allow_empty=False)
        rtype = _pick_from("Type", list(RESOURCE_TYPES),
                              default=r.resource_type)
        cap = _input("Capacity",
                      default=("" if r.capacity is None
                                else str(r.capacity)))
        location = _input("Location", default=r.location or "")
        active = _yes_no("Active?", default=r.active)
        notes = _multiline("Notes", default=r.notes or "")
        out = data.update_resource(r.resource_id, {
            "name": name, "resource_type": rtype,
            "capacity": cap, "location": location,
            "notes": notes, "active": active,
        })
        print(f"\n  ✓ Updated resource #{out.resource_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("edit_resource failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def delete_resource_flow() -> None:
    print("\n═══ Delete Resource ═══")
    try:
        r = _pick_resource()
        if not _yes_no(
                f"Delete resource #{r.resource_id} {r.name!r}?"):
            print("  (cancelled)")
            return
        if data.delete_resource(r.resource_id):
            print(f"\n  ✓ Deleted resource #{r.resource_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("delete_resource_flow failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


# ── Booking flows ────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Bookings ═══")
    _print_booking_table(data.list_bookings_with_detail())
    _pause()


def list_by_status() -> None:
    try:
        status = _pick_from("Filter by status",
                              list(BOOKING_STATUSES))
        print(f"\n═══ Bookings with status: {status} ═══")
        _print_booking_table(data.list_bookings_with_detail(
            status=status))
        _pause()
    except _UserAbort:
        return


def list_by_resource() -> None:
    try:
        r = _pick_resource()
        print(f"\n═══ Bookings for resource: {r.name} ═══")
        _print_booking_table(data.list_bookings_with_detail(
            resource_id=r.resource_id))
        _pause()
    except _UserAbort:
        return


def list_by_date_range() -> None:
    try:
        date_from = _input("From date (YYYY-MM-DD, blank=any)")
        date_to   = _input("To   date (YYYY-MM-DD, blank=any)")
        print(f"\n═══ Bookings {date_from or '…'} to "
              f"{date_to or '…'} ═══")
        _print_booking_table(data.list_bookings_with_detail(
            date_from=date_from or None, date_to=date_to or None))
        _pause()
    except _UserAbort:
        return
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()


def view_booking() -> None:
    try:
        b = _pick_booking()
        _print_booking_full(b)
        _pause()
    except _UserAbort:
        return


def add_booking() -> None:
    print("\n═══ Add Booking ═══")
    try:
        r = _pick_resource(active_only=True)
        date_s = _input("Booking date (YYYY-MM-DD)",
                          allow_empty=False)
        start = _input("Start time (HH:MM)", allow_empty=False)
        end = _input("End time (HH:MM)", allow_empty=False)
        booked_by = _input("Booked by (name)", allow_empty=False)
        purpose = _input("Purpose", allow_empty=False)
        attendees = _input("Attendee count (blank for n/a)")
        status = _pick_from("Status", list(BOOKING_STATUSES),
                              default=DEFAULT_BOOKING_STATUS)
        notes = _multiline("Notes (optional)")
        try:
            b = data.create_booking({
                "resource_id": r.resource_id,
                "booking_date": date_s,
                "start_time": start, "end_time": end,
                "booked_by": booked_by, "purpose": purpose,
                "attendee_count": attendees,
                "status": status, "notes": notes,
            })
        except ClashError as e:
            print(f"\n  ⚠ {e}")
            if _yes_no("  Book anyway (override clash)?"):
                b = data.create_booking({
                    "resource_id": r.resource_id,
                    "booking_date": date_s,
                    "start_time": start, "end_time": end,
                    "booked_by": booked_by, "purpose": purpose,
                    "attendee_count": attendees,
                    "status": status, "notes": notes,
                }, ignore_clashes=True)
            else:
                print("  (cancelled)")
                return
        print(f"\n  ✓ Created booking #{b.booking_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("add_booking failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def edit_booking() -> None:
    print("\n═══ Edit Booking ═══")
    try:
        b = _pick_booking()
        change_resource = _yes_no(
            f"Current resource: #{b.resource_id}.  Change?")
        rid = b.resource_id
        if change_resource:
            rid = _pick_resource(active_only=True).resource_id
        date_s = _input("Booking date", default=b.booking_date,
                          allow_empty=False)
        start = _input("Start time", default=b.start_time,
                        allow_empty=False)
        end = _input("End time", default=b.end_time,
                      allow_empty=False)
        booked_by = _input("Booked by", default=b.booked_by,
                              allow_empty=False)
        purpose = _input("Purpose", default=b.purpose,
                            allow_empty=False)
        attendees = _input("Attendee count",
                              default=("" if b.attendee_count is None
                                        else str(b.attendee_count)))
        status = _pick_from("Status", list(BOOKING_STATUSES),
                              default=b.status)
        notes = _multiline("Notes", default=b.notes or "")
        payload = {
            "resource_id": rid, "booking_date": date_s,
            "start_time": start, "end_time": end,
            "booked_by": booked_by, "purpose": purpose,
            "attendee_count": attendees,
            "status": status, "notes": notes,
        }
        try:
            out = data.update_booking(b.booking_id, payload)
        except ClashError as e:
            print(f"\n  ⚠ {e}")
            if _yes_no("  Save anyway (override clash)?"):
                out = data.update_booking(
                    b.booking_id, payload, ignore_clashes=True)
            else:
                print("  (cancelled)")
                return
        print(f"\n  ✓ Updated booking #{out.booking_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("edit_booking failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def cancel_booking_flow() -> None:
    print("\n═══ Cancel Booking ═══")
    try:
        b = _pick_booking()
        if b.status == "Cancelled":
            print("  Already cancelled.")
            _pause()
            return
        if not _yes_no(f"Cancel booking #{b.booking_id}?"):
            print("  (no action)")
            return
        out = data.cancel_booking(b.booking_id)
        print(f"\n  ✓ Cancelled booking #{out.booking_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("cancel_booking_flow failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def delete_booking_flow() -> None:
    print("\n═══ Delete Booking ═══")
    try:
        b = _pick_booking()
        _print_booking_full(b)
        if not _yes_no("\n  Delete this booking?"):
            print("  (cancelled)")
            return
        if data.delete_booking(b.booking_id):
            print(f"\n  ✓ Deleted booking #{b.booking_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except Exception as e:
        logger.exception("delete_booking_flow failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def show_summary() -> None:
    print("\n═══ Room Booking Summary ═══")
    try:
        s = data.summary()
        print(f"\n  Total resources       : {s.total_resources}"
              f" (active {s.active_resources})")
        print(f"  Total bookings        : {s.total_bookings}")
        print(f"  Today (non-cancelled) : {s.bookings_today}")
        print(f"  Upcoming (14 d)       : {s.upcoming_bookings}")
        print("\n  By status:")
        for st, n in s.by_status.items():
            print(f"    {st:<14} {n:>3}")
        print("\n  Resources by type:")
        for t, n in s.by_resource_type.items():
            if n:
                print(f"    {t:<16} {n:>3}")
        _pause()
    except Exception as e:
        logger.exception("show_summary failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


# ── Menu ─────────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all bookings",          list_all),
    ("List bookings by status",    list_by_status),
    ("List bookings for resource", list_by_resource),
    ("List bookings by date",      list_by_date_range),
    ("View booking",               view_booking),
    ("Add booking",                add_booking),
    ("Edit booking",               edit_booking),
    ("Cancel booking",             cancel_booking_flow),
    ("Delete booking",             delete_booking_flow),
    ("List resources",             list_resources_flow),
    ("Add resource",               add_resource),
    ("Edit resource",              edit_resource),
    ("Delete resource",            delete_resource_flow),
    ("Summary report",             show_summary),
]


def run() -> None:
    while True:
        print("\n══════ Room & Resource Booking ══════")
        for i, (label, _fn) in enumerate(_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _label, fn = _MENU[int(choice) - 1]
        try:
            fn()
        except _UserAbort:
            print("\n  (cancelled)")
        except Exception as e:
            logger.exception("Room booking CLI flow crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Room Booking":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Room booking CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
