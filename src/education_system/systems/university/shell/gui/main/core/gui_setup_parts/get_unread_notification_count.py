"""Extracted function implementation."""
import logging

logger = logging.getLogger(__name__)

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _get_unread_notification_count(self):
    """Best-effort live unread count for the logged-in user's inbox — the
    sum of unread University ``messages`` and unread cross-system messages.
    Returns 0 on any failure — the bell must never break the shell."""
    cu = getattr(self.auth, 'current_user', None) if getattr(self, 'auth', None) else None
    if not isinstance(cu, dict):
        return 0

    total = 0

    # University inbox: messages addressed to this user's legacy users.id.
    uni_id = cu.get('id')
    if uni_id is not None:
        try:
            from education_system.systems.university.infrastructure.database.db import (
                get_connection,
            )
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM messages "
                    "WHERE recipient_id = ? "
                    "AND (is_read IS NULL OR is_read = 0) "
                    "AND (is_archived IS NULL OR is_archived = 0) "
                    "AND (is_deleted_by_recipient IS NULL OR is_deleted_by_recipient = 0)",
                    (uni_id,),
                ).fetchone()
                if row:
                    total += int(row[0])
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    # Cross-system inbox: keyed by the shared auth.db id.
    cross_id = cu.get('shared_auth_id') or cu.get('user_id') or cu.get('id')
    if cross_id is not None:
        try:
            from education_system.platform.features.messaging.messaging_service import (
                InterSystemMessagingService,
            )
            total += int(InterSystemMessagingService().get_unread_count(cross_id, "university"))
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    return total
