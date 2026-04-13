"""Prevent Duty CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def prevent_duty_menu(auth):
    """Prevent Duty management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.admin.prevent_duty.services.prevent_duty_service import PreventDutyService

    svc = PreventDutyService(get_db_path())

    while True:
        print_header("Prevent Duty")
        print_menu([
            ("1", "List records"),
            ("2", "View details"),
            ("3", "Add record"),
            ("4", "Update record"),
            ("5", "Delete record"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_all()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            concern_type = input("  Concern Type: ").strip()
            description = input("  Description: ").strip()
            risk_level = input("  Risk Level: ").strip()
            status = input("  Status: ").strip()
            try:
                svc.create(concern_type=concern_type, description=description, risk_level=risk_level, status=status)
                print("\n  Record created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            concern_type = input("  Concern Type: ").strip()
            description = input("  Description: ").strip()
            risk_level = input("  Risk Level: ").strip()
            status = input("  Status: ").strip()
            try:
                svc.update(int(pk), concern_type=concern_type, description=description, risk_level=risk_level, status=status)
                print("\n  Record updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete(int(pk))
                print("\n  Record deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
