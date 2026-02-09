"""
Real-Time Activity Stream

Provides real-time activity feed and event tracking.
"""

import logging
from typing import List, Optional, Dict, Set
from datetime import datetime, timedelta
from enum import Enum
from .websocket_manager import get_websocket_manager, MessageType

logger = logging.getLogger(__name__)


class ActivityType(str, Enum):
    """Activity types"""
    GRADE_POSTED = "grade_posted"
    ASSIGNMENT_SUBMITTED = "assignment_submitted"
    ASSIGNMENT_CREATED = "assignment_created"
    ENROLLMENT_ADDED = "enrollment_added"
    COURSE_UPDATED = "course_updated"
    ANNOUNCEMENT_POSTED = "announcement_posted"
    COMMENT_ADDED = "comment_added"
    FILE_UPLOADED = "file_uploaded"
    PAYMENT_MADE = "payment_made"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"


class ActivityVisibility(str, Enum):
    """Activity visibility levels"""
    PUBLIC = "public"           # Visible to all users
    COURSE = "course"           # Visible to course members
    DEPARTMENT = "department"   # Visible to department members
    PRIVATE = "private"         # Visible only to involved users


class ActivityStream:
    """
    Real-time activity stream service.

    Tracks and broadcasts user activities across the system.
    """

    def __init__(self):
        """Initialize activity stream"""
        self.ws_manager = get_websocket_manager()

        # Store recent activities
        # list of activity dictionaries
        self.activities: List[dict] = []

        # user_id -> list of activities (personalized feed)
        self.user_feeds: Dict[str, List[dict]] = {}

        # Track activity subscriptions
        # user_id -> set of filter criteria
        self.subscriptions: Dict[str, Set[str]] = {}

    async def post_activity(
        self,
        activity_type: ActivityType,
        user_id: str,
        title: str,
        description: str,
        visibility: ActivityVisibility = ActivityVisibility.PUBLIC,
        metadata: Optional[dict] = None,
        related_users: Optional[List[str]] = None,
        course_id: Optional[str] = None,
        department_id: Optional[str] = None
    ) -> dict:
        """
        Post a new activity to the stream.

        Args:
            activity_type: Type of activity
            user_id: User who performed the activity
            title: Activity title
            description: Activity description
            visibility: Visibility level
            metadata: Additional metadata
            related_users: Users directly related to this activity
            course_id: Related course ID (for course activities)
            department_id: Related department ID (for department activities)

        Returns:
            Activity data dictionary
        """
        activity = {
            "activity_id": f"act_{datetime.utcnow().timestamp()}",
            "type": activity_type.value,
            "user_id": user_id,
            "title": title,
            "description": description,
            "visibility": visibility.value,
            "metadata": metadata or {},
            "related_users": related_users or [],
            "course_id": course_id,
            "department_id": department_id,
            "timestamp": datetime.utcnow().isoformat(),
            "likes": 0,
            "comments": []
        }

        # Store activity
        self.activities.append(activity)

        # Limit activity history (keep last 1000)
        if len(self.activities) > 1000:
            self.activities = self.activities[-1000:]

        # Add to relevant user feeds
        await self._add_to_feeds(activity)

        # Broadcast activity
        await self._broadcast_activity(activity)

        logger.info(f"Activity posted: {activity_type.value} by user {user_id}")
        return activity

    async def subscribe_to_activities(
        self,
        user_id: str,
        filters: Optional[List[str]] = None
    ):
        """
        Subscribe a user to activity updates.

        Args:
            user_id: User identifier
            filters: Optional list of activity type filters
        """
        if user_id not in self.subscriptions:
            self.subscriptions[user_id] = set()

        if filters:
            self.subscriptions[user_id].update(filters)

        logger.info(f"User {user_id} subscribed to activities")

    async def unsubscribe_from_activities(self, user_id: str):
        """
        Unsubscribe a user from activity updates.

        Args:
            user_id: User identifier
        """
        if user_id in self.subscriptions:
            del self.subscriptions[user_id]

        logger.info(f"User {user_id} unsubscribed from activities")

    def get_activity_feed(
        self,
        user_id: str,
        activity_types: Optional[List[ActivityType]] = None,
        limit: int = 50,
        before_timestamp: Optional[str] = None
    ) -> List[dict]:
        """
        Get activity feed for a user.

        Args:
            user_id: User identifier
            activity_types: Filter by activity types
            limit: Maximum number of activities to return
            before_timestamp: Get activities before this timestamp

        Returns:
            List of activity dictionaries
        """
        # Get user's feed or all activities
        if user_id in self.user_feeds:
            activities = self.user_feeds[user_id]
        else:
            activities = self.activities

        # Filter by type
        if activity_types:
            type_values = [t.value for t in activity_types]
            activities = [
                a for a in activities
                if a["type"] in type_values
            ]

        # Filter by timestamp
        if before_timestamp:
            activities = [
                a for a in activities
                if a["timestamp"] < before_timestamp
            ]

        # Return most recent first
        return list(reversed(activities[-limit:]))

    def get_recent_activities(
        self,
        minutes: int = 60,
        activity_types: Optional[List[ActivityType]] = None
    ) -> List[dict]:
        """
        Get activities from the last N minutes.

        Args:
            minutes: Number of minutes to look back
            activity_types: Filter by activity types

        Returns:
            List of activity dictionaries
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        cutoff_iso = cutoff_time.isoformat()

        activities = [
            a for a in self.activities
            if a["timestamp"] >= cutoff_iso
        ]

        if activity_types:
            type_values = [t.value for t in activity_types]
            activities = [
                a for a in activities
                if a["type"] in type_values
            ]

        return activities

    async def like_activity(self, activity_id: str, user_id: str):
        """
        Like an activity.

        Args:
            activity_id: Activity identifier
            user_id: User who liked the activity
        """
        for activity in self.activities:
            if activity["activity_id"] == activity_id:
                activity["likes"] += 1

                # Broadcast like update
                await self._broadcast_activity_update(
                    activity_id,
                    "like",
                    user_id
                )
                break

    async def comment_on_activity(
        self,
        activity_id: str,
        user_id: str,
        comment_text: str
    ):
        """
        Add a comment to an activity.

        Args:
            activity_id: Activity identifier
            user_id: User adding comment
            comment_text: Comment text
        """
        comment = {
            "comment_id": f"comment_{datetime.utcnow().timestamp()}",
            "user_id": user_id,
            "text": comment_text,
            "timestamp": datetime.utcnow().isoformat()
        }

        for activity in self.activities:
            if activity["activity_id"] == activity_id:
                activity["comments"].append(comment)

                # Broadcast comment update
                await self._broadcast_activity_update(
                    activity_id,
                    "comment",
                    user_id,
                    comment
                )
                break

    async def _add_to_feeds(self, activity: dict):
        """
        Add activity to relevant user feeds.

        Args:
            activity: Activity data
        """
        visibility = activity["visibility"]

        if visibility == ActivityVisibility.PUBLIC.value:
            # Add to all user feeds (or rely on broadcast)
            pass

        elif visibility == ActivityVisibility.PRIVATE.value:
            # Add only to related users' feeds
            for user_id in activity.get("related_users", []):
                if user_id not in self.user_feeds:
                    self.user_feeds[user_id] = []
                self.user_feeds[user_id].append(activity)

        # Add to activity owner's feed
        owner_id = activity["user_id"]
        if owner_id not in self.user_feeds:
            self.user_feeds[owner_id] = []
        self.user_feeds[owner_id].append(activity)

    async def _broadcast_activity(self, activity: dict):
        """
        Broadcast activity to subscribed users.

        Args:
            activity: Activity data
        """
        activity_message = {
            "type": MessageType.ACTIVITY,
            **activity
        }

        visibility = activity["visibility"]

        if visibility == ActivityVisibility.PUBLIC.value:
            # Broadcast to all subscribed users
            for user_id in self.subscriptions.keys():
                if self._should_receive_activity(user_id, activity):
                    await self.ws_manager.send_to_user(user_id, activity_message)

        elif visibility == ActivityVisibility.PRIVATE.value:
            # Send only to related users
            for user_id in activity.get("related_users", []):
                if user_id in self.subscriptions:
                    await self.ws_manager.send_to_user(user_id, activity_message)

    def _should_receive_activity(self, user_id: str, activity: dict) -> bool:
        """
        Check if a user should receive an activity.

        Args:
            user_id: User identifier
            activity: Activity data

        Returns:
            True if user should receive the activity
        """
        if user_id not in self.subscriptions:
            return False

        # Check filters
        filters = self.subscriptions[user_id]
        if not filters:
            return True  # No filters, receive all

        # Check if activity type matches filters
        return activity["type"] in filters

    async def _broadcast_activity_update(
        self,
        activity_id: str,
        update_type: str,
        user_id: str,
        data: Optional[dict] = None
    ):
        """
        Broadcast activity update (like, comment).

        Args:
            activity_id: Activity identifier
            update_type: Type of update
            user_id: User who made the update
            data: Additional update data
        """
        update_message = {
            "type": MessageType.ACTIVITY,
            "update_type": update_type,
            "activity_id": activity_id,
            "user_id": user_id,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Broadcast to all subscribed users
        for subscribed_user_id in self.subscriptions.keys():
            await self.ws_manager.send_to_user(subscribed_user_id, update_message)

    def get_stats(self) -> dict:
        """
        Get activity stream statistics.

        Returns:
            Dictionary with activity stats
        """
        activity_type_counts = {}
        for activity in self.activities:
            activity_type = activity["type"]
            activity_type_counts[activity_type] = activity_type_counts.get(activity_type, 0) + 1

        return {
            "total_activities": len(self.activities),
            "total_subscribers": len(self.subscriptions),
            "activity_type_counts": activity_type_counts,
            "activities_last_hour": len(self.get_recent_activities(minutes=60))
        }


# Global activity stream instance
_activity_stream: Optional[ActivityStream] = None


def get_activity_stream() -> ActivityStream:
    """
    Get the global activity stream instance.

    Returns:
        ActivityStream instance
    """
    global _activity_stream
    if _activity_stream is None:
        _activity_stream = ActivityStream()
    return _activity_stream
