"""CLI interface for intervention tracking management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.intervention_tracking.services.intervention_tracking_service import InterventionService
from education_system.college_system.infrastructure.auth.core import UserAuth


def intervention_tracking_menu(auth: UserAuth):
    """Intervention Tracking management menu."""
    service = InterventionService(auth._db_path)

    while True:
        print_header("Intervention Tracking")
        options = [
            ("1", "List Interventions"),
            ("2", "Add Intervention"),
            ("3", "View Intervention"),
            ("4", "Update Intervention"),
            ("5", "Delete Intervention"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_interventions(service)
        elif choice == "2":
            _add_intervention(service)
        elif choice == "3":
            _view_intervention(service)
        elif choice == "4":
            _update_intervention(service)
        elif choice == "5":
            _delete_intervention(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_interventions(service):
    print_header("List Interventions")
    try:
        items = service.list_interventions()
        if not items:
            print("\n  No interventions found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Student ID':<10}" + f"{'Staff ID':<10}" + f"{'Type':<15}" + f"{'Subject':<15}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('student_id', '') or '')[:20].ljust(10) + str(item.get('staff_id', '') or '')[:20].ljust(10) + str(item.get('intervention_type', '') or '')[:20].ljust(15) + str(item.get('subject_area', '') or '')[:20].ljust(15))
        print(f"\n  Total: {len(items)} interventions")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_intervention(service):
    print_header("Add Intervention")
    try:
        data = {}
        for field in ['student_id', 'staff_id', 'intervention_type', 'subject_area', 'sessions_total']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_intervention(**data)
        print(f"\n  Intervention created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_intervention(service):
    print_header("View Intervention")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_intervention(pk)
        if not item:
            print("\n  Intervention not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_intervention(service):
    print_header("Update Intervention")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_intervention(pk)
        if not item:
            print("\n  Intervention not found.")
            return
        data = {}
        for field in ['student_id', 'staff_id', 'intervention_type', 'subject_area', 'sessions_total']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_intervention(pk, **data)
            print(f"\n  Intervention updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_intervention(service):
    print_header("Delete Intervention")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete intervention {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_intervention(pk)
            print(f"\n  Intervention deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
