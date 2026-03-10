"""Timetable CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def timetable_menu(auth):
    """Timetable management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.academics.timetable.services.timetable_service import TimetableService

    svc = TimetableService(get_db_path())

    while True:
        print_header("Timetable")
        print_menu([
            ("1", "List slots"),
            ("2", "View details"),
            ("3", "Add Slot"),
            ("4", "Update Slot"),
            ("5", "Delete Slot"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_slots()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_slot(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            class_name = input("  Class Name: ").strip()
            day = input("  Day: ").strip()
            period = input("  Period: ").strip()
            subject_code = input("  Subject Code: ").strip()
            try:
                svc.create_slot(class_name=class_name, day=day, period=period, subject_code=subject_code)
                print("\n  Slot created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            class_name = input("  Class Name: ").strip()
            day = input("  Day: ").strip()
            period = input("  Period: ").strip()
            subject_code = input("  Subject Code: ").strip()
            try:
                svc.update_slot(int(pk), class_name=class_name, day=day, period=period, subject_code=subject_code)
                print("\n  Slot updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_slot(int(pk))
                print("\n  Slot deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
