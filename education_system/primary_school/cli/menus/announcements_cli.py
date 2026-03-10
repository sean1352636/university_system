"""Announcements CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def announcements_menu(auth):
    """Announcements management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.communication.announcements.services.announcement_service import AnnouncementService

    svc = AnnouncementService(get_db_path())

    while True:
        print_header("Announcements")
        print_menu([
            ("1", "List announcements"),
            ("2", "View details"),
            ("3", "Add Announcement"),
            ("4", "Update Announcement"),
            ("5", "Delete Announcement"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_announcements()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_announcement(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            title = input("  Title: ").strip()
            content = input("  Content: ").strip()
            try:
                svc.create_announcement(title=title, content=content)
                print("\n  Announcement created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            title = input("  Title: ").strip()
            content = input("  Content: ").strip()
            try:
                svc.update_announcement(int(pk), title=title, content=content)
                print("\n  Announcement updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_announcement(int(pk))
                print("\n  Announcement deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
