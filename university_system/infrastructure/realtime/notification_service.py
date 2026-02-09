"""
Real-Time Notification Service

Sends real-time notifications to connected users via WebSocket.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from .websocket_manager import get_websocket_manager, MessageType

logger = logging.getLogger(__name__)


class NotificationPriority(str, Enum):
    """Notification priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class NotificationCategory(str, Enum):
    """Notification categories"""
    GRADE = "grade"
    ASSIGNMENT = "assignment"
    ENROLLMENT = "enrollment"
    ANNOUNCEMENT = "announcement"
    PAYMENT = "payment"
    MESSAGE = "message"
    ALERT = "alert"
    SYSTEM = "system"


class NotificationService:
    """
    Service for sending real-time notifications to users.

    Handles notification delivery, priority, and read status tracking.
    """

    def __init__(self):
        """Initialize notification service"""
        self.ws_manager = get_websocket_manager()

        # Track notification history (in-memory, consider using database)
        # user_id -> list of notification dicts
        self.notification_history: Dict[str, List[dict]] = {}

    async def send_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        category: NotificationCategory,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        data: Optional[dict] = None,
        action_url: Optional[str] = None,
        persistent: bool = True
    ) -> bool:
        """
        Send a real-time notification to a user.

        Args:
            user_id: Target user ID
            title: Notification title
            message: Notification message
            category: Notification category
            priority: Notification priority
            data: Additional data payload
            action_url: URL for notification action
            persistent: Whether to save notification history

        Returns:
            True if notification was sent
        """
        notification = {
            "type": MessageType.NOTIFICATION,
            "notification_id": f"{user_id}_{datetime.utcnow().timestamp()}",
            "title": title,
            "message": message,
            "category": category.value,
            "priority": priority.value,
            "data": data or {},
            "action_url": action_url,
            "timestamp": datetime.utcnow().isoformat(),
            "read": False
        }

        # Send to user if online
        sent_count = await self.ws_manager.send_to_user(user_id, notification)

        # Store in history if persistent
        if persistent:
            if user_id not in self.notification_history:
                self.notification_history[user_id] = []
            self.notification_history[user_id].append(notification)

            # Limit history size (keep last 100 notifications)
            if len(self.notification_history[user_id]) > 100:
                self.notification_history[user_id] = self.notification_history[user_id][-100:]

        logger.info(
            f"Sent {category.value} notification to user {user_id} "
            f"(priority: {priority.value}, delivered: {sent_count > 0})"
        )

        return sent_count > 0

    async def send_to_multiple(
        self,
        user_ids: List[str],
        title: str,
        message: str,
        category: NotificationCategory,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        data: Optional[dict] = None
    ):
        """
        Send notification to multiple users.

        Args:
            user_ids: List of user IDs
            title: Notification title
            message: Notification message
            category: Notification category
            priority: Notification priority
            data: Additional data payload
        """
        for user_id in user_ids:
            await self.send_notification(
                user_id=user_id,
                title=title,
                message=message,
                category=category,
                priority=priority,
                data=data
            )

    async def notify_grade_update(
        self,
        student_id: str,
        course_name: str,
        grade: str,
        assignment_name: Optional[str] = None
    ):
        """
        Send grade update notification.

        Args:
            student_id: Student ID
            course_name: Course name
            grade: Grade value
            assignment_name: Assignment name (if applicable)
        """
        if assignment_name:
            title = f"New Grade: {assignment_name}"
            message = f"Your grade for '{assignment_name}' in {course_name} is now available: {grade}"
        else:
            title = f"New Grade: {course_name}"
            message = f"Your final grade for {course_name} has been posted: {grade}"

        await self.send_notification(
            user_id=student_id,
            title=title,
            message=message,
            category=NotificationCategory.GRADE,
            priority=NotificationPriority.HIGH,
            data={
                "course": course_name,
                "grade": grade,
                "assignment": assignment_name
            }
        )

    async def notify_assignment_posted(
        self,
        student_ids: List[str],
        course_name: str,
        assignment_name: str,
        due_date: str
    ):
        """
        Notify students of new assignment.

        Args:
            student_ids: List of student IDs
            course_name: Course name
            assignment_name: Assignment name
            due_date: Due date string
        """
        await self.send_to_multiple(
            user_ids=student_ids,
            title=f"New Assignment: {assignment_name}",
            message=f"A new assignment has been posted in {course_name}. Due: {due_date}",
            category=NotificationCategory.ASSIGNMENT,
            priority=NotificationPriority.MEDIUM,
            data={
                "course": course_name,
                "assignment": assignment_name,
                "due_date": due_date
            }
        )

    async def notify_enrollment_success(
        self,
        student_id: str,
        course_name: str,
        course_code: str
    ):
        """
        Notify student of successful enrollment.

        Args:
            student_id: Student ID
            course_name: Course name
            course_code: Course code
        """
        await self.send_notification(
            user_id=student_id,
            title="Enrollment Confirmed",
            message=f"You have successfully enrolled in {course_code}: {course_name}",
            category=NotificationCategory.ENROLLMENT,
            priority=NotificationPriority.HIGH,
            data={
                "course_code": course_code,
                "course_name": course_name
            }
        )

    async def notify_payment_received(
        self,
        student_id: str,
        amount: float,
        description: str
    ):
        """
        Notify student of payment received.

        Args:
            student_id: Student ID
            amount: Payment amount
            description: Payment description
        """
        await self.send_notification(
            user_id=student_id,
            title="Payment Received",
            message=f"Payment of ${amount:.2f} received for {description}",
            category=NotificationCategory.PAYMENT,
            priority=NotificationPriority.MEDIUM,
            data={
                "amount": amount,
                "description": description
            }
        )

    async def send_system_alert(
        self,
        user_ids: List[str],
        title: str,
        message: str,
        urgent: bool = False
    ):
        """
        Send system alert to users.

        Args:
            user_ids: List of user IDs
            title: Alert title
            message: Alert message
            urgent: Whether alert is urgent
        """
        priority = NotificationPriority.URGENT if urgent else NotificationPriority.HIGH

        await self.send_to_multiple(
            user_ids=user_ids,
            title=title,
            message=message,
            category=NotificationCategory.ALERT,
            priority=priority
        )

    def get_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[dict]:
        """
        Get notification history for a user.

        Args:
            user_id: User ID
            unread_only: Return only unread notifications
            limit: Maximum number of notifications to return

        Returns:
            List of notification dictionaries
        """
        if user_id not in self.notification_history:
            return []

        notifications = self.notification_history[user_id]

        if unread_only:
            notifications = [n for n in notifications if not n.get("read", False)]

        # Return most recent first
        return list(reversed(notifications[-limit:]))

    async def mark_as_read(self, user_id: str, notification_id: str):
        """
        Mark a notification as read.

        Args:
            user_id: User ID
            notification_id: Notification ID
        """
        if user_id in self.notification_history:
            for notification in self.notification_history[user_id]:
                if notification.get("notification_id") == notification_id:
                    notification["read"] = True
                    notification["read_at"] = datetime.utcnow().isoformat()
                    break


# Global notification service instance
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """
    Get the global notification service instance.

    Returns:
        NotificationService instance
    """
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
