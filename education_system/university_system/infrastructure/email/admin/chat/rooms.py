"""RoomsMixin — extracted from chat.py."""
from __future__ import annotations

from education_system.university_system.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)


class RoomsMixin:
    """Methods grouped from the original _ChatMixin."""

    @handle_exception
    def create_chat_room(self, name, description=None, room_type='public', max_members=None):
        """Create a new chat room"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to create chat rooms")
            return False

        # Validate inputs
        if not name or not name.strip():
            log_event('error', "Chat room name is required")
            return False

        # Valid room types
        valid_types = ['public', 'private', 'course', 'department']
        if room_type not in valid_types:
            room_type = 'public'

        if max_members is not None:
            try:
                max_members = int(max_members)
            except (TypeError, ValueError):
                log_event('error', "max_members must be an integer")
                return False
            if max_members < 2:
                log_event('error', "max_members must be at least 2")
                return False

        def _create_room(cursor):
            creator_id = self.auth.current_user['id']
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Check if room name already exists
            cursor.execute('SELECT id FROM chat_rooms WHERE name = ? AND is_active = 1', (name.strip(),))
            if cursor.fetchone():
                log_event('error', f"Chat room '{name}' already exists")
                return False

            # Create the chat room
            if max_members is not None:
                cursor.execute('''
                INSERT INTO chat_rooms (name, description, room_type, created_by, created_at, max_members, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ''', (name.strip(), description, room_type, creator_id, created_at, max_members))
            else:
                cursor.execute('''
                INSERT INTO chat_rooms (name, description, room_type, created_by, created_at, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
                ''', (name.strip(), description, room_type, creator_id, created_at))

            room_id = cursor.lastrowid

            # Add creator as admin member
            cursor.execute('''
            INSERT INTO chat_room_members (room_id, user_id, joined_at, is_admin)
            VALUES (?, ?, ?, 1)
            ''', (room_id, creator_id, created_at))

            # Log the action (pass cursor to avoid nested transactions)
            self._log_communication_action(
                creator_id,
                "create_chat_room",
                f"Created chat room '{name}' (ID: {room_id})",
                cursor=cursor
            )

            return room_id

        try:
            result = execute_db_operation(_create_room)
            if result:
                log_event('info', f"Chat room '{name}' created successfully with ID {result}")
            return result
        except Exception as e:
            log_event('error', f"Error creating chat room: {e}")
            return False

    @handle_exception
    def join_chat_room(self, room_id):
        """Join a chat room"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to join chat rooms")
            return False

        def _join_room(cursor):
            user_id = self.auth.current_user['id']
            joined_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Check if room exists and is active
            cursor.execute('''
            SELECT name, room_type FROM chat_rooms
            WHERE id = ? AND is_active = 1
            ''', (room_id,))

            room_data = cursor.fetchone()
            if not room_data:
                log_event('error', f"Chat room {room_id} not found or inactive")
                return False

            room_name, room_type = room_data

            # Banned users may not rejoin (under any circumstances).
            cursor.execute(
                'SELECT 1 FROM chat_room_bans WHERE room_id = ? AND user_id = ?',
                (room_id, user_id),
            )
            if cursor.fetchone():
                log_event('warning',
                          f"Banned user {user_id} attempted to rejoin room {room_id}")
                return "banned"

            # Check if user is already a member
            cursor.execute('''
            SELECT id FROM chat_room_members
            WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id))

            if cursor.fetchone():
                log_event('warning', f"User already member of room {room_id}")
                return "already_member"

            # For private rooms, check if user has an invitation
            if room_type == 'private':
                cursor.execute('''
                SELECT id FROM chat_room_invitations
                WHERE room_id = ? AND user_id = ? AND status = 'pending'
                ''', (room_id, user_id))

                if not cursor.fetchone():
                    log_event('error', f"No invitation found for private room {room_id}")
                    return False

                # Accept the invitation
                cursor.execute('''
                UPDATE chat_room_invitations
                SET status = 'accepted', responded_at = ?
                WHERE room_id = ? AND user_id = ? AND status = 'pending'
                ''', (joined_at, room_id, user_id))

            # Add user to room
            cursor.execute('''
            INSERT INTO chat_room_members (room_id, user_id, joined_at, is_admin)
            VALUES (?, ?, ?, 0)
            ''', (room_id, user_id, joined_at))

            # Log the action (pass cursor to avoid nested transactions)
            self._log_communication_action(
                user_id,
                "join_chat_room",
                f"Joined chat room '{room_name}' (ID: {room_id})",
                cursor=cursor
            )

            return True

        try:
            result = execute_db_operation(_join_room)
            if result == True:
                log_event('info', f"Successfully joined chat room {room_id}")
            elif result == "already_member":
                log_event('info', f"User already member of chat room {room_id}")
            return result
        except Exception as e:
            log_event('error', f"Error joining chat room: {e}")
            return False

    @handle_exception
    def leave_chat_room(self, room_id):
        """Leave a chat room"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to leave chat rooms")
            return False

        def _leave_room(cursor):
            user_id = self.auth.current_user['id']

            # Check if user is a member
            cursor.execute('''
            SELECT is_admin FROM chat_room_members
            WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id))

            member_data = cursor.fetchone()
            if not member_data:
                log_event('error', f"User not a member of room {room_id}")
                return False

            is_admin = member_data[0]

            # Get room info
            cursor.execute('SELECT name, created_by FROM chat_rooms WHERE id = ?', (room_id,))
            room_data = cursor.fetchone()
            if not room_data:
                return False

            room_name, created_by = room_data

            # Check if user is the creator/owner
            if created_by == user_id:
                # Transfer ownership to another admin or delete room
                cursor.execute('''
                SELECT user_id FROM chat_room_members
                WHERE room_id = ? AND user_id != ? AND is_admin = 1
                LIMIT 1
                ''', (room_id, user_id))

                next_admin = cursor.fetchone()
                if next_admin:
                    # Transfer ownership
                    cursor.execute('''
                    UPDATE chat_rooms SET created_by = ? WHERE id = ?
                    ''', (next_admin[0], room_id))
                    log_event('info', f"Transferred room ownership to user {next_admin[0]}")
                else:
                    # No other admins, check if there are other members
                    cursor.execute('''
                    SELECT COUNT(*) FROM chat_room_members
                    WHERE room_id = ? AND user_id != ?
                    ''', (room_id, user_id))

                    other_members = cursor.fetchone()[0]
                    if other_members == 0:
                        # No other members, deactivate the room
                        cursor.execute('''
                        UPDATE chat_rooms SET is_active = 0 WHERE id = ?
                        ''', (room_id,))
                        log_event('info', f"Deactivated empty room {room_id}")
                    else:
                        # Promote the most senior member to admin
                        cursor.execute('''
                        SELECT user_id FROM chat_room_members
                        WHERE room_id = ? AND user_id != ?
                        ORDER BY joined_at ASC LIMIT 1
                        ''', (room_id, user_id))

                        senior_member = cursor.fetchone()
                        if senior_member:
                            cursor.execute('''
                            UPDATE chat_room_members SET is_admin = 1
                            WHERE room_id = ? AND user_id = ?
                            ''', (room_id, senior_member[0]))

                            cursor.execute('''
                            UPDATE chat_rooms SET created_by = ? WHERE id = ?
                            ''', (senior_member[0], room_id))

                            log_event('info', f"Promoted user {senior_member[0]} to room admin")

            # Remove user from room
            cursor.execute('''
            DELETE FROM chat_room_members
            WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id))

            # Log the action (pass cursor to avoid nested transactions)
            self._log_communication_action(
                user_id,
                "leave_chat_room",
                f"Left chat room '{room_name}' (ID: {room_id})",
                cursor=cursor
            )

            return True

        try:
            result = execute_db_operation(_leave_room)
            if result:
                log_event('info', f"Successfully left chat room {room_id}")
            return result
        except Exception as e:
            log_event('error', f"Error leaving chat room: {e}")
            return False

    @handle_exception
    def get_chat_rooms(self, user_filter='joined', page=1, limit=10):
        """Get chat rooms (joined, public, or all)"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to view chat rooms")
            return {'rooms': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

        user_id = self.auth.current_user['id']
        offset = (page - 1) * limit

        def _get_rooms(cursor):
            if user_filter == 'joined':
                # Get rooms user is a member of
                cursor.execute('''
                SELECT r.id, r.name, r.description, r.room_type, r.created_at,
                       u.username as creator, m.is_admin,
                       (SELECT COUNT(*) FROM chat_room_members WHERE room_id = r.id) as member_count,
                       (SELECT COUNT(*) FROM chat_messages WHERE room_id = r.id) as message_count,
                       r.category, r.icon, r.colour,
                       COALESCE(m.is_favourite, 0),
                       COALESCE(m.is_banned, 0), m.muted_until,
                       r.created_by,
                       r.linked_course_code, r.linked_assignment_group_id,
                       COALESCE(r.announcement_mode, 0),
                       r.oh_starts_at, r.oh_ends_at
                FROM chat_rooms r
                JOIN chat_room_members m ON r.id = m.room_id
                JOIN users u ON r.created_by = u.id
                WHERE m.user_id = ? AND r.is_active = 1
                ORDER BY COALESCE(m.is_favourite, 0) DESC,
                         COALESCE(r.category, '~'), r.name
                LIMIT ? OFFSET ?
                ''', (user_id, limit, offset))

                rooms = cursor.fetchall()

                # Get total count
                cursor.execute('''
                SELECT COUNT(*) FROM chat_rooms r
                JOIN chat_room_members m ON r.id = m.room_id
                WHERE m.user_id = ? AND r.is_active = 1
                ''', (user_id,))

            elif user_filter == 'public':
                # Get public rooms user can join
                cursor.execute('''
                SELECT r.id, r.name, r.description, r.room_type, r.created_at,
                       u.username as creator, 0 as is_admin,
                       (SELECT COUNT(*) FROM chat_room_members WHERE room_id = r.id) as member_count,
                       (SELECT COUNT(*) FROM chat_messages WHERE room_id = r.id) as message_count
                FROM chat_rooms r
                JOIN users u ON r.created_by = u.id
                WHERE r.room_type = 'public' AND r.is_active = 1
                  AND r.id NOT IN (
                      SELECT room_id FROM chat_room_members WHERE user_id = ?
                  )
                ORDER BY r.name
                LIMIT ? OFFSET ?
                ''', (user_id, limit, offset))

                rooms = cursor.fetchall()

                # Get total count
                cursor.execute('''
                SELECT COUNT(*) FROM chat_rooms r
                WHERE r.room_type = 'public' AND r.is_active = 1
                  AND r.id NOT IN (
                      SELECT room_id FROM chat_room_members WHERE user_id = ?
                  )
                ''', (user_id,))

            else:  # all
                # Get all active rooms (admin view)
                cursor.execute('''
                SELECT r.id, r.name, r.description, r.room_type, r.created_at,
                       u.username as creator,
                       COALESCE(m.is_admin, 0) as is_admin,
                       (SELECT COUNT(*) FROM chat_room_members WHERE room_id = r.id) as member_count,
                       (SELECT COUNT(*) FROM chat_messages WHERE room_id = r.id) as message_count
                FROM chat_rooms r
                JOIN users u ON r.created_by = u.id
                LEFT JOIN chat_room_members m ON r.id = m.room_id AND m.user_id = ?
                WHERE r.is_active = 1
                ORDER BY r.name
                LIMIT ? OFFSET ?
                ''', (user_id, limit, offset))

                rooms = cursor.fetchall()

                # Get total count
                cursor.execute('SELECT COUNT(*) FROM chat_rooms WHERE is_active = 1')

            total_count = cursor.fetchone()[0]

            # Format room data. The 'joined' branch returns extra columns
            # (category/icon/colour/favourite/ban/mute/owner_id); the 'public'
            # branch only returns the first 9.
            room_list = []
            for room in rooms:
                entry = {
                    'id': room[0],
                    'name': room[1],
                    'description': room[2],
                    'room_type': room[3],
                    'created_at': room[4],
                    'creator': room[5],
                    'is_admin': bool(room[6]),
                    'member_count': room[7],
                    'message_count': room[8],
                }
                if len(room) > 9:
                    entry.update({
                        'category': room[9],
                        'icon': room[10],
                        'colour': room[11],
                        'is_favourite': bool(room[12]),
                        'is_banned': bool(room[13]),
                        'muted_until': room[14],
                        'created_by': room[15],
                    })
                if len(room) > 16:
                    entry.update({
                        'linked_course_code': room[16],
                        'linked_assignment_group_id': room[17],
                        'announcement_mode': bool(room[18]),
                        'oh_starts_at': room[19],
                        'oh_ends_at': room[20],
                    })
                room_list.append(entry)

            return {
                'rooms': room_list,
                'total_count': total_count,
                'page': page,
                'limit': limit,
                'total_pages': (total_count + limit - 1) // limit if limit > 0 else 1
            }

        try:
            return execute_db_operation(_get_rooms)
        except Exception as e:
            log_event('error', f"Error getting chat rooms: {e}")
            return {'rooms': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

    @handle_exception
    def get_room_members(self, room_id):
        """Get members of a chat room"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to view room members")
            return []

        def _get_members(cursor):
            user_id = self.auth.current_user['id']

            # Check if user is a member of the room
            cursor.execute('''
            SELECT 1 FROM chat_room_members
            WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id))

            if not cursor.fetchone():
                log_event('error', f"User not a member of room {room_id}")
                return []

            # Get room members and creator id (for is_creator flag)
            cursor.execute('SELECT created_by FROM chat_rooms WHERE id = ?', (room_id,))
            creator_row = cursor.fetchone()
            creator_id = creator_row[0] if creator_row else None

            cursor.execute('''
            SELECT m.user_id, u.username, u.first_name, u.last_name, u.email,
                   m.joined_at, m.is_admin,
                   COALESCE(m.is_banned, 0), m.muted_until
            FROM chat_room_members m
            JOIN users u ON m.user_id = u.id
            WHERE m.room_id = ?
            ORDER BY m.is_admin DESC, m.joined_at ASC
            ''', (room_id,))

            members = cursor.fetchall()

            # Format member data
            member_list = []
            for member in members:
                full_name = f"{member[2]} {member[3]}".strip()
                member_list.append({
                    'user_id': member[0],
                    'username': member[1],
                    'full_name': full_name if full_name else member[1],
                    'email': member[4],
                    'joined_at': member[5],
                    'is_admin': bool(member[6]),
                    'is_banned': bool(member[7]),
                    'muted_until': member[8],
                    'is_creator': member[0] == creator_id,
                })

            return member_list

        try:
            return execute_db_operation(_get_members)
        except Exception as e:
            log_event('error', f"Error getting room members: {e}")
            return []

    def _is_room_admin(self, cursor, room_id, user_id):
        cursor.execute(
            'SELECT created_by FROM chat_rooms WHERE id = ?', (room_id,),
        )
        row = cursor.fetchone()
        if row and row[0] == user_id:
            return True
        cursor.execute(
            'SELECT COALESCE(is_admin, 0) FROM chat_room_members WHERE room_id = ? AND user_id = ?',
            (room_id, user_id),
        )
        r = cursor.fetchone()
        return bool(r and r[0])

    @handle_exception
    def update_chat_room(self, room_id, *, name=None, description=None,
                         room_type=None, category=None, icon=None, colour=None,
                         max_members=None, linked_course_code=None,
                         linked_assignment_group_id=None,
                         announcement_mode=None,
                         oh_starts_at=None, oh_ends_at=None,
                         retention_days=None, slow_mode_seconds=None,
                         is_encrypted=None):
        """Update room metadata. Caller must be a room admin or the creator.
        Pass None to leave a field unchanged; pass an empty string to clear."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        if room_type is not None and room_type not in ('public', 'private', 'course', 'department'):
            log_event('error', f"Invalid room_type: {room_type}")
            return False
        if max_members is not None:
            try:
                max_members = int(max_members)
            except (TypeError, ValueError):
                return False
            if max_members < 2:
                return False

        def _update(cursor):
            if not self._is_room_admin(cursor, room_id, user_id):
                return False
            sets, params = [], []
            for col, val in (('name', name), ('description', description),
                             ('room_type', room_type), ('category', category),
                             ('icon', icon), ('colour', colour),
                             ('max_members', max_members),
                             ('linked_course_code', linked_course_code),
                             ('linked_assignment_group_id', linked_assignment_group_id),
                             ('announcement_mode',
                              None if announcement_mode is None else (1 if announcement_mode else 0)),
                             ('oh_starts_at', oh_starts_at),
                             ('oh_ends_at', oh_ends_at),
                             ('retention_days',
                              None if retention_days is None
                              else (int(retention_days) if str(retention_days).strip() else None)),
                             ('slow_mode_seconds',
                              None if slow_mode_seconds is None
                              else int(slow_mode_seconds)),
                             ('is_encrypted',
                              None if is_encrypted is None else (1 if is_encrypted else 0))):
                if val is not None:
                    sets.append(f"{col} = ?")
                    params.append(val if val != '' else None)
            if not sets:
                return True
            params.append(room_id)
            cursor.execute(
                f"UPDATE chat_rooms SET {', '.join(sets)} WHERE id = ?", params,
            )
            self._log_communication_action(
                user_id, "update_chat_room",
                f"Updated chat room {room_id}: {', '.join(sets)}", cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_update)
        except Exception as e:
            log_event('error', f"Error updating chat room: {e}")
            return False

    @handle_exception
    def archive_chat_room(self, room_id, archive=True):
        """Archive (hide from listings) or unarchive a chat room."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _arch(cursor):
            if not self._is_room_admin(cursor, room_id, user_id):
                return False
            if archive:
                cursor.execute(
                    'UPDATE chat_rooms SET is_active = 0, archived_at = ?, archived_by = ? WHERE id = ?',
                    (now, user_id, room_id),
                )
            else:
                cursor.execute(
                    'UPDATE chat_rooms SET is_active = 1, archived_at = NULL, archived_by = NULL WHERE id = ?',
                    (room_id,),
                )
            self._log_communication_action(
                user_id, "archive_chat_room" if archive else "unarchive_chat_room",
                f"{'Archived' if archive else 'Unarchived'} chat room {room_id}",
                cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_arch)
        except Exception as e:
            log_event('error', f"Error archiving chat room: {e}")
            return False

    @handle_exception
    def delete_chat_room(self, room_id):
        """Permanently delete a chat room and all related data. Creator only."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        def _delete(cursor):
            cursor.execute('SELECT created_by FROM chat_rooms WHERE id = ?', (room_id,))
            row = cursor.fetchone()
            if not row or row[0] != user_id:
                return False
            # Cascade manually since we don't rely on FK ON DELETE.
            cursor.execute(
                '''DELETE FROM chat_message_reactions WHERE message_id IN
                   (SELECT id FROM chat_messages WHERE room_id = ?)''',
                (room_id,),
            )
            for table in (
                'chat_messages', 'chat_room_members', 'chat_room_invitations',
                'chat_message_reads', 'chat_typing', 'chat_presence',
            ):
                try:
                    cursor.execute(f'DELETE FROM {table} WHERE room_id = ?', (room_id,))
                except Exception:
                    pass
            cursor.execute('DELETE FROM chat_rooms WHERE id = ?', (room_id,))
            self._log_communication_action(
                user_id, "delete_chat_room",
                f"Deleted chat room {room_id}", cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_delete)
        except Exception as e:
            log_event('error', f"Error deleting chat room: {e}")
            return False

    @handle_exception
    def transfer_room_ownership(self, room_id, new_owner_user_id):
        """Reassign created_by. Caller must be the current owner."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        def _transfer(cursor):
            cursor.execute('SELECT created_by FROM chat_rooms WHERE id = ?', (room_id,))
            row = cursor.fetchone()
            if not row or row[0] != user_id:
                return False
            cursor.execute(
                'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                (room_id, new_owner_user_id),
            )
            if not cursor.fetchone():
                return False
            cursor.execute(
                'UPDATE chat_rooms SET created_by = ? WHERE id = ?',
                (new_owner_user_id, room_id),
            )
            cursor.execute(
                'UPDATE chat_room_members SET is_admin = 1 WHERE room_id = ? AND user_id = ?',
                (room_id, new_owner_user_id),
            )
            self._log_communication_action(
                user_id, "transfer_room_ownership",
                f"Transferred chat room {room_id} ownership to user {new_owner_user_id}",
                cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_transfer)
        except Exception as e:
            log_event('error', f"Error transferring ownership: {e}")
            return False

    @handle_exception
    def set_room_admin(self, room_id, target_user_id, is_admin=True):
        """Promote or demote a member. Caller must be a room admin/creator.
        Cannot demote the creator."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        def _set(cursor):
            if not self._is_room_admin(cursor, room_id, user_id):
                return False
            cursor.execute('SELECT created_by FROM chat_rooms WHERE id = ?', (room_id,))
            row = cursor.fetchone()
            if row and row[0] == target_user_id and not is_admin:
                return False
            cursor.execute(
                'UPDATE chat_room_members SET is_admin = ? WHERE room_id = ? AND user_id = ?',
                (1 if is_admin else 0, room_id, target_user_id),
            )
            self._log_communication_action(
                user_id, "set_room_admin",
                f"{'Promoted' if is_admin else 'Demoted'} user {target_user_id} in room {room_id}",
                cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_set)
        except Exception as e:
            log_event('error', f"Error setting admin: {e}")
            return False

    @handle_exception
    def set_favourite_room(self, room_id, favourite=True):
        """Mark or unmark a room as a favourite for the current user."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        def _fav(cursor):
            cursor.execute(
                'UPDATE chat_room_members SET is_favourite = ? WHERE room_id = ? AND user_id = ?',
                (1 if favourite else 0, room_id, user_id),
            )
            return cursor.rowcount > 0

        try:
            return execute_db_operation(_fav)
        except Exception as e:
            log_event('error', f"Error setting favourite: {e}")
            return False

    @handle_exception
    def list_chat_categories(self):
        """Return the distinct non-empty categories currently in use."""
        def _list(cursor):
            cursor.execute(
                "SELECT DISTINCT category FROM chat_rooms WHERE category IS NOT NULL "
                "AND TRIM(category) != '' ORDER BY category"
            )
            return [r[0] for r in cursor.fetchall()]

        try:
            return execute_db_operation(_list)
        except Exception as e:
            log_event('error', f"Error listing categories: {e}")
            return []

    @handle_exception
    def get_room_info(self, room_id):
        """Return full metadata for a single room (None if not visible)."""
        if not self.auth or not self.auth.current_user:
            return None
        user_id = self.auth.current_user['id']

        def _get(cursor):
            cursor.execute(
                '''SELECT r.id, r.name, r.description, r.room_type, r.created_by,
                          COALESCE(r.announcement_mode, 0),
                          r.oh_starts_at, r.oh_ends_at,
                          r.linked_course_code, r.linked_assignment_group_id,
                          r.category, r.icon, r.colour,
                          COALESCE(m.is_admin, 0) AS is_admin
                   FROM chat_rooms r
                   LEFT JOIN chat_room_members m
                     ON m.room_id = r.id AND m.user_id = ?
                   WHERE r.id = ?''',
                (user_id, room_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                'id': row[0], 'name': row[1], 'description': row[2],
                'room_type': row[3], 'created_by': row[4],
                'announcement_mode': bool(row[5]),
                'oh_starts_at': row[6], 'oh_ends_at': row[7],
                'linked_course_code': row[8],
                'linked_assignment_group_id': row[9],
                'category': row[10], 'icon': row[11], 'colour': row[12],
                'is_admin': bool(row[13]),
            }

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting room info: {e}")
            return None

