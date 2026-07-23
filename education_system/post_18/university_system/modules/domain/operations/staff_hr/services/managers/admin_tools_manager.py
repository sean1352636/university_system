"""
Admin Tools Manager

Handles document approvals, interdepartmental requests,
access cards, key assignments, and visitor management.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction

try:
    from education_system.post_18.university_system.core.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


class AdminToolsManager:
    """Manager for administrative tools and workflows."""

    # ==================== DOCUMENT APPROVALS ====================

    @staticmethod
    def get_pending_approvals(approver_id: str) -> List[Dict[str, Any]]:
        """Get documents pending approval for a user."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM document_approvals
                WHERE status = 'pending' AND current_approver = ?
                ORDER BY submitted_date
            ''', (approver_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def submit_document(submitted_by: str, document_type: str,
                        document_title: str, **data) -> int:
        """Submit a document for approval."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO document_approvals (
                    document_type, document_title, document_description,
                    document_path, submitted_by, submitted_by_name,
                    current_approver, approval_chain, total_steps
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (document_type, document_title, data.get('document_description'),
                  data.get('document_path'), submitted_by,
                  data.get('submitted_by_name'), data.get('current_approver'),
                  data.get('approval_chain'), data.get('total_steps', 1)))
            approval_id = cursor.lastrowid
            log_activity('submit', 'document_approval', details={
                'approval_id': approval_id
            })
            return approval_id

    @staticmethod
    def approve_document(approval_id: int, approver_id: str,
                         comments: Optional[str] = None) -> bool:
        """Approve a document."""
        with transaction() as conn:
            # Get current approval info
            approval = conn.execute('''
                SELECT current_step, total_steps, approval_chain
                FROM document_approvals WHERE approval_id = ?
            ''', (approval_id,)).fetchone()

            if not approval:
                return False

            current_step = approval[0]
            total_steps = approval[1]

            # Record in history
            conn.execute('''
                INSERT INTO document_approval_history (
                    approval_id, approver_id, action, step_number, comments
                ) VALUES (?, ?, 'approved', ?, ?)
            ''', (approval_id, approver_id, current_step, comments))

            if current_step >= total_steps:
                # Final approval
                conn.execute('''
                    UPDATE document_approvals
                    SET status = 'approved', completed_date = ?, comments = ?
                    WHERE approval_id = ?
                ''', (datetime.now().isoformat(), comments, approval_id))
            else:
                # Move to next step
                conn.execute('''
                    UPDATE document_approvals
                    SET current_step = current_step + 1
                    WHERE approval_id = ?
                ''', (approval_id,))

            return True

    @staticmethod
    def reject_document(approval_id: int, approver_id: str,
                        reason: str) -> bool:
        """Reject a document."""
        with transaction() as conn:
            conn.execute('''
                UPDATE document_approvals
                SET status = 'rejected', comments = ?, completed_date = ?
                WHERE approval_id = ?
            ''', (reason, datetime.now().isoformat(), approval_id))

            conn.execute('''
                INSERT INTO document_approval_history (
                    approval_id, approver_id, action, comments
                ) VALUES (?, ?, 'rejected', ?)
            ''', (approval_id, approver_id, reason))

            return True

    @staticmethod
    def get_approval_history(approval_id: int) -> List[Dict[str, Any]]:
        """Get approval history for a document."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM document_approval_history
                WHERE approval_id = ? ORDER BY action_date
            ''', (approval_id,)).fetchall()
            return [dict(row) for row in rows]

    # ==================== INTERDEPARTMENTAL REQUESTS ====================

    @staticmethod
    def get_interdept_requests(status: Optional[str] = None,
                               department: Optional[str] = None,
                               limit: int = 50) -> List[Dict[str, Any]]:
        """Get interdepartmental requests."""
        with get_connection() as conn:
            query = 'SELECT * FROM interdepartmental_requests WHERE 1=1'
            params = []
            if status:
                query += ' AND status = ?'
                params.append(status)
            if department:
                query += ' AND (from_department = ? OR to_department = ?)'
                params.extend([department, department])
            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_request(requested_by: str, request_type: str,
                       request_title: str, to_department: str,
                       **data) -> int:
        """Create an interdepartmental request."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO interdepartmental_requests (
                    request_type, from_department, to_department,
                    requested_by, requested_by_name, request_title,
                    request_description, priority, due_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (request_type, data.get('from_department'), to_department,
                  requested_by, data.get('requested_by_name'), request_title,
                  data.get('request_description'),
                  data.get('priority', 'normal'), data.get('due_date')))
            return cursor.lastrowid

    @staticmethod
    def assign_request(request_id: int, assigned_to: str,
                       assigned_to_name: Optional[str] = None) -> bool:
        """Assign a request to someone."""
        with transaction() as conn:
            conn.execute('''
                UPDATE interdepartmental_requests
                SET assigned_to = ?, assigned_to_name = ?,
                    status = 'in_progress', updated_at = ?
                WHERE request_id = ?
            ''', (assigned_to, assigned_to_name,
                  datetime.now().isoformat(), request_id))
            return True

    @staticmethod
    def complete_request(request_id: int, response: str) -> bool:
        """Complete a request with response."""
        with transaction() as conn:
            conn.execute('''
                UPDATE interdepartmental_requests
                SET status = 'completed', response = ?,
                    completed_date = ?, updated_at = ?
                WHERE request_id = ?
            ''', (response, datetime.now().isoformat(),
                  datetime.now().isoformat(), request_id))
            return True

    # ==================== ACCESS CARDS ====================

    @staticmethod
    def get_access_cards(user_id: Optional[str] = None,
                         status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get access card assignments."""
        with get_connection() as conn:
            query = 'SELECT * FROM access_cards WHERE 1=1'
            params = []
            if user_id:
                query += ' AND user_id = ?'
                params.append(user_id)
            if status:
                query += ' AND status = ?'
                params.append(status)
            query += ' ORDER BY issue_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def issue_access_card(card_number: str, user_id: str,
                          issued_by: str, **data) -> int:
        """Issue an access card."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO access_cards (
                    card_number, user_id, user_name, card_type,
                    access_level, buildings_access, issue_date,
                    expiry_date, issued_by, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (card_number, user_id, data.get('user_name'),
                  data.get('card_type', 'staff'), data.get('access_level'),
                  data.get('buildings_access'),
                  data.get('issue_date', datetime.now().strftime('%Y-%m-%d')),
                  data.get('expiry_date'), issued_by, data.get('notes')))
            log_activity('issue', 'access_card', user_id=user_id,
                        details={'card_number': card_number})
            return cursor.lastrowid

    @staticmethod
    def deactivate_access_card(card_id: int, reason: Optional[str] = None) -> bool:
        """Deactivate an access card."""
        with transaction() as conn:
            conn.execute('''
                UPDATE access_cards
                SET status = 'inactive', notes = COALESCE(notes || ' | ', '') || ?
                WHERE card_id = ?
            ''', (f'Deactivated: {reason}' if reason else 'Deactivated', card_id))
            return True

    # ==================== KEY ASSIGNMENTS ====================

    @staticmethod
    def get_key_assignments(user_id: Optional[str] = None,
                            status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get key assignments."""
        with get_connection() as conn:
            query = 'SELECT * FROM key_assignments WHERE 1=1'
            params = []
            if user_id:
                query += ' AND assigned_to = ?'
                params.append(user_id)
            if status:
                query += ' AND status = ?'
                params.append(status)
            query += ' ORDER BY assigned_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def assign_key(key_number: str, user_id: str, issued_by: str,
                   **data) -> int:
        """Assign a key to a user."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO key_assignments (
                    key_number, key_type, room_location, building,
                    assigned_to, assigned_to_name, assigned_date,
                    issued_by, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (key_number, data.get('key_type'), data.get('room_location'),
                  data.get('building'), user_id, data.get('assigned_to_name'),
                  datetime.now().strftime('%Y-%m-%d'), issued_by,
                  data.get('notes')))
            log_activity('assign', 'key', user_id=user_id,
                        details={'key_number': key_number})
            return cursor.lastrowid

    @staticmethod
    def return_key(assignment_id: int) -> bool:
        """Record key return."""
        with transaction() as conn:
            conn.execute('''
                UPDATE key_assignments
                SET status = 'returned', return_date = ?
                WHERE assignment_id = ?
            ''', (datetime.now().strftime('%Y-%m-%d'), assignment_id))
            return True

    # ==================== VISITOR MANAGEMENT ====================

    @staticmethod
    def get_visitor_registrations(date: Optional[str] = None,
                                  host_id: Optional[str] = None,
                                  status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get visitor registrations."""
        with get_connection() as conn:
            query = 'SELECT * FROM visitor_registrations WHERE 1=1'
            params = []
            if date:
                query += ' AND scheduled_date = ?'
                params.append(date)
            if host_id:
                query += ' AND host_id = ?'
                params.append(host_id)
            if status:
                query += ' AND status = ?'
                params.append(status)
            query += ' ORDER BY scheduled_date DESC, scheduled_time'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def register_visitor(host_id: str, visitor_name: str,
                         scheduled_date: str, **data) -> int:
        """Register a visitor."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO visitor_registrations (
                    visitor_name, visitor_email, visitor_phone,
                    visitor_company, host_id, host_name, host_department,
                    visit_purpose, scheduled_date, scheduled_time,
                    vehicle_registration, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (visitor_name, data.get('visitor_email'),
                  data.get('visitor_phone'), data.get('visitor_company'),
                  host_id, data.get('host_name'), data.get('host_department'),
                  data.get('visit_purpose'), scheduled_date,
                  data.get('scheduled_time'), data.get('vehicle_registration'),
                  data.get('notes')))
            return cursor.lastrowid

    @staticmethod
    def check_in_visitor(visitor_id: int,
                         badge_number: Optional[str] = None) -> bool:
        """Check in a visitor."""
        with transaction() as conn:
            conn.execute('''
                UPDATE visitor_registrations
                SET status = 'checked_in', check_in_time = ?, badge_number = ?
                WHERE visitor_id = ?
            ''', (datetime.now().strftime('%H:%M:%S'), badge_number, visitor_id))
            return True

    @staticmethod
    def check_out_visitor(visitor_id: int) -> bool:
        """Check out a visitor."""
        with transaction() as conn:
            conn.execute('''
                UPDATE visitor_registrations
                SET status = 'checked_out', check_out_time = ?
                WHERE visitor_id = ?
            ''', (datetime.now().strftime('%H:%M:%S'), visitor_id))
            return True

    @staticmethod
    def get_todays_visitors(host_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get today's visitors."""
        today = datetime.now().strftime('%Y-%m-%d')
        with get_connection() as conn:
            query = '''
                SELECT * FROM visitor_registrations
                WHERE scheduled_date = ?
            '''
            params = [today]
            if host_id:
                query += ' AND host_id = ?'
                params.append(host_id)
            query += ' ORDER BY scheduled_time'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
