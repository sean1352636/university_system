"""Notification preferences mixin for CommunicationDashboard.

Storage layout: the `user_preferences` table holds one row per user with
- typed columns for top-level toggles (email_notifications, in_app_notifications, ...)
- a `preferences_json` TEXT column for the per-message-type toggles
  (message/announcement/chat notifications, daily_digest, etc.) since those
  weren't given dedicated columns at schema-design time.

The previous implementation read/wrote columns
(`message_notifications`, `announcement_notifications`, ...) on a different
table (`notification_preferences`) — none of those columns exist there, so
both reads and writes raised "no such column" errors. This rewrite uses the
table and columns that actually exist.
"""

from __future__ import annotations

import json

from education_system.post_18.university_system.infrastructure.email.admin._imports import (
    execute_db_operation,
    log_event,
)


_DEFAULT_PREFS = {
    'email_notifications': True,
    'message_notifications': True,
    'announcement_notifications': True,
    'chat_notifications': True,
    'daily_digest': False,
}

# Keys that live in the typed columns rather than inside preferences_json.
_TYPED_COLUMNS = {'email_notifications'}


class _PreferencesMixin:
    """Mixin providing notification preference management."""

    def _current_user_id(self):
        if not self.auth or not self.auth.current_user:
            return None
        return str(self.auth.current_user.get('id') or self.auth.current_user.get('user_id'))

    def get_notification_preferences(self):
        """Return the current user's notification preferences dict.

        Falls back to defaults when no row exists for the user. Never raises.
        """
        user_id = self._current_user_id()
        if user_id is None:
            return None

        def _get_prefs(cursor):
            cursor.execute(
                "SELECT email_notifications, preferences_json "
                "FROM user_preferences WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return dict(_DEFAULT_PREFS)
            email_flag, prefs_json = row[0], row[1]
            prefs = dict(_DEFAULT_PREFS)
            if prefs_json:
                try:
                    blob = json.loads(prefs_json)
                    if isinstance(blob, dict):
                        prefs.update(blob)
                except (ValueError, TypeError):
                    # Corrupt JSON — keep defaults but log it for debugging
                    log_event('warning',
                              f"user_preferences.preferences_json for {user_id} is not valid JSON; using defaults")
            # Typed column wins over JSON for the keys it owns
            if email_flag is not None:
                prefs['email_notifications'] = bool(email_flag)
            return prefs

        try:
            return execute_db_operation(_get_prefs)
        except Exception as e:
            log_event('error', f"Error getting notification preferences: {e}")
            return None

    def update_notification_preferences(self, preferences):
        """Persist the given preferences dict for the current user.

        Writes the typed flags to their dedicated columns and the rest into
        `preferences_json`. Returns True on success, False on auth/DB error.
        """
        user_id = self._current_user_id()
        if user_id is None:
            return False

        # Merge with defaults so partial dicts don't drop existing keys.
        merged = dict(_DEFAULT_PREFS)
        merged.update({k: bool(v) for k, v in preferences.items() if k in _DEFAULT_PREFS})

        # Split typed vs JSON
        email_flag = 1 if merged.get('email_notifications', True) else 0
        json_blob = {k: v for k, v in merged.items() if k not in _TYPED_COLUMNS}
        prefs_json = json.dumps(json_blob)

        def _update_prefs(cursor):
            cursor.execute(
                "INSERT INTO user_preferences (user_id, email_notifications, preferences_json) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "  email_notifications = excluded.email_notifications, "
                "  preferences_json    = excluded.preferences_json",
                (user_id, email_flag, prefs_json),
            )
            self._log_communication_action(
                user_id,
                "update_preferences",
                "Updated notification preferences",
                cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_update_prefs)
        except Exception as e:
            log_event('error', f"Error updating notification preferences: {e}")
            return False
