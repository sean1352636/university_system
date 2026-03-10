"""CLI interface for kpi dashboard management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.kpi_dashboard.services.kpi_dashboard_service import KPIDashboardService
from education_system.college_system.infrastructure.auth.core import UserAuth


def kpi_dashboard_menu(auth: UserAuth):
    """KPI Dashboard management menu."""
    service = KPIDashboardService(auth._db_path)

    while True:
        print_header("KPI Dashboard")
        options = [
            ("1", "List Targets"),
            ("2", "Add Target"),
            ("3", "View Target"),
            ("4", "Update Target"),
            ("5", "Delete Target"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_targets(service)
        elif choice == "2":
            _add_target(service)
        elif choice == "3":
            _view_target(service)
        elif choice == "4":
            _update_target(service)
        elif choice == "5":
            _delete_target(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_targets(service):
    print_header("List Targets")
    try:
        items = service.list_targets()
        if not items:
            print("\n  No targets found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Year':<10}" + f"{'KPI':<25}" + f"{'Category':<15}" + f"{'Target':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('academic_year', '') or '')[:20].ljust(10) + str(item.get('kpi_name', '') or '')[:20].ljust(25) + str(item.get('kpi_category', '') or '')[:20].ljust(15) + str(item.get('target_value', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} targets")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_target(service):
    print_header("Add Target")
    try:
        data = {}
        for field in ['academic_year', 'kpi_name', 'kpi_category', 'target_value', 'actual_value']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_target(**data)
        print(f"\n  Target created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_target(service):
    print_header("View Target")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_target(pk)
        if not item:
            print("\n  Target not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_target(service):
    print_header("Update Target")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_target(pk)
        if not item:
            print("\n  Target not found.")
            return
        data = {}
        for field in ['academic_year', 'kpi_name', 'kpi_category', 'target_value', 'actual_value']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_target(pk, **data)
            print(f"\n  Target updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_target(service):
    print_header("Delete Target")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete target {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_target(pk)
            print(f"\n  Target deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
