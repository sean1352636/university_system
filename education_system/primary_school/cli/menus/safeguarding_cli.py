"""Safeguarding CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def safeguarding_menu(auth):
    """Safeguarding management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.pastoral_care.safeguarding.services.safeguarding_service import SafeguardingService

    svc = SafeguardingService(get_db_path())

    while True:
        print_header("Safeguarding")
        print_menu([
            ("1", "List concerns"),
            ("2", "View details"),
            ("3", "Add Concern"),
            ("4", "Update Concern"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_concerns()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_concern(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            pupil_id = input("  Pupil Id: ").strip()
            concern_type = input("  Concern Type: ").strip()
            description = input("  Description: ").strip()
            try:
                svc.create_concern(pupil_id=pupil_id, concern_type=concern_type, description=description)
                print("\n  Concern created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            pupil_id = input("  Pupil Id: ").strip()
            concern_type = input("  Concern Type: ").strip()
            description = input("  Description: ").strip()
            try:
                svc.update_concern(int(pk), pupil_id=pupil_id, concern_type=concern_type, description=description)
                print("\n  Concern updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
