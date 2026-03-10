"""CLI interface for activity feed management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.activity_feed.services.activity_feed_service import ActivityFeedService
from education_system.college_system.infrastructure.auth.core import UserAuth


def activity_feed_menu(auth: UserAuth):
    """Activity Feed management menu."""
    service = ActivityFeedService(auth._db_path)

    while True:
        print_header("Activity Feed")
        options = [
            ("1", "List Feed_Items"),
            ("2", "Add Feed_Item"),
            ("3", "View Feed_Item"),
            ("4", "Update Feed_Item"),
            ("5", "Delete Feed_Item"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_feed_items(service)
        elif choice == "2":
            _add_feed_item(service)
        elif choice == "3":
            _view_feed_item(service)
        elif choice == "4":
            _update_feed_item(service)
        elif choice == "5":
            _delete_feed_item(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_feed_items(service):
    print_header("List Feed_Items")
    try:
        items = service.list_feed_items()
        if not items:
            print("\n  No feed_items found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'User ID':<10}" + f"{'Type':<12}" + f"{'Title':<25}" + f"{'Description':<37}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('user_id', '') or '')[:20].ljust(10) + str(item.get('activity_type', '') or '')[:20].ljust(12) + str(item.get('title', '') or '')[:20].ljust(25) + str(item.get('description', '') or '')[:20].ljust(37))
        print(f"\n  Total: {len(items)} feed_items")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_feed_item(service):
    print_header("Add Feed_Item")
    try:
        data = {}
        for field in ['user_id', 'activity_type', 'title', 'description', 'entity_type']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_feed_item(**data)
        print(f"\n  Feed_Item created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_feed_item(service):
    print_header("View Feed_Item")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_feed_item(pk)
        if not item:
            print("\n  Feed_Item not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_feed_item(service):
    print_header("Update Feed_Item")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_feed_item(pk)
        if not item:
            print("\n  Feed_Item not found.")
            return
        data = {}
        for field in ['user_id', 'activity_type', 'title', 'description', 'entity_type']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_feed_item(pk, **data)
            print(f"\n  Feed_Item updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_feed_item(service):
    print_header("Delete Feed_Item")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete feed_item {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_feed_item(pk)
            print(f"\n  Feed_Item deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
