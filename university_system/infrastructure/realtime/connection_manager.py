"""
Connection Manager for WebSocket Connections

Manages user connections, authentication, and connection metadata.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect, status
from .websocket_manager import get_websocket_manager, MessageType

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connection lifecycle and metadata.

    Handles authentication, connection tracking, and user sessions.
    """

    def __init__(self):
        """Initialize connection manager"""
        self.ws_manager = get_websocket_manager()

        # Store connection metadata
        # user_id -> metadata dict
        self.user_metadata: Dict[str, Dict[str, Any]] = {}

    async def handle_connection(
        self,
        websocket: WebSocket,
        user_id: str,
        user_role: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        """
        Handle a new WebSocket connection with authentication.

        Args:
            websocket: WebSocket connection
            user_id: Authenticated user ID
            user_role: User's role (admin, instructor, student, etc.)
            metadata: Additional connection metadata
        """
        # Connect the WebSocket
        success = await self.ws_manager.connect(websocket, user_id)

        if not success:
            return

        # Store user metadata
        self.user_metadata[user_id] = {
            "user_id": user_id,
            "role": user_role,
            "connected_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            **(metadata or {})
        }

        # Notify user of successful connection
        await self.ws_manager.send_to_user(user_id, {
            "type": MessageType.CONNECT,
            "message": "Successfully connected to real-time service",
            "metadata": self.user_metadata[user_id],
            "timestamp": datetime.utcnow().isoformat()
        })

        # Broadcast presence update to relevant users
        await self._broadcast_presence_update(user_id, "online")

        logger.info(f"Connection established for user {user_id} (role: {user_role})")

    async def handle_disconnection(self, websocket: WebSocket):
        """
        Handle WebSocket disconnection.

        Args:
            websocket: WebSocket connection to disconnect
        """
        # Get user ID before disconnecting
        user_id = self.ws_manager.connection_to_user.get(websocket)

        # Disconnect
        await self.ws_manager.disconnect(websocket)

        if user_id:
            # Check if user still has other connections
            if not self.ws_manager.is_user_online(user_id):
                # User is fully offline
                if user_id in self.user_metadata:
                    del self.user_metadata[user_id]

                # Broadcast presence update
                await self._broadcast_presence_update(user_id, "offline")

                logger.info(f"User {user_id} is now offline")

    async def listen(self, websocket: WebSocket):
        """
        Listen for messages from a WebSocket connection.

        Args:
            websocket: WebSocket connection to listen on
        """
        try:
            while True:
                # Receive message
                message = await websocket.receive_json()

                # Update last activity
                user_id = self.ws_manager.connection_to_user.get(websocket)
                if user_id and user_id in self.user_metadata:
                    self.user_metadata[user_id]["last_activity"] = datetime.utcnow().isoformat()

                # Handle message
                await self.ws_manager.handle_message(websocket, message)

        except WebSocketDisconnect:
            await self.handle_disconnection(websocket)
        except Exception as e:
            logger.error(f"Error in WebSocket listener: {e}")
            await self.handle_disconnection(websocket)

    async def _broadcast_presence_update(self, user_id: str, status: str):
        """
        Broadcast presence update to relevant users.

        Args:
            user_id: User whose presence changed
            status: New status (online/offline)
        """
        presence_update = {
            "type": MessageType.PRESENCE_UPDATE,
            "user_id": user_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Broadcast to all users (could be filtered based on relationships)
        await self.ws_manager.broadcast(presence_update, exclude_users={user_id})

    def get_user_metadata(self, user_id: str) -> Optional[dict]:
        """
        Get metadata for a connected user.

        Args:
            user_id: User identifier

        Returns:
            User metadata dictionary or None
        """
        return self.user_metadata.get(user_id)

    def is_user_authenticated(self, user_id: str) -> bool:
        """
        Check if a user is authenticated and connected.

        Args:
            user_id: User identifier

        Returns:
            True if user is authenticated and online
        """
        return user_id in self.user_metadata

    async def update_user_metadata(self, user_id: str, metadata: dict):
        """
        Update metadata for a connected user.

        Args:
            user_id: User identifier
            metadata: Metadata dictionary to merge
        """
        if user_id in self.user_metadata:
            self.user_metadata[user_id].update(metadata)
            self.user_metadata[user_id]["last_updated"] = datetime.utcnow().isoformat()


# Global connection manager instance
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """
    Get the global connection manager instance.

    Returns:
        ConnectionManager instance
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager
