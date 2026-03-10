"""Pastoral Notes CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def pastoral_notes_menu(auth):
    """Pastoral Notes management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.pastoral_care.pastoral.services.pastoral_service import PastoralService

    svc = PastoralService(get_db_path())

    while True:
        print_header("Pastoral Notes")
        print_menu([
            ("1", "List notes"),
            ("2", "View details"),
            ("3", "Add Note"),
            ("4", "Update Note"),
            ("5", "Delete Note"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_notes()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_note(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            pupil_id = input("  Pupil Id: ").strip()
            note = input("  Note: ").strip()
            try:
                svc.create_note(pupil_id=pupil_id, note=note)
                print("\n  Note created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            pupil_id = input("  Pupil Id: ").strip()
            note = input("  Note: ").strip()
            try:
                svc.update_note(int(pk), pupil_id=pupil_id, note=note)
                print("\n  Note updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_note(int(pk))
                print("\n  Note deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
