"""CLI interface for staff wellbeing management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.staff_wellbeing.services.staff_wellbeing_service import StaffWellbeingService
from education_system.college_system.infrastructure.auth.core import UserAuth


def staff_wellbeing_menu(auth: UserAuth):
    """Staff Wellbeing management menu."""
    service = StaffWellbeingService(auth._db_path)

    while True:
        print_header("Staff Wellbeing")
        options = [
            ("1", "List Checkins"),
            ("2", "Add Checkin"),
            ("3", "View Checkin"),
            ("4", "Update Checkin"),
            ("5", "Delete Checkin"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_checkins(service)
        elif choice == "2":
            _add_checkin(service)
        elif choice == "3":
            _view_checkin(service)
        elif choice == "4":
            _update_checkin(service)
        elif choice == "5":
            _delete_checkin(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_checkins(service):
    print_header("List Checkins")
    try:
        items = service.list_checkins()
        if not items:
            print("\n  No checkins found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Staff ID':<10}" + f"{'Date':<12}" + f"{'Mood':<10}" + f"{'Workload':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('staff_id', '') or '')[:20].ljust(10) + str(item.get('checkin_date', '') or '')[:20].ljust(12) + str(item.get('mood_rating', '') or '')[:20].ljust(10) + str(item.get('workload_rating', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} checkins")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_checkin(service):
    print_header("Add Checkin")
    try:
        data = {}
        for field in ['staff_id', 'checkin_date', 'mood_rating', 'workload_rating', 'stress_level']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_checkin(**data)
        print(f"\n  Checkin created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_checkin(service):
    print_header("View Checkin")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_checkin(pk)
        if not item:
            print("\n  Checkin not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_checkin(service):
    print_header("Update Checkin")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_checkin(pk)
        if not item:
            print("\n  Checkin not found.")
            return
        data = {}
        for field in ['staff_id', 'checkin_date', 'mood_rating', 'workload_rating', 'stress_level']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_checkin(pk, **data)
            print(f"\n  Checkin updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_checkin(service):
    print_header("Delete Checkin")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete checkin {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_checkin(pk)
            print(f"\n  Checkin deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
