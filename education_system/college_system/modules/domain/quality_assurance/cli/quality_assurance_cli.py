"""CLI interface for quality assurance management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.quality_assurance.services.quality_assurance_service import QualityAssuranceService
from education_system.college_system.infrastructure.auth.core import UserAuth


def quality_assurance_menu(auth: UserAuth):
    """Quality Assurance management menu."""
    service = QualityAssuranceService(auth._db_path)

    while True:
        print_header("Quality Assurance")
        options = [
            ("1", "List Reviews"),
            ("2", "Add Review"),
            ("3", "View Review"),
            ("4", "Update Review"),
            ("5", "Delete Review"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_reviews(service)
        elif choice == "2":
            _add_review(service)
        elif choice == "3":
            _view_review(service)
        elif choice == "4":
            _update_review(service)
        elif choice == "5":
            _delete_review(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_reviews(service):
    print_header("List Reviews")
    try:
        items = service.list_reviews()
        if not items:
            print("\n  No reviews found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Type':<15}" + f"{'Year':<10}" + f"{'Title':<25}" + f"{'Reviewer':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('review_type', '') or '')[:20].ljust(15) + str(item.get('academic_year', '') or '')[:20].ljust(10) + str(item.get('title', '') or '')[:20].ljust(25) + str(item.get('lead_reviewer_id', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} reviews")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_review(service):
    print_header("Add Review")
    try:
        data = {}
        for field in ['review_type', 'academic_year', 'title', 'lead_reviewer_id', 'overall_grade']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_review(**data)
        print(f"\n  Review created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_review(service):
    print_header("View Review")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_review(pk)
        if not item:
            print("\n  Review not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_review(service):
    print_header("Update Review")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_review(pk)
        if not item:
            print("\n  Review not found.")
            return
        data = {}
        for field in ['review_type', 'academic_year', 'title', 'lead_reviewer_id', 'overall_grade']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_review(pk, **data)
            print(f"\n  Review updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_review(service):
    print_header("Delete Review")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete review {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_review(pk)
            print(f"\n  Review deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
