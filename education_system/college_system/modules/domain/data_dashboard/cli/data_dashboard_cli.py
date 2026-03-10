"""CLI interface for data dashboard management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.data_dashboard.services.data_dashboard_service import DataDashboardService
from education_system.college_system.infrastructure.auth.core import UserAuth


def data_dashboard_menu(auth: UserAuth):
    """Data Dashboard management menu."""
    service = DataDashboardService(auth._db_path)

    while True:
        print_header("Data Dashboard")
        options = [
            ("1", "List Widgets"),
            ("2", "Add Widget"),
            ("3", "View Widget"),
            ("4", "Update Widget"),
            ("5", "Delete Widget"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_widgets(service)
        elif choice == "2":
            _add_widget(service)
        elif choice == "3":
            _view_widget(service)
        elif choice == "4":
            _update_widget(service)
        elif choice == "5":
            _delete_widget(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_widgets(service):
    print_header("List Widgets")
    try:
        items = service.list_widgets()
        if not items:
            print("\n  No widgets found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'User ID':<10}" + f"{'Type':<15}" + f"{'Config':<25}" + f"{'Order':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('user_id', '') or '')[:20].ljust(10) + str(item.get('widget_type', '') or '')[:20].ljust(15) + str(item.get('config', '') or '')[:20].ljust(25) + str(item.get('display_order', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} widgets")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_widget(service):
    print_header("Add Widget")
    try:
        data = {}
        for field in ['user_id', 'widget_type', 'config', 'display_order', 'is_visible']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_widget(**data)
        print(f"\n  Widget created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_widget(service):
    print_header("View Widget")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_widget(pk)
        if not item:
            print("\n  Widget not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_widget(service):
    print_header("Update Widget")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_widget(pk)
        if not item:
            print("\n  Widget not found.")
            return
        data = {}
        for field in ['user_id', 'widget_type', 'config', 'display_order', 'is_visible']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_widget(pk, **data)
            print(f"\n  Widget updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_widget(service):
    print_header("Delete Widget")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete widget {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_widget(pk)
            print(f"\n  Widget deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
