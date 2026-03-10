"""Webhook Manager"""

from ._imports import get_connection


class WebhookManager:
    """Manages integration webhooks"""

    @staticmethod
    def register_webhook(install_id: int, webhook_url: str, event_type: str,
                        secret_key: str = "") -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO integration_webhooks (
                    install_id, webhook_url, event_type, secret_key
                ) VALUES (?, ?, ?, ?)
            ''', (install_id, webhook_url, event_type, secret_key))
            webhook_id = cursor.lastrowid
            conn.commit()
            return webhook_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error registering webhook: {e}")
        finally:
            conn.close()
