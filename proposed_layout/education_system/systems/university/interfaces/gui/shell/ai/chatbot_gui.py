import tkinter as tk
from tkinter import messagebox
import logging

from education_system.systems.university.infrastructure.ai.university_chatbot import LIBRARIES_AVAILABLE
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.infrastructure.activity_logger import log_activity

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"

# Import all mixins
from education_system.systems.university.interfaces.gui.shell.ai.styles import StylesMixin
from education_system.systems.university.interfaces.gui.shell.ai.context import ContextMixin
from education_system.systems.university.interfaces.gui.shell.ai.events import EventsMixin
from education_system.systems.university.interfaces.gui.shell.ai.status_bar import StatusBarMixin
from education_system.systems.university.interfaces.gui.shell.ai.menu import MenuMixin
from education_system.systems.university.interfaces.gui.shell.ai.screens.chat import ChatScreenMixin
from education_system.systems.university.interfaces.gui.shell.ai.screens.settings import SettingsScreenMixin
from education_system.systems.university.interfaces.gui.shell.ai.screens.admin import AdminPanelMixin
from education_system.systems.university.interfaces.gui.shell.ai.features.messaging import MessagingMixin
from education_system.systems.university.interfaces.gui.shell.ai.features.dashboard import DashboardMixin
from education_system.systems.university.interfaces.gui.shell.ai.features.voice import VoiceMixin
from education_system.systems.university.interfaces.gui.shell.ai.features.search import SearchMixin
from education_system.systems.university.interfaces.gui.shell.ai.features.notifications import NotificationsMixin
from education_system.systems.university.interfaces.gui.shell.ai.features.session import SessionMixin
from education_system.systems.university.interfaces.gui.shell.ai.features.export import ExportMixin
from education_system.systems.university.interfaces.gui.shell.ai.features.booking import BookingMixin

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
    BookingMixin,
):
    """Modern GUI interface for the University Chatbot"""

    def __init__(self, chatbot_instance, parent_window=None, auth_system=None):
        if not LIBRARIES_AVAILABLE['tkinter']:
            raise ImportError("tkinter not available - cannot create GUI")

        self.chatbot = chatbot_instance
        self.current_user = None
        self.session_id = None
        self.conversation_active = False

        # Prefer the auth instance the caller passed in (they've already
        # authenticated through the main GUI); fall back to the central
        # get_auth() so callers that don't wire one through still work.
        self.auth_system = auth_system
        if self.auth_system is None or not getattr(
                self.auth_system, 'current_user', None):
            try:
                central = get_auth()
            except Exception:
                central = None
            if central is not None and getattr(central, 'current_user', None):
                self.auth_system = central
            elif self.auth_system is None:
                self.auth_system = central

        # Check authentication BEFORE creating GUI
        if not self.auth_system or not getattr(
                self.auth_system, 'current_user', None):
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
            self.root.geometry("1400x900+%d+%d" % ((self.root.winfo_screenwidth() - 1400) // 2, (self.root.winfo_screenheight() - 900) // 2))
            self.root.minsize(1200, 800)

        # Default all popups (messagebox / filedialog) to this window so they
        # don't fall back to the main-GUI root — that fallback raises the main
        # window and hides the chatbot behind it. Restored on close.
        self._install_dialog_parenting()

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

    def _install_dialog_parenting(self):
        """Make every messagebox / filedialog default its ``parent`` to this
        chatbot window.

        The dialog helpers in ``tkinter.messagebox`` / ``tkinter.filedialog``
        fall back to the process default root (the main GUI) when no ``parent``
        is given. That fallback pops the dialog over the main window and raises
        it, hiding this chatbot Toplevel. We wrap the helpers so an unparented
        call is anchored to ``self.root`` instead. Wrappers are removed again in
        :meth:`_restore_dialog_parenting` when the window closes.
        """
        import tkinter.messagebox as _mb
        import tkinter.filedialog as _fd

        self._patched_dialogs = []

        def _wrap(module, name):
            original = getattr(module, name, None)
            if original is None:
                return

            def wrapper(*args, **kwargs):
                if "parent" not in kwargs:
                    try:
                        if self.root and self.root.winfo_exists():
                            kwargs["parent"] = self.root
                    except Exception:
                        pass
                return original(*args, **kwargs)

            setattr(module, name, wrapper)
            self._patched_dialogs.append((module, name, original))

        for _name in ("showinfo", "showwarning", "showerror", "askyesno",
                      "askokcancel", "askquestion", "askyesnocancel",
                      "askretrycancel"):
            _wrap(_mb, _name)
        for _name in ("asksaveasfilename", "askopenfilename", "askdirectory",
                      "asksaveasfile", "askopenfile", "askopenfilenames"):
            _wrap(_fd, _name)

    def _restore_dialog_parenting(self):
        """Undo :meth:`_install_dialog_parenting` (called on window close)."""
        for module, name, original in getattr(self, "_patched_dialogs", []):
            try:
                setattr(module, name, original)
            except Exception:
                pass
        self._patched_dialogs = []

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
