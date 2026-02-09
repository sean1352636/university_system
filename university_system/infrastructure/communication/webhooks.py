"""
Webhook Dispatcher Service

Implements webhook system for event-driven integrations.
Features retry logic with exponential backoff and delivery tracking.
"""

import logging
import json
import hmac
import hashlib
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import requests

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.communication.models import (
    WebhookSubscription,
    WebhookDelivery,
    WebhookEvent
)

logger = logging.getLogger(__name__)


class WebhookDispatcher:
    """Service for dispatching webhooks to external systems"""

    def __init__(self):
        """Initialize webhook dispatcher"""
        self._ensure_tables()

    def _ensure_tables(self):
        """Create webhook tables"""
        try:
            with transaction() as conn:
                # Webhook subscriptions table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS webhook_subscriptions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        url TEXT NOT NULL,
                        secret TEXT NOT NULL,
                        events_json TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        retry_count INTEGER DEFAULT 3,
                        timeout_seconds INTEGER DEFAULT 5,
                        created_by TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                ''')

                # Webhook delivery log
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS webhook_deliveries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        webhook_id INTEGER NOT NULL,
                        event_type TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        status_code INTEGER,
                        response_body TEXT,
                        error_message TEXT,
                        attempt_number INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        delivered_at TIMESTAMP,
                        next_retry_at TIMESTAMP,
                        FOREIGN KEY (webhook_id) REFERENCES webhook_subscriptions(id)
                    )
                ''')

                # Create indexes
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook_id
                    ON webhook_deliveries(webhook_id, created_at DESC)
                ''')

                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_retry
                    ON webhook_deliveries(next_retry_at)
                    WHERE next_retry_at IS NOT NULL
                ''')

                logger.info("Webhook tables ensured")
        except Exception as e:
            logger.error(f"Error creating webhook tables: {e}")

    def create_webhook(
        self,
        name: str,
        url: str,
        secret: str,
        events: List[str],
        created_by: str,
        retry_count: int = 3,
        timeout_seconds: int = 5
    ) -> Optional[int]:
        """
        Create a new webhook subscription

        Args:
            name: Webhook name
            url: Target URL
            secret: Secret for HMAC signature
            events: List of event types to subscribe to
            created_by: User creating the webhook
            retry_count: Number of retry attempts
            timeout_seconds: Request timeout

        Returns:
            Webhook ID or None on failure
        """
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO webhook_subscriptions (
                        name, url, secret, events_json, created_by,
                        retry_count, timeout_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    name,
                    url,
                    secret,
                    json.dumps(events),
                    created_by,
                    retry_count,
                    timeout_seconds
                ))

                webhook_id = cursor.lastrowid
                logger.info(f"Created webhook subscription: {name} (ID: {webhook_id})")
                return webhook_id

        except Exception as e:
            logger.error(f"Error creating webhook: {e}")
            return None

    def update_webhook(
        self,
        webhook_id: int,
        name: Optional[str] = None,
        url: Optional[str] = None,
        secret: Optional[str] = None,
        events: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
        retry_count: Optional[int] = None,
        timeout_seconds: Optional[int] = None
    ) -> bool:
        """Update webhook subscription"""
        try:
            updates = []
            params = []

            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if url is not None:
                updates.append("url = ?")
                params.append(url)
            if secret is not None:
                updates.append("secret = ?")
                params.append(secret)
            if events is not None:
                updates.append("events_json = ?")
                params.append(json.dumps(events))
            if is_active is not None:
                updates.append("is_active = ?")
                params.append(1 if is_active else 0)
            if retry_count is not None:
                updates.append("retry_count = ?")
                params.append(retry_count)
            if timeout_seconds is not None:
                updates.append("timeout_seconds = ?")
                params.append(timeout_seconds)

            if not updates:
                return False

            updates.append("updated_at = ?")
            params.append(datetime.utcnow())
            params.append(webhook_id)

            with transaction() as conn:
                conn.execute(f'''
                    UPDATE webhook_subscriptions
                    SET {", ".join(updates)}
                    WHERE id = ?
                ''', params)

            logger.info(f"Updated webhook {webhook_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating webhook: {e}")
            return False

    def delete_webhook(self, webhook_id: int) -> bool:
        """Delete webhook subscription"""
        try:
            with transaction() as conn:
                conn.execute('''
                    DELETE FROM webhook_subscriptions
                    WHERE id = ?
                ''', (webhook_id,))

            logger.info(f"Deleted webhook {webhook_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting webhook: {e}")
            return False

    def get_webhook(self, webhook_id: int) -> Optional[WebhookSubscription]:
        """Get webhook by ID"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT id, name, url, secret, events_json, is_active,
                           retry_count, timeout_seconds, created_by,
                           created_at, updated_at
                    FROM webhook_subscriptions
                    WHERE id = ?
                ''', (webhook_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                return WebhookSubscription(
                    id=row[0],
                    name=row[1],
                    url=row[2],
                    secret=row[3],
                    events=json.loads(row[4]),
                    is_active=bool(row[5]),
                    retry_count=row[6],
                    timeout_seconds=row[7],
                    created_by=row[8],
                    created_at=datetime.fromisoformat(row[9]) if row[9] else datetime.utcnow(),
                    updated_at=datetime.fromisoformat(row[10]) if row[10] else None
                )

        except Exception as e:
            logger.error(f"Error fetching webhook: {e}")
            return None

    def list_webhooks(self, active_only: bool = False) -> List[WebhookSubscription]:
        """List all webhook subscriptions"""
        try:
            with get_connection() as conn:
                query = '''
                    SELECT id, name, url, secret, events_json, is_active,
                           retry_count, timeout_seconds, created_by,
                           created_at, updated_at
                    FROM webhook_subscriptions
                '''

                if active_only:
                    query += ' WHERE is_active = 1'

                query += ' ORDER BY created_at DESC'

                cursor = conn.execute(query)
                webhooks = []

                for row in cursor.fetchall():
                    webhooks.append(WebhookSubscription(
                        id=row[0],
                        name=row[1],
                        url=row[2],
                        secret=row[3],
                        events=json.loads(row[4]),
                        is_active=bool(row[5]),
                        retry_count=row[6],
                        timeout_seconds=row[7],
                        created_by=row[8],
                        created_at=datetime.fromisoformat(row[9]) if row[9] else datetime.utcnow(),
                        updated_at=datetime.fromisoformat(row[10]) if row[10] else None
                    ))

                return webhooks

        except Exception as e:
            logger.error(f"Error listing webhooks: {e}")
            return []

    def dispatch_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatch event to all subscribed webhooks

        Args:
            event_type: Type of event (e.g., 'student.enrolled')
            payload: Event data

        Returns:
            Dictionary with dispatch results
        """
        # Find all active webhooks subscribed to this event
        webhooks = self._get_webhooks_for_event(event_type)

        if not webhooks:
            logger.debug(f"No webhooks subscribed to event {event_type}")
            return {
                'event_type': event_type,
                'dispatched': 0,
                'success': 0,
                'failed': 0
            }

        success_count = 0
        failed_count = 0
        results = []

        for webhook in webhooks:
            result = self._deliver_webhook(webhook, event_type, payload)
            results.append(result)

            if result['status'] == 'success':
                success_count += 1
            else:
                failed_count += 1

        return {
            'event_type': event_type,
            'dispatched': len(webhooks),
            'success': success_count,
            'failed': failed_count,
            'results': results
        }

    def _get_webhooks_for_event(self, event_type: str) -> List[WebhookSubscription]:
        """Get all active webhooks subscribed to an event"""
        webhooks = self.list_webhooks(active_only=True)
        return [w for w in webhooks if event_type in w.events or '*' in w.events]

    def _deliver_webhook(
        self,
        webhook: WebhookSubscription,
        event_type: str,
        payload: Dict[str, Any],
        attempt_number: int = 1
    ) -> Dict[str, Any]:
        """
        Deliver webhook to a single endpoint

        Args:
            webhook: Webhook subscription
            event_type: Event type
            payload: Event data
            attempt_number: Attempt number for retries

        Returns:
            Delivery result dictionary
        """
        # Build webhook payload
        webhook_payload = {
            'event': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            'data': payload
        }

        payload_json = json.dumps(webhook_payload)

        # Generate signature
        signature = self._sign_payload(payload_json, webhook.secret)

        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Signature': signature,
            'X-Webhook-Event': event_type,
            'X-Webhook-Delivery-ID': str(int(time.time() * 1000)),
            'User-Agent': 'UniversitySystem-Webhook/1.0'
        }

        try:
            # Send webhook
            response = requests.post(
                webhook.url,
                data=payload_json,
                headers=headers,
                timeout=webhook.timeout_seconds
            )

            # Log successful delivery
            self._log_delivery(
                webhook.id,
                event_type,
                webhook_payload,
                response.status_code,
                response.text[:1000],  # Limit response body
                None,
                attempt_number,
                delivered=True
            )

            logger.info(
                f"Webhook delivered to {webhook.name}: "
                f"{event_type} (status: {response.status_code})"
            )

            return {
                'webhook_id': webhook.id,
                'webhook_name': webhook.name,
                'status': 'success',
                'status_code': response.status_code,
                'attempt': attempt_number
            }

        except requests.exceptions.Timeout as e:
            error_msg = f"Webhook timeout: {str(e)}"
            logger.error(f"Webhook timeout for {webhook.name}: {e}")

            # Schedule retry if attempts remain
            self._handle_failed_delivery(
                webhook,
                event_type,
                webhook_payload,
                None,
                error_msg,
                attempt_number
            )

            return {
                'webhook_id': webhook.id,
                'webhook_name': webhook.name,
                'status': 'failed',
                'error': error_msg,
                'attempt': attempt_number,
                'will_retry': attempt_number < webhook.retry_count
            }

        except Exception as e:
            error_msg = f"Webhook error: {str(e)}"
            logger.error(f"Webhook error for {webhook.name}: {e}")

            # Schedule retry if attempts remain
            self._handle_failed_delivery(
                webhook,
                event_type,
                webhook_payload,
                None,
                error_msg,
                attempt_number
            )

            return {
                'webhook_id': webhook.id,
                'webhook_name': webhook.name,
                'status': 'failed',
                'error': error_msg,
                'attempt': attempt_number,
                'will_retry': attempt_number < webhook.retry_count
            }

    def _sign_payload(self, payload: str, secret: str) -> str:
        """Generate HMAC signature for webhook payload"""
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _log_delivery(
        self,
        webhook_id: int,
        event_type: str,
        payload: Dict[str, Any],
        status_code: Optional[int],
        response_body: str,
        error_message: Optional[str],
        attempt_number: int,
        delivered: bool = False
    ) -> Optional[int]:
        """Log webhook delivery attempt"""
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO webhook_deliveries (
                        webhook_id, event_type, payload_json, status_code,
                        response_body, error_message, attempt_number,
                        delivered_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    webhook_id,
                    event_type,
                    json.dumps(payload),
                    status_code,
                    response_body,
                    error_message,
                    attempt_number,
                    datetime.utcnow() if delivered else None
                ))

                return cursor.lastrowid

        except Exception as e:
            logger.error(f"Error logging webhook delivery: {e}")
            return None

    def _handle_failed_delivery(
        self,
        webhook: WebhookSubscription,
        event_type: str,
        payload: Dict[str, Any],
        status_code: Optional[int],
        error_message: str,
        attempt_number: int
    ):
        """Handle failed webhook delivery and schedule retry if needed"""
        # Log the failure
        delivery_id = self._log_delivery(
            webhook.id,
            event_type,
            payload,
            status_code,
            '',
            error_message,
            attempt_number,
            delivered=False
        )

        # Schedule retry if attempts remain
        if attempt_number < webhook.retry_count and delivery_id:
            # Exponential backoff: 1min, 5min, 30min
            retry_delays = [60, 300, 1800]
            delay_seconds = retry_delays[min(attempt_number - 1, len(retry_delays) - 1)]
            next_retry = datetime.utcnow() + timedelta(seconds=delay_seconds)

            try:
                with transaction() as conn:
                    conn.execute('''
                        UPDATE webhook_deliveries
                        SET next_retry_at = ?
                        WHERE id = ?
                    ''', (next_retry, delivery_id))

                logger.info(
                    f"Scheduled retry for webhook {webhook.name} "
                    f"(attempt {attempt_number + 1}/{webhook.retry_count}) at {next_retry}"
                )

            except Exception as e:
                logger.error(f"Error scheduling webhook retry: {e}")

    def process_retries(self, max_retries: int = 10) -> int:
        """
        Process pending webhook retries

        Args:
            max_retries: Maximum number of retries to process

        Returns:
            Number of retries processed
        """
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT id, webhook_id, event_type, payload_json, attempt_number
                    FROM webhook_deliveries
                    WHERE next_retry_at IS NOT NULL
                      AND next_retry_at <= ?
                    ORDER BY next_retry_at
                    LIMIT ?
                ''', (datetime.utcnow(), max_retries))

                retries = cursor.fetchall()

            processed = 0
            for delivery_id, webhook_id, event_type, payload_json, attempt_number in retries:
                webhook = self.get_webhook(webhook_id)
                if not webhook or not webhook.is_active:
                    # Clear retry flag for inactive webhooks
                    with transaction() as conn:
                        conn.execute('''
                            UPDATE webhook_deliveries
                            SET next_retry_at = NULL
                            WHERE id = ?
                        ''', (delivery_id,))
                    continue

                # Attempt delivery
                payload = json.loads(payload_json)
                self._deliver_webhook(webhook, event_type, payload['data'], attempt_number + 1)

                # Clear retry flag
                with transaction() as conn:
                    conn.execute('''
                        UPDATE webhook_deliveries
                        SET next_retry_at = NULL
                        WHERE id = ?
                    ''', (delivery_id,))

                processed += 1

            return processed

        except Exception as e:
            logger.error(f"Error processing webhook retries: {e}")
            return 0


# Singleton instance
_webhook_dispatcher: Optional[WebhookDispatcher] = None


def get_webhook_dispatcher() -> WebhookDispatcher:
    """Get or create webhook dispatcher singleton"""
    global _webhook_dispatcher
    if _webhook_dispatcher is None:
        _webhook_dispatcher = WebhookDispatcher()
    return _webhook_dispatcher
