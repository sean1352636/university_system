"""CLI interface for visitor management management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.visitors.services.visitors_service import VisitorService
from education_system.college_system.infrastructure.auth.core import UserAuth


def visitors_menu(auth: UserAuth):
    """Visitor Management management menu."""
    service = VisitorService(auth._db_path)

    while True:
        print_header("Visitor Management")
        options = [
            ("1", "List Visitors"),
            ("2", "Add Visitor"),
            ("3", "View Visitor"),
            ("4", "Update Visitor"),
            ("5", "Delete Visitor"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_visitors(service)
        elif choice == "2":
            _add_visitor(service)
        elif choice == "3":
            _view_visitor(service)
        elif choice == "4":
            _update_visitor(service)
        elif choice == "5":
            _delete_visitor(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_visitors(service):
    print_header("List Visitors")
    try:
        items = service.list_visitors()
        if not items:
            print("\n  No visitors found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'First Name':<12}" + f"{'Last Name':<12}" + f"{'Organisation':<18}" + f"{'Purpose':<25}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('first_name', '') or '')[:20].ljust(12) + str(item.get('last_name', '') or '')[:20].ljust(12) + str(item.get('organization', '') or '')[:20].ljust(18) + str(item.get('purpose', '') or '')[:20].ljust(25))
        print(f"\n  Total: {len(items)} visitors")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_visitor(service):
    print_header("Add Visitor")
    try:
        data = {}
        for field in ['first_name', 'last_name', 'organization', 'purpose', 'visiting_staff_id']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_visitor(**data)
        print(f"\n  Visitor created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_visitor(service):
    print_header("View Visitor")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_visitor(pk)
        if not item:
            print("\n  Visitor not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_visitor(service):
    print_header("Update Visitor")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_visitor(pk)
        if not item:
            print("\n  Visitor not found.")
            return
        data = {}
        for field in ['first_name', 'last_name', 'organization', 'purpose', 'visiting_staff_id']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_visitor(pk, **data)
            print(f"\n  Visitor updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_visitor(service):
    print_header("Delete Visitor")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete visitor {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_visitor(pk)
            print(f"\n  Visitor deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
