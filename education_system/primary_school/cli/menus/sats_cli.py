"""SATs CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def sats_menu(auth):
    """SATs management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.academics.sats.services.sats_service import SATsService

    svc = SATsService(get_db_path())

    while True:
        print_header("SATs")
        print_menu([
            ("1", "List results"),
            ("2", "View details"),
            ("3", "Add Result"),
            ("4", "Update Result"),
            ("5", "Delete Result"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_results()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_result(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            pupil_id = input("  Pupil Id: ").strip()
            subject = input("  Subject: ").strip()
            score = input("  Score: ").strip()
            year = input("  Year: ").strip()
            try:
                svc.create_result(pupil_id=pupil_id, subject=subject, score=score, year=year)
                print("\n  Result created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            pupil_id = input("  Pupil Id: ").strip()
            subject = input("  Subject: ").strip()
            score = input("  Score: ").strip()
            year = input("  Year: ").strip()
            try:
                svc.update_result(int(pk), pupil_id=pupil_id, subject=subject, score=score, year=year)
                print("\n  Result updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_result(int(pk))
                print("\n  Result deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
