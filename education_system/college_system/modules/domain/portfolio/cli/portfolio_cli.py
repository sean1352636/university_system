"""CLI interface for student portfolio management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.portfolio.services.portfolio_service import PortfolioService
from education_system.college_system.infrastructure.auth.core import UserAuth


def portfolio_menu(auth: UserAuth):
    """Student Portfolio management menu."""
    service = PortfolioService(auth._db_path)

    while True:
        print_header("Student Portfolio")
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
        print("\n  " + f"{'ID':<6}" + f"{'Student ID':<10}" + f"{'Title':<25}" + f"{'Type':<12}" + f"{'Description':<25}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('student_id', '') or '')[:20].ljust(10) + str(item.get('title', '') or '')[:20].ljust(25) + str(item.get('item_type', '') or '')[:20].ljust(12) + str(item.get('description', '') or '')[:20].ljust(25))
        print(f"\n  Total: {len(items)} items")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_item(service):
    print_header("Add Item")
    try:
        data = {}
        for field in ['student_id', 'title', 'item_type', 'description', 'file_path']:
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
        for field in ['student_id', 'title', 'item_type', 'description', 'file_path']:
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
