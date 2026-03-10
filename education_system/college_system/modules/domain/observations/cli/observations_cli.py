"""CLI interface for teaching observations management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.observations.services.observations_service import ObservationService
from education_system.college_system.infrastructure.auth.core import UserAuth


def observations_menu(auth: UserAuth):
    """Teaching Observations management menu."""
    service = ObservationService(auth._db_path)

    while True:
        print_header("Teaching Observations")
        options = [
            ("1", "List Observations"),
            ("2", "Add Observation"),
            ("3", "View Observation"),
            ("4", "Update Observation"),
            ("5", "Delete Observation"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_observations(service)
        elif choice == "2":
            _add_observation(service)
        elif choice == "3":
            _view_observation(service)
        elif choice == "4":
            _update_observation(service)
        elif choice == "5":
            _delete_observation(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_observations(service):
    print_header("List Observations")
    try:
        items = service.list_observations()
        if not items:
            print("\n  No observations found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Teacher ID':<10}" + f"{'Observer ID':<10}" + f"{'Date':<12}" + f"{'Course ID':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('teacher_id', '') or '')[:20].ljust(10) + str(item.get('observer_id', '') or '')[:20].ljust(10) + str(item.get('scheduled_date', '') or '')[:20].ljust(12) + str(item.get('course_id', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} observations")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_observation(service):
    print_header("Add Observation")
    try:
        data = {}
        for field in ['teacher_id', 'observer_id', 'scheduled_date', 'course_id', 'observation_type']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_observation(**data)
        print(f"\n  Observation created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_observation(service):
    print_header("View Observation")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_observation(pk)
        if not item:
            print("\n  Observation not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_observation(service):
    print_header("Update Observation")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_observation(pk)
        if not item:
            print("\n  Observation not found.")
            return
        data = {}
        for field in ['teacher_id', 'observer_id', 'scheduled_date', 'course_id', 'observation_type']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_observation(pk, **data)
            print(f"\n  Observation updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_observation(service):
    print_header("Delete Observation")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete observation {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_observation(pk)
            print(f"\n  Observation deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
