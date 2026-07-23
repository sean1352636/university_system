"""
Payroll Menu - Payslips, overtime, allowances and payroll runs CLI.

Wired to PayrollManager (the same manager the payroll GUI uses).
"""

from datetime import datetime

from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.payroll_manager import (
    PayrollManager,
)


def display_payroll_menu(user_id: str, is_admin: bool = False) -> None:
    """Display the payroll management menu."""
    while True:
        print("\n" + "=" * 60)
        print("PAYROLL MANAGEMENT")
        print("=" * 60)

        print("\n  1. View My Payslips")
        print("  2. View My Overtime")
        print("  3. Log Overtime")

        if is_admin:
            print("\n--- Administration ---")
            print("  4. Pending Overtime Approvals")
            print("  5. Add Allowance")
            print("  6. View Pay Periods")
            print("  7. Create Pay Period")
            print("  8. Run Payroll")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _view_payslips(user_id)
        elif choice == '2':
            _view_overtime(user_id)
        elif choice == '3':
            _log_overtime(user_id)
        elif choice == '4' and is_admin:
            _overtime_approvals(user_id)
        elif choice == '5' and is_admin:
            _add_allowance(user_id)
        elif choice == '6' and is_admin:
            _view_periods()
        elif choice == '7' and is_admin:
            _create_period(user_id)
        elif choice == '8' and is_admin:
            _run_payroll(user_id)
        else:
            print("Invalid choice.")


def _view_payslips(user_id: str) -> None:
    """List the user's payroll history."""
    records = PayrollManager.get_user_payroll_history(user_id)
    print("\n" + "-" * 60)
    print("MY PAYSLIPS")
    print("-" * 60)

    if records:
        for r in records:
            print(f"\n  {r.get('period_name', 'N/A')}  ({r.get('period_start', '')} to {r.get('period_end', '')})")
            print(f"    Gross: {r.get('gross_pay', 0):.2f}  |  Tax: {r.get('tax', 0):.2f}  |  Net: {r.get('net_pay', 0):.2f}")
    else:
        print("\n  No payslips found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _view_overtime(user_id: str) -> None:
    """List the user's overtime entries."""
    entries = PayrollManager.get_user_overtime(user_id)
    print("\n" + "-" * 60)
    print("MY OVERTIME")
    print("-" * 60)

    if entries:
        for e in entries:
            print(f"\n  #{e.get('overtime_id')}  {e.get('date', '')}")
            print(f"    Hours: {e.get('hours', 0):.1f}  |  Rate: {e.get('rate_multiplier', 1.0):.1f}x  |  "
                  f"Status: {e.get('status', '').title()}")
    else:
        print("\n  No overtime entries.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _log_overtime(user_id: str) -> None:
    """Log an overtime entry."""
    print("\n--- Log Overtime ---")
    date = input(f"Date (YYYY-MM-DD) [{datetime.now().strftime('%Y-%m-%d')}]: ").strip() \
        or datetime.now().strftime('%Y-%m-%d')

    try:
        hours = float(input("Hours: ").strip())
        if hours <= 0:
            raise ValueError("Hours must be greater than 0")
        rate = input("Rate multiplier (1.0/1.5/2.0) [1.5]: ").strip() or '1.5'
        rate_multiplier = float(rate)
        reason = input("Reason (optional): ").strip() or None

        overtime_id = PayrollManager.log_overtime(
            user_id, date=date, hours=hours,
            rate_multiplier=rate_multiplier, reason=reason,
        )
        print(f"\nOvertime logged. ID: {overtime_id}")
    except ValueError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _overtime_approvals(approver_id: str) -> None:
    """Approve or reject pending overtime."""
    pending = PayrollManager.get_pending_overtime()
    print("\n" + "-" * 60)
    print("PENDING OVERTIME APPROVALS")
    print("-" * 60)

    if not pending:
        print("\n  No pending overtime.")
        input("\nPress Enter to continue...")
        return

    for i, e in enumerate(pending, 1):
        print(f"  {i}. #{e.get('overtime_id')}  User: {e.get('user_id')}  "
              f"{e.get('date', '')}  {e.get('hours', 0):.1f}h @ {e.get('rate_multiplier', 1.0):.1f}x")

    try:
        idx = int(input("\nSelect entry (0 to abort): ").strip())
        if idx == 0:
            return
        if 1 <= idx <= len(pending):
            entry = pending[idx - 1]
            action = input("Approve or Reject? (a/r): ").strip().lower()
            if action == 'a':
                PayrollManager.approve_overtime(entry['overtime_id'], approver_id)
                print("\nOvertime approved.")
            elif action == 'r':
                PayrollManager.reject_overtime(entry['overtime_id'], approver_id)
                print("\nOvertime rejected.")
            else:
                print("\nNo action taken.")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _add_allowance(approver_id: str) -> None:
    """Add a payroll allowance for a user."""
    print("\n--- Add Allowance ---")
    target_user = input("User ID: ").strip()
    allowance_type = input("Type (Housing/Transport/Meal/Phone/Other) [Housing]: ").strip() or 'Housing'

    if not target_user:
        print("\nUser ID is required.")
        input("Press Enter to continue...")
        return

    try:
        amount = float(input("Amount: ").strip())
        frequency = input("Frequency (monthly/bi-weekly/weekly/annual) [monthly]: ").strip() or 'monthly'

        allowance_id = PayrollManager.add_allowance(
            user_id=target_user, allowance_type=allowance_type,
            amount=amount, frequency=frequency, approved_by=approver_id,
        )
        print(f"\nAllowance added. ID: {allowance_id}")
    except ValueError:
        print("\nInvalid amount.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _view_periods() -> None:
    """List pay periods."""
    periods = PayrollManager.get_periods()
    print("\n" + "-" * 60)
    print("PAY PERIODS")
    print("-" * 60)

    if periods:
        for p in periods:
            print(f"\n  #{p.get('period_id')}  {p.get('name', '')}  ({p.get('period_type', '')})")
            print(f"    {p.get('start_date', '')} to {p.get('end_date', '')}  |  "
                  f"Status: {p.get('status', '').title()}")
    else:
        print("\n  No pay periods.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _create_period(user_id: str) -> None:
    """Create a new pay period."""
    print("\n--- Create Pay Period ---")
    name = input("Name: ").strip()
    if not name:
        print("\nName is required.")
        input("Press Enter to continue...")
        return

    period_type = input("Type (monthly/bi-weekly/weekly) [monthly]: ").strip() or 'monthly'
    start_date = input("Start date (YYYY-MM-DD): ").strip()
    end_date = input("End date (YYYY-MM-DD): ").strip()
    payment_date = input("Payment date (YYYY-MM-DD, optional): ").strip() or None

    try:
        period_id = PayrollManager.create_period(
            name=name, period_type=period_type,
            start_date=start_date, end_date=end_date,
            payment_date=payment_date, created_by=user_id,
        )
        print(f"\nPay period created. ID: {period_id}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _run_payroll(user_id: str) -> None:
    """Run payroll for a selected period."""
    periods = PayrollManager.get_periods()
    open_periods = [p for p in periods if p.get('status', '').lower() != 'completed']

    if not open_periods:
        print("\nNo periods available to process.")
        input("Press Enter to continue...")
        return

    print("\nAvailable periods:")
    for i, p in enumerate(open_periods, 1):
        print(f"  {i}. #{p.get('period_id')}  {p.get('name', '')} [{p.get('status', '').title()}]")

    try:
        idx = int(input("\nSelect period (0 to abort): ").strip())
        if idx == 0:
            return
        if 1 <= idx <= len(open_periods):
            period = open_periods[idx - 1]
            confirm = input(f"Run payroll for '{period.get('name')}'? (y/n): ").strip().lower()
            if confirm != 'y':
                return
            result = PayrollManager.run_payroll(period['period_id'], created_by=user_id)
            if result.get('error'):
                print(f"\nError: {result['error']}")
            else:
                print(f"\nPayroll complete: {result.get('total_records', 0)} records | "
                      f"Gross: {result.get('total_gross', 0):.2f} | Net: {result.get('total_net', 0):.2f}")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")
