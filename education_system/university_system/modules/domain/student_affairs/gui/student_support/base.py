import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import tkinter.font as tkFont
from datetime import datetime, timedelta
import json
import os
import threading
import webbrowser
from typing import Dict, List, Optional, Any
from education_system.university_system.infrastructure.database.db import sqlite3
from pathlib import Path
import logging
from education_system.university_system.modules.shared.constants import paths

# Import i18n for language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import activity logger for audit trail
try:
    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import email service for notifications
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    from education_system.university_system.infrastructure.email.templates import load_template, render_template
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    send_email = lambda *args, **kwargs: False
    load_template = lambda *args, **kwargs: None
    render_template = lambda *args, **kwargs: (None, None)

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# --------------------------------------------------------------------
# Override sqlite3.connect for this module when targeting the
# student_records.db database. Many functions within this GUI refer to
# str(DEFAULT_DB_PATH) without specifying a full path. Without this
# override, a new database would be created in the current working
# directory, leading to multiple database files and missing tables. The
# override redirects connections to the shared student_records.db in
# university_system/data/db_files. If a different database name/path is
# supplied, the connection falls back to the original behaviour.

_original_sqlite3_connect = sqlite3.connect  # preserve original

def _patched_sqlite_connect(database, *args, **kwargs):
    """Redirect connections targeting student_records.db to the central path."""
    try:
        # Determine basename; accept Path or str
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name == str(DEFAULT_DB_PATH):
            return _original_sqlite3_connect(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except Exception:
        pass
    return _original_sqlite3_connect(database, *args, **kwargs)

sqlite3.connect = _patched_sqlite_connect

# Import all functionality from student_support module (it's a single monolithic file)
try:
    # Import everything from the single student_support module
    from education_system.university_system.modules.domain.student_affairs.services.student_support import (
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
        from education_system.university_system.modules.domain.student_affairs.services.student_support import (
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
        self.root.geometry("1850x1100")
        self.root.minsize(1400, 900)

        # Initialize authentication system - use provided auth or global fallback
        if auth_system:
            self.auth = auth_system
        else:
            global auth
            self.auth = auth if 'auth' in globals() and auth is not None else None

        # Initialize support system
        self.config = None
        try:
            if SupportConfig is None or EnhancedStudentSupport is None:
                raise RuntimeError("Enhanced support components are unavailable")

            self.config = SupportConfig()
            self.support = EnhancedStudentSupport(self.config)
        except Exception as e:
            messagebox.showerror("Initialization Error", f"Failed to initialize support system: {e}")
            self.support = None

        # Theme configuration
        self.setup_theme()

        # GUI state
        self.current_ticket = None
        self.search_results = {}
        self.dashboard_data = {}

        # Initialize status_var early to prevent attribute errors
        self.status_var = None
        self._faq_last_mode = 'category'
        self._faq_last_category = None
        self._faq_last_query = None
        self._kb_last_mode = 'list'
        self._kb_last_search = ''
        self.resource_records: Dict[int, Dict[str, Any]] = {}
        self.template_records: Dict[int, Dict[str, Any]] = {}

        # Setup current user from existing authentication system
        self.setup_current_user()

        # Check authentication status - require login through main system
        # Ensure self.auth is set from shared_context if not already provided
        if not self.auth:
            from education_system.university_system.infrastructure.shared_context import get_auth
            self.auth = get_auth()

        # Robust authentication check
        auth_valid = False
        if self.auth:
            # Check if current_user exists and is not None/empty
            if hasattr(self.auth, 'current_user') and self.auth.current_user:
                # Additional check: ensure it's a dict with at least username
                if isinstance(self.auth.current_user, dict) and self.auth.current_user.get('username'):
                    auth_valid = True
                    print(f"✓ Student Support GUI: Authenticated as {self.auth.current_user.get('username')} ({self.auth.current_user.get('role', 'user')})")

        if not auth_valid:
            print(f"✗ Student Support GUI: Authentication failed - auth={self.auth}, current_user={getattr(self.auth, 'current_user', None) if self.auth else None}")
            messagebox.showerror("Authentication Required",
                "Please log in through the main University System GUI.\n\n"
                "Run: python run.py --gui")
            self.root.destroy()
            return

        # Set auth in the student_support module so service functions can access it
        try:
            set_auth(self.auth)
            print(f"✓ Student Support GUI: Auth context set in service module")
        except Exception as e:
            print(f"⚠ Warning: Could not set auth in service module: {e}")

        # Create main interface
        self.create_widgets()
        self.create_menu()

        # Load dashboard
        self.load_dashboard()

    def setup_current_user(self):
        """Setup current user from existing authentication system"""
        try:
            # Ensure we have the most current authentication info
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                print(f"✓ Student Support GUI: Using authenticated user {self.auth.current_user.get('username', 'Unknown')} ({self.auth.current_user.get('role', 'user')})")
            else:
                print("ℹ Student Support GUI: No authenticated user - will show login required message")
        except Exception as e:
            print(f"✗ Error checking current user: {e}")

    def _get_current_user_identity(self):
        """Return (user_id, username) for the authenticated user if available."""
        if not self.auth or not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            return None, None
        current = self.auth.current_user
        user_id = current.get('id') or current.get('user_id')
        username = current.get('username')
        return user_id, username

    def get_user_role(self):
        """Get the current user's role from authentication system"""
        try:
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                role = self.auth.current_user.get('role', '').lower()
                return role
            return None
        except Exception as e:
            print(f"Error getting user role: {e}")
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff or support staff"""
        role = self.get_user_role()
        return role in ['staff', 'support_staff', 'instructor']

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'

    def _safe_db_call(self, operation, *args, **kwargs):
        """Run a database operation with automatic commit/rollback handling."""
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
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

        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            username = getattr(self.auth.current_user, 'username', 'Unknown') if hasattr(self.auth.current_user, 'username') else self.auth.current_user.get('username', 'Unknown')
            role = getattr(self.auth.current_user, 'role', 'user') if hasattr(self.auth.current_user, 'role') else self.auth.current_user.get('role', 'user')
            user_info = f"👤 {username}\n📋 {role.title()}"
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

        # Role-based features
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            user_role = getattr(self.auth.current_user, 'role', 'user') if hasattr(self.auth.current_user, 'role') else self.auth.current_user.get('role', 'user')

            if user_role == 'student':
                ttk.Separator(self.nav_frame, orient='horizontal').pack(fill="x", pady=10)
                self.create_nav_button(_t("student_support.nav.create_ticket"), self.show_create_ticket)
                self.create_nav_button(_t("student_support.nav.my_tickets"), self.show_my_tickets)
                self.create_nav_button(_t("student_support.nav.templates"), self.show_ticket_templates)
                self.create_nav_button(_t("student_support.nav.submit_rating"), self.show_satisfaction_rating)

            elif user_role in ('staff', 'admin'):
                ttk.Separator(self.nav_frame, orient='horizontal').pack(fill="x", pady=10)
                self.create_nav_button(_t("student_support.nav.all_tickets"), self.show_all_tickets)
                self.create_nav_button(_t("student_support.nav.reports"), self.show_reports)
                self.create_nav_button(_t("student_support.nav.manage_templates"), self.show_manage_templates)
                self.create_nav_button(_t("student_support.nav.manage_kb"), self.show_manage_kb)
                self.create_nav_button(_t("student_support.nav.bulk_operations"), self.show_bulk_operations)
                self.create_nav_button(_t("student_support.nav.export_data"), self.show_export_data_dialog)
                self.create_nav_button(_t("student_support.nav.user_management"), self.show_user_management)
        # Settings
        ttk.Separator(self.nav_frame, orient='horizontal').pack(fill="x", pady=10)
        self.create_nav_button(_t("student_support.nav.preferences"), self.show_preferences)
        self.create_nav_button(_t("student_support.nav.notifications"), self.show_notifications)

        # Link to Helpdesk GUI
        ttk.Separator(self.nav_frame, orient='horizontal').pack(fill="x", pady=10)
        self.create_nav_button(_t("student_support.nav.it_helpdesk"), self.open_helpdesk_gui)

        # Refresh button
        refresh_frame = ttk.Frame(self.sidebar, padding="10")
        refresh_frame.pack(side="bottom", fill="x")
        ttk.Button(refresh_frame, text=_t("common.refresh"), command=self.refresh_data).pack(fill="x")
        ttk.Button(refresh_frame, text=_t("common.return_to_homescreen"), command=self.return_to_main_menu).pack(fill="x", pady=(8, 0))

        # Force scroll region update after all content is added
        self.sidebar.update_idletasks()
        self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))

        # Ensure canvas shows scrollbar when needed
        self.sidebar_canvas.update_idletasks()

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
        file_menu.add_command(label=_t("student_support.menu.new_ticket"), command=self.show_create_ticket)

        # Admin/Staff can export data
        if is_admin or is_staff:
            file_menu.add_separator()
            file_menu.add_command(label=_t("student_support.menu.export_data"), command=self.show_export_dialog)
            file_menu.add_separator()

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.view"), menu=view_menu)
        view_menu.add_command(label=_t("student_support.menu.dashboard"), command=self.show_dashboard)

        # Admin/Staff can view all tickets
        if is_admin or is_staff:
            view_menu.add_command(label=_t("student_support.menu.all_tickets"), command=self.show_all_tickets)

        view_menu.add_command(label=_t("student_support.menu.search"), command=self.show_search)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.tools"), menu=tools_menu)
        tools_menu.add_command(label=_t("student_support.menu.preferences"), command=self.show_preferences)
        tools_menu.add_command(label=_t("student_support.menu.refresh_data"), command=self.refresh_data)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.help"), menu=help_menu)
        help_menu.add_command(label=_t("student_support.menu.user_guide"), command=self.show_help)
        help_menu.add_command(label=_t("student_support.menu.about"), command=self.show_about)

    def clear_content(self):
        """Clear all notebook tabs"""
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)

    def update_status(self, message):
        """Update status bar message"""
        try:
            if hasattr(self, 'status_var') and self.status_var:
                self.status_var.set(message)
                self.root.update_idletasks()
        except Exception:
            # If status_var doesn't exist yet, just ignore the update
            pass


def _patched_sqlite_connect(database, *args, **kwargs):
    """Redirect connections targeting student_records.db to the central path."""
    try:
        # Determine basename; accept Path or str
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name == str(DEFAULT_DB_PATH):
            return _original_sqlite3_connect(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except Exception:
        pass
    return _original_sqlite3_connect(database, *args, **kwargs)
