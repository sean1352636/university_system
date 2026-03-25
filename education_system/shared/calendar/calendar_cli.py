"""CLI module for the Cross-System Calendar."""

from datetime import datetime

from education_system.shared.calendar.calendar_service import (
    CrossSystemCalendarService,
    EVENT_TYPES,
)

SYSTEM_NAMES = {
    "university": "University",
    "college": "Sixth Form College",
    "school": "Secondary School",
    "primary": "Primary School",
}

ALL_SYSTEMS_KEYS = ["primary", "school", "college", "university"]


def run(db_path=None, auth=None):
    """Run the Cross-System Calendar CLI menu loop."""
    svc = CrossSystemCalendarService(db_path=db_path)

    user_name = ""
    user_system = ""
    if isinstance(auth, dict):
        user_name = auth.get("display_name") or auth.get("username", "")
        user_system = auth.get("system_key", "")

    while True:
        print("\n=== Cross-System Calendar ===")
        print("1) View upcoming events")
        print("2) View month")
        print("3) Add event")
        print("4) Edit event")
        print("5) Delete event")
        print("6) Filter by system")
        print("0) Back")

        choice = input("\nChoice: ").strip()

        if choice == "1":
            _view_upcoming(svc)
        elif choice == "2":
            _view_month(svc)
        elif choice == "3":
            _add_event(svc, user_name, user_system)
        elif choice == "4":
            _edit_event(svc)
        elif choice == "5":
            _delete_event(svc)
        elif choice == "6":
            _filter_by_system(svc)
        elif choice == "0":
            break
        else:
            print("Invalid choice.")


def _print_events(events):
    """Print a formatted table of events."""
    if not events:
        print("No events found.")
        return

    print(f"\n{'ID':<6} {'Date':<12} {'Time':<8} {'Title':<30} {'Type':<12} {'Systems':<20}")
    print("-" * 88)
    for ev in events:
        systems = ev.get("systems", "all")
        if systems == "all":
            systems = "All"
        else:
            parts = [SYSTEM_NAMES.get(s.strip(), s.strip()) for s in systems.split(",")]
            systems = ", ".join(parts)
        if len(systems) > 18:
            systems = systems[:17] + "..."

        print(f"{ev['id']:<6} {ev.get('event_date', ''):<12} "
              f"{ev.get('event_time', '') or '--:--':<8} "
              f"{ev.get('title', ''):<30} {ev.get('event_type', ''):<12} {systems:<20}")
    print(f"\nTotal: {len(events)} event(s)")


def _view_upcoming(svc):
    days_str = input("Days ahead [30]: ").strip()
    days = int(days_str) if days_str.isdigit() else 30
    events = svc.get_upcoming(days=days)
    _print_events(events)


def _view_month(svc):
    now = datetime.now()
    month_str = input(f"Month [1-12, default {now.month}]: ").strip()
    year_str = input(f"Year [default {now.year}]: ").strip()
    month = int(month_str) if month_str.isdigit() else now.month
    year = int(year_str) if year_str.isdigit() else now.year
    events = svc.get_events(month=month, year=year)
    _print_events(events)


def _add_event(svc, user_name, user_system):
    print("\n--- Add New Event ---")
    title = input("Title: ").strip()
    if not title:
        print("Title is required.")
        return

    description = input("Description (optional): ").strip()
    date = input("Date (YYYY-MM-DD): ").strip()
    if not date:
        print("Date is required.")
        return

    time_val = input("Time (HH:MM, optional): ").strip()
    end_date = input("End date (YYYY-MM-DD, optional): ").strip()

    print(f"Event types: {', '.join(EVENT_TYPES)}")
    event_type = input("Event type [other]: ").strip() or "other"
    if event_type not in EVENT_TYPES:
        print(f"Invalid type. Using 'other'.")
        event_type = "other"

    print("Systems (comma-separated, or 'all'):")
    for i, key in enumerate(ALL_SYSTEMS_KEYS, 1):
        print(f"  {i}. {SYSTEM_NAMES.get(key, key)} ({key})")
    systems_input = input("Systems [all]: ").strip() or "all"

    try:
        ev = svc.create_event(
            title=title, description=description, date=date,
            time=time_val, end_date=end_date, systems=systems_input,
            event_type=event_type, created_by=user_name,
            created_system=user_system,
        )
        if ev:
            print(f"Event created with ID {ev['id']}.")
        else:
            print("Failed to create event.")
    except Exception as e:
        print(f"Error: {e}")


def _edit_event(svc):
    eid_str = input("Event ID to edit: ").strip()
    if not eid_str.isdigit():
        print("Invalid ID.")
        return

    eid = int(eid_str)
    ev = svc.get_event(eid)
    if not ev:
        print("Event not found.")
        return

    print(f"\nEditing event {eid}: {ev.get('title', '')}")
    print("(Press Enter to keep current value)\n")

    title = input(f"Title [{ev.get('title', '')}]: ").strip() or ev.get("title", "")
    description = input(f"Description [{ev.get('description', '')}]: ").strip()
    if not description:
        description = ev.get("description", "")
    date = input(f"Date [{ev.get('event_date', '')}]: ").strip() or ev.get("event_date", "")
    time_val = input(f"Time [{ev.get('event_time', '')}]: ").strip()
    if not time_val:
        time_val = ev.get("event_time", "")
    end_date = input(f"End date [{ev.get('end_date', '')}]: ").strip()
    if not end_date:
        end_date = ev.get("end_date", "")
    event_type = input(f"Type [{ev.get('event_type', '')}]: ").strip()
    if not event_type:
        event_type = ev.get("event_type", "other")
    systems = input(f"Systems [{ev.get('systems', 'all')}]: ").strip()
    if not systems:
        systems = ev.get("systems", "all")

    try:
        svc.update_event(
            eid, title=title, description=description, event_date=date,
            event_time=time_val, end_date=end_date, systems=systems,
            event_type=event_type,
        )
        print("Event updated.")
    except Exception as e:
        print(f"Error: {e}")


def _delete_event(svc):
    eid_str = input("Event ID to delete: ").strip()
    if not eid_str.isdigit():
        print("Invalid ID.")
        return

    eid = int(eid_str)
    ev = svc.get_event(eid)
    if not ev:
        print("Event not found.")
        return

    confirm = input(f"Delete '{ev.get('title', '')}'? (y/n): ").strip().lower()
    if confirm == "y":
        svc.delete_event(eid)
        print("Event deleted.")
    else:
        print("Cancelled.")


def _filter_by_system(svc):
    print("\nSystems:")
    for i, key in enumerate(ALL_SYSTEMS_KEYS, 1):
        print(f"  {i}. {SYSTEM_NAMES.get(key, key)} ({key})")

    sys_input = input("System key: ").strip()
    if not sys_input:
        print("No system specified.")
        return

    events = svc.get_upcoming(system=sys_input, days=90)
    print(f"\nEvents for {SYSTEM_NAMES.get(sys_input, sys_input)} (next 90 days):")
    _print_events(events)
