"""
Contract Manager - Staff contract and employment management.

Provides functionality for:
- Contract creation and tracking
- Renewal alerts (30/60/90 days)
- Probation period tracking
- Probation review scheduling
- Contract amendment history
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.core.sql_safety import validate_identifier


class ContractManager:
    """Manager for staff contracts and employment records."""

    # ==================== CONTRACT CRUD ====================

    @staticmethod
    def create_contract(user_id: str, **data) -> int:
        """Create a new staff contract."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO staff_contracts (
                    user_id, contract_type, start_date, end_date, salary,
                    salary_currency, pay_frequency, terms, status,
                    renewal_date, probation_end_date, notice_period_days,
                    working_hours_per_week, department, job_title,
                    manager_id, document_path, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                data.get('contract_type', 'permanent'),
                data.get('start_date'),
                data.get('end_date'),
                data.get('salary'),
                data.get('salary_currency', 'GBP'),
                data.get('pay_frequency', 'monthly'),
                data.get('terms'),
                data.get('status', 'active'),
                data.get('renewal_date'),
                data.get('probation_end_date'),
                data.get('notice_period_days', 30),
                data.get('working_hours_per_week', 37.5),
                data.get('department'),
                data.get('job_title'),
                data.get('manager_id'),
                data.get('document_path'),
                data.get('created_by'),
            ))
            contract_id = cursor.lastrowid

            # Create renewal alerts if end_date is set
            if data.get('end_date'):
                ContractManager._create_renewal_alerts(conn, contract_id, data['end_date'], user_id)

            log_activity('create', 'staff_contract', details={
                'contract_id': contract_id, 'user_id': user_id
            })
            return contract_id

    @staticmethod
    def get_contract(contract_id: int) -> Optional[Dict[str, Any]]:
        """Get a contract by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM staff_contracts WHERE contract_id = ?
            ''', (contract_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_user_contracts(user_id: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """Get all contracts for a user."""
        with get_connection() as conn:
            if include_inactive:
                rows = conn.execute('''
                    SELECT * FROM staff_contracts
                    WHERE user_id = ?
                    ORDER BY start_date DESC
                ''', (user_id,)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM staff_contracts
                    WHERE user_id = ? AND status = 'active'
                    ORDER BY start_date DESC
                ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_active_contract(user_id: str) -> Optional[Dict[str, Any]]:
        """Get the current active contract for a user."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM staff_contracts
                WHERE user_id = ? AND status = 'active'
                ORDER BY start_date DESC LIMIT 1
            ''', (user_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_contract(contract_id: int, **data) -> bool:
        """Update a contract."""
        if not data:
            return False

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('contract_id', 'created_at', 'user_id'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return False

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(contract_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE staff_contracts SET ' + ', '.join(fields) + ' WHERE contract_id = ?',
                values)
            log_activity('update', 'staff_contract', details={
                'contract_id': contract_id, 'updated_fields': list(data.keys())
            })
            return True

    @staticmethod
    def terminate_contract(contract_id: int, termination_date: str,
                          reason: str = None, terminated_by: str = None) -> bool:
        """Terminate a contract."""
        with transaction() as conn:
            conn.execute('''
                UPDATE staff_contracts
                SET status = 'terminated', end_date = ?, updated_at = ?
                WHERE contract_id = ?
            ''', (termination_date, datetime.now().isoformat(), contract_id))

            log_activity('update', 'staff_contract', details={
                'contract_id': contract_id,
                'action': 'terminated',
                'termination_date': termination_date,
                'reason': reason
            })
            return True

    # ==================== CONTRACT AMENDMENTS ====================

    @staticmethod
    def create_amendment(contract_id: int, **data) -> int:
        """Create a contract amendment."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO contract_amendments (
                    contract_id, change_type, field_changed, old_value,
                    new_value, effective_date, reason, approved_by,
                    approved_date, status, document_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                contract_id,
                data.get('change_type'),
                data.get('field_changed'),
                data.get('old_value'),
                data.get('new_value'),
                data.get('effective_date'),
                data.get('reason'),
                data.get('approved_by'),
                data.get('approved_date'),
                data.get('status', 'pending'),
                data.get('document_path'),
            ))
            amendment_id = cursor.lastrowid
            log_activity('create', 'contract_amendment', details={
                'amendment_id': amendment_id, 'contract_id': contract_id
            })
            return amendment_id

    @staticmethod
    def get_contract_amendments(contract_id: int) -> List[Dict[str, Any]]:
        """Get all amendments for a contract."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM contract_amendments
                WHERE contract_id = ?
                ORDER BY effective_date DESC
            ''', (contract_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def approve_amendment(amendment_id: int, approved_by: str) -> bool:
        """Approve a contract amendment."""
        with transaction() as conn:
            conn.execute('''
                UPDATE contract_amendments
                SET status = 'approved', approved_by = ?, approved_date = ?
                WHERE amendment_id = ?
            ''', (approved_by, datetime.now().isoformat(), amendment_id))
            log_activity('update', 'contract_amendment', details={
                'amendment_id': amendment_id, 'action': 'approved'
            })
            return True

    # ==================== PROBATION MANAGEMENT ====================

    @staticmethod
    def create_probation_review(user_id: str, **data) -> int:
        """Create a probation review."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO probation_reviews (
                    user_id, contract_id, review_date, reviewer_id,
                    review_type, outcome, performance_rating, strengths,
                    areas_for_improvement, comments, objectives_met,
                    recommendation, next_review_date, probation_extended,
                    extension_reason, extension_end_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                data.get('contract_id'),
                data.get('review_date'),
                data.get('reviewer_id'),
                data.get('review_type', 'mid-probation'),
                data.get('outcome'),
                data.get('performance_rating'),
                data.get('strengths'),
                data.get('areas_for_improvement'),
                data.get('comments'),
                data.get('objectives_met'),
                data.get('recommendation'),
                data.get('next_review_date'),
                data.get('probation_extended', False),
                data.get('extension_reason'),
                data.get('extension_end_date'),
            ))
            review_id = cursor.lastrowid
            log_activity('create', 'probation_review', details={
                'review_id': review_id, 'user_id': user_id
            })
            return review_id

    @staticmethod
    def get_probation_reviews(user_id: str) -> List[Dict[str, Any]]:
        """Get all probation reviews for a user."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM probation_reviews
                WHERE user_id = ?
                ORDER BY review_date DESC
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_pending_probation_reviews(manager_id: str = None) -> List[Dict[str, Any]]:
        """Get staff with pending probation reviews."""
        with get_connection() as conn:
            today = datetime.now().date().isoformat()
            query = '''
                SELECT c.*, p.name as employee_name
                FROM staff_contracts c
                LEFT JOIN staff_profiles p ON c.user_id = p.user_id
                WHERE c.status = 'active'
                AND c.probation_end_date IS NOT NULL
                AND c.probation_end_date >= ?
                AND c.probation_end_date <= date(?, '+30 days')
            '''
            params = [today, today]

            if manager_id:
                query += ' AND c.manager_id = ?'
                params.append(manager_id)

            query += ' ORDER BY c.probation_end_date ASC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def extend_probation(contract_id: int, new_end_date: str,
                        reason: str, extended_by: str) -> bool:
        """Extend a probation period."""
        with transaction() as conn:
            conn.execute('''
                UPDATE staff_contracts
                SET probation_end_date = ?, updated_at = ?
                WHERE contract_id = ?
            ''', (new_end_date, datetime.now().isoformat(), contract_id))

            log_activity('update', 'staff_contract', details={
                'contract_id': contract_id,
                'action': 'probation_extended',
                'new_end_date': new_end_date,
                'reason': reason
            })
            return True

    @staticmethod
    def complete_probation(contract_id: int, outcome: str,
                          completed_by: str) -> bool:
        """Mark probation as completed."""
        with transaction() as conn:
            # Clear probation end date to indicate completion
            conn.execute('''
                UPDATE staff_contracts
                SET probation_end_date = NULL, updated_at = ?
                WHERE contract_id = ?
            ''', (datetime.now().isoformat(), contract_id))

            log_activity('update', 'staff_contract', details={
                'contract_id': contract_id,
                'action': 'probation_completed',
                'outcome': outcome
            })
            return True

    # ==================== RENEWAL ALERTS ====================

    @staticmethod
    def _create_renewal_alerts(conn, contract_id: int, end_date: str, user_id: str):
        """Create renewal alerts for a contract (internal method)."""
        end_dt = datetime.fromisoformat(end_date)
        alerts = [
            (90, '90_day_warning'),
            (60, '60_day_warning'),
            (30, '30_day_warning'),
            (14, '14_day_warning'),
            (7, '7_day_warning'),
        ]

        for days, alert_type in alerts:
            alert_date = (end_dt - timedelta(days=days)).isoformat()
            conn.execute('''
                INSERT INTO contract_renewal_alerts
                (contract_id, alert_type, alert_date, days_before_expiry, recipient_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (contract_id, alert_type, alert_date, days, user_id))

    @staticmethod
    def get_pending_renewal_alerts() -> List[Dict[str, Any]]:
        """Get all pending renewal alerts that need to be sent."""
        with get_connection() as conn:
            today = datetime.now().date().isoformat()
            rows = conn.execute('''
                SELECT a.*, c.user_id, c.job_title, c.department, c.end_date
                FROM contract_renewal_alerts a
                JOIN staff_contracts c ON a.contract_id = c.contract_id
                WHERE a.sent = 0
                AND a.alert_date <= ?
                AND c.status = 'active'
                ORDER BY a.alert_date ASC
            ''', (today,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def mark_alert_sent(alert_id: int) -> bool:
        """Mark a renewal alert as sent."""
        with transaction() as conn:
            conn.execute('''
                UPDATE contract_renewal_alerts
                SET sent = 1, sent_date = ?
                WHERE alert_id = ?
            ''', (datetime.now().isoformat(), alert_id))
            return True

    @staticmethod
    def get_expiring_contracts(days_ahead: int = 90) -> List[Dict[str, Any]]:
        """Get contracts expiring within the specified number of days."""
        with get_connection() as conn:
            today = datetime.now().date().isoformat()
            future = (datetime.now().date() + timedelta(days=days_ahead)).isoformat()
            rows = conn.execute('''
                SELECT c.*, p.employee_id, p.bio as employee_name
                FROM staff_contracts c
                LEFT JOIN staff_profiles p ON c.user_id = p.user_id
                WHERE c.status = 'active'
                AND c.end_date IS NOT NULL
                AND c.end_date BETWEEN ? AND ?
                ORDER BY c.end_date ASC
            ''', (today, future)).fetchall()
            return [dict(row) for row in rows]

    # ==================== REPORTING ====================

    @staticmethod
    def get_contract_statistics() -> Dict[str, Any]:
        """Get contract statistics."""
        with get_connection() as conn:
            stats = {}

            # Total active contracts
            row = conn.execute('''
                SELECT COUNT(*) as count FROM staff_contracts WHERE status = 'active'
            ''').fetchone()
            stats['total_active'] = row['count'] if row else 0

            # By contract type
            rows = conn.execute('''
                SELECT contract_type, COUNT(*) as count
                FROM staff_contracts
                WHERE status = 'active'
                GROUP BY contract_type
            ''').fetchall()
            stats['by_type'] = {row['contract_type']: row['count'] for row in rows}

            # Expiring soon (30 days)
            today = datetime.now().date().isoformat()
            future_30 = (datetime.now().date() + timedelta(days=30)).isoformat()
            row = conn.execute('''
                SELECT COUNT(*) as count
                FROM staff_contracts
                WHERE status = 'active'
                AND end_date BETWEEN ? AND ?
            ''', (today, future_30)).fetchone()
            stats['expiring_30_days'] = row['count'] if row else 0

            # In probation
            row = conn.execute('''
                SELECT COUNT(*) as count
                FROM staff_contracts
                WHERE status = 'active'
                AND probation_end_date IS NOT NULL
                AND probation_end_date >= ?
            ''', (today,)).fetchone()
            stats['in_probation'] = row['count'] if row else 0

            return stats

    @staticmethod
    def search_contracts(search_term: str = None, department: str = None,
                        contract_type: str = None, status: str = 'active') -> List[Dict[str, Any]]:
        """Search contracts with filters."""
        with get_connection() as conn:
            query = '''
                SELECT c.*, p.employee_id
                FROM staff_contracts c
                LEFT JOIN staff_profiles p ON c.user_id = p.user_id
                WHERE 1=1
            '''
            params = []

            if status:
                query += ' AND c.status = ?'
                params.append(status)

            if department:
                query += ' AND c.department = ?'
                params.append(department)

            if contract_type:
                query += ' AND c.contract_type = ?'
                params.append(contract_type)

            if search_term:
                query += ''' AND (c.user_id LIKE ? OR c.job_title LIKE ?
                            OR p.employee_id LIKE ?)'''
                search_pattern = f'%{search_term}%'
                params.extend([search_pattern, search_pattern, search_pattern])

            query += ' ORDER BY c.start_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
