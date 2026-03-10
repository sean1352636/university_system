"""Chat room mixin for CommunicationDashboard."""

from __future__ import annotations

from education_system.university_system.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)


class _ChatMixin:
    """Mixin providing chat room lifecycle, membership, and messaging."""

    @handle_exception
    def create_chat_room(self, name, description=None, room_type='public'):
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

        def _create_room(cursor):
            creator_id = self.auth.current_user['id']
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Check if room name already exists
            cursor.execute('SELECT id FROM chat_rooms WHERE name = ? AND is_active = 1', (name.strip(),))
            if cursor.fetchone():
                log_event('error', f"Chat room '{name}' already exists")
                return False

            # Create the chat room
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
    def send_chat_message(self, room_id, content):
        """Send a message to a chat room"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to send chat messages")
            return False

        if not content or not content.strip():
            log_event('error', "Message content is required")
            return False

        def _send_message(cursor):
            user_id = self.auth.current_user['id']
            sent_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Check if user is a member of the room
            cursor.execute('''
            SELECT 1 FROM chat_room_members
            WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id))

            if not cursor.fetchone():
                log_event('error', f"User not a member of room {room_id}")
                return False

            # Check if room is active
            cursor.execute('''
            SELECT is_active FROM chat_rooms WHERE id = ?
            ''', (room_id,))

            room_data = cursor.fetchone()
            if not room_data or not room_data[0]:
                log_event('error', f"Room {room_id} not found or inactive")
                return False

            # Send the message
            cursor.execute('''
            INSERT INTO chat_messages (room_id, sender_id, content, sent_at)
            VALUES (?, ?, ?, ?)
            ''', (room_id, user_id, content.strip(), sent_at))

            message_id = cursor.lastrowid

            return message_id

        try:
            result = execute_db_operation(_send_message)
            if result:
                log_event('info', f"Chat message sent to room {room_id}")
            return result
        except Exception as e:
            log_event('error', f"Error sending chat message: {e}")
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
                       (SELECT COUNT(*) FROM chat_messages WHERE room_id = r.id) as message_count
                FROM chat_rooms r
                JOIN chat_room_members m ON r.id = m.room_id
                JOIN users u ON r.created_by = u.id
                WHERE m.user_id = ? AND r.is_active = 1
                ORDER BY r.name
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

            # Format room data
            room_list = []
            for room in rooms:
                room_list.append({
                    'id': room[0],
                    'name': room[1],
                    'description': room[2],
                    'room_type': room[3],
                    'created_at': room[4],
                    'creator': room[5],
                    'is_admin': bool(room[6]),
                    'member_count': room[7],
                    'message_count': room[8]
                })

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
    def get_chat_messages(self, room_id, page=1, limit=20):
        """Get messages from a chat room"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to view chat messages")
            return {'messages': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

        user_id = self.auth.current_user['id']
        offset = (page - 1) * limit

        def _get_messages(cursor):
            # Check if user is a member of the room
            cursor.execute('''
            SELECT 1 FROM chat_room_members
            WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id))

            if not cursor.fetchone():
                log_event('error', f"User not a member of room {room_id}")
                return {'messages': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

            # Get messages (most recent first, then reverse for display)
            cursor.execute('''
            SELECT m.id, m.content, m.sent_at, u.username, u.first_name, u.last_name
            FROM chat_messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.room_id = ?
            ORDER BY m.sent_at DESC
            LIMIT ? OFFSET ?
            ''', (room_id, limit, offset))

            messages = cursor.fetchall()

            # Get total count
            cursor.execute('''
            SELECT COUNT(*) FROM chat_messages WHERE room_id = ?
            ''', (room_id,))

            total_count = cursor.fetchone()[0]

            # Format message data (reverse to show oldest first)
            message_list = []
            for message in reversed(messages):
                full_name = f"{message[4]} {message[5]}".strip()
                message_list.append({
                    'id': message[0],
                    'content': message[1],
                    'sent_at': message[2],
                    'sender': message[3],
                    'sender_name': full_name if full_name else message[3]
                })

            return {
                'messages': message_list,
                'total_count': total_count,
                'page': page,
                'limit': limit,
                'total_pages': (total_count + limit - 1) // limit if limit > 0 else 1
            }

        try:
            return execute_db_operation(_get_messages)
        except Exception as e:
            log_event('error', f"Error getting chat messages: {e}")
            return {'messages': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

    @handle_exception
    def invite_user_to_room(self, room_id, user_id_to_invite):
        """Invite a user to a chat room"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to invite users")
            return False

        def _invite_user(cursor):
            inviter_id = self.auth.current_user['id']
            invited_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Check if inviter is an admin of the room
            cursor.execute('''
            SELECT 1 FROM chat_room_members
            WHERE room_id = ? AND user_id = ? AND is_admin = 1
            ''', (room_id, inviter_id))

            if not cursor.fetchone():
                log_event('error', f"User not an admin of room {room_id}")
                return False

            # Check if user to invite exists
            cursor.execute('SELECT username FROM users WHERE id = ?', (user_id_to_invite,))
            user_data = cursor.fetchone()
            if not user_data:
                log_event('error', f"User {user_id_to_invite} not found")
                return False

            username = user_data[0]

            # Check if user is already a member
            cursor.execute('''
            SELECT 1 FROM chat_room_members
            WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id_to_invite))

            if cursor.fetchone():
                log_event('warning', f"User {user_id_to_invite} already a member")
                return "already_member"

            # Check if invitation already exists
            cursor.execute('''
            SELECT status FROM chat_room_invitations
            WHERE room_id = ? AND user_id = ?
            ORDER BY invited_at DESC LIMIT 1
            ''', (room_id, user_id_to_invite))

            existing_invitation = cursor.fetchone()
            if existing_invitation and existing_invitation[0] == 'pending':
                log_event('warning', f"Pending invitation already exists")
                return "already_invited"

            # Create invitation
            cursor.execute('''
            INSERT INTO chat_room_invitations (room_id, user_id, invited_by, invited_at, status)
            VALUES (?, ?, ?, ?, 'pending')
            ''', (room_id, user_id_to_invite, inviter_id, invited_at))

            # Log the action (pass cursor to avoid nested transactions)
            self._log_communication_action(
                inviter_id,
                "invite_user_to_room",
                f"Invited user {username} to room {room_id}",
                cursor=cursor
            )

            return True

        try:
            result = execute_db_operation(_invite_user)
            if result == True:
                log_event('info', f"Successfully invited user {user_id_to_invite} to room {room_id}")
            return result
        except Exception as e:
            log_event('error', f"Error inviting user to room: {e}")
            return False

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

            # Get room members
            cursor.execute('''
            SELECT m.user_id, u.username, u.first_name, u.last_name, u.email,
                   m.joined_at, m.is_admin
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
                    'is_admin': bool(member[6])
                })

            return member_list

        try:
            return execute_db_operation(_get_members)
        except Exception as e:
            log_event('error', f"Error getting room members: {e}")
            return []

    @handle_exception
    def get_pending_invitations(self):
        """Get pending chat room invitations for current user"""
        if not self.auth or not self.auth.current_user:
            return []

        def _get_invitations(cursor):
            user_id = self.auth.current_user['id']

            cursor.execute('''
            SELECT i.id, i.room_id, r.name as room_name, r.description,
                   u.username as invited_by, i.invited_at
            FROM chat_room_invitations i
            JOIN chat_rooms r ON i.room_id = r.id
            JOIN users u ON i.invited_by = u.id
            WHERE i.user_id = ? AND i.status = 'pending'
            ORDER BY i.invited_at DESC
            ''', (user_id,))

            invitations = cursor.fetchall()

            invitation_list = []
            for inv in invitations:
                invitation_list.append({
                    'id': inv[0],
                    'room_id': inv[1],
                    'room_name': inv[2],
                    'room_description': inv[3],
                    'invited_by': inv[4],
                    'invited_at': inv[5]
                })

            return invitation_list

        try:
            return execute_db_operation(_get_invitations)
        except Exception as e:
            log_event('error', f"Error getting pending invitations: {e}")
            return []

    @handle_exception
    def respond_to_invitation(self, invitation_id, accept=True):
        """Accept or decline a chat room invitation"""
        if not self.auth or not self.auth.current_user:
            return False

        def _respond_invitation(cursor):
            user_id = self.auth.current_user['id']
            responded_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Get invitation details
            cursor.execute('''
            SELECT room_id, user_id FROM chat_room_invitations
            WHERE id = ? AND status = 'pending'
            ''', (invitation_id,))

            invitation = cursor.fetchone()
            if not invitation:
                log_event('error', f"Invitation {invitation_id} not found or already processed")
                return False

            room_id, invited_user_id = invitation

            if invited_user_id != user_id:
                log_event('error', f"Invitation not for current user")
                return False

            status = 'accepted' if accept else 'declined'

            # Update invitation status
            cursor.execute('''
            UPDATE chat_room_invitations
            SET status = ?, responded_at = ?
            WHERE id = ?
            ''', (status, responded_at, invitation_id))

            # If accepted, join the room
            if accept:
                cursor.execute('''
                INSERT INTO chat_room_members (room_id, user_id, joined_at, is_admin)
                VALUES (?, ?, ?, 0)
                ''', (room_id, user_id, responded_at))

            return True

        try:
            result = execute_db_operation(_respond_invitation)
            if result:
                action = "accepted" if accept else "declined"
                log_event('info', f"Invitation {invitation_id} {action}")
            return result
        except Exception as e:
            log_event('error', f"Error responding to invitation: {e}")
            return False
