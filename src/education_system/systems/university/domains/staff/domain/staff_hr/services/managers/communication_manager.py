"""
Communication Manager

Handles staff announcements, committees, meeting minutes,
and noticeboard functionality.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers import (
    _people as people,
)
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.employee_manager import (
    EmployeeManager,
)
from education_system.systems.university.domains.staff.infrastructure.database import staff_hr_ddl

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)

ANNOUNCEMENT_PRIORITIES = ('normal', 'high', 'urgent')
#: How long a notice stays up when no expiry date is given.
NOTICE_DEFAULT_DAYS = 30


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
    def post_announcement(user_id: str, title: str, content: str,
                          category: str = 'general', priority: str = 'normal',
                          target_department: Optional[str] = None,
                          expiry_date: Optional[str] = None) -> int:
        """Post an announcement as a member of staff. It goes straight up for
        those who may run staff operations; anyone else's waits for moderation
        (see :meth:`get_pending_announcements`)."""
        if not str(title or '').strip() or not str(content or '').strip():
            raise ValueError("Title and content are required")
        if priority not in ANNOUNCEMENT_PRIORITIES:
            raise ValueError(f"Priority must be one of {', '.join(ANNOUNCEMENT_PRIORITIES)}")
        with transaction() as conn:
            staff_hr_ddl.apply_to_connection(conn)
            who = people.decider(None, user_id, conn)
            trusted = access.can(who, 'operations', conn)
            cursor = conn.execute('''
                INSERT INTO staff_announcements (
                    title, content, category, target_departments, posted_by,
                    posted_by_name, expiry_date, priority, is_active, moderation_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (title, content, category or 'general', target_department or None,
                  who['username'], access.display_name(who['username'], conn),
                  expiry_date or None, priority, 1 if trusted else 0,
                  'approved' if trusted else 'pending'))
            return cursor.lastrowid

    @staticmethod
    def get_pending_announcements() -> List[Dict[str, Any]]:
        """Announcements waiting for moderation, oldest first."""
        with get_connection() as conn:
            staff_hr_ddl.apply_to_connection(conn)
            rows = conn.execute('''
                SELECT *, COALESCE(posted_by_name, posted_by) AS author_name
                FROM staff_announcements
                WHERE moderation_status = 'pending'
                ORDER BY post_date
            ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def approve_announcement(announcement_id: int,
                             moderated_by: Optional[str] = None) -> bool:
        """Publish a pending announcement. False when none is pending."""
        with transaction() as conn:
            staff_hr_ddl.apply_to_connection(conn)
            cur = conn.execute('''
                UPDATE staff_announcements
                SET moderation_status = 'approved', is_active = 1,
                    moderated_by = ?, moderated_at = ?
                WHERE announcement_id = ? AND moderation_status = 'pending'
            ''', (moderated_by, datetime.now().isoformat(), announcement_id))
            return bool(cur.rowcount)

    @staticmethod
    def reject_announcement(announcement_id: int, reason: Optional[str] = None,
                            moderated_by: Optional[str] = None) -> bool:
        """Turn down a pending announcement. False when none is pending."""
        with transaction() as conn:
            staff_hr_ddl.apply_to_connection(conn)
            cur = conn.execute('''
                UPDATE staff_announcements
                SET moderation_status = 'rejected', is_active = 0,
                    rejection_reason = ?, moderated_by = ?, moderated_at = ?
                WHERE announcement_id = ? AND moderation_status = 'pending'
            ''', (reason, moderated_by, datetime.now().isoformat(), announcement_id))
            return bool(cur.rowcount)

    @staticmethod
    def mark_announcement_read(announcement_id: int, user_id: str) -> bool:
        """Mark an announcement as read by a user."""
        CommunicationManager.mark_announcements_read(user_id, [announcement_id])
        return True

    @staticmethod
    def mark_announcements_read(user_id: str,
                                announcement_ids: Optional[Iterable[int]] = None) -> int:
        """Mark announcements as read by a user: ``announcement_ids``, or
        every current one. Returns how many were newly read; only those count
        as a view."""
        with transaction() as conn:
            staff_hr_ddl.apply_to_connection(conn)
            reader = people.key(user_id, conn)
            if announcement_ids is None:
                announcement_ids = [row[0] for row in conn.execute('''
                    SELECT announcement_id FROM staff_announcements
                    WHERE is_active = 1
                      AND (expiry_date IS NULL OR expiry_date >= date('now'))
                ''').fetchall()]
            marked = 0
            for announcement_id in announcement_ids:
                cur = conn.execute('''
                    INSERT OR IGNORE INTO staff_announcement_reads (announcement_id, user_id)
                    VALUES (?, ?)
                ''', (announcement_id, reader))
                if cur.rowcount:
                    marked += 1
                    conn.execute('''
                        UPDATE staff_announcements
                        SET view_count = view_count + 1
                        WHERE announcement_id = ?
                    ''', (announcement_id,))
            return marked

    @staticmethod
    def get_unread_count(user_id: str) -> int:
        """Get count of unread announcements for a user."""
        with get_connection() as conn:
            staff_hr_ddl.apply_to_connection(conn)
            result = conn.execute('''
                SELECT COUNT(*) FROM staff_announcements sa
                WHERE sa.is_active = 1
                  AND (sa.expiry_date IS NULL OR sa.expiry_date >= date('now'))
                  AND sa.announcement_id NOT IN (
                      SELECT announcement_id FROM staff_announcement_reads
                      WHERE user_id = ?
                  )
            ''', (people.key(user_id, conn),)).fetchone()
            return result[0] if result else 0

    # ==================== COMMITTEES ====================

    @staticmethod
    def get_committees(active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all committees."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT c.*,
                       (SELECT COUNT(*) FROM committee_members m
                        WHERE m.committee_id = c.committee_id AND m.is_active = 1) AS member_count
                FROM committees c
                WHERE (? = 0 OR c.is_active = 1)
                ORDER BY c.name
            ''', (1 if active_only else 0,)).fetchall()
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
    def get_user_committees(user_id: str) -> List[Dict[str, Any]]:
        """The committees a person sits on, with their role in each and the
        committee's next scheduled meeting."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT c.name, c.committee_type, c.status, c.committee_id, cm.role,
                       (SELECT MIN(e.event_date) FROM unified_events e
                        WHERE e.source_type = 'committee'
                          AND e.committee_id = c.committee_id
                          AND e.event_date >= date('now')
                          AND COALESCE(e.status, '') <> 'cancelled') AS next_meeting
                FROM committee_members cm
                JOIN committees c ON cm.committee_id = c.committee_id
                WHERE cm.user_id = ? AND cm.is_active = 1
                ORDER BY c.name
            ''', (people.key(user_id, conn),)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_committee_member(committee_id: int, user_id: str,
                             **data) -> int:
        """Add a member to a committee."""
        with transaction() as conn:
            member = people.key(user_id, conn)
            cursor = conn.execute('''
                INSERT INTO committee_members (
                    committee_id, user_id, user_name, role,
                    start_date, end_date, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (committee_id, member,
                  data.get('user_name') or access.display_name(member, conn),
                  data.get('role', 'member'), data.get('start_date'),
                  data.get('end_date'), data.get('notes')))
            return cursor.lastrowid

    @staticmethod
    def remove_committee_member(committee_id: int, user_id: str) -> bool:
        """Take a member off a committee. False when they were not on it."""
        with transaction() as conn:
            cur = conn.execute('''
                DELETE FROM committee_members
                WHERE committee_id = ? AND user_id = ?
            ''', (committee_id, people.key(user_id, conn)))
            return bool(cur.rowcount)

    @staticmethod
    def get_committee_members(committee_id: int) -> List[Dict[str, Any]]:
        """Get members of a committee."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT cm.*, u.email, u.first_name, u.last_name
                FROM committee_members cm
                LEFT JOIN users u ON u.username = cm.user_id
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
    def get_notices(category: Optional[str] = None,
                    limit: int = 50) -> List[Dict[str, Any]]:
        """Notices currently on the board, newest first."""
        return CommunicationManager.get_noticeboard_posts(category, limit)

    @staticmethod
    def post_notice(user_id: str, title: str, content: str,
                    category: str = 'general',
                    expiry_date: Optional[str] = None) -> int:
        """Put a notice on the board (up for 30 days unless an expiry is given)."""
        if not str(title or '').strip() or not str(content or '').strip():
            raise ValueError("Title and content are required")
        if not expiry_date:
            expiry_date = (date.today() + timedelta(days=NOTICE_DEFAULT_DAYS)).isoformat()
        with get_connection() as conn:
            author = people.key(user_id, conn)
            name = access.display_name(author, conn)
        return CommunicationManager.create_notice(
            author, title, content=content, category=category or 'general',
            posted_by_name=name, expiry_date=expiry_date)

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

    # ==================== STAFF SEARCH ====================

    @staticmethod
    def search_staff(name: Optional[str] = None, department: Optional[str] = None,
                     job_title: Optional[str] = None,
                     limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Find colleagues in the staff directory (directory fields only)."""
        return EmployeeManager.search_employees(name=name, department=department,
                                                job_title=job_title, limit=limit)

    @staticmethod
    def search_by_expertise(expertise: str) -> List[Dict[str, Any]]:
        """Colleagues whose profile or public expertise entries mention
        ``expertise``. ``skills`` lists all of it; ``research_areas`` is the
        part recorded under the research category."""
        needle = str(expertise or '').strip().lower()
        if not needle:
            return []
        with get_connection() as conn:
            entries: Dict[str, List[Dict[str, Any]]] = {}
            for row in conn.execute('''
                SELECT user_id, expertise_area, category, keywords
                FROM staff_expertise WHERE is_public = 1
                ORDER BY expertise_area
            ''').fetchall():
                entries.setdefault(str(row['user_id']), []).append(dict(row))
        out = []
        for person in EmployeeManager.search_employees():
            own = entries.get(str(person['username']), [])
            texts = [person.get('expertise_areas') or '']
            texts += [f"{e['expertise_area']} {e.get('keywords') or ''}" for e in own]
            if not any(needle in text.lower() for text in texts):
                continue
            skills = [person['expertise_areas']] if person.get('expertise_areas') else []
            skills += [e['expertise_area'] for e in own]
            research = [e['expertise_area'] for e in own
                        if str(e.get('category') or '').lower() == 'research']
            out.append({**person, 'skills': ', '.join(skills),
                        'research_areas': ', '.join(research)})
        return out
