"""
Presence Manager for User Status Tracking

Tracks user online status, activity, and presence across the system.
"""

import logging
from typing import Dict, Optional, List, Set
from datetime import datetime, timedelta
from enum import Enum
from .websocket_manager import get_websocket_manager, MessageType

logger = logging.getLogger(__name__)


class UserStatus(str, Enum):
    """User presence status"""
    ONLINE = "online"
    AWAY = "away"
    BUSY = "busy"
    OFFLINE = "offline"


class PresenceManager:
    """
    Manages user presence and online status.

    Tracks user activity, status, and provides presence information
    to other users.
    """

    def __init__(self):
        """Initialize presence manager"""
        self.ws_manager = get_websocket_manager()

        # user_id -> presence data
        self.user_presence: Dict[str, dict] = {}

        # Track who can see whose presence (for privacy)
        # user_id -> set of user_ids they can see
        self.presence_visibility: Dict[str, Set[str]] = {}

    async def set_user_status(
        self,
        user_id: str,
        status: UserStatus,
        status_message: Optional[str] = None
    ):
        """
        Set a user's presence status.

        Args:
            user_id: User identifier
            status: User status
            status_message: Optional status message
        """
        if user_id not in self.user_presence:
            self.user_presence[user_id] = {}

        self.user_presence[user_id].update({
            "user_id": user_id,
            "status": status.value,
            "status_message": status_message,
            "last_updated": datetime.utcnow().isoformat(),
            "is_online": self.ws_manager.is_user_online(user_id)
        })

        # Broadcast status update to users who can see this user
        await self._broadcast_status_update(user_id)

        logger.info(f"User {user_id} status updated to {status.value}")

    async def update_activity(self, user_id: str, activity: str):
        """
        Update user's current activity.

        Args:
            user_id: User identifier
            activity: Activity description
        """
        if user_id not in self.user_presence:
            self.user_presence[user_id] = {
                "user_id": user_id,
                "status": UserStatus.ONLINE.value
            }

        self.user_presence[user_id].update({
            "current_activity": activity,
            "last_activity": datetime.utcnow().isoformat(),
            "is_online": True
        })

        # Broadcast activity update
        await self._broadcast_status_update(user_id)

    async def set_user_online(self, user_id: str):
        """
        Set user as online.

        Args:
            user_id: User identifier
        """
        await self.set_user_status(user_id, UserStatus.ONLINE)

    async def set_user_offline(self, user_id: str):
        """
        Set user as offline.

        Args:
            user_id: User identifier
        """
        if user_id in self.user_presence:
            self.user_presence[user_id].update({
                "status": UserStatus.OFFLINE.value,
                "is_online": False,
                "last_seen": datetime.utcnow().isoformat()
            })

            await self._broadcast_status_update(user_id)

    def get_user_presence(self, user_id: str) -> Optional[dict]:
        """
        Get presence data for a user.

        Args:
            user_id: User identifier

        Returns:
            Presence data dictionary or None
        """
        return self.user_presence.get(user_id)

    def get_online_users(self) -> List[dict]:
        """
        Get all currently online users.

        Returns:
            List of presence data for online users
        """
        online_users = []
        for user_id in self.ws_manager.get_online_users():
            presence = self.get_user_presence(user_id)
            if presence:
                online_users.append(presence)
            else:
                # Create basic presence for users without status
                online_users.append({
                    "user_id": user_id,
                    "status": UserStatus.ONLINE.value,
                    "is_online": True
                })

        return online_users

    def add_presence_visibility(self, user_id: str, can_see_user_id: str):
        """
        Allow a user to see another user's presence.

        Args:
            user_id: User who will see presence
            can_see_user_id: User whose presence will be visible
        """
        if user_id not in self.presence_visibility:
            self.presence_visibility[user_id] = set()

        self.presence_visibility[user_id].add(can_see_user_id)

    def remove_presence_visibility(self, user_id: str, cannot_see_user_id: str):
        """
        Revoke a user's ability to see another user's presence.

        Args:
            user_id: User who will not see presence
            cannot_see_user_id: User whose presence will be hidden
        """
        if user_id in self.presence_visibility:
            self.presence_visibility[user_id].discard(cannot_see_user_id)

    def can_see_presence(self, user_id: str, target_user_id: str) -> bool:
        """
        Check if a user can see another user's presence.

        Args:
            user_id: User requesting presence
            target_user_id: Target user

        Returns:
            True if user can see target's presence
        """
        # Default: users can see each other (can be restricted)
        if user_id not in self.presence_visibility:
            return True

        return target_user_id in self.presence_visibility[user_id]

    async def _broadcast_status_update(self, user_id: str):
        """
        Broadcast status update to relevant users.

        Args:
            user_id: User whose status changed
        """
        presence_data = self.get_user_presence(user_id)
        if not presence_data:
            return

        status_update = {
            "type": MessageType.PRESENCE_UPDATE,
            **presence_data
        }

        # Broadcast to all users who can see this user's presence
        # For simplicity, broadcasting to all; can be filtered
        await self.ws_manager.broadcast(status_update, exclude_users={user_id})

    async def check_away_status(self):
        """
        Check and update users who should be marked as away.

        Call this periodically to auto-update away status.
        """
        away_threshold = timedelta(minutes=5)
        now = datetime.utcnow()

        for user_id, presence in list(self.user_presence.items()):
            if presence.get("status") != UserStatus.ONLINE.value:
                continue

            last_activity = presence.get("last_activity")
            if not last_activity:
                continue

            try:
                last_activity_time = datetime.fromisoformat(last_activity)
                if now - last_activity_time > away_threshold:
                    await self.set_user_status(user_id, UserStatus.AWAY)
            except (ValueError, TypeError):
                pass

    def get_presence_summary(self) -> dict:
        """
        Get summary of presence statistics.

        Returns:
            Dictionary with presence stats
        """
        total_users = len(self.user_presence)
        status_counts = {}

        for presence in self.user_presence.values():
            status = presence.get("status", UserStatus.OFFLINE.value)
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_users": total_users,
            "online": status_counts.get(UserStatus.ONLINE.value, 0),
            "away": status_counts.get(UserStatus.AWAY.value, 0),
            "busy": status_counts.get(UserStatus.BUSY.value, 0),
            "offline": status_counts.get(UserStatus.OFFLINE.value, 0)
        }


# Global presence manager instance
_presence_manager: Optional[PresenceManager] = None


def get_presence_manager() -> PresenceManager:
    """
    Get the global presence manager instance.

    Returns:
        PresenceManager instance
    """
    global _presence_manager
    if _presence_manager is None:
        _presence_manager = PresenceManager()
    return _presence_manager
