"""CLI interface for advanced search management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.advanced_search.services.advanced_search_service import AdvancedSearchService
from education_system.college_system.infrastructure.auth.core import UserAuth


def advanced_search_menu(auth: UserAuth):
    """Advanced Search management menu."""
    service = AdvancedSearchService(auth._db_path)

    while True:
        print_header("Advanced Search")
        options = [
            ("1", "List Searches"),
            ("2", "Add Search"),
            ("3", "View Search"),
            ("4", "Update Search"),
            ("5", "Delete Search"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_searches(service)
        elif choice == "2":
            _add_search(service)
        elif choice == "3":
            _view_search(service)
        elif choice == "4":
            _update_search(service)
        elif choice == "5":
            _delete_search(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_searches(service):
    print_header("List Searches")
    try:
        items = service.list_searches()
        if not items:
            print("\n  No searches found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'User ID':<10}" + f"{'Query':<25}" + f"{'Module':<12}" + f"{'Results':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('user_id', '') or '')[:20].ljust(10) + str(item.get('query', '') or '')[:20].ljust(25) + str(item.get('module_filter', '') or '')[:20].ljust(12) + str(item.get('result_count', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} searches")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_search(service):
    print_header("Add Search")
    try:
        data = {}
        for field in ['user_id', 'query', 'module_filter', 'result_count', 'searched_at']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_search(**data)
        print(f"\n  Search created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_search(service):
    print_header("View Search")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_search(pk)
        if not item:
            print("\n  Search not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_search(service):
    print_header("Update Search")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_search(pk)
        if not item:
            print("\n  Search not found.")
            return
        data = {}
        for field in ['user_id', 'query', 'module_filter', 'result_count', 'searched_at']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_search(pk, **data)
            print(f"\n  Search updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_search(service):
    print_header("Delete Search")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete search {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_search(pk)
            print(f"\n  Search deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
