"""CLI interface for work journal management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.work_journal.services.work_journal_service import WorkJournalService
from education_system.college_system.infrastructure.auth.core import UserAuth


def work_journal_menu(auth: UserAuth):
    """Work Journal management menu."""
    service = WorkJournalService(auth._db_path)

    while True:
        print_header("Work Journal")
        options = [
            ("1", "List Placements"),
            ("2", "Add Placement"),
            ("3", "View Placement"),
            ("4", "Update Placement"),
            ("5", "Delete Placement"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_placements(service)
        elif choice == "2":
            _add_placement(service)
        elif choice == "3":
            _view_placement(service)
        elif choice == "4":
            _update_placement(service)
        elif choice == "5":
            _delete_placement(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_placements(service):
    print_header("List Placements")
    try:
        items = service.list_placements()
        if not items:
            print("\n  No placements found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Student ID':<10}" + f"{'Employer':<25}" + f"{'Role':<18}" + f"{'Start':<12}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('student_id', '') or '')[:20].ljust(10) + str(item.get('employer_name', '') or '')[:20].ljust(25) + str(item.get('role_title', '') or '')[:20].ljust(18) + str(item.get('start_date', '') or '')[:20].ljust(12))
        print(f"\n  Total: {len(items)} placements")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_placement(service):
    print_header("Add Placement")
    try:
        data = {}
        for field in ['student_id', 'employer_name', 'role_title', 'start_date', 'end_date']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_placement(**data)
        print(f"\n  Placement created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_placement(service):
    print_header("View Placement")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_placement(pk)
        if not item:
            print("\n  Placement not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_placement(service):
    print_header("Update Placement")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_placement(pk)
        if not item:
            print("\n  Placement not found.")
            return
        data = {}
        for field in ['student_id', 'employer_name', 'role_title', 'start_date', 'end_date']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_placement(pk, **data)
            print(f"\n  Placement updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_placement(service):
    print_header("Delete Placement")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete placement {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_placement(pk)
            print(f"\n  Placement deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
