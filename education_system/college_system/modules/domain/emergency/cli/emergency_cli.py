"""CLI interface for emergency management management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.emergency.services.emergency_service import EmergencyService
from education_system.college_system.infrastructure.auth.core import UserAuth


def emergency_menu(auth: UserAuth):
    """Emergency Management management menu."""
    service = EmergencyService(auth._db_path)

    while True:
        print_header("Emergency Management")
        options = [
            ("1", "List Drills"),
            ("2", "Add Drill"),
            ("3", "View Drill"),
            ("4", "Update Drill"),
            ("5", "Delete Drill"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_drills(service)
        elif choice == "2":
            _add_drill(service)
        elif choice == "3":
            _view_drill(service)
        elif choice == "4":
            _update_drill(service)
        elif choice == "5":
            _delete_drill(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_drills(service):
    print_header("List Drills")
    try:
        items = service.list_drills()
        if not items:
            print("\n  No drills found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Type':<15}" + f"{'Date':<12}" + f"{'Actual':<12}" + f"{'Duration':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('drill_type', '') or '')[:20].ljust(15) + str(item.get('scheduled_date', '') or '')[:20].ljust(12) + str(item.get('actual_date', '') or '')[:20].ljust(12) + str(item.get('duration_minutes', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} drills")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_drill(service):
    print_header("Add Drill")
    try:
        data = {}
        for field in ['drill_type', 'scheduled_date', 'actual_date', 'duration_minutes', 'outcome']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_drill(**data)
        print(f"\n  Drill created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_drill(service):
    print_header("View Drill")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_drill(pk)
        if not item:
            print("\n  Drill not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_drill(service):
    print_header("Update Drill")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_drill(pk)
        if not item:
            print("\n  Drill not found.")
            return
        data = {}
        for field in ['drill_type', 'scheduled_date', 'actual_date', 'duration_minutes', 'outcome']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_drill(pk, **data)
            print(f"\n  Drill updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_drill(service):
    print_header("Delete Drill")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete drill {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_drill(pk)
            print(f"\n  Drill deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
