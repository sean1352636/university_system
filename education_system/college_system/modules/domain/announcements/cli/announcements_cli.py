"""CLI interface for announcements management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.announcements.services.announcements_service import AnnouncementService
from education_system.college_system.infrastructure.auth.core import UserAuth


def announcements_menu(auth: UserAuth):
    """Announcements management menu."""
    service = AnnouncementService(auth._db_path)

    while True:
        print_header("Announcements")
        options = [
            ("1", "List Announcements"),
            ("2", "Add Announcement"),
            ("3", "View Announcement"),
            ("4", "Update Announcement"),
            ("5", "Delete Announcement"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_announcements(service)
        elif choice == "2":
            _add_announcement(service)
        elif choice == "3":
            _view_announcement(service)
        elif choice == "4":
            _update_announcement(service)
        elif choice == "5":
            _delete_announcement(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_announcements(service):
    print_header("List Announcements")
    try:
        items = service.list_announcements()
        if not items:
            print("\n  No announcements found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Title':<25}" + f"{'Content':<37}" + f"{'Author':<10}" + f"{'Category':<12}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('title', '') or '')[:20].ljust(25) + str(item.get('content', '') or '')[:20].ljust(37) + str(item.get('author_id', '') or '')[:20].ljust(10) + str(item.get('category', '') or '')[:20].ljust(12))
        print(f"\n  Total: {len(items)} announcements")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_announcement(service):
    print_header("Add Announcement")
    try:
        data = {}
        for field in ['title', 'content', 'author_id', 'category', 'target_role']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_announcement(**data)
        print(f"\n  Announcement created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_announcement(service):
    print_header("View Announcement")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_announcement(pk)
        if not item:
            print("\n  Announcement not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_announcement(service):
    print_header("Update Announcement")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_announcement(pk)
        if not item:
            print("\n  Announcement not found.")
            return
        data = {}
        for field in ['title', 'content', 'author_id', 'category', 'target_role']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_announcement(pk, **data)
            print(f"\n  Announcement updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_announcement(service):
    print_header("Delete Announcement")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete announcement {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_announcement(pk)
            print(f"\n  Announcement deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
