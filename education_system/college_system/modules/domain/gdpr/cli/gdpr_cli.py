"""CLI interface for gdpr & data protection management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.gdpr.services.gdpr_service import GDPRService
from education_system.college_system.infrastructure.auth.core import UserAuth


def gdpr_menu(auth: UserAuth):
    """GDPR & Data Protection management menu."""
    service = GDPRService(auth._db_path)

    while True:
        print_header("GDPR & Data Protection")
        options = [
            ("1", "List Subjects"),
            ("2", "Add Subject"),
            ("3", "View Subject"),
            ("4", "Update Subject"),
            ("5", "Delete Subject"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_subjects(service)
        elif choice == "2":
            _add_subject(service)
        elif choice == "3":
            _view_subject(service)
        elif choice == "4":
            _update_subject(service)
        elif choice == "5":
            _delete_subject(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_subjects(service):
    print_header("List Subjects")
    try:
        items = service.list_subjects()
        if not items:
            print("\n  No subjects found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'User ID':<10}" + f"{'Marketing':<10}" + f"{'Analytics':<10}" + f"{'Third Party':<10}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('user_id', '') or '')[:20].ljust(10) + str(item.get('consent_marketing', '') or '')[:20].ljust(10) + str(item.get('consent_analytics', '') or '')[:20].ljust(10) + str(item.get('consent_third_party', '') or '')[:20].ljust(10))
        print(f"\n  Total: {len(items)} subjects")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_subject(service):
    print_header("Add Subject")
    try:
        data = {}
        for field in ['user_id', 'consent_marketing', 'consent_analytics', 'consent_third_party', 'erasure_requested']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_subject(**data)
        print(f"\n  Subject created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_subject(service):
    print_header("View Subject")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_subject(pk)
        if not item:
            print("\n  Subject not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_subject(service):
    print_header("Update Subject")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_subject(pk)
        if not item:
            print("\n  Subject not found.")
            return
        data = {}
        for field in ['user_id', 'consent_marketing', 'consent_analytics', 'consent_third_party', 'erasure_requested']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_subject(pk, **data)
            print(f"\n  Subject updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_subject(service):
    print_header("Delete Subject")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete subject {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_subject(pk)
            print(f"\n  Subject deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
