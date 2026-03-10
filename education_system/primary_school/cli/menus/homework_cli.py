"""Homework CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def homework_menu(auth):
    """Homework management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.academics.homework.services.homework_service import HomeworkService

    svc = HomeworkService(get_db_path())

    while True:
        print_header("Homework")
        print_menu([
            ("1", "List homework"),
            ("2", "View details"),
            ("3", "Add Homework"),
            ("4", "Update Homework"),
            ("5", "Delete Homework"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_homework()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_homework(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            title = input("  Title: ").strip()
            class_name = input("  Class Name: ").strip()
            subject_code = input("  Subject Code: ").strip()
            due_date = input("  Due Date: ").strip()
            try:
                svc.create_homework(title=title, class_name=class_name, subject_code=subject_code, due_date=due_date)
                print("\n  Homework created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            title = input("  Title: ").strip()
            class_name = input("  Class Name: ").strip()
            subject_code = input("  Subject Code: ").strip()
            due_date = input("  Due Date: ").strip()
            try:
                svc.update_homework(int(pk), title=title, class_name=class_name, subject_code=subject_code, due_date=due_date)
                print("\n  Homework updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_homework(int(pk))
                print("\n  Homework deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
