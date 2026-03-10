"""Cover Lessons CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def cover_lessons_menu(auth):
    """Cover Lessons management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.staff.cover.services.cover_service import CoverService

    svc = CoverService(get_db_path())

    while True:
        print_header("Cover Lessons")
        print_menu([
            ("1", "List lessons"),
            ("2", "View details"),
            ("3", "Add Lesson"),
            ("4", "Update Lesson"),
            ("5", "Delete Lesson"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_lessons()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_lesson(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            date = input("  Date: ").strip()
            period = input("  Period: ").strip()
            class_name = input("  Class Name: ").strip()
            cover_staff_id = input("  Cover Staff Id: ").strip()
            try:
                svc.create_lesson(date=date, period=period, class_name=class_name, cover_staff_id=cover_staff_id)
                print("\n  Lesson created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            date = input("  Date: ").strip()
            period = input("  Period: ").strip()
            class_name = input("  Class Name: ").strip()
            cover_staff_id = input("  Cover Staff Id: ").strip()
            try:
                svc.update_lesson(int(pk), date=date, period=period, class_name=class_name, cover_staff_id=cover_staff_id)
                print("\n  Lesson updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_lesson(int(pk))
                print("\n  Lesson deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
