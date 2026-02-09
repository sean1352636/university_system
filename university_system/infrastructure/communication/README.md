```markdown
# Enhanced Communication Systems

Comprehensive multi-channel notification and communication infrastructure for the University Management System.

## Overview

The Enhanced Communication Systems provide multiple communication channels for delivering notifications, alerts, and messages to users and external systems.

## Features

### 1. Web Push Notifications

Send browser-based push notifications to users even when they're not on your site.

**Setup:**
```bash
# Install dependencies
pip install pywebpush py-vapid

# Generate VAPID keys
vapid --gen

# Set environment variables
export VAPID_PRIVATE_KEY="your_private_key"
export VAPID_PUBLIC_KEY="your_public_key"
export VAPID_SUBJECT="mailto:admin@university.edu"
```

**Usage:**
```python
from university_system.infrastructure.communication import get_push_notification_service

push_service = get_push_notification_service()

# Subscribe user
subscription_id = push_service.subscribe_user(
    user_id="STU001",
    endpoint="https://fcm.googleapis.com/fcm/send/...",
    p256dh_key="BN...",
    auth_key="..."
)

# Send notification
result = push_service.send_push_notification(
    user_id="STU001",
    title="Grade Posted",
    message="Your assignment has been graded",
    icon="/static/img/grade-icon.png",
    action_url="/grades"
)
```

### 2. Webhooks

Event-driven webhooks for integrating with external systems.

**Setup:**
```python
from university_system.infrastructure.communication import get_webhook_dispatcher

webhook_service = get_webhook_dispatcher()

# Create webhook
webhook_id = webhook_service.create_webhook(
    name="Student Enrollment Webhook",
    url="https://external-system.com/webhooks/enrollment",
    secret="your_webhook_secret",
    events=["student.enrolled", "student.graduated"],
    created_by="admin",
    retry_count=3,
    timeout_seconds=5
)
```

**Dispatch events:**
```python
# Trigger webhook event
result = webhook_service.dispatch_event(
    event_type="student.enrolled",
    payload={
        "student_id": "STU001",
        "course_id": "CS101",
        "enrollment_date": "2025-02-01"
    }
)
```

**Webhook Payload:**
```json
{
  "event": "student.enrolled",
  "timestamp": "2025-02-01T12:00:00Z",
  "data": {
    "student_id": "STU001",
    "course_id": "CS101",
    "enrollment_date": "2025-02-01"
  }
}
```

**Signature Verification:**
```python
import hmac
import hashlib

def verify_webhook(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)
```

### 3. In-App Notifications

Persistent notification center with read/unread tracking.

**Usage:**
```python
from university_system.infrastructure.communication import get_in_app_notification_service

notification_service = get_in_app_notification_service()

# Create notification with actions
notification_id = notification_service.create_notification(
    user_id="STU001",
    title="Assignment Graded",
    message="Your CS101 assignment has been graded",
    notification_type=NotificationType.GRADE_POSTED,
    priority=NotificationPriority.NORMAL,
    actions=[
        {"text": "View Grade", "url": "/grades/123"},
        {"text": "Download Feedback", "url": "/grades/123/feedback"}
    ],
    expires_in_days=30
)

# Get unread notifications
unread = notification_service.get_unread_notifications("STU001", limit=20)

# Mark as read
notification_service.mark_as_read(notification_id, "STU001")
```

### 4. Slack Integration

Send notifications to Slack channels.

**Setup:**
```bash
# Set Slack Bot Token
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_ADMIN_CHANNEL="#admin-alerts"
```

**Usage:**
```python
from university_system.infrastructure.communication import get_slack_notifier

slack = get_slack_notifier()

# Send simple message
slack.send_message(
    channel="#general",
    text="New student enrolled!"
)

# Send formatted alert
slack.send_alert(
    channel="#admin-alerts",
    title="Low Attendance Alert",
    message="Student STU001 has attendance below 75%",
    severity="warning",
    fields=[
        {"title": "Student ID", "value": "STU001"},
        {"title": "Attendance", "value": "68%"}
    ]
)

# Send enrollment notification
slack.send_enrollment_notification(
    channel="#enrollments",
    student_name="Alice Johnson",
    course_code="CS101",
    course_name="Introduction to Programming"
)
```

### 5. Microsoft Teams Integration

Send notifications to Microsoft Teams channels.

**Setup:**
```bash
# Configure Teams Incoming Webhook URL
export TEAMS_WEBHOOK_URL="https://outlook.office.com/webhook/..."
```

**Usage:**
```python
from university_system.infrastructure.communication import get_teams_notifier

teams = get_teams_notifier()

# Send alert
teams.send_alert(
    title="System Alert",
    message="Database backup completed successfully",
    severity="info",
    facts=[
        {"name": "Backup Size", "value": "1.2 GB"},
        {"name": "Duration", "value": "5 minutes"}
    ]
)

# Send actionable message
teams.send_actionable_message(
    title="Grade Approval Required",
    message="10 assignments need approval",
    actions=[
        {"name": "View Pending", "url": "https://university.edu/grades/pending"}
    ]
)
```

### 6. Unified Notification Manager

Coordinate all channels based on user preferences.

**Usage:**
```python
from university_system.infrastructure.communication import get_notification_manager

manager = get_notification_manager()

# Send notification through appropriate channels
result = manager.send_notification(
    user_id="STU001",
    title="Assignment Due Tomorrow",
    message="Your CS101 assignment is due tomorrow at 11:59 PM",
    notification_type=NotificationType.DEADLINE_REMINDER,
    priority=NotificationPriority.HIGH,
    email_template="assignment_reminder",
    email_data={"course": "CS101", "assignment": "Homework 3"},
    sms_override=False  # Only send SMS if user enabled it
)

# Send to multiple users
result = manager.send_bulk_notification(
    user_ids=["STU001", "STU002", "STU003"],
    title="Campus Closure",
    message="Campus will be closed tomorrow due to weather",
    notification_type=NotificationType.ANNOUNCEMENT,
    priority=NotificationPriority.URGENT
)

# Send admin alert
result = manager.send_admin_alert(
    title="Database Error",
    message="Connection pool exhausted",
    severity="critical",
    details={
        "error": "Too many connections",
        "pool_size": "100/100",
        "timestamp": "2025-02-01 12:00:00"
    }
)
```

## Notification Preferences

Users can control how they receive notifications.

**Get preferences:**
```python
prefs = notification_service.get_user_preferences("STU001")
# {
#   "email_enabled": True,
#   "sms_enabled": False,
#   "push_enabled": True,
#   "in_app_enabled": True,
#   "digest_frequency": "instant",
#   "quiet_hours_start": "22:00",
#   "quiet_hours_end": "07:00"
# }
```

**Update preferences:**
```python
notification_service.set_user_preferences(
    user_id="STU001",
    email_enabled=True,
    sms_enabled=False,  # Opt out of SMS
    push_enabled=True,
    in_app_enabled=True,
    digest_frequency="daily",  # Get daily digest instead
    quiet_hours_start="22:00",
    quiet_hours_end="07:00"
)
```

## API Endpoints

### Push Notifications
- `POST /api/v1/notifications/push/subscribe` - Subscribe to push
- `DELETE /api/v1/notifications/push/unsubscribe/{user_id}` - Unsubscribe
- `GET /api/v1/notifications/push/vapid-public-key` - Get VAPID public key

### Webhooks
- `POST /api/v1/notifications/webhooks` - Create webhook
- `GET /api/v1/notifications/webhooks` - List webhooks
- `GET /api/v1/notifications/webhooks/{id}` - Get webhook
- `PUT /api/v1/notifications/webhooks/{id}` - Update webhook
- `DELETE /api/v1/notifications/webhooks/{id}` - Delete webhook
- `GET /api/v1/notifications/webhooks/events/available` - List events

### In-App Notifications
- `GET /api/v1/notifications/unread/{user_id}` - Get unread
- `GET /api/v1/notifications/count/{user_id}` - Get count
- `POST /api/v1/notifications/{id}/read` - Mark as read
- `POST /api/v1/notifications/read-all/{user_id}` - Mark all as read
- `DELETE /api/v1/notifications/{id}` - Delete notification

### Preferences
- `GET /api/v1/notifications/preferences/{user_id}` - Get preferences
- `PUT /api/v1/notifications/preferences/{user_id}` - Update preferences

### Unified Delivery
- `POST /api/v1/notifications/send` - Send notification
- `POST /api/v1/notifications/send/bulk` - Send bulk
- `POST /api/v1/notifications/send/admin-alert` - Send admin alert

## Webhook Events

Available webhook event types:

- `student.enrolled` - Student enrollment
- `student.graduated` - Student graduation
- `grade.posted` - Grade published
- `payment.received` - Payment confirmation
- `course.created` - New course
- `course.updated` - Course modified
- `application.submitted` - Application submitted
- `application.approved` - Application approved
- `assignment.submitted` - Assignment submitted
- `scholarship.awarded` - Scholarship awarded

## Best Practices

### 1. User Preferences
Always respect user notification preferences. The NotificationManager does this automatically.

### 2. Quiet Hours
Don't send non-urgent notifications during user's quiet hours.

### 3. Priority Levels
Use appropriate priority levels:
- **LOW (1)**: FYI notifications
- **NORMAL (2)**: Standard notifications
- **HIGH (3)**: Important notifications
- **URGENT (4)**: Critical alerts (bypass quiet hours, enable SMS)

### 4. Webhook Security
Always validate webhook signatures:
```python
# In your webhook endpoint
signature = request.headers.get('X-Webhook-Signature')
if not verify_signature(payload, signature, webhook.secret):
    return 401  # Unauthorized
```

### 5. Error Handling
All services degrade gracefully:
```python
if not push_service.is_available():
    logger.warning("Push notifications not available")
    # Fallback to email or in-app
```

### 6. Batch Operations
Use bulk operations for efficiency:
```python
# Instead of:
for user_id in user_ids:
    send_notification(user_id, ...)

# Do:
send_bulk_notification(user_ids, ...)
```

## Dependencies

**Required:**
- `requests` - HTTP requests for webhooks/Teams

**Optional:**
- `pywebpush` - Web push notifications
- `py-vapid` - VAPID key generation
- `slack-sdk` - Slack integration

Install optional dependencies:
```bash
pip install pywebpush py-vapid slack-sdk
```

## Configuration

### Environment Variables

```bash
# Push Notifications
VAPID_PRIVATE_KEY="your_private_key"
VAPID_PUBLIC_KEY="your_public_key"
VAPID_SUBJECT="mailto:admin@university.edu"

# Slack
SLACK_BOT_TOKEN="xoxb-your-bot-token"
SLACK_ADMIN_CHANNEL="#admin-alerts"

# Microsoft Teams
TEAMS_WEBHOOK_URL="https://outlook.office.com/webhook/..."

# SMS (from existing system)
TWILIO_ACCOUNT_SID="your_account_sid"
TWILIO_AUTH_TOKEN="your_auth_token"
TWILIO_PHONE_NUMBER="+1234567890"
```

## Troubleshooting

### Push Notifications Not Working
1. Check VAPID keys are configured
2. Verify `pywebpush` is installed
3. Check browser console for subscription errors
4. Verify HTTPS (push requires secure origin)

### Webhooks Failing
1. Check webhook URL is accessible
2. Verify HMAC signature validation
3. Check timeout settings (increase if needed)
4. Review webhook delivery logs
5. Process retries: `webhook_service.process_retries()`

### Slack Messages Not Sending
1. Verify `SLACK_BOT_TOKEN` is set
2. Check bot has permission to post in channel
3. Verify `slack-sdk` is installed
4. Check Slack app is installed in workspace

### Teams Messages Not Sending
1. Verify `TEAMS_WEBHOOK_URL` is configured
2. Test webhook URL with curl
3. Check firewall isn't blocking requests
4. Verify MessageCard format is valid

## Monitoring

### Delivery Tracking

```python
# Check push delivery status
with get_connection() as conn:
    cursor = conn.execute("""
        SELECT status, COUNT(*)
        FROM push_delivery_log
        WHERE sent_at > datetime('now', '-1 day')
        GROUP BY status
    """)
    for status, count in cursor:
        print(f"{status}: {count}")

# Check webhook delivery status
with get_connection() as conn:
    cursor = conn.execute("""
        SELECT event_type, status_code, COUNT(*)
        FROM webhook_deliveries
        WHERE created_at > datetime('now', '-1 day')
        GROUP BY event_type, status_code
    """)
```

### Health Checks

```python
# Check service availability
services = {
    'push': get_push_notification_service().is_available(),
    'slack': get_slack_notifier().is_available(),
    'teams': get_teams_notifier().is_available()
}

for service, available in services.items():
    print(f"{service}: {'✓' if available else '✗'}")
```

## Examples

See `examples/communication_demo.py` for complete usage examples.

## License

MIT License - See LICENSE file for details.
```
