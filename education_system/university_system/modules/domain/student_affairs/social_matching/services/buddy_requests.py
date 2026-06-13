"""Buddy request mixin for the Social Matching Service."""

from typing import Dict, List

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608


class BuddyRequestMixin:
    """Methods for managing buddy requests."""

    def send_buddy_request(self, sender_id: str, receiver_id: str,
                          request_type: str, destination: str = "",
                          message: str = "") -> int:
        """
        Send a buddy request to another user.

        Args:
            sender_id: User sending request
            receiver_id: User receiving request
            request_type: Type (study_abroad, general, sports, etc.)
            destination: Study abroad destination (if applicable)
            message: Personal message

        Returns:
            Request ID
        """
        # Check receiver's privacy settings
        privacy = self.get_privacy_settings(receiver_id)
        if not privacy['allow_messages']:
            raise PermissionError("User does not accept buddy requests")

        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO buddy_requests
                (sender_id, receiver_id, request_type, destination, message)
                VALUES (?, ?, ?, ?, ?)
            """, (sender_id, receiver_id, request_type, destination, message))

            request_id = cursor.lastrowid

        log_activity('create', 'buddy_request', user_id=sender_id,
                    details={'receiver': receiver_id, 'type': request_type})
        return request_id

    def get_buddy_requests(self, user_id: str, status: str = 'pending',
                          direction: str = 'received') -> List[Dict]:
        """
        Get buddy requests for a user.

        Args:
            user_id: User identifier
            status: Request status (pending, accepted, declined)
            direction: 'received' or 'sent'

        Returns:
            List of buddy requests
        """
        with get_connection() as conn:
            if direction == 'received':
                field = 'receiver_id'
            else:
                field = 'sender_id'

            safe_field = validate_identifier(field, "column")
            cursor = conn.execute(
                "SELECT request_id, sender_id, receiver_id, request_type,"
                "       destination, message, status, sent_at, responded_at"
                " FROM buddy_requests"
                " WHERE " + safe_field + " = ? AND status = ?"
                " ORDER BY sent_at DESC",
                (user_id, status))

            requests = []
            for row in cursor.fetchall():
                requests.append({
                    'request_id': row[0],
                    'sender_id': row[1],
                    'receiver_id': row[2],
                    'type': row[3],
                    'destination': row[4],
                    'message': row[5],
                    'status': row[6],
                    'sent_at': row[7],
                    'responded_at': row[8]
                })
            return requests

    def respond_to_buddy_request(self, request_id: int, user_id: str,
                                 accept: bool) -> bool:
        """Respond to a buddy request (accept or decline)."""
        status = 'accepted' if accept else 'declined'

        with transaction() as conn:
            cursor = conn.execute("""
                UPDATE buddy_requests
                SET status = ?, responded_at = CURRENT_TIMESTAMP
                WHERE request_id = ? AND receiver_id = ?
            """, (status, request_id, user_id))

            if cursor.rowcount > 0:
                log_activity('update', 'buddy_request', user_id=user_id,
                           details={'request_id': request_id, 'response': status})
                return True
        return False
