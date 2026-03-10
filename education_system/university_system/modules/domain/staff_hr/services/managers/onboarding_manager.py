"""
Onboarding Manager

Handles onboarding/offboarding templates, task assignments,
and progress tracking for new and departing staff.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction

try:
    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


class OnboardingManager:
    """Manager for onboarding/offboarding processes."""

    @staticmethod
    def get_templates(template_type: Optional[str] = None,
                      active_only: bool = True) -> List[Dict[str, Any]]:
        """Get onboarding templates."""
        with get_connection() as conn:
            query = 'SELECT * FROM onboarding_templates WHERE 1=1'
            params = []
            if active_only:
                query += ' AND is_active = 1'
            if template_type:
                query += ' AND template_type = ?'
                params.append(template_type)
            query += ' ORDER BY name'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_template(template_id: int) -> Optional[Dict[str, Any]]:
        """Get a template by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM onboarding_templates WHERE template_id = ?
            ''', (template_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_template(name: str, created_by: str, **data) -> int:
        """Create a new onboarding template."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO onboarding_templates (
                    name, description, role, department,
                    template_type, estimated_days, is_active, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, data.get('description'), data.get('role'),
                  data.get('department'), data.get('template_type', 'onboarding'),
                  data.get('estimated_days', 30), data.get('is_active', 1), created_by))
            return cursor.lastrowid

    @staticmethod
    def get_template_tasks(template_id: int) -> List[Dict[str, Any]]:
        """Get tasks for a template."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM onboarding_template_tasks
                WHERE template_id = ? ORDER BY order_num, task_id
            ''', (template_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_template_task(template_id: int, title: str, **data) -> int:
        """Add a task to a template."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO onboarding_template_tasks (
                    template_id, title, description, category,
                    assigned_to_role, due_days, is_required, order_num
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (template_id, title, data.get('description'),
                  data.get('category', 'general'),
                  data.get('assigned_to_role', 'employee'),
                  data.get('due_days', 0), data.get('is_required', 1),
                  data.get('order_num', 0)))
            return cursor.lastrowid

    @staticmethod
    def assign_template(user_id: str, template_id: int, assigned_by: str,
                        start_date: Optional[str] = None) -> int:
        """Assign a template to a user."""
        start = start_date or datetime.now().strftime('%Y-%m-%d')
        with transaction() as conn:
            template = conn.execute('''
                SELECT estimated_days FROM onboarding_templates WHERE template_id = ?
            ''', (template_id,)).fetchone()
            estimated_days = template[0] if template else 30

            cursor = conn.execute('''
                INSERT INTO onboarding_assignments (
                    user_id, template_id, assigned_by, start_date,
                    target_completion_date, status
                ) VALUES (?, ?, ?, ?, date(?, '+' || ? || ' days'), 'in_progress')
            ''', (user_id, template_id, assigned_by, start, start, estimated_days))
            assignment_id = cursor.lastrowid

            # Create task progress records
            tasks = conn.execute('''
                SELECT task_id, due_days FROM onboarding_template_tasks
                WHERE template_id = ?
            ''', (template_id,)).fetchall()

            for task in tasks:
                conn.execute('''
                    INSERT INTO onboarding_task_progress (
                        assignment_id, task_id, status,
                        due_date
                    ) VALUES (?, ?, 'pending', date(?, '+' || ? || ' days'))
                ''', (assignment_id, task[0], start, task[1]))

            log_activity('assign', 'onboarding', user_id=user_id,
                        details={'assignment_id': assignment_id})
            return assignment_id

    @staticmethod
    def get_assignments(user_id: str,
                        status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get onboarding assignments for a user."""
        with get_connection() as conn:
            query = '''
                SELECT oa.*, ot.name as template_name, ot.template_type
                FROM onboarding_assignments oa
                JOIN onboarding_templates ot ON oa.template_id = ot.template_id
                WHERE oa.user_id = ?
            '''
            params = [user_id]
            if status:
                query += ' AND oa.status = ?'
                params.append(status)
            query += ' ORDER BY oa.start_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_task_progress(assignment_id: int) -> List[Dict[str, Any]]:
        """Get task progress for an assignment."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT tp.*, tt.title, tt.description, tt.category,
                       tt.assigned_to_role, tt.is_required
                FROM onboarding_task_progress tp
                JOIN onboarding_template_tasks tt ON tp.task_id = tt.task_id
                WHERE tp.assignment_id = ?
                ORDER BY tt.order_num, tt.task_id
            ''', (assignment_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def complete_task(progress_id: int, completed_by: str,
                      notes: Optional[str] = None) -> bool:
        """Mark a task as complete."""
        with transaction() as conn:
            conn.execute('''
                UPDATE onboarding_task_progress
                SET status = 'completed', completed_by = ?,
                    completed_date = ?, notes = ?, updated_at = ?
                WHERE progress_id = ?
            ''', (completed_by, datetime.now().isoformat(), notes,
                  datetime.now().isoformat(), progress_id))

            # Check if all required tasks are complete
            progress = conn.execute('''
                SELECT tp.assignment_id FROM onboarding_task_progress tp
                WHERE tp.progress_id = ?
            ''', (progress_id,)).fetchone()

            if progress:
                incomplete = conn.execute('''
                    SELECT COUNT(*) FROM onboarding_task_progress tp
                    JOIN onboarding_template_tasks tt ON tp.task_id = tt.task_id
                    WHERE tp.assignment_id = ?
                      AND tt.is_required = 1 AND tp.status != 'completed'
                ''', (progress[0],)).fetchone()

                if incomplete[0] == 0:
                    conn.execute('''
                        UPDATE onboarding_assignments
                        SET status = 'completed', actual_completion_date = ?,
                            updated_at = ?
                        WHERE assignment_id = ?
                    ''', (datetime.now().isoformat()[:10],
                          datetime.now().isoformat(), progress[0]))

            return True

    @staticmethod
    def get_pending_tasks(user_id: Optional[str] = None,
                          assigned_to: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get pending onboarding tasks."""
        with get_connection() as conn:
            query = '''
                SELECT tp.*, tt.title, tt.description, tt.category,
                       oa.user_id, u.first_name, u.last_name
                FROM onboarding_task_progress tp
                JOIN onboarding_template_tasks tt ON tp.task_id = tt.task_id
                JOIN onboarding_assignments oa ON tp.assignment_id = oa.assignment_id
                LEFT JOIN users u ON oa.user_id = u.id
                WHERE tp.status = 'pending' AND oa.status = 'in_progress'
            '''
            params = []
            if user_id:
                query += ' AND oa.user_id = ?'
                params.append(user_id)
            if assigned_to:
                query += ' AND tp.assigned_to = ?'
                params.append(assigned_to)
            query += ' ORDER BY tp.due_date'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_overdue_tasks() -> List[Dict[str, Any]]:
        """Get overdue onboarding tasks."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT tp.*, tt.title, oa.user_id, u.first_name, u.last_name
                FROM onboarding_task_progress tp
                JOIN onboarding_template_tasks tt ON tp.task_id = tt.task_id
                JOIN onboarding_assignments oa ON tp.assignment_id = oa.assignment_id
                LEFT JOIN users u ON oa.user_id = u.id
                WHERE tp.status = 'pending'
                  AND tp.due_date < date('now')
                  AND oa.status = 'in_progress'
                ORDER BY tp.due_date
            ''').fetchall()
            return [dict(row) for row in rows]
