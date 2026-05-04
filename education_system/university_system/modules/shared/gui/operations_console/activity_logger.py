"""Activity Logger adapter — embeds EnhancedActivityLoggerGUI.

The class accepts ``parent`` and falls into a non-standalone branch
that skips title/geometry calls, so a ttk.Frame works as parent.
"""

import tkinter as tk
from tkinter import ttk


def build_activity_logger_panel(parent, auth=None):
    container = ttk.Frame(parent)
    container.pack(fill=tk.BOTH, expand=True)

    try:
        from education_system.university_system.modules.shared.gui.simple_activity_logger_gui.main_gui import (
            EnhancedActivityLoggerGUI,
        )
    except Exception as e:
        ttk.Label(container,
                  text=f"Activity Logger unavailable: {e}",
                  foreground="#c62828").pack(padx=20, pady=20)
        return {'frame': container, 'stop': lambda: None}

    gui = EnhancedActivityLoggerGUI(auth=auth, parent=container)

    def _stop():
        try:
            if hasattr(gui, 'on_closing'):
                gui.on_closing()
        except Exception:
            pass

    return {'frame': container, 'stop': _stop, 'gui': gui}
