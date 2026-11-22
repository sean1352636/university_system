"""
Leave Menu - Leave management CLI.

Leave, sickness absence, family leave, flexible working and (HR) leave
entitlements. Everything goes through ``LeaveManager`` and the
``domain/staff_hr`` leave modules, which check who may do what; pass
``auth`` (the signed-in session) so they check that person — without it the
role is read from ``users`` for ``user_id``.
"""

from datetime import datetime
from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr import leave_rules
from education_system.systems.university.domains.staff.domain.staff_hr.services import LeaveManager
from education_system.systems.university.domains.staff.interfaces.cli.staff_hr.menus import (
    leave_more_menus as more,
)


def display_leave_menu(user_id: str, is_approver: bool = False,
                       approval_mode: bool = False, auth=None) -> None:
    """Display leave management menu."""
    actor = access.user_of(auth) if auth is not None else leave_rules.actor_for(user_id)
    user_id = access.username_of(actor) or user_id
    is_approver = is_approver or access.can(actor, 'manager')
    is_hr = access.can(actor, 'hr')
    while True:
        print("\n" + "=" * 60)
        print("LEAVE MANAGEMENT")
        print("=" * 60)

        # Show current balance summary
        balances = LeaveManager.get_balance(user_id)
        if balances:
            print("\nMy Leave Balance:")
            for b in balances[:3]:  # Show top 3
                remaining = b.get('remaining_days', 0)
                print(f"  {b.get('leave_type_name')}: {remaining:.1f} days remaining")

        print("\n  1. View Full Leave Balance")
        print("  2. Submit Leave Request")
        print("  3. View My Requests")
        print("  4. Cancel Pending Request")
        print("  5. Team Leave Calendar")

        if is_approver or approval_mode:
            print("\n--- Approvals ---")
            print("  6. View Pending Approvals")
            print("  7. Approve/Reject Request")

        print("\n--- Absence & Family ---")
        print("  8. Sickness Absence")
        print("  9. Family Leave")
        print(" 10. Flexible Working")
        if is_hr:
            print(" 11. Leave Entitlements (HR)")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _view_balance(user_id)
        elif choice == '2':
            _submit_request(user_id, actor)
        elif choice == '3':
            _view_requests(user_id)
        elif choice == '4':
            _cancel_request(user_id, actor)
        elif choice == '5':
            _view_calendar(actor)
        elif choice == '6' and (is_approver or approval_mode):
            _view_pending_approvals(user_id, actor)
        elif choice == '7' and (is_approver or approval_mode):
            _handle_approval(user_id, actor)
        elif choice == '8':
            more.absence_menu(actor)
        elif choice == '9':
            more.family_menu(actor)
        elif choice == '10':
            more.flexible_menu(actor)
        elif choice == '11' and is_hr:
            more.entitlements_menu(actor)
        else:
            print("Invalid choice.")


def _view_balance(user_id: str) -> None:
    """View full leave balance."""
    balances = LeaveManager.get_balance(user_id)
    print("\n" + "-" * 50)
    print("LEAVE BALANCE - " + str(datetime.now().year))
    print("-" * 50)
    if balances:
        for b in balances:
            allocated = b.get('allocated_days', 0)
            used = b.get('used_days', 0)
            remaining = b.get('remaining_days', 0)
            print(f"\n{b.get('leave_type_name')}:")
            print(f"  Allocated: {allocated:.1f} | Used: {used:.1f} | Remaining: {remaining:.1f}")
            extras = []
            if b.get('bank_holiday_days'):
                extras.append(f"bank holidays booked {b['bank_holiday_days']:g}")
            if b.get('carried_over'):
                extras.append(f"carried over {b['carried_over']:g}"
                              + (f" (expires {b['carry_over_expires']})"
                                 if b.get('carry_over_expires') else ''))
            if b.get('pending_days'):
                extras.append(f"pending {b['pending_days']:g}")
            if extras:
                print("  " + "; ".join(extras))
    else:
        print("No leave balance found. Contact HR.")
    print("-" * 50)
    input("\nPress Enter to continue...")


def _submit_request(user_id: str, actor=None) -> None:
    """Submit a leave request."""
    print("\n--- Submit Leave Request ---")

    # Show leave types
    leave_types = LeaveManager.get_leave_types()
    print("\nAvailable Leave Types:")
    for i, lt in enumerate(leave_types, 1):
        print(f"  {i}. {lt.get('name')} (max {lt.get('max_days_per_year', 'N/A')} days/year)")

    try:
        type_choice = int(input("\nSelect leave type: ").strip()) - 1
        if type_choice < 0 or type_choice >= len(leave_types):
            print("Invalid selection.")
            input("Press Enter to continue...")
            return
        leave_type = leave_types[type_choice]
    except ValueError:
        print("Invalid input.")
        input("Press Enter to continue...")
        return

    start_date = input("Start Date (YYYY-MM-DD): ").strip()
    end_date = input("End Date (YYYY-MM-DD): ").strip()
    half = input("Half days? (s)tart, (e)nd, (b)oth or Enter for none: ").strip().lower()
    reason = input("Reason: ").strip()

    try:
        # Validate dates
        datetime.strptime(start_date, '%Y-%m-%d')
        datetime.strptime(end_date, '%Y-%m-%d')

        # Check for conflicts
        days = LeaveManager.count_days(user_id, start_date, end_date,
                                       half in ('s', 'b'), half in ('e', 'b'))
        print(f"\nThat is {days:g} working days.")
        request_id = LeaveManager.submit_request(
            user_id, leave_type['leave_type_id'],
            start_date, end_date, reason=reason, actor=actor,
            start_half=half in ('s', 'b'), end_half=half in ('e', 'b'),
        )
        print(f"\nLeave request submitted successfully. Request ID: {request_id}")

    except (ValueError, PermissionError) as e:
        print(f"\nNot submitted: {e}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _view_requests(user_id: str) -> None:
    """View user's leave requests."""
    requests = LeaveManager.get_requests(user_id, limit=20)
    print("\n" + "-" * 60)
    print("MY LEAVE REQUESTS")
    print("-" * 60)
    if requests:
        for r in requests:
            status_icon = {'pending': '⏳', 'approved': '✓', 'rejected': '✗', 'cancelled': '○'}
            icon = status_icon.get(r.get('status', ''), '?')
            print(f"\n[{icon}] {r.get('leave_type_name')}")
            print(f"    {r.get('start_date')} to {r.get('end_date')} ({r.get('total_days')} days)")
            print(f"    Status: {r.get('status').upper()}")
            if r.get('rejection_reason'):
                print(f"    Reason: {r.get('rejection_reason')}")
    else:
        print("No leave requests found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _cancel_request(user_id: str, actor=None) -> None:
    """Cancel a pending request, or approved leave that has not started."""
    today = datetime.now().strftime('%Y-%m-%d')
    requests = [r for r in LeaveManager.get_requests(user_id, limit=200)
                if (r.get('source') or 'leave') == 'leave' and
                (r['status'] == 'pending' or (r['status'] == 'approved' and r['start_date'] > today))]
    if not requests:
        print("\nNo pending requests to cancel.")
        input("Press Enter to continue...")
        return

    print("\nPending Requests:")
    for i, r in enumerate(requests, 1):
        print(f"  {i}. {r.get('leave_type_name')}: {r.get('start_date')} to {r.get('end_date')}"
              f" ({r.get('status')})")

    try:
        choice = int(input("\nSelect request to cancel (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(requests):
            request = requests[choice - 1]
            if LeaveManager.cancel_request(request['request_id'], user_id, actor=actor):
                print("\nRequest cancelled successfully.")
            else:
                print("\nFailed to cancel request.")
    except ValueError:
        print("Invalid input.")

    input("Press Enter to continue...")


def _view_calendar(actor=None) -> None:
    """View team leave calendar."""
    month = datetime.now().month
    year = datetime.now().year
    calendar = LeaveManager.get_calendar(month=month, year=year, actor=actor)

    print("\n" + "-" * 60)
    print(f"LEAVE CALENDAR - {datetime(year, month, 1).strftime('%B %Y')}")
    print("-" * 60)
    if calendar:
        for entry in calendar:
            name = f"{entry.get('first_name', '')} {entry.get('last_name', '')}"
            print(f"  {name.strip() or 'Unknown'}")
            print(f"    {entry.get('start_date')} to {entry.get('end_date')}")
            print(f"    Type: {entry.get('leave_type_name')}")
    else:
        print("No approved leave this month.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _view_pending_approvals(approver_id: str, actor=None) -> None:
    """View pending leave approvals."""
    pending = LeaveManager.get_pending_approvals(approver_id, actor=actor)
    print("\n" + "-" * 60)
    print("PENDING LEAVE APPROVALS")
    print("-" * 60)
    if pending:
        for i, r in enumerate(pending, 1):
            name = f"{r.get('first_name', '')} {r.get('last_name', '')}"
            print(f"\n  {i}. {name.strip() or r.get('user_id')}")
            print(f"     {r.get('leave_type_name')}: {r.get('start_date')} to {r.get('end_date')}")
            print(f"     Days: {r.get('total_days')} | Dept: {r.get('department', 'N/A')}")
            if r.get('reason'):
                print(f"     Reason: {r.get('reason')[:50]}...")
    else:
        print("No pending approvals.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _handle_approval(approver_id: str, actor=None) -> None:
    """Handle leave approval/rejection."""
    pending = LeaveManager.get_pending_approvals(approver_id, actor=actor)
    if not pending:
        print("\nNo pending approvals.")
        input("Press Enter to continue...")
        return

    print("\nPending Requests:")
    for i, r in enumerate(pending, 1):
        name = f"{r.get('first_name', '')} {r.get('last_name', '')}"
        print(f"  {i}. {name.strip()}: {r.get('leave_type_name')} ({r.get('total_days')} days)")

    try:
        choice = int(input("\nSelect request (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(pending):
            request = pending[choice - 1]
            action = input("(A)pprove or (R)eject? ").strip().upper()
            if action == 'A':
                LeaveManager.approve_request(request['request_id'], approver_id, actor=actor)
                print("\nRequest approved.")
            elif action == 'R':
                reason = input("Rejection reason: ").strip()
                LeaveManager.reject_request(request['request_id'], approver_id, reason,
                                            actor=actor)
                print("\nRequest rejected.")
            else:
                print("Invalid action.")
    except PermissionError as e:
        print(f"\nNot allowed: {e}")
    except ValueError as e:
        print(f"Invalid: {e}")

    input("Press Enter to continue...")
