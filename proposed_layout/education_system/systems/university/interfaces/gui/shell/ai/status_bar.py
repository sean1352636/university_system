import tkinter as tk
from tkinter import ttk

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"


class StatusBarMixin:
    """Mixin for status bar and screen visibility management."""

    def create_status_bar(self):
        """Create status bar at bottom"""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Status label
        self.status_label = ttk.Label(self.status_bar, text=_t("chatbot.status_ready", default="Ready"))
        self.status_label.pack(side=tk.LEFT, padx=5)

        # Connection status
        self.connection_label = ttk.Label(self.status_bar, text=_t("chatbot.status_connected", default="● Connected"), foreground='green')
        self.connection_label.pack(side=tk.RIGHT, padx=5)

    def hide_all_screens(self):
        """Hide all screen frames"""
        frames_to_hide = [self.chat_frame, self.settings_frame]
        if hasattr(self, 'admin_frame'):
            frames_to_hide.append(self.admin_frame)
        for frame in frames_to_hide:
            frame.pack_forget()

    def show_settings_screen(self):
        """Show the settings screen"""
        self.hide_all_screens()
        self.settings_frame.pack(fill=tk.BOTH, expand=True)
        self.conversation_active = False
