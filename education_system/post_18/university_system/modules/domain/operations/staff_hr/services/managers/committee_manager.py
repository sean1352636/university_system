"""
Committee & Meeting Manager

Provides functionality for:
- Committee creation and membership management
- Meeting scheduling and lifecycle
- Agenda item management and reordering
- Meeting minutes recording and approval
- Voting with simple majority, two-thirds, and unanimous modes
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity
from education_system.post_18.university_system.core.sql_safety import validate_identifier  # nosec B608


class CommitteeManager:
    """Manager for committees, meetings, agendas, minutes, and voting."""

    # ==================== COMMITTEE MANAGEMENT ====================

    @staticmethod
    def create_committee(name: str, description: str, committee_type: str,
                         chair_id: str, department: str,
                         created_by: str) -> int:
        """Create a new committee.

        Args:
            name: Committee name.
            description: Purpose or description of the committee.
            committee_type: Type of committee (e.g. 'standing', 'ad_hoc').
            chair_id: User ID of the committee chair.
            department: Department the committee belongs to.
            created_by: User ID of the creator.

        Returns:
            The ID of the newly created committee.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO committees (
                    name, description, committee_type, chair_id,
                    department, status, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)
            ''', (
                name, description, committee_type, chair_id,
                department, created_by,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            committee_id = cursor.lastrowid
            log_activity('create', 'committee', details={
                'committee_id': committee_id, 'name': name,
                'created_by': created_by,
            })
            return committee_id

    @staticmethod
    def get_committee(committee_id: int) -> Optional[Dict[str, Any]]:
        """Get a single committee by ID.

        Args:
            committee_id: The committee's primary key.

        Returns:
            A dict of the committee row, or None if not found.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM committees WHERE id = ?
            ''', (committee_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_committees(department: str = None,
                       status: str = None) -> List[Dict[str, Any]]:
        """Get committees with optional filters.

        Args:
            department: Filter by department name.
            status: Filter by committee status.

        Returns:
            A list of committee dicts ordered by name.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM committees WHERE 1=1'
            params: list = []

            if department:
                query += ' AND department = ?'
                params.append(department)

            if status:
                query += ' AND status = ?'
                params.append(status)

            query += ' ORDER BY name'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_committee(committee_id: int, **data) -> None:
        """Update allowed fields on a committee.

        Allowed fields: name, description, committee_type, chair_id, status.

        Args:
            committee_id: The committee to update.
            **data: Field-value pairs to update.
        """
        allowed_fields = {
            'name', 'description', 'committee_type', 'chair_id', 'status',
        }

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
        values.append(committee_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE committees SET ' + ', '.join(fields) + ' WHERE id = ?',
                values)
            log_activity('update', 'committee', details={
                'committee_id': committee_id,
                'updated_fields': list(data.keys()),
            })

    @staticmethod
    def get_committee_members(committee_id: int) -> List[Dict[str, Any]]:
        """Get all members of a committee.

        Args:
            committee_id: The committee to list members for.

        Returns:
            A list of member dicts for the given committee.
        """
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM committee_members
                WHERE committee_id = ?
            ''', (committee_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_member(committee_id: int, user_id: str,
                   role: str = 'member') -> int:
        """Add a member to a committee.

        Args:
            committee_id: The committee to add the member to.
            user_id: The user to add.
            role: The member's role (default 'member').

        Returns:
            The ID of the new committee_members row.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO committee_members (
                    committee_id, user_id, role, joined_at
                ) VALUES (?, ?, ?, ?)
            ''', (
                committee_id, user_id, role,
                datetime.now().isoformat(),
            ))
            member_id = cursor.lastrowid
            log_activity('create', 'committee_member', details={
                'committee_id': committee_id, 'user_id': user_id,
                'role': role,
            })
            return member_id

    @staticmethod
    def remove_member(committee_id: int, user_id: str) -> None:
        """Remove a member from a committee.

        Args:
            committee_id: The committee to remove the member from.
            user_id: The user to remove.
        """
        with transaction() as conn:
            conn.execute('''
                DELETE FROM committee_members
                WHERE committee_id = ? AND user_id = ?
            ''', (committee_id, user_id))
            log_activity('delete', 'committee_member', details={
                'committee_id': committee_id, 'user_id': user_id,
            })

    # ==================== MEETING MANAGEMENT ====================

    @staticmethod
    def schedule_meeting(committee_id: int, title: str, meeting_date: str,
                         start_time: str, end_time: str = None,
                         location: str = None, virtual_link: str = None,
                         chair_id: str = None, secretary_id: str = None,
                         recurrence: str = 'none',
                         created_by: str = None) -> int:
        """Schedule a new meeting for a committee.

        Args:
            committee_id: The committee hosting the meeting.
            title: Meeting title.
            meeting_date: Date of the meeting (ISO format).
            start_time: Start time of the meeting.
            end_time: End time of the meeting (optional).
            location: Physical location (optional).
            virtual_link: Virtual meeting URL (optional).
            chair_id: User ID of the meeting chair (optional).
            secretary_id: User ID of the meeting secretary (optional).
            recurrence: Recurrence pattern, default 'none'.
            created_by: User ID of the creator (optional).

        Returns:
            The ID of the newly created meeting.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO committee_meetings (
                    committee_id, title, meeting_date, start_time, end_time,
                    location, virtual_link, chair_id, secretary_id,
                    recurrence, status, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', ?, ?, ?)
            ''', (
                committee_id, title, meeting_date, start_time, end_time,
                location, virtual_link, chair_id, secretary_id,
                recurrence, created_by,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            meeting_id = cursor.lastrowid
            log_activity('create', 'committee_meeting', details={
                'meeting_id': meeting_id, 'committee_id': committee_id,
                'title': title,
            })
            return meeting_id

    @staticmethod
    def get_meeting(meeting_id: int) -> Optional[Dict[str, Any]]:
        """Get a single meeting by ID.

        Args:
            meeting_id: The meeting's primary key.

        Returns:
            A dict of the meeting row, or None if not found.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM committee_meetings WHERE id = ?
            ''', (meeting_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_meetings(committee_id: int = None,
                     status: str = None) -> List[Dict[str, Any]]:
        """Get meetings with optional filters.

        Args:
            committee_id: Filter by committee.
            status: Filter by meeting status.

        Returns:
            A list of meeting dicts ordered by meeting_date descending.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM committee_meetings WHERE 1=1'
            params: list = []

            if committee_id:
                query += ' AND committee_id = ?'
                params.append(committee_id)

            if status:
                query += ' AND status = ?'
                params.append(status)

            query += ' ORDER BY meeting_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_meeting(meeting_id: int, **data) -> None:
        """Update allowed fields on a meeting.

        Allowed fields: title, meeting_date, start_time, end_time,
        location, virtual_link, status, chair_id, secretary_id.

        Args:
            meeting_id: The meeting to update.
            **data: Field-value pairs to update.
        """
        allowed_fields = {
            'title', 'meeting_date', 'start_time', 'end_time',
            'location', 'virtual_link', 'status', 'chair_id', 'secretary_id',
        }

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
        values.append(meeting_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE committee_meetings SET ' + ', '.join(fields) + ' WHERE id = ?',
                values)
            log_activity('update', 'committee_meeting', details={
                'meeting_id': meeting_id,
                'updated_fields': list(data.keys()),
            })

    @staticmethod
    def cancel_meeting(meeting_id: int) -> None:
        """Cancel a meeting by setting its status to 'cancelled'.

        Args:
            meeting_id: The meeting to cancel.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE committee_meetings
                SET status = 'cancelled', updated_at = ?
                WHERE id = ?
            ''', (datetime.now().isoformat(), meeting_id))
            log_activity('update', 'committee_meeting', details={
                'meeting_id': meeting_id, 'action': 'cancelled',
            })

    # ==================== AGENDA MANAGEMENT ====================

    @staticmethod
    def add_agenda_item(meeting_id: int, title: str, item_order: int,
                        description: str = None,
                        item_type: str = 'discussion',
                        presenter_id: str = None,
                        duration_minutes: int = 15) -> int:
        """Add an agenda item to a meeting.

        Args:
            meeting_id: The meeting this item belongs to.
            title: Agenda item title.
            item_order: Ordering position of the item.
            description: Detailed description (optional).
            item_type: Type of item, default 'discussion'.
            presenter_id: User ID of the presenter (optional).
            duration_minutes: Estimated duration in minutes, default 15.

        Returns:
            The ID of the newly created agenda item.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO committee_agenda_items (
                    meeting_id, title, item_order, description,
                    item_type, presenter_id, duration_minutes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                meeting_id, title, item_order, description,
                item_type, presenter_id, duration_minutes,
                datetime.now().isoformat(),
            ))
            item_id = cursor.lastrowid
            log_activity('create', 'committee_agenda_item', details={
                'item_id': item_id, 'meeting_id': meeting_id,
                'title': title,
            })
            return item_id

    @staticmethod
    def get_agenda(meeting_id: int) -> List[Dict[str, Any]]:
        """Get all agenda items for a meeting ordered by item_order.

        Args:
            meeting_id: The meeting to retrieve the agenda for.

        Returns:
            A list of agenda item dicts ordered by item_order.
        """
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM committee_agenda_items
                WHERE meeting_id = ?
                ORDER BY item_order
            ''', (meeting_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_agenda_item(item_id: int, **data) -> None:
        """Update an agenda item.

        Args:
            item_id: The agenda item to update.
            **data: Field-value pairs to update.
        """
        if not data:
            return

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('id', 'meeting_id', 'created_at'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        values.append(item_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE committee_agenda_items SET '
                + ', '.join(fields) + ' WHERE id = ?',
                values)
            log_activity('update', 'committee_agenda_item', details={
                'item_id': item_id, 'updated_fields': list(data.keys()),
            })

    @staticmethod
    def remove_agenda_item(item_id: int) -> None:
        """Delete an agenda item.

        Args:
            item_id: The agenda item to delete.
        """
        with transaction() as conn:
            conn.execute('''
                DELETE FROM committee_agenda_items WHERE id = ?
            ''', (item_id,))
            log_activity('delete', 'committee_agenda_item', details={
                'item_id': item_id,
            })

    @staticmethod
    def reorder_agenda(meeting_id: int, item_ids: List[int]) -> None:
        """Reorder agenda items for a meeting.

        Each item in item_ids is assigned an item_order equal to its
        position in the list (starting from 1).

        Args:
            meeting_id: The meeting whose agenda is being reordered.
            item_ids: Ordered list of agenda item IDs.
        """
        with transaction() as conn:
            for order, item_id in enumerate(item_ids, start=1):
                conn.execute('''
                    UPDATE committee_agenda_items
                    SET item_order = ?
                    WHERE id = ? AND meeting_id = ?
                ''', (order, item_id, meeting_id))
            log_activity('update', 'committee_agenda_item', details={
                'meeting_id': meeting_id, 'action': 'reorder',
                'item_ids': item_ids,
            })

    # ==================== MINUTES ====================

    @staticmethod
    def record_minutes(meeting_id: int, content: str,
                       recorded_by: str) -> int:
        """Record minutes for a meeting.

        Args:
            meeting_id: The meeting the minutes are for.
            content: The minutes text content.
            recorded_by: User ID of the person recording.

        Returns:
            The ID of the newly created minutes record.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO meeting_minutes (
                    meeting_id, content, recorded_by, status, created_at
                ) VALUES (?, ?, ?, 'draft', ?)
            ''', (
                meeting_id, content, recorded_by,
                datetime.now().isoformat(),
            ))
            minute_id = cursor.lastrowid
            log_activity('create', 'meeting_minutes', details={
                'minute_id': minute_id, 'meeting_id': meeting_id,
                'recorded_by': recorded_by,
            })
            return minute_id

    @staticmethod
    def get_minutes(meeting_id: int) -> List[Dict[str, Any]]:
        """Get all minutes records for a meeting.

        Args:
            meeting_id: The meeting to retrieve minutes for.

        Returns:
            A list of minutes dicts for the given meeting.
        """
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM meeting_minutes
                WHERE meeting_id = ?
            ''', (meeting_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def approve_minutes(minute_id: int, approved_by: str) -> None:
        """Approve a minutes record.

        Args:
            minute_id: The minutes record to approve.
            approved_by: User ID of the approver.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE meeting_minutes
                SET status = 'approved', approved_by = ?, approved_at = ?
                WHERE id = ?
            ''', (approved_by, datetime.now().isoformat(), minute_id))
            log_activity('update', 'meeting_minutes', details={
                'minute_id': minute_id, 'action': 'approved',
                'approved_by': approved_by,
            })

    # ==================== VOTING ====================

    @staticmethod
    def create_vote(meeting_id: int, committee_id: int, title: str,
                    description: str = None,
                    vote_type: str = 'simple_majority',
                    is_secret_ballot: bool = False,
                    created_by: str = None) -> int:
        """Create a new vote for a meeting.

        Args:
            meeting_id: The meeting the vote is associated with.
            committee_id: The committee conducting the vote.
            title: Title or motion being voted on.
            description: Detailed description of the motion (optional).
            vote_type: Voting rule - 'simple_majority', 'two_thirds',
                       or 'unanimous'.
            is_secret_ballot: Whether individual votes are hidden.
            created_by: User ID of the creator (optional).

        Returns:
            The ID of the newly created vote.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO committee_votes (
                    meeting_id, committee_id, title, description,
                    vote_type, is_secret_ballot, status,
                    created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)
            ''', (
                meeting_id, committee_id, title, description,
                vote_type, int(is_secret_ballot),
                created_by, datetime.now().isoformat(),
            ))
            vote_id = cursor.lastrowid
            log_activity('create', 'committee_vote', details={
                'vote_id': vote_id, 'meeting_id': meeting_id,
                'title': title,
            })
            return vote_id

    @staticmethod
    def cast_ballot(vote_id: int, voter_id: str, choice: str) -> int:
        """Cast a ballot on an open vote.

        Args:
            vote_id: The vote to cast a ballot on.
            voter_id: The user casting the ballot.
            choice: The voter's choice ('for', 'against', 'abstain').

        Returns:
            The ID of the newly created ballot.

        Raises:
            ValueError: If the voter has already cast a ballot on this vote.
        """
        with transaction() as conn:
            # Check for existing ballot (UNIQUE constraint)
            existing = conn.execute('''
                SELECT id FROM committee_ballots
                WHERE vote_id = ? AND voter_id = ?
            ''', (vote_id, voter_id)).fetchone()

            if existing:
                raise ValueError(
                    f"Voter {voter_id} has already cast a ballot on vote {vote_id}"
                )

            cursor = conn.execute('''
                INSERT INTO committee_ballots (
                    vote_id, voter_id, choice, cast_at
                ) VALUES (?, ?, ?, ?)
            ''', (
                vote_id, voter_id, choice,
                datetime.now().isoformat(),
            ))
            ballot_id = cursor.lastrowid
            log_activity('create', 'committee_ballot', details={
                'ballot_id': ballot_id, 'vote_id': vote_id,
            })
            return ballot_id

    @staticmethod
    def close_vote(vote_id: int) -> Dict[str, Any]:
        """Close a vote, tally ballots, and determine the result.

        The result is determined according to the vote_type:
        - simple_majority: 'for' count > 'against' count
        - two_thirds: 'for' count >= 2/3 of (for + against)
        - unanimous: 'against' == 0 and 'for' > 0

        Args:
            vote_id: The vote to close.

        Returns:
            A dict containing the vote tallies and result, e.g.::

                {
                    'vote_id': 1,
                    'votes_for': 5,
                    'votes_against': 2,
                    'votes_abstain': 1,
                    'result': 'passed',
                    'vote_type': 'simple_majority',
                }
        """
        with transaction() as conn:
            # Get the vote record
            vote_row = conn.execute('''
                SELECT * FROM committee_votes WHERE id = ?
            ''', (vote_id,)).fetchone()

            if not vote_row:
                raise ValueError(f"Vote {vote_id} not found")

            vote = dict(vote_row)

            # Count ballots
            rows = conn.execute('''
                SELECT choice, COUNT(*) as cnt
                FROM committee_ballots
                WHERE vote_id = ?
                GROUP BY choice
            ''', (vote_id,)).fetchall()

            tallies = {r['choice']: r['cnt'] for r in rows}
            votes_for = tallies.get('for', 0)
            votes_against = tallies.get('against', 0)
            votes_abstain = tallies.get('abstain', 0)

            # Determine result based on vote_type
            vote_type = vote['vote_type']
            if vote_type == 'simple_majority':
                result = 'passed' if votes_for > votes_against else 'failed'
            elif vote_type == 'two_thirds':
                total_decisive = votes_for + votes_against
                result = (
                    'passed'
                    if total_decisive > 0 and votes_for >= (2 / 3) * total_decisive
                    else 'failed'
                )
            elif vote_type == 'unanimous':
                result = (
                    'passed'
                    if votes_against == 0 and votes_for > 0
                    else 'failed'
                )
            else:
                result = 'passed' if votes_for > votes_against else 'failed'

            # Update the vote record
            conn.execute('''
                UPDATE committee_votes
                SET votes_for = ?, votes_against = ?, votes_abstain = ?,
                    result = ?, status = 'closed', closed_at = ?
                WHERE id = ?
            ''', (
                votes_for, votes_against, votes_abstain,
                result, datetime.now().isoformat(), vote_id,
            ))

            results = {
                'vote_id': vote_id,
                'votes_for': votes_for,
                'votes_against': votes_against,
                'votes_abstain': votes_abstain,
                'result': result,
                'vote_type': vote_type,
            }

            log_activity('update', 'committee_vote', details={
                'vote_id': vote_id, 'action': 'closed',
                'result': result,
            })

            return results

    @staticmethod
    def get_vote_results(vote_id: int) -> Dict[str, Any]:
        """Get vote details and results.

        If the vote is a secret ballot, individual ballots are not
        included.  If it is not a secret ballot, a 'ballots' list is
        appended to the returned dict.

        Args:
            vote_id: The vote to retrieve results for.

        Returns:
            A dict with the vote record and, for non-secret ballots,
            a list of individual ballots.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM committee_votes WHERE id = ?
            ''', (vote_id,)).fetchone()

            if not row:
                raise ValueError(f"Vote {vote_id} not found")

            vote = dict(row)

            if not vote.get('is_secret_ballot'):
                ballots = conn.execute('''
                    SELECT * FROM committee_ballots
                    WHERE vote_id = ?
                ''', (vote_id,)).fetchall()
                vote['ballots'] = [dict(b) for b in ballots]

            return vote

    @staticmethod
    def get_meeting_votes(meeting_id: int) -> List[Dict[str, Any]]:
        """Get all votes associated with a meeting.

        Args:
            meeting_id: The meeting to retrieve votes for.

        Returns:
            A list of vote dicts for the given meeting.
        """
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM committee_votes
                WHERE meeting_id = ?
            ''', (meeting_id,)).fetchall()
            return [dict(row) for row in rows]
