"""
Time Manager

Handles time entries, clock in/out, timesheets,
attendance tracking, and time reports.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction

try:
    from education_system.university_system.core.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


class TimeManager:
    """Manager for time and attendance tracking."""

    @staticmethod
    def clock_in(user_id: str, location: str = 'office',
                 work_type: str = 'regular', notes: Optional[str] = None) -> int:
        """Record clock-in time for a user."""
        now = datetime.now()
        with transaction() as conn:
            existing = conn.execute('''
                SELECT entry_id FROM time_entries
                WHERE user_id = ? AND entry_date = ? AND clock_out IS NULL
            ''', (user_id, now.strftime('%Y-%m-%d'))).fetchone()

            if existing:
                raise ValueError("Already clocked in. Please clock out first.")

            cursor = conn.execute('''
                INSERT INTO time_entries (
                    user_id, entry_date, clock_in, work_type, location, notes
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S'),
                  work_type, location, notes))
            entry_id = cursor.lastrowid
            log_activity('clock_in', 'time_entry', user_id=user_id,
                        details={'entry_id': entry_id})
            return entry_id

    @staticmethod
    def clock_out(user_id: str, notes: Optional[str] = None) -> bool:
        """Record clock-out time for a user."""
        now = datetime.now()
        with transaction() as conn:
            entry = conn.execute('''
                SELECT entry_id FROM time_entries
                WHERE user_id = ? AND entry_date = ? AND clock_out IS NULL
            ''', (user_id, now.strftime('%Y-%m-%d'))).fetchone()

            if not entry:
                raise ValueError("No active clock-in found.")

            conn.execute('''
                UPDATE time_entries
                SET clock_out = ?, updated_at = ?
                WHERE entry_id = ?
            ''', (now.strftime('%H:%M:%S'), now.isoformat(), entry[0]))
            log_activity('clock_out', 'time_entry', user_id=user_id,
                        details={'entry_id': entry[0]})
            return True

    @staticmethod
    def get_current_status(user_id: str) -> Optional[Dict[str, Any]]:
        """Check if user is currently clocked in."""
        today = datetime.now().strftime('%Y-%m-%d')
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM time_entries
                WHERE user_id = ? AND entry_date = ? AND clock_out IS NULL
            ''', (user_id, today)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_entries(user_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get time entries for a user within a date range."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM time_entries
                WHERE user_id = ? AND entry_date BETWEEN ? AND ?
                ORDER BY entry_date DESC, clock_in DESC
            ''', (user_id, start_date, end_date)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_manual_entry(user_id: str, entry_date: str, clock_in: str,
                         clock_out: str, **data) -> int:
        """Add a manual time entry."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO time_entries (
                    user_id, entry_date, clock_in, clock_out,
                    break_minutes, work_type, location, notes, is_manual
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            ''', (user_id, entry_date, clock_in, clock_out,
                  data.get('break_minutes', 0), data.get('work_type', 'regular'),
                  data.get('location', 'office'), data.get('notes')))
            return cursor.lastrowid

    @staticmethod
    def get_timesheet(user_id: str, week_start: str) -> Optional[Dict[str, Any]]:
        """Get a timesheet for a specific week."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM timesheets WHERE user_id = ? AND week_start = ?
            ''', (user_id, week_start)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def submit_timesheet(timesheet_id: int) -> bool:
        """Submit a timesheet for approval."""
        with transaction() as conn:
            conn.execute('''
                UPDATE timesheets
                SET status = 'submitted', submitted_date = ?, updated_at = ?
                WHERE timesheet_id = ? AND status = 'draft'
            ''', (datetime.now().isoformat(), datetime.now().isoformat(), timesheet_id))
            return True

    @staticmethod
    def approve_timesheet(timesheet_id: int, approver_id: str) -> bool:
        """Approve a timesheet."""
        with transaction() as conn:
            conn.execute('''
                UPDATE timesheets
                SET status = 'approved', approved_by = ?, approved_date = ?, updated_at = ?
                WHERE timesheet_id = ? AND status = 'submitted'
            ''', (approver_id, datetime.now().isoformat(),
                  datetime.now().isoformat(), timesheet_id))
            return True

    @staticmethod
    def get_pending_approvals(approver_id: str) -> List[Dict[str, Any]]:
        """Get timesheets pending approval."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT t.*, p.department, u.first_name, u.last_name
                FROM timesheets t
                LEFT JOIN staff_profiles p ON t.user_id = p.user_id
                LEFT JOIN users u ON t.user_id = u.id
                WHERE t.status = 'submitted'
                ORDER BY t.submitted_date
            ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_attendance_report(department: Optional[str] = None,
                              start_date: Optional[str] = None,
                              end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get attendance report."""
        start = start_date or (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        end = end_date or datetime.now().strftime('%Y-%m-%d')

        with get_connection() as conn:
            query = '''
                SELECT p.user_id, p.department, u.first_name, u.last_name,
                       COUNT(DISTINCT te.entry_date) as days_worked
                FROM staff_profiles p
                LEFT JOIN users u ON p.user_id = u.id
                LEFT JOIN time_entries te ON p.user_id = te.user_id
                    AND te.entry_date BETWEEN ? AND ?
                WHERE 1=1
            '''
            params = [start, end]

            if department:
                query += ' AND p.department = ?'
                params.append(department)

            query += ' GROUP BY p.user_id ORDER BY p.department'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
