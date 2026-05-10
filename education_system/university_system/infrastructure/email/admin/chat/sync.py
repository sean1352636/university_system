"""SyncMixin — extracted from chat.py."""
from __future__ import annotations

from education_system.university_system.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)


class SyncMixin:
    """Methods grouped from the original _ChatMixin."""

    @handle_exception
    def sync_course_chat_rooms(self):
        """Best-effort: ensure a chat room exists for every module the
        current user is enrolled in or instructs, and that the user is a
        member. Returns the number of rooms created/updated."""
        if not self.auth or not self.auth.current_user:
            return 0
        user_id = self.auth.current_user['id']
        username = self.auth.current_user.get('username') or ''
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _sync(cursor):
            modules = []
            try:
                cursor.execute('''
                    SELECT m.module_code, m.module_name
                    FROM modules m
                    JOIN student_modules sm ON sm.module_code = m.module_code
                    JOIN students s ON s.student_id = sm.student_id
                    WHERE s.user_id = ? OR s.student_id = ?
                ''', (user_id, username))
                modules = list(cursor.fetchall())
            except Exception:
                # Schema may not be present in this DB; skip silently.
                modules = []
            try:
                cursor.execute('''
                    SELECT module_code, module_name FROM modules
                    WHERE instructor_id = ? OR instructor_id = ?
                ''', (user_id, str(user_id)))
                modules.extend(cursor.fetchall())
            except Exception:
                pass

            seen, count = set(), 0
            for code, name in modules:
                if not code or code in seen:
                    continue
                seen.add(code)
                cursor.execute(
                    'SELECT id FROM chat_rooms WHERE linked_course_code = ?', (code,),
                )
                row = cursor.fetchone()
                if row:
                    room_id = row[0]
                else:
                    room_name = f"{code} — {name}" if name else str(code)
                    cursor.execute(
                        '''INSERT INTO chat_rooms
                           (name, description, room_type, created_by, created_at,
                            is_active, category, linked_course_code)
                           VALUES (?, ?, 'course', ?, ?, 1, 'Courses', ?)''',
                        (room_name[:100], f"Auto-linked to module {code}",
                         user_id, now, code),
                    )
                    room_id = cursor.lastrowid
                    count += 1
                # Ensure the user is a member (admin if instructor, else member).
                cursor.execute(
                    'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                    (room_id, user_id),
                )
                if not cursor.fetchone():
                    cursor.execute(
                        '''INSERT INTO chat_room_members
                           (room_id, user_id, joined_at, is_admin)
                           VALUES (?, ?, ?, 0)''',
                        (room_id, user_id, now),
                    )
            return count

        try:
            return execute_db_operation(_sync)
        except Exception as e:
            log_event('error', f"Error syncing course chat rooms: {e}")
            return 0

    @handle_exception
    def sync_assignment_group_room(self, group_id):
        """Ensure a chat room exists for an assignment group and that all its
        members are joined. Caller must be a group member or an admin."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _sync(cursor):
            try:
                cursor.execute(
                    'SELECT group_name, assignment_id FROM assignment_groups WHERE id = ?',
                    (group_id,),
                )
                row = cursor.fetchone()
            except Exception:
                return False
            if not row:
                return False
            group_name = row[0]
            try:
                cursor.execute(
                    'SELECT student_id FROM assignment_group_members WHERE group_id = ?',
                    (group_id,),
                )
                member_ids = [r[0] for r in cursor.fetchall()]
            except Exception:
                member_ids = []

            cursor.execute(
                'SELECT id FROM chat_rooms WHERE linked_assignment_group_id = ?',
                (group_id,),
            )
            r = cursor.fetchone()
            if r:
                room_id = r[0]
            else:
                cursor.execute(
                    '''INSERT INTO chat_rooms
                       (name, description, room_type, created_by, created_at,
                        is_active, category, linked_assignment_group_id)
                       VALUES (?, ?, 'private', ?, ?, 1, 'Group projects', ?)''',
                    (f"Group: {group_name}"[:100],
                     f"Auto-linked to assignment group {group_id}",
                     user_id, now, group_id),
                )
                room_id = cursor.lastrowid
            for mid in set(member_ids + [user_id]):
                cursor.execute(
                    'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                    (room_id, mid),
                )
                if not cursor.fetchone():
                    is_admin = 1 if mid == user_id else 0
                    cursor.execute(
                        '''INSERT INTO chat_room_members
                           (room_id, user_id, joined_at, is_admin)
                           VALUES (?, ?, ?, ?)''',
                        (room_id, mid, now, is_admin),
                    )
            return room_id

        try:
            return execute_db_operation(_sync)
        except Exception as e:
            log_event('error', f"Error syncing group chat room: {e}")
            return False

    @handle_exception
    def get_or_create_linked_room(self, entity_type, entity_id, *, name,
                                  description=None, room_type='private',
                                  category=None, icon=None,
                                  invite_user_ids=None,
                                  oh_starts_at=None, oh_ends_at=None,
                                  announcement_mode=False):
        """Find or create a chat room linked to an external entity.

        Caller-supplied entity_type/entity_id pair is the unique key. If a room
        already exists, the caller is added as a member if missing, plus any
        users in invite_user_ids. Returns the room id (or False on failure)."""
        if not self.auth or not self.auth.current_user:
            return False
        if not entity_type or entity_id is None:
            return False
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        eid_str = str(entity_id)

        def _go(cursor):
            cursor.execute(
                'SELECT id FROM chat_rooms WHERE linked_entity_type = ? AND linked_entity_id = ?',
                (entity_type, eid_str),
            )
            row = cursor.fetchone()
            if row:
                room_id = row[0]
            else:
                cursor.execute(
                    '''INSERT INTO chat_rooms
                       (name, description, room_type, created_by, created_at,
                        is_active, category, icon,
                        linked_entity_type, linked_entity_id,
                        oh_starts_at, oh_ends_at, announcement_mode)
                       VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)''',
                    (name[:100], description, room_type, user_id, now,
                     category, icon, entity_type, eid_str,
                     oh_starts_at, oh_ends_at,
                     1 if announcement_mode else 0),
                )
                room_id = cursor.lastrowid
                cursor.execute(
                    '''INSERT INTO chat_room_members
                       (room_id, user_id, joined_at, is_admin)
                       VALUES (?, ?, ?, 1)''',
                    (room_id, user_id, now),
                )
                self._log_communication_action(
                    user_id, "create_linked_room",
                    f"Created linked room {room_id} for {entity_type}#{eid_str}",
                    cursor=cursor,
                )
            # Ensure caller is a member.
            cursor.execute(
                'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                (room_id, user_id),
            )
            if not cursor.fetchone():
                cursor.execute(
                    '''INSERT INTO chat_room_members
                       (room_id, user_id, joined_at, is_admin)
                       VALUES (?, ?, ?, 0)''',
                    (room_id, user_id, now),
                )
            # Add any extra invitees.
            for uid in (invite_user_ids or []):
                if not uid or uid == user_id:
                    continue
                cursor.execute(
                    'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                    (room_id, uid),
                )
                if cursor.fetchone():
                    continue
                cursor.execute(
                    '''INSERT INTO chat_room_members
                       (room_id, user_id, joined_at, is_admin)
                       VALUES (?, ?, ?, 0)''',
                    (room_id, uid, now),
                )
            return room_id

        try:
            return execute_db_operation(_go)
        except Exception as e:
            log_event('error', f"Error get_or_create_linked_room: {e}")
            return False

    # Convenience wrappers per domain ---------------------------------

    def get_or_create_event_room(self, event_id, event_title):
        return self.get_or_create_linked_room(
            'event', event_id,
            name=f"Event: {event_title}",
            category='Events', icon='📅',
            room_type='public',
        )

    def get_or_create_club_room(self, club_id, club_name, member_user_ids=None):
        return self.get_or_create_linked_room(
            'club', club_id,
            name=f"Club: {club_name}",
            category='Clubs & Societies', icon='🎭',
            room_type='private',
            invite_user_ids=member_user_ids or [],
        )

    def get_or_create_residence_room(self, residence_id, residence_name,
                                     resident_user_ids=None):
        return self.get_or_create_linked_room(
            'residence', residence_id,
            name=f"Residence: {residence_name}",
            category='Housing', icon='🏠',
            room_type='private',
            invite_user_ids=resident_user_ids or [],
        )

    def get_or_create_advisor_oh_room(self, advisor_user_id, student_user_id,
                                      starts_at=None, ends_at=None):
        """An office-hours-style 1:1 room between a career advisor and a student."""
        if not advisor_user_id or not student_user_id:
            return False
        # Compose a stable key from the two participants + start time so the
        # same advisor/student get a fresh room per appointment.
        eid = f"{advisor_user_id}-{student_user_id}-{starts_at or 'nows'}"
        return self.get_or_create_linked_room(
            'advisor_oh', eid,
            name="Career advisor — office hours",
            description="Auto-created from appointment booking.",
            category='Career', icon='💼',
            room_type='private',
            invite_user_ids=[advisor_user_id, student_user_id],
            oh_starts_at=starts_at, oh_ends_at=ends_at,
        )

