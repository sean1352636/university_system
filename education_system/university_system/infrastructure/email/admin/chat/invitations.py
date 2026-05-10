"""InvitationsMixin — extracted from chat.py."""
from __future__ import annotations

from education_system.university_system.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)


class InvitationsMixin:
    """Methods grouped from the original _ChatMixin."""

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

            # Refuse to invite a banned user — admin must unban first.
            cursor.execute(
                'SELECT 1 FROM chat_room_bans WHERE room_id = ? AND user_id = ?',
                (room_id, user_id_to_invite),
            )
            if cursor.fetchone():
                log_event('warning',
                          f"Refused invite of banned user {user_id_to_invite} to room {room_id}")
                return "banned"

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

            # Banned users cannot accept invitations either.
            if accept:
                cursor.execute(
                    'SELECT 1 FROM chat_room_bans WHERE room_id = ? AND user_id = ?',
                    (room_id, user_id),
                )
                if cursor.fetchone():
                    log_event('warning',
                              f"Banned user {user_id} tried to accept invitation to room {room_id}")
                    return "banned"

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

    # ------------------------------------------------------------------
    # Live-update helpers: incremental fetch, read receipts, typing,
    # presence, and unread counts. Polled by the GUI; SQLite-friendly.
    # ------------------------------------------------------------------

