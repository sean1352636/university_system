"""Finance CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def finance_menu(auth):
    """Finance menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.admin.finance.services.finance_service import FinanceService

    svc = FinanceService(get_db_path())

    while True:
        print_header("Finance")
        print_menu([("1", "Transactions"), ("2", "Add transaction"), ("3", "Budgets"), ("4", "Add budget"), ("0", "Back")])
        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            for item in (svc.list_transactions() or []):
                print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            desc = input("  Description: ").strip()
            amt = input("  Amount: ").strip()
            cat = input("  Category: ").strip()
            try:
                svc.create_transaction(description=desc, amount=float(amt), category=cat)
                print("\n  Created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            for item in (svc.list_budgets() or []):
                print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "4":
            cat = input("  Category: ").strip()
            amt = input("  Amount: ").strip()
            try:
                svc.create_budget(category=cat, allocated_amount=float(amt))
                print("\n  Created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
