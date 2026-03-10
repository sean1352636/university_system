"""CLI interface for staff appraisals management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.appraisals.services.appraisals_service import AppraisalService
from education_system.college_system.infrastructure.auth.core import UserAuth


def appraisals_menu(auth: UserAuth):
    """Staff Appraisals management menu."""
    service = AppraisalService(auth._db_path)

    while True:
        print_header("Staff Appraisals")
        options = [
            ("1", "List Appraisals"),
            ("2", "Add Appraisal"),
            ("3", "View Appraisal"),
            ("4", "Update Appraisal"),
            ("5", "Delete Appraisal"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_appraisals(service)
        elif choice == "2":
            _add_appraisal(service)
        elif choice == "3":
            _view_appraisal(service)
        elif choice == "4":
            _update_appraisal(service)
        elif choice == "5":
            _delete_appraisal(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_appraisals(service):
    print_header("List Appraisals")
    try:
        items = service.list_appraisals()
        if not items:
            print("\n  No appraisals found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Staff ID':<10}" + f"{'Appraiser ID':<10}" + f"{'Year':<12}" + f"{'Type':<12}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('staff_id', '') or '')[:20].ljust(10) + str(item.get('appraiser_id', '') or '')[:20].ljust(10) + str(item.get('academic_year', '') or '')[:20].ljust(12) + str(item.get('appraisal_type', '') or '')[:20].ljust(12))
        print(f"\n  Total: {len(items)} appraisals")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_appraisal(service):
    print_header("Add Appraisal")
    try:
        data = {}
        for field in ['staff_id', 'appraiser_id', 'academic_year', 'appraisal_type', 'overall_rating']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_appraisal(**data)
        print(f"\n  Appraisal created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_appraisal(service):
    print_header("View Appraisal")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_appraisal(pk)
        if not item:
            print("\n  Appraisal not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_appraisal(service):
    print_header("Update Appraisal")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_appraisal(pk)
        if not item:
            print("\n  Appraisal not found.")
            return
        data = {}
        for field in ['staff_id', 'appraiser_id', 'academic_year', 'appraisal_type', 'overall_rating']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_appraisal(pk, **data)
            print(f"\n  Appraisal updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_appraisal(service):
    print_header("Delete Appraisal")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete appraisal {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_appraisal(pk)
            print(f"\n  Appraisal deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
