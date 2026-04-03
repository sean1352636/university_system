"""
Enhanced Library Management System - GUI Version
Maintains all original CLI functions while adding a modern GUI interface
Backwards compatible with existing database and auth systems
"""


from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()
from tkinter.scrolledtext import ScrolledText
import threading
import queue
import os
import sys
from datetime import datetime, timedelta
import json
from education_system.university_system.infrastructure.database.db import sqlite3
from typing import Dict, List, Optional, Any
import logging
import urllib.request
import urllib.parse
import urllib.error

# Import custom exceptions for better error handling
from education_system.university_system.infrastructure.exceptions import (
    DatabaseError,
    QueryError,
    ValidationError,
    InvalidInputError,
    FileError,
    UniversityFileNotFoundError
)

# Import all original library functions
try:
    # Import from modular library package
    from education_system.university_system.modules.domain.academics.services.library.settings import (
        auth, get_current_user_id, set_auth, get_library_settings, update_library_setting
    )
    from education_system.university_system.modules.domain.academics.services.library.menu import display_library_menu
    from education_system.university_system.modules.domain.academics.services.library.barcode import (
        generate_barcode, generate_qr_code, process_scanned_barcode
    )
    from education_system.university_system.modules.domain.academics.services.library.reports import (
        generate_circulation_report, generate_library_statistics_export, generate_user_activity_report
    )
    from education_system.university_system.modules.domain.academics.services.library.database import (
        get_db_connection, init_library_db, log_audit_event
    )
    from education_system.university_system.modules.domain.academics.services.library.backup import (
        quick_system_health_check, restore_from_backup
    )
    from education_system.university_system.modules.domain.academics.services.library.reading_lists import view_reading_list_details
    ORIGINAL_LIBRARY_AVAILABLE = True
except ImportError:
    print("Warning: Original library module not found. GUI will use standalone functions.")
    ORIGINAL_LIBRARY_AVAILABLE = False

# Import shared authentication system
try:
    from education_system.university_system.infrastructure.auth import UserAuth
    from education_system.university_system.infrastructure.shared_context import get_auth, get_current_user
    SHARED_AUTH_AVAILABLE = True
except ImportError:
    print("Warning: Shared authentication system not found.")
    SHARED_AUTH_AVAILABLE = False
    # Provide fallback functions
    def get_auth():
        return None
    def get_current_user():
        return None

from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD,
        ensure_student_finance_account_exists,
        top_up_student_finance_account
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

# Import matplotlib for library finance charts
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: Matplotlib not available for library finance charts")

# Import email service for library finance notifications
try:
    from education_system.university_system.infrastructure.email.email_service import send_email_as_system
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    def send_email_as_system(*args, **kwargs):
        return False
    print("Warning: Email service not available for library finance")

_AUDIT_LOG_COLUMNS_CACHE: Optional[List[str]] = None
_STUDENT_COLUMNS_CACHE: Optional[List[str]] = None

class LibraryGUI:
    def __init__(self, master, auth=None):
        self.master = master
        self.master.title(_("library.title"))
        self.master.geometry("1400x900")
        if master is None:
            self.master = tk.Tk()
            self.owns_root = True
        else:
            self.master = master
            self.owns_root = False

        # Use provided auth or create new one if not provided
        self.auth = auth if auth else None

        # Cross-platform window maximization
        try:
            # Try Windows-specific maximization first
            self.master.state('zoomed')
        except tk.TclError:
            # Fallback for Linux/Unix systems
            try:
                # Get screen dimensions
                screen_width = self.master.winfo_screenwidth()
                screen_height = self.master.winfo_screenheight()
                # Set window to nearly full screen (leave some space for taskbar)
                self.master.geometry(f"{screen_width-50}x{screen_height-100}+25+25")
            except tk.TclError:
                # Final fallback - just use the default size
                self.master.geometry("1400x900")

        # Set up styling
        self.setup_styles()

        # Initialize variables
        self.search_results = []
        self.current_book_details = None

        # Initialize GUI components
        self.setup_gui()

        # Initialize database and auth if original library is available
        if ORIGINAL_LIBRARY_AVAILABLE:
            self.initialize_library_system()

        # Setup authentication - use provided auth or initialize if needed
        self.setup_shared_authentication()

        # Setup event handlers
        self.setup_event_handlers()

        # Check for late fees and display notification
        self.check_and_display_late_fees()

    def get_user_role(self):
        """Get the current user's role from authentication system"""
        try:
            if self.auth:
                if hasattr(self.auth, 'current_user') and self.auth.current_user:
                    role = self.auth.current_user.get('role', '').lower()
                    return role
                elif hasattr(self.auth, 'user_role'):
                    return self.auth.user_role.lower()
            return None
        except (AttributeError, TypeError, KeyError) as e:
            print(f"Error getting user role: {e}")
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff/instructor"""
        role = self.get_user_role()
        return role in ['staff', 'instructor', 'faculty']

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'

    def __getattr__(self, name):
        """Fallback for undefined attributes or commands.

        Many menu commands and button callbacks in the GUI reference
        methods that may not yet be implemented.  Instead of raising
        ``AttributeError`` and causing the application to crash, this
        fallback returns a placeholder function for any undefined
        attribute accessed on the ``LibraryGUI`` instance.  When
        invoked, the placeholder will display a warning message
        informing the user that the requested feature is not yet
        available.

        Parameters
        ----------
        name : str
            The attribute name being accessed.

        Returns
        -------
        Callable
            A function that accepts arbitrary arguments and displays a
            warning message.
        """
        # Only generate placeholders for attributes that start with typical
        # command prefixes.  This avoids intercepting legitimate
        # attribute accesses such as Tkinter variables or internal state.
        if name.startswith(('import_', 'export_', 'backup_', 'restore_',
                            'show_', 'add_', 'edit_', 'delete_', 'reserve_',
                            'checkout_', 'return_', 'view_', 'contact_',
                            'share_', 'update_', 'process_', 'waive_')):
            def placeholder(*args, **kwargs):
                try:
                    messagebox.showwarning(
                        _("library.messages.feature_not_implemented_title"),
                        _("library.messages.feature_not_implemented").format(name=name)
                    )
                except tk.TclError:
                    # If messagebox cannot be displayed (e.g., in headless
                    # environments), log to console instead
                    print(f"Warning: '{name}' is not implemented yet.")
            return placeholder
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def get_db_connection():
        """Get database connection - wrapper for backwards compatibility"""
        if ORIGINAL_LIBRARY_AVAILABLE:
            # This should call the original library's get_db_connection
            try:
                from education_system.university_system.modules.domain.academics.services.library.database import get_db_connection as original_get_db_connection
                return original_get_db_connection()
            except ImportError:
                pass

        # Fallback implementation
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            return sqlite3.connect(str(DEFAULT_DB_PATH))
        except (sqlite3.Error, OSError) as e:
            print(f"Database connection error: {e}")
            return None

    def setup_styles(self):
        """Configure GUI styling"""
        style = ttk.Style()
        style.theme_use('clam')

        # Configure custom styles
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
        style.configure('Heading.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Success.TLabel', foreground='green')
        style.configure('Error.TLabel', foreground='red')
        style.configure('Warning.TLabel', foreground='orange')

    def setup_gui(self):
        """Create the main GUI layout"""
        # Create main menu bar
        self.create_menu_bar()

        # Quick toolbar
        toolbar = ttk.Frame(self.master)
        toolbar.pack(fill=tk.X, padx=5, pady=(5, 0))
        ttk.Button(toolbar, text=_("library.buttons.return_to_main_menu"), command=self.return_to_main_menu).pack(side=tk.LEFT)

        # Create main frame with sidebar and content area
        self.main_frame = ttk.Frame(self.master)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create sidebar for navigation
        self.create_sidebar()

        # Create main content area
        self.create_content_area()

        # Create status bar
        self.create_status_bar()

        # Show dashboard directly if authenticated, otherwise show message
        self.initialize_main_content()

    def create_menu_bar(self):
        """Create the application menu bar with role-based access"""
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)

        is_admin = self.is_admin()
        is_staff = self.is_staff()
        is_student = self.is_student()

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("library.menu.file"), menu=file_menu)

        # Admin and Staff can import/export
        if is_admin or is_staff:
            file_menu.add_command(label=_("library.menu.bulk_import_books"), command=self.bulk_import_books_gui)
            file_menu.add_command(label=_("library.menu.bulk_export_books"), command=self.bulk_export_books_gui)
            file_menu.add_separator()

        # Admin only - System backup/restore
        if is_admin:
            file_menu.add_command(label=_("library.menu.backup_system"), command=self.backup_system_gui)
            file_menu.add_command(label=_("library.menu.restore_system"), command=self.restore_system_gui)
            file_menu.add_separator()

        file_menu.add_command(label=_("common.exit"), command=self.exit_application)

        # Admin and Staff can export statistics
        if is_admin or is_staff:
            file_menu.add_separator()
            file_menu.add_command(label=_("library.menu.export_statistics"), command=self.generate_library_statistics_export)

        # Edit menu - Admin and Staff only
        if is_admin or is_staff:
            edit_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("library.menu.edit"), menu=edit_menu)

            if is_admin:
                edit_menu.add_command(label=_("library.menu.settings"), command=self.show_settings)
                edit_menu.add_command(label=_("library.menu.enhanced_settings_management"), command=self.enhanced_settings_management_gui)

            edit_menu.add_command(label=_("library.menu.user_preferences"), command=self.show_user_preferences)

            if is_admin:
                edit_menu.add_separator()
                edit_menu.add_command(label=_("library.menu.export_settings"), command=self.export_settings_gui)
                edit_menu.add_command(label=_("library.menu.import_settings"), command=self.import_settings_gui)
                edit_menu.add_command(label=_("library.menu.reset_to_defaults"), command=self.reset_settings_to_default_gui)
                edit_menu.add_command(label=_("library.menu.backup_settings"), command=self.backup_settings_only_gui)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("library.menu.view"), menu=view_menu)
        view_menu.add_command(label=_("library.menu.dashboard"), command=self.show_dashboard)
        view_menu.add_command(label=_("library.menu.all_books"), command=self.show_all_books)

        # Staff and Admin can see overdue items
        if is_admin or is_staff:
            view_menu.add_command(label=_("library.menu.overdue_items"), command=self.show_overdue_books)

        view_menu.add_command(label=_("library.menu.book_return_calendar"), command=self.open_calendar_with_due_dates)

        # Reports - Admin and Staff only
        if is_admin or is_staff:
            view_menu.add_command(label=_("library.menu.reports"), command=self.show_reports)
            view_menu.add_separator()
            view_menu.add_command(label=_("library.menu.advanced_analytics_dashboard"), command=self.show_advanced_analytics_gui)

        # System Maintenance - Admin only
        if is_admin:
            view_menu.add_separator()
            view_menu.add_command(label=_("library.menu.system_maintenance"), command=self.library_maintenance_gui)

        # Circulation menu
        circulation_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("library.menu.circulation"), menu=circulation_menu)
        circulation_menu.add_command(label=_("library.menu.checkout_book"), command=self.enhanced_checkout_book_gui)
        circulation_menu.add_command(label=_("library.menu.return_book"), command=self.enhanced_return_book_gui)
        circulation_menu.add_command(label=_("library.menu.renew_book"), command=self.renew_book_gui)
        circulation_menu.add_separator()
        circulation_menu.add_command(label=_("library.menu.reserve_book"), command=self.reserve_book_gui)

        # Manage Reservations - Staff and Admin only
        if is_admin or is_staff:
            circulation_menu.add_command(label=_("library.menu.manage_reservations"), command=self.manage_reservations_gui)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("library.menu.tools"), menu=tools_menu)
        tools_menu.add_command(label=_("library.menu.advanced_search"), command=self.show_advanced_search_gui)

        # Barcode Scanner - Staff and Admin only
        if is_admin or is_staff:
            tools_menu.add_command(label=_("library.menu.barcode_scanner"), command=self.show_barcode_scanner)

        tools_menu.add_separator()
        tools_menu.add_command(label=_("library.menu.reading_lists"), command=self.manage_reading_lists_gui)
        tools_menu.add_command(label=_("library.menu.rate_review_book"), command=self.rate_and_review_book_gui)
        tools_menu.add_separator()
        tools_menu.add_command(label=_("library.menu.digital_library"), command=self.show_digital_library_gui)

        # Digital Access Permissions - Admin only
        if is_admin:
            tools_menu.add_command(label=_("library.menu.digital_access_permissions"), command=self.manage_digital_access_permissions_gui)

        tools_menu.add_separator()
        tools_menu.add_command(label=_("library.menu.loan_history"), command=self.view_loan_history_gui)

        # Process Fine Payment - Staff and Admin only
        if is_admin or is_staff:
            tools_menu.add_command(label=_("library.menu.process_fine_payment"), command=self.process_fine_payment_gui)
            tools_menu.add_separator()
            tools_menu.add_command(label=_("library.menu.library_events"), command=self.manage_library_events_gui)

        # Library Card Generation - Staff and Admin only
        if is_admin or is_staff:
            tools_menu.add_separator()
            tools_menu.add_command(label=_("library.menu.generate_library_card"), command=self.generate_library_card_gui)
            tools_menu.add_command(label=_("library.menu.bulk_generate_cards"), command=self.bulk_generate_library_cards_gui)
            tools_menu.add_command(label=_("library.menu.print_library_card"), command=self.print_library_card_gui)
            tools_menu.add_separator()
            tools_menu.add_command(label=_("library.menu.barcode_generator"), command=self.show_barcode_generator)

        # Reports menu - Admin and Staff only
        if is_admin or is_staff:
            reports_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("library.menu.reports"), menu=reports_menu)
            reports_menu.add_command(label=_("library.menu.circulation_report"), command=self.generate_circulation_report_gui)
            reports_menu.add_command(label=_("library.menu.advanced_analytics"), command=self.show_advanced_analytics_gui)
            reports_menu.add_command(label=_("library.menu.export_analytics"), command=self.export_analytics_report)

        # System menu - Admin only
        if is_admin:
            system_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("library.menu.system"), menu=system_menu)
            system_menu.add_command(label=_("library.menu.automated_notifications"), command=self.send_automated_notifications_gui)
            system_menu.add_separator()
            system_menu.add_command(label=_("library.menu.backup_recovery"), command=self.system_backup_gui)
            system_menu.add_command(label=_("library.menu.system_maintenance"), command=self.library_maintenance_gui)
            system_menu.add_separator()
            system_menu.add_command(label=_("library.menu.system_health_check"), command=self.system_health_check_gui)
            system_menu.add_command(label=_("library.menu.database_optimization"), command=self.database_optimization_gui)
            system_menu.add_command(label=_("library.menu.clear_cache"), command=self.clear_cache_gui)
            system_menu.add_separator()
            system_menu.add_command(label=_("library.menu.view_audit_log"), command=self.view_audit_log_gui)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("library.menu.help"), menu=help_menu)
        help_menu.add_command(label=_("library.menu.user_guide"), command=self.show_help)
        help_menu.add_command(label=_("library.menu.keyboard_shortcuts"), command=self.show_shortcuts)
        help_menu.add_separator()
        help_menu.add_command(label=_("library.menu.about"), command=self.show_about)

    def create_sidebar(self):
        """Create the navigation sidebar"""
        # Create sidebar container
        sidebar_container = ttk.Frame(self.main_frame, width=250)
        sidebar_container.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        sidebar_container.pack_propagate(False)

        # Canvas + scrollbar for sidebar
        self.sidebar_canvas = tk.Canvas(sidebar_container, highlightthickness=0, bg='#f0f0f0', width=230)
        self.sidebar_scrollbar = ttk.Scrollbar(sidebar_container, orient="vertical", command=self.sidebar_canvas.yview)
        self.sidebar = ttk.Frame(self.sidebar_canvas)

        # Put sidebar frame inside canvas
        self.sidebar_window = self.sidebar_canvas.create_window((0, 0), window=self.sidebar, anchor="nw")

        # Wire up scrolling
        self.sidebar_canvas.configure(yscrollcommand=self.sidebar_scrollbar.set)
        self.sidebar_canvas.pack(side='left', fill='both', expand=True)
        self.sidebar_scrollbar.pack(side='right', fill='y')

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

        # Title
        title_label = ttk.Label(self.sidebar, text=_("library.sidebar.title"), style='Title.TLabel')
        title_label.pack(pady=(10, 20))

        # User info frame
        self.user_frame = ttk.LabelFrame(self.sidebar, text=_("library.sidebar.user_information"))
        self.user_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # User display will be updated after auth is set up
        self.user_label = ttk.Label(self.user_frame, text=_("library.sidebar.initializing"))
        self.user_label.pack(pady=5)

        # Navigation buttons
        nav_frame = ttk.LabelFrame(self.sidebar, text=_("library.sidebar.navigation"))
        nav_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Define navigation items
        nav_items = [
            (_("library.nav.dashboard"), self.show_dashboard),
            (_("library.nav.all_books"), self.show_all_books),
            (_("library.nav.search_books"), self.show_search_books),
            (_("library.nav.add_book"), self.show_add_book),
            (_("library.nav.checkout"), self.show_checkout),
            (_("library.nav.return"), self.show_return),
            (_("library.nav.reservations"), self.show_reservations),
            (_("library.nav.reading_lists"), self.show_reading_lists),
            (_("library.nav.reviews"), self.show_reviews),
            (_("library.nav.library_finance"), self.open_library_finance),
            (_("library.nav.loan_history"), self.view_loan_history_gui),
            (_("library.nav.library_cards"), self.show_library_cards_generator),
            (_("library.nav.barcode_tools"), self.show_barcode_generator),
            (_("library.nav.maintenance"), self.library_maintenance_gui),
            (_("library.nav.system_health"), self.quick_system_health_check),
            (_("library.nav.reports"), self.show_reports),
            (_("library.nav.settings"), self.show_settings),
        ]

        self.nav_buttons = {}
        for text, command in nav_items:
            btn = ttk.Button(nav_frame, text=text, command=command, width=30)
            btn.pack(fill=tk.X, padx=5, pady=2)
            self.nav_buttons[text] = btn

        # Force scroll region update after all content is added
        self.sidebar.update_idletasks()
        self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))

        # Ensure canvas shows scrollbar when needed
        self.sidebar_canvas.update_idletasks()

    def create_content_area(self):
        """Create the main content area with scrollbar"""
        # Create container for scrollable content
        content_container = ttk.Frame(self.main_frame)
        content_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Create canvas and scrollbar for content area
        self.content_canvas = tk.Canvas(content_container, highlightthickness=0)
        content_scrollbar = ttk.Scrollbar(content_container, orient="vertical", command=self.content_canvas.yview)
        self.content_frame = ttk.Frame(self.content_canvas)

        self.content_frame.bind(
            "<Configure>",
            lambda e: self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))
        )

        self.content_canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
        self.content_canvas.configure(yscrollcommand=content_scrollbar.set)

        self.content_canvas.pack(side="left", fill="both", expand=True)
        content_scrollbar.pack(side="right", fill="y")

        # Create notebook for tabbed interface within the scrollable content
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

    def create_status_bar(self):
        """Create the status bar"""
        self.status_frame = ttk.Frame(self.master)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(self.status_frame, text=_("library.status.ready"))
        self.status_label.pack(side=tk.LEFT, padx=5)

        # Connection status
        self.connection_label = ttk.Label(self.status_frame, text="●", foreground="red")
        self.connection_label.pack(side=tk.RIGHT, padx=5)

        # Current time
        self.time_label = ttk.Label(self.status_frame, text="")
        self.time_label.pack(side=tk.RIGHT, padx=5)

        # Start time updates
        self.update_time()

    def _bind_sidebar_scroll_events(self):
        """Bind mouse wheel and keys to sidebar scrolling"""
        def _on_mousewheel(event):
            # Only scroll if bar is visible (i.e., content taller than viewport)
            if self.sidebar_scrollbar.winfo_viewable():
                if event.delta:  # Windows
                    self.sidebar_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                else:            # Linux
                    if event.num == 4:
                        self.sidebar_canvas.yview_scroll(-1, "units")
                    elif event.num == 5:
                        self.sidebar_canvas.yview_scroll(1, "units")

        def _on_keypress(event):
            if self.sidebar_scrollbar.winfo_viewable():
                if event.keysym == 'Up':
                    self.sidebar_canvas.yview_scroll(-1, "units")
                elif event.keysym == 'Down':
                    self.sidebar_canvas.yview_scroll(1, "units")
                elif event.keysym == 'Page_Up':
                    self.sidebar_canvas.yview_scroll(-10, "units")
                elif event.keysym == 'Page_Down':
                    self.sidebar_canvas.yview_scroll(10, "units")

        # Bind to sidebar and its children
        self.sidebar_canvas.bind("<MouseWheel>", _on_mousewheel)  # Windows
        self.sidebar_canvas.bind("<Button-4>", _on_mousewheel)    # Linux
        self.sidebar_canvas.bind("<Button-5>", _on_mousewheel)    # Linux
        self.sidebar_canvas.bind("<KeyPress>", _on_keypress)
        self.sidebar_canvas.focus_set()

    def update_time(self):
        """Update the time display"""
        try:
            # Check if master window still exists
            if not hasattr(self, 'master') or not self.master.winfo_exists():
                return

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if hasattr(self, 'time_label') and self.time_label.winfo_exists():
                self.time_label.config(text=current_time)
            self.master.after(1000, self.update_time)
        except (tk.TclError, Exception):
            # Window destroyed, don't schedule next update
            pass

    def initialize_library_system(self):
        """Initialize the library system with backwards compatibility"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                # Initialize the database
                if init_library_db():
                    self.update_status(_("library.status.db_initialized"), "success")
                    self.connection_label.config(foreground="green")
                else:
                    self.update_status(_("library.status.db_init_failed"), "error")

                # Auth will be set up separately in setup_shared_authentication()
                pass
            else:
                self.update_status(_("library.status.standalone_mode"), "warning")
        except (sqlite3.Error, DatabaseError, OSError) as e:
            self.update_status(_("library.status.init_error").format(error=str(e)), "error")

    def setup_shared_authentication(self):
        """Setup shared authentication system - connects to global auth context"""
        try:
            # If auth was not provided in constructor, use the global auth instance
            if not self.auth:
                if SHARED_AUTH_AVAILABLE:
                    # Get the global auth instance from shared_context
                    self.auth = get_auth()
                    print(f"Library GUI connected to global auth context")
                else:
                    # Create new auth instance if shared context not available
                    self.auth = UserAuth()
                    print(f"Library GUI created standalone auth instance")

            # Set up global auth for backwards compatibility with original library
            if self.auth and ORIGINAL_LIBRARY_AVAILABLE:
                global auth
                auth = self.auth
                try:
                    set_auth(self.auth)
                except (AttributeError, TypeError):
                    pass  # Ignore if set_auth function doesn't exist

        except (ImportError, AttributeError, TypeError) as e:
            print(f"Warning: Could not setup shared authentication: {e}")
            # Create minimal fallback if needed
            if not self.auth:
                class SimpleAuth:
                    def __init__(self):
                        self.current_user = None

                    def check_permission(self, permission):
                        return True  # Allow all permissions in fallback mode

                self.auth = SimpleAuth()

        # Update user display after auth is set up
        self.update_user_display()

    def update_user_display(self):
        """Update user display based on current authentication status"""
        try:
            # Try to get current user from global context first
            current_user = None
            if SHARED_AUTH_AVAILABLE:
                current_user = get_current_user()

            # Fall back to local auth instance
            if not current_user and self.auth and hasattr(self.auth, 'current_user'):
                current_user = self.auth.current_user

            # Update the label based on user info
            if current_user:
                username = current_user.get('username', _("library.labels.unknown_user"))
                role = current_user.get('role', '')
                if role:
                    self.user_label.config(text=_("library.labels.logged_in_as_with_role").format(username=username, role=role))
                else:
                    self.user_label.config(text=_("library.labels.logged_in_as").format(username=username))
            else:
                self.user_label.config(text=_("library.labels.no_user_authenticated"))
        except (AttributeError, TypeError, tk.TclError) as e:
            print(f"Error updating user display: {e}")
            self.user_label.config(text=_("library.labels.no_user_authenticated"))

    def initialize_main_content(self):
        """Initialize main content based on auth status"""
        self.update_user_display()

        # Always show dashboard - authentication will be handled by the calling system
        self.show_dashboard()

    def refresh_user_display(self):
        """Public method to refresh user display - call this after login/logout events"""
        self.update_user_display()

    def setup_event_handlers(self):
        """Setup event handlers"""
        self.master.protocol("WM_DELETE_WINDOW", self.exit_application)

    def return_to_main_menu(self):
        """Close this window so control returns to the launcher."""
        try:
            self.master.destroy()
        except tk.TclError:
            self.master.quit()

    def update_status(self, message, status_type="info"):
        """Update the status bar"""
        self.status_label.config(text=message)

        # Color coding based on status type
        colors = {
            "info": "black",
            "success": "green",
            "warning": "orange",
            "error": "red"
        }
        self.status_label.config(foreground=colors.get(status_type, "black"))

    def clear_content_area(self):
        """Clear the content area"""
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)

    def check_permission(self, permission):
        """Check if current user has permission"""
        if not self.auth:
            return True  # Allow all if no auth system

        # For shared auth system, check if user is authenticated
        if hasattr(self.auth, 'current_user') and self.auth.current_user:
            return self.auth.check_permission(permission)

        # If auth system exists but no user logged in, show error
        messagebox.showerror(_("common.error"), _("library.messages.please_login"))
        return False

    def exit_application(self, restart=False):
        """Exit the application"""
        # Save any pending data
        try:
            if ORIGINAL_LIBRARY_AVAILABLE and hasattr(self, 'auth') and self.auth and hasattr(self, 'current_user') and self.current_user:
                log_audit_event(get_current_user_id(), "GUI: Application exit", "system")
        except (ValueError, TypeError, AttributeError):
            pass

        if restart:
            # Restart the application
            import sys
            os.execl(sys.executable, sys.executable, *sys.argv)  # nosemgrep: python.lang.security.audit.dangerous-os-exec
            if self.owns_root:
                self.master.quit()
                self.master.destroy()
            else:
                self.master.destroy()

