"""
Expense Menu - Expense claims and reimbursement CLI.
"""

from datetime import datetime
from education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.expense_manager import ExpenseManager
from education_system.university_system.modules.domain.staff_comms.staff_hr.cli.validators import (
    validate_date, validate_required, validate_choice, validate_currency,
    validate_integer, validate_confirmation,
    get_date_input, get_choice_input, get_required_input, get_currency_input,
    get_integer_input, get_confirmation, ValidationError
)


def display_expense_menu(user_id: str, is_admin: bool = False) -> None:
    """Display expense claims menu."""
    while True:
        print("\n" + "=" * 60)
        print("EXPENSE CLAIMS & REIMBURSEMENTS")
        print("=" * 60)

        print("\n--- My Expenses ---")
        print("  1. Submit New Expense Claim")
        print("  2. View My Claims")
        print("  3. View Pending Claims")
        print("  4. View Reimbursement Status")

        if is_admin:
            print("\n--- Approvals ---")
            print("  5. Review Pending Approvals")
            print("  6. Search All Claims")

            print("\n--- Administration ---")
            print("  7. Manage Categories")
            print("  8. Manage Policies")
            print("  9. Process Reimbursements")
            print(" 10. Expense Reports")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _submit_claim(user_id)
        elif choice == '2':
            _view_my_claims(user_id)
        elif choice == '3':
            _view_pending_claims(user_id)
        elif choice == '4':
            _view_reimbursement_status(user_id)
        elif choice == '5' and is_admin:
            _review_approvals(user_id)
        elif choice == '6' and is_admin:
            _search_claims()
        elif choice == '7' and is_admin:
            _manage_categories()
        elif choice == '8' and is_admin:
            _manage_policies()
        elif choice == '9' and is_admin:
            _process_reimbursements()
        elif choice == '10' and is_admin:
            _expense_reports()
        else:
            print("Invalid choice.")


def _submit_claim(user_id: str) -> None:
    """Submit a new expense claim."""
    print("\n--- Submit Expense Claim ---")

    # Show categories
    categories = ExpenseManager.get_all_categories()
    if not categories:
        print("\nNo expense categories configured. Contact administrator.")
        input("Press Enter to continue...")
        return

    print("\nAvailable Categories:")
    for i, cat in enumerate(categories, 1):
        max_info = f" (max: £{cat['max_amount']:.2f})" if cat.get('max_amount') else ""
        receipt_info = " [Receipt Required]" if cat.get('requires_receipt') else ""
        print(f"  {i}. {cat['name']}{max_info}{receipt_info}")

    try:
        cat_choice = get_integer_input(
            "\nSelect category (number): ", "Category",
            min_value=1, max_value=len(categories)
        )
        category = categories[cat_choice - 1]
    except ValidationError as e:
        print(f"Error: {e}")
        return

    try:
        amount = get_currency_input("Amount: $", "Amount", min_value=0.01)
    except ValidationError as e:
        print(f"Error: {e}")
        return

    # Check category limit
    if category.get('max_amount') and amount > category['max_amount']:
        print(f"\nWarning: Amount exceeds category limit of £{category['max_amount']:.2f}")
        if not get_confirmation("Continue anyway?"):
            print("Cancelled.")
            return

    try:
        description = get_required_input("Description: ", "Description")
        expense_date = get_date_input("Expense Date (YYYY-MM-DD): ", "Expense Date")
    except ValidationError as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")
        return

    receipt_path = input("Receipt Path (Enter for none): ").strip() or None

    if category.get('requires_receipt') and not receipt_path:
        print("\nThis category requires a receipt.")
        try:
            receipt_path = get_required_input("Receipt Path: ", "Receipt Path")
        except ValidationError as e:
            print(f"Error: {e}")
            print("Cancelled - receipt required.")
            input("Press Enter to continue...")
            return

    try:
        claim_id = ExpenseManager.create_claim(
            user_id,
            category_id=category['category_id'],
            amount=amount,
            description=description,
            expense_date=expense_date,
            receipt_path=receipt_path
        )
        print(f"\nExpense claim submitted successfully. Claim ID: {claim_id}")
    except Exception as e:
        print(f"\nError submitting claim: {e}")

    input("Press Enter to continue...")


def _view_my_claims(user_id: str) -> None:
    """View user's expense claims."""
    print("\n--- My Expense Claims ---")
    print("Filter by status:")
    print("  1. All Claims")
    print("  2. Pending")
    print("  3. Approved")
    print("  4. Rejected")
    print("  5. Reimbursed")

    filter_choice = input("\nChoice (default: All): ").strip()

    status_map = {'2': 'pending', '3': 'approved', '4': 'rejected', '5': 'reimbursed'}
    status = status_map.get(filter_choice)

    claims = ExpenseManager.get_user_claims(user_id, status=status)

    if not claims:
        print("\nNo claims found.")
    else:
        print(f"\n--- {len(claims)} Claims ---")
        total = 0
        for c in claims:
            status_icon = {
                'pending': '⏳', 'approved': '✓', 'rejected': '✗',
                'reimbursed': '💰', 'cancelled': '○'
            }.get(c.get('status', ''), '?')

            print(f"\n{status_icon} Claim #{c.get('claim_id')}")
            print(f"   Amount: £{c.get('amount', 0):.2f}")
            print(f"   Category: {c.get('category_name', 'N/A')}")
            print(f"   Date: {c.get('expense_date')} | Status: {c.get('status')}")
            print(f"   Description: {c.get('description', '')[:50]}")
            if c.get('status') == 'approved':
                total += c.get('amount', 0)

        print(f"\nTotal Approved: £{total:.2f}")

    input("\nPress Enter to continue...")


def _view_pending_claims(user_id: str) -> None:
    """View pending claims."""
    claims = ExpenseManager.get_user_claims(user_id, status='pending')

    if not claims:
        print("\nNo pending claims.")
    else:
        print(f"\n--- {len(claims)} Pending Claims ---")
        for c in claims:
            print(f"\n⏳ Claim #{c.get('claim_id')}")
            print(f"   Amount: £{c.get('amount', 0):.2f}")
            print(f"   Submitted: {c.get('submitted_date')}")
            print(f"   Description: {c.get('description', '')[:50]}")

    input("\nPress Enter to continue...")


def _view_reimbursement_status(user_id: str) -> None:
    """View reimbursement status."""
    claims = ExpenseManager.get_user_claims(user_id, status='approved')
    reimbursed = ExpenseManager.get_user_claims(user_id, status='reimbursed')

    print("\n--- Reimbursement Status ---")

    pending_amount = sum(c.get('amount', 0) for c in claims)
    reimbursed_amount = sum(c.get('amount', 0) for c in reimbursed)

    print(f"\nPending Reimbursement: £{pending_amount:.2f} ({len(claims)} claims)")
    print(f"Total Reimbursed: £{reimbursed_amount:.2f} ({len(reimbursed)} claims)")

    if claims:
        print("\n--- Awaiting Reimbursement ---")
        for c in claims:
            print(f"  Claim #{c.get('claim_id')}: £{c.get('amount', 0):.2f} - {c.get('description', '')[:30]}")

    if reimbursed:
        print("\n--- Recent Reimbursements ---")
        for c in reimbursed[:5]:
            print(f"  Claim #{c.get('claim_id')}: £{c.get('amount', 0):.2f}")

    input("\nPress Enter to continue...")


def _review_approvals(approver_id: str) -> None:
    """Review and approve/reject claims."""
    claims = ExpenseManager.get_pending_approvals(approver_id)

    if not claims:
        print("\nNo claims pending your approval.")
        input("Press Enter to continue...")
        return

    print(f"\n--- {len(claims)} Claims Pending Approval ---")

    for c in claims:
        print(f"\n{'=' * 40}")
        print(f"Claim #{c.get('claim_id')} - {c.get('user_id')}")
        print(f"Amount: £{c.get('amount', 0):.2f}")
        print(f"Category: {c.get('category_name', 'N/A')}")
        print(f"Date: {c.get('expense_date')}")
        print(f"Description: {c.get('description')}")
        print(f"Receipt: {'Yes' if c.get('receipt_path') else 'No'}")

        print("\nActions: [A]pprove, [R]eject, [S]kip, [Q]uit")
        action = input("Action: ").strip().upper()

        if action == 'Q':
            break
        elif action == 'A':
            comments = input("Comments (optional): ").strip()
            ExpenseManager.approve_claim(c['claim_id'], approver_id, comments)
            print("Claim approved.")
        elif action == 'R':
            comments = input("Rejection reason: ").strip()
            if comments:
                ExpenseManager.reject_claim(c['claim_id'], approver_id, comments)
                print("Claim rejected.")
            else:
                print("Rejection requires a reason. Skipped.")
        elif action == 'S':
            continue

    input("\nPress Enter to continue...")


def _search_claims() -> None:
    """Search all claims."""
    print("\n--- Search Claims ---")
    print("Search by:")
    print("  1. User ID")
    print("  2. Status")
    print("  3. Category")
    print("  4. Date Range")
    print("  5. View All")

    search_choice = input("\nChoice: ").strip()

    claims = []
    if search_choice == '1':
        try:
            user_id = get_required_input("User ID: ", "User ID")
        except ValidationError as e:
            print(f"Error: {e}")
            return
        claims = ExpenseManager.get_user_claims(user_id)
    elif search_choice == '2':
        statuses = ['pending', 'approved', 'rejected', 'reimbursed', 'cancelled']
        try:
            status = get_choice_input(
                f"Status ({', '.join(statuses)}): ", statuses, "Status"
            )
        except ValidationError as e:
            print(f"Error: {e}")
            return
        claims = ExpenseManager.search_claims(status=status)
    elif search_choice == '3':
        categories = ExpenseManager.get_all_categories()
        for i, cat in enumerate(categories, 1):
            print(f"  {i}. {cat['name']}")
        try:
            cat_choice = get_integer_input(
                "Category (number): ", "Category",
                min_value=1, max_value=len(categories)
            )
            category_id = categories[cat_choice - 1]['category_id']
            claims = ExpenseManager.search_claims(category_id=category_id)
        except ValidationError as e:
            print(f"Error: {e}")
            return
    elif search_choice == '4':
        try:
            start_date = get_date_input("Start Date (YYYY-MM-DD): ", "Start Date")
            end_date = get_date_input("End Date (YYYY-MM-DD): ", "End Date")
        except ValidationError as e:
            print(f"Error: {e}")
            return
        claims = ExpenseManager.search_claims(start_date=start_date, end_date=end_date)
    elif search_choice == '5':
        claims = ExpenseManager.search_claims()
    else:
        print("Invalid choice.")
        return

    if not claims:
        print("\nNo claims found.")
    else:
        print(f"\n--- Found {len(claims)} Claims ---")
        total = sum(c.get('amount', 0) for c in claims)
        for c in claims:
            print(f"\n#{c.get('claim_id')} - {c.get('user_id')}")
            print(f"  £{c.get('amount', 0):.2f} | {c.get('status')} | {c.get('expense_date')}")
            print(f"  {c.get('description', '')[:50]}")
        print(f"\nTotal: £{total:.2f}")

    input("\nPress Enter to continue...")


def _manage_categories() -> None:
    """Manage expense categories."""
    while True:
        print("\n--- Manage Expense Categories ---")
        categories = ExpenseManager.get_all_categories()

        if categories:
            print("\nCurrent Categories:")
            for cat in categories:
                status = "Active" if cat.get('is_active') else "Inactive"
                max_amt = f"Max: £{cat['max_amount']:.2f}" if cat.get('max_amount') else "No limit"
                receipt = "Receipt required" if cat.get('requires_receipt') else ""
                print(f"  [{cat['category_id']}] {cat['name']} - {status} | {max_amt} {receipt}")

        print("\nOptions:")
        print("  1. Add Category")
        print("  2. Update Category")
        print("  3. Toggle Active Status")
        print("  0. Return")

        choice = input("\nChoice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            name = input("Category Name: ").strip()
            description = input("Description: ").strip()
            max_amount = input("Max Amount (Enter for none): ").strip()
            requires_receipt = input("Requires Receipt? (yes/no): ").strip().lower() == 'yes'

            try:
                cat_id = ExpenseManager.create_category(
                    name=name,
                    description=description,
                    max_amount=float(max_amount) if max_amount else None,
                    requires_receipt=requires_receipt
                )
                print(f"Category created. ID: {cat_id}")
            except Exception as e:
                print(f"Error: {e}")

        elif choice == '2':
            cat_id = input("Category ID to update: ").strip()
            name = input("New Name (Enter to skip): ").strip()
            max_amount = input("New Max Amount (Enter to skip): ").strip()

            updates = {}
            if name:
                updates['name'] = name
            if max_amount:
                updates['max_amount'] = float(max_amount)

            if updates:
                ExpenseManager.update_category(int(cat_id), **updates)
                print("Category updated.")

        elif choice == '3':
            cat_id = input("Category ID to toggle: ").strip()
            # Get current status and toggle
            for cat in categories:
                if cat['category_id'] == int(cat_id):
                    new_status = not cat.get('is_active', True)
                    ExpenseManager.update_category(int(cat_id), is_active=new_status)
                    print(f"Category {'activated' if new_status else 'deactivated'}.")
                    break

    input("Press Enter to continue...")


def _manage_policies() -> None:
    """Manage expense policies."""
    while True:
        print("\n--- Manage Expense Policies ---")
        policies = ExpenseManager.get_all_policies()

        if policies:
            print("\nCurrent Policies:")
            for p in policies:
                status = "Active" if p.get('is_active') else "Inactive"
                print(f"\n  [{p['policy_id']}] {p['name']} ({status})")
                print(f"      {p.get('description', '')[:60]}")
                if p.get('max_single_expense'):
                    print(f"      Max Single: £{p['max_single_expense']:.2f}")
                if p.get('max_monthly_total'):
                    print(f"      Max Monthly: £{p['max_monthly_total']:.2f}")

        print("\nOptions:")
        print("  1. Add Policy")
        print("  2. Update Policy")
        print("  3. Toggle Active Status")
        print("  0. Return")

        choice = input("\nChoice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            name = input("Policy Name: ").strip()
            description = input("Description: ").strip()
            max_single = input("Max Single Expense (Enter for none): ").strip()
            max_monthly = input("Max Monthly Total (Enter for none): ").strip()
            roles = input("Applies to Roles (comma-separated, Enter for all): ").strip()

            try:
                policy_id = ExpenseManager.create_policy(
                    name=name,
                    description=description,
                    max_single_expense=float(max_single) if max_single else None,
                    max_monthly_total=float(max_monthly) if max_monthly else None,
                    applies_to_roles=roles if roles else None
                )
                print(f"Policy created. ID: {policy_id}")
            except Exception as e:
                print(f"Error: {e}")

        elif choice == '2':
            policy_id = input("Policy ID to update: ").strip()
            name = input("New Name (Enter to skip): ").strip()
            max_single = input("New Max Single (Enter to skip): ").strip()

            updates = {}
            if name:
                updates['name'] = name
            if max_single:
                updates['max_single_expense'] = float(max_single)

            if updates:
                ExpenseManager.update_policy(int(policy_id), **updates)
                print("Policy updated.")

        elif choice == '3':
            policy_id = input("Policy ID to toggle: ").strip()
            for p in policies:
                if p['policy_id'] == int(policy_id):
                    new_status = not p.get('is_active', True)
                    ExpenseManager.update_policy(int(policy_id), is_active=new_status)
                    print(f"Policy {'activated' if new_status else 'deactivated'}.")
                    break

    input("Press Enter to continue...")


def _process_reimbursements() -> None:
    """Process reimbursements for approved claims."""
    claims = ExpenseManager.get_claims_for_reimbursement()

    if not claims:
        print("\nNo claims pending reimbursement.")
        input("Press Enter to continue...")
        return

    print(f"\n--- {len(claims)} Claims Ready for Reimbursement ---")

    total = sum(c.get('amount', 0) for c in claims)
    print(f"Total Amount: £{total:.2f}")

    for c in claims:
        print(f"\n#{c.get('claim_id')} - {c.get('user_id')}: £{c.get('amount', 0):.2f}")

    print("\nOptions:")
    print("  1. Process All")
    print("  2. Process Individual")
    print("  0. Return")

    choice = input("\nChoice: ").strip()

    if choice == '1':
        payment_method = input("Payment Method (bank_transfer/check/cash): ").strip() or 'bank_transfer'
        confirm = input(f"Process £{total:.2f} to {len(claims)} claims? (yes/no): ").strip().lower()

        if confirm == 'yes':
            for c in claims:
                ref = f"REIMB-{datetime.now().strftime('%Y%m%d')}-{c['claim_id']}"
                ExpenseManager.create_reimbursement(
                    claim_id=c['claim_id'],
                    amount=c['amount'],
                    payment_method=payment_method,
                    reference_number=ref
                )
            print(f"\n{len(claims)} reimbursements processed.")

    elif choice == '2':
        claim_id = input("Claim ID to process: ").strip()
        for c in claims:
            if c['claim_id'] == int(claim_id):
                payment_method = input("Payment Method: ").strip() or 'bank_transfer'
                ref = input("Reference Number: ").strip()
                ExpenseManager.create_reimbursement(
                    claim_id=int(claim_id),
                    amount=c['amount'],
                    payment_method=payment_method,
                    reference_number=ref
                )
                print("Reimbursement processed.")
                break
        else:
            print("Claim not found in pending list.")

    input("\nPress Enter to continue...")


def _expense_reports() -> None:
    """Generate expense reports."""
    print("\n--- Expense Reports ---")
    print("  1. Summary by Category")
    print("  2. Summary by Department")
    print("  3. Monthly Trend")
    print("  4. User Expense Summary")
    print("  5. Policy Compliance Check")

    choice = input("\nChoice: ").strip()

    if choice == '1':
        stats = ExpenseManager.get_expense_statistics()
        print("\n--- Expenses by Category ---")
        for cat, data in stats.get('by_category', {}).items():
            print(f"  {cat}: £{data.get('total', 0):.2f} ({data.get('count', 0)} claims)")

    elif choice == '2':
        stats = ExpenseManager.get_expense_statistics()
        print("\n--- Expenses by Department ---")
        for dept, data in stats.get('by_department', {}).items():
            print(f"  {dept}: £{data.get('total', 0):.2f} ({data.get('count', 0)} claims)")

    elif choice == '3':
        stats = ExpenseManager.get_expense_statistics()
        print("\n--- Monthly Expense Trend ---")
        for month, amount in stats.get('monthly_trend', {}).items():
            print(f"  {month}: £{amount:.2f}")

    elif choice == '4':
        user_id = input("User ID: ").strip()
        summary = ExpenseManager.get_user_expense_summary(user_id)
        print(f"\n--- Expense Summary for {user_id} ---")
        print(f"Total Claims: {summary.get('total_claims', 0)}")
        print(f"Total Amount: £{summary.get('total_amount', 0):.2f}")
        print(f"Approved: £{summary.get('approved_amount', 0):.2f}")
        print(f"Pending: £{summary.get('pending_amount', 0):.2f}")
        print(f"Reimbursed: £{summary.get('reimbursed_amount', 0):.2f}")

    elif choice == '5':
        print("\nChecking policy compliance...")
        violations = ExpenseManager.check_policy_compliance()
        if violations:
            print(f"\n{len(violations)} potential violations found:")
            for v in violations:
                print(f"  - {v.get('user_id')}: {v.get('violation_type')} - {v.get('details')}")
        else:
            print("No policy violations detected.")

    input("\nPress Enter to continue...")
