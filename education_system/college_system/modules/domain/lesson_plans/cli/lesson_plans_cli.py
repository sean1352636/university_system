"""CLI interface for lesson plans management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.lesson_plans.services.lesson_plans_service import LessonPlanService
from education_system.college_system.infrastructure.auth.core import UserAuth


def lesson_plans_menu(auth: UserAuth):
    """Lesson Plans management menu."""
    service = LessonPlanService(auth._db_path)

    while True:
        print_header("Lesson Plans")
        options = [
            ("1", "List Plans"),
            ("2", "Add Plan"),
            ("3", "View Plan"),
            ("4", "Update Plan"),
            ("5", "Delete Plan"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_plans(service)
        elif choice == "2":
            _add_plan(service)
        elif choice == "3":
            _view_plan(service)
        elif choice == "4":
            _update_plan(service)
        elif choice == "5":
            _delete_plan(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_plans(service):
    print_header("List Plans")
    try:
        items = service.list_plans()
        if not items:
            print("\n  No plans found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Course ID':<10}" + f"{'Teacher ID':<10}" + f"{'Date':<12}" + f"{'Topic':<25}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('course_id', '') or '')[:20].ljust(10) + str(item.get('teacher_id', '') or '')[:20].ljust(10) + str(item.get('lesson_date', '') or '')[:20].ljust(12) + str(item.get('topic', '') or '')[:20].ljust(25))
        print(f"\n  Total: {len(items)} plans")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_plan(service):
    print_header("Add Plan")
    try:
        data = {}
        for field in ['course_id', 'teacher_id', 'lesson_date', 'topic', 'learning_objectives']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_plan(**data)
        print(f"\n  Plan created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_plan(service):
    print_header("View Plan")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_plan(pk)
        if not item:
            print("\n  Plan not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_plan(service):
    print_header("Update Plan")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_plan(pk)
        if not item:
            print("\n  Plan not found.")
            return
        data = {}
        for field in ['course_id', 'teacher_id', 'lesson_date', 'topic', 'learning_objectives']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_plan(pk, **data)
            print(f"\n  Plan updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_plan(service):
    print_header("Delete Plan")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete plan {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_plan(pk)
            print(f"\n  Plan deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
