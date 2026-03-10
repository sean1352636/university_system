"""CLI interface for policies management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.policies.services.policies_service import PolicyService
from education_system.college_system.infrastructure.auth.core import UserAuth


def policies_menu(auth: UserAuth):
    """Policies management menu."""
    service = PolicyService(auth._db_path)

    while True:
        print_header("Policies")
        options = [
            ("1", "List Policies"),
            ("2", "Add Policy"),
            ("3", "View Policy"),
            ("4", "Update Policy"),
            ("5", "Delete Policy"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_policies(service)
        elif choice == "2":
            _add_policy(service)
        elif choice == "3":
            _view_policy(service)
        elif choice == "4":
            _update_policy(service)
        elif choice == "5":
            _delete_policy(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_policies(service):
    print_header("List Policies")
    try:
        items = service.list_policies()
        if not items:
            print("\n  No policies found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Title':<25}" + f"{'Category':<15}" + f"{'Version':<10}" + f"{'Author':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('title', '') or '')[:20].ljust(25) + str(item.get('category', '') or '')[:20].ljust(15) + str(item.get('version', '') or '')[:20].ljust(10) + str(item.get('author_id', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} policies")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_policy(service):
    print_header("Add Policy")
    try:
        data = {}
        for field in ['title', 'category', 'version', 'author_id', 'content']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_policy(**data)
        print(f"\n  Policy created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_policy(service):
    print_header("View Policy")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_policy(pk)
        if not item:
            print("\n  Policy not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_policy(service):
    print_header("Update Policy")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_policy(pk)
        if not item:
            print("\n  Policy not found.")
            return
        data = {}
        for field in ['title', 'category', 'version', 'author_id', 'content']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_policy(pk, **data)
            print(f"\n  Policy updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_policy(service):
    print_header("Delete Policy")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete policy {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_policy(pk)
            print(f"\n  Policy deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
