"""
Cover Menu - Substitute / cover teaching CLI.

Wired to CoverManager (cover requests, teaching qualifications,
volunteer offers, and cover assignments).
"""

from education_system.systems.university.domain.staff.staff_hr.services.managers import (
    CoverManager,
)


def display_cover_menu(user_id: str, is_manager: bool = False) -> None:
    """Display the cover / substitute teaching menu."""
    while True:
        print("\n" + "=" * 60)
        print("COVER / SUBSTITUTE TEACHING")
        print("=" * 60)

        print("\n  1. My Cover Requests")
        print("  2. Open Cover Requests")
        print("  3. Create Cover Request")
        print("  4. Cancel Request")
        print("  5. Volunteer for Cover")
        print("  6. My Teaching Qualifications")
        print("  7. Add Teaching Qualification")

        if is_manager:
            print("\n--- Manager ---")
            print("  8. View Offers for Request")
            print("  9. Assign Cover")
            print("  10. Complete Assignment")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _list_my_requests(user_id)
        elif choice == '2':
            _list_open_requests()
        elif choice == '3':
            _create_request(user_id)
        elif choice == '4':
            _cancel_request()
        elif choice == '5':
            _volunteer(user_id)
        elif choice == '6':
            _list_qualifications(user_id)
        elif choice == '7':
            _add_qualification(user_id)
        elif choice == '8' and is_manager:
            _list_offers()
        elif choice == '9' and is_manager:
            _assign_cover(user_id)
        elif choice == '10' and is_manager:
            _complete_assignment()
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


def _print_requests(requests: list, title: str) -> None:
    """Print a list of cover requests."""
    print("\n" + "-" * 60)
    print(title)
    print("-" * 60)
    if requests:
        for r in requests:
            print(f"  {r.get('request_id')}. {r.get('cover_date')} "
                  f"{r.get('start_time')}-{r.get('end_time')} "
                  f"[{r.get('status')}] ({r.get('urgency')})")
            course = r.get('course_name') or r.get('course_code')
            if course:
                print(f"      Course: {course}")
    else:
        print("  No requests found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _list_my_requests(user_id: str) -> None:
    """List a user's own cover requests."""
    _print_requests(CoverManager.get_user_requests(user_id),
                    "MY COVER REQUESTS")


def _list_open_requests() -> None:
    """List open cover requests."""
    department = input("Filter by department (blank for all): ").strip() or None
    _print_requests(CoverManager.get_open_requests(department=department),
                    "OPEN COVER REQUESTS")


def _create_request(user_id: str) -> None:
    """Create a cover request."""
    print("\n--- Create Cover Request ---")
    cover_date = input("Cover Date (YYYY-MM-DD): ").strip()
    start_time = input("Start Time (HH:MM): ").strip()
    end_time = input("End Time (HH:MM): ").strip()
    if not cover_date or not start_time or not end_time:
        print("Date and times are required.")
        input("Press Enter to continue...")
        return
    request_type = input("Request Type [teaching]: ").strip() or 'teaching'
    course_code = input("Course Code (optional): ").strip() or None
    course_name = input("Course Name (optional): ").strip() or None
    location = input("Location (optional): ").strip() or None
    reason = input("Reason (optional): ").strip() or None
    urgency = input("Urgency [normal]: ").strip() or 'normal'
    department = input("Department (optional): ").strip() or None
    try:
        request_id = CoverManager.create_request(
            user_id, cover_date, start_time, end_time,
            request_type=request_type, course_code=course_code,
            course_name=course_name, location=location, reason=reason,
            urgency=urgency, department=department)
        print(f"\nCover request created. ID: {request_id}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _cancel_request() -> None:
    """Cancel a cover request."""
    request_id = _prompt_int("Request ID to cancel: ")
    if request_id is None:
        return
    try:
        CoverManager.cancel_request(request_id)
        print("\nRequest cancelled.")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _volunteer(user_id: str) -> None:
    """Volunteer for a cover request."""
    request_id = _prompt_int("Request ID to volunteer for: ")
    if request_id is None:
        return
    message = input("Message (optional): ").strip() or None
    try:
        offer_id = CoverManager.volunteer(request_id, user_id, message=message)
        print(f"\nOffer submitted. ID: {offer_id}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _list_qualifications(user_id: str) -> None:
    """List a user's teaching qualifications."""
    quals = CoverManager.get_qualifications(user_id)
    print("\n" + "-" * 60)
    print("MY TEACHING QUALIFICATIONS")
    print("-" * 60)
    if quals:
        for q in quals:
            print(f"  {q.get('qualification_id')}. {q.get('subject_area')} "
                  f"[{q.get('qualification_level')}]")
            if q.get('course_code'):
                print(f"      Course: {q.get('course_code')}")
    else:
        print("  No qualifications found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _add_qualification(user_id: str) -> None:
    """Add a teaching qualification."""
    print("\n--- Add Teaching Qualification ---")
    subject_area = input("Subject Area: ").strip()
    if not subject_area:
        print("Subject area is required.")
        input("Press Enter to continue...")
        return
    course_code = input("Course Code (optional): ").strip() or None
    level = input("Qualification Level [qualified]: ").strip() or 'qualified'
    try:
        qualification_id = CoverManager.add_qualification(
            user_id, subject_area, course_code=course_code,
            qualification_level=level)
        print(f"\nQualification added. ID: {qualification_id}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _list_offers() -> None:
    """List volunteer offers for a cover request."""
    request_id = _prompt_int("Request ID: ")
    if request_id is None:
        return
    offers = CoverManager.get_offers(request_id)
    print("\n" + "-" * 60)
    print(f"OFFERS - Request #{request_id}")
    print("-" * 60)
    if offers:
        for o in offers:
            print(f"  Offer {o.get('offer_id')}: {o.get('volunteer_id')}")
            if o.get('message'):
                print(f"      {o.get('message')}")
    else:
        print("  No offers found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _assign_cover(user_id: str) -> None:
    """Assign cover to a staff member."""
    print("\n--- Assign Cover ---")
    request_id = _prompt_int("Request ID: ")
    if request_id is None:
        return
    assignee_id = input("Assignee User ID: ").strip()
    if not assignee_id:
        print("Assignee is required.")
        input("Press Enter to continue...")
        return
    try:
        assignment_id = CoverManager.assign_cover(
            request_id, assignee_id, user_id)
        print(f"\nCover assigned. Assignment ID: {assignment_id}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _complete_assignment() -> None:
    """Complete a cover assignment."""
    print("\n--- Complete Assignment ---")
    assignment_id = _prompt_int("Assignment ID: ")
    if assignment_id is None:
        return
    feedback = input("Feedback (optional): ").strip() or None
    rating_raw = input("Rating 1-5 (optional): ").strip()
    rating = None
    if rating_raw:
        try:
            rating = int(rating_raw)
        except ValueError:
            print("Invalid rating; skipping.")
    try:
        CoverManager.complete_assignment(
            assignment_id, feedback=feedback, rating=rating)
        print("\nAssignment completed.")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")
