"""CLI interface for skills passport management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.skills_passport.services.skills_passport_service import SkillsPassportService
from education_system.college_system.infrastructure.auth.core import UserAuth


def skills_passport_menu(auth: UserAuth):
    """Skills Passport management menu."""
    service = SkillsPassportService(auth._db_path)

    while True:
        print_header("Skills Passport")
        options = [
            ("1", "List Categories"),
            ("2", "Add Category"),
            ("3", "View Category"),
            ("4", "Update Category"),
            ("5", "Delete Category"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_categories(service)
        elif choice == "2":
            _add_category(service)
        elif choice == "3":
            _view_category(service)
        elif choice == "4":
            _update_category(service)
        elif choice == "5":
            _delete_category(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_categories(service):
    print_header("List Categories")
    try:
        items = service.list_categories()
        if not items:
            print("\n  No categories found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Name':<25}" + f"{'Description':<25}" + f"{'Order':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('name', '') or '')[:20].ljust(25) + str(item.get('description', '') or '')[:20].ljust(25) + str(item.get('display_order', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} categories")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_category(service):
    print_header("Add Category")
    try:
        data = {}
        for field in ['name', 'description', 'display_order']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_category(**data)
        print(f"\n  Category created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_category(service):
    print_header("View Category")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_category(pk)
        if not item:
            print("\n  Category not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_category(service):
    print_header("Update Category")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_category(pk)
        if not item:
            print("\n  Category not found.")
            return
        data = {}
        for field in ['name', 'description', 'display_order']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_category(pk, **data)
            print(f"\n  Category updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_category(service):
    print_header("Delete Category")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete category {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_category(pk)
            print(f"\n  Category deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
