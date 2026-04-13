"""Academic Year CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def academic_year_menu(auth):
    """Academic Year management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.academics.academic_year.services.academic_year_service import AcademicYearService

    svc = AcademicYearService(get_db_path())

    while True:
        print_header("Academic Year")
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
            items = svc.list_years()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_year(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            name = input("  Name: ").strip()
            start_date = input("  Start Date: ").strip()
            end_date = input("  End Date: ").strip()
            try:
                svc.create_year(name=name, start_date=start_date, end_date=end_date)
                print("\n  Record created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            name = input("  Name: ").strip()
            start_date = input("  Start Date: ").strip()
            end_date = input("  End Date: ").strip()
            try:
                svc.update_year(int(pk), name=name, start_date=start_date, end_date=end_date)
                print("\n  Record updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_year(int(pk))
                print("\n  Record deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
