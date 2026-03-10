"""Notification preferences mixin for CommunicationDashboard."""

from __future__ import annotations

from education_system.university_system.infrastructure.email.admin._imports import (
    execute_db_operation,
    log_event,
)


class _PreferencesMixin:
    """Mixin providing notification preference management."""

    def get_notification_preferences(self):
        """Get notification preferences for the current user"""
        if not self.auth or not self.auth.current_user:
            return None

        def _get_prefs(cursor):
            cursor.execute('''
            SELECT email_notifications, message_notifications, announcement_notifications,
                   chat_notifications, daily_digest
            FROM notification_preferences
            WHERE user_id = ?
            ''', (self.auth.current_user['id'],))

            result = cursor.fetchone()

            if result:
                return {
                    'email_notifications': bool(result[0]),
                    'message_notifications': bool(result[1]),
                    'announcement_notifications': bool(result[2]),
                    'chat_notifications': bool(result[3]),
                    'daily_digest': bool(result[4])
                }
            else:
                # Create default preferences
                default_prefs = {
                    'email_notifications': True,
                    'message_notifications': True,
                    'announcement_notifications': True,
                    'chat_notifications': True,
                    'daily_digest': False
                }

                cursor.execute('''
                INSERT INTO notification_preferences
                (user_id, email_notifications, message_notifications, announcement_notifications,
                 chat_notifications, daily_digest)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    self.auth.current_user['id'],
                    default_prefs['email_notifications'],
                    default_prefs['message_notifications'],
                    default_prefs['announcement_notifications'],
                    default_prefs['chat_notifications'],
                    default_prefs['daily_digest']
                ))

                return default_prefs

        try:
            return execute_db_operation(_get_prefs)
        except Exception as e:
            log_event('error', f"Error getting notification preferences: {e}")
            return None

    def update_notification_preferences(self, preferences):
        """Update notification preferences for the current user"""
        if not self.auth or not self.auth.current_user:
            return False

        def _update_prefs(cursor):
            cursor.execute('''
            INSERT OR REPLACE INTO notification_preferences
            (user_id, email_notifications, message_notifications, announcement_notifications,
             chat_notifications, daily_digest)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                self.auth.current_user['id'],
                preferences['email_notifications'],
                preferences['message_notifications'],
                preferences['announcement_notifications'],
                preferences['chat_notifications'],
                preferences['daily_digest']
            ))

            # Log the action (pass cursor to avoid nested transactions)
            self._log_communication_action(
                self.auth.current_user['id'],
                "update_preferences",
                "Updated notification preferences",
                cursor=cursor
            )
            return True

        try:
            return execute_db_operation(_update_prefs)
        except Exception as e:
            log_event('error', f"Error updating notification preferences: {e}")
            return False
