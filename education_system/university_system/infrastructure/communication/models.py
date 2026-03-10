"""
Data models for Enhanced Communication Systems
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List

# Re-export existing enums from realtime_notifications
from education_system.university_system.infrastructure.communication.realtime_notifications import (
    NotificationType,
    NotificationPriority,
    Notification as InAppNotification,
)


class NotificationStatus(Enum):
    """Status of notification delivery"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"


class WebhookEvent(Enum):
    """Types of webhook events"""
    STUDENT_ENROLLED = "student.enrolled"
    STUDENT_GRADUATED = "student.graduated"
    GRADE_POSTED = "grade.posted"
    PAYMENT_RECEIVED = "payment.received"
    COURSE_CREATED = "course.created"
    COURSE_UPDATED = "course.updated"
    APPLICATION_SUBMITTED = "application.submitted"
    APPLICATION_APPROVED = "application.approved"
    ASSIGNMENT_SUBMITTED = "assignment.submitted"
    SCHOLARSHIP_AWARDED = "scholarship.awarded"


@dataclass
class PushSubscription:
    """Web Push subscription details"""
    id: Optional[int] = None
    user_id: str = ""
    endpoint: str = ""
    p256dh_key: str = ""
    auth_key: str = ""
    user_agent: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'endpoint': self.endpoint,
            'keys': {
                'p256dh': self.p256dh_key,
                'auth': self.auth_key
            }
        }


@dataclass
class WebhookSubscription:
    """Webhook subscription configuration"""
    id: Optional[int] = None
    name: str = ""
    url: str = ""
    secret: str = ""
    events: List[str] = field(default_factory=list)
    is_active: bool = True
    retry_count: int = 3
    timeout_seconds: int = 5
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


@dataclass
class WebhookDelivery:
    """Webhook delivery attempt record"""
    id: Optional[int] = None
    webhook_id: int = 0
    event_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    status_code: Optional[int] = None
    response_body: str = ""
    error_message: str = ""
    attempt_number: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
    delivered_at: Optional[datetime] = None


@dataclass
class NotificationPreference:
    """User notification preferences"""
    id: Optional[int] = None
    user_id: str = ""
    notification_type: str = ""
    email_enabled: bool = True
    sms_enabled: bool = False
    push_enabled: bool = True
    in_app_enabled: bool = True
    digest_frequency: str = "instant"  # instant, daily, weekly
    quiet_hours_start: Optional[str] = None  # HH:MM format
    quiet_hours_end: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


# Re-export for convenience
__all__ = [
    'NotificationType',
    'NotificationPriority',
    'NotificationStatus',
    'InAppNotification',
    'PushSubscription',
    'WebhookSubscription',
    'WebhookDelivery',
    'WebhookEvent',
    'NotificationPreference',
]
