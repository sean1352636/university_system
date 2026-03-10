"""Central Communication Infrastructure

This package provides unified communication services for the University System.

Services:
- SMS: Central SMS service for notifications (sms_service.py)
- Email: Uses infrastructure.email.email_service
- Templates: Email template management
- Logging: Communication audit trail
- Real-time Notifications: WebSocket-based notifications
- Push Notifications: Web Push for browsers
- Webhooks: Event-driven integrations
- In-App Notifications: Notification center
- Slack: Slack channel integration
- Teams: Microsoft Teams integration
- Notification Manager: Unified multi-channel delivery

For MFA-specific SMS/Email, use infrastructure.auth modules instead.
"""

from education_system.university_system.infrastructure.communication.sms_service import (
    SMSService,
    SMSProvider,
    get_sms_service,
    send_sms,
    send_bulk_sms
)

# Real-time notifications
from education_system.university_system.infrastructure.communication.realtime_notifications import (
    NotificationService,
    Notification,
    NotificationType,
    NotificationPriority,
    NotificationHandler,
    DatabaseNotificationHandler,
    InMemoryNotificationHandler,
    get_notification_service,
    notify_grade_posted,
    notify_message_received,
)

# Enhanced communication systems
from education_system.university_system.infrastructure.communication.models import (
    NotificationStatus,
    WebhookEvent,
    PushSubscription,
    WebhookSubscription,
    WebhookDelivery,
    NotificationPreference,
)

from education_system.university_system.infrastructure.communication.push_notifications import (
    PushNotificationService,
    get_push_notification_service,
)

from education_system.university_system.infrastructure.communication.webhooks import (
    WebhookDispatcher,
    get_webhook_dispatcher,
)

from education_system.university_system.infrastructure.communication.in_app_notifications import (
    InAppNotificationService,
    get_in_app_notification_service,
)

from education_system.university_system.infrastructure.communication.slack_integration import (
    SlackNotifier,
    get_slack_notifier,
)

from education_system.university_system.infrastructure.communication.teams_integration import (
    TeamsNotifier,
    get_teams_notifier,
)

from education_system.university_system.infrastructure.communication.notification_manager import (
    NotificationManager,
    get_notification_manager,
    send_notification,
    send_admin_alert,
)

__all__ = [
    # SMS Services
    'SMSService',
    'SMSProvider',
    'get_sms_service',
    'send_sms',
    'send_bulk_sms',
    # Real-time Notifications (Base)
    'NotificationService',
    'Notification',
    'NotificationType',
    'NotificationPriority',
    'NotificationHandler',
    'DatabaseNotificationHandler',
    'InMemoryNotificationHandler',
    'get_notification_service',
    'notify_grade_posted',
    'notify_message_received',
    # Models
    'NotificationStatus',
    'WebhookEvent',
    'PushSubscription',
    'WebhookSubscription',
    'WebhookDelivery',
    'NotificationPreference',
    # Push Notifications
    'PushNotificationService',
    'get_push_notification_service',
    # Webhooks
    'WebhookDispatcher',
    'get_webhook_dispatcher',
    # In-App Notifications
    'InAppNotificationService',
    'get_in_app_notification_service',
    # Slack Integration
    'SlackNotifier',
    'get_slack_notifier',
    # Teams Integration
    'TeamsNotifier',
    'get_teams_notifier',
    # Unified Manager
    'NotificationManager',
    'get_notification_manager',
    'send_notification',
    'send_admin_alert',
]
