"""
Employee Manager

Handles staff profile management, documents, qualifications,
emergency contacts, workload allocation, and directory search.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from university_system.infrastructure.database.db import get_connection, transaction

try:
    from university_system.modules.shared.utils.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


class EmployeeManager:
    """Manager for staff profiles and employee data."""

    # ==================== PROFILE OPERATIONS ====================

    @staticmethod
    def get_profile(user_id: str) -> Optional[Dict[str, Any]]:
        """Get staff profile by user ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM staff_profiles WHERE user_id = ?
            ''', (user_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_profile(user_id: str, **data) -> int:
        """Create a new staff profile."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO staff_profiles (
                    user_id, employee_id, department, job_title,
                    employment_type, hire_date, contract_end_date,
                    manager_id, office_location, phone_extension,
                    emergency_contact_name, emergency_contact_phone,
                    emergency_contact_relationship, bio,
                    expertise_areas, qualifications
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                data.get('employee_id'),
                data.get('department'),
                data.get('job_title'),
                data.get('employment_type', 'full-time'),
                data.get('hire_date'),
                data.get('contract_end_date'),
                data.get('manager_id'),
                data.get('office_location'),
                data.get('phone_extension'),
                data.get('emergency_contact_name'),
                data.get('emergency_contact_phone'),
                data.get('emergency_contact_relationship'),
                data.get('bio'),
                data.get('expertise_areas'),
                data.get('qualifications'),
            ))
            profile_id = cursor.lastrowid
            log_activity('create', 'staff_profile', user_id=user_id,
                        details={'profile_id': profile_id})
            return profile_id

    @staticmethod
    def update_profile(user_id: str, **data) -> bool:
        """Update staff profile fields."""
        if not data:
            return False

        # Build dynamic update query
        fields = []
        values = []
        for key, value in data.items():
            if key not in ('user_id', 'profile_id', 'created_at'):
                fields.append(f'{key} = ?')
                values.append(value)

        if not fields:
            return False

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(user_id)

        with transaction() as conn:
            conn.execute(f'''
                UPDATE staff_profiles
                SET {', '.join(fields)}
                WHERE user_id = ?
            ''', values)
            log_activity('update', 'staff_profile', user_id=user_id,
                        details={'updated_fields': list(data.keys())})
            return True

    @staticmethod
    def update_emergency_contact(user_id: str, name: str, phone: str,
                                  relationship: str) -> bool:
        """Update emergency contact information."""
        with transaction() as conn:
            conn.execute('''
                UPDATE staff_profiles
                SET emergency_contact_name = ?,
                    emergency_contact_phone = ?,
                    emergency_contact_relationship = ?,
                    updated_at = ?
                WHERE user_id = ?
            ''', (name, phone, relationship, datetime.now().isoformat(), user_id))
            log_activity('update', 'emergency_contact', user_id=user_id)
            return True

    # ==================== DOCUMENT OPERATIONS ====================

    @staticmethod
    def get_documents(user_id: str, doc_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all documents for a user, optionally filtered by type."""
        with get_connection() as conn:
            if doc_type:
                rows = conn.execute('''
                    SELECT * FROM staff_documents
                    WHERE user_id = ? AND document_type = ?
                    ORDER BY created_at DESC
                ''', (user_id, doc_type)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM staff_documents
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_document(user_id: str, doc_type: str, doc_name: str,
                     file_path: Optional[str] = None, **data) -> int:
        """Add a new document to a staff profile."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO staff_documents (
                    user_id, document_type, document_name, file_path,
                    issue_date, expiry_date, status, uploaded_by, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                doc_type,
                doc_name,
                file_path,
                data.get('issue_date'),
                data.get('expiry_date'),
                data.get('status', 'active'),
                data.get('uploaded_by'),
                data.get('notes'),
            ))
            doc_id = cursor.lastrowid
            log_activity('create', 'staff_document', user_id=user_id,
                        details={'document_id': doc_id, 'type': doc_type})
            return doc_id

    @staticmethod
    def update_document(document_id: int, **data) -> bool:
        """Update a document record."""
        if not data:
            return False

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('document_id', 'user_id', 'created_at'):
                fields.append(f'{key} = ?')
                values.append(value)

        if not fields:
            return False

        values.append(document_id)

        with transaction() as conn:
            conn.execute(f'''
                UPDATE staff_documents
                SET {', '.join(fields)}
                WHERE document_id = ?
            ''', values)
            log_activity('update', 'staff_document',
                        details={'document_id': document_id})
            return True

    @staticmethod
    def delete_document(document_id: int) -> bool:
        """Delete a document record."""
        with transaction() as conn:
            conn.execute('DELETE FROM staff_documents WHERE document_id = ?',
                        (document_id,))
            log_activity('delete', 'staff_document',
                        details={'document_id': document_id})
            return True

    @staticmethod
    def get_expiring_documents(days: int = 30) -> List[Dict[str, Any]]:
        """Get documents expiring within the specified number of days."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT d.*, p.department, p.job_title
                FROM staff_documents d
                LEFT JOIN staff_profiles p ON d.user_id = p.user_id
                WHERE d.expiry_date IS NOT NULL
                  AND d.expiry_date <= date('now', '+' || ? || ' days')
                  AND d.expiry_date >= date('now')
                  AND d.status = 'active'
                ORDER BY d.expiry_date
            ''', (days,)).fetchall()
            return [dict(row) for row in rows]

    # ==================== WORKLOAD OPERATIONS ====================

    @staticmethod
    def get_workload(user_id: str, academic_year: Optional[str] = None,
                     semester: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get workload allocation for a user."""
        with get_connection() as conn:
            query = 'SELECT * FROM staff_workload WHERE user_id = ?'
            params = [user_id]

            if academic_year:
                query += ' AND academic_year = ?'
                params.append(academic_year)
            if semester:
                query += ' AND semester = ?'
                params.append(semester)

            query += ' ORDER BY academic_year DESC, semester DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def set_workload(user_id: str, academic_year: str, semester: str,
                     **hours) -> int:
        """Set or update workload allocation for a user."""
        with transaction() as conn:
            # Check if record exists
            existing = conn.execute('''
                SELECT workload_id FROM staff_workload
                WHERE user_id = ? AND academic_year = ? AND semester = ?
            ''', (user_id, academic_year, semester)).fetchone()

            if existing:
                # Update existing record
                conn.execute('''
                    UPDATE staff_workload
                    SET teaching_hours = ?,
                        research_hours = ?,
                        admin_hours = ?,
                        service_hours = ?,
                        total_fte = ?,
                        notes = ?,
                        updated_at = ?
                    WHERE workload_id = ?
                ''', (
                    hours.get('teaching_hours', 0),
                    hours.get('research_hours', 0),
                    hours.get('admin_hours', 0),
                    hours.get('service_hours', 0),
                    hours.get('total_fte', 1.0),
                    hours.get('notes'),
                    datetime.now().isoformat(),
                    existing[0],
                ))
                log_activity('update', 'staff_workload', user_id=user_id,
                            details={'workload_id': existing[0]})
                return existing[0]
            else:
                # Create new record
                cursor = conn.execute('''
                    INSERT INTO staff_workload (
                        user_id, academic_year, semester,
                        teaching_hours, research_hours, admin_hours,
                        service_hours, total_fte, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    academic_year,
                    semester,
                    hours.get('teaching_hours', 0),
                    hours.get('research_hours', 0),
                    hours.get('admin_hours', 0),
                    hours.get('service_hours', 0),
                    hours.get('total_fte', 1.0),
                    hours.get('notes'),
                ))
                workload_id = cursor.lastrowid
                log_activity('create', 'staff_workload', user_id=user_id,
                            details={'workload_id': workload_id})
                return workload_id

    # ==================== SCHEDULE OPERATIONS ====================

    @staticmethod
    def get_schedules(user_id: str) -> List[Dict[str, Any]]:
        """Get all schedules for a user."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM staff_schedules
                WHERE user_id = ?
                ORDER BY day_of_week, start_time
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_schedule(user_id: str, day_of_week: int, start_time: str,
                     end_time: str, **data) -> int:
        """Add a schedule entry for a user."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO staff_schedules (
                    user_id, day_of_week, start_time, end_time,
                    location, schedule_type, is_recurring,
                    effective_from, effective_to, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                day_of_week,
                start_time,
                end_time,
                data.get('location'),
                data.get('schedule_type', 'office_hours'),
                data.get('is_recurring', 1),
                data.get('effective_from'),
                data.get('effective_to'),
                data.get('notes'),
            ))
            schedule_id = cursor.lastrowid
            log_activity('create', 'staff_schedule', user_id=user_id,
                        details={'schedule_id': schedule_id})
            return schedule_id

    @staticmethod
    def delete_schedule(schedule_id: int) -> bool:
        """Delete a schedule entry."""
        with transaction() as conn:
            conn.execute('DELETE FROM staff_schedules WHERE schedule_id = ?',
                        (schedule_id,))
            log_activity('delete', 'staff_schedule',
                        details={'schedule_id': schedule_id})
            return True

    # ==================== DIRECTORY OPERATIONS ====================

    @staticmethod
    def search_directory(search: Optional[str] = None,
                         department: Optional[str] = None,
                         expertise: Optional[str] = None,
                         limit: int = 50,
                         offset: int = 0) -> List[Dict[str, Any]]:
        """Search staff directory with optional filters."""
        with get_connection() as conn:
            query = '''
                SELECT p.*, u.username, u.email, u.first_name, u.last_name
                FROM staff_profiles p
                LEFT JOIN users u ON p.user_id = u.id
                WHERE 1=1
            '''
            params = []

            if search:
                query += '''
                    AND (p.user_id LIKE ?
                         OR p.employee_id LIKE ?
                         OR p.job_title LIKE ?
                         OR p.expertise_areas LIKE ?
                         OR u.first_name LIKE ?
                         OR u.last_name LIKE ?
                         OR u.email LIKE ?)
                '''
                search_term = f'%{search}%'
                params.extend([search_term] * 7)

            if department:
                query += ' AND p.department = ?'
                params.append(department)

            if expertise:
                query += ' AND p.expertise_areas LIKE ?'
                params.append(f'%{expertise}%')

            query += ' ORDER BY p.department, p.job_title LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_directory_count(search: Optional[str] = None,
                            department: Optional[str] = None,
                            expertise: Optional[str] = None) -> int:
        """Get total count for directory search."""
        with get_connection() as conn:
            query = '''
                SELECT COUNT(*) FROM staff_profiles p
                LEFT JOIN users u ON p.user_id = u.id
                WHERE 1=1
            '''
            params = []

            if search:
                query += '''
                    AND (p.user_id LIKE ?
                         OR p.employee_id LIKE ?
                         OR p.job_title LIKE ?
                         OR p.expertise_areas LIKE ?
                         OR u.first_name LIKE ?
                         OR u.last_name LIKE ?
                         OR u.email LIKE ?)
                '''
                search_term = f'%{search}%'
                params.extend([search_term] * 7)

            if department:
                query += ' AND p.department = ?'
                params.append(department)

            if expertise:
                query += ' AND p.expertise_areas LIKE ?'
                params.append(f'%{expertise}%')

            result = conn.execute(query, params).fetchone()
            return result[0] if result else 0

    @staticmethod
    def get_departments() -> List[str]:
        """Get list of all departments from profiles."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT DISTINCT department FROM staff_profiles
                WHERE department IS NOT NULL AND department != ''
                ORDER BY department
            ''').fetchall()
            return [row[0] for row in rows]

    @staticmethod
    def get_staff_by_manager(manager_id: str) -> List[Dict[str, Any]]:
        """Get all staff reporting to a manager."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT p.*, u.email, u.first_name, u.last_name
                FROM staff_profiles p
                LEFT JOIN users u ON p.user_id = u.id
                WHERE p.manager_id = ?
                ORDER BY p.job_title
            ''', (manager_id,)).fetchall()
            return [dict(row) for row in rows]
