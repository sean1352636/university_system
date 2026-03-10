"""Staff Directory CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def staff_directory_menu(auth):
    """Staff Directory menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.staff.staff_directory.services.staff_directory_service import StaffDirectoryService

    svc = StaffDirectoryService(get_db_path())

    while True:
        print_header("Staff Directory")
        print_menu([("1", "List all"), ("2", "View details"), ("0", "Back")])
        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_staff()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_staff_member(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
