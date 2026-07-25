"""Notifications Hub GUI.

The Hub is now an **unread inbox**: it surfaces the logged-in user's
unread received messages, drawn from the same unified feed the email
Messages tab uses:

* University intra-system user-to-user messages (CommunicationDashboard).
* Cross-system staff messages (InterSystemMessagingService).

A Source filter (All / University / Cross-system) lets the user narrow the
feed, and the view defaults to unread-only. The legacy ``notifications``
table and its standalone management screens have been retired.
"""

import logging
import tkinter as tk

logger = logging.getLogger(__name__)


class NotificationsGUI:
    """Unread-inbox Hub window (bell button target)."""

    def __init__(self, parent=None):
        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        self.window.title("Notifications — Unread Inbox")
        self.window.geometry("1060x700")
        self.window.minsize(860, 550)

        try:
            from education_system.systems.university.infrastructure.shared_context import get_auth
            self.auth = get_auth()
        except Exception:
            self.auth = None

        self._panel = None
        self._build_ui()

    def _build_ui(self):
        from education_system.platform.features.messaging.unified_inbox import UnifiedInboxPanel

        dashboard = self._build_dashboard()
        try:
            self._panel = UnifiedInboxPanel(
                self.window,
                auth=self.auth,
                system_key="university",
                dashboard=dashboard,
                root=self.window,
                unread_only=True,
            )
            self._panel.pack(fill=tk.BOTH, expand=True)
        except Exception:
            logger.exception("Failed to build unified inbox panel")
            from tkinter import ttk
            ttk.Label(
                self.window,
                text="Inbox unavailable — please try again later.",
                padding=20,
            ).pack(fill=tk.BOTH, expand=True)

    def _build_dashboard(self):
        """Build the CommunicationDashboard that serves the university inbox.

        Best-effort: if it can't be constructed (e.g. no auth session), the
        panel still works with the cross-system stream alone.
        """
        try:
            from education_system.systems.university.infrastructure.email.admin import (
                CommunicationDashboard,
            )
            return CommunicationDashboard(auth=self.auth)
        except Exception:
            logger.warning("CommunicationDashboard unavailable for Notifications Hub", exc_info=True)
            return None

    def refresh(self):
        if self._panel is not None:
            self._panel.refresh()


def launch_notifications_gui(parent=None):
    """Convenience launcher matching the pattern used by other domain GUIs."""
    return NotificationsGUI(parent=parent)
