"""Console menu for the generic room-booking service — mirrors employer_portal_cli."""
from __future__ import annotations

from typing import Any

from education_system.post_18.university_system.modules.domain.campus.room_booking.services.room_booking_service import (
    RoomBookingService,
    RoomBookingError,
)


auth: Any = None


def set_auth(auth_object: Any) -> None:
    global auth
    auth = auth_object


def _require_login() -> bool:
    if not auth or not getattr(auth, "current_user", None):
        print("You must be logged in to access room booking.")
        return False
    return True


def _print_bookings(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("No bookings found.")
        return
    print(f"\n{'ID':<5} {'Room':<6} {'Booked By':<14} {'Start':<17} {'End':<17} "
          f"{'Status':<10} {'Purpose':<20}")
    print("-" * 95)
    for b in rows:
        print(f"{b['booking_id']:<5} {b['room_id']:<6} "
              f"{(b.get('booked_by') or '-')[:14]:<14} "
              f"{(b.get('start_datetime') or '-'):<17} "
              f"{(b.get('end_datetime') or '-'):<17} "
              f"{(b.get('booking_status') or '-'):<10} "
              f"{(b.get('purpose') or '-')[:20]:<20}")
    print(f"\nTotal: {len(rows)}")


def _list_bookings(svc: RoomBookingService) -> None:
    room = input("Filter by room id (Enter for all): ").strip()
    on_date = input("Filter by date YYYY-MM-DD (Enter for all): ").strip() or None
    try:
        rid = int(room) if room else None
        rows = svc.list_bookings(room_id=rid, on_date=on_date)
    except (RoomBookingError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    _print_bookings(rows)


def _find_available(svc: RoomBookingService) -> None:
    start = input("Start (YYYY-MM-DD HH:MM): ").strip()
    end = input("End   (YYYY-MM-DD HH:MM): ").strip()
    cap_raw = input("Min capacity (Enter to skip): ").strip()
    equip = input("Required equipment (comma-separated, Enter to skip): ").strip()
    try:
        cap = int(cap_raw) if cap_raw else None
        rooms = svc.find_available_rooms(start, end, capacity_min=cap, equipment_csv=equip)
    except (RoomBookingError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    if not rooms:
        print("No available rooms.")
        return
    print(f"\n{'ID':<5} {'Number':<10} {'Type':<14} {'Cap':<5} {'Equipment':<30}")
    print("-" * 70)
    for r in rooms:
        print(f"{r.get('room_id',''):<5} "
              f"{(r.get('room_number') or '-')[:10]:<10} "
              f"{(r.get('room_type') or '-')[:14]:<14} "
              f"{(r.get('capacity') or '-'):<5} "
              f"{(r.get('equipment') or '-')[:30]:<30}")
    print(f"\nTotal: {len(rooms)}")


def _book_room(svc: RoomBookingService) -> None:
    try:
        rid = int(input("Room ID: ").strip())
        start = input("Start (YYYY-MM-DD HH:MM): ").strip()
        end = input("End   (YYYY-MM-DD HH:MM): ").strip()
        booked_by = input("Booked by (user/email): ").strip()
        purpose = input("Purpose: ").strip()
        equip = input("Equipment needed (comma-separated, Enter to skip): ").strip()
        bid = svc.create_booking(rid, start, end, booked_by, purpose, equipment_needed=equip)
        print(f"Booking #{bid} created.")
    except (RoomBookingError, ValueError) as exc:
        print(f"Error: {exc}")


def _reschedule(svc: RoomBookingService) -> None:
    try:
        bid = int(input("Booking ID: ").strip())
        start = input("New start (YYYY-MM-DD HH:MM): ").strip()
        end = input("New end   (YYYY-MM-DD HH:MM): ").strip()
        svc.reschedule_booking(bid, start, end)
        print("Booking rescheduled.")
    except (RoomBookingError, ValueError) as exc:
        print(f"Error: {exc}")


def _cancel(svc: RoomBookingService) -> None:
    try:
        bid = int(input("Booking ID: ").strip())
        if svc.cancel_booking(bid):
            print(f"Booking #{bid} cancelled.")
        else:
            print(f"Booking #{bid} not found or already cancelled.")
    except (RoomBookingError, ValueError) as exc:
        print(f"Error: {exc}")


def display_room_booking_menu() -> None:
    """Top-level room-booking menu."""
    if not _require_login():
        return
    db_path = getattr(auth, "_db_path", None)
    svc = RoomBookingService(db_path)

    actions = {
        "1": ("List Bookings",     _list_bookings),
        "2": ("Find Available",    _find_available),
        "3": ("Book Room",         _book_room),
        "4": ("Reschedule",        _reschedule),
        "5": ("Cancel Booking",    _cancel),
    }
    while True:
        print("\nRoom Booking")
        print("=" * 30)
        for k, (label, _) in actions.items():
            print(f"{k}. {label}")
        print("0. Return to Previous Menu")
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if not action:
            print("Invalid choice.")
            continue
        try:
            action[1](svc)
        except KeyboardInterrupt:
            print("\nCancelled.")
        except RoomBookingError as exc:
            print(f"Error: {exc}")
