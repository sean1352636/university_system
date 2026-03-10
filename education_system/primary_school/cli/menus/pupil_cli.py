"""Pupils CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def pupils_menu(auth):
    """Pupils management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.academics.pupils.services.pupil_service import PupilService

    svc = PupilService(get_db_path())

    while True:
        print_header("Pupils")
        print_menu([
            ("1", "List pupils"),
            ("2", "View details"),
            ("3", "Add Pupil"),
            ("4", "Update Pupil"),
            ("5", "Delete Pupil"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_pupils()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_pupil(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            first_name = input("  First Name: ").strip()
            last_name = input("  Last Name: ").strip()
            date_of_birth = input("  Date Of Birth: ").strip()
            year_group = input("  Year Group: ").strip()
            try:
                svc.create_pupil(first_name=first_name, last_name=last_name, date_of_birth=date_of_birth, year_group=year_group)
                print("\n  Pupil created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            first_name = input("  First Name: ").strip()
            last_name = input("  Last Name: ").strip()
            date_of_birth = input("  Date Of Birth: ").strip()
            year_group = input("  Year Group: ").strip()
            try:
                svc.update_pupil(int(pk), first_name=first_name, last_name=last_name, date_of_birth=date_of_birth, year_group=year_group)
                print("\n  Pupil updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_pupil(int(pk))
                print("\n  Pupil deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
