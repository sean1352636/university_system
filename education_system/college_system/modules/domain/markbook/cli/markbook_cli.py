"""CLI interface for markbook management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.markbook.services.markbook_service import MarkbookService
from education_system.college_system.infrastructure.auth.core import UserAuth


def markbook_menu(auth: UserAuth):
    """Markbook management menu."""
    service = MarkbookService(auth._db_path)

    while True:
        print_header("Markbook")
        options = [
            ("1", "List Columns"),
            ("2", "Add Column"),
            ("3", "View Column"),
            ("4", "Update Column"),
            ("5", "Delete Column"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_columns(service)
        elif choice == "2":
            _add_column(service)
        elif choice == "3":
            _view_column(service)
        elif choice == "4":
            _update_column(service)
        elif choice == "5":
            _delete_column(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_columns(service):
    print_header("List Columns")
    try:
        items = service.list_columns()
        if not items:
            print("\n  No columns found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Course ID':<10}" + f"{'Column':<18}" + f"{'Type':<12}" + f"{'Max Score':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('course_id', '') or '')[:20].ljust(10) + str(item.get('column_name', '') or '')[:20].ljust(18) + str(item.get('column_type', '') or '')[:20].ljust(12) + str(item.get('max_score', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} columns")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_column(service):
    print_header("Add Column")
    try:
        data = {}
        for field in ['course_id', 'column_name', 'column_type', 'max_score', 'weight']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_column(**data)
        print(f"\n  Column created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_column(service):
    print_header("View Column")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_column(pk)
        if not item:
            print("\n  Column not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_column(service):
    print_header("Update Column")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_column(pk)
        if not item:
            print("\n  Column not found.")
            return
        data = {}
        for field in ['course_id', 'column_name', 'column_type', 'max_score', 'weight']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_column(pk, **data)
            print(f"\n  Column updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_column(service):
    print_header("Delete Column")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete column {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_column(pk)
            print(f"\n  Column deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
