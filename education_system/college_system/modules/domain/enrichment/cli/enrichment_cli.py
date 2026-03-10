"""CLI interface for enrichment management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.enrichment.services.enrichment_service import EnrichmentService
from education_system.college_system.infrastructure.auth.core import UserAuth


def enrichment_menu(auth: UserAuth):
    """Enrichment management menu."""
    service = EnrichmentService(auth._db_path)

    while True:
        print_header("Enrichment")
        options = [
            ("1", "List Activities"),
            ("2", "Add Activity"),
            ("3", "View Activity"),
            ("4", "Update Activity"),
            ("5", "Delete Activity"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_activities(service)
        elif choice == "2":
            _add_activity(service)
        elif choice == "3":
            _view_activity(service)
        elif choice == "4":
            _update_activity(service)
        elif choice == "5":
            _delete_activity(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_activities(service):
    print_header("List Activities")
    try:
        items = service.list_activities()
        if not items:
            print("\n  No activities found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Name':<25}" + f"{'Type':<12}" + f"{'Lead Staff':<10}" + f"{'Day':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('name', '') or '')[:20].ljust(25) + str(item.get('activity_type', '') or '')[:20].ljust(12) + str(item.get('lead_staff_id', '') or '')[:20].ljust(10) + str(item.get('day_of_week', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} activities")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_activity(service):
    print_header("Add Activity")
    try:
        data = {}
        for field in ['name', 'activity_type', 'lead_staff_id', 'day_of_week', 'time_slot']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_activity(**data)
        print(f"\n  Activity created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_activity(service):
    print_header("View Activity")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_activity(pk)
        if not item:
            print("\n  Activity not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_activity(service):
    print_header("Update Activity")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_activity(pk)
        if not item:
            print("\n  Activity not found.")
            return
        data = {}
        for field in ['name', 'activity_type', 'lead_staff_id', 'day_of_week', 'time_slot']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_activity(pk, **data)
            print(f"\n  Activity updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_activity(service):
    print_header("Delete Activity")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete activity {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_activity(pk)
            print(f"\n  Activity deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
