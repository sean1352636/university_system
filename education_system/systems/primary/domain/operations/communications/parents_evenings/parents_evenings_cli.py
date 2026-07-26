"""CLI flows for Primary School Parents' Evenings."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.primary.domain.operations.communications.parents_evenings import parents_evenings
from education_system.systems.primary.domain.operations.communications.parents_evenings import parents_evenings as data
from education_system.systems.primary.domain.staff import staff as staff_data
from education_system.systems.primary.domain import _pupils_bridge as student_data
from education_system.systems.primary.domain.operations.communications.parents_evenings.parents_evenings import (
    BOOKING_STATUSES,
    Booking,
    DEFAULT_BOOKING_STATUS,
    DEFAULT_EVENT_STATUS,
    DEFAULT_YEAR_GROUP,
    EVENT_STATUSES,
    Event,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

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


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_student() -> str:
    students = student_data.list_students()
    if not students:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(students)} (or student ID)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(students):
                return students[n - 1].student_id
            continue
        match = next((s for s in students
                       if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


def _pick_staff() -> str:
    staff = staff_data.list_staff(active_only=True)
    if not staff:
        print("    No active staff.")
        raise _UserAbort
    print("\n  Staff:")
    for i, t in enumerate(staff, 1):
        print(f"    {i:>3}) {t.staff_id}  {t.full_name} ({t.role})")
    while True:
        raw = _input(f"  Pick #1..{len(staff)} (or staff ID)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(staff):
                return staff[n - 1].staff_id
            continue
        match = next((t for t in staff
                       if t.staff_id.lower() == raw.lower()), None)
        if match:
            return match.staff_id
        print("    No matching staff.")


def _pick_event() -> Event:
    events = data.list_events()
    if not events:
        print("    No events. Create one first.")
        raise _UserAbort
    print("\n  Events:")
    for i, e in enumerate(events, 1):
        print(f"    {i:>3}) #{e.event_id}  {e.event_date}  "
              f"{e.name}  ({e.status})")
    while True:
        raw = _input(f"  Pick #1..{len(events)} (or event ID)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(events):
                return events[n - 1]
            ev = next((e for e in events if e.event_id == n), None)
            if ev:
                return ev
            print("    Not a listed index or ID.")
            continue
        print("    Enter a number.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_events(rows: list[Event]) -> None:
    if not rows:
        print("\n  (no events)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10}  {'Time':<13}  "
          f"{'Name':<30}  {'Year':<8}  {'Status':<20}  Slot(min)")
    print("  " + "-" * 100)
    for e in rows:
        print(f"  {e.event_id:>4}  {e.event_date:<10}  "
              f"{e.start_time}-{e.end_time:<5}  {e.name[:30]:<30}  "
              f"{e.year_group:<8}  {e.status:<20}  {e.slot_minutes:>3}")
    print(f"\n  {len(rows)} event(s).")


def _print_bookings(rows: list[Booking]) -> None:
    if not rows:
        print("\n  (no bookings)")
        return
    s_names = {s.student_id: s.full_name
                for s in student_data.list_students()}
    t_names = {t.staff_id: t.full_name
                for t in staff_data.list_staff()}
    print()
    print(f"  {'#':>4}  {'Ev':>4}  {'Slot':<6}  "
          f"{'Student':<10}  {'Name':<22}  "
          f"{'Staff':<10}  {'Staff name':<22}  Status")
    print("  " + "-" * 110)
    for b in rows:
        print(f"  {b.booking_id:>4}  {b.event_id:>4}  {b.slot_time:<6}  "
              f"{b.student_id:<10}  "
              f"{s_names.get(b.student_id, '?')[:22]:<22}  "
              f"{b.staff_id:<10}  "
              f"{t_names.get(b.staff_id, '?')[:22]:<22}  "
              f"{b.status}")
    print(f"\n  {len(rows)} booking(s).")


# ── Event flows ────────────────────────────────────────────────────

def list_events() -> None:
    print("\n═══ Parents' Evenings ═══")
    _print_events(data.list_events())
    _event_action_loop()


def list_upcoming() -> None:
    print("\n═══ Upcoming Parents' Evenings ═══")
    today = _date.today().isoformat()
    _print_events(data.list_events(open_only=True, date_from=today))
    _event_action_loop()


def view_event(event_id: int | None = None) -> None:
    print("\n═══ View Event ═══")
    try:
        if event_id is None:
            event = _pick_event()
        else:
            event = data.get_event(event_id)
            if event is None:
                print(f"  ✗ No event #{event_id}")
                _pause()
                return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    summ = data.summarize_event(event.event_id)
    print()
    print(f"    Event ID    : #{event.event_id}")
    print(f"    Name        : {event.name}")
    print(f"    Date        : {event.event_date}")
    print(f"    Time        : {event.start_time} – {event.end_time}")
    print(f"    Slot length : {event.slot_minutes} min "
          f"({summ.total_slots} slots/staff)")
    print(f"    Year group  : {event.year_group}")
    print(f"    Location    : {event.location or '—'}")
    print(f"    Status      : {event.status}")
    print()
    print(f"    Booked      : {summ.booked}")
    print(f"    Attended    : {summ.attended}")
    print(f"    No-Show     : {summ.no_shows}")
    print(f"    Cancelled   : {summ.cancelled}")
    print(f"    Students    : {summ.distinct_students}")
    print(f"    Staff       : {summ.distinct_staff}")
    print(f"    Fill rate   : "
          f"{summ.fill_rate if summ.fill_rate is not None else '—'}%")
    if event.notes:
        print("\n    Notes:")
        for line in event.notes.splitlines() or [""]:
            print(f"      {line}")
    _pause()


def _event_form(existing: Event | None) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    p["name"] = _input(
        "Event name",
        default=existing.name if is_edit else "",
        allow_empty=False)
    p["event_date"] = _input(
        "Event date (YYYY-MM-DD)",
        default=existing.event_date if is_edit
                else _date.today().isoformat(),
        allow_empty=False)
    p["year_group"] = _pick_from(
        "Year group", list(YEAR_GROUPS),
        default=existing.year_group if is_edit else DEFAULT_YEAR_GROUP)
    p["location"] = _input(
        "Location",
        default=(existing.location or "") if is_edit else "Main Hall")
    p["start_time"] = _input(
        "Start time (HH:MM)",
        default=existing.start_time if is_edit else "17:00",
        allow_empty=False)
    p["end_time"] = _input(
        "End time (HH:MM)",
        default=existing.end_time if is_edit else "20:00",
        allow_empty=False)
    p["slot_minutes"] = _input(
        "Slot length (minutes)",
        default=str(existing.slot_minutes) if is_edit else "10",
        allow_empty=False)
    p["status"] = _pick_from(
        "Status", list(EVENT_STATUSES),
        default=existing.status if is_edit else DEFAULT_EVENT_STATUS)
    p["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return p


def new_event() -> None:
    print("\n═══ New Parents' Evening ═══")
    try:
        payload = _event_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        e = data.create_event(payload)
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    print(f"\n  ✓ Created event #{e.event_id} ({e.name} on {e.event_date})")
    _pause()


def edit_event(event_id: int | None = None) -> None:
    print("\n═══ Edit Event ═══")
    try:
        if event_id is None:
            event = _pick_event()
        else:
            event = data.get_event(event_id)
            if event is None:
                print(f"  ✗ No event #{event_id}")
                _pause()
                return
        payload = _event_form(event)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_event(event.event_id, payload)
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    print(f"\n  ✓ Updated event #{event.event_id}")
    _pause()


def set_event_status_flow(event_id: int | None = None) -> None:
    print("\n═══ Change Event Status ═══")
    try:
        if event_id is None:
            event = _pick_event()
        else:
            event = data.get_event(event_id)
            if event is None:
                print(f"  ✗ No event #{event_id}")
                _pause()
                return
        new_status = _pick_from(
            "New status", list(EVENT_STATUSES), default=event.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_event_status(event.event_id, new_status)
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    print(f"\n  ✓ #{event.event_id} → {new_status}")
    _pause()


def delete_event_flow(event_id: int | None = None) -> None:
    print("\n═══ Delete Event ═══")
    print("  ⚠ This deletes all bookings for the event.")
    try:
        if event_id is None:
            event = _pick_event()
        else:
            event = data.get_event(event_id)
            if event is None:
                print(f"  ✗ No event #{event_id}")
                _pause()
                return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete #{event.event_id} ({event.name})? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_event(event.event_id):
        print(f"\n  ✓ Deleted #{event.event_id}")
    _pause()


# ── Booking flows ──────────────────────────────────────────────────

def list_bookings_for_event() -> None:
    print("\n═══ Bookings for Event ═══")
    try:
        event = _pick_event()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_bookings(data.list_bookings(event_id=event.event_id))
    _booking_action_loop()


def new_booking() -> None:
    print("\n═══ New Booking ═══")
    try:
        event = _pick_event()
        print(f"\n  Event #{event.event_id}  {event.name}  "
              f"{event.event_date}  {event.start_time}-{event.end_time}")
        sid = _pick_student()
        stid = _pick_staff()
        free = data.free_slots_for_staff(event.event_id, stid)
        if not free:
            print(f"  ✗ Staff {stid} has no free slots for this event.")
            _pause()
            return
        slot = _pick_from(f"Free slots for staff {stid}", free,
                            default=free[0])
        parent = _input("Parent / guardian name (optional)")
        status = _pick_from("Status", list(BOOKING_STATUSES),
                              default=DEFAULT_BOOKING_STATUS)
        notes = _input("Notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        b = data.create_booking(event.event_id, {
            "student_id": sid, "staff_id": stid, "slot_time": slot,
            "status": status, "parent_name": parent, "notes": notes,
        })
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    print(f"\n  ✓ Created booking #{b.booking_id} "
          f"({sid} ↔ {stid} at {slot})")
    _pause()


def edit_booking(booking_id: int | None = None) -> None:
    print("\n═══ Edit Booking ═══")
    try:
        bid = booking_id if booking_id is not None else int(
            _input("Booking ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_booking(bid)
    if existing is None:
        print(f"  ✗ No booking #{bid}")
        _pause()
        return
    event = data.get_event(existing.event_id)
    if event is None:
        print("  ✗ Parent event missing")
        _pause()
        return
    try:
        slot = _input("Slot time (HH:MM)", default=existing.slot_time)
        parent = _input("Parent name",
                          default=existing.parent_name or "")
        status = _pick_from("Status", list(BOOKING_STATUSES),
                              default=existing.status)
        notes = _input("Notes", default=existing.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_booking(bid, {
            "slot_time": slot, "status": status,
            "parent_name": parent, "notes": notes,
        })
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    print(f"\n  ✓ Updated #{bid}")
    _pause()


def set_booking_status_flow(booking_id: int | None = None) -> None:
    print("\n═══ Change Booking Status ═══")
    try:
        bid = booking_id if booking_id is not None else int(
            _input("Booking ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_booking(bid)
    if existing is None:
        print(f"  ✗ No booking #{bid}")
        _pause()
        return
    try:
        new_status = _pick_from(
            "New status", list(BOOKING_STATUSES),
            default=existing.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_booking_status(bid, new_status)
    except ValidationError as ex:
        print(f"\n  ✗ {ex}")
        _pause()
        return
    print(f"\n  ✓ #{bid} → {new_status}")
    _pause()


def delete_booking_flow(booking_id: int | None = None) -> None:
    print("\n═══ Delete Booking ═══")
    try:
        bid = booking_id if booking_id is not None else int(
            _input("Booking ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_booking(bid) is None:
        print(f"  ✗ No booking #{bid}")
        _pause()
        return
    if _input(f"Delete booking #{bid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_booking(bid):
        print(f"\n  ✓ Deleted #{bid}")
    _pause()


def staff_schedule_flow() -> None:
    print("\n═══ Staff Schedule ═══")
    try:
        event = _pick_event()
        stid = _pick_staff()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.staff_schedule(event.event_id, stid)
    print(f"\n  Event #{event.event_id} {event.name}  "
          f"— Staff {stid}")
    _print_bookings(rows)
    free = data.free_slots_for_staff(event.event_id, stid)
    print(f"\n  Free slots: {', '.join(free) if free else '(none)'}")
    _pause()


def student_schedule_flow() -> None:
    print("\n═══ Student Schedule ═══")
    try:
        event = _pick_event()
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.student_schedule(event.event_id, sid)
    print(f"\n  Event #{event.event_id} {event.name}  — Student {sid}")
    _print_bookings(rows)
    _pause()


def summary() -> None:
    print("\n═══ Parents' Evenings Summary ═══")
    summ = data.summary()
    print(f"\n  Total events       : {summ.total_events}")
    print(f"  Upcoming events    : {summ.upcoming_events}")
    print(f"  Open for booking   : {summ.open_for_booking}")
    print(f"  Completed          : {summ.completed}")
    print(f"  Total bookings     : {summ.total_bookings}")
    if summ.next_event:
        e = summ.next_event
        print(f"\n  Next event: #{e.event_id}  {e.event_date} "
              f"{e.start_time}-{e.end_time}  {e.name}  ({e.status})")
    print("\n  Events by status:")
    for s in EVENT_STATUSES:
        n = summ.by_event_status.get(s, 0)
        if n:
            print(f"    {s:<22} : {n}")
    print("\n  Bookings by status:")
    for s in BOOKING_STATUSES:
        n = summ.by_booking_status.get(s, 0)
        if n:
            print(f"    {s:<22} : {n}")
    _pause()


# ── Action loops ──────────────────────────────────────────────────

def _event_action_loop() -> None:
    print()
    print("  Actions:  V) View   E) Edit   S) Status   B) Bookings   "
          "D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "s", "b", "d"):
            print("    Pick V, E, S, B, D, or Enter.")
            continue
        try:
            raw = _input("Event ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            eid = int(raw)
        except ValueError:
            print("    Event ID must be a whole number.")
            continue
        if choice == "v":
            view_event(eid)
        elif choice == "e":
            edit_event(eid)
        elif choice == "s":
            set_event_status_flow(eid)
        elif choice == "b":
            ev = data.get_event(eid)
            if ev is None:
                print(f"  ✗ No event #{eid}")
                _pause()
            else:
                _print_bookings(data.list_bookings(event_id=eid))
                _booking_action_loop()
        elif choice == "d":
            delete_event_flow(eid)
        return


def _booking_action_loop() -> None:
    print()
    print("  Actions:  E) Edit   S) Status   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("e", "s", "d"):
            print("    Pick E, S, D, or Enter.")
            continue
        try:
            raw = _input("Booking ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            bid = int(raw)
        except ValueError:
            print("    Booking ID must be a whole number.")
            continue
        if choice == "e":
            edit_booking(bid)
        elif choice == "s":
            set_booking_status_flow(bid)
        elif choice == "d":
            delete_booking_flow(bid)
        return


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Upcoming Events",       list_upcoming),
    ("All Events",            list_events),
    ("View Event",            view_event),
    ("New Event",             new_event),
    ("Edit Event",            edit_event),
    ("Change Event Status",   set_event_status_flow),
    ("Delete Event",          delete_event_flow),
    ("Bookings for Event",    list_bookings_for_event),
    ("New Booking",           new_booking),
    ("Edit Booking",          edit_booking),
    ("Change Booking Status", set_booking_status_flow),
    ("Delete Booking",        delete_booking_flow),
    ("Staff Schedule",        staff_schedule_flow),
    ("Student Schedule",      student_schedule_flow),
    ("Summary",               summary),
]


def run() -> None:
    while True:
        print("\n── Parents' Evenings ──")
        for i, (label, _) in enumerate(_MENU, 1):
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
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Parents'-evenings CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Parents' Evenings":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Parents'-evenings CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
