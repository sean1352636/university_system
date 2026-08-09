"""
Travel Menu - Travel and conference management CLI.

Wired to TravelManager (travel requests, conference registrations,
and the two-level approval workflow).
"""

from education_system.systems.university.domain.staff.staff_hr.services.managers import (
    TravelManager,
)


def display_travel_menu(user_id: str, is_manager: bool = False) -> None:
    """Display the travel and conference menu."""
    while True:
        print("\n" + "=" * 60)
        print("TRAVEL & CONFERENCES")
        print("=" * 60)

        print("\n  1. My Travel Requests")
        print("  2. Create Travel Request")
        print("  3. Submit Request for Approval")
        print("  4. Cancel Request")
        print("  5. My Conference Registrations")
        print("  6. Register for Conference")

        if is_manager:
            print("\n--- Manager ---")
            print("  7. Pending Approvals")
            print("  8. Approve Request")
            print("  9. Reject Request")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _list_requests(user_id)
        elif choice == '2':
            _create_request(user_id)
        elif choice == '3':
            _submit_request(user_id)
        elif choice == '4':
            _cancel_request()
        elif choice == '5':
            _list_conferences(user_id)
        elif choice == '6':
            _register_conference(user_id)
        elif choice == '7' and is_manager:
            _list_pending(user_id)
        elif choice == '8' and is_manager:
            _approve_request(user_id)
        elif choice == '9' and is_manager:
            _reject_request(user_id)
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


def _list_requests(user_id: str) -> None:
    """List a user's travel requests."""
    requests = TravelManager.get_user_requests(user_id)
    print("\n" + "-" * 60)
    print("MY TRAVEL REQUESTS")
    print("-" * 60)
    if requests:
        for r in requests:
            print(f"  {r.get('request_id')}. {r.get('purpose')} -> "
                  f"{r.get('destination')} [{r.get('status')}]")
            print(f"      {r.get('departure_date')} to {r.get('return_date')} "
                  f"| Budget: {r.get('estimated_budget', 0)}")
    else:
        print("  No travel requests found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _create_request(user_id: str) -> None:
    """Create a travel request (draft)."""
    print("\n--- Create Travel Request ---")
    purpose = input("Purpose: ").strip()
    destination = input("Destination: ").strip()
    if not purpose or not destination:
        print("Purpose and destination are required.")
        input("Press Enter to continue...")
        return
    departure_date = input("Departure Date (YYYY-MM-DD): ").strip()
    return_date = input("Return Date (YYYY-MM-DD): ").strip()
    estimated_budget = _prompt_float("Estimated Budget: ")
    funding_source = input("Funding Source [department]: ").strip() or 'department'
    justification = input("Justification (optional): ").strip() or None
    department = input("Department (optional): ").strip() or None
    try:
        request_id = TravelManager.create_request(
            user_id, purpose, destination, departure_date, return_date,
            estimated_budget=estimated_budget, funding_source=funding_source,
            justification=justification, department=department)
        print(f"\nTravel request created (draft). ID: {request_id}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _submit_request(user_id: str) -> None:
    """Submit a draft request for approval."""
    request_id = _prompt_int("Request ID to submit: ")
    if request_id is None:
        return
    try:
        TravelManager.submit_request(request_id, user_id)
        print("\nRequest submitted for approval.")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _cancel_request() -> None:
    """Cancel a travel request."""
    request_id = _prompt_int("Request ID to cancel: ")
    if request_id is None:
        return
    try:
        TravelManager.cancel_request(request_id)
        print("\nRequest cancelled.")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _list_conferences(user_id: str) -> None:
    """List a user's conference registrations."""
    conferences = TravelManager.get_user_conferences(user_id)
    print("\n" + "-" * 60)
    print("MY CONFERENCE REGISTRATIONS")
    print("-" * 60)
    if conferences:
        for c in conferences:
            presenting = ' (presenting)' if c.get('is_presenting') else ''
            print(f"  {c.get('registration_id')}. {c.get('conference_name')}"
                  f"{presenting}")
            print(f"      {c.get('start_date')} to {c.get('end_date')} "
                  f"| Fee: {c.get('registration_fee', 0)}")
    else:
        print("  No conference registrations found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _register_conference(user_id: str) -> None:
    """Register for a conference."""
    print("\n--- Register for Conference ---")
    name = input("Conference Name: ").strip()
    if not name:
        print("Conference name is required.")
        input("Press Enter to continue...")
        return
    start_date = input("Start Date (YYYY-MM-DD): ").strip()
    end_date = input("End Date (YYYY-MM-DD): ").strip()
    location = input("Location (optional): ").strip() or None
    fee = _prompt_float("Registration Fee: ")
    is_presenting = input("Are you presenting? (y/N): ").strip().lower() == 'y'
    presentation_title = None
    if is_presenting:
        presentation_title = input("Presentation Title: ").strip() or None
    try:
        registration_id = TravelManager.register_conference(
            user_id, name, start_date, end_date, location=location,
            registration_fee=fee, presentation_title=presentation_title,
            is_presenting=is_presenting)
        print(f"\nConference registered. ID: {registration_id}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _list_pending(user_id: str) -> None:
    """List pending travel approvals."""
    pending = TravelManager.get_pending_approvals()
    print("\n" + "-" * 60)
    print("PENDING TRAVEL APPROVALS")
    print("-" * 60)
    if pending:
        for p in pending:
            print(f"  Approval {p.get('approval_id')} "
                  f"(level: {p.get('approval_level')}) - "
                  f"Request {p.get('request_id')}: {p.get('purpose')} -> "
                  f"{p.get('destination')}")
    else:
        print("  No pending approvals.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _approve_request(user_id: str) -> None:
    """Approve a travel request at one level."""
    approval_id = _prompt_int("Approval ID to approve: ")
    if approval_id is None:
        return
    comments = input("Comments (optional): ").strip() or None
    try:
        TravelManager.approve_request(approval_id, user_id, comments=comments)
        print("\nApproval recorded.")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _reject_request(user_id: str) -> None:
    """Reject a travel request."""
    approval_id = _prompt_int("Approval ID to reject: ")
    if approval_id is None:
        return
    comments = input("Comments (optional): ").strip() or None
    try:
        TravelManager.reject_request(approval_id, user_id, comments=comments)
        print("\nRequest rejected.")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")
