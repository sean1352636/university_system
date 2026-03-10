"""Clubs CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def clubs_menu(auth):
    """Clubs management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.pupil_life.clubs.services.club_service import ClubService

    svc = ClubService(get_db_path())

    while True:
        print_header("Clubs")
        print_menu([
            ("1", "List clubs"),
            ("2", "View details"),
            ("3", "Add Club"),
            ("4", "Update Club"),
            ("5", "Delete Club"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_clubs()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_club(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            name = input("  Name: ").strip()
            description = input("  Description: ").strip()
            try:
                svc.create_club(name=name, description=description)
                print("\n  Club created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            name = input("  Name: ").strip()
            description = input("  Description: ").strip()
            try:
                svc.update_club(int(pk), name=name, description=description)
                print("\n  Club updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_club(int(pk))
                print("\n  Club deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
