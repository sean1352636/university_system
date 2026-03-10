"""CLI interface for meal ordering management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.meal_ordering.services.meal_ordering_service import MealOrderingService
from education_system.college_system.infrastructure.auth.core import UserAuth


def meal_ordering_menu(auth: UserAuth):
    """Meal Ordering management menu."""
    service = MealOrderingService(auth._db_path)

    while True:
        print_header("Meal Ordering")
        options = [
            ("1", "List Items"),
            ("2", "Add Item"),
            ("3", "View Item"),
            ("4", "Update Item"),
            ("5", "Delete Item"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_items(service)
        elif choice == "2":
            _add_item(service)
        elif choice == "3":
            _view_item(service)
        elif choice == "4":
            _update_item(service)
        elif choice == "5":
            _delete_item(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_items(service):
    print_header("List Items")
    try:
        items = service.list_items()
        if not items:
            print("\n  No items found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Name':<25}" + f"{'Category':<12}" + f"{'Price':<10}" + f"{'Dietary':<15}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('name', '') or '')[:20].ljust(25) + str(item.get('category', '') or '')[:20].ljust(12) + str(item.get('price', '') or '')[:20].ljust(10) + str(item.get('dietary_tags', '') or '')[:20].ljust(15))
        print(f"\n  Total: {len(items)} items")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_item(service):
    print_header("Add Item")
    try:
        data = {}
        for field in ['name', 'category', 'price', 'dietary_tags', 'description']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_item(**data)
        print(f"\n  Item created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_item(service):
    print_header("View Item")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_item(pk)
        if not item:
            print("\n  Item not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_item(service):
    print_header("Update Item")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_item(pk)
        if not item:
            print("\n  Item not found.")
            return
        data = {}
        for field in ['name', 'category', 'price', 'dietary_tags', 'description']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_item(pk, **data)
            print(f"\n  Item updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_item(service):
    print_header("Delete Item")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete item {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_item(pk)
            print(f"\n  Item deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
