"""
Staff Mentoring Programme Manager

Provides functionality for:
- Mentoring programme creation and management
- Mentor registration and availability tracking
- Mentor-mentee matching and lifecycle
- Mentoring session logging and tracking
- Goal setting and progress monitoring
- Programme and mentor statistics reporting
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.core.sql_safety import validate_identifier


class MentoringManager:
    """Manager for mentoring programmes, mentors, matches, sessions, and goals."""

    # ==================== PROGRAMME MANAGEMENT ====================

    @staticmethod
    def create_programme(name: str, description: str, programme_type: str,
                         department: str, max_mentees_per_mentor: int,
                         duration_months: int, created_by: str) -> int:
        """Create a new mentoring programme.

        Args:
            name: Programme name.
            description: Purpose or description of the programme.
            programme_type: Type of programme (e.g. 'research', 'teaching', 'buddy').
            department: Department the programme belongs to.
            max_mentees_per_mentor: Maximum mentees each mentor can take.
            duration_months: Default duration of the programme in months.
            created_by: User ID of the creator.

        Returns:
            The ID of the newly created programme.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO staff_mentoring_programmes (
                    name, description, programme_type, department,
                    max_mentees_per_mentor, duration_months,
                    status, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
            ''', (
                name, description, programme_type, department,
                max_mentees_per_mentor, duration_months,
                created_by,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            programme_id = cursor.lastrowid
            log_activity('create', 'mentoring_programme', details={
                'programme_id': programme_id, 'name': name,
                'created_by': created_by,
            })
            return programme_id

    @staticmethod
    def get_programme(programme_id: int) -> Optional[Dict[str, Any]]:
        """Get a single mentoring programme by ID.

        Args:
            programme_id: The programme's primary key.

        Returns:
            A dict of the programme row, or None if not found.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM staff_mentoring_programmes
                WHERE programme_id = ?
            ''', (programme_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_programmes(status: str = None,
                       programme_type: str = None) -> List[Dict[str, Any]]:
        """Get mentoring programmes with optional filters.

        Args:
            status: Filter by programme status.
            programme_type: Filter by programme type.

        Returns:
            A list of programme dicts ordered by name.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM staff_mentoring_programmes WHERE 1=1'
            params: list = []

            if status:
                query += ' AND status = ?'
                params.append(status)

            if programme_type:
                query += ' AND programme_type = ?'
                params.append(programme_type)

            query += ' ORDER BY name'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_programme(programme_id: int, **data) -> None:
        """Update allowed fields on a mentoring programme.

        Allowed fields: name, description, programme_type, department,
        max_mentees_per_mentor, duration_months, status.

        Args:
            programme_id: The programme to update.
            **data: Field-value pairs to update.
        """
        allowed_fields = {
            'name', 'description', 'programme_type', 'department',
            'max_mentees_per_mentor', 'duration_months', 'status',
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
        values.append(programme_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE staff_mentoring_programmes SET '
                + ', '.join(fields) + ' WHERE programme_id = ?',
                values)
            log_activity('update', 'mentoring_programme', details={
                'programme_id': programme_id,
                'updated_fields': list(data.keys()),
            })

    # ==================== MENTOR MANAGEMENT ====================

    @staticmethod
    def register_mentor(user_id: str, programme_id: int,
                        expertise_areas: str, max_mentees: int,
                        bio: str) -> int:
        """Register a new mentor for a programme.

        Args:
            user_id: The user ID of the mentor.
            programme_id: The programme to register the mentor for.
            expertise_areas: JSON string of the mentor's expertise areas.
            max_mentees: Maximum number of mentees the mentor can take.
            bio: A short biography or description of the mentor.

        Returns:
            The ID of the newly created mentor record.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO staff_mentors (
                    user_id, programme_id, expertise_areas, max_mentees,
                    current_mentees, availability, bio, status,
                    joined_at, updated_at
                ) VALUES (?, ?, ?, ?, 0, 'available', ?, 'active', ?, ?)
            ''', (
                user_id, programme_id, expertise_areas, max_mentees,
                bio,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            mentor_id = cursor.lastrowid
            log_activity('create', 'mentor', details={
                'mentor_id': mentor_id, 'user_id': user_id,
                'programme_id': programme_id,
            })
            return mentor_id

    @staticmethod
    def get_mentor(mentor_id: int) -> Optional[Dict[str, Any]]:
        """Get a single mentor by ID.

        Args:
            mentor_id: The mentor's primary key.

        Returns:
            A dict of the mentor row, or None if not found.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM staff_mentors WHERE mentor_id = ?
            ''', (mentor_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_mentors(programme_id: int = None,
                    availability: str = None) -> List[Dict[str, Any]]:
        """Get mentors with optional filters.

        Args:
            programme_id: Filter by programme.
            availability: Filter by availability status.

        Returns:
            A list of mentor dicts ordered by joined_at descending.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM staff_mentors WHERE 1=1'
            params: list = []

            if programme_id:
                query += ' AND programme_id = ?'
                params.append(programme_id)

            if availability:
                query += ' AND availability = ?'
                params.append(availability)

            query += ' ORDER BY joined_at DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_mentor(mentor_id: int, **data) -> None:
        """Update allowed fields on a mentor.

        Allowed fields: expertise_areas, max_mentees, availability, bio, status.

        Args:
            mentor_id: The mentor to update.
            **data: Field-value pairs to update.
        """
        allowed_fields = {
            'expertise_areas', 'max_mentees', 'availability', 'bio', 'status',
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
        values.append(mentor_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE staff_mentors SET '
                + ', '.join(fields) + ' WHERE mentor_id = ?',
                values)
            log_activity('update', 'mentor', details={
                'mentor_id': mentor_id,
                'updated_fields': list(data.keys()),
            })

    # ==================== MATCH MANAGEMENT ====================

    @staticmethod
    def create_match(programme_id: int, mentor_id: int,
                     mentee_user_id: str, match_reason: str,
                     matched_by: str) -> int:
        """Create a new mentor-mentee match.

        Also increments the mentor's current_mentees count.

        Args:
            programme_id: The programme this match belongs to.
            mentor_id: The mentor being matched.
            mentee_user_id: The user ID of the mentee.
            match_reason: Reason or rationale for the match.
            matched_by: User ID of the person creating the match.

        Returns:
            The ID of the newly created match.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO staff_mentoring_matches (
                    programme_id, mentor_id, mentee_user_id,
                    match_reason, status, matched_by,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'proposed', ?, ?, ?)
            ''', (
                programme_id, mentor_id, mentee_user_id,
                match_reason, matched_by,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            match_id = cursor.lastrowid

            # Increment the mentor's current_mentees count
            conn.execute('''
                UPDATE staff_mentors
                SET current_mentees = current_mentees + 1, updated_at = ?
                WHERE mentor_id = ?
            ''', (datetime.now().isoformat(), mentor_id))

            log_activity('create', 'mentoring_match', details={
                'match_id': match_id, 'programme_id': programme_id,
                'mentor_id': mentor_id, 'mentee_user_id': mentee_user_id,
                'matched_by': matched_by,
            })
            return match_id

    @staticmethod
    def get_match(match_id: int) -> Optional[Dict[str, Any]]:
        """Get a single match by ID.

        Args:
            match_id: The match's primary key.

        Returns:
            A dict of the match row, or None if not found.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM staff_mentoring_matches WHERE match_id = ?
            ''', (match_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_user_matches(user_id: str,
                         role: str = None) -> List[Dict[str, Any]]:
        """Get all matches for a user, optionally filtered by role.

        Args:
            user_id: The user ID to look up matches for.
            role: If 'mentor', find matches where the user is a mentor
                  (via staff_mentors.user_id). If 'mentee', find matches
                  where the user is the mentee. If None, return both.

        Returns:
            A list of match dicts for the given user.
        """
        with get_connection() as conn:
            if role == 'mentor':
                rows = conn.execute('''
                    SELECT m.* FROM staff_mentoring_matches m
                    JOIN staff_mentors sm ON m.mentor_id = sm.mentor_id
                    WHERE sm.user_id = ?
                    ORDER BY m.created_at DESC
                ''', (user_id,)).fetchall()
            elif role == 'mentee':
                rows = conn.execute('''
                    SELECT * FROM staff_mentoring_matches
                    WHERE mentee_user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,)).fetchall()
            else:
                # Return matches where user is either mentor or mentee
                rows = conn.execute('''
                    SELECT m.* FROM staff_mentoring_matches m
                    JOIN staff_mentors sm ON m.mentor_id = sm.mentor_id
                    WHERE sm.user_id = ?
                    UNION
                    SELECT * FROM staff_mentoring_matches
                    WHERE mentee_user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id, user_id)).fetchall()

            return [dict(row) for row in rows]

    @staticmethod
    def activate_match(match_id: int, start_date: str) -> None:
        """Activate a match by setting its status to 'active'.

        Args:
            match_id: The match to activate.
            start_date: The start date for the mentoring relationship.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE staff_mentoring_matches
                SET status = 'active', start_date = ?, updated_at = ?
                WHERE match_id = ?
            ''', (start_date, datetime.now().isoformat(), match_id))
            log_activity('update', 'mentoring_match', details={
                'match_id': match_id, 'action': 'activated',
                'start_date': start_date,
            })

    @staticmethod
    def complete_match(match_id: int, mentor_rating: int = None,
                       mentee_rating: int = None) -> None:
        """Complete a match and decrement the mentor's current_mentees.

        Sets the match status to 'completed' and records the actual end
        date. Optionally stores ratings for the mentor and mentee.

        Args:
            match_id: The match to complete.
            mentor_rating: Rating given to the mentor (optional).
            mentee_rating: Rating given to the mentee (optional).
        """
        with transaction() as conn:
            # Get the mentor_id before updating
            row = conn.execute('''
                SELECT mentor_id FROM staff_mentoring_matches
                WHERE match_id = ?
            ''', (match_id,)).fetchone()

            if not row:
                return

            mentor_id = row['mentor_id']

            conn.execute('''
                UPDATE staff_mentoring_matches
                SET status = 'completed', actual_end_date = ?,
                    mentor_rating = ?, mentee_rating = ?, updated_at = ?
                WHERE match_id = ?
            ''', (
                datetime.now().isoformat(),
                mentor_rating, mentee_rating,
                datetime.now().isoformat(), match_id,
            ))

            # Decrement the mentor's current_mentees count
            conn.execute('''
                UPDATE staff_mentors
                SET current_mentees = MAX(current_mentees - 1, 0),
                    updated_at = ?
                WHERE mentor_id = ?
            ''', (datetime.now().isoformat(), mentor_id))

            log_activity('update', 'mentoring_match', details={
                'match_id': match_id, 'action': 'completed',
                'mentor_id': mentor_id,
            })

    # ==================== SESSION MANAGEMENT ====================

    @staticmethod
    def log_session(match_id: int, session_date: str,
                    duration_minutes: int, session_type: str,
                    location: str, virtual_link: str,
                    topics_discussed: str,
                    action_items: str) -> int:
        """Log a new mentoring session.

        Args:
            match_id: The match this session belongs to.
            session_date: Date of the session (ISO format).
            duration_minutes: Duration of the session in minutes.
            session_type: Type of session (e.g. 'one_on_one', 'group').
            location: Physical location of the session.
            virtual_link: Virtual meeting URL.
            topics_discussed: Summary of topics discussed.
            action_items: Action items arising from the session.

        Returns:
            The ID of the newly created session.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO staff_mentoring_sessions (
                    match_id, session_date, duration_minutes,
                    session_type, location, virtual_link,
                    topics_discussed, action_items,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', ?)
            ''', (
                match_id, session_date, duration_minutes,
                session_type, location, virtual_link,
                topics_discussed, action_items,
                datetime.now().isoformat(),
            ))
            session_id = cursor.lastrowid
            log_activity('create', 'mentoring_session', details={
                'session_id': session_id, 'match_id': match_id,
                'session_date': session_date,
            })
            return session_id

    @staticmethod
    def get_sessions(match_id: int,
                     status: str = None) -> List[Dict[str, Any]]:
        """Get all sessions for a match, optionally filtered by status.

        Args:
            match_id: The match to retrieve sessions for.
            status: Filter by session status.

        Returns:
            A list of session dicts ordered by session_date descending.
        """
        with get_connection() as conn:
            query = '''
                SELECT * FROM staff_mentoring_sessions
                WHERE match_id = ?
            '''
            params: list = [match_id]

            if status:
                query += ' AND status = ?'
                params.append(status)

            query += ' ORDER BY session_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_session(session_id: int, **data) -> None:
        """Update allowed fields on a mentoring session.

        Allowed fields: topics_discussed, action_items, mentor_notes,
        mentee_notes, status.

        Args:
            session_id: The session to update.
            **data: Field-value pairs to update.
        """
        allowed_fields = {
            'topics_discussed', 'action_items', 'mentor_notes',
            'mentee_notes', 'status',
        }

        fields = []
        values = []
        for key, value in data.items():
            if key in allowed_fields:
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        values.append(session_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE staff_mentoring_sessions SET '
                + ', '.join(fields) + ' WHERE session_id = ?',
                values)
            log_activity('update', 'mentoring_session', details={
                'session_id': session_id,
                'updated_fields': list(data.keys()),
            })

    @staticmethod
    def complete_session(session_id: int) -> None:
        """Complete a session by setting its status to 'completed'.

        Args:
            session_id: The session to complete.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE staff_mentoring_sessions
                SET status = 'completed'
                WHERE session_id = ?
            ''', (session_id,))
            log_activity('update', 'mentoring_session', details={
                'session_id': session_id, 'action': 'completed',
            })

    # ==================== GOAL MANAGEMENT ====================

    @staticmethod
    def create_goal(match_id: int, title: str, description: str,
                    target_date: str) -> int:
        """Create a new mentoring goal for a match.

        Args:
            match_id: The match this goal belongs to.
            title: Goal title.
            description: Detailed description of the goal.
            target_date: Target completion date (ISO format).

        Returns:
            The ID of the newly created goal.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO staff_mentoring_goals (
                    match_id, title, description, target_date,
                    status, progress_pct, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'in_progress', 0, ?, ?)
            ''', (
                match_id, title, description, target_date,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            goal_id = cursor.lastrowid
            log_activity('create', 'mentoring_goal', details={
                'goal_id': goal_id, 'match_id': match_id,
                'title': title,
            })
            return goal_id

    @staticmethod
    def get_goals(match_id: int,
                  status: str = None) -> List[Dict[str, Any]]:
        """Get all goals for a match, optionally filtered by status.

        Args:
            match_id: The match to retrieve goals for.
            status: Filter by goal status.

        Returns:
            A list of goal dicts for the given match.
        """
        with get_connection() as conn:
            query = '''
                SELECT * FROM staff_mentoring_goals
                WHERE match_id = ?
            '''
            params: list = [match_id]

            if status:
                query += ' AND status = ?'
                params.append(status)

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_goal(goal_id: int, **data) -> None:
        """Update allowed fields on a mentoring goal.

        Allowed fields: title, description, target_date, status, progress_pct.

        Args:
            goal_id: The goal to update.
            **data: Field-value pairs to update.
        """
        allowed_fields = {
            'title', 'description', 'target_date', 'status', 'progress_pct',
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
        values.append(goal_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE staff_mentoring_goals SET '
                + ', '.join(fields) + ' WHERE goal_id = ?',
                values)
            log_activity('update', 'mentoring_goal', details={
                'goal_id': goal_id,
                'updated_fields': list(data.keys()),
            })

    @staticmethod
    def complete_goal(goal_id: int) -> None:
        """Complete a goal by setting status, progress, and completion date.

        Sets the goal status to 'completed', progress_pct to 100, and
        records the completion_date.

        Args:
            goal_id: The goal to complete.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE staff_mentoring_goals
                SET status = 'completed', progress_pct = 100,
                    completion_date = ?, updated_at = ?
                WHERE goal_id = ?
            ''', (
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                goal_id,
            ))
            log_activity('update', 'mentoring_goal', details={
                'goal_id': goal_id, 'action': 'completed',
            })

    # ==================== REPORTING ====================

    @staticmethod
    def get_programme_statistics(programme_id: int) -> Dict[str, Any]:
        """Get aggregate statistics for a mentoring programme.

        Args:
            programme_id: The programme to retrieve statistics for.

        Returns:
            A dict containing:
            - programme_id: The programme ID.
            - total_mentors: Count of mentors in the programme.
            - active_matches: Count of matches with status 'active'.
            - completed_matches: Count of matches with status 'completed'.
            - total_sessions: Count of all sessions across matches.
        """
        with get_connection() as conn:
            # Count mentors
            mentor_row = conn.execute('''
                SELECT COUNT(*) as cnt FROM staff_mentors
                WHERE programme_id = ?
            ''', (programme_id,)).fetchone()
            total_mentors = mentor_row['cnt'] if mentor_row else 0

            # Count active matches
            active_row = conn.execute('''
                SELECT COUNT(*) as cnt FROM staff_mentoring_matches
                WHERE programme_id = ? AND status = 'active'
            ''', (programme_id,)).fetchone()
            active_matches = active_row['cnt'] if active_row else 0

            # Count completed matches
            completed_row = conn.execute('''
                SELECT COUNT(*) as cnt FROM staff_mentoring_matches
                WHERE programme_id = ? AND status = 'completed'
            ''', (programme_id,)).fetchone()
            completed_matches = completed_row['cnt'] if completed_row else 0

            # Count total sessions across all matches in the programme
            session_row = conn.execute('''
                SELECT COUNT(*) as cnt FROM staff_mentoring_sessions s
                JOIN staff_mentoring_matches m ON s.match_id = m.match_id
                WHERE m.programme_id = ?
            ''', (programme_id,)).fetchone()
            total_sessions = session_row['cnt'] if session_row else 0

            return {
                'programme_id': programme_id,
                'total_mentors': total_mentors,
                'active_matches': active_matches,
                'completed_matches': completed_matches,
                'total_sessions': total_sessions,
            }

    @staticmethod
    def get_mentor_statistics(mentor_id: int) -> Dict[str, Any]:
        """Get aggregate statistics for a mentor.

        Args:
            mentor_id: The mentor to retrieve statistics for.

        Returns:
            A dict containing:
            - mentor_id: The mentor ID.
            - total_matches: Count of all matches for the mentor.
            - total_sessions: Count of all sessions across the mentor's matches.
            - avg_mentee_rating: Average mentee_rating across completed
              matches, or None if no ratings exist.
        """
        with get_connection() as conn:
            # Count matches
            match_row = conn.execute('''
                SELECT COUNT(*) as cnt FROM staff_mentoring_matches
                WHERE mentor_id = ?
            ''', (mentor_id,)).fetchone()
            total_matches = match_row['cnt'] if match_row else 0

            # Count sessions
            session_row = conn.execute('''
                SELECT COUNT(*) as cnt FROM staff_mentoring_sessions s
                JOIN staff_mentoring_matches m ON s.match_id = m.match_id
                WHERE m.mentor_id = ?
            ''', (mentor_id,)).fetchone()
            total_sessions = session_row['cnt'] if session_row else 0

            # Average mentee rating
            rating_row = conn.execute('''
                SELECT AVG(mentee_rating) as avg_rating
                FROM staff_mentoring_matches
                WHERE mentor_id = ? AND mentee_rating IS NOT NULL
            ''', (mentor_id,)).fetchone()
            avg_mentee_rating = (
                round(rating_row['avg_rating'], 2)
                if rating_row and rating_row['avg_rating'] is not None
                else None
            )

            return {
                'mentor_id': mentor_id,
                'total_matches': total_matches,
                'total_sessions': total_sessions,
                'avg_mentee_rating': avg_mentee_rating,
            }
