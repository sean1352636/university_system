"""
Contract Menu - Contract management CLI.
"""

from datetime import datetime
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.contract_manager import ContractManager
from education_system.post_18.university_system.modules.domain.operations.staff_hr.cli.validators import (
    validate_date, validate_required, validate_choice, validate_number,
    validate_integer, validate_confirmation, validate_user_id,
    get_date_input, get_choice_input, get_required_input, get_currency_input,
    get_integer_input, get_confirmation, ValidationError
)


def display_contract_menu(user_id: str, is_admin: bool = False) -> None:
    """Display contract management menu."""
    while True:
        print("\n" + "=" * 60)
        print("CONTRACT MANAGEMENT")
        print("=" * 60)

        print("\n--- My Contract ---")
        print("  1. View My Contract")
        print("  2. View Contract History")
        print("  3. View Probation Status")

        if is_admin:
            print("\n--- Administration ---")
            print("  4. Search Contracts")
            print("  5. Create New Contract")
            print("  6. Manage Contract")
            print("  7. Expiring Contracts")
            print("  8. Probation Reviews Due")
            print("  9. Contract Statistics")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _view_my_contract(user_id)
        elif choice == '2':
            _view_contract_history(user_id)
        elif choice == '3':
            _view_probation_status(user_id)
        elif choice == '4' and is_admin:
            _search_contracts()
        elif choice == '5' and is_admin:
            _create_contract()
        elif choice == '6' and is_admin:
            _manage_contract()
        elif choice == '7' and is_admin:
            _expiring_contracts()
        elif choice == '8' and is_admin:
            _probation_reviews_due()
        elif choice == '9' and is_admin:
            _contract_statistics()
        else:
            print("Invalid choice.")


def _view_my_contract(user_id: str) -> None:
    """View current contract."""
    contract = ContractManager.get_active_contract(user_id)

    if not contract:
        print("\nNo active contract found.")
        input("Press Enter to continue...")
        return

    print("\n--- Current Contract ---")
    print(f"Contract ID: {contract.get('contract_id')}")
    print(f"Type: {contract.get('contract_type', 'N/A')}")
    print(f"Status: {contract.get('status', 'N/A')}")
    print(f"Start Date: {contract.get('start_date', 'N/A')}")
    print(f"End Date: {contract.get('end_date', 'N/A')}")
    print(f"Department: {contract.get('department', 'N/A')}")
    print(f"Job Title: {contract.get('job_title', 'N/A')}")
    print(f"Working Hours: {contract.get('working_hours_per_week', 'N/A')} hrs/week")
    print(f"Notice Period: {contract.get('notice_period_days', 'N/A')} days")

    if contract.get('probation_end_date'):
        print(f"Probation End: {contract['probation_end_date']}")

    input("\nPress Enter to continue...")


def _view_contract_history(user_id: str) -> None:
    """View contract history."""
    contracts = ContractManager.get_user_contracts(user_id, include_inactive=True)

    if not contracts:
        print("\nNo contracts found.")
        input("Press Enter to continue...")
        return

    print(f"\n--- Contract History ({len(contracts)} contracts) ---")
    for c in contracts:
        status_icon = "✓" if c.get('status') == 'active' else "○"
        print(f"\n{status_icon} Contract #{c.get('contract_id')}")
        print(f"  Type: {c.get('contract_type')} | Status: {c.get('status')}")
        print(f"  Period: {c.get('start_date')} to {c.get('end_date', 'Ongoing')}")
        print(f"  Role: {c.get('job_title', 'N/A')}")

    input("\nPress Enter to continue...")


def _view_probation_status(user_id: str) -> None:
    """View probation status and reviews."""
    contract = ContractManager.get_active_contract(user_id)

    if not contract:
        print("\nNo active contract found.")
        input("Press Enter to continue...")
        return

    if not contract.get('probation_end_date'):
        print("\nYou are not currently on probation.")
        input("Press Enter to continue...")
        return

    print("\n--- Probation Status ---")
    print(f"Probation End Date: {contract['probation_end_date']}")

    # Calculate days remaining
    end_date = datetime.fromisoformat(contract['probation_end_date'])
    days_remaining = (end_date - datetime.now()).days
    print(f"Days Remaining: {max(0, days_remaining)}")

    # Get probation reviews
    reviews = ContractManager.get_probation_reviews(user_id)
    if reviews:
        print("\n--- Review History ---")
        for r in reviews:
            print(f"\nReview Date: {r.get('review_date')}")
            print(f"  Type: {r.get('review_type')}")
            print(f"  Outcome: {r.get('outcome', 'Pending')}")
            if r.get('performance_rating'):
                print(f"  Rating: {r['performance_rating']}/5")

    input("\nPress Enter to continue...")


def _search_contracts() -> None:
    """Search contracts."""
    print("\n--- Search Contracts ---")
    print("Search by:")
    print("  1. Employee ID/Name")
    print("  2. Department")
    print("  3. Contract Type")
    print("  4. View All Active")

    search_choice = input("\nChoice: ").strip()

    if search_choice == '1':
        term = input("Search term: ").strip()
        contracts = ContractManager.search_contracts(search_term=term)
    elif search_choice == '2':
        dept = input("Department: ").strip()
        contracts = ContractManager.search_contracts(department=dept)
    elif search_choice == '3':
        print("Types: permanent, fixed-term, temporary, casual, contractor")
        ctype = input("Contract type: ").strip()
        contracts = ContractManager.search_contracts(contract_type=ctype)
    elif search_choice == '4':
        contracts = ContractManager.search_contracts()
    else:
        print("Invalid choice.")
        return

    if not contracts:
        print("\nNo contracts found.")
    else:
        print(f"\n--- Found {len(contracts)} contracts ---")
        for c in contracts:
            print(f"\n#{c.get('contract_id')} - {c.get('user_id')}")
            print(f"  {c.get('job_title')} | {c.get('department')}")
            print(f"  Type: {c.get('contract_type')} | Status: {c.get('status')}")
            print(f"  Period: {c.get('start_date')} to {c.get('end_date', 'Ongoing')}")

    input("\nPress Enter to continue...")


def _create_contract() -> None:
    """Create a new contract."""
    print("\n--- Create New Contract ---")

    try:
        user_id = get_required_input("Employee User ID: ", "Employee User ID")
    except ValidationError as e:
        print(f"Error: {e}")
        return

    contract_types = ['permanent', 'fixed-term', 'temporary', 'casual', 'contractor']
    print(f"\nContract Types: {', '.join(contract_types)}")

    try:
        contract_type = get_choice_input(
            "Contract Type: ", contract_types, "Contract Type", allow_empty=True
        ) or 'permanent'
        start_date = get_date_input("Start Date (YYYY-MM-DD): ", "Start Date")
        end_date = get_date_input(
            "End Date (YYYY-MM-DD, Enter for none): ", "End Date", allow_empty=True
        )
        department = get_required_input("Department: ", "Department")
        job_title = get_required_input("Job Title: ", "Job Title")
        salary = get_currency_input("Salary (Enter for none): ", "Salary", allow_empty=True)
        probation_months = get_integer_input(
            "Probation Period (months, Enter for none): ",
            "Probation Period", allow_empty=True, min_value=1, max_value=24
        )
    except ValidationError as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")
        return

    probation_end = None
    if probation_months:
        from datetime import timedelta
        start = datetime.fromisoformat(start_date)
        probation_end = (start + timedelta(days=int(probation_months) * 30)).isoformat()[:10]

    try:
        contract_id = ContractManager.create_contract(
            user_id,
            contract_type=contract_type,
            start_date=start_date,
            end_date=end_date,
            department=department,
            job_title=job_title,
            salary=salary,
            probation_end_date=probation_end
        )
        print(f"\nContract created successfully. ID: {contract_id}")
    except Exception as e:
        print(f"\nError creating contract: {e}")

    input("Press Enter to continue...")


def _manage_contract() -> None:
    """Manage an existing contract."""
    try:
        contract_id = get_integer_input("\nEnter Contract ID: ", "Contract ID", min_value=1)
    except ValidationError as e:
        print(f"Error: {e}")
        return

    contract = ContractManager.get_contract(contract_id)
    if not contract:
        print("Contract not found.")
        input("Press Enter to continue...")
        return

    print(f"\n--- Contract #{contract_id} ---")
    print(f"Employee: {contract.get('user_id')}")
    print(f"Status: {contract.get('status')}")
    print(f"Type: {contract.get('contract_type')}")

    print("\nActions:")
    print("  1. Update Contract")
    print("  2. Add Amendment")
    print("  3. Record Probation Review")
    print("  4. Extend Probation")
    print("  5. Complete Probation")
    print("  6. Terminate Contract")
    print("  0. Cancel")

    action = input("\nChoice: ").strip()

    if action == '1':
        _update_contract(int(contract_id))
    elif action == '2':
        _add_amendment(int(contract_id))
    elif action == '3':
        _record_probation_review(contract)
    elif action == '4':
        _extend_probation(int(contract_id))
    elif action == '5':
        _complete_probation(int(contract_id))
    elif action == '6':
        _terminate_contract(int(contract_id))


def _update_contract(contract_id: int) -> None:
    """Update contract fields."""
    print("\nEnter new values (press Enter to skip):")
    job_title = input("Job Title: ").strip()
    department = input("Department: ").strip()

    try:
        salary = get_currency_input("Salary: ", "Salary", allow_empty=True)
    except ValidationError as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")
        return

    updates = {}
    if job_title:
        updates['job_title'] = job_title
    if department:
        updates['department'] = department
    if salary is not None:
        updates['salary'] = salary

    if updates:
        ContractManager.update_contract(contract_id, **updates)
        print("Contract updated.")
    else:
        print("No changes made.")

    input("Press Enter to continue...")


def _add_amendment(contract_id: int) -> None:
    """Add a contract amendment."""
    print("\n--- Add Amendment ---")
    change_types = ['salary', 'hours', 'role', 'terms', 'other']

    try:
        change_type = get_choice_input(
            f"Change Type ({', '.join(change_types)}): ",
            change_types, "Change Type"
        )
        field_changed = get_required_input("Field Changed: ", "Field Changed")
        old_value = get_required_input("Old Value: ", "Old Value")
        new_value = get_required_input("New Value: ", "New Value")
        effective_date = get_date_input("Effective Date (YYYY-MM-DD): ", "Effective Date")
        reason = get_required_input("Reason: ", "Reason")
    except ValidationError as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")
        return

    try:
        amendment_id = ContractManager.create_amendment(
            contract_id,
            change_type=change_type,
            field_changed=field_changed,
            old_value=old_value,
            new_value=new_value,
            effective_date=effective_date,
            reason=reason
        )
        print(f"\nAmendment added. ID: {amendment_id}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _record_probation_review(contract: dict) -> None:
    """Record a probation review."""
    print("\n--- Record Probation Review ---")
    review_types = ['mid-probation', 'final', 'extended']
    outcomes = ['pass', 'fail', 'extend']

    try:
        review_date = get_date_input("Review Date (YYYY-MM-DD): ", "Review Date")
        reviewer_id = get_required_input("Reviewer ID: ", "Reviewer ID")
        review_type = get_choice_input(
            f"Review Type ({', '.join(review_types)}): ",
            review_types, "Review Type", allow_empty=True
        ) or 'mid-probation'
        performance_rating = get_integer_input(
            "Performance Rating (1-5): ", "Performance Rating",
            allow_empty=True, min_value=1, max_value=5
        )
        outcome = get_choice_input(
            f"Outcome ({', '.join(outcomes)}): ",
            outcomes, "Outcome"
        )
        comments = input("Comments: ").strip()
    except ValidationError as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")
        return

    try:
        review_id = ContractManager.create_probation_review(
            contract['user_id'],
            contract_id=contract['contract_id'],
            review_date=review_date,
            reviewer_id=reviewer_id,
            review_type=review_type,
            performance_rating=performance_rating,
            outcome=outcome,
            comments=comments
        )
        print(f"\nReview recorded. ID: {review_id}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _extend_probation(contract_id: int) -> None:
    """Extend probation period."""
    try:
        new_end_date = get_date_input("\nNew Probation End Date (YYYY-MM-DD): ", "New End Date")
        reason = get_required_input("Reason for Extension: ", "Reason")
        extended_by = get_required_input("Extended By (User ID): ", "Extended By")
    except ValidationError as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")
        return

    ContractManager.extend_probation(contract_id, new_end_date, reason, extended_by)
    print("Probation extended.")

    input("Press Enter to continue...")


def _complete_probation(contract_id: int) -> None:
    """Complete probation."""
    try:
        outcome = get_choice_input("\nOutcome (pass/fail): ", ['pass', 'fail'], "Outcome")
        completed_by = get_required_input("Completed By (User ID): ", "Completed By")
    except ValidationError as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")
        return

    ContractManager.complete_probation(contract_id, outcome, completed_by)
    print("Probation completed.")

    input("Press Enter to continue...")


def _terminate_contract(contract_id: int) -> None:
    """Terminate a contract."""
    if not get_confirmation("\nAre you sure you want to terminate this contract?"):
        print("Cancelled.")
        return

    try:
        termination_date = get_date_input("Termination Date (YYYY-MM-DD): ", "Termination Date")
        reason = get_required_input("Reason: ", "Reason")
        terminated_by = get_required_input("Terminated By (User ID): ", "Terminated By")
    except ValidationError as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")
        return

    ContractManager.terminate_contract(contract_id, termination_date, reason, terminated_by)
    print("Contract terminated.")

    input("Press Enter to continue...")


def _expiring_contracts() -> None:
    """View expiring contracts."""
    print("\n--- Expiring Contracts ---")
    try:
        days = get_integer_input(
            "Days ahead to check (default 90): ", "Days",
            allow_empty=True, min_value=1, max_value=365
        ) or 90
    except ValidationError as e:
        print(f"Error: {e}")
        input("Press Enter to continue...")
        return

    contracts = ContractManager.get_expiring_contracts(days)

    if not contracts:
        print(f"\nNo contracts expiring in the next {days} days.")
    else:
        print(f"\n{len(contracts)} contracts expiring:")
        for c in contracts:
            print(f"\n#{c.get('contract_id')} - {c.get('user_id')}")
            print(f"  {c.get('job_title')} | {c.get('department')}")
            print(f"  Expires: {c.get('end_date')}")

    input("\nPress Enter to continue...")


def _probation_reviews_due() -> None:
    """View pending probation reviews."""
    reviews = ContractManager.get_pending_probation_reviews()

    if not reviews:
        print("\nNo probation reviews due.")
    else:
        print(f"\n--- {len(reviews)} Probation Reviews Due ---")
        for r in reviews:
            print(f"\n{r.get('user_id')}")
            print(f"  {r.get('job_title')} | {r.get('department')}")
            print(f"  Probation Ends: {r.get('probation_end_date')}")

    input("\nPress Enter to continue...")


def _contract_statistics() -> None:
    """View contract statistics."""
    stats = ContractManager.get_contract_statistics()

    print("\n--- Contract Statistics ---")
    print(f"Total Active Contracts: {stats.get('total_active', 0)}")
    print(f"Expiring in 30 Days: {stats.get('expiring_30_days', 0)}")
    print(f"In Probation: {stats.get('in_probation', 0)}")

    print("\nBy Contract Type:")
    for ctype, count in stats.get('by_type', {}).items():
        print(f"  {ctype}: {count}")

    input("\nPress Enter to continue...")
