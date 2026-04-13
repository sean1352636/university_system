"""
Gym/Fitness Center CLI Interface

Command-line interface for gym management including memberships,
class bookings, personal training, equipment, and reporting.
"""

from datetime import datetime

from education_system.university_system.modules.domain.gym.services.gym_core import (
    init_gym_db,
    MembershipManager,
    ClassManager,
    PTSessionManager,
    EquipmentManager,
    TransactionManager,
    ReportManager,
    MEMBERSHIP_TYPES,
    CLASS_TYPES,
    EQUIPMENT_CATEGORIES,
    PT_SESSION_FEES,
)


def display_menu():
    """Display the gym management menu and handle user input."""
    init_gym_db()

    while True:
        print("\n" + "=" * 70)
        print(" " * 18 + "GYM / FITNESS CENTER MANAGEMENT")
        print("=" * 70)

        print("\n[Memberships]")
        print("1.  Create Membership")
        print("2.  View Membership")
        print("3.  List All Memberships")
        print("4.  Renew Membership")
        print("5.  Cancel Membership")

        print("\n[Attendance]")
        print("6.  Member Check-In")
        print("7.  Member Check-Out")

        print("\n[Classes]")
        print("8.  List Fitness Classes")
        print("9.  Book a Class")
        print("10. Cancel Class Booking")
        print("11. View Member Bookings")

        print("\n[Personal Training]")
        print("12. Book PT Session")
        print("13. View Member PT Sessions")
        print("14. Cancel PT Session")

        print("\n[Equipment]")
        print("15. List Gym Equipment")
        print("16. Report Equipment Issue")

        print("\n[Payments]")
        print("17. Record Payment")
        print("18. View User Transactions")

        print("\n[Reports]")
        print("19. Daily Attendance Report")
        print("20. Membership Statistics")
        print("21. Monthly Summary")

        print("\n0.  Back to Main Menu")
        print("=" * 70)

        choice = input("\nEnter your choice: ").strip()

        try:
            if choice == "0":
                break
            elif choice == "1":
                _create_membership()
            elif choice == "2":
                _view_membership()
            elif choice == "3":
                _list_memberships()
            elif choice == "4":
                _renew_membership()
            elif choice == "5":
                _cancel_membership()
            elif choice == "6":
                _check_in()
            elif choice == "7":
                _check_out()
            elif choice == "8":
                _list_classes()
            elif choice == "9":
                _book_class()
            elif choice == "10":
                _cancel_booking()
            elif choice == "11":
                _view_member_bookings()
            elif choice == "12":
                _book_pt_session()
            elif choice == "13":
                _view_pt_sessions()
            elif choice == "14":
                _cancel_pt_session()
            elif choice == "15":
                _list_equipment()
            elif choice == "16":
                _report_equipment_issue()
            elif choice == "17":
                _record_payment()
            elif choice == "18":
                _view_transactions()
            elif choice == "19":
                _daily_attendance()
            elif choice == "20":
                _membership_stats()
            elif choice == "21":
                _monthly_summary()
            else:
                print("Invalid choice. Please try again.")
        except Exception as e:
            print(f"\nError: {e}")


def _create_membership():
    """Create a new gym membership."""
    print("\n--- Create Membership ---")
    user_id = input("User ID: ").strip()
    user_name = input("Full name: ").strip()
    user_email = input("Email: ").strip()

    print("Membership types:")
    for key, info in MEMBERSHIP_TYPES.items():
        print(f"  {key}: {info['name']} - ${info['monthly_fee']:.2f}/month ({', '.join(info['features'])})")
    membership_type = input("Membership type: ").strip()

    months_str = input("Number of months (default 1): ").strip()
    months = int(months_str) if months_str else 1

    emergency_contact = input("Emergency contact name (optional): ").strip() or None
    emergency_phone = input("Emergency contact phone (optional): ").strip() or None
    health_conditions = input("Health conditions (optional): ").strip() or None

    result = MembershipManager.create_membership(
        user_id, user_name, user_email, membership_type, months,
        emergency_contact=emergency_contact,
        emergency_phone=emergency_phone,
        health_conditions=health_conditions,
    )
    if result:
        print(f"\nMembership created successfully!")
        print(f"  Member Number: {result['member_number']}")
        print(f"  Total Fee:     ${result['total_fee']:.2f}")
        print(f"  Start Date:    {result['start_date']}")
        print(f"  End Date:      {result['end_date']}")
    else:
        print("Failed to create membership. Check membership type is valid.")


def _view_membership():
    """View membership details."""
    print("\n--- View Membership ---")
    print("Search by: 1) Membership ID  2) Member Number  3) User ID")
    search_by = input("Choice: ").strip()

    membership = None
    if search_by == "1":
        mid = int(input("Membership ID: ").strip())
        membership = MembershipManager.get_membership(membership_id=mid)
    elif search_by == "2":
        mnum = input("Member number: ").strip()
        membership = MembershipManager.get_membership(member_number=mnum)
    elif search_by == "3":
        uid = input("User ID: ").strip()
        membership = MembershipManager.get_membership(user_id=uid)
    else:
        print("Invalid choice.")
        return

    if not membership:
        print("Membership not found.")
        return

    print(f"\n  Membership ID:  {membership['membership_id']}")
    print(f"  Member Number:  {membership['member_number']}")
    print(f"  Name:           {membership['user_name']}")
    print(f"  Email:          {membership.get('user_email', 'N/A')}")
    print(f"  Type:           {membership['membership_type']}")
    print(f"  Monthly Fee:    ${membership['monthly_fee']:.2f}")
    print(f"  Start Date:     {membership['start_date']}")
    print(f"  End Date:       {membership.get('end_date', 'N/A')}")
    print(f"  Status:         {membership['status']}")
    print(f"  Auto-Renew:     {'Yes' if membership.get('auto_renew') else 'No'}")


def _list_memberships():
    """List all memberships."""
    print("\n--- List Memberships ---")
    status = input("Filter by status (active/cancelled, Enter for all): ").strip() or None

    memberships = MembershipManager.get_all_memberships(status)
    if not memberships:
        print("No memberships found.")
        return

    print(f"\n{'ID':<6}{'Member #':<22}{'Name':<20}{'Type':<12}{'Status':<12}{'End Date':<12}")
    print("-" * 84)
    for m in memberships:
        print(
            f"{m['membership_id']:<6}{m['member_number']:<22}{m['user_name']:<20}"
            f"{m['membership_type']:<12}{m['status']:<12}{m.get('end_date', 'N/A'):<12}"
        )


def _renew_membership():
    """Renew a membership."""
    print("\n--- Renew Membership ---")
    membership_id = int(input("Membership ID: ").strip())
    months_str = input("Months to renew (default 1): ").strip()
    months = int(months_str) if months_str else 1

    result = MembershipManager.renew_membership(membership_id, months)
    if result:
        print(f"Membership renewed successfully!")
        print(f"  New End Date: {result['new_end_date']}")
        print(f"  Total Fee:    ${result['total_fee']:.2f}")
    else:
        print("Failed to renew membership.")


def _cancel_membership():
    """Cancel a membership."""
    print("\n--- Cancel Membership ---")
    membership_id = int(input("Membership ID: ").strip())
    confirm = input("Are you sure? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    if MembershipManager.cancel_membership(membership_id):
        print("Membership cancelled successfully.")
    else:
        print("Failed to cancel membership.")


def _check_in():
    """Record member check-in."""
    print("\n--- Member Check-In ---")
    membership_id = int(input("Membership ID: ").strip())
    attendance_id = MembershipManager.check_in(membership_id)
    if attendance_id:
        print(f"Checked in successfully. Attendance ID: {attendance_id}")
    else:
        print("Failed to check in.")


def _check_out():
    """Record member check-out."""
    print("\n--- Member Check-Out ---")
    attendance_id = int(input("Attendance ID: ").strip())
    if MembershipManager.check_out(attendance_id):
        print("Checked out successfully.")
    else:
        print("Failed to check out.")


def _list_classes():
    """List fitness classes."""
    print("\n--- Fitness Classes ---")
    print(f"Types: {', '.join(CLASS_TYPES)}")
    class_type = input("Filter by type (Enter for all): ").strip() or None
    day = input("Filter by day (e.g. Monday, Enter for all): ").strip() or None

    classes = ClassManager.get_all_classes(class_type, day)
    if not classes:
        print("No classes found.")
        return

    print(f"\n{'ID':<5}{'Name':<22}{'Type':<12}{'Day':<12}{'Time':<14}{'Location':<15}{'Spots':<8}")
    print("-" * 88)
    for c in classes:
        spots = c['max_capacity'] - c['current_enrolled']
        print(
            f"{c['class_id']:<5}{c['class_name']:<22}{c['class_type']:<12}"
            f"{c['schedule_day']:<12}{c['start_time']}-{c['end_time']:<8}"
            f"{c['location']:<15}{spots:<8}"
        )


def _book_class():
    """Book a fitness class."""
    print("\n--- Book a Class ---")
    class_id = int(input("Class ID: ").strip())
    member_id = int(input("Membership ID: ").strip())
    booking_date = input("Booking date (YYYY-MM-DD): ").strip()

    result = ClassManager.book_class(class_id, member_id, booking_date)
    if result:
        print(f"Class booked successfully!")
        print(f"  Booking ID:  {result['booking_id']}")
        print(f"  Booking Ref: {result['booking_ref']}")
    else:
        print("Failed to book class. Class may be full or not found.")


def _cancel_booking():
    """Cancel a class booking."""
    print("\n--- Cancel Class Booking ---")
    booking_id = int(input("Booking ID: ").strip())
    if ClassManager.cancel_booking(booking_id):
        print("Booking cancelled successfully.")
    else:
        print("Failed to cancel booking.")


def _view_member_bookings():
    """View member's class bookings."""
    print("\n--- Member Class Bookings ---")
    member_id = int(input("Membership ID: ").strip())

    bookings = ClassManager.get_member_bookings(member_id)
    if not bookings:
        print("No bookings found.")
        return

    for b in bookings:
        print(
            f"  [{b['booking_id']}] {b.get('class_name', 'N/A')} | "
            f"Date: {b['booking_date']} | "
            f"Time: {b.get('start_time', 'N/A')} | "
            f"Location: {b.get('location', 'N/A')} | "
            f"Ref: {b['booking_ref']}"
        )


def _book_pt_session():
    """Book a personal training session."""
    print("\n--- Book PT Session ---")
    member_id = int(input("Membership ID: ").strip())
    trainer_name = input("Trainer name: ").strip()
    session_date = input("Session date (YYYY-MM-DD): ").strip()
    session_time = input("Session time (HH:MM): ").strip()

    print("Session types and fees:")
    for stype, fee in PT_SESSION_FEES.items():
        print(f"  {stype}: ${fee:.2f}")
    session_type = input("Session type (default 'single'): ").strip() or "single"

    duration_str = input("Duration in minutes (default 60): ").strip()
    duration = int(duration_str) if duration_str else 60

    result = PTSessionManager.book_session(
        member_id, trainer_name, session_date, session_time,
        session_type, duration,
    )
    if result:
        print(f"PT session booked successfully!")
        print(f"  Session ID:  {result['session_id']}")
        print(f"  Booking Ref: {result['booking_ref']}")
        print(f"  Fee:         ${result['fee']:.2f}")
    else:
        print("Failed to book PT session.")


def _view_pt_sessions():
    """View member's PT sessions."""
    print("\n--- Member PT Sessions ---")
    member_id = int(input("Membership ID: ").strip())

    sessions = PTSessionManager.get_member_sessions(member_id)
    if not sessions:
        print("No PT sessions found.")
        return

    for s in sessions:
        print(
            f"  [{s['session_id']}] Trainer: {s['trainer_name']} | "
            f"Date: {s['session_date']} {s['session_time']} | "
            f"Duration: {s['duration_minutes']}min | "
            f"Fee: ${s['fee']:.2f} | "
            f"Status: {s['status']}"
        )


def _cancel_pt_session():
    """Cancel a PT session."""
    print("\n--- Cancel PT Session ---")
    session_id = int(input("Session ID: ").strip())
    if PTSessionManager.cancel_session(session_id):
        print("PT session cancelled successfully.")
    else:
        print("Failed to cancel PT session.")


def _list_equipment():
    """List gym equipment."""
    print("\n--- Gym Equipment ---")
    print(f"Categories: {', '.join(EQUIPMENT_CATEGORIES)}")
    category = input("Filter by category (Enter for all): ").strip() or None
    status = input("Filter by status (available/maintenance, Enter for all): ").strip() or None

    equipment = EquipmentManager.get_all_equipment(category, status)
    if not equipment:
        print("No equipment found.")
        return

    print(f"\n{'ID':<6}{'Name':<25}{'Category':<15}{'Brand':<15}{'Status':<14}{'Location':<12}")
    print("-" * 87)
    for e in equipment:
        print(
            f"{e['equipment_id']:<6}{e['equipment_name']:<25}{e['category']:<15}"
            f"{e.get('brand', 'N/A'):<15}{e['status']:<14}{e.get('location', 'N/A'):<12}"
        )


def _report_equipment_issue():
    """Report an equipment issue."""
    print("\n--- Report Equipment Issue ---")
    equipment_id = int(input("Equipment ID: ").strip())
    issue = input("Describe the issue: ").strip()

    if EquipmentManager.report_issue(equipment_id, issue):
        print("Issue reported successfully. Equipment marked for maintenance.")
    else:
        print("Failed to report issue.")


def _record_payment():
    """Record a gym payment."""
    print("\n--- Record Payment ---")
    user_id = input("User ID: ").strip()
    print("Transaction types: membership, class_booking, pt_session, other")
    transaction_type = input("Transaction type: ").strip()
    amount = float(input("Amount: ").strip())
    payment_method = input("Payment method (card/cash/transfer): ").strip()
    member_id_str = input("Membership ID (optional): ").strip()
    member_id = int(member_id_str) if member_id_str else None

    result = TransactionManager.record_payment(
        user_id, transaction_type, amount, payment_method, member_id,
    )
    if result:
        print(f"Payment recorded successfully!")
        print(f"  Transaction ID: {result['transaction_id']}")
        print(f"  Reference:      {result['reference']}")
        print(f"  Amount:         ${result['amount']:.2f}")
    else:
        print("Failed to record payment.")


def _view_transactions():
    """View user transactions."""
    print("\n--- User Transactions ---")
    user_id = input("User ID: ").strip()

    transactions = TransactionManager.get_user_transactions(user_id)
    if not transactions:
        print("No transactions found.")
        return

    for t in transactions:
        print(
            f"  [{t.get('transaction_id')}] Type: {t.get('transaction_type', 'N/A')} | "
            f"Amount: ${t.get('amount', 0):.2f} | "
            f"Method: {t.get('payment_method', 'N/A')} | "
            f"Date: {t.get('created_at', 'N/A')}"
        )


def _daily_attendance():
    """Display daily attendance report."""
    print("\n--- Daily Attendance Report ---")
    date = input("Date (YYYY-MM-DD, Enter for today): ").strip() or None

    report = ReportManager.get_daily_attendance(date)
    if not report:
        print("No data available.")
        return

    print(f"  Date:       {report.get('date', 'N/A')}")
    print(f"  Check-ins:  {report.get('check_ins', 0)}")
    print(f"  Revenue:    ${report.get('revenue', 0):.2f}")


def _membership_stats():
    """Display membership statistics."""
    print("\n--- Membership Statistics ---")
    stats = ReportManager.get_membership_stats()
    if not stats:
        print("No data available.")
        return

    print(f"  Total Active Members: {stats.get('total_active', 0)}")
    print("\n  By Type:")
    for mtype, info in stats.get('by_type', {}).items():
        print(f"    {mtype}: {info['count']} members, ${info['revenue']:.2f}/month")


def _monthly_summary():
    """Display monthly summary."""
    print("\n--- Monthly Summary ---")
    year_str = input("Year (Enter for current): ").strip()
    month_str = input("Month (1-12, Enter for current): ").strip()

    year = int(year_str) if year_str else None
    month = int(month_str) if month_str else None

    report = ReportManager.get_monthly_summary(year, month)
    if not report:
        print("No data available.")
        return

    print(f"  Period:          {report.get('year', '')}-{report.get('month', ''):02d}")
    print(f"  Total Revenue:   ${report.get('total_revenue', 0):.2f}")
    print(f"  New Members:     {report.get('new_members', 0)}")
    print(f"  Class Bookings:  {report.get('class_bookings', 0)}")


if __name__ == "__main__":
    display_menu()
