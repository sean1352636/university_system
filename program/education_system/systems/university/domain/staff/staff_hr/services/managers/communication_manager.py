"""
Communication Manager

Handles staff announcements, committees, meeting minutes,
and noticeboard functionality.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import get_connection, transaction

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


class CommunicationManager:
    """Manager for staff communication features."""

    # ==================== ANNOUNCEMENTS ====================

    @staticmethod
    def get_announcements(active_only: bool = True,
                          department: Optional[str] = None,
                          limit: int = 50) -> List[Dict[str, Any]]:
        """Get staff announcements."""
        with get_connection() as conn:
            query = 'SELECT * FROM staff_announcements WHERE 1=1'
            params = []
            if active_only:
                query += ' AND is_active = 1 AND (expiry_date IS NULL OR expiry_date >= date("now"))'
            if department:
                query += ' AND (target_departments IS NULL OR target_departments LIKE ?)'
                params.append(f'%{department}%')
            query += ' ORDER BY is_pinned DESC, post_date DESC LIMIT ?'
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_announcement(posted_by: str, title: str, content: str,
                            **data) -> int:
        """Create a new announcement."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO staff_announcements (
                    title, content, category, target_audience,
                    target_departments, target_roles, posted_by,
                    posted_by_name, expiry_date, is_pinned
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, content, data.get('category', 'general'),
                  data.get('target_audience', 'all'),
                  data.get('target_departments'), data.get('target_roles'),
                  posted_by, data.get('posted_by_name'),
                  data.get('expiry_date'), data.get('is_pinned', 0)))
            return cursor.lastrowid

    @staticmethod
    def mark_announcement_read(announcement_id: int, user_id: str) -> bool:
        """Mark an announcement as read by a user."""
        with transaction() as conn:
            conn.execute('''
                INSERT OR IGNORE INTO announcement_reads (announcement_id, user_id)
                VALUES (?, ?)
            ''', (announcement_id, user_id))
            conn.execute('''
                UPDATE staff_announcements
                SET view_count = view_count + 1
                WHERE announcement_id = ?
            ''', (announcement_id,))
            return True

    @staticmethod
    def get_unread_count(user_id: str) -> int:
        """Get count of unread announcements for a user."""
        with get_connection() as conn:
            result = conn.execute('''
                SELECT COUNT(*) FROM staff_announcements sa
                WHERE sa.is_active = 1
                  AND (sa.expiry_date IS NULL OR sa.expiry_date >= date('now'))
                  AND sa.announcement_id NOT IN (
                      SELECT announcement_id FROM announcement_reads
                      WHERE user_id = ?
                  )
            ''', (user_id,)).fetchone()
            return result[0] if result else 0

    # ==================== COMMITTEES ====================

    @staticmethod
    def get_committees(active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all committees."""
        with get_connection() as conn:
            if active_only:
                rows = conn.execute('''
                    SELECT * FROM committees WHERE is_active = 1 ORDER BY name
                ''').fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM committees ORDER BY name
                ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_committee(name: str, **data) -> int:
        """Create a new committee."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO committees (
                    name, description, committee_type, department,
                    chair_id, chair_name, secretary_id, secretary_name,
                    meeting_frequency, meeting_location
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, data.get('description'),
                  data.get('committee_type', 'standing'),
                  data.get('department'), data.get('chair_id'),
                  data.get('chair_name'), data.get('secretary_id'),
                  data.get('secretary_name'), data.get('meeting_frequency'),
                  data.get('meeting_location')))
            return cursor.lastrowid

    @staticmethod
    def get_committee_memberships(user_id: str) -> List[Dict[str, Any]]:
        """Get committee memberships for a user."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT cm.*, c.name as committee_name, c.committee_type
                FROM committee_members cm
                JOIN committees c ON cm.committee_id = c.committee_id
                WHERE cm.user_id = ? AND cm.is_active = 1
                ORDER BY c.name
            ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_committee_member(committee_id: int, user_id: str,
                             **data) -> int:
        """Add a member to a committee."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO committee_members (
                    committee_id, user_id, user_name, role,
                    start_date, end_date, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (committee_id, user_id, data.get('user_name'),
                  data.get('role', 'member'), data.get('start_date'),
                  data.get('end_date'), data.get('notes')))
            return cursor.lastrowid

    @staticmethod
    def get_committee_members(committee_id: int) -> List[Dict[str, Any]]:
        """Get members of a committee."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT cm.*, u.email, u.first_name, u.last_name
                FROM committee_members cm
                LEFT JOIN users u ON cm.user_id = u.id
                WHERE cm.committee_id = ? AND cm.is_active = 1
                ORDER BY cm.role, cm.user_name
            ''', (committee_id,)).fetchall()
            return [dict(row) for row in rows]

    # ==================== MEETING MINUTES ====================

    @staticmethod
    def get_meeting_minutes(committee_id: Optional[int] = None,
                            limit: int = 20) -> List[Dict[str, Any]]:
        """Get meeting minutes."""
        with get_connection() as conn:
            if committee_id:
                rows = conn.execute('''
                    SELECT * FROM meeting_minutes
                    WHERE committee_id = ?
                    ORDER BY meeting_date DESC LIMIT ?
                ''', (committee_id, limit)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM meeting_minutes
                    ORDER BY meeting_date DESC LIMIT ?
                ''', (limit,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_minutes(meeting_title: str, meeting_date: str,
                       recorded_by: str, **data) -> int:
        """Create meeting minutes."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO meeting_minutes (
                    committee_id, committee_name, meeting_title, meeting_date,
                    meeting_time, location, attendees, apologies, agenda,
                    minutes_content, action_items, decisions, next_meeting_date,
                    recorded_by, recorded_by_name, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (data.get('committee_id'), data.get('committee_name'),
                  meeting_title, meeting_date, data.get('meeting_time'),
                  data.get('location'), data.get('attendees'),
                  data.get('apologies'), data.get('agenda'),
                  data.get('minutes_content'), data.get('action_items'),
                  data.get('decisions'), data.get('next_meeting_date'),
                  recorded_by, data.get('recorded_by_name'),
                  data.get('status', 'draft')))
            return cursor.lastrowid

    @staticmethod
    def approve_minutes(minutes_id: int, approved_by: str) -> bool:
        """Approve meeting minutes."""
        with transaction() as conn:
            conn.execute('''
                UPDATE meeting_minutes
                SET status = 'approved', approved_by = ?, approved_date = ?
                WHERE minutes_id = ?
            ''', (approved_by, datetime.now().isoformat(), minutes_id))
            return True

    # ==================== NOTICEBOARD ====================

    @staticmethod
    def get_noticeboard_posts(category: Optional[str] = None,
                              limit: int = 50) -> List[Dict[str, Any]]:
        """Get noticeboard posts."""
        with get_connection() as conn:
            query = '''
                SELECT * FROM staff_noticeboard
                WHERE is_active = 1
                  AND (expiry_date IS NULL OR expiry_date >= date('now'))
            '''
            params = []
            if category:
                query += ' AND category = ?'
                params.append(category)
            query += ' ORDER BY post_date DESC LIMIT ?'
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def create_notice(posted_by: str, title: str, **data) -> int:
        """Create a noticeboard post."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO staff_noticeboard (
                    title, content, category, posted_by, posted_by_name,
                    contact_info, expiry_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (title, data.get('content'), data.get('category', 'general'),
                  posted_by, data.get('posted_by_name'),
                  data.get('contact_info'), data.get('expiry_date')))
            return cursor.lastrowid

    @staticmethod
    def delete_notice(notice_id: int, user_id: str) -> bool:
        """Delete a noticeboard post (only by owner)."""
        with transaction() as conn:
            result = conn.execute('''
                UPDATE staff_noticeboard SET is_active = 0
                WHERE notice_id = ? AND posted_by = ?
            ''', (notice_id, user_id))
            return result.rowcount > 0

    @staticmethod
    def get_noticeboard_categories() -> List[str]:
        """Get available noticeboard categories."""
        return ['for_sale', 'wanted', 'events', 'lost_found',
                'housing', 'carpool', 'general']
