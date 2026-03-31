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

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608


class DirectoryManager:
    """Manager for staff directory, expertise, and office hours."""

    # ==================== DIRECTORY SEARCH ====================

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
                base = 'SELECT sp.* FROM staff_profiles sp'
                conditions = []
                params: list = []

                if expertise:
                    base += ' JOIN staff_expertise se ON sp.user_id = se.user_id'
                    conditions.append('se.expertise_area LIKE ?')
                    params.append(f'%{expertise}%')

                if query:
                    conditions.append(
                        '(sp.first_name LIKE ? OR sp.last_name LIKE ? OR sp.email LIKE ?)'
                    )
                    params.extend([f'%{query}%', f'%{query}%', f'%{query}%'])

                if department:
                    conditions.append('sp.department = ?')
                    params.append(department)

                if conditions:
                    base += ' WHERE ' + ' AND '.join(conditions)

                base += ' ORDER BY sp.last_name, sp.first_name'
                rows = conn.execute(base, params).fetchall()
                return [dict(row) for row in rows]
        except Exception:
            return []

    @staticmethod
    def get_staff_profile(user_id: str) -> Optional[Dict[str, Any]]:
        """Get a single staff profile by user ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM staff_profiles WHERE user_id = ?
            ''', (user_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_department_staff(department: str) -> List[Dict[str, Any]]:
        """Get all staff members in a department."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM staff_profiles
                WHERE department = ?
                ORDER BY last_name, first_name
            ''', (department,)).fetchall()
            return [dict(row) for row in rows]

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
                INSERT INTO staff_office_hours (
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
                SELECT * FROM staff_office_hours
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
                'UPDATE staff_office_hours SET ' + ', '.join(fields)
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
                DELETE FROM staff_office_hours WHERE hours_id = ?
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
