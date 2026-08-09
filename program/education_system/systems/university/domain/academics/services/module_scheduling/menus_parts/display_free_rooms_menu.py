"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_free_rooms_menu(scheduler):
    """Display free rooms finder menu"""
    print("\n🏢 Find Free Rooms:")

    day = input(f"Day of week ({', '.join(DAYS_OF_WEEK)}): ")
    if day not in DAYS_OF_WEEK:
        print("Invalid day of week.")
        return

    start_time = input("Start time (HH:MM): ")
    end_time = input("End time (HH:MM): ")

    try:
        min_capacity = int(input("Minimum capacity (0 for any): ") or "0")
    except ValueError:
        min_capacity = 0

    room_type = input(f"Room type ({', '.join(ROOM_TYPES)}, or leave blank for any): ")
    if room_type and room_type not in ROOM_TYPES:
        room_type = None

    free_rooms = scheduler.find_free_rooms(day, start_time, end_time, min_capacity, room_type)

    if free_rooms:
        print(f"\nFree Rooms on {day} {start_time}-{end_time}:")
        print("=" * 80)
        print(f"{'ID':<5} {'Building':<15} {'Room':<10} {'Capacity':<10} {'Type':<15} {'Equipment':<20}")
        print("-" * 80)

        for room in free_rooms:
            room_id, room_number, building, capacity, room_type, equipment = room
            equipment = equipment or "N/A"
            print(f"{room_id:<5} {building:<15} {room_number:<10} {capacity:<10} "
                  f"{room_type:<15} {equipment[:18]:<20}")

        print("=" * 80)
    else:
        print("No free rooms found matching your criteria.")
