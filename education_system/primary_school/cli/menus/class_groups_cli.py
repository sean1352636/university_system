"""Class Groups CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def class_groups_menu(auth):
    """Class Groups management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.pupil_life.class_groups.services.class_group_service import ClassGroupService

    svc = ClassGroupService(get_db_path())

    while True:
        print_header("Class Groups")
        print_menu([
            ("1", "List groups"),
            ("2", "View details"),
            ("3", "Add Group"),
            ("4", "Update Group"),
            ("5", "Delete Group"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_groups()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_group(int(pk))
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
                svc.create_group(name=name, year_group=year_group)
                print("\n  Group created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            name = input("  Name: ").strip()
            year_group = input("  Year Group: ").strip()
            try:
                svc.update_group(int(pk), name=name, year_group=year_group)
                print("\n  Group updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_group(int(pk))
                print("\n  Group deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
