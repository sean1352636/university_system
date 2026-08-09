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
        self.status_bar = ttk.Frame(self.root, style='CB.TFrame')
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Status label
        self.status_label = ttk.Label(self.status_bar, text=_t("chatbot.status_ready", default="Ready"), style='CB.TLabel')
        self.status_label.pack(side=tk.LEFT, padx=5)

        # Connection status
        self.connection_label = ttk.Label(self.status_bar, text="", style='CB.TLabel')
        self.connection_label.pack(side=tk.RIGHT, padx=5)
        self._backend_state = 'reconnecting'
        self.refresh_service_status()

    def set_activity_status(self, state):
        """Set a truthful, translated activity state."""
        labels = {
            'ready': _t('chatbot.status_ready', default='Ready'),
            'processing': _t('chatbot.status_processing', default='Processing'),
            'listening': _t('chatbot.status_listening', default='Listening'),
            'failed': _t('chatbot.status_failed', default='Request failed'),
            'stopped': _t('chatbot.status_stopped', default='Generation stopped'),
        }
        self.status_label.configure(text=labels.get(state, str(state)))

    def set_backend_status(self, state):
        self._backend_state = state
        labels = {
            'online': _t('chatbot.backend_online', default='Assistant: Online'),
            'offline': _t('chatbot.backend_offline', default='Assistant: Offline'),
            'reconnecting': _t('chatbot.backend_reconnecting', default='Assistant: Reconnecting'),
        }
        voice = getattr(getattr(self, 'chatbot', None), 'voice_interface', None)
        voice_text = (_t('chatbot.voice_available', default='Voice: Available')
                      if voice is not None and getattr(voice, 'enabled', False)
                      else _t('chatbot.voice_unavailable_status', default='Voice: Unavailable'))
        self.connection_label.configure(text=f"{labels.get(state, state)} | {voice_text}")

    def refresh_service_status(self):
        """Check the local assistant interface instead of showing a static state."""
        try:
            processor = getattr(self.chatbot, 'process_message', None)
            if not callable(processor):
                raise RuntimeError('message processor unavailable')
            health = getattr(self.chatbot, 'get_system_status', None)
            if callable(health):
                health()
            self.set_backend_status('online')
            if hasattr(self, 'retry_offline_queue'):
                self.retry_offline_queue()
        except Exception:
            self.set_backend_status('offline')
        try:
            self._status_after_id = self.root.after(10000, self.refresh_service_status)
        except Exception:
            self._status_after_id = None

    def schedule_reconnect_check(self):
        self.set_backend_status('reconnecting')
        try:
            self.root.after(1500, self.refresh_service_status)
        except Exception:
            pass

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
