
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

from ._dialogs import make_toplevel, messagebox, filedialog
from . import common as _common
import tkinter.font as tkFont
from datetime import datetime, timedelta
import json
import os
import threading
import webbrowser
from typing import Dict, List, Optional, Any
from education_system.systems.university.infrastructure.database.db import sqlite3
from pathlib import Path
import logging
from education_system import paths

# Import i18n for language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import activity logger for audit trail
try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import email service for notifications
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email
    from education_system.systems.university.infrastructure.email.templates import load_template, render_template
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    send_email = lambda *args, **kwargs: False
    load_template = lambda *args, **kwargs: None
    render_template = lambda *args, **kwargs: (None, None)

# Use centralized path configuration
DEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH


# Import all functionality from student_support module (it's a single monolithic file)
try:
    # Import everything from the single student_support module
    from education_system.systems.university.domains.student_support.domain.student_support import (
        # Core constants and enums
        SUPPORT_CATEGORIES, TICKET_PRIORITIES, TICKET_STATUSES,
        NotificationType, TicketSentiment, FileType,
        # Main classes
        EnhancedStudentSupport, SupportConfig,
        # Utility functions
        setup_enhanced_logging, audit_action, set_auth,
        # Display functions
        display_support_menu, display_enhanced_faqs, display_enhanced_resources,
        # Ticket management functions
        view_my_tickets_enhanced, view_all_tickets_enhanced,
        create_enhanced_ticket, display_ticket_details_enhanced,
        # Admin functions
        manage_templates_menu, manage_knowledge_base_menu, show_template_statistics,
        # Helper functions
        format_ticket_status_display, format_priority_display, format_file_size,
        truncate_text, handle_support_error, validate_ticket_permissions
    )

    # Auth handling - auth is now managed differently in the new structure
    auth = None  # Will be set via set_auth_instance()

except ImportError:
    # Backwards compatibility - if module structure changes or imports fail
    try:
        from education_system.systems.university.domains.student_support.domain.student_support import (
            SUPPORT_CATEGORIES, TICKET_PRIORITIES, TICKET_STATUSES,
            EnhancedStudentSupport, SupportConfig, display_support_menu, set_auth
        )
        auth = None
    except ImportError:
        # If even the fallback import fails, define minimal stubs
        auth = None
        SUPPORT_CATEGORIES = []
        TICKET_PRIORITIES = []
        TICKET_STATUSES = []
        EnhancedStudentSupport = None
        SupportConfig = None
        display_support_menu = None

    # Define fallback functions if not available
    display_enhanced_faqs = None
    display_enhanced_resources = None
    view_my_tickets_enhanced = None
    view_all_tickets_enhanced = None
    create_enhanced_ticket = None
    display_ticket_details_enhanced = None
    manage_templates_menu = None
    manage_knowledge_base_menu = None
    show_template_statistics = None

    # Define fallback enum types
    from enum import Enum
    class NotificationType(str, Enum):
        INFO = 'info'
        WARNING = 'warning'
        ERROR = 'error'

    class TicketSentiment(str, Enum):
        POSITIVE = 'positive'
        NEUTRAL = 'neutral'
        NEGATIVE = 'negative'

    class FileType(str, Enum):
        IMAGE = 'image'
        DOCUMENT = 'document'
        OTHER = 'other'

    # Define fallback helper functions
    setup_enhanced_logging = lambda: None
    audit_action = lambda *args, **kwargs: None
    set_auth = lambda x: None  # Fallback if set_auth not available
    validate_ticket_permissions = lambda *args, **kwargs: True
    format_ticket_status_display = lambda x: str(x)
    format_priority_display = lambda x: str(x)
    format_file_size = lambda x: f"{x} bytes"
    truncate_text = lambda x, length=100: x[:length] if len(x) > length else x
    handle_support_error = lambda *args, **kwargs: None


class StudentSupportGUIBase:
    def __init__(self, root, auth_system=None):
        # Initialize i18n for language support
        init_i18n()

        self.root = root
        self.root.title(_t("student_support.title"))
        # The house window size; window_sizing.install() clamps it to the screen.
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        # The signed-in session: the one passed in, else the shared context's.
        self.auth = auth_system
        if not self.auth:
            from education_system.systems.university.infrastructure.shared_context import get_auth
            self.auth = get_auth()

        # Initialize support system
        self.config = None
        try:
            if SupportConfig is None or EnhancedStudentSupport is None:
                raise RuntimeError("Enhanced support components are unavailable")

            self.config = SupportConfig()
            self.support = EnhancedStudentSupport(self.config)
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.student_support.base.dialogs.initialization_error', default="Initialization Error"), f"Failed to initialize support system: {e}")
            self.support = None

        # Theme configuration
        self.setup_theme()

        # GUI state
        self.current_ticket = None
        self.search_results = {}
        self.dashboard_data = {}
        self._current_view = None

        # Initialize status_var early to prevent attribute errors
        self.status_var = None
        self._faq_last_mode = 'category'
        self._faq_last_category = None
        self._faq_last_query = None
        self._kb_last_mode = 'list'
        self._kb_last_search = ''
        self.resource_records: Dict[int, Dict[str, Any]] = {}
        self.template_records: Dict[int, Dict[str, Any]] = {}

        # A signed-in session is required (shared_context can hand back an
        # auth object with nobody signed in).
        if not _common.actor(self):
            logger.warning("Student Support opened without a signed-in user")
            messagebox.showerror(_t('gui.pastoral.student_support.base.dialogs.authentication_required', default="Authentication Required"),
                _t('gui.pastoral.student_support.base.dialogs.please_log_in_through_the_main_university_system_gui_run_python', default="Please log in through the main University System GUI.\n\n"
                "Run: python -m education_system --gui"))
            self.root.destroy()
            return

        # Older support helpers still read the module's session (the export
        # and dashboard features); the screens pass the actor explicitly.
        try:
            set_auth(self.auth)
        except Exception:
            logger.warning("Could not set auth in the support service module", exc_info=True)

        # Create main interface
        self.create_widgets()
        self.create_menu()
        self.bind_shortcuts()

        # Load dashboard
        self.load_dashboard()

    def setup_current_user(self):
        """Kept for callers: the session is checked in ``__init__``."""
        return _common.actor(self) or None

    def _get_current_user_identity(self):
        """Return (user_id, username) for the authenticated user if available."""
        if not self.auth or not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            return None, None
        current = self.auth.current_user
        user_id = current.get('id') or current.get('user_id')
        username = current.get('username')
        return user_id, username

    def get_user_role(self):
        """The signed-in user's role, lower case (None when nobody)."""
        return _common.role(self) or None

    def is_admin(self):
        """An administrator (``student_support.auth.ADMIN_ROLES``)."""
        return _common.is_admin(self)

    def is_staff(self):
        """Works support tickets (support roles, admins, the health team,
        safeguarding leads and anyone routing puts in a team) — instructors
        and other staff only raise tickets of their own."""
        return _common.is_case_worker(self)

    def is_student(self):
        """Check if current user is student"""
        return _common.role(self) == 'student'

    def bind_shortcuts(self):
        """Ctrl+N new ticket, Ctrl+F search, F5 refresh (Ctrl+W closes a
        dialog: bound on each dialog by ``make_toplevel``)."""
        self.root.bind('<Control-n>', lambda _e: self.show_create_ticket())
        self.root.bind('<Control-N>', lambda _e: self.show_create_ticket())
        self.root.bind('<Control-f>', lambda _e: self.show_search())
        self.root.bind('<Control-F>', lambda _e: self.show_search())
        self.root.bind('<F5>', lambda _e: self.refresh_data())

    def set_view(self, key):
        """Record which screen is showing (``refresh_data`` dispatches on it)."""
        self._current_view = key

    def _safe_db_call(self, operation, *args, **kwargs):
        """Run a database operation with automatic commit/rollback handling."""
        conn = None
        try:
            conn = _common.ss('store').connect()
            result = operation(conn, *args, **kwargs)
            conn.commit()
            return result
        except sqlite3.Error as exc:
            if conn:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
            logging_error = getattr(logging, "error", print)
            logging_error(f"StudentSupportGUI database error: {exc}")
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass

    def _create_scrollable_frame(self, parent, bg=None):
        """Create a scrollable frame that expands to fill available space.

        Returns:
            tuple: (canvas, scrollbar, scrollable_frame) - the canvas, scrollbar, and inner frame
        """
        if bg is None:
            bg = self.colors.get('background', '#f8fafc')

        canvas = tk.Canvas(parent, bg=bg, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        # Create window and store reference
        scroll_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        # Update scroll region when content changes
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        # Make scrollable frame fill canvas width and expand height if needed
        def on_canvas_configure(event):
            canvas.itemconfigure(scroll_window, width=event.width)
            # If content is smaller than canvas, expand to fill
            content_height = scrollable_frame.winfo_reqheight()
            if content_height < event.height:
                canvas.itemconfigure(scroll_window, height=event.height)

        canvas.bind("<Configure>", on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)

        return canvas, scrollbar, scrollable_frame

    def setup_theme(self):
        """Setup modern theme and styling"""
        style = ttk.Style()

        # Configure colors
        self.colors = {
            'primary': '#2563eb',
            'secondary': '#64748b',
            'success': '#16a34a',
            'warning': '#d97706',
            'error': '#dc2626',
            'background': '#f8fafc',
            'surface': '#ffffff',
            'text': '#1e293b',
            'text_secondary': '#64748b'
        }

        # Configure styles
        style.configure('Title.TLabel', font=('Segoe UI', 16, 'bold'), foreground=self.colors['text'])
        style.configure('Heading.TLabel', font=('Segoe UI', 12, 'bold'), foreground=self.colors['text'])
        style.configure('Card.TFrame', relief='solid', borderwidth=1, background=self.colors['surface'])
        style.configure('Primary.TButton', font=('Segoe UI', 10))
        style.configure('Success.TButton', font=('Segoe UI', 10))

        # Configure root background
        self.root.configure(bg=self.colors['background'])

    def create_widgets(self):
        """Create main interface widgets"""
        # Add homescreen button at the top
        return_btn = ttk.Button(
            self.root,
            text=_t("common.return_to_homescreen"),
            command=self.return_to_main_menu
        )
        return_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        # Main container with minimal padding
        self.main_frame = ttk.Frame(self.root, padding="5")
        self.main_frame.grid(row=0, column=0, sticky="nsew")

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(0, weight=1)

        # Create sidebar
        self.create_sidebar()

        # Create main content area
        self.create_content_area()

        # Create status bar
        self.create_status_bar()

        # Keep the placed homescreen button above the gridded main frame
        return_btn.lift()

    def create_sidebar(self):
        """Create scrollable navigation sidebar"""
        # Create sidebar container
        sidebar_container = ttk.Frame(self.main_frame, style='Card.TFrame', width=250)
        sidebar_container.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        sidebar_container.grid_propagate(False)

        # Canvas + scrollbar for sidebar
        self.sidebar_canvas = tk.Canvas(sidebar_container, highlightthickness=0, bg='#f0f0f0', width=230)
        self.sidebar_scrollbar = ttk.Scrollbar(sidebar_container, orient="vertical", command=self.sidebar_canvas.yview)
        self.sidebar = ttk.Frame(self.sidebar_canvas)

        # Put sidebar frame inside canvas
        self.sidebar_window = self.sidebar_canvas.create_window((0, 0), window=self.sidebar, anchor="nw")

        # Wire up scrolling
        self.sidebar_canvas.configure(yscrollcommand=self.sidebar_scrollbar.set)
        self.sidebar_canvas.grid(row=0, column=0, sticky="nsew")
        self.sidebar_scrollbar.grid(row=0, column=1, sticky="ns")

        # Configure grid weights for sidebar container
        sidebar_container.rowconfigure(0, weight=1)
        sidebar_container.columnconfigure(0, weight=1)

        # Keep sidebar width in sync with canvas width
        def _on_sidebar_canvas_configure(event):
            self.sidebar_canvas.itemconfig(self.sidebar_window, width=event.width)
        self.sidebar_canvas.bind("<Configure>", _on_sidebar_canvas_configure)

        # Update scrollregion whenever sidebar content changes
        self.sidebar.bind(
            "<Configure>",
            lambda e: self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))
        )

        # Bind mouse wheel scrolling for sidebar
        self._bind_sidebar_scroll_events()

    def _bind_sidebar_scroll_events(self):
        """Bind mouse wheel and keys to sidebar scrolling"""
        def _on_mousewheel(event):
            # Only scroll if bar is visible (i.e., content taller than viewport)
            if hasattr(self, 'sidebar_scrollbar') and self.sidebar_scrollbar.winfo_viewable():
                if event.delta:  # Windows
                    self.sidebar_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                else:            # Linux
                    if event.num == 4:
                        self.sidebar_canvas.yview_scroll(-1, "units")
                    elif event.num == 5:
                        self.sidebar_canvas.yview_scroll(1, "units")

        def _on_keypress(event):
            if hasattr(self, 'sidebar_scrollbar') and self.sidebar_scrollbar.winfo_viewable():
                if event.keysym == 'Up':
                    self.sidebar_canvas.yview_scroll(-1, "units")
                elif event.keysym == 'Down':
                    self.sidebar_canvas.yview_scroll(1, "units")
                elif event.keysym == 'Page_Up':
                    self.sidebar_canvas.yview_scroll(-10, "units")
                elif event.keysym == 'Page_Down':
                    self.sidebar_canvas.yview_scroll(10, "units")

        # Bind to sidebar and its children
        if hasattr(self, 'sidebar_canvas'):
            self.sidebar_canvas.bind("<MouseWheel>", _on_mousewheel)  # Windows
            self.sidebar_canvas.bind("<Button-4>", _on_mousewheel)    # Linux
            self.sidebar_canvas.bind("<Button-5>", _on_mousewheel)    # Linux
            self.sidebar_canvas.bind("<KeyPress>", _on_keypress)
            self.sidebar_canvas.focus_set()

        # User info section
        user_frame = ttk.Frame(self.sidebar, padding="10")
        user_frame.pack(fill="x", pady=(0, 10))

        me = _common.actor(self)
        if me:
            user_info = f"👤 {me['username']}\n📋 {me['role'].replace('_', ' ').title()}"
        else:
            user_info = "👤 Not logged in"

        ttk.Label(user_frame, text=user_info, font=('Segoe UI', 10)).pack()

        # Navigation buttons
        self.nav_frame = ttk.Frame(self.sidebar, padding="10")
        self.nav_frame.pack(fill="both", expand=True)

        # Dashboard
        self.create_nav_button(_t("student_support.nav.dashboard"), self.show_dashboard)

        # Common features
        self.create_nav_button(_t("student_support.nav.search"), self.show_search)
        self.create_nav_button(_t("student_support.nav.faqs"), self.show_faqs)
        self.create_nav_button(_t("student_support.nav.knowledge_base"), self.show_knowledge_base)
        self.create_nav_button(_t("student_support.nav.resources"), self.show_resources)

        # Everyone raises and follows their own tickets (staff and
        # instructors too); case workers also get the staff screens.
        ttk.Separator(self.nav_frame, orient='horizontal').pack(fill="x", pady=10)
        self.create_nav_button(_t("student_support.nav.create_ticket"), self.show_create_ticket)
        self.create_nav_button(_t("student_support.nav.my_tickets"), self.show_my_tickets)
        self.create_nav_button(_t('gui.pastoral.student_support.base.nav.known_issues', default="📢 Known Issues"),
                               lambda: self._support_tool('open_known_issues'))
        if self.is_student():
            self.create_nav_button(_t("student_support.nav.templates"), self.show_ticket_templates)
            self.create_nav_button(_t("student_support.nav.submit_rating"), self.show_satisfaction_rating)

        if self.is_staff():
            ttk.Separator(self.nav_frame, orient='horizontal').pack(fill="x", pady=10)
            self.create_nav_button(_t("student_support.nav.all_tickets"), self.show_all_tickets)
            self.create_nav_button(_t('gui.pastoral.student_support.base.nav.caseload', default="🗂️ My Caseload"), self.show_caseload)
            self.create_nav_button(_t('gui.pastoral.student_support.base.nav.followed', default="👁️ Tickets I Follow"),
                                   lambda: self._support_tool('open_followed',
                                                              open_ticket=self.view_ticket_details))
            self.create_nav_button(_t('gui.pastoral.student_support.base.nav.incidents', default="🚨 Major Incidents"),
                                   lambda: self._support_tool('open_incidents',
                                                              open_ticket=self.view_ticket_details))
            if _common.is_support_staff(self):
                self.create_nav_button(_t("student_support.nav.reports"), self.show_reports)
                self.create_nav_button(_t('gui.pastoral.student_support.base.nav.service_report', default="📈 Service Report"), self.show_service_report)
                self.create_nav_button(_t("student_support.nav.manage_templates"), self.show_manage_templates)
                self.create_nav_button(_t("student_support.nav.manage_kb"), self.show_manage_kb)
                self.create_nav_button(_t("student_support.nav.bulk_operations"), self.show_bulk_operations)
                self.create_nav_button(_t("student_support.nav.export_data"), self.show_export_data_dialog)
            if _common.can_manage_users(self):
                self.create_nav_button(_t("student_support.nav.user_management"), self.show_user_management)
            if self.is_admin():
                self.create_nav_button(_t('gui.pastoral.student_support.base.nav.teams', default="👥 Teams"), self.show_teams_admin)
                self.create_nav_button(_t('gui.pastoral.student_support.base.nav.data_protection', default="🛡️ Data Protection"), self.show_data_protection)
                self.create_nav_button(_t('gui.pastoral.student_support.base.nav.support_mail', default="📥 Support E-mail"),
                                       lambda: self._support_tool('open_mail_quarantine'))
                self.create_nav_button(_t('gui.pastoral.student_support.base.nav.automation', default="⚙️ Automation"),
                                       lambda: self._support_tool('open_automation_settings'))
        # Settings
        ttk.Separator(self.nav_frame, orient='horizontal').pack(fill="x", pady=10)
        self.create_nav_button(_t("student_support.nav.preferences"), self.show_preferences)
        self.create_nav_button(_t("student_support.nav.notifications"), self.show_notifications)
        self.create_nav_button("💬 Feedback", self.show_general_feedback)

        # Link to Helpdesk GUI
        ttk.Separator(self.nav_frame, orient='horizontal').pack(fill="x", pady=10)
        self.create_nav_button(_t("student_support.nav.it_helpdesk"), self.open_helpdesk_gui)

        # Refresh button
        refresh_frame = ttk.Frame(self.sidebar, padding="10")
        refresh_frame.pack(side="bottom", fill="x")
        ttk.Button(refresh_frame, text=_t("common.refresh"), command=self.refresh_data).pack(fill="x")

        # Force scroll region update after all content is added
        self.sidebar.update_idletasks()
        self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))

        # Ensure canvas shows scrollbar when needed
        self.sidebar_canvas.update_idletasks()

    def _support_tool(self, name, *args, **kwargs):
        """Open one of the shared support windows (links, time, followers,
        incidents, known issues, e-mail review, automation) as the signed-in
        user; the support services check permission."""
        from education_system.systems.university.domains.student_support.interfaces.gui.helpdesk import (
            support_tools,
        )
        return getattr(support_tools, name)(self.root, self.auth, *args, **kwargs)

    def create_nav_button(self, text, command):
        """Create a navigation button"""
        btn = ttk.Button(self.nav_frame, text=text, command=command, width=25)
        btn.pack(fill="x", pady=2)
        return btn

    def create_content_area(self):
        """Create main content area with scrollbar"""
        # Content container
        content_container = ttk.Frame(self.main_frame, style='Card.TFrame')
        content_container.grid(row=0, column=1, sticky="nsew")
        content_container.rowconfigure(0, weight=1)
        content_container.columnconfigure(0, weight=1)


        # Create canvas and scrollbar for content area
        self.content_canvas = tk.Canvas(content_container, highlightthickness=0)
        content_scrollbar = ttk.Scrollbar(content_container, orient="vertical", command=self.content_canvas.yview)
        self.content_frame = ttk.Frame(self.content_canvas)

        self.content_frame.bind(
            "<Configure>",
            lambda e: self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))
        )

        # Put content_frame inside the canvas and keep a reference
        self.content_window = self.content_canvas.create_window((0, 0), window=self.content_frame, anchor="nw")

        # Keep content_frame size in sync with the canvas size
        def _on_content_canvas_configure(event):
            self.content_canvas.itemconfig(self.content_window, width=event.width, height=event.height)

        self.content_canvas.bind("<Configure>", _on_content_canvas_configure)

        self.content_canvas.configure(yscrollcommand=content_scrollbar.set)

        self.content_canvas.pack(side="left", fill="both", expand=True)
        content_scrollbar.pack(side="right", fill="y")

        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(0, weight=1)


        # Create notebook for multiple views within the scrollable content
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        # Initialize with dashboard
        self.show_dashboard()

    def create_status_bar(self):
        """Create status bar"""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 3))

        self.status_var = tk.StringVar()
        self.status_var.set(_t("common.ready"))

        ttk.Label(self.status_frame, textvariable=self.status_var).pack(side="left")

        # System status indicator
        self.system_status = ttk.Label(self.status_frame, text=_t("common.online"))
        self.system_status.pack(side="right")

    def create_menu(self):
        """Create application menu with role-based filtering"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # Get user role for filtering
        is_admin = self.is_admin()
        is_staff = self.is_staff()
        is_student = self.is_student()

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.file"), menu=file_menu)
        file_menu.add_command(label=_t("student_support.menu.new_ticket"), command=self.show_create_ticket,
                              accelerator="Ctrl+N")

        # Support staff can export data (the same dialog as the sidebar's
        # Export Data, which checks the role again).
        if _common.is_support_staff(self):
            file_menu.add_separator()
            file_menu.add_command(label=_t("student_support.menu.export_data"), command=self.show_export_dialog)
            file_menu.add_separator()

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.view"), menu=view_menu)
        view_menu.add_command(label=_t("student_support.menu.dashboard"), command=self.show_dashboard)
        view_menu.add_command(label=_t('gui.pastoral.student_support.base.menu.my_tickets', default="My Tickets"),
                              command=self.show_my_tickets)

        if is_staff:
            view_menu.add_command(label=_t("student_support.menu.all_tickets"), command=self.show_all_tickets)
            view_menu.add_command(label=_t('gui.pastoral.student_support.base.menu.caseload', default="My Caseload"),
                                  command=self.show_caseload)
            if _common.is_support_staff(self):
                view_menu.add_command(label=_t('gui.pastoral.student_support.base.menu.service_report', default="Service Report"),
                                      command=self.show_service_report)
        if is_admin:
            view_menu.add_command(label=_t('gui.pastoral.student_support.base.menu.teams', default="Teams"),
                                  command=self.show_teams_admin)
            view_menu.add_command(label=_t('gui.pastoral.student_support.base.menu.data_protection', default="Data Protection"),
                                  command=self.show_data_protection)

        view_menu.add_command(label=_t("student_support.menu.search"), command=self.show_search,
                              accelerator="Ctrl+F")

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.tools"), menu=tools_menu)
        tools_menu.add_command(label=_t("student_support.menu.preferences"), command=self.show_preferences)
        tools_menu.add_command(label=_t("student_support.menu.refresh_data"), command=self.refresh_data,
                               accelerator="F5")

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.help"), menu=help_menu)
        help_menu.add_command(label=_t("student_support.menu.user_guide"), command=self.show_help)
        help_menu.add_command(label=_t("student_support.menu.about"), command=self.show_about)

    def clear_content(self):
        """Remove every notebook tab and destroy the widgets behind it.

        ``forget()`` detaches a tab but leaves the frame — and everything in
        it — alive as a child of the notebook. Every navigation click built a
        fresh screen and abandoned the previous one, so widgets accumulated
        for the life of the session until the X server ran out of pixmaps
        ("BadAlloc ... X_CreatePixmap"). Destroying the frame frees them.

        Leaving the New Ticket screen closes its self-help suggestion visit
        (read a suggestion and left: deflected; else abandoned).
        """
        if getattr(self, '_deflection_visit', None):
            self._close_deflection_visit()
        for tab in self.notebook.tabs():
            try:
                widget = self.notebook.nametowidget(tab)
            except KeyError:
                widget = None
            self.notebook.forget(tab)
            if widget is not None:
                try:
                    widget.destroy()
                except tk.TclError:
                    pass

    def update_status(self, message):
        """Update status bar message"""
        try:
            if hasattr(self, 'status_var') and self.status_var:
                self.status_var.set(message)
                self.root.update_idletasks()
        except Exception:
            # If status_var doesn't exist yet, just ignore the update
            logger.debug("Suppressed exception", exc_info=True)

