"""CLI interface for cpd records management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.cpd.services.cpd_service import CPDService
from education_system.college_system.infrastructure.auth.core import UserAuth


def cpd_menu(auth: UserAuth):
    """CPD Records management menu."""
    service = CPDService(auth._db_path)

    while True:
        print_header("CPD Records")
        options = [
            ("1", "List Records"),
            ("2", "Add Record"),
            ("3", "View Record"),
            ("4", "Update Record"),
            ("5", "Delete Record"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_records(service)
        elif choice == "2":
            _add_record(service)
        elif choice == "3":
            _view_record(service)
        elif choice == "4":
            _update_record(service)
        elif choice == "5":
            _delete_record(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_records(service):
    print_header("List Records")
    try:
        items = service.list_records()
        if not items:
            print("\n  No records found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Staff ID':<10}" + f"{'Title':<25}" + f"{'Provider':<18}" + f"{'Type':<12}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('staff_id', '') or '')[:20].ljust(10) + str(item.get('title', '') or '')[:20].ljust(25) + str(item.get('provider', '') or '')[:20].ljust(18) + str(item.get('cpd_type', '') or '')[:20].ljust(12))
        print(f"\n  Total: {len(items)} records")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_record(service):
    print_header("Add Record")
    try:
        data = {}
        for field in ['staff_id', 'title', 'provider', 'cpd_type', 'hours']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_record(**data)
        print(f"\n  Record created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_record(service):
    print_header("View Record")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_record(pk)
        if not item:
            print("\n  Record not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_record(service):
    print_header("Update Record")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_record(pk)
        if not item:
            print("\n  Record not found.")
            return
        data = {}
        for field in ['staff_id', 'title', 'provider', 'cpd_type', 'hours']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_record(pk, **data)
            print(f"\n  Record updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_record(service):
    print_header("Delete Record")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete record {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_record(pk)
            print(f"\n  Record deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
