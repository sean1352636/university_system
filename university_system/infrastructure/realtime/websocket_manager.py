"""
WebSocket Manager for Real-Time Communication

Handles WebSocket connections, message routing, and connection lifecycle.
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any, List, Callable
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from enum import Enum

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """WebSocket message types"""
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    NOTIFICATION = "notification"
    CHAT_MESSAGE = "chat_message"
    PRESENCE_UPDATE = "presence_update"
    DASHBOARD_UPDATE = "dashboard_update"
    GRADE_UPDATE = "grade_update"
    DOCUMENT_UPDATE = "document_update"
    ACTIVITY = "activity"
    PING = "ping"
    PONG = "pong"
    ERROR = "error"


class WebSocketManager:
    """
    Central WebSocket management system.

    Handles WebSocket connections, message broadcasting, and user sessions.
    Thread-safe and supports multiple concurrent connections per user.
    """

    def __init__(self):
        """Initialize the WebSocket manager"""
        # user_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}

        # room_id -> set of user_ids
        self.rooms: Dict[str, Set[str]] = {}

        # WebSocket -> user_id mapping for quick lookups
        self.connection_to_user: Dict[WebSocket, str] = {}

        # Message handlers for different message types
        self.handlers: Dict[MessageType, List[Callable]] = {}

        # Connection lock for thread safety
        self._lock = asyncio.Lock()

        logger.info("WebSocketManager initialized")

    async def connect(self, websocket: WebSocket, user_id: str) -> bool:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket connection
            user_id: Unique identifier for the user

        Returns:
            True if connection was successful
        """
        try:
            await websocket.accept()

            async with self._lock:
                # Add connection to user's connection set
                if user_id not in self.active_connections:
                    self.active_connections[user_id] = set()
                self.active_connections[user_id].add(websocket)

                # Map connection to user
                self.connection_to_user[websocket] = user_id

            # Send connection confirmation
            await self.send_to_connection(websocket, {
                "type": MessageType.CONNECT,
                "message": "Connected successfully",
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            })

            logger.info(f"User {user_id} connected via WebSocket")
            return True

        except Exception as e:
            logger.error(f"Error connecting WebSocket for user {user_id}: {e}")
            return False

    async def disconnect(self, websocket: WebSocket):
        """
        Remove a WebSocket connection.

        Args:
            websocket: The WebSocket connection to remove
        """
        async with self._lock:
            user_id = self.connection_to_user.get(websocket)

            if user_id:
                # Remove from user's connections
                if user_id in self.active_connections:
                    self.active_connections[user_id].discard(websocket)

                    # Remove user entry if no more connections
                    if not self.active_connections[user_id]:
                        del self.active_connections[user_id]

                # Remove from connection mapping
                del self.connection_to_user[websocket]

                # Remove from all rooms
                for room_users in self.rooms.values():
                    room_users.discard(user_id)

                logger.info(f"User {user_id} disconnected from WebSocket")

    async def send_to_user(self, user_id: str, message: dict) -> int:
        """
        Send a message to all connections of a specific user.

        Args:
            user_id: User identifier
            message: Message dictionary to send

        Returns:
            Number of connections message was sent to
        """
        if user_id not in self.active_connections:
            return 0

        connections = self.active_connections[user_id].copy()
        sent_count = 0

        for websocket in connections:
            try:
                await websocket.send_json(message)
                sent_count += 1
            except WebSocketDisconnect:
                await self.disconnect(websocket)
            except Exception as e:
                logger.error(f"Error sending to user {user_id}: {e}")

        return sent_count

    async def send_to_connection(self, websocket: WebSocket, message: dict):
        """
        Send a message to a specific WebSocket connection.

        Args:
            websocket: The WebSocket connection
            message: Message dictionary to send
        """
        try:
            await websocket.send_json(message)
        except WebSocketDisconnect:
            await self.disconnect(websocket)
        except Exception as e:
            logger.error(f"Error sending to connection: {e}")

    async def broadcast(self, message: dict, exclude_users: Optional[Set[str]] = None):
        """
        Broadcast a message to all connected users.

        Args:
            message: Message dictionary to send
            exclude_users: Set of user IDs to exclude from broadcast
        """
        exclude_users = exclude_users or set()

        for user_id in list(self.active_connections.keys()):
            if user_id not in exclude_users:
                await self.send_to_user(user_id, message)

    async def join_room(self, user_id: str, room_id: str):
        """
        Add a user to a room for group messaging.

        Args:
            user_id: User identifier
            room_id: Room identifier
        """
        async with self._lock:
            if room_id not in self.rooms:
                self.rooms[room_id] = set()
            self.rooms[room_id].add(user_id)

        logger.info(f"User {user_id} joined room {room_id}")

    async def leave_room(self, user_id: str, room_id: str):
        """
        Remove a user from a room.

        Args:
            user_id: User identifier
            room_id: Room identifier
        """
        async with self._lock:
            if room_id in self.rooms:
                self.rooms[room_id].discard(user_id)

                # Clean up empty rooms
                if not self.rooms[room_id]:
                    del self.rooms[room_id]

        logger.info(f"User {user_id} left room {room_id}")

    async def send_to_room(self, room_id: str, message: dict, exclude_users: Optional[Set[str]] = None):
        """
        Send a message to all users in a room.

        Args:
            room_id: Room identifier
            message: Message dictionary to send
            exclude_users: Set of user IDs to exclude
        """
        if room_id not in self.rooms:
            return

        exclude_users = exclude_users or set()
        room_users = self.rooms[room_id].copy()

        for user_id in room_users:
            if user_id not in exclude_users:
                await self.send_to_user(user_id, message)

    def is_user_online(self, user_id: str) -> bool:
        """
        Check if a user has any active connections.

        Args:
            user_id: User identifier

        Returns:
            True if user has active connections
        """
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0

    def get_online_users(self) -> List[str]:
        """
        Get list of all currently connected users.

        Returns:
            List of user IDs
        """
        return list(self.active_connections.keys())

    def get_room_users(self, room_id: str) -> Set[str]:
        """
        Get all users in a specific room.

        Args:
            room_id: Room identifier

        Returns:
            Set of user IDs in the room
        """
        return self.rooms.get(room_id, set()).copy()

    def get_user_rooms(self, user_id: str) -> List[str]:
        """
        Get all rooms a user is currently in.

        Args:
            user_id: User identifier

        Returns:
            List of room IDs
        """
        return [room_id for room_id, users in self.rooms.items() if user_id in users]

    def register_handler(self, message_type: MessageType, handler: Callable):
        """
        Register a message handler for a specific message type.

        Args:
            message_type: Type of message to handle
            handler: Async function to handle the message
        """
        if message_type not in self.handlers:
            self.handlers[message_type] = []
        self.handlers[message_type].append(handler)

    async def handle_message(self, websocket: WebSocket, message: dict):
        """
        Handle an incoming WebSocket message.

        Args:
            websocket: The WebSocket connection
            message: Parsed message dictionary
        """
        try:
            message_type = MessageType(message.get("type", ""))

            # Call registered handlers
            if message_type in self.handlers:
                for handler in self.handlers[message_type]:
                    await handler(websocket, message)

        except ValueError:
            logger.warning(f"Unknown message type: {message.get('type')}")
            await self.send_to_connection(websocket, {
                "type": MessageType.ERROR,
                "error": "Unknown message type",
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await self.send_to_connection(websocket, {
                "type": MessageType.ERROR,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })

    async def ping_all(self):
        """Send ping to all connected users to keep connections alive"""
        ping_message = {
            "type": MessageType.PING,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(ping_message)

    def get_stats(self) -> dict:
        """
        Get current WebSocket statistics.

        Returns:
            Dictionary with connection stats
        """
        total_connections = sum(len(conns) for conns in self.active_connections.values())

        return {
            "total_users": len(self.active_connections),
            "total_connections": total_connections,
            "total_rooms": len(self.rooms),
            "average_connections_per_user": (
                total_connections / len(self.active_connections)
                if self.active_connections else 0
            )
        }


# Global WebSocket manager instance
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """
    Get the global WebSocket manager instance.

    Returns:
        WebSocketManager instance
    """
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager
