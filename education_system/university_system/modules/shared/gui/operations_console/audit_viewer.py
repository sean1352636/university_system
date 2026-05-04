"""Audit Viewer adapter — embeds AuditLogViewerGUI directly in the
operations console notebook tab.

As of 8.117.80, AuditLogViewerGUI inherits from ``ttk.Frame`` (with a
standalone factory that wraps it in a Toplevel). It can be packed into
any container, so embedding is a one-liner.
"""

import logging
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)


def build_audit_viewer_panel(parent, root_window=None, admin_user_id=None):
    container = ttk.Frame(parent)
    container.pack(fill=tk.BOTH, expand=True)

    try:
        from education_system.university_system.modules.shared.gui.security.audit_log_viewer_gui import (
            AuditLogViewerGUI,
        )
    except Exception as e:
        ttk.Label(container,
                  text=f"Audit Viewer unavailable: {e}",
                  foreground="#c62828").pack(padx=20, pady=20)
        return {'frame': container, 'stop': lambda: None}

    viewer = AuditLogViewerGUI(container, admin_user_id=admin_user_id,
                               embedded=True)
    viewer.pack(fill=tk.BOTH, expand=True)

    def _stop():
        try:
            viewer._stop_auto_refresh()
        except Exception:
            pass

    return {'frame': container, 'stop': _stop, 'viewer': viewer}
