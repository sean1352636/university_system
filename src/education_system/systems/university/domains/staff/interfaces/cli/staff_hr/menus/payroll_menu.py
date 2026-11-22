"""
Payroll Menu - Payslips, overtime, allowances and payroll runs CLI.

Wired to PayrollManager (the same manager the payroll GUI uses), plus the
pay structure and pensions. Administration is payroll's
(``access.can(actor, 'payroll')``); overtime approvals are line managers'
and payroll's. Every call passes the signed-in person as ``actor``.
"""

from datetime import datetime

from education_system.systems.university.domains.staff.domain.staff_hr import (
    access,
    pay_structure,
    pensions,
)
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.payroll_manager import (
    PayrollManager,
)


def _actor_for(user_id, is_admin: bool, auth=None):
    """The signed-in session (``auth``), else one built from the caller's
    user id (username or users.id) and its admin flag."""
    if auth is not None and access.user_of(auth):
        return auth
    username = access.staff_key(user_id) or str(user_id)
    return {'username': username, 'role': 'admin' if is_admin else 'staff'}


def _pause() -> None:
    input("\nPress Enter to continue...")


def display_payroll_menu(user_id: str, is_admin: bool = False, auth=None) -> None:
    """Display the payroll management menu."""
    actor = _actor_for(user_id, is_admin, auth)
    user_id = access.username_of(actor)
    is_payroll = access.can(actor, 'payroll')
    can_approve = is_payroll or access.can(actor, 'manager')
    while True:
        print("\n" + "=" * 60)
        print("PAYROLL MANAGEMENT")
        print("=" * 60)

        print("\n  1. View My Payslips")
        print("  2. View My Overtime")
        print("  3. Log Overtime")
        print("  9. My Pension")

        if can_approve:
            print("\n--- Approvals ---")
            print("  4. Pending Overtime Approvals")
        if is_payroll:
            print("\n--- Administration ---")
            print("  5. Add Allowance")
            print("  6. View Pay Periods")
            print("  7. Create Pay Period")
            print("  8. Run Payroll")
            print(" 10. Pay Structure (spine, grades, increments, pay award)")
            print(" 11. Pension Schemes & Members")
            print(" 12. Mark Pay Period Paid")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _view_payslips(user_id, actor)
        elif choice == '2':
            _view_overtime(user_id, actor)
        elif choice == '3':
            _log_overtime(user_id, actor)
        elif choice == '9':
            _my_pension(actor)
        elif choice == '4' and can_approve:
            _overtime_approvals(user_id, actor)
        elif choice == '5' and is_payroll:
            _add_allowance(user_id, actor)
        elif choice == '6' and is_payroll:
            _view_periods()
        elif choice == '7' and is_payroll:
            _create_period(user_id, actor)
        elif choice == '8' and is_payroll:
            _run_payroll(user_id, actor)
        elif choice == '10' and is_payroll:
            _pay_structure_menu(actor)
        elif choice == '11' and is_payroll:
            _pensions_admin_menu(actor)
        elif choice == '12' and is_payroll:
            _mark_paid(actor)
        else:
            print("Invalid choice.")


def _view_payslips(user_id: str, actor=None) -> None:
    """List the user's payroll history."""
    records = PayrollManager.get_user_payroll_history(user_id, actor=actor)
    print("\n" + "-" * 60)
    print("MY PAYSLIPS")
    print("-" * 60)

    if records:
        for r in records:
            print(f"\n  {r.get('period_name', 'N/A')}  ({r.get('period_start', '')} to {r.get('period_end', '')})")
            print(f"    Basic: {r.get('basic_salary') or 0:.2f}  |  Overtime: {r.get('overtime_pay') or 0:.2f}"
                  f"  |  Allowances: {r.get('allowances_total') or 0:.2f}")
            print(f"    Gross: {r.get('gross_pay') or 0:.2f}  |  Tax: {r.get('tax_deduction') or 0:.2f}"
                  f"  |  NI: {r.get('ni_deduction') or 0:.2f}  |  Pension ({r.get('pension_scheme') or '-'}): "
                  f"{r.get('pension_deduction') or 0:.2f}  |  Net: {r.get('net_pay') or 0:.2f}")
            if r.get('unpaid_leave_days'):
                print(f"    Unpaid leave: {r['unpaid_leave_days']} day(s)")
    else:
        print("\n  No payslips found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _view_overtime(user_id: str, actor=None) -> None:
    """List the user's overtime entries."""
    entries = PayrollManager.get_user_overtime(user_id, actor=actor)
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


def _log_overtime(user_id: str, actor=None) -> None:
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
            rate_multiplier=rate_multiplier, reason=reason, actor=actor,
        )
        print(f"\nOvertime logged. ID: {overtime_id}")
    except ValueError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _overtime_approvals(approver_id: str, actor=None) -> None:
    """Approve or reject pending overtime (your reports'; payroll: everyone's)."""
    pending = PayrollManager.get_pending_overtime(actor=actor)
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
                PayrollManager.approve_overtime(entry['overtime_id'], approver_id, actor=actor)
                print("\nOvertime approved.")
            elif action == 'r':
                PayrollManager.reject_overtime(entry['overtime_id'], approver_id, actor=actor)
                print("\nOvertime rejected.")
            else:
                print("\nNo action taken.")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _add_allowance(approver_id: str, actor=None) -> None:
    """Add a payroll allowance for a user."""
    print("\n--- Add Allowance ---")
    target_user = input("Username: ").strip()
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
            amount=amount, frequency=frequency, approved_by=approver_id, actor=actor,
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


def _create_period(user_id: str, actor=None) -> None:
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
            payment_date=payment_date, created_by=user_id, actor=actor,
        )
        print(f"\nPay period created. ID: {period_id}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _run_payroll(user_id: str, actor=None) -> None:
    """Run payroll for a selected period."""
    periods = PayrollManager.get_periods()
    open_periods = [p for p in periods
                    if (p.get('status') or '').lower() not in ('completed', 'paid', 'closed')]

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
            result = PayrollManager.run_payroll(period['period_id'], created_by=user_id, actor=actor)
            if result.get('error'):
                print(f"\nError: {result['error']}")
            else:
                print(f"\nPayroll complete: {result.get('total_records', 0)} records | "
                      f"Gross: {result.get('total_gross', 0):.2f} | Net: {result.get('total_net', 0):.2f} | "
                      f"Employer pension: {result.get('total_employer_pension', 0):.2f} | "
                      f"Payslip notices: {result.get('notices_sent', 0)}")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _mark_paid(actor) -> None:
    """Mark a completed pay period paid."""
    done = [p for p in PayrollManager.get_periods() if (p.get('status') or '').lower() == 'completed']
    if not done:
        print("\nNo completed periods.")
        _pause()
        return
    for i, p in enumerate(done, 1):
        print(f"  {i}. #{p['period_id']}  {p.get('name', '')}")
    try:
        idx = int(input("\nSelect period (0 to abort): ").strip())
        if 1 <= idx <= len(done):
            PayrollManager.update_period_status(done[idx - 1]['period_id'], 'paid', actor=actor)
            print("\nPeriod marked paid.")
    except (ValueError, PermissionError) as e:
        print(f"\nError: {e}")
    _pause()


def _ask(prompt: str, cast=str, default=None):
    raw = input(prompt).strip()
    if not raw:
        return default
    return cast(raw)


# ==================== PENSIONS ====================

def _my_pension(actor) -> None:
    """Your pension membership, with the option to opt out."""
    me = access.username_of(actor)
    rows = pensions.memberships(actor, me)
    print("\n--- My Pension ---")
    if not rows:
        print("  You are not in a pension scheme.")
    for m in rows:
        print(f"  {m['scheme_code']}  {m.get('scheme_name') or ''}  joined {m['joined_on']}"
              f"  {('left ' + m['opted_out_on']) if m.get('opted_out_on') else '(current)'}")
    if any(not m.get('opted_out_on') for m in rows) and \
            input("\nOpt out of your pension? (y/n): ").strip().lower() == 'y':
        when = input(f"From (YYYY-MM-DD) [{datetime.now().date().isoformat()}]: ").strip() or None
        try:
            pensions.opt_out(actor, me, when, 'opted out by member')
            print("You have opted out.")
        except (ValueError, PermissionError) as e:
            print(f"Error: {e}")
    _pause()


def _pensions_admin_menu(actor) -> None:
    """Payroll: scheme rates, tiers, enrolment and opt-outs."""
    while True:
        print("\n--- Pension Schemes & Members ---")
        print("  1. List Schemes")
        print("  2. Change Scheme Rates")
        print("  3. Set Scheme Tiers")
        print("  4. List Members")
        print("  5. Enrol a Member")
        print("  6. Opt a Member Out")
        print("  0. Back")
        choice = input("\nChoice: ").strip()
        if choice == '0':
            return
        try:
            if choice == '1':
                for s in pensions.list_schemes(True):
                    tiers = ', '.join(f"{t['lower_limit']:g}+ {t['employee_rate_pct']:g}%"
                                      for t in s['tiers']) if s['tiered'] else ''
                    print(f"  {s['scheme_code']:5} {s['name']}: employee "
                          f"{'tiered (' + tiers + ')' if s['tiered'] else str(s['employee_rate_pct']) + '%'}"
                          f", employer {s['employer_rate_pct']}% (basis {s['tier_basis']})")
            elif choice == '2':
                code = input("Scheme code: ").strip().upper()
                pensions.update_scheme(actor, code,
                                       employee_rate_pct=_ask("Employee % (Enter to keep): ", float),
                                       employer_rate_pct=_ask("Employer % (Enter to keep): ", float))
                print("Saved.")
            elif choice == '3':
                code = input("Scheme code: ").strip().upper()
                print("Enter tiers as lower-upper:rate separated by ';' (last upper blank)")
                tiers = []
                for part in filter(None, (p.strip() for p in input("Tiers: ").split(';'))):
                    band, rate = part.split(':')
                    low, high = band.split('-')
                    tiers.append((float(low), float(high) if high.strip() else None, float(rate)))
                pensions.set_tiers(actor, code, tiers)
                print("Saved.")
            elif choice == '4':
                for m in pensions.memberships(actor):
                    print(f"  #{m['membership_id']} {m['user_id']:15} {m['scheme_code']:5} "
                          f"{m['joined_on']} -> {m.get('opted_out_on') or 'current'}")
            elif choice == '5':
                pensions.enrol(actor, input("Username: ").strip(),
                               input("Scheme code: ").strip().upper(),
                               _ask("From (YYYY-MM-DD, Enter for today): "))
                print("Enrolled.")
            elif choice == '6':
                done = pensions.opt_out(actor, input("Username: ").strip(),
                                        _ask("From (YYYY-MM-DD, Enter for today): "),
                                        'opted out by payroll')
                print("Opted out." if done else "They are not in a scheme.")
        except (ValueError, PermissionError) as e:
            print(f"Error: {e}")
        _pause()


# ==================== PAY STRUCTURE ====================

def _pay_structure_menu(actor) -> None:
    """Payroll: spine, grades, jobs, contract pay, increments, pay award."""
    while True:
        print("\n--- Pay Structure ---")
        print("  1. View Pay Spine")
        print("  2. Set a Spine Value")
        print("  3. View Grades")
        print("  4. Add / Change a Grade")
        print("  5. Map a Job Title to a Grade")
        print("  6. Set a Contract's Pay Terms")
        print("  7. Preview Annual Increment")
        print("  8. Run Annual Increment")
        print("  9. Increment Settings")
        print(" 10. Apply a Pay Award")
        print("  0. Back")
        choice = input("\nChoice: ").strip()
        if choice == '0':
            return
        try:
            if choice == '1':
                year = _ask(f"Pay year [{pay_structure.current_pay_year()}]: ")
                for r in pay_structure.list_spine(year):
                    value = f"{r['annual_value']:,.0f}" if r['annual_value'] is not None else '-'
                    print(f"  Point {r['point']:3}  {value:>10}  {r['label']}")
            elif choice == '2':
                pay_structure.set_spine_value(
                    actor, int(input("Point: ")),
                    _ask(f"Pay year [{pay_structure.current_pay_year()}]: ",
                         default=pay_structure.current_pay_year()),
                    float(input("Annual value: ")), _ask("Label (optional): "))
                print("Saved.")
            elif choice == '3':
                for g in pay_structure.list_grades(include_inactive=True):
                    print(f"  {g['grade_code']:6} {g['name']}: points {g['min_point']}-{g['max_point']}"
                          f"{' (contribution to ' + str(g['contribution_max_point']) + ')' if g['contribution_max_point'] else ''}"
                          f"{'' if g['is_active'] else ' [inactive]'}")
            elif choice == '4':
                pay_structure.save_grade(actor, input("Code: ").strip(), input("Name: ").strip(),
                                         int(input("Bottom point: ")), int(input("Top point: ")),
                                         _ask("Top contribution point (optional): ", int))
                print("Saved.")
            elif choice == '5':
                pay_structure.map_job(actor, input("Job title: ").strip(),
                                      _ask("Grade code (Enter to remove): "))
                print("Saved.")
            elif choice == '6':
                cid = int(input("Contract ID: "))
                override = _ask("Override salary (Enter for none): ", float)
                result = pay_structure.assign(
                    actor, cid, grade_code=_ask("Grade (Enter to keep): "),
                    spine_point=_ask("Spine point (Enter to keep): ", int),
                    fte=_ask("FTE (Enter to keep): ", float),
                    pension_scheme=_ask("Pension scheme (Enter to keep): "),
                    salary_override=override,
                    override_reason=_ask("Override reason: ") if override is not None else None,
                    clear_override=input("Clear an existing override? (y/n): ").strip().lower() == 'y')
                print(f"Full-time salary {result['full_time']:,.2f} ({result['source']}), FTE {result['fte']}")
            elif choice in ('7', '8'):
                effective = _ask("Effective date (Enter for the latest increment date): ")
                if choice == '7':
                    for p in pay_structure.preview_increments(actor, effective):
                        print(f"  #{p['contract_id']} {p['user_id']:15} {p['from_point']} -> "
                              f"{p['to_point']}  {p['outcome']} ({p['reason']})")
                elif input("Apply the increment now? (y/n): ").strip().lower() == 'y':
                    r = pay_structure.run_increments(actor, effective)
                    print("Already run for that date." if r['already_run'] else
                          f"{r['moved']} moved, {r['held']} held (effective {r['effective_date']}).")
            elif choice == '9':
                settings = pay_structure.get_settings()
                mmdd = _ask(f"Increment date MM-DD [{settings.get('increment_date')}]: ")
                months = _ask(f"Qualifying months [{settings.get('increment_min_service_months')}]: ")
                if mmdd:
                    pay_structure.set_setting(actor, 'increment_date', mmdd)
                if months:
                    pay_structure.set_setting(actor, 'increment_min_service_months', months)
                print("Saved.")
            elif choice == '10':
                r = pay_structure.apply_pay_award(
                    actor, input("New pay year (e.g. 2026/27): ").strip(),
                    float(input("Uplift %: ")), _ask("From pay year (Enter for latest): "),
                    _ask("Minimum uplift £ (Enter for 0): ", float, 0), _ask("Notes: "))
                print(f"{r['points_updated']} points set; {r['contracts_resynced']} salaries updated.")
        except (ValueError, PermissionError) as e:
            print(f"Error: {e}")
        _pause()
