"""
Leave Manager

Handles leave requests, balances, approvals,
leave types, and leave calendar functionality.
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.sql_safety import validate_identifier  # nosec B608

try:
    from education_system.post_18.university_system.core.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


def _send_staff_hr_email(template_name: str, recipient_email: str,
                         vars_: Dict[str, Any]) -> bool:
    """Render ``staff_hr/<template_name>`` and dispatch best-effort.

    Skips silently when *recipient_email* is empty."""
    if not recipient_email:
        logger.debug("staff_hr/%s skipped: no recipient", template_name)
        return False
    try:
        from education_system.post_18.university_system.infrastructure.email.template_utils import (
            render_template,
        )
        from education_system.post_18.university_system.infrastructure.email.email_service import (
            send_email,
        )
    except Exception:
        logger.exception("email infrastructure unavailable")
        return False
    subject, body = render_template(f"staff_hr/{template_name}", vars_)
    if not subject or not body:
        logger.error("template render failed: staff_hr/%s", template_name)
        return False
    try:
        send_email(recipient_email=recipient_email, subject=subject, body=body)
        logger.info("sent staff_hr/%s to %s", template_name, recipient_email)
        return True
    except Exception:
        logger.exception("send_email failed staff_hr/%s recipient=%s",
                         template_name, recipient_email)
        return False


class LeaveManager:
    """Manager for leave requests and balances."""

    # ==================== LEAVE TYPES ====================

    @staticmethod
    def get_leave_types(active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all leave types."""
        with get_connection() as conn:
            if active_only:
                rows = conn.execute('''
                    SELECT * FROM leave_types WHERE is_active = 1
                    ORDER BY name
                ''').fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM leave_types ORDER BY name
                ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_leave_type(leave_type_id: int) -> Optional[Dict[str, Any]]:
        """Get a leave type by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM leave_types WHERE leave_type_id = ?
            ''', (leave_type_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_leave_type(name: str, **data) -> int:
        """Create a new leave type."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO leave_types (
                    name, description, max_days_per_year,
                    requires_approval, is_paid, color_code, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                name,
                data.get('description'),
                data.get('max_days_per_year', 0),
                data.get('requires_approval', 1),
                data.get('is_paid', 1),
                data.get('color_code', '#3498db'),
                data.get('is_active', 1),
            ))
            leave_type_id = cursor.lastrowid
            log_activity('create', 'leave_type',
                        details={'leave_type_id': leave_type_id, 'name': name})
            return leave_type_id

    @staticmethod
    def update_leave_type(leave_type_id: int, **data) -> bool:
        """Update a leave type."""
        if not data:
            return False

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('leave_type_id', 'created_at'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return False

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(leave_type_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE leave_types SET ' + ', '.join(fields) + ' WHERE leave_type_id = ?',
                values)
            log_activity('update', 'leave_type',
                        details={'leave_type_id': leave_type_id})
            return True

    # ==================== LEAVE BALANCES ====================

    @staticmethod
    def get_balance(user_id: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get leave balance for a user, optionally for a specific year."""
        current_year = year or datetime.now().year
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT b.*, t.name as leave_type_name, t.color_code,
                       (b.allocated_days + b.carried_over - b.used_days) as remaining_days
                FROM leave_balances b
                JOIN leave_types t ON b.leave_type_id = t.leave_type_id
                WHERE b.user_id = ? AND b.year = ?
                ORDER BY t.name
            ''', (user_id, current_year)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_balance_for_type(user_id: str, leave_type_id: int,
                             year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get leave balance for a specific leave type."""
        current_year = year or datetime.now().year
        with get_connection() as conn:
            row = conn.execute('''
                SELECT b.*, t.name as leave_type_name,
                       (b.allocated_days + b.carried_over - b.used_days) as remaining_days
                FROM leave_balances b
                JOIN leave_types t ON b.leave_type_id = t.leave_type_id
                WHERE b.user_id = ? AND b.leave_type_id = ? AND b.year = ?
            ''', (user_id, leave_type_id, current_year)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def allocate_balance(user_id: str, leave_type_id: int, year: int,
                         allocated_days: float, carried_over: float = 0) -> int:
        """Allocate leave balance for a user."""
        with transaction() as conn:
            # Check if balance exists
            existing = conn.execute('''
                SELECT balance_id FROM leave_balances
                WHERE user_id = ? AND leave_type_id = ? AND year = ?
            ''', (user_id, leave_type_id, year)).fetchone()

            if existing:
                conn.execute('''
                    UPDATE leave_balances
                    SET allocated_days = ?, carried_over = ?, updated_at = ?
                    WHERE balance_id = ?
                ''', (allocated_days, carried_over, datetime.now().isoformat(),
                      existing[0]))
                log_activity('update', 'leave_balance', user_id=user_id,
                            details={'balance_id': existing[0]})
                return existing[0]
            else:
                cursor = conn.execute('''
                    INSERT INTO leave_balances (
                        user_id, leave_type_id, year,
                        allocated_days, used_days, carried_over
                    ) VALUES (?, ?, ?, ?, 0, ?)
                ''', (user_id, leave_type_id, year, allocated_days, carried_over))
                balance_id = cursor.lastrowid
                log_activity('create', 'leave_balance', user_id=user_id,
                            details={'balance_id': balance_id})
                return balance_id

    @staticmethod
    def update_used_days(user_id: str, leave_type_id: int, year: int,
                         days_change: float) -> bool:
        """Update used days for a leave balance (add or subtract)."""
        with transaction() as conn:
            conn.execute('''
                UPDATE leave_balances
                SET used_days = used_days + ?, updated_at = ?
                WHERE user_id = ? AND leave_type_id = ? AND year = ?
            ''', (days_change, datetime.now().isoformat(),
                  user_id, leave_type_id, year))
            return True

    # ==================== LEAVE REQUESTS ====================

    @staticmethod
    def submit_request(user_id: str, leave_type_id: int, start_date: str,
                       end_date: str, **data) -> int:
        """Submit a new leave request."""
        # Calculate total days
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        total_days = (end - start).days + 1

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO leave_requests (
                    user_id, leave_type_id, start_date, end_date,
                    total_days, reason, document_path, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            ''', (
                user_id,
                leave_type_id,
                start_date,
                end_date,
                total_days,
                data.get('reason'),
                data.get('document_path'),
            ))
            request_id = cursor.lastrowid
            log_activity('create', 'leave_request', user_id=user_id,
                        details={'request_id': request_id, 'days': total_days})
            return request_id

    @staticmethod
    def get_request(request_id: int) -> Optional[Dict[str, Any]]:
        """Get a leave request by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT r.*, t.name as leave_type_name, t.color_code
                FROM leave_requests r
                JOIN leave_types t ON r.leave_type_id = t.leave_type_id
                WHERE r.request_id = ?
            ''', (request_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_requests(user_id: str, status: Optional[str] = None,
                     year: Optional[int] = None,
                     limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get leave requests for a user."""
        with get_connection() as conn:
            query = '''
                SELECT r.*, t.name as leave_type_name, t.color_code
                FROM leave_requests r
                JOIN leave_types t ON r.leave_type_id = t.leave_type_id
                WHERE r.user_id = ?
            '''
            params = [user_id]

            if status:
                query += ' AND r.status = ?'
                params.append(status)

            if year:
                query += " AND strftime('%Y', r.start_date) = ?"
                params.append(str(year))

            query += ' ORDER BY r.created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_pending_approvals(approver_id: str,
                              department: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get leave requests pending approval for a manager."""
        with get_connection() as conn:
            query = '''
                SELECT r.*, t.name as leave_type_name, t.color_code,
                       p.department, p.job_title,
                       u.first_name, u.last_name, u.email
                FROM leave_requests r
                JOIN leave_types t ON r.leave_type_id = t.leave_type_id
                LEFT JOIN staff_profiles p ON r.user_id = p.user_id
                LEFT JOIN users u ON r.user_id = u.id
                WHERE r.status = 'pending'
                  AND (p.manager_id = ? OR ? IN (
                      SELECT user_id FROM staff_profiles WHERE department = p.department
                      AND job_title LIKE '%Manager%'
                  ))
            '''
            params = [approver_id, approver_id]

            if department:
                query += ' AND p.department = ?'
                params.append(department)

            query += ' ORDER BY r.created_at'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def approve_request(request_id: int, approver_id: str,
                        recipient_email: str = "",
                        staff_name: str = "") -> bool:
        """Approve a leave request."""
        with transaction() as conn:
            # Get request details
            request = conn.execute('''
                SELECT user_id, leave_type_id, total_days, start_date
                FROM leave_requests WHERE request_id = ? AND status = 'pending'
            ''', (request_id,)).fetchone()

            if not request:
                return False

            user_id = request[0]
            leave_type_id = request[1]
            total_days = request[2]
            year = datetime.strptime(request[3], '%Y-%m-%d').year

            # Update request status
            conn.execute('''
                UPDATE leave_requests
                SET status = 'approved',
                    approved_by = ?,
                    approved_date = ?,
                    updated_at = ?
                WHERE request_id = ?
            ''', (approver_id, datetime.now().isoformat(),
                  datetime.now().isoformat(), request_id))

            # Update leave balance
            conn.execute('''
                UPDATE leave_balances
                SET used_days = used_days + ?, updated_at = ?
                WHERE user_id = ? AND leave_type_id = ? AND year = ?
            ''', (total_days, datetime.now().isoformat(),
                  user_id, leave_type_id, year))

            log_activity('approve', 'leave_request',
                        details={'request_id': request_id, 'approver': approver_id})
            try:
                from education_system.post_18.university_system.modules.services.integration_bus import (
                    publish_leave_decision,
                )
                end_row = conn.execute(
                    "SELECT start_date, end_date, leave_type_id FROM leave_requests "
                    "WHERE request_id = ?",
                    (request_id,),
                ).fetchone()
                if end_row:
                    publish_leave_decision(
                        user_id,
                        action="approved",
                        start_date=end_row[0],
                        end_date=end_row[1],
                        leave_type=str(end_row[2]) if end_row[2] is not None else None,
                        source="leave",
                    )
            except Exception:
                pass

            # Best-effort notification — pulls remaining balance + leave type name.
            try:
                detail = conn.execute(
                    """SELECT r.start_date, r.end_date, r.total_days,
                              COALESCE(lt.name, '') AS leave_type,
                              COALESCE(lb.allocated_days, 0) - COALESCE(lb.used_days, 0) AS remaining
                         FROM leave_requests r
                         LEFT JOIN leave_types    lt ON lt.leave_type_id = r.leave_type_id
                         LEFT JOIN leave_balances lb ON lb.user_id = r.user_id
                                                    AND lb.leave_type_id = r.leave_type_id
                                                    AND lb.year = ?
                        WHERE r.request_id = ?""",
                    (year, request_id),
                ).fetchone()
                if detail:
                    _send_staff_hr_email('leave_approved', recipient_email, {
                        'staff_id':        user_id,
                        'staff_name':      staff_name or user_id,
                        'request_id':      request_id,
                        'leave_type':      detail[3] or '(unspecified)',
                        'start_date':      detail[0],
                        'end_date':        detail[1],
                        'total_days':      detail[2],
                        'approver':        approver_id,
                        'approved_on':     datetime.now().date().isoformat(),
                        'remaining_days':  detail[4] if detail[4] is not None else '(see HR portal)',
                    })
            except Exception:
                logger.exception("leave-approval email dispatch failed rid=%s", request_id)
            return True

    @staticmethod
    def reject_request(request_id: int, approver_id: str, reason: str,
                       recipient_email: str = "",
                       staff_name: str = "") -> bool:
        """Reject a leave request."""
        with transaction() as conn:
            conn.execute('''
                UPDATE leave_requests
                SET status = 'rejected',
                    approved_by = ?,
                    approved_date = ?,
                    rejection_reason = ?,
                    updated_at = ?
                WHERE request_id = ? AND status = 'pending'
            ''', (approver_id, datetime.now().isoformat(), reason,
                  datetime.now().isoformat(), request_id))
            log_activity('reject', 'leave_request',
                        details={'request_id': request_id, 'approver': approver_id})

            try:
                detail = conn.execute(
                    """SELECT r.user_id, r.start_date, r.end_date, r.total_days,
                              COALESCE(lt.name, '') AS leave_type
                         FROM leave_requests r
                         LEFT JOIN leave_types lt ON lt.leave_type_id = r.leave_type_id
                        WHERE r.request_id = ?""",
                    (request_id,),
                ).fetchone()
                if detail:
                    _send_staff_hr_email('leave_rejected', recipient_email, {
                        'staff_id':         detail[0],
                        'staff_name':       staff_name or detail[0],
                        'request_id':       request_id,
                        'leave_type':       detail[4] or '(unspecified)',
                        'start_date':       detail[1],
                        'end_date':         detail[2],
                        'total_days':       detail[3],
                        'approver':         approver_id,
                        'approved_on':      datetime.now().date().isoformat(),
                        'rejection_reason': reason or '(no reason supplied)',
                    })
            except Exception:
                logger.exception("leave-rejection email dispatch failed rid=%s", request_id)
            return True

    @staticmethod
    def cancel_request(request_id: int, user_id: str) -> bool:
        """Cancel a leave request (only pending requests)."""
        with transaction() as conn:
            result = conn.execute('''
                UPDATE leave_requests
                SET status = 'cancelled', updated_at = ?
                WHERE request_id = ? AND user_id = ? AND status = 'pending'
            ''', (datetime.now().isoformat(), request_id, user_id))
            if result.rowcount > 0:
                log_activity('cancel', 'leave_request', user_id=user_id,
                            details={'request_id': request_id})
                return True
            return False

    # ==================== LEAVE CALENDAR ====================

    @staticmethod
    def get_calendar(department: Optional[str] = None,
                     month: Optional[int] = None,
                     year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get leave calendar for a department or all staff."""
        current_year = year or datetime.now().year
        current_month = month or datetime.now().month

        with get_connection() as conn:
            query = '''
                SELECT r.*, t.name as leave_type_name, t.color_code,
                       p.department, u.first_name, u.last_name
                FROM leave_requests r
                JOIN leave_types t ON r.leave_type_id = t.leave_type_id
                LEFT JOIN staff_profiles p ON r.user_id = p.user_id
                LEFT JOIN users u ON r.user_id = u.id
                WHERE r.status = 'approved'
                  AND (
                      (strftime('%Y', r.start_date) = ? AND strftime('%m', r.start_date) = ?)
                      OR (strftime('%Y', r.end_date) = ? AND strftime('%m', r.end_date) = ?)
                  )
            '''
            params = [str(current_year), f'{current_month:02d}',
                     str(current_year), f'{current_month:02d}']

            if department:
                query += ' AND p.department = ?'
                params.append(department)

            query += ' ORDER BY r.start_date'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def check_conflicts(user_id: str, start_date: str, end_date: str,
                        exclude_request_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Check for conflicting leave requests."""
        with get_connection() as conn:
            query = '''
                SELECT r.*, t.name as leave_type_name
                FROM leave_requests r
                JOIN leave_types t ON r.leave_type_id = t.leave_type_id
                WHERE r.user_id = ?
                  AND r.status IN ('pending', 'approved')
                  AND r.start_date <= ?
                  AND r.end_date >= ?
            '''
            params = [user_id, end_date, start_date]

            if exclude_request_id:
                query += ' AND r.request_id != ?'
                params.append(exclude_request_id)

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    # ==================== REPORTS ====================

    @staticmethod
    def get_leave_summary(department: Optional[str] = None,
                          year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get leave usage summary by department or overall."""
        current_year = year or datetime.now().year
        with get_connection() as conn:
            query = '''
                SELECT p.department,
                       t.name as leave_type,
                       SUM(b.allocated_days) as total_allocated,
                       SUM(b.used_days) as total_used,
                       SUM(b.allocated_days + b.carried_over - b.used_days) as total_remaining,
                       COUNT(DISTINCT b.user_id) as staff_count
                FROM leave_balances b
                JOIN leave_types t ON b.leave_type_id = t.leave_type_id
                -- b.user_id is stored as the numeric users.id, whereas
                -- staff_profiles.user_id keys on the username; bridge via users.
                LEFT JOIN users u
                    ON u.username = b.user_id OR CAST(u.id AS TEXT) = b.user_id
                LEFT JOIN staff_profiles p
                    ON p.user_id = b.user_id OR p.user_id = u.username
                WHERE b.year = ?
            '''
            params = [current_year]

            if department:
                query += ' AND p.department = ?'
                params.append(department)

            query += ' GROUP BY p.department, t.name ORDER BY p.department, t.name'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
