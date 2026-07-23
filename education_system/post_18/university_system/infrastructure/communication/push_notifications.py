"""
Web Push Notifications Service

Implements web push notifications using the WebPush protocol.
Requires py-vapid and pywebpush libraries.
"""

import logging
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.infrastructure.communication.models import PushSubscription, NotificationStatus

logger = logging.getLogger(__name__)

# Optional dependency - graceful degradation if not available
try:
    from pywebpush import webpush, WebPushException
    WEBPUSH_AVAILABLE = True
except ImportError:
    WEBPUSH_AVAILABLE = False
    logger.warning("pywebpush not available - push notifications disabled")


class PushNotificationService:
    """Service for sending web push notifications"""

    def __init__(self):
        """Initialize push notification service"""
        self.vapid_private_key = os.getenv('VAPID_PRIVATE_KEY', '')
        self.vapid_public_key = os.getenv('VAPID_PUBLIC_KEY', '')
        self.vapid_claims = {
            "sub": os.getenv('VAPID_SUBJECT', 'mailto:admin@university.edu')
        }
        self._ensure_tables()

    def is_available(self) -> bool:
        """Check if push notifications are available"""
        return WEBPUSH_AVAILABLE and bool(self.vapid_private_key) and bool(self.vapid_public_key)

    def _ensure_tables(self):
        """Create push subscription tables"""
        try:
            with transaction() as conn:
                # Push subscriptions table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS push_subscriptions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        endpoint TEXT NOT NULL UNIQUE,
                        p256dh_key TEXT NOT NULL,
                        auth_key TEXT NOT NULL,
                        user_agent TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used TIMESTAMP,
                        is_active INTEGER DEFAULT 1
                    )
                ''')

                # Push delivery log
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS push_delivery_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        subscription_id INTEGER,
                        user_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        message TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        error_message TEXT,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        delivered_at TIMESTAMP,
                        FOREIGN KEY (subscription_id) REFERENCES push_subscriptions(id)
                    )
                ''')

                # Create indexes
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user_id
                    ON push_subscriptions(user_id, is_active)
                ''')

                logger.info("Push notification tables ensured")
        except Exception as e:
            logger.error(f"Error creating push notification tables: {e}")

    def subscribe_user(
        self,
        user_id: str,
        endpoint: str,
        p256dh_key: str,
        auth_key: str,
        user_agent: Optional[str] = None
    ) -> Optional[int]:
        """
        Subscribe user to push notifications

        Args:
            user_id: User ID
            endpoint: Push service endpoint
            p256dh_key: p256dh encryption key
            auth_key: Auth secret
            user_agent: User agent string

        Returns:
            Subscription ID or None on failure
        """
        try:
            with transaction() as conn:
                # Deactivate existing subscriptions for this endpoint
                conn.execute('''
                    UPDATE push_subscriptions
                    SET is_active = 0
                    WHERE endpoint = ?
                ''', (endpoint,))

                # Create new subscription
                cursor = conn.execute('''
                    INSERT INTO push_subscriptions (
                        user_id, endpoint, p256dh_key, auth_key, user_agent
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (user_id, endpoint, p256dh_key, auth_key, user_agent))

                subscription_id = cursor.lastrowid
                logger.info(f"User {user_id} subscribed to push notifications")
                return subscription_id

        except Exception as e:
            logger.error(f"Error subscribing user to push: {e}")
            return None

    def unsubscribe_user(self, user_id: str, endpoint: Optional[str] = None) -> bool:
        """
        Unsubscribe user from push notifications

        Args:
            user_id: User ID
            endpoint: Specific endpoint to unsubscribe (or None for all)

        Returns:
            True if successful
        """
        try:
            with transaction() as conn:
                if endpoint:
                    conn.execute('''
                        UPDATE push_subscriptions
                        SET is_active = 0
                        WHERE user_id = ? AND endpoint = ?
                    ''', (user_id, endpoint))
                else:
                    conn.execute('''
                        UPDATE push_subscriptions
                        SET is_active = 0
                        WHERE user_id = ?
                    ''', (user_id,))

                logger.info(f"User {user_id} unsubscribed from push notifications")
                return True

        except Exception as e:
            logger.error(f"Error unsubscribing user from push: {e}")
            return False

    def get_user_subscriptions(self, user_id: str) -> List[PushSubscription]:
        """Get all active push subscriptions for user"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT id, user_id, endpoint, p256dh_key, auth_key,
                           user_agent, created_at, last_used, is_active
                    FROM push_subscriptions
                    WHERE user_id = ? AND is_active = 1
                ''', (user_id,))

                subscriptions = []
                for row in cursor.fetchall():
                    subscriptions.append(PushSubscription(
                        id=row[0],
                        user_id=row[1],
                        endpoint=row[2],
                        p256dh_key=row[3],
                        auth_key=row[4],
                        user_agent=row[5],
                        created_at=datetime.fromisoformat(row[6]) if row[6] else datetime.utcnow(),
                        last_used=datetime.fromisoformat(row[7]) if row[7] else None,
                        is_active=bool(row[8])
                    ))

                return subscriptions

        except Exception as e:
            logger.error(f"Error fetching user subscriptions: {e}")
            return []

    def send_push_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        icon: Optional[str] = None,
        badge: Optional[str] = None,
        action_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send push notification to user

        Args:
            user_id: Target user ID
            title: Notification title
            message: Notification message
            data: Additional data
            icon: Icon URL
            badge: Badge URL
            action_url: URL to open on click

        Returns:
            Dictionary with delivery results
        """
        if not WEBPUSH_AVAILABLE:
            logger.warning("WebPush not available - cannot send push notification")
            return {
                'success': False,
                'error': 'WebPush library not installed',
                'sent': 0,
                'failed': 0
            }

        if not self.vapid_private_key or not self.vapid_public_key:
            logger.warning("VAPID keys not configured - cannot send push notification")
            return {
                'success': False,
                'error': 'VAPID keys not configured',
                'sent': 0,
                'failed': 0
            }

        subscriptions = self.get_user_subscriptions(user_id)

        if not subscriptions:
            logger.info(f"No push subscriptions found for user {user_id}")
            return {
                'success': False,
                'error': 'No active subscriptions',
                'sent': 0,
                'failed': 0
            }

        # Build notification payload
        payload = {
            'title': title,
            'body': message,
            'icon': icon or '/static/img/notification-icon.png',
            'badge': badge or '/static/img/badge.png',
            'data': data or {},
        }

        if action_url:
            payload['data']['url'] = action_url

        sent_count = 0
        failed_count = 0
        results = []

        for subscription in subscriptions:
            try:
                # Send push notification
                response = webpush(
                    subscription_info=subscription.to_dict(),
                    data=json.dumps(payload),
                    vapid_private_key=self.vapid_private_key,
                    vapid_claims=self.vapid_claims
                )

                # Log successful delivery
                self._log_delivery(
                    subscription.id,
                    user_id,
                    title,
                    message,
                    NotificationStatus.SENT,
                    None
                )

                # Update last used timestamp
                self._update_last_used(subscription.id)

                sent_count += 1
                results.append({
                    'subscription_id': subscription.id,
                    'status': 'sent',
                    'status_code': response.status_code
                })

            except WebPushException as e:
                logger.error(f"WebPush error for subscription {subscription.id}: {e}")

                # Check if subscription is no longer valid (410 Gone)
                if e.response and e.response.status_code == 410:
                    self._deactivate_subscription(subscription.id)

                # Log failed delivery
                self._log_delivery(
                    subscription.id,
                    user_id,
                    title,
                    message,
                    NotificationStatus.FAILED,
                    str(e)
                )

                failed_count += 1
                results.append({
                    'subscription_id': subscription.id,
                    'status': 'failed',
                    'error': str(e)
                })

            except Exception as e:
                logger.error(f"Error sending push to subscription {subscription.id}: {e}")
                failed_count += 1
                results.append({
                    'subscription_id': subscription.id,
                    'status': 'failed',
                    'error': str(e)
                })

        return {
            'success': sent_count > 0,
            'sent': sent_count,
            'failed': failed_count,
            'results': results
        }

    def _log_delivery(
        self,
        subscription_id: Optional[int],
        user_id: str,
        title: str,
        message: str,
        status: NotificationStatus,
        error_message: Optional[str]
    ):
        """Log push notification delivery attempt"""
        try:
            with transaction() as conn:
                conn.execute('''
                    INSERT INTO push_delivery_log (
                        subscription_id, user_id, title, message,
                        status, error_message, delivered_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    subscription_id,
                    user_id,
                    title,
                    message,
                    status.value,
                    error_message,
                    datetime.utcnow() if status == NotificationStatus.SENT else None
                ))
        except Exception as e:
            logger.error(f"Error logging push delivery: {e}")

    def _update_last_used(self, subscription_id: int):
        """Update subscription last used timestamp"""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE push_subscriptions
                    SET last_used = ?
                    WHERE id = ?
                ''', (datetime.utcnow(), subscription_id))
        except Exception as e:
            logger.error(f"Error updating subscription last_used: {e}")

    def _deactivate_subscription(self, subscription_id: int):
        """Deactivate invalid subscription"""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE push_subscriptions
                    SET is_active = 0
                    WHERE id = ?
                ''', (subscription_id,))
            logger.info(f"Deactivated invalid subscription {subscription_id}")
        except Exception as e:
            logger.error(f"Error deactivating subscription: {e}")

    def get_vapid_public_key(self) -> Optional[str]:
        """Get VAPID public key for client-side subscription"""
        return self.vapid_public_key if self.vapid_public_key else None


# Singleton instance
_push_notification_service: Optional[PushNotificationService] = None


def get_push_notification_service() -> PushNotificationService:
    """Get or create push notification service singleton"""
    global _push_notification_service
    if _push_notification_service is None:
        _push_notification_service = PushNotificationService()
    return _push_notification_service
