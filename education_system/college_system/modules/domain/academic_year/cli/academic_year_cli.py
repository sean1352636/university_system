"""CLI interface for academic year management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.academic_year.services.academic_year_service import AcademicYearService
from education_system.college_system.infrastructure.auth.core import UserAuth


def academic_year_menu(auth: UserAuth):
    """Academic Year management menu."""
    service = AcademicYearService(auth._db_path)

    while True:
        print_header("Academic Year")
        options = [
            ("1", "List Years"),
            ("2", "Add Year"),
            ("3", "View Year"),
            ("4", "Update Year"),
            ("5", "Delete Year"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_years(service)
        elif choice == "2":
            _add_year(service)
        elif choice == "3":
            _view_year(service)
        elif choice == "4":
            _update_year(service)
        elif choice == "5":
            _delete_year(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_years(service):
    print_header("List Years")
    try:
        items = service.list_years()
        if not items:
            print("\n  No years found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Name':<18}" + f"{'Start':<12}" + f"{'End':<12}" + f"{'Current':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('name', '') or '')[:20].ljust(18) + str(item.get('start_date', '') or '')[:20].ljust(12) + str(item.get('end_date', '') or '')[:20].ljust(12) + str(item.get('is_current', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} years")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_year(service):
    print_header("Add Year")
    try:
        data = {}
        for field in ['name', 'start_date', 'end_date', 'is_current', 'status']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_year(**data)
        print(f"\n  Year created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_year(service):
    print_header("View Year")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_year(pk)
        if not item:
            print("\n  Year not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_year(service):
    print_header("Update Year")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_year(pk)
        if not item:
            print("\n  Year not found.")
            return
        data = {}
        for field in ['name', 'start_date', 'end_date', 'is_current', 'status']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_year(pk, **data)
            print(f"\n  Year updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_year(service):
    print_header("Delete Year")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete year {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_year(pk)
            print(f"\n  Year deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
