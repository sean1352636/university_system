"""
Grant Budget Menu - Grant funding budget management CLI.

Wired to GrantBudgetManager (categories, allocations, expenses,
transfers, and budget reporting).
"""

from education_system.systems.university.domain.staff.staff_hr.services.managers import (
    GrantBudgetManager,
)


def display_grant_budget_menu(user_id: str, is_admin: bool = False) -> None:
    """Display the grant budget management menu."""
    while True:
        print("\n" + "=" * 60)
        print("GRANT BUDGET MANAGEMENT")
        print("=" * 60)

        print("\n  1. View Budget Summary")
        print("  2. List Budget Categories")
        print("  3. Create Budget Category")
        print("  4. List Allocations")
        print("  5. Create Allocation")
        print("  6. Update Allocation")
        print("  7. List Expenses")
        print("  8. Submit Expense")
        print("  9. List Transfers")
        print("  10. Request Budget Transfer")

        if is_admin:
            print("\n--- Approvals ---")
            print("  11. Approve Expense")
            print("  12. Reject Expense")
            print("  13. Approve Transfer")
            print("  14. Reject Transfer")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _view_summary()
        elif choice == '2':
            _list_categories()
        elif choice == '3':
            _create_category()
        elif choice == '4':
            _list_allocations()
        elif choice == '5':
            _create_allocation()
        elif choice == '6':
            _update_allocation()
        elif choice == '7':
            _list_expenses()
        elif choice == '8':
            _submit_expense(user_id)
        elif choice == '9':
            _list_transfers()
        elif choice == '10':
            _request_transfer(user_id)
        elif choice == '11' and is_admin:
            _approve_expense(user_id)
        elif choice == '12' and is_admin:
            _reject_expense(user_id)
        elif choice == '13' and is_admin:
            _approve_transfer(user_id)
        elif choice == '14' and is_admin:
            _reject_transfer(user_id)
        else:
            print("Invalid choice.")


def _prompt_int(label: str) -> int | None:
    """Prompt for an integer, returning None on invalid/empty input."""
    raw = input(label).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print("Invalid number.")
        return None


def _prompt_float(label: str, default: float = 0.0) -> float:
    """Prompt for a float value with a default."""
    raw = input(label).strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print("Invalid amount; using default.")
        return default


def _view_summary() -> None:
    """View a grant application's budget summary."""
    grant_id = _prompt_int("Grant Application ID: ")
    if grant_id is None:
        return

    summary = GrantBudgetManager.get_grant_budget_summary(grant_id)
    print("\n" + "-" * 60)
    print(f"BUDGET SUMMARY - Grant #{grant_id}")
    print("-" * 60)
    print(f"  Total Allocated: {summary.get('total_allocated', 0)}")
    print(f"  Total Spent:     {summary.get('total_spent', 0)}")
    print(f"  Total Committed: {summary.get('total_committed', 0)}")
    print(f"  Total Remaining: {summary.get('total_remaining', 0)}")

    categories = summary.get('categories', [])
    if categories:
        print("\n  By Category:")
        for c in categories:
            print(f"    - {c.get('category_name')}: "
                  f"allocated {c.get('allocated_amount', 0)}, "
                  f"spent {c.get('spent_amount', 0)}, "
                  f"remaining {c.get('remaining_amount', 0)}")
    else:
        print("\n  No allocations recorded.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _list_categories() -> None:
    """List budget categories."""
    categories = GrantBudgetManager.get_categories(active_only=False)
    print("\n" + "-" * 60)
    print("BUDGET CATEGORIES")
    print("-" * 60)
    if categories:
        for c in categories:
            active = '' if c.get('is_active') else ' [inactive]'
            print(f"  {c.get('category_id')}. {c.get('name')}{active}")
            if c.get('description'):
                print(f"      {c.get('description')}")
    else:
        print("  No categories found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _create_category() -> None:
    """Create a budget category."""
    print("\n--- Create Budget Category ---")
    name = input("Category Name: ").strip()
    if not name:
        print("Name is required.")
        input("Press Enter to continue...")
        return
    description = input("Description: ").strip()
    try:
        category_id = GrantBudgetManager.create_category(name, description)
        print(f"\nCategory created. ID: {category_id}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _list_allocations() -> None:
    """List allocations for a grant application."""
    grant_id = _prompt_int("Grant Application ID: ")
    if grant_id is None:
        return
    allocations = GrantBudgetManager.get_allocations(grant_id)
    print("\n" + "-" * 60)
    print(f"ALLOCATIONS - Grant #{grant_id}")
    print("-" * 60)
    if allocations:
        for a in allocations:
            print(f"  {a.get('allocation_id')}. {a.get('category_name')} - "
                  f"allocated {a.get('allocated_amount', 0)}, "
                  f"remaining {a.get('remaining_amount', 0)}")
    else:
        print("  No allocations found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _create_allocation() -> None:
    """Create a budget allocation."""
    print("\n--- Create Allocation ---")
    grant_id = _prompt_int("Grant Application ID: ")
    if grant_id is None:
        return
    category_id = _prompt_int("Category ID: ")
    if category_id is None:
        return
    amount = _prompt_float("Allocated Amount: ")
    notes = input("Notes (optional): ").strip() or None
    try:
        allocation_id = GrantBudgetManager.create_allocation(
            grant_id, category_id, amount, notes=notes)
        print(f"\nAllocation created. ID: {allocation_id}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _update_allocation() -> None:
    """Update an allocation's amount or notes."""
    print("\n--- Update Allocation ---")
    allocation_id = _prompt_int("Allocation ID: ")
    if allocation_id is None:
        return
    amount_raw = input("New Allocated Amount (blank to skip): ").strip()
    notes_raw = input("New Notes (blank to skip): ").strip()

    data = {}
    if amount_raw:
        try:
            data['allocated_amount'] = float(amount_raw)
        except ValueError:
            print("Invalid amount.")
            input("Press Enter to continue...")
            return
    if notes_raw:
        data['notes'] = notes_raw

    if not data:
        print("Nothing to update.")
        input("Press Enter to continue...")
        return
    try:
        GrantBudgetManager.update_allocation(allocation_id, **data)
        print("\nAllocation updated.")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _list_expenses() -> None:
    """List expenses for a grant application."""
    grant_id = _prompt_int("Grant Application ID (blank for all): ")
    status = input("Filter by status (blank for all): ").strip() or None
    expenses = GrantBudgetManager.get_expenses(
        grant_application_id=grant_id, status=status)
    print("\n" + "-" * 60)
    print("EXPENSE ITEMS")
    print("-" * 60)
    if expenses:
        for e in expenses:
            print(f"  {e.get('expense_id')}. {e.get('description')} - "
                  f"{e.get('amount', 0)} [{e.get('status')}] "
                  f"({e.get('expense_date')})")
    else:
        print("  No expenses found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _submit_expense(user_id: str) -> None:
    """Submit an expense item."""
    print("\n--- Submit Expense ---")
    grant_id = _prompt_int("Grant Application ID: ")
    if grant_id is None:
        return
    allocation_id = _prompt_int("Allocation ID: ")
    if allocation_id is None:
        return
    category_id = _prompt_int("Category ID: ")
    if category_id is None:
        return
    description = input("Description: ").strip()
    amount = _prompt_float("Amount: ")
    expense_date = input("Expense Date (YYYY-MM-DD): ").strip()
    vendor = input("Vendor: ").strip()
    invoice_number = input("Invoice Number: ").strip()
    receipt_path = input("Receipt Path (optional): ").strip()
    notes = input("Notes (optional): ").strip() or None
    try:
        expense_id = GrantBudgetManager.submit_expense(
            grant_id, allocation_id, category_id, description, amount,
            expense_date, vendor, receipt_path, invoice_number,
            user_id, notes=notes)
        print(f"\nExpense submitted. ID: {expense_id}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _approve_expense(user_id: str) -> None:
    """Approve an expense item."""
    expense_id = _prompt_int("Expense ID to approve: ")
    if expense_id is None:
        return
    try:
        GrantBudgetManager.approve_expense(expense_id, user_id)
        print("\nExpense approved.")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _reject_expense(user_id: str) -> None:
    """Reject an expense item."""
    expense_id = _prompt_int("Expense ID to reject: ")
    if expense_id is None:
        return
    try:
        GrantBudgetManager.reject_expense(expense_id, user_id)
        print("\nExpense rejected.")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _list_transfers() -> None:
    """List budget transfers."""
    grant_id = _prompt_int("Grant Application ID (blank for all): ")
    status = input("Filter by status (blank for all): ").strip() or None
    transfers = GrantBudgetManager.get_transfers(
        grant_application_id=grant_id, status=status)
    print("\n" + "-" * 60)
    print("BUDGET TRANSFERS")
    print("-" * 60)
    if transfers:
        for t in transfers:
            print(f"  {t.get('transfer_id')}. {t.get('amount', 0)} "
                  f"from allocation {t.get('from_allocation_id')} "
                  f"to {t.get('to_allocation_id')} [{t.get('status')}]")
    else:
        print("  No transfers found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _request_transfer(user_id: str) -> None:
    """Request a budget transfer."""
    print("\n--- Request Budget Transfer ---")
    grant_id = _prompt_int("Grant Application ID: ")
    if grant_id is None:
        return
    from_id = _prompt_int("From Allocation ID: ")
    if from_id is None:
        return
    to_id = _prompt_int("To Allocation ID: ")
    if to_id is None:
        return
    amount = _prompt_float("Amount: ")
    reason = input("Reason: ").strip()
    try:
        transfer_id = GrantBudgetManager.request_transfer(
            grant_id, from_id, to_id, amount, reason, user_id)
        print(f"\nTransfer requested. ID: {transfer_id}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _approve_transfer(user_id: str) -> None:
    """Approve a budget transfer."""
    transfer_id = _prompt_int("Transfer ID to approve: ")
    if transfer_id is None:
        return
    try:
        GrantBudgetManager.approve_transfer(transfer_id, user_id)
        print("\nTransfer approved.")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _reject_transfer(user_id: str) -> None:
    """Reject a budget transfer."""
    transfer_id = _prompt_int("Transfer ID to reject: ")
    if transfer_id is None:
        return
    try:
        GrantBudgetManager.reject_transfer(transfer_id, user_id)
        print("\nTransfer rejected.")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")
