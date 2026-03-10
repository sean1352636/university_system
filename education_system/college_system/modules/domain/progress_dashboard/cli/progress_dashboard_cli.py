"""CLI interface for progress dashboard management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.progress_dashboard.services.progress_dashboard_service import ProgressDashboardService
from education_system.college_system.infrastructure.auth.core import UserAuth


def progress_dashboard_menu(auth: UserAuth):
    """Progress Dashboard management menu."""
    service = ProgressDashboardService(auth._db_path)

    while True:
        print_header("Progress Dashboard")
        options = [
            ("1", "List Snapshots"),
            ("2", "Add Snapshot"),
            ("3", "View Snapshot"),
            ("4", "Update Snapshot"),
            ("5", "Delete Snapshot"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_snapshots(service)
        elif choice == "2":
            _add_snapshot(service)
        elif choice == "3":
            _view_snapshot(service)
        elif choice == "4":
            _update_snapshot(service)
        elif choice == "5":
            _delete_snapshot(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_snapshots(service):
    print_header("List Snapshots")
    try:
        items = service.list_snapshots()
        if not items:
            print("\n  No snapshots found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Student ID':<10}" + f"{'Date':<12}" + f"{'Attendance %':<10}" + f"{'Avg Grade':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('student_id', '') or '')[:20].ljust(10) + str(item.get('snapshot_date', '') or '')[:20].ljust(12) + str(item.get('attendance_percent', '') or '')[:20].ljust(10) + str(item.get('average_grade', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} snapshots")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_snapshot(service):
    print_header("Add Snapshot")
    try:
        data = {}
        for field in ['student_id', 'snapshot_date', 'attendance_percent', 'average_grade', 'assignments_due']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_snapshot(**data)
        print(f"\n  Snapshot created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_snapshot(service):
    print_header("View Snapshot")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_snapshot(pk)
        if not item:
            print("\n  Snapshot not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_snapshot(service):
    print_header("Update Snapshot")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_snapshot(pk)
        if not item:
            print("\n  Snapshot not found.")
            return
        data = {}
        for field in ['student_id', 'snapshot_date', 'attendance_percent', 'average_grade', 'assignments_due']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_snapshot(pk, **data)
            print(f"\n  Snapshot updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_snapshot(service):
    print_header("Delete Snapshot")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete snapshot {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_snapshot(pk)
            print(f"\n  Snapshot deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
