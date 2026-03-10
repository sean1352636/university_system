"""CPD Records CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def cpd_records_menu(auth):
    """CPD Records management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.staff.cpd.services.cpd_service import CPDService

    svc = CPDService(get_db_path())

    while True:
        print_header("CPD Records")
        print_menu([
            ("1", "List records"),
            ("2", "View details"),
            ("3", "Add Record"),
            ("4", "Update Record"),
            ("5", "Delete Record"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_records()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_record(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            staff_id = input("  Staff Id: ").strip()
            title = input("  Title: ").strip()
            date = input("  Date: ").strip()
            try:
                svc.create_record(staff_id=staff_id, title=title, date=date)
                print("\n  Record created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            staff_id = input("  Staff Id: ").strip()
            title = input("  Title: ").strip()
            date = input("  Date: ").strip()
            try:
                svc.update_record(int(pk), staff_id=staff_id, title=title, date=date)
                print("\n  Record updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_record(int(pk))
                print("\n  Record deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
