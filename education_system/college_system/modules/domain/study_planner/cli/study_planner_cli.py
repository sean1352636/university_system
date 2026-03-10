"""CLI interface for study planner management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.study_planner.services.study_planner_service import StudyPlannerService
from education_system.college_system.infrastructure.auth.core import UserAuth


def study_planner_menu(auth: UserAuth):
    """Study Planner management menu."""
    service = StudyPlannerService(auth._db_path)

    while True:
        print_header("Study Planner")
        options = [
            ("1", "List Sessions"),
            ("2", "Add Session"),
            ("3", "View Session"),
            ("4", "Update Session"),
            ("5", "Delete Session"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_sessions(service)
        elif choice == "2":
            _add_session(service)
        elif choice == "3":
            _view_session(service)
        elif choice == "4":
            _update_session(service)
        elif choice == "5":
            _delete_session(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_sessions(service):
    print_header("List Sessions")
    try:
        items = service.list_sessions()
        if not items:
            print("\n  No sessions found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Student ID':<10}" + f"{'Subject':<15}" + f"{'Topic':<18}" + f"{'Date':<12}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('student_id', '') or '')[:20].ljust(10) + str(item.get('subject', '') or '')[:20].ljust(15) + str(item.get('topic', '') or '')[:20].ljust(18) + str(item.get('planned_date', '') or '')[:20].ljust(12))
        print(f"\n  Total: {len(items)} sessions")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_session(service):
    print_header("Add Session")
    try:
        data = {}
        for field in ['student_id', 'subject', 'topic', 'planned_date', 'planned_duration']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_session(**data)
        print(f"\n  Session created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_session(service):
    print_header("View Session")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_session(pk)
        if not item:
            print("\n  Session not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_session(service):
    print_header("Update Session")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_session(pk)
        if not item:
            print("\n  Session not found.")
            return
        data = {}
        for field in ['student_id', 'subject', 'topic', 'planned_date', 'planned_duration']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_session(pk, **data)
            print(f"\n  Session updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_session(service):
    print_header("Delete Session")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete session {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_session(pk)
            print(f"\n  Session deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
