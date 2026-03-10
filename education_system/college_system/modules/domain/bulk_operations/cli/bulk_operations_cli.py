"""CLI interface for bulk operations management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.bulk_operations.services.bulk_operations_service import BulkOperationService
from education_system.college_system.infrastructure.auth.core import UserAuth


def bulk_operations_menu(auth: UserAuth):
    """Bulk Operations management menu."""
    service = BulkOperationService(auth._db_path)

    while True:
        print_header("Bulk Operations")
        options = [
            ("1", "List Jobs"),
            ("2", "Add Job"),
            ("3", "View Job"),
            ("4", "Update Job"),
            ("5", "Delete Job"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_jobs(service)
        elif choice == "2":
            _add_job(service)
        elif choice == "3":
            _view_job(service)
        elif choice == "4":
            _update_job(service)
        elif choice == "5":
            _delete_job(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_jobs(service):
    print_header("List Jobs")
    try:
        items = service.list_jobs()
        if not items:
            print("\n  No jobs found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Type':<15}" + f"{'By':<10}" + f"{'File':<25}" + f"{'Total':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('job_type', '') or '')[:20].ljust(15) + str(item.get('initiated_by', '') or '')[:20].ljust(10) + str(item.get('file_path', '') or '')[:20].ljust(25) + str(item.get('total_rows', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} jobs")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_job(service):
    print_header("Add Job")
    try:
        data = {}
        for field in ['job_type', 'initiated_by', 'file_path', 'total_rows', 'processed_rows']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_job(**data)
        print(f"\n  Job created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_job(service):
    print_header("View Job")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_job(pk)
        if not item:
            print("\n  Job not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_job(service):
    print_header("Update Job")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_job(pk)
        if not item:
            print("\n  Job not found.")
            return
        data = {}
        for field in ['job_type', 'initiated_by', 'file_path', 'total_rows', 'processed_rows']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_job(pk, **data)
            print(f"\n  Job updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_job(service):
    print_header("Delete Job")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete job {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_job(pk)
            print(f"\n  Job deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
