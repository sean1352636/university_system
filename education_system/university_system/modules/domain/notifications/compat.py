"""
Backward Compatibility Layer for Notifications

This module provides backward compatibility for legacy code that uses the old
notification_type column which no longer exists in the notifications table.

The new schema uses 'channel' and 'priority' instead of 'notification_type'.

Usage in legacy code:
    Instead of direct SQL inserts:
        cursor.execute('''
            INSERT INTO notifications (recipient_id, notification_type, title, message)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'assignment', 'Title', 'Message'))

    Use:
        from education_system.university_system.modules.domain.notifications.compat import create_notification_compat
        create_notification_compat(
            conn, recipient_id=user_id, notification_type='assignment',
            title='Title', message='Message'
        )
"""

from typing import Optional
from datetime import datetime
from education_system.university_system.modules.domain.notifications.services.notifications_service import (
    create_notification_legacy,
    map_notification_type_to_channel_priority
)


def create_notification_compat(
    conn,
    recipient_id: Optional[str] = None,
    user_id: Optional[str] = None,
    notification_type: str = 'general',
    title: str = '',
    message: str = '',
    created_date: Optional[str] = None,
    created_datetime: Optional[str] = None,
    recipient_type: Optional[str] = None,
    related_document_id: Optional[int] = None,
    student_id: Optional[str] = None,
    subject: Optional[str] = None,
    sent_date: Optional[str] = None,
    priority: Optional[str] = None,
    is_sent: Optional[int] = None,
    **kwargs
) -> int:
    """
    Compatibility wrapper for creating notifications with old-style parameters.

    This function accepts any combination of legacy parameters and maps them
    to the new notification schema.

    Args:
        conn: Database connection (for API compatibility, not used)
        recipient_id: Legacy recipient ID
        user_id: User ID
        notification_type: Old notification type (mapped to channel/priority)
        title: Notification title
        message: Notification message
        subject: Alternative to title
        created_date: Legacy creation date (ignored)
        created_datetime: Legacy creation datetime (ignored)
        recipient_type: Legacy recipient type
        related_document_id: Related document ID
        student_id: Alternative to user_id/recipient_id
        sent_date: Legacy sent date (ignored)
        priority: Override priority from notification_type mapping
        is_sent: Legacy sent flag (ignored)
        **kwargs: Additional parameters stored in metadata

    Returns:
        notification_id: Created notification ID
    """
    # Determine user_id from various legacy parameter names
    final_user_id = user_id or recipient_id or student_id
    if not final_user_id:
        raise ValueError("user_id, recipient_id, or student_id must be provided")

    # Use subject as title if title not provided
    final_title = title or subject or 'Notification'

    # Map notification_type to channel and priority if not overridden
    if not priority:
        channel, final_priority = map_notification_type_to_channel_priority(notification_type)
    else:
        # Priority was explicitly provided
        channel, _ = map_notification_type_to_channel_priority(notification_type)
        final_priority = priority

    # Call the legacy creation function
    return create_notification_legacy(
        user_id=final_user_id,
        title=final_title,
        message=message,
        notification_type=notification_type,
        recipient_id=recipient_id,
        recipient_type=recipient_type,
        related_document_id=related_document_id,
        **kwargs
    )


# Monkey-patch helper for direct SQL replacements
def patch_notification_insert(cursor, query: str, params: tuple):
    """
    Helper to intercept old-style notification INSERT statements.

    This is a transitional helper - eventually all code should use
    create_notification_compat or the NotificationsService directly.
    """
    # Check if this is an INSERT into notifications with old schema
    if 'INSERT INTO notifications' in query.upper() and 'NOTIFICATION_TYPE' in query.upper():
        # Extract parameter names from query (simplified parser)
        # This is a best-effort attempt to map old-style inserts
        print(f"Warning: Legacy notification INSERT detected. Consider updating to use create_notification_compat()")

        # Try to map parameters (this is fragile but provides compatibility)
        try:
            create_notification_compat(
                cursor.connection,
                *params  # Pass params positionally
            )
        except Exception as e:
            print(f"Failed to map legacy notification insert: {e}")
            raise

    # If not a notification insert or new schema, execute normally
    return cursor.execute(query, params)
