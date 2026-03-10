"""
Workload Manager - Staff workload tracking and analysis.

Provides functionality for:
- Workload allocation management
- Workload norms configuration
- Workload analysis and balance checking
- Department workload overview
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.core.sql_safety import validate_identifier


class WorkloadManager:
    """Manager for staff workload tracking and analysis."""

    # ==================== ALLOCATION MANAGEMENT ====================

    @staticmethod
    def add_allocation(user_id: str, academic_year: str, activity_name: str,
                       activity_type: str, hours_per_week: float = 0,
                       weighting_factor: float = 1.0, semester: str = None,
                       notes: str = None, created_by: str = None) -> int:
        """Add a workload allocation for a user."""
        weighted_hours = hours_per_week * weighting_factor
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO workload_allocations (
                    user_id, academic_year, activity_name, activity_type,
                    hours_per_week, weighting_factor, weighted_hours,
                    semester, notes, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, academic_year, activity_name, activity_type,
                hours_per_week, weighting_factor, weighted_hours,
                semester, notes, created_by,
                datetime.now().isoformat(),
            ))
            allocation_id = cursor.lastrowid
            log_activity('create', 'workload_allocation', details={
                'allocation_id': allocation_id, 'user_id': user_id,
                'activity_name': activity_name, 'activity_type': activity_type,
            })
            return allocation_id

    @staticmethod
    def get_allocation(allocation_id: int) -> Optional[Dict[str, Any]]:
        """Get a single allocation by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM workload_allocations WHERE allocation_id = ?
            ''', (allocation_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_user_allocations(user_id: str, academic_year: str = None,
                             semester: str = None) -> List[Dict[str, Any]]:
        """Get allocations for a user, optionally filtered by academic year and semester."""
        with get_connection() as conn:
            query = '''
                SELECT * FROM workload_allocations
                WHERE user_id = ?
            '''
            params = [user_id]

            if academic_year:
                query += ' AND academic_year = ?'
                params.append(academic_year)

            if semester:
                query += ' AND semester = ?'
                params.append(semester)

            query += ' ORDER BY activity_type, activity_name'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_allocation(allocation_id: int, **data) -> None:
        """Update allocation fields. Recalculates weighted_hours if hours or weighting changed."""
        allowed_fields = {
            'activity_name', 'activity_type', 'hours_per_week',
            'weighting_factor', 'semester', 'notes',
        }

        fields = []
        values = []
        for key, value in data.items():
            if key in allowed_fields:
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        # Recalculate weighted_hours if hours_per_week or weighting_factor changed
        if 'hours_per_week' in data or 'weighting_factor' in data:
            with get_connection() as conn:
                row = conn.execute('''
                    SELECT hours_per_week, weighting_factor
                    FROM workload_allocations WHERE allocation_id = ?
                ''', (allocation_id,)).fetchone()

            if row:
                current = dict(row)
                hours = data.get('hours_per_week', current['hours_per_week'])
                weighting = data.get('weighting_factor', current['weighting_factor'])
                weighted_hours = hours * weighting
                fields.append('weighted_hours = ?')
                values.append(weighted_hours)

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(allocation_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE workload_allocations SET ' + ', '.join(fields)
                + ' WHERE allocation_id = ?',
                values)
            log_activity('update', 'workload_allocation', details={
                'allocation_id': allocation_id,
                'updated_fields': list(data.keys()),
            })

    @staticmethod
    def remove_allocation(allocation_id: int) -> None:
        """Delete a workload allocation."""
        with transaction() as conn:
            conn.execute('''
                DELETE FROM workload_allocations WHERE allocation_id = ?
            ''', (allocation_id,))
            log_activity('delete', 'workload_allocation', details={
                'allocation_id': allocation_id,
            })

    # ==================== NORMS MANAGEMENT ====================

    @staticmethod
    def create_norm(name: str, teaching_pct: int = 40, research_pct: int = 40,
                    admin_pct: int = 10, service_pct: int = 10,
                    total_hours_per_week: int = 40, department: str = None,
                    role: str = None, is_default: bool = False) -> int:
        """Create a workload norm."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO workload_norms (
                    name, teaching_pct, research_pct, admin_pct, service_pct,
                    total_hours_per_week, department, role, is_default, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name, teaching_pct, research_pct, admin_pct, service_pct,
                total_hours_per_week, department, role, int(is_default),
                datetime.now().isoformat(),
            ))
            norm_id = cursor.lastrowid
            log_activity('create', 'workload_norm', details={
                'norm_id': norm_id, 'name': name,
            })
            return norm_id

    @staticmethod
    def get_norms(department: str = None,
                  role: str = None) -> List[Dict[str, Any]]:
        """Get workload norms, optionally filtered by department and role."""
        with get_connection() as conn:
            query = 'SELECT * FROM workload_norms'
            params = []
            conditions = []

            if department:
                conditions.append('department = ?')
                params.append(department)

            if role:
                conditions.append('role = ?')
                params.append(role)

            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)

            query += ' ORDER BY name'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_norm(norm_id: int) -> Optional[Dict[str, Any]]:
        """Get a single norm by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM workload_norms WHERE norm_id = ?
            ''', (norm_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_norm(norm_id: int, **data) -> None:
        """Update norm fields."""
        allowed_fields = {
            'name', 'teaching_pct', 'research_pct', 'admin_pct', 'service_pct',
            'total_hours_per_week', 'department', 'role', 'is_default',
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
        values.append(norm_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE workload_norms SET ' + ', '.join(fields)
                + ' WHERE norm_id = ?',
                values)
            log_activity('update', 'workload_norm', details={
                'norm_id': norm_id,
                'updated_fields': list(data.keys()),
            })

    @staticmethod
    def delete_norm(norm_id: int) -> None:
        """Delete a workload norm."""
        with transaction() as conn:
            conn.execute('''
                DELETE FROM workload_norms WHERE norm_id = ?
            ''', (norm_id,))
            log_activity('delete', 'workload_norm', details={
                'norm_id': norm_id,
            })

    # ==================== WORKLOAD ANALYSIS ====================

    @staticmethod
    def get_user_workload_summary(user_id: str,
                                  academic_year: str = None) -> Dict[str, Any]:
        """Get workload summary for a user, with hours summed by activity type.

        Returns dict with: user_id, totals by type (teaching, research, admin,
        service), total_hours, allocation_count.
        """
        with get_connection() as conn:
            query = '''
                SELECT activity_type, SUM(weighted_hours) as type_hours,
                       COUNT(*) as type_count
                FROM workload_allocations
                WHERE user_id = ?
            '''
            params = [user_id]

            if academic_year:
                query += ' AND academic_year = ?'
                params.append(academic_year)

            query += ' GROUP BY activity_type'
            rows = conn.execute(query, params).fetchall()

            summary: Dict[str, Any] = {
                'user_id': user_id,
                'teaching': 0,
                'research': 0,
                'admin': 0,
                'service': 0,
                'total_hours': 0,
                'allocation_count': 0,
            }

            for row in rows:
                row_dict = dict(row)
                activity_type = row_dict['activity_type']
                type_hours = row_dict['type_hours'] or 0
                type_count = row_dict['type_count'] or 0

                if activity_type in summary:
                    summary[activity_type] = type_hours

                summary['total_hours'] += type_hours
                summary['allocation_count'] += type_count

            return summary

    @staticmethod
    def get_balance_analysis(user_id: str,
                             academic_year: str = None) -> Dict[str, Any]:
        """Analyse workload balance against applicable norm.

        Gets the user's workload summary, finds the applicable norm
        (by department/role, falling back to default), compares actual
        percentages vs norm percentages, and flags imbalances (diff > 10%).
        """
        summary = WorkloadManager.get_user_workload_summary(user_id, academic_year)

        # Try to find applicable norm by department/role
        norm = None
        with get_connection() as conn:
            # Try to find by user's department and role from staff_profiles
            profile_row = conn.execute('''
                SELECT department, job_title AS role FROM staff_profiles
                WHERE user_id = ?
            ''', (user_id,)).fetchone()

            if profile_row:
                profile = dict(profile_row)
                dept = profile.get('department')
                role = profile.get('role')

                if dept and role:
                    norm_row = conn.execute('''
                        SELECT * FROM workload_norms
                        WHERE department = ? AND role = ?
                        LIMIT 1
                    ''', (dept, role)).fetchone()
                    if norm_row:
                        norm = dict(norm_row)

                if not norm and dept:
                    norm_row = conn.execute('''
                        SELECT * FROM workload_norms
                        WHERE department = ? AND role IS NULL
                        LIMIT 1
                    ''', (dept,)).fetchone()
                    if norm_row:
                        norm = dict(norm_row)

            # Fall back to default norm
            if not norm:
                norm_row = conn.execute('''
                    SELECT * FROM workload_norms
                    WHERE is_default = 1
                    LIMIT 1
                ''').fetchone()
                if norm_row:
                    norm = dict(norm_row)

        # Compare actual percentages vs norm percentages
        total = summary['total_hours'] or 1  # avoid div by zero
        comparison = {}
        for activity_type in ['teaching', 'research', 'admin', 'service']:
            actual_hours = summary.get(activity_type, 0)
            actual_pct = (actual_hours / total) * 100
            norm_pct = norm.get(f'{activity_type}_pct', 0) if norm else 0
            diff = actual_pct - norm_pct
            comparison[activity_type] = {
                'actual_hours': actual_hours,
                'actual_pct': round(actual_pct, 1),
                'norm_pct': norm_pct,
                'difference': round(diff, 1),
                'is_imbalanced': abs(diff) > 10,
            }

        return {
            'summary': summary,
            'norm': norm,
            'comparison': comparison,
        }

    # ==================== DEPARTMENT VIEW ====================

    @staticmethod
    def get_department_workloads(department: str,
                                 academic_year: str = None) -> List[Dict[str, Any]]:
        """Get all staff in a department with their workload summaries.

        Queries workload_allocations grouped by user_id and activity_type,
        then assembles per-user summaries.
        """
        with get_connection() as conn:
            query = '''
                SELECT wa.user_id, wa.activity_type,
                       SUM(wa.weighted_hours) as type_hours,
                       COUNT(*) as type_count
                FROM workload_allocations wa
                JOIN staff_profiles sp ON wa.user_id = sp.user_id
                WHERE sp.department = ?
            '''
            params = [department]

            if academic_year:
                query += ' AND wa.academic_year = ?'
                params.append(academic_year)

            query += ' GROUP BY wa.user_id, wa.activity_type'
            rows = conn.execute(query, params).fetchall()

            # Assemble per-user summaries
            user_map: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                row_dict = dict(row)
                uid = row_dict['user_id']
                activity_type = row_dict['activity_type']
                type_hours = row_dict['type_hours'] or 0
                type_count = row_dict['type_count'] or 0

                if uid not in user_map:
                    user_map[uid] = {
                        'user_id': uid,
                        'department': department,
                        'teaching': 0,
                        'research': 0,
                        'admin': 0,
                        'service': 0,
                        'total_hours': 0,
                        'allocation_count': 0,
                    }

                if activity_type in ('teaching', 'research', 'admin', 'service'):
                    user_map[uid][activity_type] = type_hours

                user_map[uid]['total_hours'] += type_hours
                user_map[uid]['allocation_count'] += type_count

            return list(user_map.values())
