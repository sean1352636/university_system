"""Activity Log adapter — embeds LogManagementGUI in embedded mode."""

import tkinter as tk
from tkinter import ttk


def build_activity_log_panel(parent, auth=None):
    container = ttk.Frame(parent)
    container.pack(fill=tk.BOTH, expand=True)

    try:
        from education_system.university_system.infrastructure.logging.gui.log_management_gui import (
            LogManagementGUI,
        )
    except Exception as e:
        ttk.Label(container,
                  text=f"Activity Log unavailable: {e}",
                  foreground="#c62828").pack(padx=20, pady=20)
        return {'frame': container, 'stop': lambda: None}

    LogManagementGUI(container, auth=auth, embedded=True)
    return {'frame': container, 'stop': lambda: None}
