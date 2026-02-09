"""
Real-Time Chat Service

Provides live chat support and messaging between users.
"""

import logging
from typing import List, Optional, Dict, Set
from datetime import datetime
from enum import Enum
from .websocket_manager import get_websocket_manager, MessageType

logger = logging.getLogger(__name__)


class ChatMessageType(str, Enum):
    """Chat message types"""
    TEXT = "text"
    FILE = "file"
    IMAGE = "image"
    SYSTEM = "system"


class ChatRoomType(str, Enum):
    """Chat room types"""
    DIRECT = "direct"          # 1-on-1 chat
    GROUP = "group"            # Group chat
    SUPPORT = "support"        # Support ticket chat
    COURSE = "course"          # Course discussion


class ChatService:
    """
    Real-time chat service for instant messaging.

    Supports direct messages, group chats, and support conversations.
    """

    def __init__(self):
        """Initialize chat service"""
        self.ws_manager = get_websocket_manager()

        # room_id -> room metadata
        self.chat_rooms: Dict[str, dict] = {}

        # room_id -> list of messages
        self.message_history: Dict[str, List[dict]] = {}

        # user_id -> set of room_ids (for quick lookup)
        self.user_rooms: Dict[str, Set[str]] = {}

    async def create_chat_room(
        self,
        room_id: str,
        room_type: ChatRoomType,
        participants: List[str],
        room_name: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> dict:
        """
        Create a new chat room.

        Args:
            room_id: Unique room identifier
            room_type: Type of chat room
            participants: List of participant user IDs
            room_name: Optional room name
            metadata: Additional room metadata

        Returns:
            Room data dictionary
        """
        room_data = {
            "room_id": room_id,
            "type": room_type.value,
            "name": room_name or f"Chat Room {room_id}",
            "participants": participants,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        self.chat_rooms[room_id] = room_data
        self.message_history[room_id] = []

        # Add room to user's room list
        for user_id in participants:
            if user_id not in self.user_rooms:
                self.user_rooms[user_id] = set()
            self.user_rooms[user_id].add(room_id)

            # Add user to WebSocket room
            await self.ws_manager.join_room(user_id, room_id)

        # Notify participants
        await self._send_room_notification(
            room_id,
            f"Chat room '{room_data['name']}' created"
        )

        logger.info(f"Chat room {room_id} created with {len(participants)} participants")
        return room_data

    async def send_message(
        self,
        room_id: str,
        sender_id: str,
        message_text: str,
        message_type: ChatMessageType = ChatMessageType.TEXT,
        attachments: Optional[List[dict]] = None
    ) -> Optional[dict]:
        """
        Send a message to a chat room.

        Args:
            room_id: Chat room ID
            sender_id: Sender user ID
            message_text: Message text
            message_type: Type of message
            attachments: Optional file attachments

        Returns:
            Message data or None if failed
        """
        if room_id not in self.chat_rooms:
            logger.warning(f"Chat room {room_id} not found")
            return None

        # Verify sender is participant
        room = self.chat_rooms[room_id]
        if sender_id not in room["participants"]:
            logger.warning(f"User {sender_id} is not a participant in room {room_id}")
            return None

        # Create message
        message = {
            "message_id": f"{room_id}_{datetime.utcnow().timestamp()}",
            "room_id": room_id,
            "sender_id": sender_id,
            "text": message_text,
            "type": message_type.value,
            "attachments": attachments or [],
            "timestamp": datetime.utcnow().isoformat(),
            "read_by": [sender_id]  # Mark as read by sender
        }

        # Store message
        self.message_history[room_id].append(message)

        # Limit history size (keep last 500 messages)
        if len(self.message_history[room_id]) > 500:
            self.message_history[room_id] = self.message_history[room_id][-500:]

        # Send to room via WebSocket
        websocket_message = {
            "type": MessageType.CHAT_MESSAGE,
            **message
        }

        await self.ws_manager.send_to_room(room_id, websocket_message)

        logger.info(f"Message sent in room {room_id} by user {sender_id}")
        return message

    async def add_participant(self, room_id: str, user_id: str):
        """
        Add a participant to a chat room.

        Args:
            room_id: Chat room ID
            user_id: User ID to add
        """
        if room_id not in self.chat_rooms:
            return

        room = self.chat_rooms[room_id]
        if user_id not in room["participants"]:
            room["participants"].append(user_id)

            # Add to user's room list
            if user_id not in self.user_rooms:
                self.user_rooms[user_id] = set()
            self.user_rooms[user_id].add(room_id)

            # Add to WebSocket room
            await self.ws_manager.join_room(user_id, room_id)

            # Notify room
            await self._send_room_notification(
                room_id,
                f"User {user_id} joined the chat"
            )

    async def remove_participant(self, room_id: str, user_id: str):
        """
        Remove a participant from a chat room.

        Args:
            room_id: Chat room ID
            user_id: User ID to remove
        """
        if room_id not in self.chat_rooms:
            return

        room = self.chat_rooms[room_id]
        if user_id in room["participants"]:
            room["participants"].remove(user_id)

            # Remove from user's room list
            if user_id in self.user_rooms:
                self.user_rooms[user_id].discard(room_id)

            # Remove from WebSocket room
            await self.ws_manager.leave_room(user_id, room_id)

            # Notify room
            await self._send_room_notification(
                room_id,
                f"User {user_id} left the chat"
            )

    def get_room_messages(
        self,
        room_id: str,
        limit: int = 100,
        before_timestamp: Optional[str] = None
    ) -> List[dict]:
        """
        Get message history for a room.

        Args:
            room_id: Chat room ID
            limit: Maximum number of messages to return
            before_timestamp: Get messages before this timestamp

        Returns:
            List of message dictionaries
        """
        if room_id not in self.message_history:
            return []

        messages = self.message_history[room_id]

        if before_timestamp:
            messages = [
                m for m in messages
                if m["timestamp"] < before_timestamp
            ]

        # Return most recent messages
        return messages[-limit:]

    def get_user_rooms(self, user_id: str) -> List[dict]:
        """
        Get all chat rooms for a user.

        Args:
            user_id: User ID

        Returns:
            List of room data dictionaries
        """
        if user_id not in self.user_rooms:
            return []

        room_ids = self.user_rooms[user_id]
        return [
            self.chat_rooms[room_id]
            for room_id in room_ids
            if room_id in self.chat_rooms
        ]

    def get_room_info(self, room_id: str) -> Optional[dict]:
        """
        Get information about a chat room.

        Args:
            room_id: Chat room ID

        Returns:
            Room data dictionary or None
        """
        return self.chat_rooms.get(room_id)

    async def mark_messages_read(self, room_id: str, user_id: str):
        """
        Mark all messages in a room as read by a user.

        Args:
            room_id: Chat room ID
            user_id: User ID
        """
        if room_id not in self.message_history:
            return

        for message in self.message_history[room_id]:
            if user_id not in message.get("read_by", []):
                message["read_by"].append(user_id)

    def get_unread_count(self, room_id: str, user_id: str) -> int:
        """
        Get count of unread messages for a user in a room.

        Args:
            room_id: Chat room ID
            user_id: User ID

        Returns:
            Number of unread messages
        """
        if room_id not in self.message_history:
            return 0

        unread = 0
        for message in self.message_history[room_id]:
            if user_id not in message.get("read_by", []):
                unread += 1

        return unread

    async def _send_room_notification(self, room_id: str, message: str):
        """
        Send a system notification to a room.

        Args:
            room_id: Chat room ID
            message: Notification message
        """
        notification = {
            "type": MessageType.CHAT_MESSAGE,
            "message_id": f"{room_id}_system_{datetime.utcnow().timestamp()}",
            "room_id": room_id,
            "sender_id": "system",
            "text": message,
            "message_type": ChatMessageType.SYSTEM.value,
            "timestamp": datetime.utcnow().isoformat()
        }

        await self.ws_manager.send_to_room(room_id, notification)

    async def create_support_chat(
        self,
        student_id: str,
        support_staff_id: str,
        ticket_id: Optional[str] = None
    ) -> dict:
        """
        Create a support chat room.

        Args:
            student_id: Student user ID
            support_staff_id: Support staff user ID
            ticket_id: Optional support ticket ID

        Returns:
            Room data dictionary
        """
        room_id = f"support_{ticket_id or datetime.utcnow().timestamp()}"

        return await self.create_chat_room(
            room_id=room_id,
            room_type=ChatRoomType.SUPPORT,
            participants=[student_id, support_staff_id],
            room_name=f"Support Chat - Ticket {ticket_id or 'New'}",
            metadata={"ticket_id": ticket_id}
        )


# Global chat service instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """
    Get the global chat service instance.

    Returns:
        ChatService instance
    """
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
