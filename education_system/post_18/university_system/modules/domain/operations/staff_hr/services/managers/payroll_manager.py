"""
Payroll Manager - Payroll processing and pay records management.

Provides functionality for:
- Pay period creation and management
- Payroll processing with tax/NI/pension calculations
- Payslip generation and history
- Overtime logging and approval
- Allowance management
- Tax bracket configuration
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity
from education_system.post_18.university_system.core.sql_safety import validate_identifier  # nosec B608


class PayrollManager:
    """Manager for payroll processing and pay records."""

    @staticmethod
    def send_payslip_notice(record_id: int, recipient_email: str,
                            staff_name: str = "") -> bool:
        """Email a staff member to say a payslip is ready in the HR portal.
        Reads pay-record + period rows to populate the email. Best-effort."""
        try:
            with get_connection() as conn:
                row = conn.execute(
                    """SELECT pr.user_id, pr.gross_pay, pr.total_deductions, pr.net_pay,
                              pp.name, pp.start_date, pp.end_date, pp.payment_date
                         FROM payroll_records pr
                         JOIN pay_periods     pp ON pp.period_id = pr.period_id
                        WHERE pr.record_id = ?""",
                    (record_id,),
                ).fetchone()
        except Exception:
            row = None
        if not row:
            return False
        from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.leave_manager import (
            _send_staff_hr_email,
        )
        return _send_staff_hr_email('payslip_notice', recipient_email, {
            'staff_id':         row[0],
            'staff_name':       staff_name or row[0],
            'period_name':      row[4] or 'Pay period',
            'period_start':     row[5] or '',
            'period_end':       row[6] or '',
            'pay_date':         row[7] or '',
            'gross_pay':        row[1] or 0,
            'total_deductions': row[2] or 0,
            'net_pay':          row[3] or 0,
            'record_id':        record_id,
        })

    # ==================== PAY PERIOD MANAGEMENT ====================

    @staticmethod
    def create_period(name: str, period_type: str, start_date: str,
                      end_date: str, payment_date: str = None,
                      created_by: str = None) -> int:
        """Create a new pay period."""
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
                             updated_by: str = None) -> bool:
        """Update period status (draft/open/processing/completed/closed)."""
        with transaction() as conn:
            conn.execute('''
                UPDATE payroll_periods
                SET status = ?, updated_by = ?, updated_at = ?
                WHERE period_id = ?
            ''', (status, updated_by, datetime.now().isoformat(), period_id))
            log_activity('update', 'payroll_period', details={
                'period_id': period_id, 'status': status, 'updated_by': updated_by
            })
            return True

    # ==================== PAYROLL PROCESSING ====================

    @staticmethod
    def run_payroll(period_id: int, created_by: str = None) -> Dict[str, Any]:
        """Run payroll for a period.

        1. Get period details
        2. Get all active contracts (staff_contracts WHERE status='active')
        3. For each contract calculate gross, deductions, net
        4. Insert payroll records
        5. Update period status to 'completed'
        6. Return summary dict
        """
        with transaction() as conn:
            # 1. Get period details
            period = conn.execute('''
                SELECT * FROM payroll_periods WHERE period_id = ?
            ''', (period_id,)).fetchone()

            if not period:
                return {'error': 'Period not found', 'total_records': 0}

            period = dict(period)

            # Update period status to processing
            conn.execute('''
                UPDATE payroll_periods
                SET status = 'processing', updated_at = ?
                WHERE period_id = ?
            ''', (datetime.now().isoformat(), period_id))

            # 2. Get all active contracts
            contracts = conn.execute('''
                SELECT * FROM staff_contracts WHERE status = 'active'
            ''').fetchall()
            contracts = [dict(c) for c in contracts]

            total_gross = 0.0
            total_net = 0.0
            total_records = 0

            # 3. For each contract, calculate pay
            for contract in contracts:
                user_id = contract['user_id']
                annual_salary = contract.get('salary', 0) or 0

                # basic_salary = annual / 12 (monthly)
                basic_salary = annual_salary / 12

                # Sum approved overtime hours for the period date range
                ot_row = conn.execute('''
                    SELECT COALESCE(SUM(hours * rate_multiplier), 0) as weighted_hours
                    FROM payroll_overtime
                    WHERE user_id = ?
                    AND status = 'approved'
                    AND date BETWEEN ? AND ?
                ''', (user_id, period['start_date'], period['end_date'])).fetchone()

                overtime_hours = ot_row['weighted_hours'] if ot_row else 0
                # Overtime pay: overtime weighted hours * hourly rate (monthly / 160)
                hourly_rate = basic_salary / 160 if basic_salary > 0 else 0
                overtime_pay = overtime_hours * hourly_rate

                # Sum active allowances
                allow_row = conn.execute('''
                    SELECT COALESCE(SUM(amount), 0) as total_allowances
                    FROM payroll_allowances
                    WHERE user_id = ?
                    AND is_active = 1
                ''', (user_id,)).fetchone()

                allowances = allow_row['total_allowances'] if allow_row else 0

                # Gross pay
                gross = basic_salary + overtime_pay + allowances

                # Calculate deductions based on annual gross
                gross_annual = gross * 12
                tax_year = '2025/26'

                # Get tax brackets for progressive taxation
                brackets = conn.execute('''
                    SELECT * FROM tax_brackets
                    WHERE tax_year = ?
                    ORDER BY lower_limit ASC
                ''', (tax_year,)).fetchall()
                brackets = [dict(b) for b in brackets]

                # Progressive tax calculation
                annual_tax = 0.0
                for bracket in brackets:
                    lower = bracket.get('lower_limit', 0) or 0
                    upper = bracket.get('upper_limit') or float('inf')
                    rate = bracket.get('rate', 0) or 0
                    personal_allowance = bracket.get('personal_allowance', 0) or 0

                    taxable_in_bracket = max(0, min(gross_annual, upper) - max(lower, personal_allowance))
                    if taxable_in_bracket > 0:
                        annual_tax += taxable_in_bracket * rate

                # NI calculation: 8% on earnings between 12570-50270, 2% above 50270
                annual_ni = 0.0
                if gross_annual > 12570:
                    ni_band1 = min(gross_annual, 50270) - 12570
                    annual_ni += max(0, ni_band1) * 0.08
                if gross_annual > 50270:
                    ni_band2 = gross_annual - 50270
                    annual_ni += ni_band2 * 0.02

                # Pension: 5% of gross
                annual_pension = gross_annual * 0.05

                # Monthly deductions
                tax = annual_tax / 12
                ni = annual_ni / 12
                pension = annual_pension / 12

                # Net pay
                net = gross - tax - ni - pension

                # Insert payroll record. Column names match the schema —
                # the previous version used 'allowances', 'tax',
                # 'national_insurance', 'pension' which don't exist on
                # payroll_records (real columns: allowances_total,
                # tax_deduction, ni_deduction, pension_deduction). Fixed.
                conn.execute('''
                    INSERT INTO payroll_records (
                        period_id, user_id, basic_salary, overtime_pay,
                        allowances_total, gross_pay, tax_deduction, ni_deduction,
                        pension_deduction, net_pay, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    period_id, user_id, basic_salary, overtime_pay,
                    allowances, gross, tax, ni,
                    pension, net, datetime.now().isoformat(),
                ))

                total_gross += gross
                total_net += net
                total_records += 1

            # 4. Update period status to 'completed'
            conn.execute('''
                UPDATE payroll_periods
                SET status = 'completed', updated_by = ?, updated_at = ?
                WHERE period_id = ?
            ''', (created_by, datetime.now().isoformat(), period_id))

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
            from education_system.post_18.university_system.modules.domain.finance.ledger import notify_ledger
            notify_ledger('payroll_run', period_id, posted_by=created_by or 'payroll')
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning("ledger hook failed for payroll run %s: %s",
                                                period_id, _e)

        # 5. Return summary
        return {
            'total_records': total_records,
            'total_gross': round(total_gross, 2),
            'total_net': round(total_net, 2),
        }

    @staticmethod
    def calculate_deductions(gross_annual: float,
                             tax_year: str = '2025/26') -> Dict[str, float]:
        """Calculate tax deductions based on annual gross.

        1. Get tax_brackets for tax_year ordered by lower_limit
        2. Apply progressive taxation
        3. NI: 8% on earnings between 12570-50270, 2% above 50270
        4. Pension: 5% of gross
        Returns dict with tax, ni, pension keys (annual amounts).
        """
        with get_connection() as conn:
            # Get tax brackets
            brackets = conn.execute('''
                SELECT * FROM tax_brackets
                WHERE tax_year = ?
                ORDER BY lower_limit ASC
            ''', (tax_year,)).fetchall()
            brackets = [dict(b) for b in brackets]

            # Progressive tax calculation
            tax = 0.0
            for bracket in brackets:
                lower = bracket.get('lower_limit', 0) or 0
                upper = bracket.get('upper_limit') or float('inf')
                rate = bracket.get('rate', 0) or 0
                personal_allowance = bracket.get('personal_allowance', 0) or 0

                taxable_in_bracket = max(0, min(gross_annual, upper) - max(lower, personal_allowance))
                if taxable_in_bracket > 0:
                    tax += taxable_in_bracket * rate

            # NI: 8% on earnings between 12570-50270, 2% above 50270
            ni = 0.0
            if gross_annual > 12570:
                ni_band1 = min(gross_annual, 50270) - 12570
                ni += max(0, ni_band1) * 0.08
            if gross_annual > 50270:
                ni_band2 = gross_annual - 50270
                ni += ni_band2 * 0.02

            # Pension: 5% of gross
            pension = gross_annual * 0.05

            return {
                'tax': round(tax, 2),
                'ni': round(ni, 2),
                'pension': round(pension, 2),
            }

    # ==================== PAYSLIP & HISTORY ====================

    @staticmethod
    def get_user_payroll_history(user_id: str,
                                 limit: int = 24) -> List[Dict[str, Any]]:
        """Get payroll records for a user with period info."""
        with get_connection() as conn:
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
    def get_payroll_record(record_id: int) -> Optional[Dict[str, Any]]:
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
            return dict(row) if row else None

    @staticmethod
    def get_payroll_summary(period_id: int) -> Dict[str, Any]:
        """Get summary for a period: total_records, total_gross, total_deductions, total_net, by_department."""
        with get_connection() as conn:
            # Aggregate totals
            row = conn.execute('''
                SELECT COUNT(*) as total_records,
                       COALESCE(SUM(gross_pay), 0) as total_gross,
                       COALESCE(SUM(tax + national_insurance + pension), 0) as total_deductions,
                       COALESCE(SUM(net_pay), 0) as total_net
                FROM payroll_records
                WHERE period_id = ?
            ''', (period_id,)).fetchone()

            summary = dict(row) if row else {
                'total_records': 0,
                'total_gross': 0,
                'total_deductions': 0,
                'total_net': 0,
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
                     reason: str = None) -> int:
        """Log overtime hours."""
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
                          status: str = None) -> List[Dict[str, Any]]:
        """Get overtime entries for a user."""
        with get_connection() as conn:
            query = 'SELECT * FROM payroll_overtime WHERE user_id = ?'
            params = [user_id]

            if status:
                query += ' AND status = ?'
                params.append(status)

            query += ' ORDER BY date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_pending_overtime() -> List[Dict[str, Any]]:
        """Get all pending overtime entries (for admin approval)."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM payroll_overtime
                WHERE status = 'pending'
                ORDER BY date ASC
            ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def approve_overtime(overtime_id: int, approved_by: str) -> None:
        """Approve overtime entry."""
        with transaction() as conn:
            conn.execute('''
                UPDATE payroll_overtime
                SET status = 'approved', approved_by = ?, approved_date = ?
                WHERE overtime_id = ?
            ''', (approved_by, datetime.now().isoformat(), overtime_id))
            log_activity('update', 'payroll_overtime', details={
                'overtime_id': overtime_id, 'action': 'approved',
                'approved_by': approved_by,
            })

    @staticmethod
    def reject_overtime(overtime_id: int, approved_by: str) -> None:
        """Reject overtime entry."""
        with transaction() as conn:
            conn.execute('''
                UPDATE payroll_overtime
                SET status = 'rejected', approved_by = ?, approved_date = ?
                WHERE overtime_id = ?
            ''', (approved_by, datetime.now().isoformat(), overtime_id))
            log_activity('update', 'payroll_overtime', details={
                'overtime_id': overtime_id, 'action': 'rejected',
                'approved_by': approved_by,
            })

    # ==================== ALLOWANCE MANAGEMENT ====================

    @staticmethod
    def add_allowance(user_id: str, allowance_type: str, amount: float,
                      frequency: str = 'monthly', start_date: str = None,
                      approved_by: str = None,
                      notes: str = None) -> int:
        """Add a recurring allowance."""
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
            log_activity('create', 'payroll_allowance', details={
                'allowance_id': allowance_id, 'user_id': user_id,
                'allowance_type': allowance_type, 'amount': amount,
            })
            return allowance_id

    @staticmethod
    def get_user_allowances(user_id: str,
                            active_only: bool = True) -> List[Dict[str, Any]]:
        """Get allowances for a user."""
        with get_connection() as conn:
            query = 'SELECT * FROM payroll_allowances WHERE user_id = ?'
            params = [user_id]

            if active_only:
                query += ' AND is_active = 1'

            query += ' ORDER BY allowance_type'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def deactivate_allowance(allowance_id: int) -> None:
        """Deactivate an allowance."""
        with transaction() as conn:
            conn.execute('''
                UPDATE payroll_allowances
                SET is_active = 0, updated_at = ?
                WHERE allowance_id = ?
            ''', (datetime.now().isoformat(), allowance_id))
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
                           personal_allowance: float = 0) -> int:
        """Create a tax bracket."""
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
