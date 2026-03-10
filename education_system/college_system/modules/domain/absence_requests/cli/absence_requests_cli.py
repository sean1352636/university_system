"""CLI interface for absence requests management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.absence_requests.services.absence_requests_service import AbsenceRequestService
from education_system.college_system.infrastructure.auth.core import UserAuth


def absence_requests_menu(auth: UserAuth):
    """Absence Requests management menu."""
    service = AbsenceRequestService(auth._db_path)

    while True:
        print_header("Absence Requests")
        options = [
            ("1", "List Requests"),
            ("2", "Add Request"),
            ("3", "View Request"),
            ("4", "Update Request"),
            ("5", "Delete Request"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_requests(service)
        elif choice == "2":
            _add_request(service)
        elif choice == "3":
            _view_request(service)
        elif choice == "4":
            _update_request(service)
        elif choice == "5":
            _delete_request(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_requests(service):
    print_header("List Requests")
    try:
        items = service.list_requests()
        if not items:
            print("\n  No requests found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Staff ID':<10}" + f"{'Type':<12}" + f"{'Start':<12}" + f"{'End':<12}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('staff_id', '') or '')[:20].ljust(10) + str(item.get('absence_type', '') or '')[:20].ljust(12) + str(item.get('start_date', '') or '')[:20].ljust(12) + str(item.get('end_date', '') or '')[:20].ljust(12))
        print(f"\n  Total: {len(items)} requests")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_request(service):
    print_header("Add Request")
    try:
        data = {}
        for field in ['staff_id', 'absence_type', 'start_date', 'end_date', 'reason']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_request(**data)
        print(f"\n  Request created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_request(service):
    print_header("View Request")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_request(pk)
        if not item:
            print("\n  Request not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_request(service):
    print_header("Update Request")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_request(pk)
        if not item:
            print("\n  Request not found.")
            return
        data = {}
        for field in ['staff_id', 'absence_type', 'start_date', 'end_date', 'reason']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_request(pk, **data)
            print(f"\n  Request updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_request(service):
    print_header("Delete Request")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete request {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_request(pk)
            print(f"\n  Request deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
