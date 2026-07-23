"""
Unified Notification Manager

Coordinates all communication channels (email, SMS, push, in-app, webhooks)
and respects user preferences for multi-channel notification delivery.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, time as datetime_time

from education_system.post_18.university_system.infrastructure.communication.models import NotificationType, NotificationPriority
from education_system.post_18.university_system.infrastructure.communication.in_app_notifications import get_in_app_notification_service
from education_system.post_18.university_system.infrastructure.communication.push_notifications import get_push_notification_service
from education_system.post_18.university_system.infrastructure.communication.sms_service import get_sms_service
from education_system.post_18.university_system.infrastructure.communication.slack_integration import get_slack_notifier
from education_system.post_18.university_system.infrastructure.communication.teams_integration import get_teams_notifier
from education_system.post_18.university_system.infrastructure.communication.webhooks import get_webhook_dispatcher
from education_system.post_18.university_system.infrastructure.email import email_service

logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Unified notification manager

    Coordinates multi-channel notification delivery based on user preferences.
    """

    def __init__(self):
        """Initialize notification manager"""
        # Initialize services
        self.in_app = get_in_app_notification_service()
        self.push = get_push_notification_service()
        self.sms = get_sms_service()
        self.email = email_service  # Email service is function-based
        self.slack = get_slack_notifier()
        self.teams = get_teams_notifier()
        self.webhooks = get_webhook_dispatcher()

    def send_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.SYSTEM_ALERT,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        data: Optional[Dict[str, Any]] = None,
        actions: Optional[List[Dict[str, str]]] = None,
        email_template: Optional[str] = None,
        email_data: Optional[Dict[str, Any]] = None,
        sms_override: bool = False,
        trigger_webhooks: bool = True
    ) -> Dict[str, Any]:
        """
        Send notification through appropriate channels

        Args:
            user_id: Target user ID
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            priority: Priority level
            data: Additional data
            actions: In-app notification actions
            email_template: Email template name
            email_data: Email template data
            sms_override: Force SMS even if disabled
            trigger_webhooks: Trigger webhooks for this event

        Returns:
            Delivery results for all channels
        """
        results = {
            'user_id': user_id,
            'channels': {},
            'success': False
        }

        # Get user preferences
        prefs = self.in_app.get_user_preferences(user_id)

        # Check quiet hours
        if self._is_quiet_hours(prefs) and priority != NotificationPriority.URGENT:
            logger.info(f"Skipping notification for {user_id} - quiet hours")
            results['skipped'] = 'quiet_hours'
            return results

        # Get user contact info
        user_info = self._get_user_info(user_id)

        # 1. In-App Notification (always send unless disabled)
        if prefs.get('in_app_enabled', True):
            try:
                notification_id = self.in_app.create_notification(
                    user_id=user_id,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    priority=priority,
                    data=data,
                    actions=actions
                )

                results['channels']['in_app'] = {
                    'success': notification_id is not None,
                    'notification_id': notification_id
                }

                if notification_id:
                    results['success'] = True

            except Exception as e:
                logger.error(f"Error sending in-app notification: {e}")
                results['channels']['in_app'] = {
                    'success': False,
                    'error': str(e)
                }

        # 2. Push Notification
        if prefs.get('push_enabled', True) and self.push.is_available():
            try:
                push_result = self.push.send_push_notification(
                    user_id=user_id,
                    title=title,
                    message=message,
                    data=data
                )

                results['channels']['push'] = push_result

                if push_result.get('success'):
                    results['success'] = True

            except Exception as e:
                logger.error(f"Error sending push notification: {e}")
                results['channels']['push'] = {
                    'success': False,
                    'error': str(e)
                }

        # 3. Email
        if prefs.get('email_enabled', True) and user_info.get('email'):
            try:
                if email_template:
                    # Send templated email
                    email_result = self.email.send_template_email(
                        template_name=email_template,
                        recipient_email=user_info['email'],
                        template_vars=email_data or {}
                    )
                else:
                    # Send simple email
                    email_result = self.email.send_email(
                        recipient_email=user_info['email'],
                        subject=title,
                        body=message
                    )

                results['channels']['email'] = {
                    'success': email_result is not None,
                    'recipient': user_info['email']
                }

                if email_result:
                    results['success'] = True

            except Exception as e:
                logger.error(f"Error sending email: {e}")
                results['channels']['email'] = {
                    'success': False,
                    'error': str(e)
                }

        # 4. SMS (only for urgent or if override)
        if (prefs.get('sms_enabled', False) or sms_override) and user_info.get('phone'):
            # Only send SMS for urgent notifications or if explicitly requested
            if priority == NotificationPriority.URGENT or sms_override:
                try:
                    sms_result = self.sms.send_sms(
                        to_number=user_info['phone'],
                        message=f"{title}: {message}",
                        student_id=user_id
                    )

                    results['channels']['sms'] = {
                        'success': sms_result,
                        'recipient': user_info['phone']
                    }

                    if sms_result:
                        results['success'] = True

                except Exception as e:
                    logger.error(f"Error sending SMS: {e}")
                    results['channels']['sms'] = {
                        'success': False,
                        'error': str(e)
                    }

        # 5. Trigger webhooks
        if trigger_webhooks and data:
            try:
                # Build webhook event based on notification type
                event_type = self._map_notification_to_webhook_event(notification_type)

                if event_type:
                    webhook_payload = {
                        'user_id': user_id,
                        'title': title,
                        'message': message,
                        'type': notification_type.value,
                        'priority': priority.value,
                        'data': data,
                        'timestamp': datetime.utcnow().isoformat()
                    }

                    webhook_result = self.webhooks.dispatch_event(
                        event_type=event_type,
                        payload=webhook_payload
                    )

                    results['channels']['webhooks'] = webhook_result

            except Exception as e:
                logger.error(f"Error dispatching webhooks: {e}")
                results['channels']['webhooks'] = {
                    'success': False,
                    'error': str(e)
                }

        return results

    def send_bulk_notification(
        self,
        user_ids: List[str],
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.ANNOUNCEMENT,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send notification to multiple users

        Args:
            user_ids: List of user IDs
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            priority: Priority level
            data: Additional data

        Returns:
            Bulk delivery results
        """
        results = {
            'total': len(user_ids),
            'success': 0,
            'failed': 0,
            'details': []
        }

        for user_id in user_ids:
            try:
                result = self.send_notification(
                    user_id=user_id,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    priority=priority,
                    data=data,
                    trigger_webhooks=False  # Don't trigger webhooks for bulk
                )

                if result.get('success'):
                    results['success'] += 1
                else:
                    results['failed'] += 1

                results['details'].append(result)

            except Exception as e:
                logger.error(f"Error sending bulk notification to {user_id}: {e}")
                results['failed'] += 1
                results['details'].append({
                    'user_id': user_id,
                    'success': False,
                    'error': str(e)
                })

        logger.info(
            f"Bulk notification sent: {results['success']}/{results['total']} successful"
        )

        return results

    def send_admin_alert(
        self,
        title: str,
        message: str,
        severity: str = "info",
        details: Optional[Dict[str, Any]] = None,
        slack_channel: Optional[str] = None,
        teams_webhook: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send alert to administrators via Slack/Teams

        Args:
            title: Alert title
            message: Alert message
            severity: Severity level (info, warning, error, critical)
            details: Additional details
            slack_channel: Slack channel (optional)
            teams_webhook: Teams webhook URL (optional)

        Returns:
            Delivery results
        """
        results = {
            'slack': None,
            'teams': None
        }

        # Send to Slack
        if self.slack.is_available():
            try:
                fields = []
                if details:
                    for key, value in details.items():
                        fields.append({
                            'title': key.replace('_', ' ').title(),
                            'value': str(value)
                        })

                slack_result = self.slack.send_alert(
                    channel=slack_channel or os.getenv('SLACK_ADMIN_CHANNEL', '#admin-alerts'),
                    title=title,
                    message=message,
                    severity=severity,
                    fields=fields
                )

                results['slack'] = slack_result

            except Exception as e:
                logger.error(f"Error sending Slack alert: {e}")
                results['slack'] = {'success': False, 'error': str(e)}

        # Send to Teams
        if self.teams.is_available():
            try:
                facts = []
                if details:
                    for key, value in details.items():
                        facts.append({
                            'name': key.replace('_', ' ').title(),
                            'value': str(value)
                        })

                teams_result = self.teams.send_alert(
                    title=title,
                    message=message,
                    severity=severity,
                    facts=facts,
                    webhook_url=teams_webhook
                )

                results['teams'] = teams_result

            except Exception as e:
                logger.error(f"Error sending Teams alert: {e}")
                results['teams'] = {'success': False, 'error': str(e)}

        return results

    def _is_quiet_hours(self, prefs: Dict[str, Any]) -> bool:
        """Check if current time is in user's quiet hours"""
        start = prefs.get('quiet_hours_start')
        end = prefs.get('quiet_hours_end')

        if not start or not end:
            return False

        try:
            start_time = datetime_time.fromisoformat(start)
            end_time = datetime_time.fromisoformat(end)
            current_time = datetime.now().time()

            # Handle overnight quiet hours (e.g., 22:00 to 07:00)
            if start_time > end_time:
                return current_time >= start_time or current_time <= end_time
            else:
                return start_time <= current_time <= end_time

        except Exception as e:
            logger.error(f"Error checking quiet hours: {e}")
            return False

    def _get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get user contact information"""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT email_address, phone_number
                    FROM students
                    WHERE student_id = ?
                ''', (user_id,))

                row = cursor.fetchone()

                if row:
                    return {
                        'email': row[0],
                        'phone': row[1]
                    }

        except Exception as e:
            logger.error(f"Error fetching user info: {e}")

        return {}

    def _map_notification_to_webhook_event(
        self,
        notification_type: NotificationType
    ) -> Optional[str]:
        """Map notification type to webhook event"""
        mapping = {
            NotificationType.GRADE_POSTED: 'grade.posted',
            NotificationType.ENROLLMENT_CONFIRMED: 'student.enrolled',
            NotificationType.PAYMENT_RECEIVED: 'payment.received',
            NotificationType.COURSE_UPDATE: 'course.updated'
        }

        return mapping.get(notification_type)


# Singleton instance
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """Get or create notification manager singleton"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager


# Convenience functions
def send_notification(
    user_id: str,
    title: str,
    message: str,
    notification_type: NotificationType = NotificationType.SYSTEM_ALERT,
    **kwargs
) -> Dict[str, Any]:
    """Send notification (convenience function)"""
    manager = get_notification_manager()
    return manager.send_notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        **kwargs
    )


def send_admin_alert(
    title: str,
    message: str,
    **kwargs
) -> Dict[str, Any]:
    """Send admin alert (convenience function)"""
    manager = get_notification_manager()
    return manager.send_admin_alert(
        title=title,
        message=message,
        **kwargs
    )


import os
