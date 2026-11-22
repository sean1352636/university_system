"""
Admin Tools Manager

Handles document approvals, interdepartmental requests,
access cards, key assignments, and visitor management.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers import (
    _people as people,
)

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
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
    def get_pending_document_approvals(approver_id: str) -> List[Dict[str, Any]]:
        """Documents waiting on this person, or on nobody in particular,
        oldest first. Never their own: nobody approves what they submitted."""
        with get_connection() as conn:
            approver = people.key(approver_id, conn)
            rows = conn.execute('''
                SELECT *, document_title AS document_name,
                       COALESCE(submitted_by_name, submitted_by) AS submitter_name
                FROM document_approvals
                WHERE status IN ('pending', 'in_review') AND submitted_by <> ?
                  AND (current_approver = ? OR COALESCE(current_approver, '') = '')
                ORDER BY submitted_date
            ''', (approver, approver)).fetchall()
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
    def submit_request(requested_by: str, request_type: str, target_department: str,
                       description: Optional[str] = None, priority: str = 'normal',
                       title: Optional[str] = None) -> int:
        """A member of staff asks another department for something. The title
        defaults to the first line of the description, and the asking
        department comes from their staff profile."""
        with get_connection() as conn:
            person = people.key(requested_by, conn)
            profile = conn.execute('SELECT department FROM staff_profiles WHERE user_id = ?',
                                   (person,)).fetchone()
            name = access.display_name(person, conn)
        text = str(description or '').strip()
        return AdminToolsManager.create_request(
            person, request_type,
            str(title or '').strip() or (text.splitlines()[0][:80] if text else request_type),
            target_department,
            from_department=profile[0] if profile else None,
            requested_by_name=name, request_description=text or None,
            priority='normal' if priority in (None, '', 'medium') else priority)

    @staticmethod
    def get_user_requests(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """The requests a person has made, newest first."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT *, to_department AS target_department, created_at AS submitted_date
                FROM interdepartmental_requests
                WHERE requested_by = ?
                ORDER BY created_at DESC LIMIT ?
            ''', (people.key(user_id, conn), limit)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def _may_decide_request(conn, row, who: dict) -> bool:
        """The department asked or whoever it is assigned to decides a
        request, or HR. Never the person who asked."""
        name = who['username']
        if row['requested_by'] == name:
            return False
        if row['assigned_to'] == name or access.is_hr(who, conn):
            return True
        mine = conn.execute('SELECT department FROM staff_profiles WHERE user_id = ?',
                            (name,)).fetchone()
        return bool(mine and mine[0] and mine[0] == row['to_department'])

    @staticmethod
    def get_pending_requests(user_id: str) -> List[Dict[str, Any]]:
        """Pending requests this person may decide, oldest first."""
        with get_connection() as conn:
            who = people.decider(None, user_id, conn)
            rows = conn.execute('''
                SELECT *, COALESCE(requested_by_name, requested_by) AS requester_name
                FROM interdepartmental_requests
                WHERE status = 'pending'
                ORDER BY created_at
            ''').fetchall()
            return [dict(row) for row in rows
                    if AdminToolsManager._may_decide_request(conn, row, who)]

    @staticmethod
    def _pending_request_for(conn, request_id: int, user_id: str) -> Optional[dict]:
        """The decider, when this request is pending (None otherwise).
        PermissionError when they may not decide it."""
        who = people.decider(None, user_id, conn)
        row = conn.execute('SELECT * FROM interdepartmental_requests WHERE request_id = ?',
                           (request_id,)).fetchone()
        if not row or row['status'] != 'pending':
            return None
        if not AdminToolsManager._may_decide_request(conn, row, who):
            raise PermissionError("Only the department asked or HR can decide this request")
        return who

    @staticmethod
    def approve_request(request_id: int, user_id: str) -> bool:
        """Accept a pending request: it moves to in progress with the person
        accepting it. False when it is not pending."""
        with transaction() as conn:
            who = AdminToolsManager._pending_request_for(conn, request_id, user_id)
            if not who:
                return False
            conn.execute('''
                UPDATE interdepartmental_requests
                SET status = 'in_progress', assigned_to = ?, assigned_to_name = ?, updated_at = ?
                WHERE request_id = ?
            ''', (who['username'], access.display_name(who['username'], conn),
                  datetime.now().isoformat(), request_id))
            return True

    @staticmethod
    def reject_request(request_id: int, user_id: str, reason: str) -> bool:
        """Turn down a pending request: it is cancelled with the reason as its
        response. False when it is not pending."""
        now = datetime.now().isoformat()
        with transaction() as conn:
            who = AdminToolsManager._pending_request_for(conn, request_id, user_id)
            if not who:
                return False
            conn.execute('''
                UPDATE interdepartmental_requests
                SET status = 'cancelled', response = ?, completed_date = ?, updated_at = ?
                WHERE request_id = ?
            ''', (f"Rejected by {who['username']}: {reason}" if reason
                  else f"Rejected by {who['username']}", now, now, request_id))
            return True

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

    @staticmethod
    def deactivate_card_by_number(card_number: str, reason: Optional[str] = None) -> bool:
        """Deactivate the access card with this number. False when no such card."""
        with get_connection() as conn:
            row = conn.execute('SELECT card_id FROM access_cards WHERE card_number = ?',
                               (card_number,)).fetchone()
        return AdminToolsManager.deactivate_access_card(row[0], reason) if row else False

    @staticmethod
    def report_lost_card(card_number: str, reported_by: Optional[str] = None) -> bool:
        """Mark an access card lost, which stops it working. False when no
        such card, or it was already reported."""
        note = f"Reported lost {datetime.now().strftime('%Y-%m-%d')}"
        if reported_by:
            note += f" by {reported_by}"
        with transaction() as conn:
            cur = conn.execute('''
                UPDATE access_cards
                SET status = 'lost', notes = COALESCE(notes || ' | ', '') || ?
                WHERE card_number = ? AND status <> 'lost'
            ''', (note, card_number))
            if cur.rowcount:
                log_activity('update', 'access_card', details={'card_number': card_number,
                                                               'action': 'reported_lost'})
            return bool(cur.rowcount)

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
    def get_issued_keys() -> List[Dict[str, Any]]:
        """Every key currently out with someone, latest first."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT *, room_location AS location, assigned_date AS issued_date,
                       COALESCE(assigned_to_name, assigned_to) AS holder_name
                FROM key_assignments
                WHERE status = 'assigned'
                ORDER BY assigned_date DESC
            ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def issue_key(user_id: str, key_number: str, location: Optional[str] = None,
                  issued_by: Optional[str] = None, **data) -> int:
        """Hand a key to someone. One key can only be with one person, so a
        key still out with someone must come back first."""
        with get_connection() as conn:
            if conn.execute("SELECT 1 FROM key_assignments WHERE key_number = ? "
                            "AND status = 'assigned'", (key_number,)).fetchone():
                raise ValueError(f"Key {key_number} is already issued")
            holder = people.key(user_id, conn)
            name = access.display_name(holder, conn)
        return AdminToolsManager.assign_key(key_number, holder, issued_by,
                                            room_location=location, assigned_to_name=name,
                                            **data)

    @staticmethod
    def return_key_by_number(key_number: str) -> bool:
        """Record the return of a key that is out. False when it is not out."""
        with get_connection() as conn:
            row = conn.execute("SELECT assignment_id FROM key_assignments WHERE key_number = ? "
                               "AND status = 'assigned'", (key_number,)).fetchone()
        return AdminToolsManager.return_key(row[0]) if row else False

    @staticmethod
    def report_lost_key(key_number: str, reported_by: Optional[str] = None) -> bool:
        """Mark a key that is out as lost. False when it is not out."""
        note = f"Reported lost {datetime.now().strftime('%Y-%m-%d')}"
        if reported_by:
            note += f" by {reported_by}"
        with transaction() as conn:
            cur = conn.execute('''
                UPDATE key_assignments
                SET status = 'lost', notes = COALESCE(notes || ' | ', '') || ?
                WHERE key_number = ? AND status = 'assigned'
            ''', (note, key_number))
            if cur.rowcount:
                log_activity('update', 'key', details={'key_number': key_number,
                                                       'action': 'reported_lost'})
            return bool(cur.rowcount)

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
    def find_visitor(reference: str) -> Optional[int]:
        """The visitor a registration number or a name refers to: a name means
        one of today's visitors. None when nobody matches; ValueError when a
        name matches more than one."""
        text = str(reference or '').strip()
        if not text:
            return None
        with get_connection() as conn:
            if text.isdigit():
                row = conn.execute('SELECT visitor_id FROM visitor_registrations '
                                   'WHERE visitor_id = ?', (int(text),)).fetchone()
                return row[0] if row else None
            rows = conn.execute('''
                SELECT visitor_id FROM visitor_registrations
                WHERE scheduled_date = ? AND LOWER(visitor_name) = LOWER(?)
            ''', (datetime.now().strftime('%Y-%m-%d'), text)).fetchall()
        if len(rows) > 1:
            raise ValueError(f"More than one visitor today is called {text}; use the ID")
        return rows[0][0] if rows else None

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
