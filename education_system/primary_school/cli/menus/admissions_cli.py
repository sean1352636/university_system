"""Admissions CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def admissions_menu(auth):
    """Admissions management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.admin.admissions.services.admissions_service import AdmissionsService

    svc = AdmissionsService(get_db_path())

    while True:
        print_header("Admissions")
        print_menu([
            ("1", "List applications"),
            ("2", "View details"),
            ("3", "Add Application"),
            ("4", "Update Application"),
            ("5", "Delete Application"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_applications()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_application(int(pk))
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
            try:
                svc.create_application(first_name=first_name, last_name=last_name, date_of_birth=date_of_birth)
                print("\n  Application created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            first_name = input("  First Name: ").strip()
            last_name = input("  Last Name: ").strip()
            date_of_birth = input("  Date Of Birth: ").strip()
            try:
                svc.update_application(int(pk), first_name=first_name, last_name=last_name, date_of_birth=date_of_birth)
                print("\n  Application updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_application(int(pk))
                print("\n  Application deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
