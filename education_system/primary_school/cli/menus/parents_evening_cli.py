"""Parents Evening CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def parents_evening_menu(auth):
    """Parents Evening menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.communication.parents_evening.services.parents_evening_service import ParentsEveningService

    svc = ParentsEveningService(get_db_path())

    while True:
        print_header("Parents Evening")
        print_menu([("1", "Events"), ("2", "Create event"), ("3", "View slots"), ("4", "Create slot"), ("0", "Back")])
        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            for item in (svc.list_events() or []):
                print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            title = input("  Title: ").strip()
            date = input("  Date: ").strip()
            try:
                svc.create_event(title=title, date=date)
                print("\n  Created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            eid = input("  Event ID: ").strip()
            for item in (svc.list_slots(int(eid)) or []):
                print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "4":
            eid = input("  Event ID: ").strip()
            tid = input("  Teacher ID: ").strip()
            ts = input("  Time slot: ").strip()
            try:
                svc.create_slot(event_id=int(eid), teacher_id=tid, time_slot=ts)
                print("\n  Created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
