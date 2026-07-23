"""Notifications Hub module.

The Hub is now an **unread inbox** built on the shared unified-inbox panel
(University ``messages`` + cross-system messages). The legacy
``notifications`` table, its ``NotificationsService`` and the standalone
CLI have been retired; only the GUI window remains.
"""

from education_system.post_18.university_system.modules.domain.operations.communications.notifications.gui.notifications_gui import (
    NotificationsGUI,
    launch_notifications_gui,
)

__all__ = ["NotificationsGUI", "launch_notifications_gui"]
