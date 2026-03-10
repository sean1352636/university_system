"""CLI interface for print credits management."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.print_credits.services.print_credits_service import PrintCreditService
from education_system.college_system.infrastructure.auth.core import UserAuth


def print_credits_menu(auth: UserAuth):
    """Print Credits management menu."""
    service = PrintCreditService(auth._db_path)

    while True:
        print_header("Print Credits")
        options = [
            ("1", "List Accounts"),
            ("2", "Add Account"),
            ("3", "View Account"),
            ("4", "Update Account"),
            ("5", "Delete Account"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_accounts(service)
        elif choice == "2":
            _add_account(service)
        elif choice == "3":
            _view_account(service)
        elif choice == "4":
            _update_account(service)
        elif choice == "5":
            _delete_account(service)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_accounts(service):
    print_header("List Accounts")
    try:
        items = service.list_accounts()
        if not items:
            print("\n  No accounts found.")
            return
        print("\n  " + f"{'ID':<6}" + f"{'Student ID':<10}" + f"{'Balance':<10}" + f"{'Quota':<10}" + f"{'Reset Date':<12}")
        print(f"  {'-' * 60}")
        for item in items:
            print("  " + str(item.get('id', ''))[:5].ljust(6) + str(item.get('student_id', '') or '')[:20].ljust(10) + str(item.get('balance', '') or '')[:20].ljust(10) + str(item.get('quota_remaining', '') or '')[:20].ljust(10) + str(item.get('quota_reset_date', '') or '')[:20].ljust(12))
        print(f"\n  Total: {len(items)} accounts")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_account(service):
    print_header("Add Account")
    try:
        data = {}
        for field in ['student_id', 'balance', 'quota_remaining', 'quota_reset_date']:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = service.create_account(**data)
        print(f"\n  Account created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_account(service):
    print_header("View Account")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_account(pk)
        if not item:
            print("\n  Account not found.")
            return
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_account(service):
    print_header("Update Account")
    try:
        pk = int(input("  Enter ID: ").strip())
        item = service.get_account(pk)
        if not item:
            print("\n  Account not found.")
            return
        data = {}
        for field in ['student_id', 'balance', 'quota_remaining', 'quota_reset_date']:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            service.update_account(pk, **data)
            print(f"\n  Account updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_account(service):
    print_header("Delete Account")
    try:
        pk = int(input("  Enter ID: ").strip())
        confirm = input(f"  Delete account {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            service.delete_account(pk)
            print(f"\n  Account deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")
