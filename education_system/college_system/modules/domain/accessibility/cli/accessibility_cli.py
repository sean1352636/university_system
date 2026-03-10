"""CLI interface for accessibility management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.accessibility.services.accessibility_service import AccessibilityService
from education_system.college_system.infrastructure.auth.core import UserAuth


def accessibility_menu(auth: UserAuth):
    """Accessibility management menu."""
    service = AccessibilityService(auth._db_path)

    while True:
        print_header("Accessibility")
        options = [
            ("1", "List Preferences"),
            ("2", "Add Preference"),
            ("3", "View Preference"),
            ("4", "Update Preference"),
            ("5", "Delete Preference"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_preferences(service)
        elif choice == "2":
            _add_preference(service)
        elif choice == "3":
            _view_preference(service)
        elif choice == "4":
            _update_preference(service)
        elif choice == "5":
            _delete_preference(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_preferences(service):
    print_header("List Preferences")
    try:
        items = service.list_preferences()
        if not items:
            print("\n  No preferences found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'User ID':<10}" + f"{'Theme':<12}" + f"{'Font Size':<10}" + f"{'Font':<12}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('user_id', '') or '')[:20].ljust(10) + str(item.get('theme', '') or '')[:20].ljust(12) + str(item.get('font_size', '') or '')[:20].ljust(10) + str(item.get('font_family', '') or '')[:20].ljust(12))
        print(f"\n  Total: {len(items)} preferences")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_preference(service):
    print_header("Add Preference")
    try:
        data = {}
        for field in ['user_id', 'theme', 'font_size', 'font_family', 'reduce_animations']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_preference(**data)
        print(f"\n  Preference created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_preference(service):
    print_header("View Preference")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_preference(pk)
        if not item:
            print("\n  Preference not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_preference(service):
    print_header("Update Preference")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_preference(pk)
        if not item:
            print("\n  Preference not found.")
            return
        data = {}
        for field in ['user_id', 'theme', 'font_size', 'font_family', 'reduce_animations']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_preference(pk, **data)
            print(f"\n  Preference updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_preference(service):
    print_header("Delete Preference")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete preference {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_preference(pk)
            print(f"\n  Preference deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
