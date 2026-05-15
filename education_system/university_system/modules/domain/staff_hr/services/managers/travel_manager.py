"""
Travel & Conference Manager

Provides functionality for:
- Travel request management
- Itinerary planning
- Conference registration tracking
- Two-level approval workflow
- Travel expense linking
- Travel statistics and reporting
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import json

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608


class TravelManager:
    """Manager for travel requests and conference management."""

    # ==================== REQUEST LIFECYCLE ====================

    @staticmethod
    def create_request(user_id: str, purpose: str, destination: str,
                       departure_date: str, return_date: str,
                       estimated_budget: float = 0,
                       budget_breakdown_json: str = None,
                       funding_source: str = 'department',
                       justification: str = None,
                       department: str = None) -> int:
        """Create a travel request (draft)."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO travel_requests (
                    user_id, purpose, destination, departure_date, return_date,
                    estimated_budget, budget_breakdown_json, funding_source,
                    justification, department, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)
            ''', (
                user_id, purpose, destination, departure_date, return_date,
                estimated_budget, budget_breakdown_json, funding_source,
                justification, department,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            request_id = cursor.lastrowid
            log_activity('create', 'travel_request', details={
                'request_id': request_id, 'user_id': user_id,
                'destination': destination,
            })
            return request_id

    @staticmethod
    def get_request(request_id: int) -> Optional[Dict[str, Any]]:
        """Get a single request by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM travel_requests WHERE request_id = ?
            ''', (request_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_user_requests(user_id: str, status: str = None) -> List[Dict[str, Any]]:
        """Get requests for a user, optionally filtered by status."""
        with get_connection() as conn:
            query = '''
                SELECT * FROM travel_requests
                WHERE user_id = ?
            '''
            params = [user_id]

            if status:
                query += ' AND status = ?'
                params.append(status)

            query += ' ORDER BY departure_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_request(request_id: int, **data) -> None:
        """Update request fields. Only if status='draft'."""
        allowed_fields = {
            'purpose', 'destination', 'departure_date', 'return_date',
            'estimated_budget', 'budget_breakdown_json', 'funding_source',
            'justification',
        }

        with transaction() as conn:
            # Verify status is draft
            row = conn.execute('''
                SELECT status FROM travel_requests WHERE request_id = ?
            ''', (request_id,)).fetchone()

            if not row:
                raise ValueError(f"Travel request {request_id} not found")
            if row['status'] != 'draft':
                raise ValueError(
                    f"Cannot update request {request_id}: status is '{row['status']}', must be 'draft'"
                )

            fields = []
            values = []
            for key, value in data.items():
                if key in allowed_fields:
                    fields.append(validate_identifier(key, "column") + ' = ?')
                    values.append(value)

            if not fields:
                return

            fields.append('updated_at = ?')
            values.append(datetime.now().isoformat())
            values.append(request_id)

            conn.execute(
                'UPDATE travel_requests SET ' + ', '.join(fields) + ' WHERE request_id = ?',
                values)
            log_activity('update', 'travel_request', details={
                'request_id': request_id, 'updated_fields': list(data.keys()),
            })

    @staticmethod
    def submit_request(request_id: int, user_id: str) -> None:
        """Submit a draft request for approval."""
        with transaction() as conn:
            # Verify status is draft
            row = conn.execute('''
                SELECT status FROM travel_requests WHERE request_id = ?
            ''', (request_id,)).fetchone()

            if not row:
                raise ValueError(f"Travel request {request_id} not found")
            if row['status'] != 'draft':
                raise ValueError(
                    f"Cannot submit request {request_id}: status is '{row['status']}', must be 'draft'"
                )

            # Update status to pending_approval
            conn.execute('''
                UPDATE travel_requests
                SET status = 'pending_approval', updated_at = ?
                WHERE request_id = ?
            ''', (datetime.now().isoformat(), request_id))

            # Create approval records for two levels
            for level in ('line_manager', 'department_head'):
                conn.execute('''
                    INSERT INTO travel_approvals (
                        request_id, approval_level, status, created_at
                    ) VALUES (?, ?, 'pending', ?)
                ''', (request_id, level, datetime.now().isoformat()))

            log_activity('update', 'travel_request', details={
                'request_id': request_id, 'user_id': user_id,
                'action': 'submitted',
            })

    @staticmethod
    def cancel_request(request_id: int) -> None:
        """Cancel a request. Only if not already completed."""
        with transaction() as conn:
            row = conn.execute('''
                SELECT status FROM travel_requests WHERE request_id = ?
            ''', (request_id,)).fetchone()

            if not row:
                raise ValueError(f"Travel request {request_id} not found")
            if row['status'] == 'completed':
                raise ValueError(
                    f"Cannot cancel request {request_id}: already completed"
                )

            conn.execute('''
                UPDATE travel_requests
                SET status = 'cancelled', updated_at = ?
                WHERE request_id = ?
            ''', (datetime.now().isoformat(), request_id))

            log_activity('update', 'travel_request', details={
                'request_id': request_id, 'action': 'cancelled',
            })

    # ==================== ITINERARY MANAGEMENT ====================

    @staticmethod
    def add_itinerary_leg(request_id: int, leg_order: int,
                          transport_type: str = 'flight',
                          departure_location: str = None,
                          arrival_location: str = None,
                          departure_datetime: str = None,
                          arrival_datetime: str = None,
                          booking_reference: str = None,
                          carrier: str = None,
                          cost: float = 0,
                          notes: str = None) -> int:
        """Add a journey leg to a travel request."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO travel_itinerary (
                    request_id, leg_order, transport_type,
                    departure_location, arrival_location,
                    departure_datetime, arrival_datetime,
                    booking_reference, carrier, cost, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                request_id, leg_order, transport_type,
                departure_location, arrival_location,
                departure_datetime, arrival_datetime,
                booking_reference, carrier, cost, notes,
            ))
            leg_id = cursor.lastrowid
            log_activity('create', 'travel_itinerary', details={
                'leg_id': leg_id, 'request_id': request_id,
            })
            return leg_id

    @staticmethod
    def get_itinerary(request_id: int) -> List[Dict[str, Any]]:
        """Get itinerary legs for a request."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM travel_itinerary
                WHERE request_id = ?
                ORDER BY leg_order
            ''', (request_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_itinerary_leg(leg_id: int, **data) -> None:
        """Update an itinerary leg."""
        if not data:
            return

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('leg_id', 'request_id'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        values.append(leg_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE travel_itinerary SET ' + ', '.join(fields) + ' WHERE leg_id = ?',
                values)
            log_activity('update', 'travel_itinerary', details={
                'leg_id': leg_id, 'updated_fields': list(data.keys()),
            })

    @staticmethod
    def delete_itinerary_leg(leg_id: int) -> None:
        """Delete an itinerary leg."""
        with transaction() as conn:
            conn.execute('''
                DELETE FROM travel_itinerary WHERE leg_id = ?
            ''', (leg_id,))
            log_activity('delete', 'travel_itinerary', details={'leg_id': leg_id})

    # ==================== CONFERENCE MANAGEMENT ====================

    @staticmethod
    def register_conference(user_id: str, conference_name: str,
                            start_date: str, end_date: str,
                            travel_request_id: int = None,
                            conference_url: str = None,
                            location: str = None,
                            registration_fee: float = 0,
                            presentation_title: str = None,
                            presentation_type: str = None,
                            is_presenting: bool = False) -> int:
        """Register for a conference."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO conference_registrations (
                    user_id, conference_name, start_date, end_date,
                    travel_request_id, conference_url, location,
                    registration_fee, presentation_title,
                    presentation_type, is_presenting, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, conference_name, start_date, end_date,
                travel_request_id, conference_url, location,
                registration_fee, presentation_title,
                presentation_type, int(is_presenting),
                datetime.now().isoformat(),
            ))
            registration_id = cursor.lastrowid
            log_activity('create', 'conference_registration', details={
                'registration_id': registration_id, 'user_id': user_id,
                'conference_name': conference_name,
            })
            return registration_id

    @staticmethod
    def get_user_conferences(user_id: str) -> List[Dict[str, Any]]:
        """Get conferences for a user."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM conference_registrations
                WHERE user_id = ?
                ORDER BY start_date DESC
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_conference(registration_id: int) -> Optional[Dict[str, Any]]:
        """Get a single conference registration."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM conference_registrations
                WHERE registration_id = ?
            ''', (registration_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_conference(registration_id: int, **data) -> None:
        """Update conference registration details."""
        if not data:
            return

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('registration_id', 'created_at', 'user_id'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        values.append(registration_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE conference_registrations SET ' + ', '.join(fields)
                + ' WHERE registration_id = ?',
                values)
            log_activity('update', 'conference_registration', details={
                'registration_id': registration_id,
                'updated_fields': list(data.keys()),
            })

    # ==================== APPROVAL WORKFLOW ====================

    @staticmethod
    def approve_request(approval_id: int, approver_id: str,
                        comments: str = None) -> None:
        """Approve a travel request at one level."""
        with transaction() as conn:
            # Update this approval level
            conn.execute('''
                UPDATE travel_approvals
                SET status = 'approved', approver_id = ?, comments = ?,
                    reviewed_date = ?
                WHERE approval_id = ?
            ''', (approver_id, comments, datetime.now().isoformat(), approval_id))

            # Get the request_id for this approval
            row = conn.execute('''
                SELECT request_id FROM travel_approvals WHERE approval_id = ?
            ''', (approval_id,)).fetchone()

            if not row:
                raise ValueError(f"Travel approval {approval_id} not found")

            request_id = row['request_id']

            # Check if all levels are now approved
            pending = conn.execute('''
                SELECT COUNT(*) as cnt FROM travel_approvals
                WHERE request_id = ? AND status != 'approved'
            ''', (request_id,)).fetchone()

            if pending['cnt'] == 0:
                # All levels approved - update request status
                conn.execute('''
                    UPDATE travel_requests
                    SET status = 'approved', updated_at = ?
                    WHERE request_id = ?
                ''', (datetime.now().isoformat(), request_id))

            log_activity('update', 'travel_request', details={
                'request_id': request_id, 'approval_id': approval_id,
                'action': 'approved', 'approver': approver_id,
            })

    @staticmethod
    def reject_request(approval_id: int, approver_id: str,
                       comments: str = None) -> None:
        """Reject a travel request."""
        with transaction() as conn:
            # Update this approval level
            conn.execute('''
                UPDATE travel_approvals
                SET status = 'rejected', approver_id = ?, comments = ?,
                    reviewed_date = ?
                WHERE approval_id = ?
            ''', (approver_id, comments, datetime.now().isoformat(), approval_id))

            # Get the request_id for this approval
            row = conn.execute('''
                SELECT request_id FROM travel_approvals WHERE approval_id = ?
            ''', (approval_id,)).fetchone()

            if not row:
                raise ValueError(f"Travel approval {approval_id} not found")

            request_id = row['request_id']

            # Reject the entire request
            conn.execute('''
                UPDATE travel_requests
                SET status = 'rejected', updated_at = ?
                WHERE request_id = ?
            ''', (datetime.now().isoformat(), request_id))

            log_activity('update', 'travel_request', details={
                'request_id': request_id, 'approval_id': approval_id,
                'action': 'rejected', 'approver': approver_id,
            })

    @staticmethod
    def get_pending_approvals(approver_id: str = None) -> List[Dict[str, Any]]:
        """Get pending travel approvals."""
        with get_connection() as conn:
            query = '''
                SELECT ta.*, tr.user_id, tr.purpose, tr.destination,
                       tr.departure_date, tr.return_date, tr.estimated_budget,
                       tr.department
                FROM travel_approvals ta
                JOIN travel_requests tr ON ta.request_id = tr.request_id
                WHERE ta.status = 'pending'
            '''
            params = []

            if approver_id:
                query += ' AND ta.approver_id = ?'
                params.append(approver_id)

            query += ' ORDER BY tr.departure_date ASC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    # ==================== EXPENSE LINKING ====================

    @staticmethod
    def create_expense_from_travel(request_id: int, user_id: str) -> int:
        """Create an expense claim linked to a travel request."""
        with transaction() as conn:
            # Get travel request details
            row = conn.execute('''
                SELECT * FROM travel_requests WHERE request_id = ?
            ''', (request_id,)).fetchone()

            if not row:
                raise ValueError(f"Travel request {request_id} not found")

            request_data = dict(row)

            # Try to call ExpenseManager.create_claim()
            try:
                from education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.expense_manager import (
                    ExpenseManager,
                )
                claim_id = ExpenseManager.create_claim(
                    user_id,
                    description=f"Travel: {request_data['purpose']} - {request_data['destination']}",
                    amount=request_data['estimated_budget'],
                    expense_date=request_data['departure_date'],
                    status='draft',
                    notes=f"Auto-created from travel request #{request_id}",
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Could not create expense claim: ExpenseManager not available ({exc})"
                ) from exc

            # Link expense claim to travel request
            conn.execute('''
                INSERT INTO travel_expenses (request_id, claim_id, created_at)
                VALUES (?, ?, ?)
            ''', (request_id, claim_id, datetime.now().isoformat()))

            log_activity('create', 'travel_expense', details={
                'request_id': request_id, 'claim_id': claim_id,
            })
            return claim_id

    @staticmethod
    def get_travel_expenses(request_id: int) -> List[Dict[str, Any]]:
        """Get linked expense claims for a travel request."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT te.*, ec.user_id, ec.amount, ec.currency,
                       ec.description, ec.status as claim_status,
                       ec.expense_date
                FROM travel_expenses te
                JOIN expense_claims ec ON te.claim_id = ec.claim_id
                WHERE te.request_id = ?
                ORDER BY ec.expense_date
            ''', (request_id,)).fetchall()
            return [dict(row) for row in rows]

    # ==================== REPORTING ====================

    @staticmethod
    def get_travel_statistics(department: str = None,
                              year: int = None) -> Dict[str, Any]:
        """Get travel statistics."""
        with get_connection() as conn:
            where_clause = '1=1'
            params: list = []

            if department:
                where_clause += ' AND department = ?'
                params.append(department)

            if year:
                where_clause += ' AND departure_date LIKE ?'
                params.append(f'{year}-%')

            # Total requests and budget
            row = conn.execute(
                'SELECT COUNT(*) as total_requests,'
                ' SUM(estimated_budget) as total_budget'
                ' FROM travel_requests WHERE ' + where_clause,
                params).fetchone()

            stats: Dict[str, Any] = {
                'total_requests': row['total_requests'] or 0,
                'total_budget': row['total_budget'] or 0,
            }

            # By status
            rows = conn.execute(
                'SELECT status, COUNT(*) as count'
                ' FROM travel_requests WHERE ' + where_clause
                + ' GROUP BY status',
                params).fetchall()
            stats['by_status'] = {r['status']: r['count'] for r in rows}

            # By funding source
            rows = conn.execute(
                'SELECT funding_source, COUNT(*) as count'
                ' FROM travel_requests WHERE ' + where_clause
                + ' GROUP BY funding_source',
                params).fetchall()
            stats['by_funding'] = {r['funding_source']: r['count'] for r in rows}

            # By department
            rows = conn.execute(
                'SELECT department, COUNT(*) as count,'
                ' SUM(estimated_budget) as budget'
                ' FROM travel_requests WHERE ' + where_clause
                + ' GROUP BY department',
                params).fetchall()
            stats['by_department'] = {
                r['department']: {'count': r['count'], 'budget': r['budget'] or 0}
                for r in rows if r['department']
            }

            return stats
