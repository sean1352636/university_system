"""
Payroll Manager - Payroll processing and pay records management.

Provides functionality for:
- Pay period creation and management
- Payroll processing with tax/NI/pension calculations
- Payslip generation and history
- Overtime logging and approval
- Allowance management
- Tax bracket configuration

Who may do what (``access``): running payroll, periods, allowances, tax and
everyone's pay are payroll's; a payslip is its owner's and payroll's, never
the line manager's (``access.can_view_pay``); overtime is approved by the
person's line manager or payroll. Methods take ``actor`` (the signed-in auth
or user dict) and check it; ``actor=None`` is a trusted internal call (jobs,
event subscribers, tests).

A pay run pays each contract that overlaps the period: the full-time salary
(``pay_structure.derive_salary`` — the spine point's value for the pay year,
an override, or the stored salary) x FTE, pro-rated by calendar days for
starters and leavers, less approved unpaid leave (working days at 1/260 of
the annual salary), plus overtime and allowances. Pension comes from the
member's scheme (``pensions``) and is taken before tax (net pay
arrangement). When a period completes or is paid, each person is e-mailed
that their payslip is ready — with no amounts in it.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers import _people as people
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608

logger = logging.getLogger(__name__)

#: Pay periods per year by period type.
PERIODS_PER_YEAR = {'monthly': 12, 'bi-weekly': 26, 'fortnightly': 26, 'weekly': 52}
#: Statuses after which a period's records are final.
FINAL_STATUSES = ('completed', 'paid', 'closed')
#: Contract statuses that can still be paid for part of a period (leavers).
PAYABLE_CONTRACT_STATUSES = ('active', 'terminated', 'ended', 'expired', 'completed')
#: Hours in a month for the overtime hourly rate (monthly salary / 160).
OVERTIME_MONTHLY_HOURS = 160


def _ensure(conn) -> None:
    from education_system.systems.university.domains.staff.domain.staff_hr import pay_structure
    pay_structure.ensure(conn)


def _gate(actor: Any, message: str) -> Optional[str]:
    """``actor`` must hold payroll (None = trusted internal call)."""
    if actor is None:
        return None
    access.require(actor, 'payroll', message)
    return access.username_of(actor)


def _as_date(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _weekdays(first: date, last: date) -> int:
    if last < first:
        return 0
    weeks, extra = divmod((last - first).days + 1, 7)
    count = weeks * 5
    for i in range(extra):
        if (first + timedelta(days=weeks * 7 + i)).weekday() < 5:
            count += 1
    return count


def tax_year_for(on: Any) -> str:
    """UK tax year containing ``on`` ('2025/26' runs 6 Apr 2025 - 5 Apr 2026)."""
    when = _as_date(on) or date.today()
    start = when.year if when >= date(when.year, 4, 6) else when.year - 1
    return f"{start}/{(start + 1) % 100:02d}"


def _brackets(conn, tax_year: str) -> List[Dict[str, Any]]:
    """The year's brackets, else the latest earlier year's, else the latest."""
    for sql, params in (
            ("SELECT * FROM tax_brackets WHERE tax_year = ? ORDER BY lower_limit ASC", (tax_year,)),
            ("SELECT * FROM tax_brackets WHERE tax_year = (SELECT MAX(tax_year) FROM tax_brackets "
             "WHERE tax_year <= ?) ORDER BY lower_limit ASC", (tax_year,)),
            ("SELECT * FROM tax_brackets WHERE tax_year = (SELECT MAX(tax_year) FROM tax_brackets) "
             "ORDER BY lower_limit ASC", ())):
        rows = [dict(b) for b in conn.execute(sql, params).fetchall()]
        if rows:
            return rows
    return []


def _income_tax(brackets: List[Dict[str, Any]], taxable_annual: float) -> float:
    """Progressive tax over the brackets."""
    tax = 0.0
    for bracket in brackets:
        lower = bracket.get('lower_limit', 0) or 0
        upper = bracket.get('upper_limit') or float('inf')
        rate = bracket.get('rate', 0) or 0
        personal_allowance = bracket.get('personal_allowance', 0) or 0
        taxable_in_bracket = max(0, min(taxable_annual, upper) - max(lower, personal_allowance))
        if taxable_in_bracket > 0:
            tax += taxable_in_bracket * rate
    return tax


def _national_insurance(gross_annual: float) -> float:
    """8% on earnings between 12570-50270, 2% above 50270."""
    ni = 0.0
    if gross_annual > 12570:
        ni += max(0, min(gross_annual, 50270) - 12570) * 0.08
    if gross_annual > 50270:
        ni += (gross_annual - 50270) * 0.02
    return ni


def _unpaid_leave_days(conn, user_id: str, first: date, last: date) -> float:
    """Approved unpaid leave (``leave_types.is_paid = 0``), in working days,
    falling between ``first`` and ``last``."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(leave_requests)").fetchall()}
    if not cols:
        return 0.0
    days_col = "COALESCE(lr.working_days, lr.total_days)" if 'working_days' in cols else "lr.total_days"
    rows = conn.execute(
        f"SELECT lr.start_date, lr.end_date, {days_col} FROM leave_requests lr "  # nosec B608
        "JOIN leave_types lt ON lt.leave_type_id = lr.leave_type_id "
        "WHERE lr.user_id = ? AND lr.status = 'approved' AND lt.is_paid = 0 "
        "AND lr.start_date <= ? AND lr.end_date >= ?",
        (user_id, last.isoformat(), first.isoformat())).fetchall()
    total = 0.0
    for start, end, days in rows:
        l_start = _as_date(start)
        l_end = _as_date(end) or l_start
        if not l_start:
            continue
        span = _weekdays(l_start, l_end)
        if not span:
            continue
        inside = _weekdays(max(l_start, first), min(l_end, last))
        booked = float(days) if days is not None else float(span)
        total += booked * inside / span
    return round(total, 2)


def _pay_for_contract(conn, contract: Dict[str, Any], period: Dict[str, Any],
                      brackets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """One contract's pay for the period, or None if it does not overlap."""
    from education_system.systems.university.domains.staff.domain.staff_hr import (
        pay_structure,
        pensions,
    )
    p_start, p_end = _as_date(period['start_date']), _as_date(period['end_date'])
    first = max(p_start, _as_date(contract.get('start_date')) or p_start)
    last = min(p_end, _as_date(contract.get('end_date')) or p_end)
    if last < first:
        return None
    user_id = contract['user_id']
    period_days = (p_end - p_start).days + 1
    days_paid = (last - first).days + 1
    per_year = PERIODS_PER_YEAR.get(str(period.get('period_type') or 'monthly').lower(), 12)

    salary = pay_structure.derive_salary(conn, contract, on=p_end)
    full_time, fte = salary['full_time'], salary['fte']
    actual_annual = full_time * fte
    period_salary = actual_annual / per_year
    unpaid = _unpaid_leave_days(conn, user_id, first, last)
    basic = max(0.0, period_salary * days_paid / period_days
                - unpaid * actual_annual / pay_structure.DAYS_PER_YEAR_WORKING)

    # Sum approved overtime hours for the period date range
    ot_row = conn.execute('''
        SELECT COALESCE(SUM(hours * rate_multiplier), 0) as weighted_hours
        FROM payroll_overtime
        WHERE user_id = ?
        AND status = 'approved'
        AND date BETWEEN ? AND ?
    ''', (user_id, period['start_date'], period['end_date'])).fetchone()
    overtime_hours = ot_row['weighted_hours'] if ot_row else 0
    # Overtime pay: weighted hours * hourly rate (monthly salary / 160)
    hourly_rate = (actual_annual / 12) / OVERTIME_MONTHLY_HOURS if actual_annual > 0 else 0
    overtime_pay = overtime_hours * hourly_rate

    # Sum active allowances
    allow_row = conn.execute('''
        SELECT COALESCE(SUM(amount), 0) as total_allowances
        FROM payroll_allowances
        WHERE user_id = ?
        AND is_active = 1
    ''', (user_id,)).fetchone()
    allowances = allow_row['total_allowances'] if allow_row else 0

    gross = basic + overtime_pay + allowances

    # Pension on basic pay for the days the member was in their scheme
    scheme, days_in = pensions.scheme_for_period(conn, user_id, first.isoformat(),
                                                 last.isoformat())
    pensionable = basic * days_in / days_paid if days_paid else 0.0
    pension = pensions.contributions(conn, scheme, pensionable, full_time, actual_annual)

    # Tax after pension (net pay arrangement); NI on gross
    tax = _income_tax(brackets, max(0.0, gross - pension['employee']) * per_year) / per_year
    ni = _national_insurance(gross * per_year) / per_year
    net = gross - tax - ni - pension['employee']
    return {
        'user_id': user_id, 'contract_id': contract.get('contract_id'),
        'basic_salary': round(basic, 2), 'overtime_pay': round(overtime_pay, 2),
        'allowances_total': round(allowances, 2), 'gross_pay': round(gross, 2),
        'tax_deduction': round(tax, 2), 'ni_deduction': round(ni, 2),
        'pension_deduction': pension['employee'], 'employer_pension': pension['employer'],
        'pension_scheme': pension['scheme'], 'net_pay': round(net, 2), 'fte': fte,
        'days_paid': days_paid, 'period_days': period_days, 'unpaid_leave_days': unpaid,
        'salary_source': salary['source'],
    }


class PayrollManager:
    """Manager for payroll processing and pay records."""

    # ==================== PAYSLIP NOTICES ====================

    @staticmethod
    def send_payslip_notice(record_id: int, recipient_email: str = "",
                            staff_name: str = "") -> bool:
        """E-mail a member of staff that their payslip is ready to view in the
        HR portal. Names the period only — never any amounts. Records when it
        went (``notice_sent_at``). Best-effort."""
        try:
            with get_connection() as conn:
                _ensure(conn)
                row = conn.execute(
                    """SELECT pr.user_id, pp.name, pp.payment_date, pp.end_date
                         FROM payroll_records pr
                         JOIN payroll_periods pp ON pp.period_id = pr.period_id
                        WHERE pr.record_id = ?""",
                    (record_id,),
                ).fetchone()
                if row:
                    recipient_email = recipient_email or access.email_of(row[0], conn) or ''
                    staff_name = staff_name or access.display_name(row[0], conn)
        except Exception:
            logger.warning("payslip notice lookup failed for record %s", record_id, exc_info=True)
            row = None
        if not row:
            return False
        from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.leave_manager import (
            _send_staff_hr_email,
        )
        sent = _send_staff_hr_email('payslip_notice', recipient_email, {
            'staff_name':  staff_name or row[0],
            'period_name': row[1] or 'Pay period',
            'pay_date':    row[2] or row[3] or '',
            'record_id':   record_id,
        })
        if sent:
            with transaction() as conn:
                conn.execute("UPDATE payroll_records SET notice_sent_at = ? WHERE record_id = ?",
                             (datetime.now().isoformat(), record_id))
        return sent

    @staticmethod
    def send_period_notices(period_id: int) -> int:
        """Payslip-ready e-mails for every record of the period not yet told."""
        with get_connection() as conn:
            _ensure(conn)
            ids = [r[0] for r in conn.execute(
                "SELECT record_id FROM payroll_records WHERE period_id = ? AND notice_sent_at IS NULL",
                (period_id,)).fetchall()]
        sent = 0
        for record_id in ids:
            try:
                sent += bool(PayrollManager.send_payslip_notice(record_id))
            except Exception:
                logger.warning("payslip notice failed for record %s", record_id, exc_info=True)
        return sent

    # ==================== PAY PERIOD MANAGEMENT ====================

    @staticmethod
    def create_period(name: str, period_type: str, start_date: str,
                      end_date: str, payment_date: str = None,
                      created_by: str = None, actor: Any = None) -> int:
        """Create a new pay period."""
        me = _gate(actor, "Only payroll can create pay periods")
        created_by = created_by if actor is None else me
        start, end = _as_date(start_date), _as_date(end_date)
        if actor is not None and (not start or not end or end < start):
            raise ValueError("A pay period needs a start date on or before its end date")
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO payroll_periods (
                    name, period_type, start_date, end_date,
                    payment_date, status, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name,
                period_type,
                start_date,
                end_date,
                payment_date,
                'draft',
                created_by,
                datetime.now().isoformat(),
            ))
            period_id = cursor.lastrowid
            log_activity('create', 'payroll_period', details={
                'period_id': period_id, 'name': name, 'created_by': created_by
            })
            return period_id

    @staticmethod
    def get_periods(status: str = None) -> List[Dict[str, Any]]:
        """Get pay periods, optionally filtered by status."""
        with get_connection() as conn:
            query = 'SELECT * FROM payroll_periods'
            params = []

            if status:
                query += ' WHERE status = ?'
                params.append(status)

            query += ' ORDER BY start_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_period(period_id: int) -> Optional[Dict[str, Any]]:
        """Get a single period by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM payroll_periods WHERE period_id = ?
            ''', (period_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_period_status(period_id: int, status: str,
                             updated_by: str = None, actor: Any = None) -> bool:
        """Update period status (draft/open/processing/completed/paid/closed).
        Completing or paying a period sends the payslip-ready e-mails; paying
        it marks its records paid."""
        me = _gate(actor, "Only payroll can change a pay period")
        updated_by = updated_by if actor is None else me
        with transaction() as conn:
            conn.execute('''
                UPDATE payroll_periods
                SET status = ?, updated_by = ?, updated_at = ?
                WHERE period_id = ?
            ''', (status, updated_by, datetime.now().isoformat(), period_id))
            if status == 'paid':
                conn.execute("UPDATE payroll_records SET payment_status = 'paid' "
                             "WHERE period_id = ?", (period_id,))
            if actor is not None:
                _ensure(conn)
                access.audit(conn, actor, 'payroll.period_status', entity='payroll_period',
                             entity_id=period_id, details={'status': status})
            log_activity('update', 'payroll_period', details={
                'period_id': period_id, 'status': status, 'updated_by': updated_by
            })
        if status in ('completed', 'paid'):
            PayrollManager.send_period_notices(period_id)
        return True

    # ==================== PAYROLL PROCESSING ====================

    @staticmethod
    def run_payroll(period_id: int, created_by: str = None, actor: Any = None,
                    notify: bool = True) -> Dict[str, Any]:
        """Run payroll for a period.

        1. Get period details (a completed / paid / closed period is final)
        2. Get every contract overlapping the period (incl. leavers)
        3. For each contract calculate gross, deductions, net
        4. Insert payroll records (replacing an earlier unfinished run's)
        5. Update period status to 'completed' and send payslip notices
        6. Return summary dict
        """
        me = _gate(actor, "Only payroll can run payroll")
        created_by = created_by if actor is None else me
        with transaction() as conn:
            _ensure(conn)
            # 1. Get period details
            period = conn.execute('''
                SELECT * FROM payroll_periods WHERE period_id = ?
            ''', (period_id,)).fetchone()

            if not period:
                return {'error': 'Period not found', 'total_records': 0}

            period = dict(period)
            if str(period.get('status') or '').lower() in FINAL_STATUSES:
                return {'error': 'This period has already been processed', 'total_records': 0}
            if not (_as_date(period.get('start_date')) and _as_date(period.get('end_date'))):
                return {'error': 'The period has no valid start and end dates', 'total_records': 0}

            # Update period status to processing
            conn.execute('''
                UPDATE payroll_periods
                SET status = 'processing', updated_at = ?
                WHERE period_id = ?
            ''', (datetime.now().isoformat(), period_id))
            conn.execute("DELETE FROM payroll_records WHERE period_id = ?", (period_id,))

            # 2. Contracts overlapping the period
            marks = ', '.join('?' * len(PAYABLE_CONTRACT_STATUSES))
            contracts = conn.execute(
                f"SELECT * FROM staff_contracts WHERE status IN ({marks}) "  # nosec B608
                "AND (start_date IS NULL OR start_date <= ?) "
                "AND (end_date IS NULL OR end_date = '' OR end_date >= ?)",
                (*PAYABLE_CONTRACT_STATUSES, period['end_date'], period['start_date'])).fetchall()
            contracts = [dict(c) for c in contracts]
            brackets = _brackets(conn, tax_year_for(period['end_date']))

            total_gross = 0.0
            total_net = 0.0
            total_records = 0
            total_employer_pension = 0.0

            # 3. For each contract, calculate pay; 4. insert the record
            for contract in contracts:
                pay = _pay_for_contract(conn, contract, period, brackets)
                if pay is None:
                    continue
                names = list(pay) + ['period_id', 'created_at']
                conn.execute(
                    f"INSERT INTO payroll_records ({', '.join(names)}) "  # nosec B608
                    f"VALUES ({', '.join('?' * len(names))})",
                    tuple(pay.values()) + (period_id, datetime.now().isoformat()))
                total_gross += pay['gross_pay']
                total_net += pay['net_pay']
                total_employer_pension += pay['employer_pension']
                total_records += 1

            # 5. Update period status to 'completed'
            conn.execute('''
                UPDATE payroll_periods
                SET status = 'completed', updated_by = ?, updated_at = ?
                WHERE period_id = ?
            ''', (created_by, datetime.now().isoformat(), period_id))

            access.audit(conn, actor if actor is not None else (created_by or 'system'),
                         'payroll.run', entity='payroll_period', entity_id=period_id,
                         details={'records': total_records})
            log_activity('create', 'payroll_run', details={
                'period_id': period_id,
                'total_records': total_records,
                'total_gross': round(total_gross, 2),
                'total_net': round(total_net, 2),
                'created_by': created_by,
            })

        # Auto-post the run to the GL outside the transaction (the ledger
        # opens its own connection). Never raises.
        try:
            from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
            notify_ledger('payroll_run', period_id, posted_by=created_by or 'payroll')
        except Exception as _e:
            logger.warning("ledger hook failed for payroll run %s: %s", period_id, _e)

        notices = PayrollManager.send_period_notices(period_id) if notify else 0

        # 6. Return summary
        return {
            'total_records': total_records,
            'total_gross': round(total_gross, 2),
            'total_net': round(total_net, 2),
            'total_employer_pension': round(total_employer_pension, 2),
            'notices_sent': notices,
        }

    @staticmethod
    def calculate_deductions(gross_annual: float,
                             tax_year: str = '2025/26',
                             user_id: str = None) -> Dict[str, float]:
        """Calculate annual deductions on an annual gross.

        Tax over the tax year's brackets after pension (net pay arrangement);
        NI 8% on 12570-50270 and 2% above; pension at the employee rate of
        ``user_id``'s current scheme (none when no one is named).
        """
        from education_system.systems.university.domains.staff.domain.staff_hr import pensions
        with get_connection() as conn:
            pension = 0.0
            if user_id:
                _ensure(conn)
                today = date.today().isoformat()
                scheme, days = pensions.scheme_for_period(conn, user_id, today, today)
                if days:
                    pension = pensions.contributions(conn, scheme, gross_annual, gross_annual,
                                                     gross_annual)['employee']
            tax = _income_tax(_brackets(conn, tax_year), max(0.0, gross_annual - pension))
            return {
                'tax': round(tax, 2),
                'ni': round(_national_insurance(gross_annual), 2),
                'pension': round(pension, 2),
            }

    # ==================== PAYSLIP & HISTORY ====================

    @staticmethod
    def _check_pay_view(conn, actor: Any, staff: str) -> str:
        """The username whose pay ``actor`` asks for (raises if not theirs to see)."""
        user = access.staff_key(staff, conn) or str(staff)
        if not access.can_view_pay(actor, user, conn):
            raise PermissionError("Pay is visible only to the person and payroll")
        if user != access.username_of(actor):
            _ensure(conn)
            access.audit(conn, actor, 'payroll.view_pay', subject=user, entity='payroll_records')
            conn.commit()
        return user

    @staticmethod
    def get_user_payroll_history(user_id: str,
                                 limit: int = 24, actor: Any = None) -> List[Dict[str, Any]]:
        """Get payroll records for a user with period info."""
        with get_connection() as conn:
            if actor is not None:
                user_id = PayrollManager._check_pay_view(conn, actor, user_id)
            rows = conn.execute('''
                SELECT r.*, p.name as period_name, p.period_type,
                       p.start_date as period_start, p.end_date as period_end,
                       p.payment_date
                FROM payroll_records r
                JOIN payroll_periods p ON r.period_id = p.period_id
                WHERE r.user_id = ?
                ORDER BY p.start_date DESC
                LIMIT ?
            ''', (user_id, limit)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_payroll_record(record_id: int, actor: Any = None) -> Optional[Dict[str, Any]]:
        """Get a single payroll record."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT r.*, p.name as period_name, p.period_type,
                       p.start_date as period_start, p.end_date as period_end,
                       p.payment_date
                FROM payroll_records r
                JOIN payroll_periods p ON r.period_id = p.period_id
                WHERE r.record_id = ?
            ''', (record_id,)).fetchone()
            if row and actor is not None:
                PayrollManager._check_pay_view(conn, actor, row['user_id'])
            return dict(row) if row else None

    @staticmethod
    def get_period_records(period_id: int, actor: Any = None) -> List[Dict[str, Any]]:
        """Every record of a period (payroll)."""
        _gate(actor, "Only payroll can see everyone's pay")
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM payroll_records WHERE period_id = ? ORDER BY user_id",
                (period_id,)).fetchall()]

    @staticmethod
    def get_payroll_summary(period_id: int, actor: Any = None) -> Dict[str, Any]:
        """Get summary for a period: total_records, total_gross, total_deductions, total_net, by_department."""
        _gate(actor, "Only payroll can see payroll reports")
        with get_connection() as conn:
            _ensure(conn)
            # Aggregate totals
            row = conn.execute('''
                SELECT COUNT(*) as total_records,
                       COALESCE(SUM(gross_pay), 0) as total_gross,
                       COALESCE(SUM(COALESCE(tax_deduction, 0) + COALESCE(ni_deduction, 0)
                                    + COALESCE(pension_deduction, 0)
                                    + COALESCE(student_loan_deduction, 0)
                                    + COALESCE(other_deductions, 0)), 0) as total_deductions,
                       COALESCE(SUM(net_pay), 0) as total_net,
                       COALESCE(SUM(employer_pension), 0) as total_employer_pension
                FROM payroll_records
                WHERE period_id = ?
            ''', (period_id,)).fetchone()

            summary = dict(row) if row else {
                'total_records': 0,
                'total_gross': 0,
                'total_deductions': 0,
                'total_net': 0,
                'total_employer_pension': 0,
            }

            # By department
            dept_rows = conn.execute('''
                SELECT COALESCE(p.department, 'Unknown') as department,
                       COUNT(*) as record_count,
                       COALESCE(SUM(r.gross_pay), 0) as dept_gross,
                       COALESCE(SUM(r.net_pay), 0) as dept_net
                FROM payroll_records r
                LEFT JOIN staff_profiles p ON r.user_id = p.user_id
                WHERE r.period_id = ?
                GROUP BY p.department
            ''', (period_id,)).fetchall()

            summary['by_department'] = {
                row['department']: {
                    'record_count': row['record_count'],
                    'gross': row['dept_gross'],
                    'net': row['dept_net'],
                } for row in dept_rows
            }

            return summary

    # ==================== OVERTIME MANAGEMENT ====================

    @staticmethod
    def log_overtime(user_id: str, date: str, hours: float,
                     rate_multiplier: float = 1.5,
                     reason: str = None, actor: Any = None) -> int:
        """Log overtime hours (your own; payroll may log anyone's)."""
        if actor is not None:
            with get_connection() as conn:
                user_id = access.staff_key(user_id, conn) or str(user_id)
                if user_id != access.username_of(actor) and not access.can(actor, 'payroll', conn):
                    raise PermissionError("You can only log your own overtime")
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO payroll_overtime (
                    user_id, date, hours, rate_multiplier,
                    reason, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                date,
                hours,
                rate_multiplier,
                reason,
                'pending',
                datetime.now().isoformat(),
            ))
            overtime_id = cursor.lastrowid
            log_activity('create', 'payroll_overtime', details={
                'overtime_id': overtime_id, 'user_id': user_id,
                'hours': hours, 'date': date,
            })
            return overtime_id

    @staticmethod
    def get_user_overtime(user_id: str,
                          status: str = None, actor: Any = None) -> List[Dict[str, Any]]:
        """Get overtime entries for a user."""
        with get_connection() as conn:
            if actor is not None:
                user_id = access.staff_key(user_id, conn) or str(user_id)
                if not (user_id == access.username_of(actor) or access.can(actor, 'payroll', conn)
                        or access.can_approve_for(actor, user_id, conn)):
                    raise PermissionError("You cannot see this person's overtime")
            query = 'SELECT * FROM payroll_overtime WHERE user_id = ?'
            params = [user_id]

            if status:
                query += ' AND status = ?'
                params.append(status)

            query += ' ORDER BY date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_pending_overtime(actor: Any = None) -> List[Dict[str, Any]]:
        """Pending overtime: everyone's for payroll, a manager's reports' otherwise."""
        with get_connection() as conn:
            rows = [dict(row) for row in conn.execute('''
                SELECT * FROM payroll_overtime
                WHERE status = 'pending'
                ORDER BY date ASC
            ''').fetchall()]
            if actor is None or access.can(actor, 'payroll', conn):
                return rows
            me = access.username_of(actor)
            return [r for r in rows if str(r.get('user_id')) != me
                    and access.can_approve_for(actor, str(r.get('user_id')), conn)]

    @staticmethod
    def _decide_overtime(overtime_id: int, approved_by: str, status: str, actor: Any) -> None:
        with transaction() as conn:
            row = conn.execute("SELECT user_id FROM payroll_overtime WHERE overtime_id = ?",
                               (overtime_id,)).fetchone()
            if not row:
                raise ValueError("Overtime entry not found")
            # without ``actor``, the person ``approved_by`` names decides
            who = people.decider(actor, approved_by, conn)
            me = who['username']
            if row[0] == me:
                raise PermissionError("You cannot approve your own overtime")
            if not (access.can(who, 'payroll', conn)
                    or access.can_approve_for(who, row[0], conn)):
                raise PermissionError("Only their line manager or payroll can decide this")
            approved_by = me
            _ensure(conn)
            access.audit(conn, who, f'payroll.overtime_{status}', subject=row[0],
                         entity='payroll_overtime', entity_id=overtime_id)
            conn.execute('''
                UPDATE payroll_overtime
                SET status = ?, approved_by = ?, approved_date = ?
                WHERE overtime_id = ?
            ''', (status, approved_by, datetime.now().isoformat(), overtime_id))
            log_activity('update', 'payroll_overtime', details={
                'overtime_id': overtime_id, 'action': status,
                'approved_by': approved_by,
            })

    @staticmethod
    def approve_overtime(overtime_id: int, approved_by: str, actor: Any = None) -> None:
        """Approve overtime entry."""
        PayrollManager._decide_overtime(overtime_id, approved_by, 'approved', actor)

    @staticmethod
    def reject_overtime(overtime_id: int, approved_by: str, actor: Any = None) -> None:
        """Reject overtime entry."""
        PayrollManager._decide_overtime(overtime_id, approved_by, 'rejected', actor)

    # ==================== ALLOWANCE MANAGEMENT ====================

    @staticmethod
    def add_allowance(user_id: str, allowance_type: str, amount: float,
                      frequency: str = 'monthly', start_date: str = None,
                      approved_by: str = None,
                      notes: str = None, actor: Any = None) -> int:
        """Add a recurring allowance."""
        me = _gate(actor, "Only payroll can add allowances")
        if actor is not None:
            approved_by = me
            with get_connection() as conn:
                user_id = access.staff_key(user_id, conn) or ''
            if not user_id:
                raise ValueError("No member of staff by that name")
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO payroll_allowances (
                    user_id, allowance_type, amount, frequency,
                    start_date, approved_by, notes, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                allowance_type,
                amount,
                frequency,
                start_date or datetime.now().strftime('%Y-%m-%d'),
                approved_by,
                notes,
                1,
                datetime.now().isoformat(),
            ))
            allowance_id = cursor.lastrowid
            if actor is not None:
                _ensure(conn)
                access.audit(conn, actor, 'payroll.allowance_added', subject=user_id,
                             entity='payroll_allowance', entity_id=allowance_id,
                             details={'type': allowance_type})
            log_activity('create', 'payroll_allowance', details={
                'allowance_id': allowance_id, 'user_id': user_id,
                'allowance_type': allowance_type, 'amount': amount,
            })
            return allowance_id

    @staticmethod
    def get_user_allowances(user_id: str,
                            active_only: bool = True, actor: Any = None) -> List[Dict[str, Any]]:
        """Get allowances for a user."""
        with get_connection() as conn:
            if actor is not None:
                user_id = PayrollManager._check_pay_view(conn, actor, user_id)
            query = 'SELECT * FROM payroll_allowances WHERE user_id = ?'
            params = [user_id]

            if active_only:
                query += ' AND is_active = 1'

            query += ' ORDER BY allowance_type'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_all_allowances(actor: Any = None) -> List[Dict[str, Any]]:
        """Everyone's allowances (payroll)."""
        _gate(actor, "Only payroll can see everyone's allowances")
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM payroll_allowances ORDER BY user_id, allowance_type").fetchall()]

    @staticmethod
    def deactivate_allowance(allowance_id: int, actor: Any = None) -> None:
        """Deactivate an allowance."""
        _gate(actor, "Only payroll can change allowances")
        with transaction() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(payroll_allowances)").fetchall()}
            if 'updated_at' in cols:
                conn.execute('''
                    UPDATE payroll_allowances
                    SET is_active = 0, updated_at = ?
                    WHERE allowance_id = ?
                ''', (datetime.now().isoformat(), allowance_id))
            else:
                conn.execute("UPDATE payroll_allowances SET is_active = 0 WHERE allowance_id = ?",
                             (allowance_id,))
            if actor is not None:
                _ensure(conn)
                access.audit(conn, actor, 'payroll.allowance_deactivated',
                             entity='payroll_allowance', entity_id=allowance_id)
            log_activity('update', 'payroll_allowance', details={
                'allowance_id': allowance_id, 'action': 'deactivated',
            })

    # ==================== TAX CONFIGURATION ====================

    @staticmethod
    def get_tax_brackets(tax_year: str = '2025/26') -> List[Dict[str, Any]]:
        """Get tax brackets for a year."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM tax_brackets
                WHERE tax_year = ?
                ORDER BY lower_limit ASC
            ''', (tax_year,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_tax_bracket(tax_year: str, bracket_name: str,
                           lower_limit: float, upper_limit: float,
                           rate: float,
                           personal_allowance: float = 0, actor: Any = None) -> int:
        """Create a tax bracket."""
        _gate(actor, "Only payroll can change tax brackets")
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO tax_brackets (
                    tax_year, bracket_name, lower_limit, upper_limit,
                    rate, personal_allowance, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                tax_year,
                bracket_name,
                lower_limit,
                upper_limit,
                rate,
                personal_allowance,
                datetime.now().isoformat(),
            ))
            bracket_id = cursor.lastrowid
            log_activity('create', 'tax_bracket', details={
                'bracket_id': bracket_id, 'tax_year': tax_year,
                'bracket_name': bracket_name, 'rate': rate,
            })
            return bracket_id

    # ==================== COMPATIBILITY ====================

    @staticmethod
    def get_all_categories() -> List[Dict[str, Any]]:
        """Compatibility - returns empty list."""
        return []
