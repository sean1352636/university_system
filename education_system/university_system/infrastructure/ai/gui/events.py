import tkinter as tk
import logging

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.core.i18n import (
        get_text as _t,
        get_current_language,
    )
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"

logger = logging.getLogger(__name__)


class EventsMixin:
    """Mixin for event handling, keyboard shortcuts, and window lifecycle."""

    def setup_event_handlers(self):
        """Setup event handlers for the GUI"""
        # Enter key sends message in chat
        self.root.bind('<Return>', lambda e: self.send_message() if self.conversation_active else None)

        # Ctrl+Enter for new line in message entry
        self.root.bind('<Control-Return>', lambda e: self.message_entry.insert(tk.INSERT, '\n'))

        # Focus handling
        self.root.bind('<Button-1>', self.on_click)

        # Window close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for the GUI"""
        # Bind keyboard shortcuts
        self.root.bind('<F1>', lambda e: self.show_user_guide())
        self.root.bind('<F2>', lambda e: self.show_settings_screen())
        self.root.bind('<F3>', lambda e: self.toggle_voice_mode() if self.conversation_active else None)
        self.root.bind('<F5>', lambda e: self.refresh_current_view())
        self.root.bind('<Escape>', lambda e: self.clear_message_input() if self.conversation_active else None)
        self.root.bind('<Control-l>', lambda e: self.clear_chat_history() if self.conversation_active else None)

        # Admin shortcuts
        if self.current_user and self.current_user.get('role') in ['admin', 'staff']:
            self.root.bind('<Control-a>', lambda e: self.show_admin_panel())
            self.root.bind('<Control-Shift-S>', lambda e: self.show_admin_panel())
            self.root.bind('<Control-Shift-U>', lambda e: self.show_admin_panel())

    def clear_message_input(self):
        """Clear the message input field"""
        if hasattr(self, 'message_entry'):
            self.message_entry.delete("1.0", tk.END)

    def refresh_current_view(self):
        """Refresh the current view"""
        if hasattr(self, 'admin_frame') and self.admin_frame.winfo_viewable():
            self.refresh_system_status()
            self.refresh_user_list()
            self.generate_analytics_report()
            self.refresh_logs()
        elif hasattr(self, 'chat_frame') and self.chat_frame.winfo_viewable():
            self.status_label.config(text="View refreshed")

    def on_click(self, event):
        """Handle click events for focus management"""
        widget = event.widget
        if widget == self.message_entry and self.conversation_active:
            # Focus on message entry when clicking in chat area
            self.message_entry.focus()

    def on_closing(self):
        """Handle window closing"""
        # Use the exit handler which properly cleans up without logging out
        self.handle_exit()

    def handle_exit(self):
        """Handle exit to main GUI"""
        try:
            # Cleanup voice interface if enabled
            if hasattr(self.chatbot, 'voice_interface') and self.chatbot.voice_interface.enabled:
                self.chatbot.voice_interface.cleanup()

            # Close the chatbot window (returns to main GUI)
            if hasattr(self.root, 'destroy'):
                self.root.destroy()

            print("✓ Chatbot GUI closed - returning to main system")

        except Exception as e:
            print(f"Warning: Error during exit: {e}")
            # Force close if normal close fails
            try:
                self.root.quit()
            except Exception as e:
                logger.debug(f"Error closing window: {e}")
