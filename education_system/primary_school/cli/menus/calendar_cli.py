"""Calendar CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def calendar_menu(auth):
    """Calendar management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.communication.calendar.services.calendar_service import CalendarService

    svc = CalendarService(get_db_path())

    while True:
        print_header("Calendar")
        print_menu([
            ("1", "List events"),
            ("2", "View details"),
            ("3", "Add Event"),
            ("4", "Update Event"),
            ("5", "Delete Event"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_events()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_event(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            title = input("  Title: ").strip()
            start_date = input("  Start Date: ").strip()
            try:
                svc.create_event(title=title, start_date=start_date)
                print("\n  Event created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            title = input("  Title: ").strip()
            start_date = input("  Start Date: ").strip()
            try:
                svc.update_event(int(pk), title=title, start_date=start_date)
                print("\n  Event updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_event(int(pk))
                print("\n  Event deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
