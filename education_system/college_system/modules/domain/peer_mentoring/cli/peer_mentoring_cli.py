"""CLI interface for peer mentoring management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.peer_mentoring.services.peer_mentoring_service import PeerMentoringService
from education_system.college_system.infrastructure.auth.core import UserAuth


def peer_mentoring_menu(auth: UserAuth):
    """Peer Mentoring management menu."""
    service = PeerMentoringService(auth._db_path)

    while True:
        print_header("Peer Mentoring")
        options = [
            ("1", "List Pairs"),
            ("2", "Add Pair"),
            ("3", "View Pair"),
            ("4", "Update Pair"),
            ("5", "Delete Pair"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_pairs(service)
        elif choice == "2":
            _add_pair(service)
        elif choice == "3":
            _view_pair(service)
        elif choice == "4":
            _update_pair(service)
        elif choice == "5":
            _delete_pair(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_pairs(service):
    print_header("List Pairs")
    try:
        items = service.list_pairs()
        if not items:
            print("\n  No pairs found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Mentor ID':<10}" + f"{'Mentee ID':<10}" + f"{'Matched By':<10}" + f"{'Subject':<15}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('mentor_id', '') or '')[:20].ljust(10) + str(item.get('mentee_id', '') or '')[:20].ljust(10) + str(item.get('matched_by', '') or '')[:20].ljust(10) + str(item.get('subject_area', '') or '')[:20].ljust(15))
        print(f"\n  Total: {len(items)} pairs")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_pair(service):
    print_header("Add Pair")
    try:
        data = {}
        for field in ['mentor_id', 'mentee_id', 'matched_by', 'subject_area', 'start_date']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_pair(**data)
        print(f"\n  Pair created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_pair(service):
    print_header("View Pair")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_pair(pk)
        if not item:
            print("\n  Pair not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_pair(service):
    print_header("Update Pair")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_pair(pk)
        if not item:
            print("\n  Pair not found.")
            return
        data = {}
        for field in ['mentor_id', 'mentee_id', 'matched_by', 'subject_area', 'start_date']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_pair(pk, **data)
            print(f"\n  Pair updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_pair(service):
    print_header("Delete Pair")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete pair {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_pair(pk)
            print(f"\n  Pair deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
