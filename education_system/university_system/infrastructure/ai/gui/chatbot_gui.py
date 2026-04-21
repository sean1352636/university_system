import tkinter as tk
from tkinter import messagebox
import logging

from education_system.university_system.infrastructure.ai.university_chatbot import LIBRARIES_AVAILABLE
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"

# Import all mixins
from education_system.university_system.infrastructure.ai.gui.styles import StylesMixin
from education_system.university_system.infrastructure.ai.gui.context import ContextMixin
from education_system.university_system.infrastructure.ai.gui.events import EventsMixin
from education_system.university_system.infrastructure.ai.gui.status_bar import StatusBarMixin
from education_system.university_system.infrastructure.ai.gui.menu import MenuMixin
from education_system.university_system.infrastructure.ai.gui.screens.chat import ChatScreenMixin
from education_system.university_system.infrastructure.ai.gui.screens.settings import SettingsScreenMixin
from education_system.university_system.infrastructure.ai.gui.screens.admin import AdminPanelMixin
from education_system.university_system.infrastructure.ai.gui.features.messaging import MessagingMixin
from education_system.university_system.infrastructure.ai.gui.features.dashboard import DashboardMixin
from education_system.university_system.infrastructure.ai.gui.features.voice import VoiceMixin
from education_system.university_system.infrastructure.ai.gui.features.search import SearchMixin
from education_system.university_system.infrastructure.ai.gui.features.notifications import NotificationsMixin
from education_system.university_system.infrastructure.ai.gui.features.session import SessionMixin
from education_system.university_system.infrastructure.ai.gui.features.export import ExportMixin

# Configure logging
logger = logging.getLogger(__name__)


class ChatbotGUI(
    StylesMixin,
    ContextMixin,
    EventsMixin,
    StatusBarMixin,
    MenuMixin,
    ChatScreenMixin,
    SettingsScreenMixin,
    AdminPanelMixin,
    MessagingMixin,
    DashboardMixin,
    VoiceMixin,
    SearchMixin,
    NotificationsMixin,
    SessionMixin,
    ExportMixin,
):
    """Modern GUI interface for the University Chatbot"""

    def __init__(self, chatbot_instance, parent_window=None, auth_system=None):
        if not LIBRARIES_AVAILABLE['tkinter']:
            raise ImportError("tkinter not available - cannot create GUI")

        self.chatbot = chatbot_instance
        self.current_user = None
        self.session_id = None
        self.conversation_active = False

        # Use central authentication system
        self.auth_system = get_auth()

        # Check authentication BEFORE creating GUI
        if not self.auth_system.current_user:
            messagebox.showerror(
                _t("chatbot.auth_required_title", default="Authentication Required"),
                _t("chatbot.auth_required_msg", default="Please log in through the main University System GUI first.\n\nRun: python run.py --gui")
            )
            raise RuntimeError("Authentication required - not logged in")

        # Initialize main window
        self._parent_window = parent_window
        if parent_window:
            self.root = parent_window
        else:
            self.root = tk.Tk()
            self.root.title(_t("chatbot.window_title", default="University Chatbot - Student Support System"))
            self.root.geometry("1000x700")
            self.root.minsize(800, 600)

        # Configure styles and themes
        self.setup_styles()

        # Create GUI components
        self.create_widgets()

        # Setup event handlers
        self.setup_event_handlers()

        # Check if user is already authenticated and use current user
        self.setup_current_user()

        # Initialize helper systems
        self.show_notification = self.create_notification_system()
        self.show_search = self.create_search_functionality()
        self.apply_theme = self.create_theme_manager()
        self.update_session_stats, self.get_session_summary = self.create_session_management()

        # Add menu bar
        self.add_menu_bar()

        # Setup keyboard shortcuts
        self.setup_keyboard_shortcuts()

        # Log activity
        log_activity('open', 'chatbot_gui', None, details={'user': self.current_user.get('username') if self.current_user else 'Unknown'})

        # Show chat screen (user is already authenticated)
        self.show_chat_screen()

    def run(self):
        """Start the GUI main loop"""
        try:
            self.root.mainloop()
        except Exception as e:
            print(f"GUI error: {e}")
            messagebox.showerror(
                _t("chatbot.application_error", default="Application Error"),
                _t("chatbot.error_occurred", default="An error occurred: {error}").format(error=str(e))
            )
