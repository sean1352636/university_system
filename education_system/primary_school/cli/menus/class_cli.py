"""Classes CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def classes_menu(auth):
    """Classes management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.academics.classes.services.class_service import ClassService

    svc = ClassService(get_db_path())

    while True:
        print_header("Classes")
        print_menu([
            ("1", "List classes"),
            ("2", "View details"),
            ("3", "Add Class Record"),
            ("4", "Update Class Record"),
            ("5", "Delete Class Record"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_classes()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_class_record(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            name = input("  Name: ").strip()
            year_group = input("  Year Group: ").strip()
            try:
                svc.create_class_record(name=name, year_group=year_group)
                print("\n  Class Record created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            name = input("  Name: ").strip()
            year_group = input("  Year Group: ").strip()
            try:
                svc.update_class_record(int(pk), name=name, year_group=year_group)
                print("\n  Class Record updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_class_record(int(pk))
                print("\n  Class Record deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
