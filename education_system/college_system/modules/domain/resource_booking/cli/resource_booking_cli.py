"""CLI interface for resource booking management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.resource_booking.services.resource_booking_service import ResourceBookingService
from education_system.college_system.infrastructure.auth.core import UserAuth


def resource_booking_menu(auth: UserAuth):
    """Resource Booking management menu."""
    service = ResourceBookingService(auth._db_path)

    while True:
        print_header("Resource Booking")
        options = [
            ("1", "List Resources"),
            ("2", "Add Resource"),
            ("3", "View Resource"),
            ("4", "Update Resource"),
            ("5", "Delete Resource"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_resources(service)
        elif choice == "2":
            _add_resource(service)
        elif choice == "3":
            _view_resource(service)
        elif choice == "4":
            _update_resource(service)
        elif choice == "5":
            _delete_resource(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_resources(service):
    print_header("List Resources")
    try:
        items = service.list_resources()
        if not items:
            print("\n  No resources found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Name':<18}" + f"{'Type':<12}" + f"{'Location':<15}" + f"{'Capacity':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('name', '') or '')[:20].ljust(18) + str(item.get('resource_type', '') or '')[:20].ljust(12) + str(item.get('location', '') or '')[:20].ljust(15) + str(item.get('capacity', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} resources")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_resource(service):
    print_header("Add Resource")
    try:
        data = {}
        for field in ['name', 'resource_type', 'location', 'capacity', 'is_available']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_resource(**data)
        print(f"\n  Resource created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_resource(service):
    print_header("View Resource")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_resource(pk)
        if not item:
            print("\n  Resource not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_resource(service):
    print_header("Update Resource")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_resource(pk)
        if not item:
            print("\n  Resource not found.")
            return
        data = {}
        for field in ['name', 'resource_type', 'location', 'capacity', 'is_available']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_resource(pk, **data)
            print(f"\n  Resource updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_resource(service):
    print_header("Delete Resource")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete resource {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_resource(pk)
            print(f"\n  Resource deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
