"""CLI interface for multi-language management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.multi_language.services.multi_language_service import MultiLanguageService
from education_system.college_system.infrastructure.auth.core import UserAuth


def multi_language_menu(auth: UserAuth):
    """Multi-Language management menu."""
    service = MultiLanguageService(auth._db_path)

    while True:
        print_header("Multi-Language")
        options = [
            ("1", "List Overrides"),
            ("2", "Add Override"),
            ("3", "View Override"),
            ("4", "Update Override"),
            ("5", "Delete Override"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_overrides(service)
        elif choice == "2":
            _add_override(service)
        elif choice == "3":
            _view_override(service)
        elif choice == "4":
            _update_override(service)
        elif choice == "5":
            _delete_override(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_overrides(service):
    print_header("List Overrides")
    try:
        items = service.list_overrides()
        if not items:
            print("\n  No overrides found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Locale':<10}" + f"{'Key':<25}" + f"{'Value':<37}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('locale', '') or '')[:20].ljust(10) + str(item.get('key', '') or '')[:20].ljust(25) + str(item.get('value', '') or '')[:20].ljust(37))
        print(f"\n  Total: {len(items)} overrides")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_override(service):
    print_header("Add Override")
    try:
        data = {}
        for field in ['locale', 'key', 'value']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_override(**data)
        print(f"\n  Override created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_override(service):
    print_header("View Override")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_override(pk)
        if not item:
            print("\n  Override not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_override(service):
    print_header("Update Override")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_override(pk)
        if not item:
            print("\n  Override not found.")
            return
        data = {}
        for field in ['locale', 'key', 'value']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_override(pk, **data)
            print(f"\n  Override updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_override(service):
    print_header("Delete Override")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete override {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_override(pk)
            print(f"\n  Override deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
