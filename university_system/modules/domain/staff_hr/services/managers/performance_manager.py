"""
Performance Manager

Handles appraisal cycles, performance reviews,
goals tracking, and development plans.
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


class PerformanceManager:
    """Manager for performance appraisals and goals."""

    @staticmethod
    def get_active_cycle() -> Optional[Dict[str, Any]]:
        """Get the current active appraisal cycle."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM appraisal_cycles
                WHERE status = 'active'
                ORDER BY start_date DESC LIMIT 1
            ''').fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_cycles(status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all appraisal cycles."""
        with get_connection() as conn:
            if status:
                rows = conn.execute('''
                    SELECT * FROM appraisal_cycles WHERE status = ?
                    ORDER BY start_date DESC
                ''', (status,)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM appraisal_cycles ORDER BY start_date DESC
                ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_cycle(name: str, start_date: str, end_date: str,
                     created_by: str, **data) -> int:
        """Create a new appraisal cycle."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO appraisal_cycles (
                    name, description, start_date, end_date,
                    self_review_deadline, manager_review_deadline,
                    status, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, data.get('description'), start_date, end_date,
                  data.get('self_review_deadline'), data.get('manager_review_deadline'),
                  data.get('status', 'draft'), created_by))
            cycle_id = cursor.lastrowid
            log_activity('create', 'appraisal_cycle', details={'cycle_id': cycle_id})
            return cycle_id

    @staticmethod
    def activate_cycle(cycle_id: int) -> bool:
        """Activate an appraisal cycle."""
        with transaction() as conn:
            conn.execute('''
                UPDATE appraisal_cycles SET status = 'inactive'
                WHERE status = 'active'
            ''')
            conn.execute('''
                UPDATE appraisal_cycles SET status = 'active', updated_at = ?
                WHERE cycle_id = ?
            ''', (datetime.now().isoformat(), cycle_id))
            return True

    @staticmethod
    def get_appraisal(user_id: str, cycle_id: int) -> Optional[Dict[str, Any]]:
        """Get a user's appraisal record for a cycle."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM appraisal_records
                WHERE user_id = ? AND cycle_id = ?
            ''', (user_id, cycle_id)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_appraisal(user_id: str, cycle_id: int,
                         reviewer_id: Optional[str] = None) -> int:
        """Create an appraisal record for a user."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO appraisal_records (user_id, cycle_id, reviewer_id)
                VALUES (?, ?, ?)
            ''', (user_id, cycle_id, reviewer_id))
            return cursor.lastrowid

    @staticmethod
    def submit_self_review(user_id: str, cycle_id: int, self_rating: float,
                           self_comments: str, **data) -> bool:
        """Submit self-review for an appraisal."""
        with transaction() as conn:
            existing = conn.execute('''
                SELECT appraisal_id FROM appraisal_records
                WHERE user_id = ? AND cycle_id = ?
            ''', (user_id, cycle_id)).fetchone()

            if existing:
                conn.execute('''
                    UPDATE appraisal_records
                    SET self_rating = ?, self_comments = ?,
                        self_submitted_date = ?, status = 'self_review_complete',
                        updated_at = ?
                    WHERE appraisal_id = ?
                ''', (self_rating, self_comments, datetime.now().isoformat(),
                      datetime.now().isoformat(), existing[0]))
            else:
                conn.execute('''
                    INSERT INTO appraisal_records (
                        user_id, cycle_id, self_rating, self_comments,
                        self_submitted_date, status
                    ) VALUES (?, ?, ?, ?, ?, 'self_review_complete')
                ''', (user_id, cycle_id, self_rating, self_comments,
                      datetime.now().isoformat()))
            log_activity('submit', 'self_review', user_id=user_id,
                        details={'cycle_id': cycle_id})
            return True

    @staticmethod
    def submit_manager_review(reviewer_id: str, user_id: str, cycle_id: int,
                              manager_rating: float, manager_comments: str,
                              **data) -> bool:
        """Submit manager review for an appraisal."""
        with transaction() as conn:
            conn.execute('''
                UPDATE appraisal_records
                SET reviewer_id = ?, manager_rating = ?, manager_comments = ?,
                    final_rating = ?, strengths = ?, areas_for_improvement = ?,
                    development_plan = ?, manager_submitted_date = ?,
                    status = 'completed', updated_at = ?
                WHERE user_id = ? AND cycle_id = ?
            ''', (reviewer_id, manager_rating, manager_comments,
                  data.get('final_rating', manager_rating),
                  data.get('strengths'), data.get('areas_for_improvement'),
                  data.get('development_plan'), datetime.now().isoformat(),
                  datetime.now().isoformat(), user_id, cycle_id))
            log_activity('submit', 'manager_review', details={
                'reviewer': reviewer_id, 'user_id': user_id, 'cycle_id': cycle_id
            })
            return True

    @staticmethod
    def get_goals(user_id: str, cycle_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get goals for a user."""
        with get_connection() as conn:
            if cycle_id:
                rows = conn.execute('''
                    SELECT * FROM appraisal_goals
                    WHERE user_id = ? AND cycle_id = ?
                    ORDER BY target_date
                ''', (user_id, cycle_id)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM appraisal_goals
                    WHERE user_id = ? ORDER BY target_date
                ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_goal(user_id: str, title: str, **data) -> int:
        """Add a goal for a user."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO appraisal_goals (
                    user_id, cycle_id, title, description, category,
                    target_date, weight, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, data.get('cycle_id'), title, data.get('description'),
                  data.get('category', 'performance'), data.get('target_date'),
                  data.get('weight', 1.0), data.get('status', 'active')))
            return cursor.lastrowid

    @staticmethod
    def update_goal_progress(goal_id: int, progress: int,
                             notes: Optional[str] = None) -> bool:
        """Update goal progress."""
        with transaction() as conn:
            status = 'completed' if progress >= 100 else 'active'
            conn.execute('''
                UPDATE appraisal_goals
                SET progress = ?, status = ?, completion_notes = ?, updated_at = ?
                WHERE goal_id = ?
            ''', (progress, status, notes, datetime.now().isoformat(), goal_id))
            return True

    @staticmethod
    def get_pending_reviews(reviewer_id: str) -> List[Dict[str, Any]]:
        """Get appraisals pending manager review."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT ar.*, p.department, p.job_title,
                       u.first_name, u.last_name, ac.name as cycle_name
                FROM appraisal_records ar
                JOIN appraisal_cycles ac ON ar.cycle_id = ac.cycle_id
                LEFT JOIN staff_profiles p ON ar.user_id = p.user_id
                LEFT JOIN users u ON ar.user_id = u.id
                WHERE ar.status = 'self_review_complete'
                  AND (ar.reviewer_id = ? OR p.manager_id = ?)
                ORDER BY ar.self_submitted_date
            ''', (reviewer_id, reviewer_id)).fetchall()
            return [dict(row) for row in rows]
