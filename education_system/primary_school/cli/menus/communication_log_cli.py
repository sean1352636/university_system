"""Communication Log CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def communication_log_menu(auth):
    """Communication Log management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.communication.communication_log.services.communication_log_service import CommunicationLogService

    svc = CommunicationLogService(get_db_path())

    while True:
        print_header("Communication Log")
        print_menu([
            ("1", "List entries"),
            ("2", "View details"),
            ("3", "Add Entry"),
            ("4", "Update Entry"),
            ("5", "Delete Entry"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_entries()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_entry(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            pupil_id = input("  Pupil Id: ").strip()
            communication_type = input("  Communication Type: ").strip()
            summary = input("  Summary: ").strip()
            try:
                svc.create_entry(pupil_id=pupil_id, communication_type=communication_type, summary=summary)
                print("\n  Entry created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            pupil_id = input("  Pupil Id: ").strip()
            communication_type = input("  Communication Type: ").strip()
            summary = input("  Summary: ").strip()
            try:
                svc.update_entry(int(pk), pupil_id=pupil_id, communication_type=communication_type, summary=summary)
                print("\n  Entry updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_entry(int(pk))
                print("\n  Entry deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
