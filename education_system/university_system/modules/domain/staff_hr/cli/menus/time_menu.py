"""
Time Menu - Time and attendance CLI.
"""

from datetime import datetime, timedelta
from education_system.university_system.modules.domain.staff_comms.staff_hr.services import TimeManager


def display_time_menu(user_id: str, is_approver: bool = False,
                      approval_mode: bool = False) -> None:
    """Display time and attendance menu."""
    while True:
        print("\n" + "=" * 60)
        print("TIME & ATTENDANCE")
        print("=" * 60)

        # Show current status
        status = TimeManager.get_current_status(user_id)
        if status:
            print(f"\nCurrently clocked in since {status.get('clock_in')}")
        else:
            print("\nNot currently clocked in")

        print("\n  1. Clock In")
        print("  2. Clock Out")
        print("  3. View Today's Entries")
        print("  4. View Time History")
        print("  5. Add Manual Entry")
        print("  6. View Timesheets")
        print("  7. Submit Timesheet")

        if is_approver or approval_mode:
            print("\n--- Approvals ---")
            print("  8. View Pending Timesheets")
            print("  9. Approve/Reject Timesheet")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _clock_in(user_id)
        elif choice == '2':
            _clock_out(user_id)
        elif choice == '3':
            _view_today(user_id)
        elif choice == '4':
            _view_history(user_id)
        elif choice == '5':
            _add_manual_entry(user_id)
        elif choice == '6':
            _view_timesheets(user_id)
        elif choice == '7':
            _submit_timesheet(user_id)
        elif choice == '8' and (is_approver or approval_mode):
            _view_pending_timesheets(user_id)
        elif choice == '9' and (is_approver or approval_mode):
            _handle_timesheet_approval(user_id)
        else:
            print("Invalid choice.")


def _clock_in(user_id: str) -> None:
    """Clock in."""
    location = input("Location (office/remote/other): ").strip() or 'office'
    work_type = input("Work type (regular/overtime): ").strip() or 'regular'

    try:
        entry_id = TimeManager.clock_in(user_id, location, work_type)
        print(f"\nClocked in successfully at {datetime.now().strftime('%H:%M:%S')}")
    except ValueError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _clock_out(user_id: str) -> None:
    """Clock out."""
    try:
        TimeManager.clock_out(user_id)
        print(f"\nClocked out successfully at {datetime.now().strftime('%H:%M:%S')}")
    except ValueError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _view_today(user_id: str) -> None:
    """View today's time entries."""
    today = datetime.now().strftime('%Y-%m-%d')
    entries = TimeManager.get_entries(user_id, today, today)

    print("\n" + "-" * 50)
    print(f"TIME ENTRIES - {today}")
    print("-" * 50)
    if entries:
        total_hours = 0
        for e in entries:
            clock_out = e.get('clock_out', 'Active')
            print(f"  {e.get('clock_in')} - {clock_out}")
            print(f"    Type: {e.get('work_type')} | Location: {e.get('location')}")
            if e.get('clock_out'):
                # Calculate hours
                try:
                    cin = datetime.strptime(e['clock_in'], '%H:%M:%S')
                    cout = datetime.strptime(e['clock_out'], '%H:%M:%S')
                    hours = (cout - cin).seconds / 3600
                    total_hours += hours
                except (ValueError, TypeError):
                    pass
        print(f"\nTotal hours: {total_hours:.2f}")
    else:
        print("No entries today.")
    print("-" * 50)
    input("\nPress Enter to continue...")


def _view_history(user_id: str) -> None:
    """View time entry history."""
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
    entries = TimeManager.get_entries(user_id, start_date, end_date)

    print("\n" + "-" * 60)
    print(f"TIME HISTORY - Last 14 Days")
    print("-" * 60)
    if entries:
        current_date = None
        for e in entries:
            if e.get('entry_date') != current_date:
                current_date = e.get('entry_date')
                print(f"\n{current_date}:")
            clock_out = e.get('clock_out', 'Active')
            print(f"  {e.get('clock_in')} - {clock_out} ({e.get('work_type')})")
    else:
        print("No entries found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _add_manual_entry(user_id: str) -> None:
    """Add a manual time entry."""
    print("\n--- Add Manual Entry ---")
    entry_date = input("Date (YYYY-MM-DD): ").strip()
    clock_in = input("Clock In (HH:MM): ").strip()
    clock_out = input("Clock Out (HH:MM): ").strip()
    work_type = input("Work Type (regular/overtime): ").strip() or 'regular'
    notes = input("Notes: ").strip()

    try:
        # Validate
        datetime.strptime(entry_date, '%Y-%m-%d')
        datetime.strptime(clock_in, '%H:%M')
        datetime.strptime(clock_out, '%H:%M')

        TimeManager.add_manual_entry(
            user_id, entry_date, clock_in + ':00', clock_out + ':00',
            work_type=work_type, notes=notes
        )
        print("\nManual entry added successfully.")
    except ValueError:
        print("\nInvalid date/time format.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _view_timesheets(user_id: str) -> None:
    """View user's timesheets."""
    timesheets = TimeManager.get_timesheets(user_id)
    print("\n" + "-" * 60)
    print("MY TIMESHEETS")
    print("-" * 60)
    if timesheets:
        for t in timesheets:
            status = t.get('status', 'draft').upper()
            print(f"\n  Week: {t.get('week_start')} to {t.get('week_end')}")
            print(f"  Hours: {t.get('total_hours', 0):.1f} (Regular: {t.get('regular_hours', 0):.1f}, OT: {t.get('overtime_hours', 0):.1f})")
            print(f"  Status: {status}")
    else:
        print("No timesheets found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _submit_timesheet(user_id: str) -> None:
    """Submit a timesheet."""
    timesheets = TimeManager.get_timesheets(user_id, status='draft')
    if not timesheets:
        print("\nNo draft timesheets to submit.")
        input("Press Enter to continue...")
        return

    print("\nDraft Timesheets:")
    for i, t in enumerate(timesheets, 1):
        print(f"  {i}. {t.get('week_start')} - {t.get('total_hours', 0):.1f} hours")

    try:
        choice = int(input("\nSelect timesheet to submit (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(timesheets):
            timesheet = timesheets[choice - 1]
            TimeManager.submit_timesheet(timesheet['timesheet_id'])
            print("\nTimesheet submitted successfully.")
    except ValueError:
        print("Invalid input.")

    input("Press Enter to continue...")


def _view_pending_timesheets(approver_id: str) -> None:
    """View pending timesheet approvals."""
    pending = TimeManager.get_pending_approvals(approver_id)
    print("\n" + "-" * 60)
    print("PENDING TIMESHEET APPROVALS")
    print("-" * 60)
    if pending:
        for i, t in enumerate(pending, 1):
            name = f"{t.get('first_name', '')} {t.get('last_name', '')}"
            print(f"\n  {i}. {name.strip() or t.get('user_id')}")
            print(f"     Week: {t.get('week_start')} | Hours: {t.get('total_hours', 0):.1f}")
    else:
        print("No pending approvals.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _handle_timesheet_approval(approver_id: str) -> None:
    """Handle timesheet approval."""
    pending = TimeManager.get_pending_approvals(approver_id)
    if not pending:
        print("\nNo pending approvals.")
        input("Press Enter to continue...")
        return

    print("\nPending Timesheets:")
    for i, t in enumerate(pending, 1):
        name = f"{t.get('first_name', '')} {t.get('last_name', '')}"
        print(f"  {i}. {name.strip()}: {t.get('week_start')} ({t.get('total_hours', 0):.1f} hrs)")

    try:
        choice = int(input("\nSelect timesheet (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(pending):
            timesheet = pending[choice - 1]
            action = input("(A)pprove or (R)eject? ").strip().upper()
            if action == 'A':
                TimeManager.approve_timesheet(timesheet['timesheet_id'], approver_id)
                print("\nTimesheet approved.")
            elif action == 'R':
                print("\nTimesheet rejected.")
            else:
                print("Invalid action.")
    except ValueError:
        print("Invalid input.")

    input("Press Enter to continue...")
