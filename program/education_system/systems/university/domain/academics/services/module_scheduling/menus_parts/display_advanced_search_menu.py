"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_advanced_search_menu(scheduler):
    """Display advanced search menu"""
    print("\n🔍 Advanced Search & Filtering:")

    filters = {}

    print("Enter search criteria (leave blank to skip):")

    module_code = input("Module code (partial match): ").strip()
    if module_code:
        filters['module_code'] = module_code

    day = input(f"Day of week ({', '.join(DAYS_OF_WEEK)}): ").strip()
    if day and day in DAYS_OF_WEEK:
        filters['day'] = day

    time_from = input("Time from (HH:MM): ").strip()
    if time_from:
        filters['time_from'] = time_from

    time_to = input("Time to (HH:MM): ").strip()
    if time_to:
        filters['time_to'] = time_to

    session_type = input(f"Session type ({', '.join(SESSION_TYPES)}): ").strip()
    if session_type and session_type in SESSION_TYPES:
        filters['session_type'] = session_type

    instructor = input("Instructor name (partial match): ").strip()
    if instructor:
        filters['instructor'] = instructor

    building = input("Building name (partial match): ").strip()
    if building:
        filters['building'] = building

    room_type = input(f"Room type ({', '.join(ROOM_TYPES)}): ").strip()
    if room_type and room_type in ROOM_TYPES:
        filters['room_type'] = room_type

    # Perform search
    results = scheduler.advanced_schedule_search(filters)

    if results:
        print(f"\nSearch Results ({len(results)} found):")
        print("=" * 120)
        print(f"{'Module':<10} {'Name':<25} {'Day':<10} {'Time':<15} {'Room':<15} {'Instructor':<20} {'Type':<10}")
        print("-" * 120)

        for result in results:
            id, code, name, day, start, end, building, room, first_name, last_name, session_type = result
            name = name or "Unknown"
            time_slot = f"{start}-{end}"
            room_str = f"{building}-{room}" if building and room else "TBA"
            instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"

            print(f"{code:<10} {name[:23]:<25} {day:<10} {time_slot:<15} "
                  f"{room_str:<15} {instructor[:18]:<20} {session_type:<10}")

        print("=" * 120)
    else:
        print("No results found matching the search criteria.")
