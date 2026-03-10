"""CLI interface for user management management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.user_management.services.user_management_service import UserManagementService
from education_system.college_system.infrastructure.auth.core import UserAuth


def user_management_menu(auth: UserAuth):
    """User Management management menu."""
    service = UserManagementService(auth._db_path)

    while True:
        print_header("User Management")
        options = [
            ("1", "List Templates"),
            ("2", "Add Template"),
            ("3", "View Template"),
            ("4", "Update Template"),
            ("5", "Delete Template"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_templates(service)
        elif choice == "2":
            _add_template(service)
        elif choice == "3":
            _view_template(service)
        elif choice == "4":
            _update_template(service)
        elif choice == "5":
            _delete_template(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_templates(service):
    print_header("List Templates")
    try:
        items = service.list_templates()
        if not items:
            print("\n  No templates found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Name':<18}" + f"{'Role':<12}" + f"{'Permissions':<25}" + f"{'Description':<25}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('template_name', '') or '')[:20].ljust(18) + str(item.get('role', '') or '')[:20].ljust(12) + str(item.get('permissions', '') or '')[:20].ljust(25) + str(item.get('description', '') or '')[:20].ljust(25))
        print(f"\n  Total: {len(items)} templates")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_template(service):
    print_header("Add Template")
    try:
        data = {}
        for field in ['template_name', 'role', 'permissions', 'description']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_template(**data)
        print(f"\n  Template created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_template(service):
    print_header("View Template")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_template(pk)
        if not item:
            print("\n  Template not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_template(service):
    print_header("Update Template")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_template(pk)
        if not item:
            print("\n  Template not found.")
            return
        data = {}
        for field in ['template_name', 'role', 'permissions', 'description']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_template(pk, **data)
            print(f"\n  Template updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_template(service):
    print_header("Delete Template")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete template {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_template(pk)
            print(f"\n  Template deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
