"""
Directory Manager - Staff directory, expertise, and office hours management.

Provides functionality for:
- Staff directory search and profile lookup
- Expertise area management and search
- Office hours scheduling
- Combined profile retrieval
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity
from education_system.post_18.university_system.core.sql_safety import validate_identifier  # nosec B608


class DirectoryManager:
    """Manager for staff directory, expertise, and office hours."""

    # ==================== DIRECTORY SEARCH ====================

    @staticmethod
    def _enrich_identities(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fill in missing name/email from the shared auth database.

        Staff identity (name + email) lives in the shared ``auth.db`` users
        table as ``display_name`` / ``email``. The local university ``users``
        table has no rows for most staff, so the directory join leaves
        first_name/last_name/email blank even though the data exists. Look the
        missing staff up by username and populate the fields the GUI expects.

        Best-effort: if the auth DB is unavailable the rows are returned
        unchanged rather than raising.
        """
        pending = {
            str(r.get('user_id')) for r in rows
            if r.get('user_id')
            and not (r.get('first_name') or r.get('last_name') or r.get('email'))
        }
        if not pending:
            return rows

        lookup: Dict[str, Dict[str, str]] = {}
        try:
            from education_system.shared.auth.db import connect
            auth_conn = connect()
            try:
                placeholders = ','.join('?' * len(pending))
                fetched = auth_conn.execute(
                    'SELECT username, display_name, email FROM users '
                    f'WHERE username IN ({placeholders})',  # nosec B608 - placeholders only
                    tuple(pending),
                ).fetchall()
            finally:
                auth_conn.close()
            for row in fetched:
                lookup[str(row['username'])] = {
                    'display_name': row['display_name'] or '',
                    'email': row['email'] or '',
                }
        except Exception:
            return rows

        for r in rows:
            info = lookup.get(str(r.get('user_id')))
            if not info:
                continue
            if not (r.get('first_name') or r.get('last_name')):
                parts = info['display_name'].split()
                if parts:
                    r['first_name'] = parts[0]
                    r['last_name'] = ' '.join(parts[1:])
            if not r.get('email'):
                r['email'] = info['email']
        return rows

    @staticmethod
    def search_directory(query: str = None, department: str = None,
                         expertise: str = None) -> List[Dict[str, Any]]:
        """Search the staff directory with optional filters.

        Args:
            query: Search term matched against first_name, last_name, email.
            department: Exact department match.
            expertise: Search term matched against expertise_area in staff_expertise.

        Returns:
            List of matching staff profile dicts.
        """
        try:
            with get_connection() as conn:
                # Names and email live in the ``users`` table, not ``staff_profiles``.
                # staff_profiles.user_id stores the username (or, occasionally, the
                # numeric users.id), so join on either. Alias job_title/phone_extension
                # to the keys the directory GUI expects (position/phone).
                base = '''
                    SELECT sp.user_id,
                           u.first_name AS first_name,
                           u.last_name AS last_name,
                           u.email AS email,
                           sp.department AS department,
                           sp.job_title AS position,
                           sp.phone_extension AS phone,
                           sp.office_location AS office_location
                    FROM staff_profiles sp
                    LEFT JOIN users u ON u.username = sp.user_id OR u.id = sp.user_id
                '''
                conditions = []
                params: list = []

                if expertise:
                    base += ' JOIN staff_expertise se ON sp.user_id = se.user_id'
                    conditions.append('se.expertise_area LIKE ?')
                    params.append(f'%{expertise}%')

                if query:
                    like = f'%{query}%'
                    clause = ('u.first_name LIKE ? OR u.last_name LIKE ? '
                              'OR u.email LIKE ? OR sp.user_id LIKE ?')
                    q_params = [like, like, like, like]
                    # Most staff names/emails live only in the shared auth DB,
                    # so also match usernames whose auth display_name/email hit
                    # the query — otherwise a search by real name finds nothing.
                    matched = DirectoryManager._usernames_matching(query)
                    if matched:
                        placeholders = ','.join('?' * len(matched))
                        clause += f' OR sp.user_id IN ({placeholders})'  # nosec B608 - placeholders only
                        q_params.extend(matched)
                    conditions.append('(' + clause + ')')
                    params.extend(q_params)

                if department:
                    conditions.append('sp.department = ?')
                    params.append(department)

                if conditions:
                    base += ' WHERE ' + ' AND '.join(conditions)

                base += ' ORDER BY u.last_name, u.first_name, sp.user_id'
                rows = conn.execute(base, params).fetchall()
                return DirectoryManager._enrich_identities([dict(row) for row in rows])
        except Exception:
            return []

    @staticmethod
    def _usernames_matching(query: str) -> List[str]:
        """Return usernames whose shared-auth display_name/email match *query*."""
        try:
            from education_system.shared.auth.db import connect
            auth_conn = connect()
            try:
                like = f'%{query}%'
                rows = auth_conn.execute(
                    'SELECT username FROM users '
                    'WHERE display_name LIKE ? OR email LIKE ?',
                    (like, like),
                ).fetchall()
            finally:
                auth_conn.close()
            return [str(r['username']) for r in rows]
        except Exception:
            return []

    @staticmethod
    def get_staff_profile(user_id: str) -> Optional[Dict[str, Any]]:
        """Get a single staff profile by user ID, with name/email resolved.

        staff_profiles has no name columns and stores job_title/office_location/
        phone_extension; alias those to the position/office/phone keys the GUI
        reads, and resolve name/email (from the local users join or, failing
        that, the shared auth DB).
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT sp.*,
                       u.first_name AS first_name,
                       u.last_name AS last_name,
                       u.email AS email,
                       sp.job_title AS position,
                       sp.office_location AS office,
                       sp.phone_extension AS phone
                FROM staff_profiles sp
                LEFT JOIN users u ON u.username = sp.user_id OR u.id = sp.user_id
                WHERE sp.user_id = ?
            ''', (user_id,)).fetchone()
            if not row:
                return None
            return DirectoryManager._enrich_identities([dict(row)])[0]

    @staticmethod
    def get_department_staff(department: str) -> List[Dict[str, Any]]:
        """Get all staff members in a department.

        Names/email come from the ``users`` table (joined on username or id);
        job_title/phone_extension are aliased to the position/phone keys the
        directory GUI reads.
        """
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT sp.user_id,
                       u.first_name AS first_name,
                       u.last_name AS last_name,
                       u.email AS email,
                       sp.department AS department,
                       sp.job_title AS position,
                       sp.phone_extension AS phone,
                       sp.office_location AS office_location
                FROM staff_profiles sp
                LEFT JOIN users u ON u.username = sp.user_id OR u.id = sp.user_id
                WHERE sp.department = ?
                ORDER BY u.last_name, u.first_name, sp.user_id
            ''', (department,)).fetchall()
            return DirectoryManager._enrich_identities([dict(row) for row in rows])

    # ==================== EXPERTISE MANAGEMENT ====================

    @staticmethod
    def add_expertise(user_id: str, expertise_area: str,
                      category: str = 'academic',
                      proficiency: str = 'intermediate',
                      keywords: str = None) -> int:
        """Add an expertise area for a staff member."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO staff_expertise (
                    user_id, expertise_area, category,
                    proficiency, keywords
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                user_id, expertise_area, category,
                proficiency, keywords,
            ))
            expertise_id = cursor.lastrowid
            log_activity('create', 'staff_expertise', details={
                'expertise_id': expertise_id, 'user_id': user_id,
                'expertise_area': expertise_area,
            })
            return expertise_id

    @staticmethod
    def get_expertise(user_id: str) -> List[Dict[str, Any]]:
        """Get all expertise areas for a staff member."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM staff_expertise
                WHERE user_id = ?
                ORDER BY category, expertise_area
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_expertise(expertise_id: int, **data) -> None:
        """Update an expertise record."""
        if not data:
            return

        allowed_fields = {
            'expertise_area', 'category', 'proficiency',
            'keywords', 'is_public',
        }

        fields = []
        values = []
        for key, value in data.items():
            if key in allowed_fields:
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        values.append(expertise_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE staff_expertise SET ' + ', '.join(fields)
                + ' WHERE expertise_id = ?',
                values)
            log_activity('update', 'staff_expertise', details={
                'expertise_id': expertise_id,
                'updated_fields': list(data.keys()),
            })

    @staticmethod
    def remove_expertise(expertise_id: int) -> None:
        """Remove an expertise record."""
        with transaction() as conn:
            conn.execute('''
                DELETE FROM staff_expertise WHERE expertise_id = ?
            ''', (expertise_id,))
            log_activity('delete', 'staff_expertise', details={
                'expertise_id': expertise_id,
            })

    @staticmethod
    def search_by_expertise(keyword: str) -> List[Dict[str, Any]]:
        """Search staff by expertise keyword.

        Searches both expertise_area and keywords columns.

        Returns:
            List of dicts with user_id, expertise_area, category, proficiency.
        """
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT user_id, expertise_area, category, proficiency
                FROM staff_expertise
                WHERE expertise_area LIKE ? OR keywords LIKE ?
                ORDER BY expertise_area
            ''', (f'%{keyword}%', f'%{keyword}%')).fetchall()
            return [dict(row) for row in rows]

    # ==================== OFFICE HOURS ====================

    @staticmethod
    def set_office_hours(user_id: str, day_of_week: str,
                         start_time: str, end_time: str,
                         location: str = None,
                         virtual_link: str = None,
                         is_by_appointment: bool = False,
                         semester: str = None) -> int:
        """Set office hours for a staff member."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO staff_office_hours_directory (
                    user_id, day_of_week, start_time, end_time,
                    location, virtual_link, is_by_appointment, semester
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, day_of_week, start_time, end_time,
                location, virtual_link, int(is_by_appointment), semester,
            ))
            hours_id = cursor.lastrowid
            log_activity('create', 'staff_office_hours', details={
                'hours_id': hours_id, 'user_id': user_id,
                'day_of_week': day_of_week,
            })
            return hours_id

    @staticmethod
    def get_office_hours(user_id: str) -> List[Dict[str, Any]]:
        """Get office hours for a staff member."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM staff_office_hours_directory
                WHERE user_id = ?
                ORDER BY day_of_week, start_time
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_office_hours(hours_id: int, **data) -> None:
        """Update office hours record."""
        if not data:
            return

        allowed_fields = {
            'day_of_week', 'start_time', 'end_time',
            'location', 'virtual_link', 'is_by_appointment', 'semester',
        }

        fields = []
        values = []
        for key, value in data.items():
            if key in allowed_fields:
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        values.append(hours_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE staff_office_hours_directory SET ' + ', '.join(fields)
                + ' WHERE hours_id = ?',
                values)
            log_activity('update', 'staff_office_hours', details={
                'hours_id': hours_id,
                'updated_fields': list(data.keys()),
            })

    @staticmethod
    def remove_office_hours(hours_id: int) -> None:
        """Remove an office hours record."""
        with transaction() as conn:
            conn.execute('''
                DELETE FROM staff_office_hours_directory WHERE hours_id = ?
            ''', (hours_id,))
            log_activity('delete', 'staff_office_hours', details={
                'hours_id': hours_id,
            })

    # ==================== COMBINED PROFILE ====================

    @staticmethod
    def get_full_profile(user_id: str) -> Dict[str, Any]:
        """Get a combined profile with staff info, expertise, and office hours.

        Returns:
            Dict with 'profile', 'expertise', and 'office_hours' keys.
        """
        profile = DirectoryManager.get_staff_profile(user_id)
        expertise_list = DirectoryManager.get_expertise(user_id)
        office_hours_list = DirectoryManager.get_office_hours(user_id)

        return {
            'profile': profile,
            'expertise': expertise_list,
            'office_hours': office_hours_list,
        }
