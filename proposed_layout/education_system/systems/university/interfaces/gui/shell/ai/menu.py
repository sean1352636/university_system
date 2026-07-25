import tkinter as tk
import logging
from tkinter import ttk, messagebox, scrolledtext

logger = logging.getLogger(__name__)

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"


class MenuMixin:
    """Mixin for menu bar and help dialogs."""

    def add_menu_bar(self):
        """Add menu bar to main window"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)

        export_conversations = self.create_conversation_export()
        backup_system, restore_system = self.create_backup_restore()

        file_menu.add_command(label="Export Conversations", command=export_conversations)
        file_menu.add_separator()
        file_menu.add_command(label="Backup System", command=backup_system)
        file_menu.add_command(label="Restore System", command=restore_system)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Clear Chat", command=self.clear_chat_history)
        edit_menu.add_command(label="Preferences", command=self.show_settings_screen)

        # Actions menu
        actions_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Actions", menu=actions_menu)
        actions_menu.add_command(
            label=_t("chatbot.book_room_menu", default="Book a Room…"),
            command=self.show_book_room_dialog)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Chat", command=self.show_chat_screen)
        view_menu.add_command(label="Settings", command=self.show_settings_screen)
        if self.current_user and self.current_user.get('role') in ['admin', 'staff']:
            view_menu.add_command(label="Admin Panel", command=self.show_admin_panel)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_user_guide)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)
        help_menu.add_command(label="About", command=self.show_about_dialog)

    def clear_chat_history(self):
        """Clear the chat transcript and reset the conversation context."""
        if not messagebox.askyesno(
            _t("chatbot.clear_chat_title", default="Clear Chat"),
            _t("chatbot.clear_chat_confirm", default="Are you sure you want to clear the chat history?")
        ):
            return

        # Don't clear mid-response, or the typing indicator/reply would land in
        # a freshly wiped transcript.
        if getattr(self, '_processing_message', False):
            return

        # Any in-progress typing animation must stop before we wipe the widget.
        if hasattr(self, '_hide_typing_indicator'):
            self._hide_typing_indicator()

        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state=tk.DISABLED)

        # Reset the backend conversation context so a cleared chat is a genuine
        # fresh start — this drops remembered intent history and entities (e.g.
        # a module code mentioned earlier), which would otherwise persist.
        self._reset_conversation_context()

        # Let the personalised welcome summary show again next time the chat
        # screen is opened.
        if hasattr(self, '_welcome_shown'):
            del self._welcome_shown

        self.add_chat_message(
            _t("chatbot.system", default="System"),
            _t("chatbot.chat_history_cleared", default="Chat history cleared."),
            "system",
        )

    def _reset_conversation_context(self):
        """Best-effort reset of the chatbot's server-side conversation memory."""
        user_id = None
        if getattr(self, 'current_user', None):
            user_id = self.current_user.get('username')

        try:
            contexts = getattr(self.chatbot, 'conversation_contexts', None)
            if isinstance(contexts, dict) and user_id in contexts:
                del contexts[user_id]
        except Exception as e:
            logger.debug(f"Could not reset conversation context: {e}")

    def show_user_guide(self):
        """Show user guide dialog"""
        guide_window = tk.Toplevel(self.root)
        guide_window.title(_t("chatbot.user_guide_title", default="User Guide"))
        guide_window.geometry("600x500")

        guide_text = """UNIVERSITY CHATBOT USER GUIDE

GETTING STARTED:
1. Log in with your university credentials
2. Use the main chat interface to ask questions
3. Try voice commands by clicking the Voice button

FEATURES:
• Natural language processing for intelligent responses
• Voice interaction support (speak and listen)
• Quick action buttons for common tasks
• Real-time conversation tracking
• Multi-user authentication system

COMMANDS:
• Type naturally - ask about courses, grades, registration
• Use voice commands: "start voice mode", "test voice"
• Quick actions: Click buttons for common requests
• Settings: Adjust preferences and appearance

TIPS:
• Be specific in your questions for better responses
• Use voice mode for hands-free interaction
• Check the About tab for detailed feature information
• Contact support for technical issues

KEYBOARD SHORTCUTS:
• Enter: Send message
• Ctrl+Enter: New line in message
• Esc: Clear current message
• F1: Show this help guide
"""

        guide_display = scrolledtext.ScrolledText(guide_window, wrap=tk.WORD)
        guide_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        guide_display.insert(1.0, guide_text)
        guide_display.config(state=tk.DISABLED)

    def show_shortcuts(self):
        """Show keyboard shortcuts dialog"""
        shortcuts_window = tk.Toplevel(self.root)
        shortcuts_window.title(_t("chatbot.keyboard_shortcuts_title", default="Keyboard Shortcuts"))
        shortcuts_window.geometry("400x300")

        shortcuts_text = """KEYBOARD SHORTCUTS

CHAT INTERFACE:
Enter                Send message
Ctrl+Enter           New line in message
Escape               Clear message input
Ctrl+L               Clear chat history

NAVIGATION:
F1                   Show user guide
F2                   Open settings
F3                   Toggle voice mode
F5                   Refresh

ADMIN FUNCTIONS:
Ctrl+A               Open admin panel (admin only)
Ctrl+Shift+S         System status
Ctrl+Shift+U         User management
"""

        shortcuts_display = scrolledtext.ScrolledText(shortcuts_window, wrap=tk.WORD)
        shortcuts_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        shortcuts_display.insert(1.0, shortcuts_text)
        shortcuts_display.config(state=tk.DISABLED)

    def show_about_dialog(self):
        """Show about dialog"""
        about_window = tk.Toplevel(self.root)
        about_window.title(_t("chatbot.about_title", default="About University Chatbot"))
        about_window.geometry("400x350")
        about_window.resizable(False, False)

        # Center the window
        about_window.transient(self.root)
        about_window.grab_set()

        # About content
        about_frame = ttk.Frame(about_window, padding=20)
        about_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(about_frame, text=_t("chatbot.university_chatbot", default="University Chatbot"),
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 10))

        # Version info
        version_info = """Version 2.0 Enhanced Edition
Student Support System

Developed for university student services
with advanced AI capabilities and voice support.

Features:
• Natural Language Processing
• Voice Recognition & Synthesis
• Multi-user Authentication
• Real-time Analytics
• Administrative Tools
• Cross-platform GUI Support

Technologies:
• Python 3.8+
• tkinter for GUI
• Speech Recognition
• Transformers (NLP)
• SQLite Database
• Flask Web API

Copyright © 2024 University System
All rights reserved."""

        info_label = ttk.Label(about_frame, text=version_info, justify=tk.CENTER)
        info_label.pack(pady=10)

        # Close button
        ttk.Button(about_frame, text=_t("common.close", default="Close"),
                   command=about_window.destroy).pack(pady=(20, 0))
