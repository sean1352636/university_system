"""
Grievance Manager - Grievance and disciplinary management.

Provides functionality for:
- File grievances (anonymous option)
- Disciplinary record tracking
- Investigation workflow
- Appeal process
- Confidential handling
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608


class GrievanceManager:
    """Manager for grievances and disciplinary records."""

    # ==================== GRIEVANCE CATEGORIES ====================

    @staticmethod
    def get_grievance_categories(active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all grievance categories."""
        with get_connection() as conn:
            if active_only:
                rows = conn.execute('''
                    SELECT * FROM grievance_categories WHERE is_active = 1 ORDER BY name
                ''').fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM grievance_categories ORDER BY name
                ''').fetchall()
            return [dict(row) for row in rows]

    # ==================== GRIEVANCE CRUD ====================

    @staticmethod
    def _generate_reference(prefix: str = 'GRV') -> str:
        """Generate a unique reference number."""
        timestamp = datetime.now().strftime('%Y%m%d')
        unique_id = str(uuid.uuid4())[:6].upper()
        return f'{prefix}-{timestamp}-{unique_id}'

    @staticmethod
    def create_grievance(complainant_id: str, **data) -> int:
        """Create a new grievance."""
        with transaction() as conn:
            reference = GrievanceManager._generate_reference('GRV')

            # Support category name string (from CLI) or category_id
            category_id = data.get('category_id')
            category_other = data.get('category_other')

            if not category_id and data.get('category'):
                # Try to find category by name
                row = conn.execute('''
                    SELECT category_id FROM grievance_categories WHERE name = ?
                ''', (data['category'],)).fetchone()
                if row:
                    category_id = row['category_id']
                else:
                    category_other = data['category']

            # Use description as subject if subject not provided
            subject = data.get('subject') or (data.get('description', '')[:100] if data.get('description') else None)

            cursor = conn.execute('''
                INSERT INTO grievances (
                    reference_number, complainant_id, respondent_id, category_id,
                    category_other, subject, description, is_anonymous,
                    is_confidential, status, priority, assigned_to, filed_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                reference,
                complainant_id,
                data.get('respondent_id'),
                category_id,
                category_other,
                subject,
                data.get('description'),
                data.get('is_anonymous', False),
                data.get('is_confidential', True),
                'submitted',
                data.get('priority', 'normal'),
                data.get('assigned_to'),
                datetime.now().isoformat(),
            ))
            grievance_id = cursor.lastrowid

            # Create initial action record
            conn.execute('''
                INSERT INTO grievance_actions (
                    grievance_id, action_type, action_date, taken_by, details
                ) VALUES (?, 'submitted', ?, ?, 'Grievance submitted')
            ''', (grievance_id, datetime.now().isoformat(), complainant_id))

            log_activity('create', 'grievance', details={
                'grievance_id': grievance_id,
                'reference': reference,
                'is_anonymous': data.get('is_anonymous', False)
            })
            return grievance_id

    @staticmethod
    def get_grievance(grievance_id: int) -> Optional[Dict[str, Any]]:
        """Get a grievance by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT g.*, cat.name as category_name
                FROM grievances g
                LEFT JOIN grievance_categories cat ON g.category_id = cat.category_id
                WHERE g.grievance_id = ?
            ''', (grievance_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_grievance_by_reference(reference: str) -> Optional[Dict[str, Any]]:
        """Get a grievance by reference number."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT g.*, cat.name as category_name
                FROM grievances g
                LEFT JOIN grievance_categories cat ON g.category_id = cat.category_id
                WHERE g.reference_number = ?
            ''', (reference,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_user_grievances(user_id: str, as_complainant: bool = True) -> List[Dict[str, Any]]:
        """Get grievances for a user."""
        with get_connection() as conn:
            if as_complainant:
                rows = conn.execute('''
                    SELECT g.*, cat.name as category_name
                    FROM grievances g
                    LEFT JOIN grievance_categories cat ON g.category_id = cat.category_id
                    WHERE g.complainant_id = ?
                    ORDER BY g.filed_date DESC
                ''', (user_id,)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT g.*, cat.name as category_name
                    FROM grievances g
                    LEFT JOIN grievance_categories cat ON g.category_id = cat.category_id
                    WHERE g.respondent_id = ?
                    ORDER BY g.filed_date DESC
                ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_assigned_grievances(handler_id: str) -> List[Dict[str, Any]]:
        """Get grievances assigned to a handler."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT g.*, cat.name as category_name
                FROM grievances g
                LEFT JOIN grievance_categories cat ON g.category_id = cat.category_id
                WHERE g.assigned_to = ?
                AND g.status NOT IN ('resolved', 'closed', 'withdrawn')
                ORDER BY g.priority DESC, g.filed_date ASC
            ''', (handler_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_all_grievances(status: str = None, priority: str = None) -> List[Dict[str, Any]]:
        """Get all grievances with optional filters."""
        with get_connection() as conn:
            query = '''
                SELECT g.*, cat.name as category_name
                FROM grievances g
                LEFT JOIN grievance_categories cat ON g.category_id = cat.category_id
                WHERE 1=1
            '''
            params = []

            if status:
                query += ' AND g.status = ?'
                params.append(status)

            if priority:
                query += ' AND g.priority = ?'
                params.append(priority)

            query += ' ORDER BY g.filed_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_grievance(grievance_id: int, updated_by: str, **data) -> bool:
        """Update a grievance."""
        if not data:
            return False

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('grievance_id', 'created_at', 'complainant_id', 'reference_number'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return False

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(grievance_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE grievances SET ' + ', '.join(fields) + ' WHERE grievance_id = ?',
                values)

            log_activity('update', 'grievance', details={
                'grievance_id': grievance_id,
                'updated_by': updated_by,
                'updated_fields': list(data.keys())
            })
            return True

    # ==================== GRIEVANCE WORKFLOW ====================

    @staticmethod
    def assign_grievance(grievance_id: int, assigned_to: str, assigned_by: str) -> bool:
        """Assign a grievance to a handler."""
        with transaction() as conn:
            conn.execute('''
                UPDATE grievances
                SET assigned_to = ?, status = 'assigned', updated_at = ?
                WHERE grievance_id = ?
            ''', (assigned_to, datetime.now().isoformat(), grievance_id))

            conn.execute('''
                INSERT INTO grievance_actions (
                    grievance_id, action_type, action_date, taken_by, details
                ) VALUES (?, 'assigned', ?, ?, ?)
            ''', (grievance_id, datetime.now().isoformat(), assigned_by,
                  f'Assigned to {assigned_to}'))

            log_activity('update', 'grievance', details={
                'grievance_id': grievance_id, 'action': 'assigned', 'assigned_to': assigned_to
            })
            return True

    @staticmethod
    def acknowledge_grievance(grievance_id: int, acknowledged_by: str) -> bool:
        """Acknowledge receipt of a grievance."""
        with transaction() as conn:
            conn.execute('''
                UPDATE grievances
                SET status = 'acknowledged', acknowledged_date = ?, updated_at = ?
                WHERE grievance_id = ?
            ''', (datetime.now().isoformat(), datetime.now().isoformat(), grievance_id))

            conn.execute('''
                INSERT INTO grievance_actions (
                    grievance_id, action_type, action_date, taken_by, details
                ) VALUES (?, 'acknowledged', ?, ?, 'Grievance acknowledged')
            ''', (grievance_id, datetime.now().isoformat(), acknowledged_by))

            log_activity('update', 'grievance', details={
                'grievance_id': grievance_id, 'action': 'acknowledged'
            })
            return True

    @staticmethod
    def start_investigation(grievance_id: int, investigator_id: str) -> bool:
        """Start investigation on a grievance."""
        with transaction() as conn:
            conn.execute('''
                UPDATE grievances
                SET status = 'under_investigation', investigation_start_date = ?, updated_at = ?
                WHERE grievance_id = ?
            ''', (datetime.now().isoformat(), datetime.now().isoformat(), grievance_id))

            conn.execute('''
                INSERT INTO grievance_actions (
                    grievance_id, action_type, action_date, taken_by, details
                ) VALUES (?, 'investigation_started', ?, ?, 'Investigation commenced')
            ''', (grievance_id, datetime.now().isoformat(), investigator_id))

            log_activity('update', 'grievance', details={
                'grievance_id': grievance_id, 'action': 'investigation_started'
            })
            return True

    @staticmethod
    def resolve_grievance(grievance_id: int, resolver_id: str,
                         resolution_type: str, resolution_summary: str,
                         outcome: str) -> bool:
        """Resolve a grievance."""
        with transaction() as conn:
            # Calculate appeal deadline (usually 10 working days)
            appeal_deadline = (datetime.now() + timedelta(days=14)).isoformat()

            conn.execute('''
                UPDATE grievances
                SET status = 'resolved', resolution_date = ?, resolution_type = ?,
                    resolution_summary = ?, outcome = ?, appeal_deadline = ?, updated_at = ?
                WHERE grievance_id = ?
            ''', (datetime.now().isoformat(), resolution_type, resolution_summary,
                  outcome, appeal_deadline, datetime.now().isoformat(), grievance_id))

            conn.execute('''
                INSERT INTO grievance_actions (
                    grievance_id, action_type, action_date, taken_by, details, outcome
                ) VALUES (?, 'resolved', ?, ?, ?, ?)
            ''', (grievance_id, datetime.now().isoformat(), resolver_id,
                  resolution_summary, outcome))

            log_activity('update', 'grievance', details={
                'grievance_id': grievance_id, 'action': 'resolved', 'outcome': outcome
            })
            return True

    @staticmethod
    def withdraw_grievance(grievance_id: int, withdrawn_by: str, reason: str = None) -> bool:
        """Withdraw a grievance."""
        with transaction() as conn:
            conn.execute('''
                UPDATE grievances
                SET status = 'withdrawn', updated_at = ?
                WHERE grievance_id = ?
            ''', (datetime.now().isoformat(), grievance_id))

            conn.execute('''
                INSERT INTO grievance_actions (
                    grievance_id, action_type, action_date, taken_by, details
                ) VALUES (?, 'withdrawn', ?, ?, ?)
            ''', (grievance_id, datetime.now().isoformat(), withdrawn_by,
                  reason or 'Grievance withdrawn'))

            log_activity('update', 'grievance', details={
                'grievance_id': grievance_id, 'action': 'withdrawn'
            })
            return True

    # ==================== GRIEVANCE ACTIONS ====================

    @staticmethod
    def add_action(grievance_id: int, **data) -> int:
        """Add an action to a grievance."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO grievance_actions (
                    grievance_id, action_type, action_date, taken_by, details,
                    outcome, next_action, next_action_date, documents_path,
                    is_visible_to_complainant
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                grievance_id,
                data.get('action_type'),
                data.get('action_date', datetime.now().isoformat()),
                data.get('taken_by'),
                data.get('details'),
                data.get('outcome'),
                data.get('next_action'),
                data.get('next_action_date'),
                data.get('documents_path'),
                data.get('is_visible_to_complainant', True),
            ))
            action_id = cursor.lastrowid
            log_activity('create', 'grievance_action', details={
                'action_id': action_id, 'grievance_id': grievance_id
            })
            return action_id

    @staticmethod
    def get_grievance_actions(grievance_id: int,
                              visible_only: bool = False) -> List[Dict[str, Any]]:
        """Get all actions for a grievance."""
        with get_connection() as conn:
            if visible_only:
                rows = conn.execute('''
                    SELECT * FROM grievance_actions
                    WHERE grievance_id = ? AND is_visible_to_complainant = 1
                    ORDER BY action_date DESC
                ''', (grievance_id,)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM grievance_actions
                    WHERE grievance_id = ?
                    ORDER BY action_date DESC
                ''', (grievance_id,)).fetchall()
            return [dict(row) for row in rows]

    # ==================== GRIEVANCE MEETINGS ====================

    @staticmethod
    def schedule_meeting(grievance_id: int, **data) -> int:
        """Schedule a grievance meeting."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO grievance_meetings (
                    grievance_id, meeting_date, meeting_time, location,
                    attendees, purpose
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                grievance_id,
                data.get('meeting_date'),
                data.get('meeting_time'),
                data.get('location'),
                data.get('attendees'),
                data.get('purpose'),
            ))
            meeting_id = cursor.lastrowid
            log_activity('create', 'grievance_meeting', details={
                'meeting_id': meeting_id, 'grievance_id': grievance_id
            })
            return meeting_id

    @staticmethod
    def get_grievance_meetings(grievance_id: int) -> List[Dict[str, Any]]:
        """Get all meetings for a grievance."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM grievance_meetings
                WHERE grievance_id = ?
                ORDER BY meeting_date DESC
            ''', (grievance_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_meeting_minutes(meeting_id: int, minutes: str,
                               outcomes: str = None, follow_up: str = None) -> bool:
        """Update meeting minutes."""
        with transaction() as conn:
            conn.execute('''
                UPDATE grievance_meetings
                SET minutes = ?, outcomes = ?, follow_up_actions = ?
                WHERE meeting_id = ?
            ''', (minutes, outcomes, follow_up, meeting_id))
            log_activity('update', 'grievance_meeting', details={'meeting_id': meeting_id})
            return True

    # ==================== DISCIPLINARY RECORDS ====================

    @staticmethod
    def create_disciplinary_record(user_id: str, **data) -> int:
        """Create a disciplinary record."""
        with transaction() as conn:
            reference = GrievanceManager._generate_reference('DIS')

            cursor = conn.execute('''
                INSERT INTO disciplinary_records (
                    reference_number, user_id, offense_type, offense_category,
                    severity, description, date_occurred, date_reported,
                    reported_by, witnesses, evidence_path, status,
                    investigation_notes, is_confidential, previous_warnings
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                reference,
                user_id,
                data.get('offense_type'),
                data.get('offense_category'),
                data.get('severity', 'minor'),
                data.get('description'),
                data.get('date_occurred'),
                data.get('date_reported', datetime.now().isoformat()),
                data.get('reported_by'),
                data.get('witnesses'),
                data.get('evidence_path'),
                'under_review',
                data.get('investigation_notes'),
                data.get('is_confidential', True),
                data.get('previous_warnings', 0),
            ))
            record_id = cursor.lastrowid

            log_activity('create', 'disciplinary_record', details={
                'record_id': record_id, 'reference': reference
            })
            return record_id

    @staticmethod
    def get_disciplinary_record(record_id: int) -> Optional[Dict[str, Any]]:
        """Get a disciplinary record by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM disciplinary_records WHERE record_id = ?
            ''', (record_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_user_disciplinary_records(user_id: str) -> List[Dict[str, Any]]:
        """Get all disciplinary records for a user."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM disciplinary_records
                WHERE user_id = ?
                ORDER BY date_occurred DESC
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_user_disciplinary_history(user_id: str) -> List[Dict[str, Any]]:
        """Backwards-compatible alias for disciplinary history retrieval."""
        return GrievanceManager.get_user_disciplinary_records(user_id)

    @staticmethod
    def update_disciplinary_record(record_id: int, **data) -> bool:
        """Update a disciplinary record."""
        if not data:
            return False

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('record_id', 'created_at', 'user_id', 'reference_number'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return False

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(record_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE disciplinary_records SET ' + ', '.join(fields) + ' WHERE record_id = ?',
                values)
            log_activity('update', 'disciplinary_record', details={'record_id': record_id})
            return True

    # ==================== DISCIPLINARY ACTIONS ====================

    @staticmethod
    def create_disciplinary_action(record_id: int, **data) -> int:
        """Create a disciplinary action."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO disciplinary_actions (
                    record_id, action_type, action_level, effective_date,
                    end_date, duration_days, imposed_by, reason, conditions,
                    appeal_deadline, document_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record_id,
                data.get('action_type'),
                data.get('action_level'),
                data.get('effective_date'),
                data.get('end_date'),
                data.get('duration_days'),
                data.get('imposed_by'),
                data.get('reason'),
                data.get('conditions'),
                data.get('appeal_deadline'),
                data.get('document_path'),
            ))
            action_id = cursor.lastrowid

            # Update the record status
            conn.execute('''
                UPDATE disciplinary_records SET status = 'action_taken', updated_at = ?
                WHERE record_id = ?
            ''', (datetime.now().isoformat(), record_id))

            log_activity('create', 'disciplinary_action', details={
                'action_id': action_id, 'record_id': record_id
            })
            return action_id

    @staticmethod
    def get_disciplinary_actions(record_id: int) -> List[Dict[str, Any]]:
        """Get all actions for a disciplinary record."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM disciplinary_actions
                WHERE record_id = ?
                ORDER BY effective_date DESC
            ''', (record_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def acknowledge_disciplinary_action(action_id: int, acknowledged_date: str = None) -> bool:
        """Mark a disciplinary action as acknowledged by employee."""
        with transaction() as conn:
            conn.execute('''
                UPDATE disciplinary_actions
                SET acknowledged_by_employee = 1, acknowledged_date = ?
                WHERE action_id = ?
            ''', (acknowledged_date or datetime.now().isoformat(), action_id))
            log_activity('update', 'disciplinary_action', details={
                'action_id': action_id, 'action': 'acknowledged'
            })
            return True

    # ==================== APPEALS ====================

    @staticmethod
    def submit_appeal(action_id: int, appellant_id: str, grounds: str,
                     supporting_documents: str = None) -> int:
        """Submit an appeal against a disciplinary action."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO disciplinary_appeals (
                    action_id, appellant_id, appeal_date, grounds,
                    supporting_documents, status
                ) VALUES (?, ?, ?, ?, ?, 'submitted')
            ''', (action_id, appellant_id, datetime.now().isoformat(),
                  grounds, supporting_documents))
            appeal_id = cursor.lastrowid

            # Update the action
            conn.execute('''
                UPDATE disciplinary_actions SET appeal_submitted = 1
                WHERE action_id = ?
            ''', (action_id,))

            log_activity('create', 'disciplinary_appeal', details={
                'appeal_id': appeal_id, 'action_id': action_id
            })
            return appeal_id

    @staticmethod
    def file_appeal(action_id: int, appellant_id: str, grounds: str,
                    supporting_documents: str = None) -> int:
        """Backwards-compatible alias for submitting an appeal."""
        return GrievanceManager.submit_appeal(
            action_id, appellant_id, grounds, supporting_documents=supporting_documents
        )

    @staticmethod
    def get_appeal(appeal_id: int) -> Optional[Dict[str, Any]]:
        """Get an appeal by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM disciplinary_appeals WHERE appeal_id = ?
            ''', (appeal_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def process_appeal(appeal_id: int, outcome: str, outcome_details: str,
                      panel_members: str = None) -> bool:
        """Process and decide on an appeal."""
        with transaction() as conn:
            conn.execute('''
                UPDATE disciplinary_appeals
                SET status = 'decided', outcome = ?, outcome_details = ?,
                    outcome_date = ?, panel_members = ?
                WHERE appeal_id = ?
            ''', (outcome, outcome_details, datetime.now().isoformat(),
                  panel_members, appeal_id))

            # Get the action_id
            row = conn.execute('''
                SELECT action_id FROM disciplinary_appeals WHERE appeal_id = ?
            ''', (appeal_id,)).fetchone()

            if row:
                conn.execute('''
                    UPDATE disciplinary_actions SET appeal_outcome = ?
                    WHERE action_id = ?
                ''', (outcome, row['action_id']))

            log_activity('update', 'disciplinary_appeal', details={
                'appeal_id': appeal_id, 'outcome': outcome
            })
            return True

    # ==================== STATISTICS ====================

    @staticmethod
    def get_grievance_statistics() -> Dict[str, Any]:
        """Get grievance statistics."""
        with get_connection() as conn:
            stats = {}

            # Total grievances
            row = conn.execute('''
                SELECT COUNT(*) as count FROM grievances
            ''').fetchone()
            stats['total'] = row['count'] if row else 0

            # By status
            rows = conn.execute('''
                SELECT status, COUNT(*) as count FROM grievances
                GROUP BY status
            ''').fetchall()
            stats['by_status'] = {row['status']: row['count'] for row in rows}

            # By category
            rows = conn.execute('''
                SELECT cat.name, COUNT(*) as count
                FROM grievances g
                JOIN grievance_categories cat ON g.category_id = cat.category_id
                GROUP BY cat.name
            ''').fetchall()
            stats['by_category'] = {row['name']: row['count'] for row in rows}

            # Open grievances
            row = conn.execute('''
                SELECT COUNT(*) as count FROM grievances
                WHERE status NOT IN ('resolved', 'closed', 'withdrawn')
            ''').fetchone()
            stats['open'] = row['count'] if row else 0

            return stats

    @staticmethod
    def get_disciplinary_statistics() -> Dict[str, Any]:
        """Get disciplinary statistics."""
        with get_connection() as conn:
            stats = {}

            # Total records
            row = conn.execute('''
                SELECT COUNT(*) as count FROM disciplinary_records
            ''').fetchone()
            stats['total'] = row['count'] if row else 0

            # By severity
            rows = conn.execute('''
                SELECT severity, COUNT(*) as count FROM disciplinary_records
                GROUP BY severity
            ''').fetchall()
            stats['by_severity'] = {row['severity']: row['count'] for row in rows}

            # By status
            rows = conn.execute('''
                SELECT status, COUNT(*) as count FROM disciplinary_records
                GROUP BY status
            ''').fetchall()
            stats['by_status'] = {row['status']: row['count'] for row in rows}

            return stats

    # ==================== ADDITIONAL METHODS FOR CLI COMPATIBILITY ====================

    @staticmethod
    def get_all_categories() -> List[Dict[str, Any]]:
        """Get all grievance categories (alias)."""
        return GrievanceManager.get_grievance_categories(active_only=False)

    @staticmethod
    def search_grievances(status: str = None, priority: str = None,
                         category: str = None, from_date: str = None,
                         to_date: str = None) -> List[Dict[str, Any]]:
        """Search grievances with filters."""
        with get_connection() as conn:
            query = '''
                SELECT g.*, cat.name as category_name
                FROM grievances g
                LEFT JOIN grievance_categories cat ON g.category_id = cat.category_id
                WHERE 1=1
            '''
            params = []

            if status == 'active':
                query += " AND g.status NOT IN ('resolved', 'closed', 'withdrawn')"
            elif status:
                query += ' AND g.status = ?'
                params.append(status)

            if priority:
                query += ' AND g.priority = ?'
                params.append(priority)

            if category:
                query += ' AND cat.name = ?'
                params.append(category)

            if from_date:
                query += ' AND g.filed_date >= ?'
                params.append(from_date)

            if to_date:
                query += ' AND g.filed_date <= ?'
                params.append(to_date)

            query += ' ORDER BY g.filed_date DESC'
            rows = conn.execute(query, params).fetchall()

            # Add aliases for CLI compatibility
            result = []
            for row in rows:
                item = dict(row)
                item['category'] = item.get('category_name') or item.get('category_other')
                result.append(item)
            return result

    @staticmethod
    def create_action(grievance_id: int, action_type: str, **data) -> int:
        """Create a grievance action (alias for add_action)."""
        return GrievanceManager.add_action(
            grievance_id,
            action_type=action_type,
            **data
        )

    @staticmethod
    def escalate_grievance(grievance_id: int, reason: str, escalated_by: str) -> bool:
        """Escalate a grievance."""
        with transaction() as conn:
            conn.execute('''
                UPDATE grievances
                SET status = 'escalated', priority = 'high', updated_at = ?
                WHERE grievance_id = ?
            ''', (datetime.now().isoformat(), grievance_id))

            conn.execute('''
                INSERT INTO grievance_actions (
                    grievance_id, action_type, action_date, taken_by, details
                ) VALUES (?, 'escalated', ?, ?, ?)
            ''', (grievance_id, datetime.now().isoformat(), escalated_by,
                  f'Grievance escalated: {reason}'))

            log_activity('update', 'grievance', details={
                'grievance_id': grievance_id, 'action': 'escalated'
            })
            return True

    @staticmethod
    def create_meeting(grievance_id: int, **data) -> int:
        """Create a grievance meeting (alias for schedule_meeting)."""
        return GrievanceManager.schedule_meeting(
            grievance_id,
            meeting_date=data.get('scheduled_date'),
            meeting_time=data.get('scheduled_time'),
            location=data.get('location'),
            attendees=data.get('attendees'),
            purpose=data.get('meeting_type') or data.get('notes'),
        )

    @staticmethod
    def search_disciplinary_records(offense_type: str = None, severity: str = None,
                                    status: str = None, start_date: str = None,
                                    end_date: str = None) -> List[Dict[str, Any]]:
        """Search disciplinary records with filters."""
        with get_connection() as conn:
            query = 'SELECT * FROM disciplinary_records WHERE 1=1'
            params = []

            if offense_type:
                query += ' AND offense_type = ?'
                params.append(offense_type)

            if severity:
                query += ' AND severity = ?'
                params.append(severity)

            if status:
                query += ' AND status = ?'
                params.append(status)

            if start_date:
                query += ' AND date_occurred >= ?'
                params.append(start_date)

            if end_date:
                query += ' AND date_occurred <= ?'
                params.append(end_date)

            query += ' ORDER BY date_occurred DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_pending_appeals() -> List[Dict[str, Any]]:
        """Get all pending disciplinary appeals."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT a.*, da.action_type, dr.user_id, dr.offense_type
                FROM disciplinary_appeals a
                JOIN disciplinary_actions da ON a.action_id = da.action_id
                JOIN disciplinary_records dr ON da.record_id = dr.record_id
                WHERE a.status = 'submitted'
                ORDER BY a.appeal_date ASC
            ''').fetchall()

            result = []
            for row in rows:
                item = dict(row)
                item['filed_date'] = item.get('appeal_date')
                item['appeal_reason'] = item.get('grounds')
                result.append(item)
            return result

    @staticmethod
    def resolve_appeal(appeal_id: int, outcome: str, decision_notes: str,
                       decided_by: str) -> bool:
        """Resolve an appeal (alias for process_appeal)."""
        return GrievanceManager.process_appeal(
            appeal_id, outcome, decision_notes, panel_members=decided_by
        )
