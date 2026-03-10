"""CLI interface for surveys management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.surveys.services.surveys_service import SurveyService
from education_system.college_system.infrastructure.auth.core import UserAuth


def surveys_menu(auth: UserAuth):
    """Surveys management menu."""
    service = SurveyService(auth._db_path)

    while True:
        print_header("Surveys")
        options = [
            ("1", "List Surveys"),
            ("2", "Add Survey"),
            ("3", "View Survey"),
            ("4", "Update Survey"),
            ("5", "Delete Survey"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_surveys(service)
        elif choice == "2":
            _add_survey(service)
        elif choice == "3":
            _view_survey(service)
        elif choice == "4":
            _update_survey(service)
        elif choice == "5":
            _delete_survey(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_surveys(service):
    print_header("List Surveys")
    try:
        items = service.list_surveys()
        if not items:
            print("\n  No surveys found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Title':<25}" + f"{'Created By':<10}" + f"{'Type':<12}" + f"{'Anonymous':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('title', '') or '')[:20].ljust(25) + str(item.get('created_by', '') or '')[:20].ljust(10) + str(item.get('survey_type', '') or '')[:20].ljust(12) + str(item.get('is_anonymous', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} surveys")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_survey(service):
    print_header("Add Survey")
    try:
        data = {}
        for field in ['title', 'created_by', 'survey_type', 'is_anonymous', 'target_role']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_survey(**data)
        print(f"\n  Survey created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_survey(service):
    print_header("View Survey")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_survey(pk)
        if not item:
            print("\n  Survey not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_survey(service):
    print_header("Update Survey")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_survey(pk)
        if not item:
            print("\n  Survey not found.")
            return
        data = {}
        for field in ['title', 'created_by', 'survey_type', 'is_anonymous', 'target_role']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_survey(pk, **data)
            print(f"\n  Survey updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_survey(service):
    print_header("Delete Survey")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete survey {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_survey(pk)
            print(f"\n  Survey deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
