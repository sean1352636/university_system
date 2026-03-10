"""CLI interface for feedback management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.feedback.services.feedback_service import FeedbackService
from education_system.college_system.infrastructure.auth.core import UserAuth


def feedback_menu(auth: UserAuth):
    """Feedback management menu."""
    service = FeedbackService(auth._db_path)

    while True:
        print_header("Feedback")
        options = [
            ("1", "List Feedbacks"),
            ("2", "Add Feedback"),
            ("3", "View Feedback"),
            ("4", "Update Feedback"),
            ("5", "Delete Feedback"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_feedbacks(service)
        elif choice == "2":
            _add_feedback(service)
        elif choice == "3":
            _view_feedback(service)
        elif choice == "4":
            _update_feedback(service)
        elif choice == "5":
            _delete_feedback(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_feedbacks(service):
    print_header("List Feedbacks")
    try:
        items = service.list_feedbacks()
        if not items:
            print("\n  No feedbacks found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'By':<10}" + f"{'Title':<25}" + f"{'Description':<37}" + f"{'Category':<12}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('submitted_by', '') or '')[:20].ljust(10) + str(item.get('title', '') or '')[:20].ljust(25) + str(item.get('description', '') or '')[:20].ljust(37) + str(item.get('category', '') or '')[:20].ljust(12))
        print(f"\n  Total: {len(items)} feedbacks")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_feedback(service):
    print_header("Add Feedback")
    try:
        data = {}
        for field in ['submitted_by', 'title', 'description', 'category', 'is_anonymous']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_feedback(**data)
        print(f"\n  Feedback created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_feedback(service):
    print_header("View Feedback")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_feedback(pk)
        if not item:
            print("\n  Feedback not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_feedback(service):
    print_header("Update Feedback")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_feedback(pk)
        if not item:
            print("\n  Feedback not found.")
            return
        data = {}
        for field in ['submitted_by', 'title', 'description', 'category', 'is_anonymous']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_feedback(pk, **data)
            print(f"\n  Feedback updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_feedback(service):
    print_header("Delete Feedback")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete feedback {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_feedback(pk)
            print(f"\n  Feedback deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
