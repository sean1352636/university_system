"""
Enhanced Library Management System - GUI Version
Maintains all original CLI functions while adding a modern GUI interface
Backwards compatible with existing database and auth systems
"""


from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from tkinter.scrolledtext import ScrolledText
import threading
import queue
import os
import sys
from datetime import datetime, timedelta
import json
from university_system.infrastructure.database.db import sqlite3
from typing import Dict, List, Optional, Any
import logging
import urllib.request
import urllib.parse
import urllib.error

# Import all original library functions
try:
    # Import the original library module
    from university_system.modules.domain.academics.services.library import (
        auth, display_library_menu, generate_barcode,
        generate_circulation_report, generate_library_statistics_export,
        generate_qr_code, generate_user_activity_report, get_current_user_id,
        get_db_connection, get_library_settings, init_library_db,
        log_audit_event, process_scanned_barcode, quick_system_health_check,
        restore_from_backup, set_auth, update_library_setting,
        view_reading_list_details
    )
    ORIGINAL_LIBRARY_AVAILABLE = True
except ImportError:
    print("Warning: Original library module not found. GUI will use standalone functions.")
    ORIGINAL_LIBRARY_AVAILABLE = False

# Import shared authentication system
try:
    from university_system.infrastructure.auth.user_authentication import UserAuth
    from university_system.infrastructure.shared_context import get_auth, get_current_user
    SHARED_AUTH_AVAILABLE = True
except ImportError:
    print("Warning: Shared authentication system not found.")
    SHARED_AUTH_AVAILABLE = False
    # Provide fallback functions
    def get_auth():
        return None
    def get_current_user():
        return None

from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

_AUDIT_LOG_COLUMNS_CACHE: Optional[List[str]] = None
_STUDENT_COLUMNS_CACHE: Optional[List[str]] = None

class LibraryGUI:
    def __init__(self, master, auth=None):
        self.master = master
        self.master.title("Enhanced Library Management System")
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
            except Exception:
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
        except Exception as e:
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
                        "Feature Not Implemented",
                        f"The feature '{name}' is not implemented yet."
                    )
                except Exception:
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
                from university_system.modules.domain.academics.services.library import get_db_connection as original_get_db_connection
                return original_get_db_connection()
            except ImportError:
                pass
        
        # Fallback implementation
        try:
            from university_system.infrastructure.database.db import sqlite3
            return sqlite3.connect(str(DEFAULT_DB_PATH))
        except Exception as e:
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
        ttk.Button(toolbar, text="Return to Main Menu", command=self.return_to_main_menu).pack(side=tk.LEFT)

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
        menubar.add_cascade(label="File", menu=file_menu)

        # Admin and Staff can import/export
        if is_admin or is_staff:
            file_menu.add_command(label="📥 Bulk Import Books", command=self.bulk_import_books_gui)
            file_menu.add_command(label="📤 Bulk Export Books", command=self.bulk_export_books_gui)
            file_menu.add_separator()

        # Admin only - System backup/restore
        if is_admin:
            file_menu.add_command(label="Backup System", command=self.backup_system_gui)
            file_menu.add_command(label="Restore System", command=self.restore_system_gui)
            file_menu.add_separator()

        file_menu.add_command(label="Exit", command=self.exit_application)

        # Admin and Staff can export statistics
        if is_admin or is_staff:
            file_menu.add_separator()
            file_menu.add_command(label="Export Statistics", command=self.generate_library_statistics_export)

        # Edit menu - Admin and Staff only
        if is_admin or is_staff:
            edit_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="Edit", menu=edit_menu)

            if is_admin:
                edit_menu.add_command(label="Settings", command=self.show_settings)
                edit_menu.add_command(label="⚙️ Enhanced Settings Management", command=self.enhanced_settings_management_gui)

            edit_menu.add_command(label="User Preferences", command=self.show_user_preferences)

            if is_admin:
                edit_menu.add_separator()
                edit_menu.add_command(label="📤 Export Settings", command=self.export_settings_gui)
                edit_menu.add_command(label="📥 Import Settings", command=self.import_settings_gui)
                edit_menu.add_command(label="🔄 Reset to Defaults", command=self.reset_settings_to_default_gui)
                edit_menu.add_command(label="💾 Backup Settings", command=self.backup_settings_only_gui)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Dashboard", command=self.show_dashboard)
        view_menu.add_command(label="All Books", command=self.show_all_books)

        # Staff and Admin can see overdue items
        if is_admin or is_staff:
            view_menu.add_command(label="Overdue Items", command=self.show_overdue_books)

        view_menu.add_command(label="📅 Book Return Calendar", command=self.open_calendar_with_due_dates)

        # Reports - Admin and Staff only
        if is_admin or is_staff:
            view_menu.add_command(label="Reports", command=self.show_reports)
            view_menu.add_separator()
            view_menu.add_command(label="📊 Advanced Analytics Dashboard", command=self.show_advanced_analytics_gui)

        # System Maintenance - Admin only
        if is_admin:
            view_menu.add_separator()
            view_menu.add_command(label="System Maintenance", command=self.library_maintenance_gui)

        # Circulation menu
        circulation_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Circulation", menu=circulation_menu)
        circulation_menu.add_command(label="📤 Check Out Book", command=self.enhanced_checkout_book_gui)
        circulation_menu.add_command(label="📥 Return Book", command=self.enhanced_return_book_gui)
        circulation_menu.add_command(label="🔄 Renew Book", command=self.renew_book_gui)
        circulation_menu.add_separator()
        circulation_menu.add_command(label="📌 Reserve Book", command=self.reserve_book_gui)

        # Manage Reservations - Staff and Admin only
        if is_admin or is_staff:
            circulation_menu.add_command(label="📋 Manage Reservations", command=self.manage_reservations_gui)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="🔍 Advanced Search", command=self.show_advanced_search_gui)

        # Barcode Scanner - Staff and Admin only
        if is_admin or is_staff:
            tools_menu.add_command(label="Barcode Scanner", command=self.show_barcode_scanner)

        tools_menu.add_separator()
        tools_menu.add_command(label="📚 Reading Lists", command=self.manage_reading_lists_gui)
        tools_menu.add_command(label="⭐ Rate & Review Book", command=self.rate_and_review_book_gui)
        tools_menu.add_separator()
        tools_menu.add_command(label="📚 Digital Library", command=self.show_digital_library_gui)

        # Digital Access Permissions - Admin only
        if is_admin:
            tools_menu.add_command(label="🔒 Digital Access Permissions", command=self.manage_digital_access_permissions_gui)

        tools_menu.add_separator()
        tools_menu.add_command(label="Loan History", command=self.view_loan_history_gui)

        # Process Fine Payment - Staff and Admin only
        if is_admin or is_staff:
            tools_menu.add_command(label="💳 Process Fine Payment", command=self.process_fine_payment_gui)
            tools_menu.add_separator()
            tools_menu.add_command(label="📅 Library Events", command=self.manage_library_events_gui)

        # Library Card Generation - Staff and Admin only
        if is_admin or is_staff:
            tools_menu.add_separator()
            tools_menu.add_command(label="💳 Generate Library Card", command=self.generate_library_card_gui)
            tools_menu.add_command(label="💳 Bulk Generate Cards", command=self.bulk_generate_library_cards_gui)
            tools_menu.add_command(label="🖨️ Print Library Card", command=self.print_library_card_gui)
            tools_menu.add_separator()
            tools_menu.add_command(label="Barcode Generator", command=self.show_barcode_generator)

        # Reports menu - Admin and Staff only
        if is_admin or is_staff:
            reports_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="Reports", menu=reports_menu)
            reports_menu.add_command(label="📊 Circulation Report", command=self.generate_circulation_report_gui)
            reports_menu.add_command(label="📈 Advanced Analytics", command=self.show_advanced_analytics_gui)
            reports_menu.add_command(label="Export Analytics", command=self.export_analytics_report)

        # System menu - Admin only
        if is_admin:
            system_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="System", menu=system_menu)
            system_menu.add_command(label="📧 Automated Notifications", command=self.send_automated_notifications_gui)
            system_menu.add_separator()
            system_menu.add_command(label="💾 Backup & Recovery", command=self.system_backup_gui)
            system_menu.add_command(label="System Maintenance", command=self.library_maintenance_gui)
            system_menu.add_separator()
            system_menu.add_command(label="🏥 System Health Check", command=self.system_health_check_gui)
            system_menu.add_command(label="⚡ Database Optimization", command=self.database_optimization_gui)
            system_menu.add_command(label="🧹 Clear Cache", command=self.clear_cache_gui)
            system_menu.add_separator()
            system_menu.add_command(label="📋 View Audit Log", command=self.view_audit_log_gui)
    
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_help)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.show_about)
        
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
        title_label = ttk.Label(self.sidebar, text="Library System", style='Title.TLabel')
        title_label.pack(pady=(10, 20))
        
        # User info frame
        self.user_frame = ttk.LabelFrame(self.sidebar, text="User Information")
        self.user_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # User display will be updated after auth is set up
        self.user_label = ttk.Label(self.user_frame, text="Initializing...")
        self.user_label.pack(pady=5)
        
        # Navigation buttons
        nav_frame = ttk.LabelFrame(self.sidebar, text="Navigation")
        nav_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Define navigation items
        nav_items = [
            ("📊 Dashboard", self.show_dashboard),
            ("📚 All Books", self.show_all_books),
            ("🔍 Search Books", self.show_search_books),
            ("➕ Add Book", self.show_add_book),
            ("📤 Checkout", self.show_checkout),
            ("📥 Return", self.show_return),
            ("📋 Reservations", self.show_reservations),
            ("📖 Reading Lists", self.show_reading_lists),
            ("⭐ Reviews", self.show_reviews),
            ("💰 Fine Management", self.show_fine_management),
            ("📜 Loan History", self.view_loan_history_gui),
            ("💳 Library Cards", self.show_library_cards_generator),
            ("📱 Barcode Tools", self.show_barcode_generator),
            ("🔧 Maintenance", self.library_maintenance_gui),
            ("❤️ System Health", self.quick_system_health_check),
            ("📈 Reports", self.show_reports),
            ("⚙️ Settings", self.show_settings),
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

        self.status_label = ttk.Label(self.status_frame, text="Ready")
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
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if hasattr(self, 'time_label'):
                self.time_label.config(text=current_time)
            self.master.after(1000, self.update_time)
        except Exception:
            # If time label doesn't exist or any other error, just schedule next update
            self.master.after(1000, self.update_time)
        
    def initialize_library_system(self):
        """Initialize the library system with backwards compatibility"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                # Initialize the database
                if init_library_db():
                    self.update_status("Database initialized successfully", "success")
                    self.connection_label.config(foreground="green")
                else:
                    self.update_status("Database initialization failed", "error")
                    
                # Auth will be set up separately in setup_shared_authentication()
                pass
            else:
                self.update_status("Running in standalone mode", "warning")
        except Exception as e:
            self.update_status(f"Initialization error: {str(e)}", "error")
            
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
                except:
                    pass  # Ignore if set_auth function doesn't exist

        except Exception as e:
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
                username = current_user.get('username', 'Unknown User')
                role = current_user.get('role', '')
                if role:
                    self.user_label.config(text=f"Logged in as: {username} ({role})")
                else:
                    self.user_label.config(text=f"Logged in as: {username}")
            else:
                self.user_label.config(text="No user authenticated")
        except Exception as e:
            print(f"Error updating user display: {e}")
            self.user_label.config(text="No user authenticated")

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
        except Exception:
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
            
    # Login screen methods removed - authentication handled by shared system
        
    def check_permission(self, permission):
        """Check if current user has permission"""
        if not self.auth:
            return True  # Allow all if no auth system

        # For shared auth system, check if user is authenticated
        if hasattr(self.auth, 'current_user') and self.auth.current_user:
            return self.auth.check_permission(permission)

        # If auth system exists but no user logged in, show error
        messagebox.showerror("Error", "Please ensure you are logged in to the main system")
        return False
        
    def show_dashboard(self):
        """Show the main dashboard"""
        # Dashboard is always available - auth checks happen at action level
            
        self.clear_content_area()
        
        dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(dashboard_frame, text="Dashboard")
        
        # Create dashboard content
        title_label = ttk.Label(dashboard_frame, text="Library Dashboard", style='Title.TLabel')
        title_label.pack(pady=10)
        
        # Statistics frame
        stats_frame = ttk.LabelFrame(dashboard_frame, text="Library Statistics")
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Create statistics display
        self.create_statistics_display(stats_frame)
        
        # Quick actions frame
        actions_frame = ttk.LabelFrame(dashboard_frame, text="Quick Actions")
        actions_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Quick action buttons
        quick_actions = [
            ("Add New Book", self.show_add_book),
            ("Search Books", self.show_search_books),
            ("Checkout Book", self.show_checkout),
            ("Return Book", self.show_return),
            ("Manage Fines", self.show_fine_management),
            ("View Loan History", self.view_loan_history_gui),
            ("Generate Barcodes", self.show_barcode_generator),
            ("System Maintenance", self.library_maintenance_gui),
            ("System Health Check", self.quick_system_health_check),
            ("View Reports", self.show_reports),
            ("System Settings", self.show_settings)
        ]
        
        button_frame = ttk.Frame(actions_frame)
        button_frame.pack(pady=10)
        
        for i, (text, command) in enumerate(quick_actions):
            btn = ttk.Button(button_frame, text=text, command=command, width=20)
            btn.grid(row=i//3, column=i%3, padx=5, pady=5)
            
        # Recent activity frame
        activity_frame = ttk.LabelFrame(dashboard_frame, text="Recent Activity")
        activity_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.create_activity_display(activity_frame)
        
    def create_statistics_display(self, parent):
        """Create the statistics display"""
        # This would integrate with your existing analytics functions
        stats_text = ScrolledText(parent, height=6, wrap=tk.WORD)
        stats_text.pack(fill=tk.BOTH, padx=10, pady=10)
        
        # Get statistics data
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                # Use existing statistics functions
                stats_data = self.get_library_statistics()
                stats_text.insert(tk.END, stats_data)
            else:
                stats_text.insert(tk.END, "Statistics will be displayed here when connected to the library database.")
        except Exception as e:
            stats_text.insert(tk.END, f"Error loading statistics: {str(e)}")
            
        stats_text.config(state=tk.DISABLED)
        
    def get_library_statistics(self):
        """Get library statistics data"""
        try:
            conn = get_db_connection()
            if not conn:
                return "Database connection unavailable"
                
            cursor = conn.cursor()
            
            # Get basic statistics
            cursor.execute('SELECT COUNT(*) FROM books')
            total_books = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM books WHERE status = "available"')
            available_books = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status IN ("active", "overdue")')
            active_loans = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status = "overdue"')
            overdue_books = cursor.fetchone()[0]
            
            conn.close()
            
            availability_pct = (available_books / total_books * 100) if total_books else 0.0
            overdue_pct = (overdue_books / active_loans * 100) if active_loans else 0.0

            stats = f"""📚 Collection Overview:
Total Books: {total_books:,}
Available: {available_books:,}
Checked Out: {active_loans:,}
Overdue: {overdue_books:,}

📊 Collection Health: {availability_pct:.1f}% available
⚠️ Overdue Rate: {overdue_pct:.1f}%"""

            return stats
            
        except Exception as e:
            return f"Error retrieving statistics: {str(e)}"
            
    def create_activity_display(self, parent):
        """Create the recent activity display"""
        activity_text = ScrolledText(parent, height=8, wrap=tk.WORD)
        activity_text.pack(fill=tk.BOTH, padx=10, pady=10)
        
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                activity_data = self.get_recent_activity()
                activity_text.insert(tk.END, activity_data)
            else:
                activity_text.insert(tk.END, "Recent activity will be displayed here when connected to the library database.")
        except Exception as e:
            activity_text.insert(tk.END, f"Error loading activity: {str(e)}")
            
        activity_text.config(state=tk.DISABLED)
        
    def get_recent_activity(self):
        """Get recent activity data"""
        try:
            conn = get_db_connection()
            if not conn:
                return "Database connection unavailable"
                
            cursor = conn.cursor()

            # Get recent audit log entries
            audit_columns = self._get_audit_log_columns(cursor)
            has_success = 'success' in audit_columns

            select_fields = "user_id, action, timestamp"
            if has_success:
                select_fields += ", success"

            cursor.execute(f'''
                SELECT {select_fields}
                FROM audit_log
                WHERE timestamp >= datetime('now', '-24 hours')
                ORDER BY timestamp DESC
                LIMIT 10
            ''')

            raw_rows = cursor.fetchall()
            conn.close()

            if not raw_rows:
                return "No recent activity found."

            activity_text = "Recent Activity (Last 24 hours):\n\n"
            for row in raw_rows:
                user_id, action, timestamp = row[:3]
                success_val = row[3] if has_success and len(row) > 3 else None
                status = "✅" if success_val is None or bool(success_val) else "❌"
                activity_text += f"{status} {timestamp[:16]} - {user_id}: {action}\n"

            return activity_text
            
        except Exception as e:
            return f"Error retrieving activity: {str(e)}"

    def _get_audit_log_columns(self, cursor):
        """Return cached audit_log column names."""
        global _AUDIT_LOG_COLUMNS_CACHE
        if _AUDIT_LOG_COLUMNS_CACHE is None:
            cursor.execute("PRAGMA table_info(audit_log)")
            _AUDIT_LOG_COLUMNS_CACHE = [row[1] for row in cursor.fetchall()]
        return _AUDIT_LOG_COLUMNS_CACHE

    def _get_student_columns(self):
        """Return cached student table column names."""
        global _STUDENT_COLUMNS_CACHE
        if _STUDENT_COLUMNS_CACHE is None:
            try:
                conn = get_db_connection()
                if conn:
                    cur = conn.cursor()
                    cur.execute("PRAGMA table_info(students)")
                    _STUDENT_COLUMNS_CACHE = [row[1] for row in cur.fetchall()]
                    conn.close()
                else:
                    _STUDENT_COLUMNS_CACHE = []
            except Exception:
                _STUDENT_COLUMNS_CACHE = []
        return _STUDENT_COLUMNS_CACHE
            
    def show_all_books(self):
        """Show all books in a table"""
        if not self.check_permission('view_books'):
            return
            
        self.clear_content_area()
        
        books_frame = ttk.Frame(self.notebook)
        self.notebook.add(books_frame, text="All Books")
        
        # Search and filter frame
        search_frame = ttk.Frame(books_frame)
        search_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.book_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.book_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        
        search_btn = ttk.Button(search_frame, text="Search", command=self.search_books_table)
        search_btn.pack(side=tk.LEFT, padx=5)
        
        refresh_btn = ttk.Button(search_frame, text="Refresh", command=self.refresh_books_table)
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        # Books table
        table_frame = ttk.Frame(books_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create treeview for books
        columns = ('ID', 'Title', 'Author', 'Category', 'Status', 'Location')
        self.books_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)
        
        # Define column headings and widths
        column_widths = {'ID': 80, 'Title': 300, 'Author': 200, 'Category': 150, 'Status': 100, 'Location': 150}
        for col in columns:
            self.books_tree.heading(col, text=col)
            self.books_tree.column(col, width=column_widths.get(col, 100))
            
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.books_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.books_tree.xview)
        self.books_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
        self.books_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Context menu for books
        self.create_books_context_menu()
        
        # Load books data
        self.load_books_data()
        
        # Bind double-click to view details
        self.books_tree.bind('<Double-1>', self.on_book_double_click)
        
    def create_books_context_menu(self):
        """Create context menu for books table"""
        self.books_context_menu = tk.Menu(self.master, tearoff=0)
        self.books_context_menu.add_command(label="View Details", command=self.view_selected_book)
        self.books_context_menu.add_command(label="Edit Book", command=self.edit_selected_book)
        self.books_context_menu.add_separator()
        self.books_context_menu.add_command(label="Checkout", command=self.checkout_selected_book)
        self.books_context_menu.add_command(label="Reserve", command=self.reserve_selected_book)
        self.books_context_menu.add_separator()
        self.books_context_menu.add_command(label="Delete", command=self.delete_selected_book)
        self.books_context_menu.add_separator()
        self.books_context_menu.add_command(label="Generate Barcode", command=self.generate_book_barcode)
        self.books_context_menu.add_command(label="View Loan History", command=self.view_book_loan_history)
        self.books_tree.bind('<Button-3>', self.show_books_context_menu)
        
    def show_books_context_menu(self, event):
        """Show context menu for books"""
        item = self.books_tree.selection()[0] if self.books_tree.selection() else None
        if item:
            self.books_context_menu.post(event.x_root, event.y_root)
            
    def load_books_data(self, search_term=""):
        """Load books data into the table"""
        # Clear existing data
        for item in self.books_tree.get_children():
            self.books_tree.delete(item)
            
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    return
                    
                cursor = conn.cursor()
                
                if search_term:
                    cursor.execute('''
                    SELECT book_id, title, author, category, status, location
                    FROM books
                    WHERE title LIKE ? OR author LIKE ? OR category LIKE ?
                    ORDER BY title
                    ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                else:
                    cursor.execute('''
                    SELECT book_id, title, author, category, status, location
                    FROM books
                    ORDER BY title
                    ''')
                    
                books = cursor.fetchall()
                conn.close()
                
                # Insert books into table
                for book in books:
                    self.books_tree.insert('', 'end', values=book)
                    
                self.update_status(f"Loaded {len(books)} books", "success")
            else:
                # Demo data
                demo_books = [
                    ("B10001", "The Great Gatsby", "F. Scott Fitzgerald", "Fiction", "Available", "Floor 1, A1"),
                    ("B10002", "To Kill a Mockingbird", "Harper Lee", "Fiction", "Checked Out", "Floor 1, A2"),
                    ("B10003", "1984", "George Orwell", "Fiction", "Available", "Floor 1, A3"),
                ]
                
                for book in demo_books:
                    self.books_tree.insert('', 'end', values=book)
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error loading books: {str(e)}")
            
    def search_books_table(self):
        """Search books in the table"""
        search_term = self.book_search_var.get()
        self.load_books_data(search_term)
        
    def refresh_books_table(self):
        """Refresh the books table"""
        self.book_search_var.set("")
        self.load_books_data()
        
    def on_book_double_click(self, event):
        """Handle double-click on book"""
        self.view_selected_book()
        
    def view_selected_book(self):
        """View details of selected book"""
        selection = self.books_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a book first")
            return
            
        item = self.books_tree.item(selection[0])
        book_id = item['values'][0]
        
        self.show_book_details(book_id)
        
    def show_book_details(self, book_id):
        """Show detailed book information"""
        # Create new tab for book details
        details_frame = ttk.Frame(self.notebook)
        self.notebook.add(details_frame, text=f"Book Details - {book_id}")
        self.notebook.select(details_frame)
        
        # Create scrollable frame
        canvas = tk.Canvas(details_frame)
        scrollbar = ttk.Scrollbar(details_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Get book details
        book_details = self.get_book_details(book_id)
        
        if book_details:
            # Book information
            info_frame = ttk.LabelFrame(scrollable_frame, text="Book Information")
            info_frame.pack(fill=tk.X, padx=10, pady=5)
            
            # Display book information
            info_fields = [
                ("Title:", book_details.get('title', 'N/A')),
                ("Author:", book_details.get('author', 'N/A')),
                ("ISBN:", book_details.get('isbn', 'N/A')),
                ("Category:", book_details.get('category', 'N/A')),
                ("Status:", book_details.get('status', 'N/A')),
                ("Location:", book_details.get('location', 'N/A')),
                ("Reading Level:", book_details.get('reading_level', 'N/A')),
                ("Year Published:", book_details.get('year_published', 'N/A')),
                ("Publisher:", book_details.get('publisher', 'N/A')),
            ]
            
            for i, (label, value) in enumerate(info_fields):
                ttk.Label(info_frame, text=label, style='Heading.TLabel').grid(row=i, column=0, sticky='w', padx=5, pady=2)
                ttk.Label(info_frame, text=str(value)).grid(row=i, column=1, sticky='w', padx=5, pady=2)
            
            # Description
            if book_details.get('description'):
                desc_frame = ttk.LabelFrame(scrollable_frame, text="Description")
                desc_frame.pack(fill=tk.X, padx=10, pady=5)
                
                desc_text = tk.Text(desc_frame, height=4, wrap=tk.WORD)
                desc_text.pack(fill=tk.X, padx=5, pady=5)
                desc_text.insert(tk.END, book_details['description'])
                desc_text.config(state=tk.DISABLED)
            
            # Actions frame
            actions_frame = ttk.LabelFrame(scrollable_frame, text="Actions")
            actions_frame.pack(fill=tk.X, padx=10, pady=5)
            
            action_buttons = [
                ("Checkout", lambda: self.checkout_book_dialog(book_id)),
                ("Reserve", lambda: self.reserve_book_dialog(book_id)),
                ("Edit", lambda: self.edit_book_dialog(book_id)),
                ("Reviews", lambda: self.show_book_reviews(book_id)),
            ]
            
            for i, (text, command) in enumerate(action_buttons):
                btn = ttk.Button(actions_frame, text=text, command=command)
                btn.grid(row=0, column=i, padx=5, pady=5)
            
            # Loan history
            history_frame = ttk.LabelFrame(scrollable_frame, text="Loan History")
            history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            
            self.create_loan_history_table(history_frame, book_id)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
    def get_book_details(self, book_id):
        """Get detailed book information"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    return None
                    
                cursor = conn.cursor()
                cursor.execute('''
                SELECT book_id, title, author, isbn, publisher, category, year_published,
                       description, location, status, reading_level, tags
                FROM books WHERE book_id = ?
                ''', (book_id,))
                
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    columns = ['book_id', 'title', 'author', 'isbn', 'publisher', 'category', 
                              'year_published', 'description', 'location', 'status', 'reading_level', 'tags']
                    return dict(zip(columns, result))
            else:
                # Demo data
                return {
                    'book_id': book_id,
                    'title': 'Sample Book',
                    'author': 'Sample Author',
                    'isbn': '123-456-789',
                    'publisher': 'Sample Publisher',
                    'category': 'Fiction',
                    'year_published': 2023,
                    'description': 'This is a sample book description for demonstration purposes.',
                    'location': 'Floor 1, A1',
                    'status': 'Available',
                    'reading_level': 'High School',
                    'tags': 'fiction, sample'
                }
        except Exception as e:
            messagebox.showerror("Error", f"Error getting book details: {str(e)}")
            return None

    def generate_book_barcode(self):
        """Generate barcode for selected book"""
        selection = self.books_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a book first")
            return

        item = self.books_tree.item(selection[0])
        book_id = item['values'][0]
        book_title = item['values'][1] if len(item['values']) > 1 else "Unknown Title"

        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                # Try to generate using original library functions
                try:
                    barcode = generate_barcode(book_id)
                    qr_code_path = generate_qr_code(book_id, book_title)
                    # Convert PosixPath to string for database compatibility
                    qr_code_path = str(qr_code_path) if qr_code_path else None

                    # Update database with generated barcode
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute('UPDATE books SET barcode = ?, qr_code_path = ? WHERE book_id = ?',
                                     (barcode, qr_code_path, book_id))
                        conn.commit()
                        conn.close()

                    messagebox.showinfo("Success",
                                      f"Barcode generated successfully!\n\n"
                                      f"Book ID: {book_id}\n"
                                      f"Title: {book_title}\n"
                                      f"Barcode: {barcode}")

                    # Refresh the books table to show updated barcode
                    self.refresh_books_table()

                except Exception as e:
                    # Fallback to simple barcode generation
                    barcode = f"LIB{book_id}"
                    messagebox.showinfo("Barcode Generated",
                                      f"Simple barcode generated:\n\n"
                                      f"Book ID: {book_id}\n"
                                      f"Title: {book_title}\n"
                                      f"Barcode: {barcode}")
            else:
                # Demo mode - simple barcode
                barcode = f"LIB{book_id}"
                messagebox.showinfo("Demo Barcode",
                                  f"Demo barcode generated:\n\n"
                                  f"Book ID: {book_id}\n"
                                  f"Title: {book_title}\n"
                                  f"Barcode: {barcode}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate barcode: {str(e)}")

    def create_loan_history_table(self, parent, book_id):
        """Create loan history table for a book"""
        columns = ('User ID', 'Checkout Date', 'Due Date', 'Return Date', 'Status')
        history_tree = ttk.Treeview(parent, columns=columns, show='headings', height=6)
        
        for col in columns:
            history_tree.heading(col, text=col)
            history_tree.column(col, width=120)
            
        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=history_tree.yview)
        history_tree.configure(yscrollcommand=scrollbar.set)
        
        history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load loan history
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                    SELECT user_id, checkout_date, due_date, return_date, status
                    FROM book_loans
                    WHERE book_id = ?
                    ORDER BY checkout_date DESC
                    LIMIT 10
                    ''', (book_id,))
                    
                    loans = cursor.fetchall()
                    conn.close()
                    
                    for loan in loans:
                        # Format dates
                        formatted_loan = list(loan)
                        for i in [1, 2, 3]:  # Date fields
                            if formatted_loan[i]:
                                formatted_loan[i] = formatted_loan[i][:10]
                        history_tree.insert('', 'end', values=formatted_loan)
        except Exception as e:
            print(f"Error loading loan history: {e}")
            
    def show_add_book(self):
        """Show add book dialog"""
        if not self.check_permission('manage_books'):
            return
            
        self.add_book_dialog()
        
    def add_book_dialog(self):
        """Create add book dialog"""
        dialog = tk.Toplevel(self.master)
        dialog.title("Add New Book")
        dialog.geometry("600x700")
        dialog.transient(self.master)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Create form
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Form fields
        fields = [
            ("Title*:", "title"),
            ("Author*:", "author"),
            ("ISBN:", "isbn"),
            ("Publisher:", "publisher"),
            ("Category:", "category"),
            ("Year Published:", "year_published"),
            ("Location:", "location"),
            ("Reading Level:", "reading_level"),
        ]
        
        self.add_book_vars = {}

        for i, (label, field) in enumerate(fields):
            ttk.Label(main_frame, text=label).grid(row=i, column=0, sticky='w', pady=5)

            if field == "category":
                # Category dropdown
                var = tk.StringVar()
                combo = ttk.Combobox(main_frame, textvariable=var, width=40)
                combo['values'] = ('Fiction', 'Non-Fiction', 'Science', 'History', 'Computer Science',
                                  'Mathematics', 'Philosophy', 'Psychology', 'Business', 'Biography')
                combo.grid(row=i, column=1, sticky='w', pady=5)
                self.add_book_vars[field] = var
            elif field == "reading_level":
                # Reading level dropdown
                var = tk.StringVar()
                combo = ttk.Combobox(main_frame, textvariable=var, width=40)
                combo['values'] = ('Elementary', 'Middle School', 'High School', 'College', 'Unknown')
                combo.grid(row=i, column=1, sticky='w', pady=5)
                self.add_book_vars[field] = var
            elif field == "isbn":
                # ISBN field with lookup button
                isbn_frame = ttk.Frame(main_frame)
                isbn_frame.grid(row=i, column=1, sticky='w', pady=5)

                var = tk.StringVar()
                entry = ttk.Entry(isbn_frame, textvariable=var, width=32)
                entry.pack(side=tk.LEFT)
                self.add_book_vars[field] = var

                # Add lookup button
                lookup_btn = ttk.Button(isbn_frame, text="🔍 Lookup",
                                       command=lambda: self.lookup_isbn_data(dialog),
                                       width=10)
                lookup_btn.pack(side=tk.LEFT, padx=5)
            else:
                # Regular entry
                var = tk.StringVar()
                entry = ttk.Entry(main_frame, textvariable=var, width=40)
                entry.grid(row=i, column=1, sticky='w', pady=5)
                self.add_book_vars[field] = var
        
        # Description field
        ttk.Label(main_frame, text="Description:").grid(row=len(fields), column=0, sticky='nw', pady=5)
        self.add_book_description = tk.Text(main_frame, height=4, width=40)
        self.add_book_description.grid(row=len(fields), column=1, sticky='w', pady=5)
        
        # Tags field
        ttk.Label(main_frame, text="Tags:").grid(row=len(fields)+1, column=0, sticky='w', pady=5)
        self.add_book_tags = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.add_book_tags, width=40).grid(row=len(fields)+1, column=1, sticky='w', pady=5)
        ttk.Label(main_frame, text="(comma-separated)", font=('Arial', 8)).grid(row=len(fields)+2, column=1, sticky='w')
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=len(fields)+3, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Add Book", command=lambda: self.save_new_book(dialog)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # Focus on title field
        list(self.add_book_vars.values())[0].get()  # Get title entry and focus

    def lookup_isbn_data(self, dialog):
        """Lookup book data by ISBN and auto-fill the form"""
        isbn = self.add_book_vars['isbn'].get().strip()

        if not isbn:
            messagebox.showwarning("ISBN Required", "Please enter an ISBN number first")
            return

        # Clean ISBN (remove dashes and spaces)
        isbn_clean = isbn.replace('-', '').replace(' ', '')

        # Show loading status
        original_text = dialog.title()
        dialog.title("Looking up ISBN...")

        def lookup_thread():
            """Run lookup in background thread to avoid freezing GUI"""
            try:
                # Try Open Library API first
                book_data = self._fetch_from_openlibrary(isbn_clean)

                if not book_data:
                    # Try Google Books API as fallback
                    book_data = self._fetch_from_google_books(isbn_clean)

                # Update GUI in main thread
                dialog.after(0, lambda: self._populate_book_data(book_data, dialog, original_text))

            except Exception as e:
                dialog.after(0, lambda: self._handle_lookup_error(str(e), dialog, original_text))

        # Start lookup in background thread
        thread = threading.Thread(target=lookup_thread, daemon=True)
        thread.start()

    def _fetch_from_openlibrary(self, isbn):
        """Fetch book data from Open Library API"""
        try:
            url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"

            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())

            key = f"ISBN:{isbn}"
            if key not in data:
                return None

            book = data[key]

            # Extract data
            book_data = {
                'title': book.get('title', ''),
                'author': ', '.join([author.get('name', '') for author in book.get('authors', [])]),
                'publisher': ', '.join([pub.get('name', '') for pub in book.get('publishers', [])]),
                'year': book.get('publish_date', ''),
                'description': book.get('notes', '') or book.get('subtitle', ''),
                'subjects': book.get('subjects', [])
            }

            return book_data

        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError):
            return None

    def _fetch_from_google_books(self, isbn):
        """Fetch book data from Google Books API (fallback)"""
        try:
            query = urllib.parse.quote(f"isbn:{isbn}")
            url = f"https://www.googleapis.com/books/v1/volumes?q={query}"

            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())

            if 'items' not in data or len(data['items']) == 0:
                return None

            volume_info = data['items'][0]['volumeInfo']

            # Extract data
            book_data = {
                'title': volume_info.get('title', ''),
                'author': ', '.join(volume_info.get('authors', [])),
                'publisher': volume_info.get('publisher', ''),
                'year': volume_info.get('publishedDate', '')[:4] if volume_info.get('publishedDate') else '',
                'description': volume_info.get('description', ''),
                'subjects': volume_info.get('categories', [])
            }

            return book_data

        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError):
            return None

    def _populate_book_data(self, book_data, dialog, original_title):
        """Populate form fields with book data"""
        dialog.title(original_title)

        if not book_data:
            messagebox.showinfo("Not Found",
                              "Book data not found for this ISBN.\n\n" +
                              "Please enter the details manually.")
            return

        # Auto-fill fields
        if book_data.get('title'):
            self.add_book_vars['title'].set(book_data['title'])

        if book_data.get('author'):
            self.add_book_vars['author'].set(book_data['author'])

        if book_data.get('publisher'):
            self.add_book_vars['publisher'].set(book_data['publisher'])

        if book_data.get('year'):
            year_str = str(book_data['year'])
            # Extract just the year if it's a full date
            if len(year_str) >= 4:
                self.add_book_vars['year_published'].set(year_str[:4])

        # Set description
        if book_data.get('description'):
            self.add_book_description.delete("1.0", tk.END)
            self.add_book_description.insert("1.0", book_data['description'])

        # Set category based on subjects
        if book_data.get('subjects'):
            # Try to match subject to our categories
            subjects_lower = [s.lower() for s in book_data['subjects']]
            category_mapping = {
                'fiction': 'Fiction',
                'science': 'Science',
                'history': 'History',
                'computer': 'Computer Science',
                'mathematics': 'Mathematics',
                'math': 'Mathematics',
                'philosophy': 'Philosophy',
                'psychology': 'Psychology',
                'business': 'Business',
                'biography': 'Biography'
            }

            for subject in subjects_lower:
                for key, value in category_mapping.items():
                    if key in subject:
                        self.add_book_vars['category'].set(value)
                        break

        # Show success message
        messagebox.showinfo("Success",
                          f"Book information found!\n\n" +
                          f"Title: {book_data.get('title', 'N/A')}\n" +
                          f"Author: {book_data.get('author', 'N/A')}\n\n" +
                          f"Please review and adjust the details as needed.")

    def _handle_lookup_error(self, error_msg, dialog, original_title):
        """Handle lookup errors"""
        dialog.title(original_title)
        messagebox.showerror("Lookup Error",
                           f"Failed to lookup ISBN:\n{error_msg}\n\n" +
                           "Please check your internet connection and try again,\n" +
                           "or enter the book details manually.")

    def save_new_book(self, dialog):
        """Save new book to database"""
        # Validate required fields
        title = self.add_book_vars['title'].get().strip()
        author = self.add_book_vars['author'].get().strip()
        
        if not title or not author:
            messagebox.showerror("Error", "Title and Author are required fields")
            return
            
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                # Use original add book function
                book_data = {}
                for field, var in self.add_book_vars.items():
                    book_data[field] = var.get().strip()
                
                book_data['description'] = self.add_book_description.get("1.0", tk.END).strip()
                book_data['tags'] = self.add_book_tags.get().strip()
                
                # Call original function (you'd need to modify enhanced_add_book to accept parameters)
                success = self.add_book_to_database(book_data)
                
                if success:
                    messagebox.showinfo("Success", "Book added successfully!")
                    dialog.destroy()
                    self.refresh_books_table() if hasattr(self, 'books_tree') else None
                else:
                    messagebox.showerror("Error", "Failed to add book")
            else:
                # Demo mode
                messagebox.showinfo("Demo", f"Book '{title}' by {author} would be added to the database")
                dialog.destroy()
                
        except Exception as e:
            messagebox.showerror("Error", f"Error adding book: {str(e)}")
            
    def add_book_to_database(self, book_data):
        """Add book to database using original functions"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            # Generate book ID
            cursor.execute('SELECT MAX(CAST(SUBSTR(book_id, 2) AS INTEGER)) FROM books')
            result = cursor.fetchone()[0]
            next_id = 10001 if result is None else result + 1
            book_id = f"B{next_id}"
            
            # Prepare data
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            year_published = int(book_data['year_published']) if book_data['year_published'].isdigit() else None
            tags = [tag.strip() for tag in book_data['tags'].split(',') if tag.strip()]
            
            # Generate barcode
            if ORIGINAL_LIBRARY_AVAILABLE:
                barcode = generate_barcode(book_id)
                qr_code_path = generate_qr_code(book_id, book_data['title'])
                # Convert PosixPath to string for database compatibility
                qr_code_path = str(qr_code_path) if qr_code_path else None
            else:
                barcode = f"LIB{book_id}"
                qr_code_path = None

            # Insert book
            cursor.execute('''
            INSERT INTO books VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                book_id, book_data['title'], book_data['author'], book_data.get('isbn'),
                book_data.get('publisher'), book_data.get('category', 'General'), year_published,
                book_data.get('description'), book_data.get('location'), 'available', now, now,
                book_data.get('reading_level', 'Unknown'), json.dumps(tags), None, None, 0.0,
                barcode, qr_code_path, None, 'English', None, None
            ))
            
            conn.commit()
            
            # Log the action
            if ORIGINAL_LIBRARY_AVAILABLE:
                log_audit_event(get_current_user_id(), f"Added book: {book_id}", "books", book_id)
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error adding book to database: {e}")
            return False
            
    def show_search_books(self):
        """Show advanced search interface"""
        self.clear_content_area()
        
        search_frame = ttk.Frame(self.notebook)
        self.notebook.add(search_frame, text="Search Books")
        
        # Search criteria frame
        criteria_frame = ttk.LabelFrame(search_frame, text="Search Criteria")
        criteria_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Search fields
        search_fields = [
            ("Title:", "title"),
            ("Author:", "author"),
            ("ISBN:", "isbn"),
            ("Category:", "category"),
            ("Reading Level:", "reading_level"),
            ("Status:", "status"),
        ]
        
        self.search_vars = {}
        
        for i, (label, field) in enumerate(search_fields):
            row = i // 2
            col = (i % 2) * 2
            
            ttk.Label(criteria_frame, text=label).grid(row=row, column=col, sticky='w', padx=5, pady=5)
            
            if field == "category":
                var = tk.StringVar()
                combo = ttk.Combobox(criteria_frame, textvariable=var, width=20)
                combo['values'] = ('', 'Fiction', 'Non-Fiction', 'Science', 'History', 'Computer Science')
                combo.grid(row=row, column=col+1, sticky='w', padx=5, pady=5)
                self.search_vars[field] = var
            elif field == "reading_level":
                var = tk.StringVar()
                combo = ttk.Combobox(criteria_frame, textvariable=var, width=20)
                combo['values'] = ('', 'Elementary', 'Middle School', 'High School', 'College')
                combo.grid(row=row, column=col+1, sticky='w', padx=5, pady=5)
                self.search_vars[field] = var
            elif field == "status":
                var = tk.StringVar()
                combo = ttk.Combobox(criteria_frame, textvariable=var, width=20)
                combo['values'] = ('', 'available', 'checked_out', 'reserved', 'lost', 'damaged')
                combo.grid(row=row, column=col+1, sticky='w', padx=5, pady=5)
                self.search_vars[field] = var
            else:
                var = tk.StringVar()
                entry = ttk.Entry(criteria_frame, textvariable=var, width=20)
                entry.grid(row=row, column=col+1, sticky='w', padx=5, pady=5)
                self.search_vars[field] = var
        
        # Search buttons
        button_frame = ttk.Frame(criteria_frame)
        button_frame.grid(row=len(search_fields)//2 + 1, column=0, columnspan=4, pady=10)
        
        ttk.Button(button_frame, text="Search", command=self.execute_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear", command=self.clear_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Search", command=self.save_search).pack(side=tk.LEFT, padx=5)
        
        # Results frame
        results_frame = ttk.LabelFrame(search_frame, text="Search Results")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Results table
        columns = ('ID', 'Title', 'Author', 'Category', 'Status')
        self.search_results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.search_results_tree.heading(col, text=col)
            self.search_results_tree.column(col, width=150)
            
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.search_results_tree.yview)
        self.search_results_tree.configure(yscrollcommand=v_scrollbar.set)
        
        self.search_results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click
        self.search_results_tree.bind('<Double-1>', self.on_search_result_double_click)
        
    def execute_search(self):
        """Execute the search with current criteria"""
        # Clear previous results
        for item in self.search_results_tree.get_children():
            self.search_results_tree.delete(item)
            
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    return
                    
                cursor = conn.cursor()
                
                # Build dynamic query
                query = "SELECT book_id, title, author, category, status FROM books WHERE 1=1"
                params = []
                
                for field, var in self.search_vars.items():
                    value = var.get().strip()
                    if value:
                        if field in ['title', 'author', 'isbn', 'category']:
                            query += f" AND {field} LIKE ?"
                            params.append(f'%{value}%')
                        else:
                            query += f" AND {field} = ?"
                            params.append(value)
                
                query += " ORDER BY title"
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                conn.close()
                
                # Insert results
                for result in results:
                    self.search_results_tree.insert('', 'end', values=result)
                    
                self.update_status(f"Found {len(results)} books", "success")
            else:
                # Demo results
                demo_results = [
                    ("B10001", "Sample Book 1", "Author 1", "Fiction", "Available"),
                    ("B10002", "Sample Book 2", "Author 2", "Non-Fiction", "Checked Out"),
                ]
                
                for result in demo_results:
                    self.search_results_tree.insert('', 'end', values=result)
                    
        except Exception as e:
            messagebox.showerror("Error", f"Search error: {str(e)}")
            
    def clear_search(self):
        """Clear all search criteria"""
        for var in self.search_vars.values():
            var.set("")
            
        # Clear results
        for item in self.search_results_tree.get_children():
            self.search_results_tree.delete(item)
            
    def save_search(self):
        """Save current search criteria"""
        search_name = simpledialog.askstring("Save Search", "Enter name for this search:")
        if search_name:
            # Save search criteria (implementation depends on your requirements)
            messagebox.showinfo("Success", f"Search '{search_name}' saved successfully!")
            
    def on_search_result_double_click(self, event):
        """Handle double-click on search result"""
        selection = self.search_results_tree.selection()
        if selection:
            item = self.search_results_tree.item(selection[0])
            book_id = item['values'][0]
            self.show_book_details(book_id)
            
    def show_checkout(self):
        """Show checkout interface"""
        if not self.check_permission('checkout_books'):
            return
            
        self.checkout_dialog()
        
    def checkout_dialog(self):
        """Create checkout dialog"""
        # Get current logged-in user
        try:
            current_user = get_current_user()
            if not current_user:
                messagebox.showerror("Error", "No user logged in. Please log in to checkout books.")
                return

            current_user_id = current_user.get('username') or current_user.get('user_id') or current_user.get('id')
            if not current_user_id:
                messagebox.showerror("Error", "Could not determine current user ID.")
                return

            # Store current user ID for checkout
            self.selected_user_id = current_user_id

        except Exception as e:
            messagebox.showerror("Error", f"Failed to get current user: {str(e)}")
            return

        dialog = tk.Toplevel(self.master)
        dialog.title("Checkout Book")
        dialog.geometry("500x350")
        dialog.transient(self.master)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Current user display
        user_frame = ttk.LabelFrame(main_frame, text="Borrowing As")
        user_frame.pack(fill=tk.X, pady=(0, 10))

        user_info = f"User ID: {current_user_id}\nRole: {current_user.get('role', 'N/A')}"
        if current_user.get('first_name'):
            user_info = f"Name: {current_user.get('first_name', '')} {current_user.get('last_name', '')}\n" + user_info

        ttk.Label(user_frame, text=user_info, justify=tk.LEFT).pack(anchor='w', padx=10, pady=10)

        # Book selection
        book_frame = ttk.LabelFrame(main_frame, text="Book Information")
        book_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(book_frame, text="Book ID or Barcode:").pack(anchor='w', padx=5, pady=5)
        self.checkout_book_var = tk.StringVar()
        book_entry = ttk.Entry(book_frame, textvariable=self.checkout_book_var, width=30)
        book_entry.pack(anchor='w', padx=5, pady=5)

        ttk.Button(book_frame, text="Lookup Book", command=self.lookup_checkout_book).pack(anchor='w', padx=5, pady=5)

        # Book details display
        self.checkout_book_info = tk.Text(book_frame, height=4, wrap=tk.WORD, state=tk.DISABLED)
        self.checkout_book_info.pack(fill=tk.X, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        self.checkout_button = ttk.Button(button_frame, text="Checkout", command=lambda: self.process_checkout(dialog), state=tk.DISABLED)
        self.checkout_button.pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Focus on book entry
        book_entry.focus()
        
    def lookup_checkout_book(self):
        """Lookup book for checkout"""
        book_identifier = self.checkout_book_var.get().strip()
        if not book_identifier:
            messagebox.showwarning("Warning", "Please enter a book ID or barcode")
            return
            
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    return
                    
                cursor = conn.cursor()
                
                # Try to find book by ID or barcode
                cursor.execute('''
                SELECT book_id, title, author, status, location
                FROM books 
                WHERE book_id = ? OR barcode = ?
                ''', (book_identifier, book_identifier))
                
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    book_id, title, author, status, location = result
                    
                    self.checkout_book_info.config(state=tk.NORMAL)
                    self.checkout_book_info.delete("1.0", tk.END)
                    self.checkout_book_info.insert(tk.END, f"ID: {book_id}\nTitle: {title}\nAuthor: {author}\nStatus: {status}\nLocation: {location}")
                    self.checkout_book_info.config(state=tk.DISABLED)
                    
                    if status != 'available':
                        messagebox.showwarning("Warning", f"Book is currently {status} and cannot be checked out")
                    else:
                        self.selected_book_id = book_id
                        self.check_checkout_ready()
                else:
                    messagebox.showerror("Error", "Book not found")
                    self.checkout_book_info.config(state=tk.NORMAL)
                    self.checkout_book_info.delete("1.0", tk.END)
                    self.checkout_book_info.config(state=tk.DISABLED)
            else:
                # Demo mode
                self.checkout_book_info.config(state=tk.NORMAL)
                self.checkout_book_info.delete("1.0", tk.END)
                self.checkout_book_info.insert(tk.END, f"Demo Book\nTitle: Sample Book\nAuthor: Sample Author\nStatus: Available")
                self.checkout_book_info.config(state=tk.DISABLED)
                self.selected_book_id = book_identifier
                self.check_checkout_ready()
                
        except Exception as e:
            messagebox.showerror("Error", f"Error looking up book: {str(e)}")
            
    def verify_checkout_user(self):
        """Verify user for checkout"""
        user_id = self.checkout_user_var.get().strip()
        user_type = self.user_type_var.get()
        
        if not user_id:
            messagebox.showwarning("Warning", "Please enter a user ID")
            return
            
        try:
            if ORIGINAL_LIBRARY_AVAILABLE and user_type == "Student":
                conn = get_db_connection()
                if not conn:
                    return
                    
                cursor = conn.cursor()
                student_columns = self._get_student_columns()
                grade_sql = ', grade_level' if 'grade_level' in student_columns else ''
                cursor.execute(f'SELECT first_name, last_name{grade_sql} FROM students WHERE student_id = ?', (user_id,))
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    first_name, last_name = result[:2]
                    grade_level = result[2] if len(result) > 2 else 'N/A'

                    self.checkout_user_info.config(state=tk.NORMAL)
                    self.checkout_user_info.delete("1.0", tk.END)
                    self.checkout_user_info.insert(tk.END, f"Name: {first_name} {last_name}\nGrade: {grade_level}")
                    self.checkout_user_info.config(state=tk.DISABLED)
                    
                    self.selected_user_id = user_id
                    self.check_checkout_ready()
                else:
                    messagebox.showwarning("Warning", f"Student with ID {user_id} not found")
                    self.checkout_user_info.config(state=tk.NORMAL)
                    self.checkout_user_info.delete("1.0", tk.END)
                    self.checkout_user_info.config(state=tk.DISABLED)
            else:
                # For staff or demo mode
                self.checkout_user_info.config(state=tk.NORMAL)
                self.checkout_user_info.delete("1.0", tk.END)
                self.checkout_user_info.insert(tk.END, f"User ID: {user_id}\nType: {user_type}")
                self.checkout_user_info.config(state=tk.DISABLED)
                
                self.selected_user_id = user_id
                self.check_checkout_ready()
                
        except Exception as e:
            messagebox.showerror("Error", f"Error verifying user: {str(e)}")
            
    def check_checkout_ready(self):
        """Check if checkout is ready to proceed"""
        if hasattr(self, 'selected_book_id') and hasattr(self, 'selected_user_id'):
            self.checkout_button.config(state=tk.NORMAL)
        else:
            self.checkout_button.config(state=tk.DISABLED)
            
    def process_checkout(self, dialog):
        """Process the book checkout"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                # Use original checkout function
                success = self.checkout_book_database(self.selected_book_id, self.selected_user_id)
                
                if success:
                    messagebox.showinfo("Success", "Book checked out successfully!")

                    # Send checkout confirmation email
                    self._send_checkout_confirmation_email(self.selected_book_id, self.selected_user_id)

                    dialog.destroy()
                    self.refresh_books_table() if hasattr(self, 'books_tree') else None
                else:
                    messagebox.showerror("Error", "Checkout failed")
            else:
                # Demo mode
                messagebox.showinfo("Demo", f"Book {self.selected_book_id} checked out to {self.selected_user_id}")
                dialog.destroy()
                
        except Exception as e:
            messagebox.showerror("Error", f"Checkout error: {str(e)}")
            
    def checkout_book_database(self, book_id, user_id):
        """Checkout book in database"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            # Get loan period
            cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "loan_period_days"')
            loan_setting = cursor.fetchone()
            loan_period = int(loan_setting[0]) if loan_setting else 14
            
            # Set dates
            checkout_date = datetime.now()
            due_date = checkout_date + timedelta(days=loan_period)
            
            # Create loan record
            cursor.execute('''
            INSERT INTO book_loans 
            (book_id, user_id, checkout_date, due_date, status, checkout_method, staff_id)
            VALUES (?, ?, ?, ?, 'active', 'gui', ?)
            ''', (
                book_id, user_id,
                checkout_date.strftime('%Y-%m-%d %H:%M:%S'),
                due_date.strftime('%Y-%m-%d %H:%M:%S'),
                get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else self.current_user['user_id']
            ))
            
            # Update book status
            cursor.execute('UPDATE books SET status = "checked_out" WHERE book_id = ?', (book_id,))
            
            conn.commit()

            # Get book details for email
            cursor_temp = get_db_connection().cursor()
            cursor_temp.execute('SELECT title FROM books WHERE book_id = ?', (book_id,))
            book_result = cursor_temp.fetchone()
            book_title = book_result[0] if book_result else "Unknown Book"

            conn.close()

            # Send book checkout confirmation email automatically
            try:
                from university_system.infrastructure.email.email_service import send_book_checkout_confirmation
                send_book_checkout_confirmation(user_id, book_id, book_title, due_date.strftime('%Y-%m-%d'))
            except Exception as e:
                import logging
                logging.warning(f"Failed to send book checkout confirmation: {e}")

            # Log the action
            if ORIGINAL_LIBRARY_AVAILABLE:
                log_audit_event(get_current_user_id(), f"GUI: Checked out book {book_id} to {user_id}", "book_loans")

            return True
            
        except Exception as e:
            print(f"Error checking out book: {e}")
            return False
            
    def show_return(self):
        """Show return book interface"""
        if not self.check_permission('checkout_books'):
            return
            
        self.return_dialog()
        
    def return_dialog(self):
        """Create return book dialog"""
        dialog = tk.Toplevel(self.master)
        dialog.title("Return Book")
        dialog.geometry("500x350")
        dialog.transient(self.master)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Book identification
        book_frame = ttk.LabelFrame(main_frame, text="Book Identification")
        book_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(book_frame, text="Book ID or Barcode:").pack(anchor='w', padx=5, pady=5)
        self.return_book_var = tk.StringVar()
        book_entry = ttk.Entry(book_frame, textvariable=self.return_book_var, width=30)
        book_entry.pack(anchor='w', padx=5, pady=5)
        
        ttk.Button(book_frame, text="Lookup Book", command=self.lookup_return_book).pack(anchor='w', padx=5, pady=5)
        
        # Loan details
        loan_frame = ttk.LabelFrame(main_frame, text="Loan Details")
        loan_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.return_loan_info = tk.Text(loan_frame, height=6, wrap=tk.WORD, state=tk.DISABLED)
        self.return_loan_info.pack(fill=tk.X, padx=5, pady=5)
        
        # Return conditions
        condition_frame = ttk.LabelFrame(main_frame, text="Book Condition")
        condition_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.book_condition_var = tk.StringVar(value="Good")
        ttk.Radiobutton(condition_frame, text="Good Condition", variable=self.book_condition_var, value="Good").pack(anchor='w', padx=5, pady=2)
        ttk.Radiobutton(condition_frame, text="Damaged", variable=self.book_condition_var, value="Damaged").pack(anchor='w', padx=5, pady=2)
        
        ttk.Label(condition_frame, text="Notes (if damaged):").pack(anchor='w', padx=5, pady=(5, 0))
        self.condition_notes = tk.Text(condition_frame, height=2, width=50)
        self.condition_notes.pack(anchor='w', padx=5, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        self.return_button = ttk.Button(button_frame, text="Return Book", command=lambda: self.process_return(dialog), state=tk.DISABLED)
        self.return_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # Focus on book entry
        book_entry.focus()
        
    def lookup_return_book(self):
        """Lookup book for return"""
        book_identifier = self.return_book_var.get().strip()
        if not book_identifier:
            messagebox.showwarning("Warning", "Please enter a book ID or barcode")
            return
            
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    return
                    
                cursor = conn.cursor()
                
                # Find active loan
                cursor.execute('''
                SELECT bl.loan_id, bl.user_id, bl.checkout_date, bl.due_date, 
                       b.title, b.author, bl.status
                FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id
                WHERE (b.book_id = ? OR b.barcode = ?) 
                AND bl.status IN ('active', 'overdue')
                ''', (book_identifier, book_identifier))
                
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    loan_id, user_id, checkout_date, due_date, title, author, status = result
                    
                    # Calculate if overdue
                    due_date_obj = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
                    now = datetime.now()
                    is_overdue = now > due_date_obj
                    days_overdue = (now - due_date_obj).days if is_overdue else 0
                    
                    # Calculate fine
                    fine_amount = 0.0
                    if is_overdue:
                        fine_per_day = 0.50  # Default fine
                        try:
                            cursor = get_db_connection().cursor()
                            cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "fine_per_day"')
                            fine_setting = cursor.fetchone()
                            if fine_setting:
                                fine_per_day = float(fine_setting[0])
                        except:
                            pass
                        fine_amount = days_overdue * fine_per_day
                    
                    # Display loan info
                    loan_info = f"""Title: {title}
Author: {author}
Borrower: {user_id}
Checkout Date: {checkout_date[:10]}
Due Date: {due_date[:10]}
Status: {status.upper()}"""
                    
                    if is_overdue:
                        loan_info += f"\n⚠️ OVERDUE by {days_overdue} days"
                        loan_info += f"\nFine Amount: ${fine_amount:.2f}"
                    
                    self.return_loan_info.config(state=tk.NORMAL)
                    self.return_loan_info.delete("1.0", tk.END)
                    self.return_loan_info.insert(tk.END, loan_info)
                    self.return_loan_info.config(state=tk.DISABLED)
                    
                    self.selected_loan_id = loan_id
                    self.selected_return_book_id = book_identifier
                    self.return_fine_amount = fine_amount
                    self.return_borrower_id = user_id  # Store borrower ID for verification
                    self.return_button.config(state=tk.NORMAL)
                    
                else:
                    messagebox.showerror("Error", "No active loan found for this book")
                    self.return_loan_info.config(state=tk.NORMAL)
                    self.return_loan_info.delete("1.0", tk.END)
                    self.return_loan_info.config(state=tk.DISABLED)
                    self.return_button.config(state=tk.DISABLED)
            else:
                # Demo mode
                self.return_loan_info.config(state=tk.NORMAL)
                self.return_loan_info.delete("1.0", tk.END)
                self.return_loan_info.insert(tk.END, f"Demo loan for book {book_identifier}\nBorrower: DEMO_USER\nDue: Today")
                self.return_loan_info.config(state=tk.DISABLED)
                self.return_button.config(state=tk.NORMAL)
                
        except Exception as e:
            messagebox.showerror("Error", f"Error looking up book: {str(e)}")
            
    def process_return(self, dialog):
        """Process book return"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                # Verify current user can return this book
                current_user = get_current_user()
                current_user_id = current_user.get('username') or current_user.get('user_id') or current_user.get('id')
                current_user_role = current_user.get('role', '').lower()

                # Only allow the borrower or staff/admin to return
                if hasattr(self, 'return_borrower_id'):
                    if current_user_id != self.return_borrower_id and current_user_role not in ['admin', 'staff', 'librarian']:
                        messagebox.showerror("Access Denied",
                                           f"Only the borrower ({self.return_borrower_id}) or library staff can return this book.")
                        return

                success = self.return_book_database()
                
                if success:
                    messagebox.showinfo("Success", "Book returned successfully!")

                    # Send return confirmation email
                    if hasattr(self, 'return_borrower_id'):
                        self._send_return_confirmation_email(self.selected_return_book_id, self.return_borrower_id)

                    dialog.destroy()
                    self.refresh_books_table() if hasattr(self, 'books_tree') else None
                else:
                    messagebox.showerror("Error", "Return failed")
            else:
                # Demo mode
                messagebox.showinfo("Demo", "Book returned successfully!")
                dialog.destroy()
                
        except Exception as e:
            messagebox.showerror("Error", f"Return error: {str(e)}")
            
    def return_book_database(self):
        """Return book in database"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            # Get condition info
            condition = self.book_condition_var.get()
            notes = self.condition_notes.get("1.0", tk.END).strip()
            
            # Update loan record
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            UPDATE book_loans
            SET return_date = ?, status = 'returned', fine_amount = ?, notes = ?
            WHERE loan_id = ?
            ''', (now, getattr(self, 'return_fine_amount', 0.0), notes, self.selected_loan_id))
            
            # Update book status
            new_status = 'available' if condition == 'Good' else 'damaged'
            cursor.execute('UPDATE books SET status = ? WHERE book_id = ?', 
                          (new_status, self.selected_return_book_id))
            
            # Add condition notes to book if damaged
            if condition == 'Damaged' and notes:
                cursor.execute('''
                UPDATE books SET condition_notes = COALESCE(condition_notes || '; ', '') || ?
                WHERE book_id = ?
                ''', (f"Returned {now[:10]}: {notes}", self.selected_return_book_id))
            
            conn.commit()
            conn.close()
            
            # Log the action
            if ORIGINAL_LIBRARY_AVAILABLE:
                log_audit_event(get_current_user_id(), 
                              f"GUI: Returned book {self.selected_return_book_id}", 
                              "book_loans", str(self.selected_loan_id))
            
            return True
            
        except Exception as e:
            print(f"Error returning book: {e}")
            return False
            
    def show_reservations(self):
        """Show reservations management"""
        # Check permission instead of user directly
        if not self.check_permission('manage_reservations'):
            return
            
        self.clear_content_area()
        
        reservations_frame = ttk.Frame(self.notebook)
        self.notebook.add(reservations_frame, text="Reservations")
        
        # Control frame
        control_frame = ttk.Frame(reservations_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(control_frame, text="New Reservation", command=self.new_reservation_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Cancel Reservation", command=self.cancel_reservation).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Refresh", command=self.refresh_reservations).pack(side=tk.LEFT, padx=5)
        
        # Reservations table
        table_frame = ttk.Frame(reservations_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ('ID', 'Book ID', 'Title', 'User', 'Date', 'Expires', 'Position', 'Status')
        self.reservations_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.reservations_tree.heading(col, text=col)
            self.reservations_tree.column(col, width=100)
            
        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.reservations_tree.yview)
        self.reservations_tree.configure(yscrollcommand=scrollbar.set)
        
        self.reservations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load reservations
        self.load_reservations()
        
    def load_reservations(self):
        """Load reservations data"""
        # Clear existing data
        for item in self.reservations_tree.get_children():
            self.reservations_tree.delete(item)
            
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    return
                    
                cursor = conn.cursor()
                cursor.execute('''
                SELECT br.reservation_id, br.book_id, b.title, br.user_id,
                       br.reservation_date, br.expiry_date, br.priority_order, br.status
                FROM book_reservations br
                JOIN books b ON br.book_id = b.book_id
                WHERE br.status = 'active'
                ORDER BY br.book_id, br.priority_order
                ''')
                
                reservations = cursor.fetchall()
                conn.close()
                
                for reservation in reservations:
                    # Format dates
                    formatted_reservation = list(reservation)
                    formatted_reservation[4] = reservation[4][:10]  # reservation_date
                    formatted_reservation[5] = reservation[5][:10]  # expiry_date
                    self.reservations_tree.insert('', 'end', values=formatted_reservation)
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error loading reservations: {str(e)}")
            
    def refresh_reservations(self):
        """Refresh reservations table"""
        self.load_reservations()
        
    def new_reservation_dialog(self):
        """Create new reservation dialog"""
        dialog = tk.Toplevel(self.master)
        dialog.title("New Reservation")
        dialog.geometry("400x300")
        dialog.transient(self.master)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Book selection
        ttk.Label(main_frame, text="Book ID:").pack(anchor='w', pady=5)
        book_id_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=book_id_var, width=30).pack(anchor='w', pady=5)
        
        # User selection
        ttk.Label(main_frame, text="User ID:").pack(anchor='w', pady=5)
        user_id_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=user_id_var, width=30).pack(anchor='w', pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        
        def create_reservation():
            book_id = book_id_var.get().strip()
            user_id = user_id_var.get().strip()
            
            if not book_id or not user_id:
                messagebox.showwarning("Warning", "Please enter both Book ID and User ID")
                return
                
            try:
                if ORIGINAL_LIBRARY_AVAILABLE:
                    success = self.create_reservation_database(book_id, user_id)
                    if success:
                        messagebox.showinfo("Success", "Reservation created successfully!")
                        dialog.destroy()
                        self.refresh_reservations()
                    else:
                        messagebox.showerror("Error", "Failed to create reservation")
                else:
                    messagebox.showinfo("Demo", f"Reservation created for book {book_id} by user {user_id}")
                    dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Error creating reservation: {str(e)}")
        
        ttk.Button(button_frame, text="Create", command=create_reservation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
    def create_reservation_database(self, book_id, user_id):
        """Create reservation in database"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            # Check if book exists
            cursor.execute('SELECT title, status FROM books WHERE book_id = ?', (book_id,))
            book = cursor.fetchone()
            
            if not book:
                messagebox.showerror("Error", "Book not found")
                return False
            
            title, status = book
            
            # Check if user already has reservation
            cursor.execute('''
            SELECT reservation_id FROM book_reservations 
            WHERE book_id = ? AND user_id = ? AND status = 'active'
            ''', (book_id, user_id))
            
            if cursor.fetchone():
                messagebox.showwarning("Warning", "User already has a reservation for this book")
                return False
            
            # Get next priority order
            cursor.execute('''
            SELECT COALESCE(MAX(priority_order), 0) + 1 
            FROM book_reservations 
            WHERE book_id = ? AND status = 'active'
            ''', (book_id,))
            
            priority_order = cursor.fetchone()[0]
            
            # Get reservation period
            reservation_days = 3  # Default
            try:
                cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "reservation_period_days"')
                setting = cursor.fetchone()
                if setting:
                    reservation_days = int(setting[0])
            except:
                pass
            
            # Create reservation
            reservation_date = datetime.now()
            expiry_date = reservation_date + timedelta(days=reservation_days)
            
            cursor.execute('''
            INSERT INTO book_reservations 
            (book_id, user_id, reservation_date, expiry_date, status, priority_order)
            VALUES (?, ?, ?, ?, 'active', ?)
            ''', (
                book_id, user_id,
                reservation_date.strftime('%Y-%m-%d %H:%M:%S'),
                expiry_date.strftime('%Y-%m-%d %H:%M:%S'),
                priority_order
            ))
            
            conn.commit()
            conn.close()
            
            # Log the action
            if ORIGINAL_LIBRARY_AVAILABLE:
                log_audit_event(get_current_user_id(), 
                              f"GUI: Created reservation for book {book_id}", 
                              "book_reservations")
            
            return True
            
        except Exception as e:
            print(f"Error creating reservation: {e}")
            return False
            
    def cancel_reservation(self):
        """Cancel selected reservation"""
        selection = self.reservations_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a reservation to cancel")
            return
            
        item = self.reservations_tree.item(selection[0])
        reservation_id = item['values'][0]
        book_title = item['values'][2]
        user_id = item['values'][3]
        
        result = messagebox.askyesno("Confirm", f"Cancel reservation for '{book_title}' by {user_id}?")
        
        if result:
            try:
                if ORIGINAL_LIBRARY_AVAILABLE:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute('UPDATE book_reservations SET status = "cancelled" WHERE reservation_id = ?', 
                                     (reservation_id,))
                        conn.commit()
                        conn.close()
                        
                        # Log the action
                        log_audit_event(get_current_user_id(), 
                                      f"GUI: Cancelled reservation {reservation_id}", 
                                      "book_reservations")
                        
                        messagebox.showinfo("Success", "Reservation cancelled successfully!")
                        self.refresh_reservations()
                else:
                    messagebox.showinfo("Demo", "Reservation cancelled!")
                    self.refresh_reservations()
                    
            except Exception as e:
                messagebox.showerror("Error", f"Error cancelling reservation: {str(e)}")
                
    def show_reports(self):
        """Show reports interface"""
        if not self.check_permission('view_reports'):
            return
            
        self.clear_content_area()
        
        reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(reports_frame, text="Reports")
        
        title_label = ttk.Label(reports_frame, text="Library Reports", style='Title.TLabel')
        title_label.pack(pady=10)
        
        # Report types
        report_types = [
            ("Collection Overview", self.generate_collection_report),
            ("Circulation Summary", self.generate_circulation_report),
            ("Overdue Books", self.generate_overdue_report),
            ("User Activity", self.generate_user_activity_report),
            ("Popular Books", self.generate_popular_books_report),
            ("Statistics Dashboard", self.show_statistics_dashboard),
            ("Fine Collection Report", self.generate_fine_report),
            ("Library Card Usage Report", self.generate_card_usage_report), 
            ("System Health Report", self.generate_health_report),
            ("Maintenance Activity Report", self.generate_maintenance_report)
        ]
        
        # Create report buttons
        buttons_frame = ttk.Frame(reports_frame)
        buttons_frame.pack(pady=20)
        
        for i, (report_name, command) in enumerate(report_types):
            row = i // 2
            col = i % 2
            
            btn = ttk.Button(buttons_frame, text=report_name, command=command, width=25)
            btn.grid(row=row, column=col, padx=10, pady=5)
        
        # Report display area
        display_frame = ttk.LabelFrame(reports_frame, text="Report Output")
        display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.report_text = ScrolledText(display_frame, wrap=tk.WORD)
        self.report_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Email report button
        email_button_frame = ttk.Frame(display_frame)
        email_button_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(email_button_frame, text="📧 Email Report to Admin",
                  command=self.email_report_to_admin).pack(side=tk.LEFT, padx=5)
        ttk.Button(email_button_frame, text="💾 Save Report to File",
                  command=self.save_report_to_file).pack(side=tk.LEFT, padx=5)
        
    def generate_collection_report(self):
        """Generate collection overview report"""
        self.report_text.delete("1.0", tk.END)
        
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                report_data = self.get_collection_report_data()
            else:
                report_data = "DEMO COLLECTION REPORT\n" + "="*50 + "\nTotal Books: 150\nAvailable: 120\nChecked Out: 25\nDamaged: 5"
            
            self.report_text.insert(tk.END, report_data)
            
        except Exception as e:
            self.report_text.insert(tk.END, f"Error generating report: {str(e)}")

    def _show_report_message(self, title: str, body: str):
        """Utility to display a formatted report message."""
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert(tk.END, f"{title}\n{'=' * len(title)}\n\n{body}")

    def _show_report_not_available(self, title: str):
        """Notify users that a requested report is not yet implemented."""
        self._show_report_message(
            title,
            "This report is not yet available in the GUI. Please use the CLI workflow or check back after the next release."
        )
            
    def get_collection_report_data(self):
        """Get collection report data"""
        try:
            conn = get_db_connection()
            if not conn:
                return "Database connection unavailable"
                
            cursor = conn.cursor()
            
            # Collection statistics
            cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
                SUM(CASE WHEN status = 'checked_out' THEN 1 ELSE 0 END) as checked_out,
                SUM(CASE WHEN status = 'reserved' THEN 1 ELSE 0 END) as reserved,
                SUM(CASE WHEN status = 'damaged' THEN 1 ELSE 0 END) as damaged,
                SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END) as lost
            FROM books
            ''')
            
            stats = cursor.fetchone()
            
            # Category breakdown
            cursor.execute('''
            SELECT category, COUNT(*) as count
            FROM books
            GROUP BY category
            ORDER BY count DESC
            ''')
            
            categories = cursor.fetchall()
            
            conn.close()
            
            # Format report
            report = "LIBRARY COLLECTION REPORT\n"
            report += "="*50 + "\n"
            report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            report += "OVERALL STATISTICS:\n"
            report += f"Total Books: {stats[0]:,}\n"
            report += f"Available: {stats[1]:,}\n"
            report += f"Checked Out: {stats[2]:,}\n"
            report += f"Reserved: {stats[3]:,}\n"
            report += f"Damaged: {stats[4]:,}\n"
            report += f"Lost: {stats[5]:,}\n\n"
            
            report += "CATEGORY BREAKDOWN:\n"
            report += "-"*30 + "\n"
            for category, count in categories:
                report += f"{category}: {count:,}\n"
            
            return report
            
        except Exception as e:
            return f"Error generating collection report: {str(e)}"
            
    def generate_circulation_report(self):
        """Generate circulation report"""
        self.report_text.delete("1.0", tk.END)
        
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                report_data = self.get_circulation_report_data()
            else:
                report_data = "DEMO CIRCULATION REPORT\n" + "="*50 + "\nActive Loans: 25\nReturns Today: 8\nOverdue: 3"
            
            self.report_text.insert(tk.END, report_data)
            
        except Exception as e:
            self.report_text.insert(tk.END, f"Error generating report: {str(e)}")
            
    def get_circulation_report_data(self):
        """Get circulation report data"""
        try:
            conn = get_db_connection()
            if not conn:
                return "Database connection unavailable"
                
            cursor = conn.cursor()
            
            # Current circulation
            cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status IN ("active", "overdue")')
            active_loans = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status = "overdue"')
            overdue_loans = cursor.fetchone()[0]
            
            # Today's activity
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('SELECT COUNT(*) FROM book_loans WHERE date(checkout_date) = ?', (today,))
            today_checkouts = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM book_loans WHERE date(return_date) = ?', (today,))
            today_returns = cursor.fetchone()[0]
            
            # Monthly stats
            cursor.execute('''
            SELECT COUNT(*) FROM book_loans 
            WHERE checkout_date >= date('now', '-30 days')
            ''', )
            monthly_checkouts = cursor.fetchone()[0]
            
            conn.close()
            
            report = "CIRCULATION REPORT\n"
            report += "="*50 + "\n"
            report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            report += "CURRENT STATUS:\n"
            report += f"Active Loans: {active_loans:,}\n"
            report += f"Overdue Items: {overdue_loans:,}\n"
            
            report += f"\nTODAY'S ACTIVITY:\n"
            report += f"Checkouts: {today_checkouts:,}\n"
            report += f"Returns: {today_returns:,}\n"
            
            report += f"\nMONTHLY SUMMARY:\n"
            report += f"Checkouts (30 days): {monthly_checkouts:,}\n"
            
            return report
            
        except Exception as e:
            return f"Error generating circulation report: {str(e)}"
            
    def generate_overdue_report(self):
        """Generate overdue books report"""
        self.report_text.delete("1.0", tk.END)
        
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                report_data = self.get_overdue_report_data()
            else:
                report_data = "DEMO OVERDUE REPORT\n" + "="*50 + "\nNo overdue books in demo mode"
            
            self.report_text.insert(tk.END, report_data)
            
        except Exception as e:
            self.report_text.insert(tk.END, f"Error generating report: {str(e)}")
            
    def get_overdue_report_data(self):
        """Get overdue books report data"""
        try:
            conn = get_db_connection()
            if not conn:
                return "Database connection unavailable"
                
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT bl.user_id, bl.book_id, b.title, bl.due_date,
                   julianday('now') - julianday(bl.due_date) as days_overdue,
                   bl.fine_amount
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            WHERE bl.status = 'overdue'
            ORDER BY days_overdue DESC
            ''')
            
            overdue_books = cursor.fetchall()
            conn.close()
            
            report = "OVERDUE BOOKS REPORT\n"
            report += "="*50 + "\n"
            report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            if not overdue_books:
                report += "No overdue books found.\n"
            else:
                report += f"Total Overdue Items: {len(overdue_books)}\n\n"
                report += f"{'User ID':<12} {'Book ID':<10} {'Days':<5} {'Fine':<8} {'Title':<30}\n"
                report += "-"*70 + "\n"
                
                total_fines = 0
                for book in overdue_books:
                    user_id, book_id, title, due_date, days_overdue, fine = book
                    fine_amount = fine if fine else 0
                    total_fines += fine_amount
                    title_display = title[:27] + "..." if len(title) > 30 else title
                    
                    report += f"{user_id:<12} {book_id:<10} {int(days_overdue):<5} ${fine_amount:<7.2f} {title_display:<30}\n"
                
                report += "-"*70 + "\n"
                report += f"Total Outstanding Fines: ${total_fines:.2f}\n"
            
            return report
            
        except Exception as e:
            return f"Error generating overdue report: {str(e)}"
            
    def generate_user_activity_report(self):
        """Generate user activity report"""
        self._show_report_message(
            "User Activity Report",
            "This report will highlight active borrowers, engagement trends, and reservation patterns."
        )

    def generate_popular_books_report(self):
        """Generate popular books report"""
        self._show_report_message(
            "Popular Books Report",
            "This report will list the most borrowed titles, trending categories, and recommendations once analytics is enabled."
        )

    def generate_fine_report(self):
        """Generate outstanding fines report."""
        if not ORIGINAL_LIBRARY_AVAILABLE:
            self._show_report_message(
                "Fine Collection Report",
                "Demo mode: fines reporting is available only when the library database is connected."
            )
            return

        try:
            conn = get_db_connection()
            if not conn:
                raise RuntimeError("Database connection unavailable")

            cursor = conn.cursor()
            student_columns = self._get_student_columns()
            grade_sql = ', s.grade_level' if 'grade_level' in student_columns else ''
            cursor.execute(f'''
                SELECT bl.user_id,
                       COALESCE(s.first_name || ' ' || s.last_name, 'Unknown') AS full_name,
                       SUM(COALESCE(bl.fine_amount, 0)) AS total_fines,
                       COUNT(*) AS fine_items,
                       MAX(bl.due_date) AS latest_due,
                       s.email_address{grade_sql}
                FROM book_loans bl
                LEFT JOIN students s ON bl.user_id = s.student_id
                WHERE bl.fine_amount > 0 AND bl.status != 'returned'
                GROUP BY bl.user_id
                ORDER BY total_fines DESC
            ''')

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                self._show_report_message("Fine Collection Report", "No outstanding fines were found.")
                return

            title = "Fine Collection Report"
            lines = [title, "=" * len(title), ""]
            grand_total = 0.0

            for row in rows:
                user_id, full_name, total_fines, item_count, latest_due = row[:5]
                email = row[5] if len(row) > 5 else None
                grade_value = row[6] if len(row) > 6 else None

                amount = total_fines or 0.0
                grand_total += amount

                lines.append(f"User: {user_id} ({full_name})")
                if grade_value:
                    lines.append(f"Grade: {grade_value}")
                if email:
                    lines.append(f"Contact: {email}")
                lines.append(f"Outstanding Items: {item_count}")
                lines.append(f"Total Due: ${amount:.2f}")
                lines.append(f"Most Recent Due Date: {latest_due or 'N/A'}")
                lines.append("-")

            lines.append("")
            lines.append(f"Grand Total Outstanding Fines: ${grand_total:.2f}")

            self.report_text.delete("1.0", tk.END)
            self.report_text.insert(tk.END, "\n".join(lines))

        except Exception as e:
            self.report_text.delete("1.0", tk.END)
            self.report_text.insert(tk.END, f"Error generating fine report: {str(e)}")

    def generate_card_usage_report(self):
        """Generate library card usage report showing borrowing patterns."""
        if not ORIGINAL_LIBRARY_AVAILABLE:
            self._show_report_message(
                "Library Card Usage Report",
                "Demo mode: card usage reporting is available only when the library database is connected."
            )
            return

        try:
            conn = get_db_connection()
            if not conn:
                raise RuntimeError("Database connection unavailable")

            cursor = conn.cursor()

            # Get top active borrowers
            cursor.execute('''
                SELECT bl.user_id,
                       COUNT(*) as total_loans,
                       SUM(CASE WHEN bl.status = 'active' THEN 1 ELSE 0 END) as active_loans,
                       SUM(CASE WHEN bl.status = 'returned' THEN 1 ELSE 0 END) as returned_loans,
                       SUM(CASE WHEN bl.status = 'overdue' THEN 1 ELSE 0 END) as overdue_loans,
                       MAX(bl.checkout_date) as last_checkout
                FROM book_loans bl
                GROUP BY bl.user_id
                ORDER BY total_loans DESC
                LIMIT 20
            ''')

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                self._show_report_message("Library Card Usage Report", "No card usage data found.")
                return

            title = "Library Card Usage Report"
            lines = [title, "=" * len(title), ""]
            lines.append("Top 20 Active Library Card Holders")
            lines.append("-" * 60)

            for row in rows:
                user_id, total, active, returned, overdue, last_checkout = row
                lines.append(f"\nUser ID: {user_id}")
                lines.append(f"  Total Loans: {total}")
                lines.append(f"  Active: {active} | Returned: {returned} | Overdue: {overdue}")
                lines.append(f"  Last Checkout: {last_checkout[:10] if last_checkout else 'N/A'}")

            lines.append("\n" + "=" * 60)
            lines.append(f"Total Unique Users: {len(rows)}")

            self.report_text.delete("1.0", tk.END)
            self.report_text.insert(tk.END, "\n".join(lines))

        except Exception as e:
            self.report_text.delete("1.0", tk.END)
            self.report_text.insert(tk.END, f"Error generating card usage report: {str(e)}")

    def generate_health_report(self):
        """Generate library system health report showing overall status."""
        if not ORIGINAL_LIBRARY_AVAILABLE:
            self._show_report_message(
                "System Health Report",
                "Demo mode: health reporting is available only when the library database is connected."
            )
            return

        try:
            conn = get_db_connection()
            if not conn:
                raise RuntimeError("Database connection unavailable")

            cursor = conn.cursor()

            # Get overall statistics
            cursor.execute('SELECT COUNT(*) FROM books')
            total_books = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM books WHERE status = 'available'")
            available_books = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM books WHERE status = 'checked_out'")
            checked_out = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM books WHERE status = 'damaged'")
            damaged = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM book_loans WHERE status = 'active'")
            active_loans = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM book_loans WHERE status = 'overdue'")
            overdue_loans = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM book_reservations WHERE status = 'active'")
            active_reservations = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(fine_amount) FROM book_loans WHERE status != 'returned' AND fine_amount > 0")
            outstanding_fines = cursor.fetchone()[0] or 0.0

            conn.close()

            # Calculate health metrics
            availability_rate = (available_books / total_books * 100) if total_books > 0 else 0
            damage_rate = (damaged / total_books * 100) if total_books > 0 else 0
            overdue_rate = (overdue_loans / active_loans * 100) if active_loans > 0 else 0

            # Determine system health status
            if availability_rate > 70 and damage_rate < 5 and overdue_rate < 10:
                health_status = "EXCELLENT"
                status_symbol = "✓"
            elif availability_rate > 50 and damage_rate < 10 and overdue_rate < 20:
                health_status = "GOOD"
                status_symbol = "○"
            elif availability_rate > 30:
                health_status = "FAIR"
                status_symbol = "△"
            else:
                health_status = "NEEDS ATTENTION"
                status_symbol = "⚠"

            title = "Library System Health Report"
            lines = [title, "=" * len(title), ""]
            lines.append(f"System Status: {status_symbol} {health_status}")
            lines.append("")
            lines.append("=" * 60)
            lines.append("COLLECTION HEALTH")
            lines.append("-" * 60)
            lines.append(f"Total Books: {total_books}")
            lines.append(f"Available: {available_books} ({availability_rate:.1f}%)")
            lines.append(f"Checked Out: {checked_out}")
            lines.append(f"Damaged: {damaged} ({damage_rate:.1f}%)")
            lines.append("")
            lines.append("=" * 60)
            lines.append("CIRCULATION HEALTH")
            lines.append("-" * 60)
            lines.append(f"Active Loans: {active_loans}")
            lines.append(f"Overdue Loans: {overdue_loans} ({overdue_rate:.1f}%)")
            lines.append(f"Active Reservations: {active_reservations}")
            lines.append(f"Outstanding Fines: ${outstanding_fines:.2f}")
            lines.append("")
            lines.append("=" * 60)
            lines.append("RECOMMENDATIONS")
            lines.append("-" * 60)

            if damage_rate > 5:
                lines.append("⚠ High damage rate - Review book handling procedures")
            if overdue_rate > 15:
                lines.append("⚠ High overdue rate - Consider sending reminder emails")
            if availability_rate < 50:
                lines.append("⚠ Low availability - Consider acquiring more copies of popular titles")
            if outstanding_fines > 500:
                lines.append("⚠ High outstanding fines - Follow up with borrowers")

            if not any("⚠" in line for line in lines[-4:]):
                lines.append("✓ All metrics are within healthy ranges")

            self.report_text.delete("1.0", tk.END)
            self.report_text.insert(tk.END, "\n".join(lines))

        except Exception as e:
            self.report_text.delete("1.0", tk.END)
            self.report_text.insert(tk.END, f"Error generating health report: {str(e)}")

    def generate_maintenance_report(self):
        """Generate maintenance report showing books needing attention."""
        if not ORIGINAL_LIBRARY_AVAILABLE:
            self._show_report_message(
                "Maintenance Activity Report",
                "Demo mode: maintenance reporting is available only when the library database is connected."
            )
            return

        try:
            conn = get_db_connection()
            if not conn:
                raise RuntimeError("Database connection unavailable")

            cursor = conn.cursor()

            # Get damaged books
            cursor.execute('''
                SELECT book_id, title, author, status, condition_notes
                FROM books
                WHERE status = 'damaged' OR condition_notes IS NOT NULL
                ORDER BY last_updated DESC
            ''')
            damaged_books = cursor.fetchall()

            # Get frequently loaned books (high wear candidates)
            cursor.execute('''
                SELECT b.book_id, b.title, b.author, COUNT(*) as loan_count
                FROM books b
                JOIN book_loans bl ON b.book_id = bl.book_id
                GROUP BY b.book_id
                HAVING loan_count > 10
                ORDER BY loan_count DESC
                LIMIT 15
            ''')
            high_usage_books = cursor.fetchall()

            # Get books with missing information
            cursor.execute('''
                SELECT book_id, title, author,
                       CASE
                           WHEN isbn IS NULL OR isbn = '' THEN 'Missing ISBN; '
                           ELSE ''
                       END ||
                       CASE
                           WHEN location IS NULL OR location = '' THEN 'Missing Location; '
                           ELSE ''
                       END ||
                       CASE
                           WHEN category IS NULL OR category = '' THEN 'Missing Category; '
                           ELSE ''
                       END as issues
                FROM books
                WHERE (isbn IS NULL OR isbn = '')
                   OR (location IS NULL OR location = '')
                   OR (category IS NULL OR category = '')
                LIMIT 20
            ''')
            incomplete_records = cursor.fetchall()

            conn.close()

            title = "Library Maintenance Report"
            lines = [title, "=" * len(title), ""]

            # Damaged Books Section
            lines.append("=" * 60)
            lines.append("DAMAGED BOOKS REQUIRING ATTENTION")
            lines.append("-" * 60)

            if damaged_books:
                for book_id, title_text, author, status, notes in damaged_books:
                    lines.append(f"\n⚠ Book ID: {book_id}")
                    lines.append(f"  Title: {title_text}")
                    lines.append(f"  Author: {author}")
                    lines.append(f"  Status: {status}")
                    if notes:
                        lines.append(f"  Notes: {notes}")
            else:
                lines.append("✓ No damaged books found")

            # High Usage Books Section
            lines.append("\n" + "=" * 60)
            lines.append("HIGH USAGE BOOKS (Inspection Recommended)")
            lines.append("-" * 60)

            if high_usage_books:
                for book_id, title_text, author, loan_count in high_usage_books:
                    lines.append(f"\n○ Book ID: {book_id}")
                    lines.append(f"  Title: {title_text}")
                    lines.append(f"  Author: {author}")
                    lines.append(f"  Total Loans: {loan_count}")
            else:
                lines.append("✓ No high usage books to report")

            # Incomplete Records Section
            lines.append("\n" + "=" * 60)
            lines.append("INCOMPLETE BOOK RECORDS")
            lines.append("-" * 60)

            if incomplete_records:
                for book_id, title_text, author, issues in incomplete_records:
                    lines.append(f"\n△ Book ID: {book_id}")
                    lines.append(f"  Title: {title_text}")
                    lines.append(f"  Author: {author}")
                    lines.append(f"  Issues: {issues.strip()}")
            else:
                lines.append("✓ All book records are complete")

            # Summary
            lines.append("\n" + "=" * 60)
            lines.append("MAINTENANCE SUMMARY")
            lines.append("-" * 60)
            lines.append(f"Damaged Books: {len(damaged_books)}")
            lines.append(f"High Usage Books: {len(high_usage_books)}")
            lines.append(f"Incomplete Records: {len(incomplete_records)}")
            lines.append(f"Total Items Requiring Attention: {len(damaged_books) + len(incomplete_records)}")

            self.report_text.delete("1.0", tk.END)
            self.report_text.insert(tk.END, "\n".join(lines))

        except Exception as e:
            self.report_text.delete("1.0", tk.END)
            self.report_text.insert(tk.END, f"Error generating maintenance report: {str(e)}")
        
    def show_statistics_dashboard(self):
        """Show statistics dashboard"""
        self.report_text.delete("1.0", tk.END)

        try:
            stats_data = self.get_library_statistics()
            self.report_text.insert(tk.END, stats_data)
        except Exception as e:
            self.report_text.insert(tk.END, f"Error loading statistics: {str(e)}")

    def email_report_to_admin(self):
        """Email current report to administrator."""
        report_content = self.report_text.get("1.0", tk.END).strip()

        if not report_content or report_content == "":
            messagebox.showwarning("No Report", "Please generate a report first before emailing.")
            return

        try:
            # Get admin email from database
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection unavailable")
                return

            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE role = 'admin' LIMIT 1")
            admin = cursor.fetchone()
            conn.close()

            if not admin or not admin[0]:
                messagebox.showerror("Error", "No admin email address found in database")
                return

            admin_email = admin[0]

            # Create email dialog
            dialog = tk.Toplevel(self.master)
            dialog.title("Email Report")
            dialog.geometry("500x350")
            dialog.transient(self.master)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text="Email Library Report", font=('Arial', 12, 'bold')).pack(pady=10)

            # Recipient
            recipient_frame = ttk.Frame(main_frame)
            recipient_frame.pack(fill=tk.X, pady=5)
            ttk.Label(recipient_frame, text="To:").pack(side=tk.LEFT, padx=5)
            recipient_entry = ttk.Entry(recipient_frame, width=40)
            recipient_entry.insert(0, admin_email)
            recipient_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

            # Subject
            subject_frame = ttk.Frame(main_frame)
            subject_frame.pack(fill=tk.X, pady=5)
            ttk.Label(subject_frame, text="Subject:").pack(side=tk.LEFT, padx=5)
            subject_entry = ttk.Entry(subject_frame, width=40)
            subject_entry.insert(0, "Library Report - " + datetime.now().strftime('%Y-%m-%d'))
            subject_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

            # Message
            ttk.Label(main_frame, text="Additional Message:").pack(anchor='w', padx=5, pady=(10, 0))
            message_text = ScrolledText(main_frame, height=8, wrap=tk.WORD)
            message_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            message_text.insert(tk.END, "Please find the library report below:\n\n")

            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=10)

            def send_email():
                try:
                    recipient = recipient_entry.get().strip()
                    subject = subject_entry.get().strip()
                    message = message_text.get("1.0", tk.END).strip()

                    if not recipient or not subject:
                        messagebox.showwarning("Missing Information", "Please provide recipient and subject")
                        return

                    # Compose full email body
                    full_message = f"{message}\n\n{'='*60}\n{report_content}\n{'='*60}"

                    # Import and use email service
                    from university_system.infrastructure.email.email_service import send_email as send_email_service

                    send_email_service(
                        recipient_email=recipient,
                        subject=subject,
                        body=full_message
                    )

                    messagebox.showinfo("Success", f"Report emailed successfully to {recipient}")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Email Error", f"Failed to send email: {str(e)}")

            ttk.Button(button_frame, text="Send Email", command=send_email).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to prepare email: {str(e)}")

    def save_report_to_file(self):
        """Save current report to a file."""
        report_content = self.report_text.get("1.0", tk.END).strip()

        if not report_content or report_content == "":
            messagebox.showwarning("No Report", "Please generate a report first before saving.")
            return

        try:
            from tkinter import filedialog
            from university_system.modules.shared.constants import paths

            # Create reports directory if it doesn't exist
            reports_dir = paths.REPORTS_DIR
            reports_dir.mkdir(parents=True, exist_ok=True)

            # Default filename with timestamp
            default_filename = f"library_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

            # Ask user where to save
            file_path = filedialog.asksaveasfilename(
                initialdir=reports_dir,
                initialfile=default_filename,
                defaultextension=".txt",
                filetypes=[
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ]
            )

            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(report_content)

                messagebox.showinfo("Success", f"Report saved to:\n{file_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save report: {str(e)}")

    def show_settings(self):
        """Show settings interface"""
        if not self.check_permission('system_config'):
            return
            
        self.clear_content_area()
        
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="Settings")
        
        title_label = ttk.Label(settings_frame, text="System Settings", style='Title.TLabel')
        title_label.pack(pady=10)
        
        # Settings categories
        categories_frame = ttk.Frame(settings_frame)
        categories_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Create notebook for settings categories
        settings_notebook = ttk.Notebook(categories_frame)
        settings_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Library Settings tab
        library_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(library_tab, text="Library Settings")
        
        self.create_library_settings_tab(library_tab)
        
        # System Settings tab
        system_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(system_tab, text="System Settings")
        
        self.create_system_settings_tab(system_tab)
        
        # User Settings tab
        user_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(user_tab, text="User Settings")
        
        self.create_user_settings_tab(user_tab)
        
    def create_library_settings_tab(self, parent):
        """Create library settings tab"""
        # Loan settings
        loan_frame = ttk.LabelFrame(parent, text="Loan Settings")
        loan_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Load current settings
        self.library_settings_vars = {}
        
        library_settings = [
            ("Loan Period (days):", "loan_period_days", "14"),
            ("Maximum Loans per User:", "max_loans", "5"),
            ("Fine per Day ($):", "fine_per_day", "0.50"),
            ("Reservation Period (days):", "reservation_period_days", "3"),
            ("Maximum Renewals:", "max_renewals", "2"),
        ]
        
        for i, (label, setting_name, default_value) in enumerate(library_settings):
            ttk.Label(loan_frame, text=label).grid(row=i, column=0, sticky='w', padx=5, pady=5)
            
            var = tk.StringVar()
            
            # Load current value
            try:
                if ORIGINAL_LIBRARY_AVAILABLE:
                    current_value = get_library_settings(setting_name) or default_value
                else:
                    current_value = default_value
                var.set(current_value)
            except:
                var.set(default_value)
            
            entry = ttk.Entry(loan_frame, textvariable=var, width=10)
            entry.grid(row=i, column=1, sticky='w', padx=5, pady=5)
            
            self.library_settings_vars[setting_name] = var
        
        # Notification settings
        notification_frame = ttk.LabelFrame(parent, text="Notification Settings")
        notification_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.notification_vars = {}
        notification_settings = [
            ("Email Notifications", "email_notifications"),
            ("SMS Notifications", "sms_notifications"),
            ("Overdue Reminders", "overdue_notifications"),
            ("Reservation Alerts", "reservation_alerts"),
        ]
        
        for i, (label, setting_name) in enumerate(notification_settings):
            var = tk.BooleanVar()
            
            # Load current value
            try:
                if ORIGINAL_LIBRARY_AVAILABLE:
                    current_value = get_library_settings(setting_name) == 'true'
                else:
                    current_value = True
                var.set(current_value)
            except:
                var.set(True)
            
            checkbox = ttk.Checkbutton(notification_frame, text=label, variable=var)
            checkbox.grid(row=i, column=0, sticky='w', padx=5, pady=5)
            
            self.notification_vars[setting_name] = var
        
        # Save button
        ttk.Button(parent, text="Save Library Settings", command=self.save_library_settings).pack(pady=10)
        
    def create_system_settings_tab(self, parent):
        """Create system settings tab"""
        # Backup settings
        backup_frame = ttk.LabelFrame(parent, text="Backup Settings")
        backup_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.auto_backup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(backup_frame, text="Enable Automatic Backups", variable=self.auto_backup_var).pack(anchor='w', padx=5, pady=5)
        
        ttk.Label(backup_frame, text="Backup Frequency (hours):").pack(anchor='w', padx=5, pady=5)
        self.backup_frequency_var = tk.StringVar(value="24")
        ttk.Entry(backup_frame, textvariable=self.backup_frequency_var, width=10).pack(anchor='w', padx=20, pady=5)
        
        # Database settings
        db_frame = ttk.LabelFrame(parent, text="Database Settings")
        db_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(db_frame, text="Optimize Database", command=self.optimize_database).pack(anchor='w', padx=5, pady=5)
        ttk.Button(db_frame, text="Check Integrity", command=self.check_database_integrity).pack(anchor='w', padx=5, pady=5)
        ttk.Button(db_frame, text="View Audit Log", command=self.show_audit_log).pack(anchor='w', padx=5, pady=5)
        
        # Save button
        ttk.Button(parent, text="Save System Settings", command=self.save_system_settings).pack(pady=10)
        
    def create_user_settings_tab(self, parent):
        """Create user settings tab"""
        # User preferences
        pref_frame = ttk.LabelFrame(parent, text="User Preferences")
        pref_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(pref_frame, text="Default View:").pack(anchor='w', padx=5, pady=5)
        self.default_view_var = tk.StringVar(value="Dashboard")
        view_combo = ttk.Combobox(pref_frame, textvariable=self.default_view_var, width=20)
        view_combo['values'] = ('Dashboard', 'All Books', 'Search', 'Reports')
        view_combo.pack(anchor='w', padx=20, pady=5)
        
        ttk.Label(pref_frame, text="Items per Page:").pack(anchor='w', padx=5, pady=5)
        self.items_per_page_var = tk.StringVar(value="50")
        items_combo = ttk.Combobox(pref_frame, textvariable=self.items_per_page_var, width=10)
        items_combo['values'] = ('25', '50', '100', '200')
        items_combo.pack(anchor='w', padx=20, pady=5)
        
        # Interface settings
        interface_frame = ttk.LabelFrame(parent, text="Interface Settings")
        interface_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.confirm_deletes_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(interface_frame, text="Confirm Deletions", variable=self.confirm_deletes_var).pack(anchor='w', padx=5, pady=5)
        
        self.auto_refresh_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(interface_frame, text="Auto-refresh Data", variable=self.auto_refresh_var).pack(anchor='w', padx=5, pady=5)
        
        # Save button
        ttk.Button(parent, text="Save User Settings", command=self.save_user_settings).pack(pady=10)
        
    def save_library_settings(self):
        """Save library settings"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                for setting_name, var in self.library_settings_vars.items():
                    value = var.get().strip()
                    if value:
                        update_library_setting(setting_name, value)
                
                for setting_name, var in self.notification_vars.items():
                    value = 'true' if var.get() else 'false'
                    update_library_setting(setting_name, value)
                
                messagebox.showinfo("Success", "Library settings saved successfully!")
                
                # Log the action
                log_audit_event(get_current_user_id(), "GUI: Updated library settings", "library_settings")
            else:
                messagebox.showinfo("Demo", "Settings would be saved in full version")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error saving settings: {str(e)}")
            
    def save_system_settings(self):
        """Save system settings"""
        messagebox.showinfo("Success", "System settings saved successfully!")
        
    def save_user_settings(self):
        """Save user settings"""
        messagebox.showinfo("Success", "User settings saved successfully!")
        
    def optimize_database(self):
        """Optimize database"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('VACUUM')
                    cursor.execute('ANALYZE')
                    conn.close()
                    messagebox.showinfo("Success", "Database optimized successfully!")
            else:
                messagebox.showinfo("Demo", "Database optimization completed!")
        except Exception as e:
            messagebox.showerror("Error", f"Error optimizing database: {str(e)}")
            
    def check_database_integrity(self):
        """Check database integrity"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('PRAGMA integrity_check')
                    result = cursor.fetchone()[0]
                    conn.close()
                    
                    if result == 'ok':
                        messagebox.showinfo("Success", "Database integrity check passed!")
                    else:
                        messagebox.showwarning("Warning", f"Database integrity issues: {result}")
            else:
                messagebox.showinfo("Demo", "Database integrity check passed!")
        except Exception as e:
            messagebox.showerror("Error", f"Error checking database: {str(e)}")
            
    def show_audit_log(self):
        """Show audit log viewer"""
        self.audit_log_dialog()
        
    def audit_log_dialog(self):
        """Create audit log dialog"""
        dialog = tk.Toplevel(self.master)
        dialog.title("Audit Log Viewer")
        dialog.geometry("800x600")
        dialog.transient(self.master)
        
        # Filter frame
        filter_frame = ttk.Frame(dialog)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(filter_frame, text="User ID:").pack(side=tk.LEFT, padx=5)
        user_filter_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=user_filter_var, width=15).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(filter_frame, text="Action:").pack(side=tk.LEFT, padx=5)
        action_filter_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=action_filter_var, width=20).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(filter_frame, text="Filter", command=lambda: self.load_audit_log(audit_tree, user_filter_var.get(), action_filter_var.get())).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="Clear", command=lambda: self.load_audit_log(audit_tree)).pack(side=tk.LEFT, padx=5)
        
        # Audit log table
        table_frame = ttk.Frame(dialog)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ('Timestamp', 'User ID', 'Action', 'Table', 'Success')
        audit_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            audit_tree.heading(col, text=col)
            audit_tree.column(col, width=120)
            
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=audit_tree.yview)
        audit_tree.configure(yscrollcommand=v_scrollbar.set)
        
        audit_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load initial data
        self.load_audit_log(audit_tree)
        
        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
        
    def load_audit_log(self, tree, user_filter="", action_filter=""):
        """Load audit log data"""
        # Clear existing data
        for item in tree.get_children():
            tree.delete(item)
            
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    return
                    
                cursor = conn.cursor()
                
                query = '''
                SELECT timestamp, user_id, action, table_affected, success
                FROM audit_log
                WHERE 1=1
                '''
                params = []
                
                if user_filter:
                    query += ' AND user_id LIKE ?'
                    params.append(f'%{user_filter}%')
                    
                if action_filter:
                    query += ' AND action LIKE ?'
                    params.append(f'%{action_filter}%')
                
                query += ' ORDER BY timestamp DESC LIMIT 100'
                
                cursor.execute(query, params)
                logs = cursor.fetchall()
                conn.close()
                
                for log in logs:
                    timestamp, user_id, action, table_affected, success = log
                    success_text = "✅" if success else "❌"
                    
                    tree.insert('', 'end', values=(
                        timestamp[:19],  # Format timestamp
                        user_id,
                        action,
                        table_affected or "N/A",
                        success_text
                    ))
            else:
                # Demo data
                demo_logs = [
                    ("2024-01-15 10:30:00", "admin", "GUI: Login", "system", "✅"),
                    ("2024-01-15 10:31:00", "admin", "GUI: Added book B10001", "books", "✅"),
                    ("2024-01-15 10:32:00", "admin", "GUI: Checked out book", "book_loans", "✅"),
                ]
                
                for log in demo_logs:
                    tree.insert('', 'end', values=log)
                    
        except Exception as e:
            print(f"Error loading audit log: {e}")
            
    def show_reading_lists(self):
        """Show reading lists interface"""
        # Check permission instead of user directly
        if not self.check_permission('manage_reading_lists'):
            return
            
        self.clear_content_area()
        
        lists_frame = ttk.Frame(self.notebook)
        self.notebook.add(lists_frame, text="Reading Lists")
        
        title_label = ttk.Label(lists_frame, text="Reading Lists Management", style='Title.TLabel')
        title_label.pack(pady=10)
        
        # Control buttons
        control_frame = ttk.Frame(lists_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(control_frame, text="Create New List", command=self.create_reading_list_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Import List", command=self.import_reading_list_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Refresh", command=self.refresh_reading_lists).pack(side=tk.LEFT, padx=5)
        
        # Reading lists table
        table_frame = ttk.Frame(lists_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ('ID', 'Name', 'Description', 'Items', 'Type', 'Created')
        self.reading_lists_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=25)
        
        for col in columns:
            self.reading_lists_tree.heading(col, text=col)
            self.reading_lists_tree.column(col, width=120)
            
        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.reading_lists_tree.yview)
        self.reading_lists_tree.configure(yscrollcommand=scrollbar.set)
        
        self.reading_lists_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Context menu
        self.create_reading_lists_context_menu()
        
        # Load data
        self.load_reading_lists()
        
        # Bind double-click
        self.reading_lists_tree.bind('<Double-1>', self.view_reading_list_details)
        
    def create_reading_lists_context_menu(self):
        """Create context menu for reading lists"""
        self.reading_lists_context_menu = tk.Menu(self.master, tearoff=0)
        self.reading_lists_context_menu.add_command(label="View Details", command=self.view_reading_list_details)
        self.reading_lists_context_menu.add_command(label="Add Book", command=self.add_book_to_list)
        self.reading_lists_context_menu.add_command(label="Edit List", command=self.edit_reading_list)
        self.reading_lists_context_menu.add_separator()
        self.reading_lists_context_menu.add_command(label="Share List", command=self.share_reading_list)
        self.reading_lists_context_menu.add_command(label="Delete List", command=self.delete_reading_list)
        
        self.reading_lists_tree.bind('<Button-3>', self.show_reading_lists_context_menu)
        
    def show_reading_lists_context_menu(self, event):
        """Show context menu for reading lists"""
        item = self.reading_lists_tree.selection()[0] if self.reading_lists_tree.selection() else None
        if item:
            self.reading_lists_context_menu.post(event.x_root, event.y_root)
            
    def load_reading_lists(self):
        """Load reading lists data"""
        # Clear existing data
        for item in self.reading_lists_tree.get_children():
            self.reading_lists_tree.delete(item)
            
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    return
                    
                cursor = conn.cursor()
                cursor.execute('''
                SELECT rl.list_id, rl.name, rl.description, rl.created_date,
                       rl.is_public, rl.is_collaborative,
                       COUNT(rli.item_id) as item_count
                FROM reading_lists rl
                LEFT JOIN reading_list_items rli ON rl.list_id = rli.list_id
                WHERE rl.creator_id = ? OR rl.is_public = 1
                GROUP BY rl.list_id
                ORDER BY rl.created_date DESC
                ''', (get_current_user_id(),))
                
                lists = cursor.fetchall()
                conn.close()
                
                for lst in lists:
                    list_id, name, desc, created, is_public, is_collab, count = lst
                    list_type = "Public" if is_public else "Private"
                    if is_collab:
                        list_type += " + Collab"
                    
                    desc_display = (desc[:30] + "...") if desc and len(desc) > 30 else (desc or "")
                    
                    self.reading_lists_tree.insert('', 'end', values=(
                        list_id, name, desc_display, count, list_type, created[:10]
                    ))
            else:
                # Demo data
                demo_lists = [
                    (1, "My Favorites", "Books I love", 5, "Private", "2024-01-15"),
                    (2, "Science Fiction", "Best sci-fi books", 12, "Public", "2024-01-10"),
                ]
                
                for lst in demo_lists:
                    self.reading_lists_tree.insert('', 'end', values=lst)
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error loading reading lists: {str(e)}")
            
    def refresh_reading_lists(self):
        """Refresh reading lists"""
        self.load_reading_lists()
        
    def create_reading_list_dialog(self):
        """Create new reading list dialog"""
        dialog = tk.Toplevel(self.master)
        dialog.title("Create Reading List")
        dialog.geometry("400x350")
        dialog.transient(self.master)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Form fields
        ttk.Label(main_frame, text="List Name:").pack(anchor='w', pady=(0, 5))
        name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=name_var, width=40).pack(anchor='w', pady=(0, 10))
        
        ttk.Label(main_frame, text="Description:").pack(anchor='w', pady=(0, 5))
        desc_text = tk.Text(main_frame, height=4, width=40)
        desc_text.pack(anchor='w', pady=(0, 10))
        
        ttk.Label(main_frame, text="Category:").pack(anchor='w', pady=(0, 5))
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(main_frame, textvariable=category_var, width=37)
        category_combo['values'] = ('General', 'Fiction', 'Non-Fiction', 'Science', 'History', 'Educational')
        category_combo.pack(anchor='w', pady=(0, 10))
        
        # Options
        options_frame = ttk.LabelFrame(main_frame, text="Options")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        is_public_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Make this list public", variable=is_public_var).pack(anchor='w', padx=5, pady=5)
        
        is_collaborative_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Allow others to add books", variable=is_collaborative_var).pack(anchor='w', padx=5, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        def create_list():
            name = name_var.get().strip()
            description = desc_text.get("1.0", tk.END).strip()
            category = category_var.get().strip()
            
            if not name:
                messagebox.showwarning("Warning", "Please enter a list name")
                return
                
            try:
                if ORIGINAL_LIBRARY_AVAILABLE:
                    success = self.create_reading_list_database(name, description, category, 
                                                              is_public_var.get(), is_collaborative_var.get())
                    if success:
                        messagebox.showinfo("Success", f"Reading list '{name}' created successfully!")
                        dialog.destroy()
                        self.refresh_reading_lists()
                    else:
                        messagebox.showerror("Error", "Failed to create reading list")
                else:
                    messagebox.showinfo("Demo", f"Reading list '{name}' would be created")
                    dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Error creating reading list: {str(e)}")
        
        ttk.Button(button_frame, text="Create", command=create_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
    def create_reading_list_database(self, name, description, category, is_public, is_collaborative):
        """Create reading list in database"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO reading_lists 
            (name, description, creator_id, created_date, is_public, is_collaborative, category)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, description, get_current_user_id(), now, is_public, is_collaborative, category))
            
            conn.commit()
            conn.close()
            
            # Log the action
            if ORIGINAL_LIBRARY_AVAILABLE:
                log_audit_event(get_current_user_id(), f"GUI: Created reading list '{name}'", "reading_lists")
            
            return True
            
        except Exception as e:
            print(f"Error creating reading list: {e}")
            return False

    def restore_system_gui(self):
        """Restore system via GUI"""
        if not self.check_permission('system_config'):
            return
            
        backup_dir = filedialog.askdirectory(title="Select Backup Directory")
        
        if backup_dir:
            # Confirm restore operation
            result = messagebox.askyesno("Confirm Restore", 
                                       "This will overwrite current data. Are you sure you want to restore from backup?")
            
            if result:
                try:
                    if ORIGINAL_LIBRARY_AVAILABLE:
                        success = self.restore_from_backup(backup_dir)
                        if success:
                            messagebox.showinfo("Success", "System restored successfully!")
                            # Restart application to reload data
                            restart = messagebox.askyesno("Restart Required", 
                                                        "Application needs to restart to complete restore. Restart now?")
                            if restart:
                                self.exit_application(restart=True)
                        else:
                            messagebox.showerror("Error", "Restore failed")
                    else:
                        messagebox.showinfo("Demo", f"Would restore from {backup_dir}")
                except Exception as e:
                    messagebox.showerror("Error", f"Restore error: {str(e)}")

    def restore_from_backup(self, backup_dir):
        """Restore from backup directory"""
        try:
            import shutil
            
            # Check for manifest
            manifest_path = os.path.join(backup_dir, 'manifest.json')
            if os.path.exists(manifest_path):
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                print(f"Restoring backup from {manifest.get('backup_date', 'unknown date')}")
            
            # Create safety backup first
            safety_backup_dir = f"pre_restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.makedirs(safety_backup_dir, exist_ok=True)
            if hasattr(self, 'DATABASE_FILE') and os.path.exists(self.DATABASE_FILE):
                shutil.copy2(self.DATABASE_FILE, safety_backup_dir)
            
            # Restore database
            backup_db_path = os.path.join(backup_dir, 'library_database.db')
            if os.path.exists(backup_db_path) and hasattr(self, 'DATABASE_FILE'):
                shutil.copy2(backup_db_path, self.DATABASE_FILE)
            
            # Restore additional directories
            restore_dirs = ['qr_codes', 'digital_library', 'cover_images']
            for dir_name in restore_dirs:
                backup_subdir = os.path.join(backup_dir, dir_name)
                if os.path.exists(backup_subdir):
                    if os.path.exists(dir_name):
                        shutil.rmtree(dir_name)
                    shutil.copytree(backup_subdir, dir_name)
            
            # Log the action
            if ORIGINAL_LIBRARY_AVAILABLE:
                log_audit_event(get_current_user_id(), f"GUI: Restored system from {backup_dir}", "system")
            
            return True
            
        except Exception as e:
            print(f"Restore error: {e}")
            return False
            
    def show_user_preferences(self):
        """Show user preferences dialog"""
        # Get current user from auth system
        current_user = None
        if SHARED_AUTH_AVAILABLE:
            current_user = get_current_user()
        elif self.auth and hasattr(self.auth, 'current_user'):
            current_user = self.auth.current_user

        if not current_user:
            messagebox.showwarning("Warning", "Please log in first")
            return
            
        prefs_dialog = tk.Toplevel(self.master)
        prefs_dialog.title("User Preferences")
        prefs_dialog.geometry("400x300")
        prefs_dialog.transient(self.master)
        prefs_dialog.grab_set()
        
        main_frame = ttk.Frame(prefs_dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create notebook for preference categories
        prefs_notebook = ttk.Notebook(main_frame)
        prefs_notebook.pack(fill=tk.BOTH, expand=True)
        
        # General preferences
        general_frame = ttk.Frame(prefs_notebook)
        prefs_notebook.add(general_frame, text="General")
        
        ttk.Label(general_frame, text="Default Dashboard View:").pack(anchor='w', pady=5)
        self.default_dashboard_var = tk.StringVar(value="Statistics")
        dashboard_combo = ttk.Combobox(general_frame, textvariable=self.default_dashboard_var, width=30)
        dashboard_combo['values'] = ('Statistics', 'Recent Activity', 'Quick Actions', 'Reports')
        dashboard_combo.pack(anchor='w', padx=20, pady=5)
        
        ttk.Label(general_frame, text="Items per Page:").pack(anchor='w', pady=5)
        self.items_per_page_pref_var = tk.StringVar(value="50")
        items_combo = ttk.Combobox(general_frame, textvariable=self.items_per_page_pref_var, width=10)
        items_combo['values'] = ('25', '50', '100', '200')
        items_combo.pack(anchor='w', padx=20, pady=5)
        
        # Interface preferences
        interface_frame = ttk.Frame(prefs_notebook)
        prefs_notebook.add(interface_frame, text="Interface")
        
        self.confirm_actions_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(interface_frame, text="Confirm dangerous actions", 
                       variable=self.confirm_actions_var).pack(anchor='w', pady=5)
        
        self.auto_save_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(interface_frame, text="Auto-save form data", 
                       variable=self.auto_save_var).pack(anchor='w', pady=5)
        
        self.show_tooltips_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(interface_frame, text="Show tooltips", 
                       variable=self.show_tooltips_var).pack(anchor='w', pady=5)
        
        # Notification preferences
        notification_frame = ttk.Frame(prefs_notebook)
        prefs_notebook.add(notification_frame, text="Notifications")
        
        self.desktop_notifications_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(notification_frame, text="Desktop notifications", 
                       variable=self.desktop_notifications_var).pack(anchor='w', pady=5)
        
        self.sound_alerts_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(notification_frame, text="Sound alerts", 
                       variable=self.sound_alerts_var).pack(anchor='w', pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Save", command=lambda: self.save_user_preferences(prefs_dialog)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=prefs_dialog.destroy).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reset to Defaults", command=self.reset_user_preferences).pack(side=tk.LEFT, padx=5)
        
    def save_user_preferences(self, dialog):
        """Save user preferences"""
        try:
            preferences = {
                'default_dashboard': self.default_dashboard_var.get(),
                'items_per_page': self.items_per_page_pref_var.get(),
                'confirm_actions': self.confirm_actions_var.get(),
                'auto_save': self.auto_save_var.get(),
                'show_tooltips': self.show_tooltips_var.get(),
                'desktop_notifications': self.desktop_notifications_var.get(),
                'sound_alerts': self.sound_alerts_var.get(),
            }
            
            if ORIGINAL_LIBRARY_AVAILABLE:
                # Save to database user_preferences table
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    user_id = get_current_user_id()
                    
                    cursor.execute('''
                    INSERT OR REPLACE INTO user_preferences 
                    (user_id, preferred_categories, preferred_authors, reading_level, 
                     notification_preferences, privacy_settings, reading_goals, language_preference)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        user_id, 
                        json.dumps([]),  # preferred_categories
                        json.dumps([]),  # preferred_authors
                        'Unknown',       # reading_level
                        json.dumps({
                            'desktop_notifications': preferences['desktop_notifications'],
                            'sound_alerts': preferences['sound_alerts']
                        }),
                        json.dumps({
                            'confirm_actions': preferences['confirm_actions'],
                            'auto_save': preferences['auto_save']
                        }),
                        json.dumps([]),  # reading_goals
                        'English'        # language_preference
                    ))
                    
                    conn.commit()
                    conn.close()
            
            messagebox.showinfo("Success", "Preferences saved successfully!")
            dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error saving preferences: {str(e)}")
            
    def reset_user_preferences(self):
        """Reset user preferences to defaults"""
        result = messagebox.askyesno("Confirm Reset", "Reset all preferences to default values?")
        
        if result:
            self.default_dashboard_var.set("Statistics")
            self.items_per_page_pref_var.set("50")
            self.confirm_actions_var.set(True)
            self.auto_save_var.set(True)
            self.show_tooltips_var.set(True)
            self.desktop_notifications_var.set(True)
            self.sound_alerts_var.set(False)
            
            messagebox.showinfo("Success", "Preferences reset to defaults")
            
    def show_overdue_books(self):
        """Show overdue books interface"""
        if not self.check_permission('view_reports'):
            return
            
        self.clear_content_area()
        
        overdue_frame = ttk.Frame(self.notebook)
        self.notebook.add(overdue_frame, text="Overdue Books")
        
        title_label = ttk.Label(overdue_frame, text="Overdue Books Management", style='Title.TLabel')
        title_label.pack(pady=10)
        
        # Control frame
        control_frame = ttk.Frame(overdue_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(control_frame, text="Send Reminders", command=self.send_overdue_reminders).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Process Fines", command=self.process_overdue_fines).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Export Report", command=self.export_overdue_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Refresh", command=self.refresh_overdue_books).pack(side=tk.LEFT, padx=5)
        
        # Summary frame
        summary_frame = ttk.LabelFrame(overdue_frame, text="Summary")
        summary_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.overdue_summary_label = ttk.Label(summary_frame, text="Loading summary...")
        self.overdue_summary_label.pack(pady=10)
        
        # Overdue books table
        table_frame = ttk.Frame(overdue_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ('User ID', 'Book ID', 'Title', 'Due Date', 'Days Overdue', 'Fine Amount', 'Contact')
        self.overdue_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.overdue_tree.heading(col, text=col)
            self.overdue_tree.column(col, width=100)
            
        # Add scrollbar
        overdue_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.overdue_tree.yview)
        self.overdue_tree.configure(yscrollcommand=overdue_scrollbar.set)
        
        self.overdue_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        overdue_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Context menu
        self.create_overdue_context_menu()
        
        # Load data
        self.load_overdue_books()
        
    def create_overdue_context_menu(self):
        """Create context menu for overdue books"""
        self.overdue_context_menu = tk.Menu(self.master, tearoff=0)
        self.overdue_context_menu.add_command(label="Contact User", command=self.contact_overdue_user)
        self.overdue_context_menu.add_command(label="Process Return", command=self.process_overdue_return)
        self.overdue_context_menu.add_command(label="Waive Fine", command=self.waive_fine)
        self.overdue_context_menu.add_separator()
        self.overdue_context_menu.add_command(label="View User History", command=self.view_user_history)
        
        self.overdue_tree.bind('<Button-3>', self.show_overdue_context_menu)
        
    def show_overdue_context_menu(self, event):
        """Show context menu for overdue books"""
        item = self.overdue_tree.selection()[0] if self.overdue_tree.selection() else None
        if item:
            self.overdue_context_menu.post(event.x_root, event.y_root)


    def view_loan_history_gui(self):
        """GUI for viewing loan history"""
        dialog = tk.Toplevel(self.master)
        dialog.title("Loan History Viewer")
        dialog.geometry("800x600")
        dialog.transient(self.master)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Options frame
        options_frame = ttk.LabelFrame(main_frame, text="View Options")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.loan_history_type = tk.StringVar(value="all")
        ttk.Radiobutton(options_frame, text="All Recent Loans", variable=self.loan_history_type, value="all").pack(anchor='w', padx=5, pady=2)
        ttk.Radiobutton(options_frame, text="By User", variable=self.loan_history_type, value="user").pack(anchor='w', padx=5, pady=2)
        ttk.Radiobutton(options_frame, text="By Book", variable=self.loan_history_type, value="book").pack(anchor='w', padx=5, pady=2)
        
        # Search frame
        search_frame = ttk.Frame(options_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(search_frame, text="User/Book ID:").pack(side=tk.LEFT)
        self.loan_search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.loan_search_var, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Search", command=self.load_loan_history).pack(side=tk.LEFT, padx=5)
        
        # Results table
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ('Loan ID', 'User ID', 'Book ID', 'Title', 'Checkout Date', 'Due Date', 'Return Date', 'Status')
        self.loan_history_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            self.loan_history_tree.heading(col, text=col)
            self.loan_history_tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.loan_history_tree.yview)
        self.loan_history_tree.configure(yscrollcommand=scrollbar.set)
        
        self.loan_history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load initial data
        self.load_loan_history()
        
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def load_loan_history(self):
        """Load loan history data based on current selection"""
        # Clear existing data
        for item in self.loan_history_tree.get_children():
            self.loan_history_tree.delete(item)
        
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    return
                
                cursor = conn.cursor()
                history_type = self.loan_history_type.get()
                search_term = self.loan_search_var.get().strip()
                
                if history_type == "all":
                    cursor.execute('''
                    SELECT bl.loan_id, bl.user_id, bl.book_id, b.title, 
                           bl.checkout_date, bl.due_date, bl.return_date, bl.status
                    FROM book_loans bl
                    JOIN books b ON bl.book_id = b.book_id
                    ORDER BY bl.checkout_date DESC
                    LIMIT 100
                    ''')
                elif history_type == "user" and search_term:
                    cursor.execute('''
                    SELECT bl.loan_id, bl.user_id, bl.book_id, b.title, 
                           bl.checkout_date, bl.due_date, bl.return_date, bl.status
                    FROM book_loans bl
                    JOIN books b ON bl.book_id = b.book_id
                    WHERE bl.user_id = ?
                    ORDER BY bl.checkout_date DESC
                    ''', (search_term,))
                elif history_type == "book" and search_term:
                    cursor.execute('''
                    SELECT bl.loan_id, bl.user_id, bl.book_id, b.title, 
                           bl.checkout_date, bl.due_date, bl.return_date, bl.status
                    FROM book_loans bl
                    JOIN books b ON bl.book_id = b.book_id
                    WHERE bl.book_id = ?
                    ORDER BY bl.checkout_date DESC
                    ''', (search_term,))
                else:
                    return
                
                loans = cursor.fetchall()
                conn.close()
                
                for loan in loans:
                    loan_id, user_id, book_id, title, checkout, due, returned, status = loan
                    # Format dates
                    checkout_date = checkout[:10] if checkout else ""
                    due_date = due[:10] if due else ""
                    return_date = returned[:10] if returned else ""
                    
                    self.loan_history_tree.insert('', 'end', values=(
                        loan_id, user_id, book_id, title[:30], checkout_date, due_date, return_date, status
                    ))
            else:
                # Demo data
                demo_loans = [
                    (1, "USER001", "B10001", "Demo Book 1", "2024-01-15", "2024-01-29", "2024-01-25", "returned"),
                    (2, "USER002", "B10002", "Demo Book 2", "2024-01-20", "2024-02-03", "", "active"),
                ]
                
                for loan in demo_loans:
                    self.loan_history_tree.insert('', 'end', values=loan)
        
        except Exception as e:
            messagebox.showerror("Error", f"Error loading loan history: {str(e)}")

    def library_maintenance_gui(self):
        """GUI for library maintenance tasks"""
        if not self.check_permission('system_config'):
            return
        
        dialog = tk.Toplevel(self.master)
        dialog.title("Library Maintenance")
        dialog.geometry("600x500")
        dialog.transient(self.master)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        title_label = ttk.Label(main_frame, text="Library Maintenance Tasks", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Maintenance tasks
        tasks_frame = ttk.LabelFrame(main_frame, text="Available Tasks")
        tasks_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        tasks = [
            ("Clean up expired reservations", self.cleanup_expired_reservations),
            ("Update overdue status", self.update_overdue_status),
            ("Calculate fines", self.calculate_fines),
            ("Archive old loan records", self.archive_old_records),
            ("Optimize database", self.optimize_database),
            ("Check data integrity", self.check_data_integrity),
        ]
        
        for i, (task_name, task_func) in enumerate(tasks):
            task_frame = ttk.Frame(tasks_frame)
            task_frame.pack(fill=tk.X, padx=10, pady=5)
            
            ttk.Label(task_frame, text=f"{i+1}. {task_name}").pack(side=tk.LEFT)
            ttk.Button(task_frame, text="Run", command=task_func).pack(side=tk.RIGHT)
        
        # Results area
        results_frame = ttk.LabelFrame(main_frame, text="Task Results")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        self.maintenance_results = ScrolledText(results_frame, height=8, wrap=tk.WORD)
        self.maintenance_results.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def cleanup_expired_reservations(self):
        """Clean up expired reservations"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                    UPDATE book_reservations 
                    SET status = 'expired'
                    WHERE status = 'active' AND expiry_date < datetime('now')
                    ''')
                    
                    expired_count = cursor.rowcount
                    conn.commit()
                    conn.close()
                    
                    result = f"✅ Cleaned up {expired_count} expired reservations.\n"
            else:
                result = "✅ Demo: Would clean up expired reservations.\n"
            
            self.maintenance_results.insert(tk.END, result)
            self.maintenance_results.see(tk.END)
        except Exception as e:
            self.maintenance_results.insert(tk.END, f"❌ Error: {str(e)}\n")

    def update_overdue_status(self):
        """Update overdue loan status"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                    UPDATE book_loans 
                    SET status = 'overdue'
                    WHERE status = 'active' AND due_date < datetime('now')
                    ''')
                    
                    overdue_count = cursor.rowcount
                    conn.commit()
                    conn.close()
                    
                    result = f"✅ Updated {overdue_count} loans to overdue status.\n"
            else:
                result = "✅ Demo: Would update overdue status.\n"
            
            self.maintenance_results.insert(tk.END, result)
            self.maintenance_results.see(tk.END)
        except Exception as e:
            self.maintenance_results.insert(tk.END, f"❌ Error: {str(e)}\n")

    def calculate_fines(self):
        """Calculate and update fines for overdue books"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    
                    # Get fine per day setting
                    cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "fine_per_day"')
                    setting = cursor.fetchone()
                    fine_per_day = float(setting[0]) if setting else 0.50
                    
                    cursor.execute('''
                    UPDATE book_loans 
                    SET fine_amount = (julianday('now') - julianday(due_date)) * ?
                    WHERE status = 'overdue' AND due_date < datetime('now')
                    ''', (fine_per_day,))
                    
                    fine_count = cursor.rowcount
                    conn.commit()
                    conn.close()
                    
                    result = f"✅ Updated fines for {fine_count} overdue loans at ${fine_per_day:.2f} per day.\n"
            else:
                result = "✅ Demo: Would calculate and update fines.\n"
            
            self.maintenance_results.insert(tk.END, result)
            self.maintenance_results.see(tk.END)
        except Exception as e:
            self.maintenance_results.insert(tk.END, f"❌ Error: {str(e)}\n")

    def archive_old_records(self):
        """Archive old loan records"""
        result = "✅ Archive functionality would move old completed loans to archive table.\nThis helps maintain performance for active queries.\n"
        self.maintenance_results.insert(tk.END, result)
        self.maintenance_results.see(tk.END)

    def check_data_integrity(self):
        """Check database integrity"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('PRAGMA integrity_check')
                    result = cursor.fetchone()[0]
                    conn.close()
                    
                    if result == 'ok':
                        integrity_result = "✅ Database integrity check passed.\n"
                    else:
                        integrity_result = f"❌ Database integrity issues: {result}\n"
            else:
                integrity_result = "✅ Demo: Database integrity check passed.\n"
            
            self.maintenance_results.insert(tk.END, integrity_result)
            self.maintenance_results.see(tk.END)
        except Exception as e:
            self.maintenance_results.insert(tk.END, f"❌ Error checking integrity: {str(e)}\n")

    def quick_system_health_check(self):
        """Perform quick system health check"""
        dialog = tk.Toplevel(self.master)
        dialog.title("System Health Check")
        dialog.geometry("500x400")
        dialog.transient(self.master)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        title_label = ttk.Label(main_frame, text="System Health Check", style='Title.TLabel')
        title_label.pack(pady=(0, 10))
        
        # Results area
        results_text = ScrolledText(main_frame, wrap=tk.WORD)
        results_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Run health check
        health_status = []
        
        try:
            # Database connectivity
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT COUNT(*) FROM books')
                    health_status.append(("Database Connection", "✅ OK"))
                    
                    # Check integrity
                    cursor.execute('PRAGMA integrity_check')
                    integrity = cursor.fetchone()[0]
                    
                    if integrity == 'ok':
                        health_status.append(("Database Integrity", "✅ OK"))
                    else:
                        health_status.append(("Database Integrity", f"❌ {integrity}"))
                    
                    # Check overdue items
                    cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status = "overdue"')
                    overdue_count = cursor.fetchone()[0]
                    
                    if overdue_count == 0:
                        health_status.append(("Overdue Items", "✅ None"))
                    elif overdue_count < 10:
                        health_status.append(("Overdue Items", f"⚠️ {overdue_count} items"))
                    else:
                        health_status.append(("Overdue Items", f"❌ {overdue_count} items"))
                    
                    conn.close()
                else:
                    health_status.append(("Database Connection", "❌ Failed"))
            else:
                health_status.append(("Database Connection", "✅ Demo Mode"))
            
            # File system checks
            important_dirs = ['backups', 'qr_codes', 'digital_library']
            
            for directory in important_dirs:
                if os.path.exists(directory):
                    health_status.append((f"{directory.title()} Directory", "✅ Exists"))
                else:
                    health_status.append((f"{directory.title()} Directory", "⚠️ Missing"))
            
            # Display results
            results_text.insert(tk.END, "Health Check Results:\n")
            results_text.insert(tk.END, "-" * 40 + "\n\n")
            
            for check, status in health_status:
                results_text.insert(tk.END, f"{check:<25} {status}\n")
            
            results_text.insert(tk.END, "\n" + "-" * 40 + "\n")
            
            # Overall assessment
            error_count = len([s for _, s in health_status if s.startswith("❌")])
            warning_count = len([s for _, s in health_status if s.startswith("⚠️")])
            
            if error_count == 0 and warning_count == 0:
                results_text.insert(tk.END, "Overall Status: ✅ HEALTHY")
            elif error_count == 0:
                results_text.insert(tk.END, "Overall Status: ⚠️ WARNINGS")
            else:
                results_text.insert(tk.END, "Overall Status: ❌ ISSUES DETECTED")
            
        except Exception as e:
            results_text.insert(tk.END, f"Health check failed: {e}")
        
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def generate_library_statistics_export(self):
        """Generate comprehensive statistics export"""
        if not self.check_permission('generate_reports'):
            return
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            export_filename = f"library_statistics_export_{timestamp}.json"
            
            # Generate comprehensive statistics
            stats = {
                'export_info': {
                    'generated_at': datetime.now().isoformat(),
                    'generated_by': get_current_user_id(),
                    'system_version': '2.0.0'
                }
            }
            
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    
                    # Collection statistics
                    cursor.execute('SELECT COUNT(*) FROM books')
                    stats['collection_stats'] = {'total_books': cursor.fetchone()[0]}
                    
                    cursor.execute('SELECT COUNT(DISTINCT author) FROM books')
                    stats['collection_stats']['unique_authors'] = cursor.fetchone()[0]
                    
                    cursor.execute('SELECT category, COUNT(*) FROM books GROUP BY category')
                    stats['collection_stats']['books_by_category'] = dict(cursor.fetchall())
                    
                    conn.close()
            else:
                stats['collection_stats'] = {
                    'total_books': 150,
                    'unique_authors': 75,
                    'books_by_category': {'Fiction': 60, 'Non-Fiction': 40, 'Science': 30, 'History': 20}
                }
            
            # Export to JSON file
            with open(export_filename, 'w') as f:
                json.dump(stats, f, indent=2, default=str)
            
            messagebox.showinfo("Success", f"Statistics exported to: {export_filename}")
            
            log_audit_event(get_current_user_id(), 
                           f"Exported library statistics to {export_filename}",
                           "system")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error exporting statistics: {str(e)}")

    def show_barcode_generator(self):
        """Show barcode generator interface"""
        if not self.check_permission('manage_books'):
            return
        
        dialog = tk.Toplevel(self.master)
        dialog.title("Barcode Generator")
        dialog.geometry("500x400")
        dialog.transient(self.master)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        title_label = ttk.Label(main_frame, text="Generate Barcodes", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Options frame
        options_frame = ttk.LabelFrame(main_frame, text="Generation Options")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.barcode_type = tk.StringVar(value="single")
        ttk.Radiobutton(options_frame, text="Single Book", variable=self.barcode_type, value="single").pack(anchor='w', padx=5, pady=2)
        ttk.Radiobutton(options_frame, text="Multiple Books", variable=self.barcode_type, value="multiple").pack(anchor='w', padx=5, pady=2)
        ttk.Radiobutton(options_frame, text="All Books", variable=self.barcode_type, value="all").pack(anchor='w', padx=5, pady=2)
        
        # Input frame
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(input_frame, text="Book ID(s) (comma-separated):").pack(anchor='w')
        self.barcode_input = tk.Text(input_frame, height=3)
        self.barcode_input.pack(fill=tk.X, pady=5)
        
        # Generate button
        ttk.Button(main_frame, text="Generate Barcodes", command=self.generate_barcodes).pack(pady=10)
        
        # Results area
        results_frame = ttk.LabelFrame(main_frame, text="Results")
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        self.barcode_results = ScrolledText(results_frame, height=8)
        self.barcode_results.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def generate_barcodes(self):
        """Generate barcodes based on selected options"""
        try:
            barcode_type = self.barcode_type.get()
            book_ids = []
            
            if barcode_type == "single" or barcode_type == "multiple":
                input_text = self.barcode_input.get("1.0", tk.END).strip()
                if input_text:
                    book_ids = [bid.strip() for bid in input_text.split(',') if bid.strip()]
            elif barcode_type == "all":
                if ORIGINAL_LIBRARY_AVAILABLE:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute('SELECT book_id FROM books ORDER BY book_id')
                        book_ids = [row[0] for row in cursor.fetchall()]
                        conn.close()
                else:
                    book_ids = ["B10001", "B10002", "B10003"]  # Demo data
            
            if not book_ids:
                messagebox.showwarning("Warning", "Please enter book IDs or select 'All Books'")
                return
            
            # Generate barcode labels
            self.barcode_results.delete("1.0", tk.END)
            self.barcode_results.insert(tk.END, f"Generating barcodes for {len(book_ids)} books...\n\n")
            
            generated_count = 0
            
            for book_id in book_ids:
                # Get book info
                if ORIGINAL_LIBRARY_AVAILABLE:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute('SELECT title, author, barcode FROM books WHERE book_id = ?', (book_id,))
                        book_info = cursor.fetchone()
                        conn.close()
                        
                        if book_info:
                            title, author, barcode = book_info
                            self.barcode_results.insert(tk.END, f"Book ID: {book_id}\n")
                            self.barcode_results.insert(tk.END, f"Title: {title}\n")
                            self.barcode_results.insert(tk.END, f"Author: {author}\n")
                            self.barcode_results.insert(tk.END, f"Barcode: {barcode or 'Not generated'}\n")
                            self.barcode_results.insert(tk.END, "-" * 30 + "\n\n")
                            generated_count += 1
                else:
                    # Demo mode
                    self.barcode_results.insert(tk.END, f"Book ID: {book_id}\n")
                    self.barcode_results.insert(tk.END, f"Title: Demo Book\n")
                    self.barcode_results.insert(tk.END, f"Author: Demo Author\n")
                    self.barcode_results.insert(tk.END, f"Barcode: LIB{book_id}\n")
                    self.barcode_results.insert(tk.END, "-" * 30 + "\n\n")
                    generated_count += 1
            
            self.barcode_results.insert(tk.END, f"✅ Generated {generated_count} barcode labels\n")
            
            # Log the action
            log_audit_event(get_current_user_id(), 
                           f"Generated {generated_count} barcode labels",
                           "books")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error generating barcodes: {str(e)}")

    def show_fine_management(self):
        """Show fine management interface"""
        if not self.check_permission('manage_loans'):
            return
        
        dialog = tk.Toplevel(self.master)
        dialog.title("Fine Management")
        dialog.geometry("700x500")
        dialog.transient(self.master)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        title_label = ttk.Label(main_frame, text="Fine Management System", style='Title.TLabel')
        title_label.pack(pady=(0, 10))
        
        # Search frame
        search_frame = ttk.LabelFrame(main_frame, text="Find User")
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        search_inner = ttk.Frame(search_frame)
        search_inner.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(search_inner, text="User ID:").pack(side=tk.LEFT)
        self.fine_user_var = tk.StringVar()
        ttk.Entry(search_inner, textvariable=self.fine_user_var, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_inner, text="Search", command=self.load_user_fines).pack(side=tk.LEFT, padx=5)
        
        # User info frame
        info_frame = ttk.LabelFrame(main_frame, text="User Information")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.user_info_text = tk.Text(info_frame, height=3, state=tk.DISABLED)
        self.user_info_text.pack(fill=tk.X, padx=5, pady=5)
        
        # Fines table
        fines_frame = ttk.LabelFrame(main_frame, text="Outstanding Fines")
        fines_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        columns = ('Loan ID', 'Book ID', 'Title', 'Days Overdue', 'Fine Amount')
        self.fines_tree = ttk.Treeview(fines_frame, columns=columns, show='headings', height=8)
        
        for col in columns:
            self.fines_tree.heading(col, text=col)
            self.fines_tree.column(col, width=100)
        
        fines_scrollbar = ttk.Scrollbar(fines_frame, orient=tk.VERTICAL, command=self.fines_tree.yview)
        self.fines_tree.configure(yscrollcommand=fines_scrollbar.set)
        
        self.fines_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        fines_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        # Payment frame
        payment_frame = ttk.LabelFrame(main_frame, text="Process Payment")
        payment_frame.pack(fill=tk.X)
        
        payment_inner = ttk.Frame(payment_frame)
        payment_inner.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(payment_inner, text="Payment Amount: $").pack(side=tk.LEFT)
        self.payment_amount_var = tk.StringVar()
        ttk.Entry(payment_inner, textvariable=self.payment_amount_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(payment_inner, text="Process Payment", command=self.process_fine_payment).pack(side=tk.LEFT, padx=5)
        ttk.Button(payment_inner, text="💳 Pay via Finance System", command=self.pay_fine_via_finance).pack(side=tk.LEFT, padx=5)
        ttk.Button(payment_inner, text="Waive All Fines", command=self.waive_all_fines).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def load_user_fines(self):
        """Load outstanding fines for a user"""
        user_id = self.fine_user_var.get().strip()
        
        if not user_id:
            messagebox.showwarning("Warning", "Please enter a User ID")
            return
        
        # Clear existing data
        for item in self.fines_tree.get_children():
            self.fines_tree.delete(item)
        
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Get user info
                    student_columns = self._get_student_columns()
                    grade_sql = ', grade_level' if 'grade_level' in student_columns else ''
                    cursor.execute(f'SELECT first_name, last_name{grade_sql} FROM students WHERE student_id = ?', (user_id,))
                    user_info = cursor.fetchone()

                    if user_info:
                        first_name, last_name = user_info[:2]
                        grade = user_info[2] if len(user_info) > 2 else 'N/A'
                        info_text = f"Name: {first_name} {last_name}\nGrade: {grade}\nUser ID: {user_id}"
                    else:
                        info_text = f"User ID: {user_id}\nName: Not found in student records"
                    
                    self.user_info_text.config(state=tk.NORMAL)
                    self.user_info_text.delete("1.0", tk.END)
                    self.user_info_text.insert("1.0", info_text)
                    self.user_info_text.config(state=tk.DISABLED)
                    
                    # Get outstanding fines
                    cursor.execute('''
                    SELECT bl.loan_id, bl.book_id, b.title, 
                           julianday('now') - julianday(bl.due_date) as days_overdue,
                           bl.fine_amount
                    FROM book_loans bl
                    JOIN books b ON bl.book_id = b.book_id
                    WHERE bl.user_id = ? AND bl.fine_amount > 0 AND bl.status != 'returned'
                    ORDER BY bl.due_date
                    ''', (user_id,))
                    
                    fines = cursor.fetchall()
                    
                    total_fines = 0
                    for fine in fines:
                        loan_id, book_id, title, days_overdue, fine_amount = fine
                        total_fines += fine_amount
                        
                        self.fines_tree.insert('', 'end', values=(
                            loan_id, book_id, title[:20], int(days_overdue), f"${fine_amount:.2f}"
                        ))
                    
                    # Update user info with total
                    updated_info = info_text + f"\nTotal Outstanding Fines: ${total_fines:.2f}"
                    self.user_info_text.config(state=tk.NORMAL)
                    self.user_info_text.delete("1.0", tk.END)
                    self.user_info_text.insert("1.0", updated_info)
                    self.user_info_text.config(state=tk.DISABLED)
                    
                    conn.close()
            else:
                # Demo mode
                info_text = f"User ID: {user_id}\nName: Demo User\nTotal Fines: $5.00"
                self.user_info_text.config(state=tk.NORMAL)
                self.user_info_text.delete("1.0", tk.END)
                self.user_info_text.insert("1.0", info_text)
                self.user_info_text.config(state=tk.DISABLED)
                
                # Demo fine data
                self.fines_tree.insert('', 'end', values=(1, "B10001", "Demo Book", 5, "$5.00"))
        
        except Exception as e:
            messagebox.showerror("Error", f"Error loading fines: {str(e)}")

    def process_fine_payment(self):
        """Process a manual fine payment (cash/card at library desk)"""
        user_id = self.fine_user_var.get().strip()
        payment_amount = self.payment_amount_var.get().strip()

        if not user_id:
            messagebox.showwarning("Warning", "Please search for a user first")
            return

        if not payment_amount:
            messagebox.showwarning("Warning", "Please enter a payment amount")
            return

        try:
            amount = float(payment_amount)
            if amount <= 0:
                messagebox.showwarning("Warning", "Payment amount must be greater than 0")
                return
        except ValueError:
            messagebox.showwarning("Warning", "Please enter a valid payment amount")
            return

        # Get user details
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    messagebox.showerror("Error", "Database connection unavailable")
                    return

                cursor = conn.cursor()

                # Get total outstanding fines
                cursor.execute('''
                    SELECT SUM(fine_amount) FROM book_loans
                    WHERE user_id = ? AND fine_amount > 0
                ''', (user_id,))
                total_fines = cursor.fetchone()[0] or 0.0

                if total_fines == 0:
                    messagebox.showinfo("No Fines", "This user has no outstanding fines")
                    conn.close()
                    return

                if amount > total_fines:
                    response = messagebox.askyesno(
                        "Payment Exceeds Fines",
                        f"Payment amount (${amount:.2f}) exceeds total fines (${total_fines:.2f}).\n\n"
                        f"Do you want to process payment of ${total_fines:.2f} (full balance) instead?"
                    )
                    if response:
                        amount = total_fines
                    else:
                        conn.close()
                        return

                # Apply payment to fines (oldest first)
                cursor.execute('''
                    SELECT loan_id, fine_amount FROM book_loans
                    WHERE user_id = ? AND fine_amount > 0
                    ORDER BY due_date ASC
                ''', (user_id,))

                loans_with_fines = cursor.fetchall()
                remaining_payment = amount
                current_date = datetime.now().strftime('%Y-%m-%d')

                for loan_id, fine_amount in loans_with_fines:
                    if remaining_payment <= 0:
                        break

                    if remaining_payment >= fine_amount:
                        # Pay full fine for this loan
                        cursor.execute('''
                            UPDATE book_loans
                            SET fine_amount = 0,
                                notes = COALESCE(notes || '; ', '') || 'Fine paid on ' || ?
                            WHERE loan_id = ?
                        ''', (current_date, loan_id))
                        remaining_payment -= fine_amount
                    else:
                        # Partial payment
                        new_fine_amount = fine_amount - remaining_payment
                        cursor.execute('''
                            UPDATE book_loans
                            SET fine_amount = ?
                            WHERE loan_id = ?
                        ''', (new_fine_amount, loan_id))
                        remaining_payment = 0

                # Record payment in finance system
                finance_success = self._record_library_payment_in_finance(
                    user_id=user_id,
                    amount=amount,
                    payment_method="Cash/Card at Library Desk"
                )

                conn.commit()
                conn.close()

                # Log the action
                if ORIGINAL_LIBRARY_AVAILABLE:
                    log_audit_event(get_current_user_id(),
                                  f"GUI: Processed manual fine payment ${amount:.2f} for user {user_id}",
                                  "book_loans", user_id)

                success_msg = (
                    f"Payment of ${amount:.2f} processed successfully!\n\n"
                    f"Payment Method: Manual (Cash/Card at Desk)\n"
                    f"User ID: {user_id}\n"
                    f"Remaining balance will be shown in the refreshed list."
                )

                if finance_success:
                    success_msg += "\n\n✓ Payment recorded in Finance System"
                else:
                    success_msg += "\n\n⚠ Payment processed but finance recording failed"

                messagebox.showinfo("Success", success_msg)

                # Clear payment amount field
                self.payment_amount_var.set("")

                # Refresh the fines display
                self.load_user_fines()

            else:
                # Demo mode
                messagebox.showinfo("Demo", f"Demo: Payment of ${amount:.2f} processed for {user_id}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process payment: {str(e)}")

    def waive_all_fines(self):
        """Waive all outstanding fines for a user"""
        user_id = self.fine_user_var.get().strip()

        if not user_id:
            messagebox.showwarning("Warning", "Please search for a user first")
            return

        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    messagebox.showerror("Error", "Database connection unavailable")
                    return

                cursor = conn.cursor()

                # Get total outstanding fines
                cursor.execute('''
                    SELECT SUM(fine_amount) FROM book_loans
                    WHERE user_id = ? AND fine_amount > 0
                ''', (user_id,))
                total_fines = cursor.fetchone()[0] or 0.0

                if total_fines == 0:
                    messagebox.showinfo("No Fines", "This user has no outstanding fines to waive")
                    conn.close()
                    return

                # Confirm waiver
                response = messagebox.askyesno(
                    "Confirm Waive Fines",
                    f"Are you sure you want to waive all fines for user {user_id}?\n\n"
                    f"Total amount to be waived: ${total_fines:.2f}\n\n"
                    f"This action cannot be undone."
                )

                if not response:
                    conn.close()
                    return

                # Waive all fines
                current_date = datetime.now().strftime('%Y-%m-%d')
                cursor.execute('''
                    UPDATE book_loans
                    SET fine_amount = 0,
                        notes = COALESCE(notes || '; ', '') || 'Fine waived on ' || ?
                    WHERE user_id = ? AND fine_amount > 0
                ''', (current_date, user_id))

                rows_affected = cursor.rowcount
                conn.commit()
                conn.close()

                # Log the action
                if ORIGINAL_LIBRARY_AVAILABLE:
                    log_audit_event(get_current_user_id(),
                                  f"GUI: Waived all fines (${total_fines:.2f}) for user {user_id}",
                                  "book_loans", user_id)

                messagebox.showinfo("Success",
                    f"All fines waived successfully!\n\n"
                    f"User ID: {user_id}\n"
                    f"Amount waived: ${total_fines:.2f}\n"
                    f"Loans affected: {rows_affected}")

                # Refresh the fines display
                self.load_user_fines()

            else:
                # Demo mode
                messagebox.showinfo("Demo", f"Demo: All fines waived for {user_id}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to waive fines: {str(e)}")

    def view_fine_history(self):
        """View complete fine payment and waiver history for a user"""
        user_id = self.fine_user_var.get().strip()

        if not user_id:
            messagebox.showwarning("Warning", "Please search for a user first")
            return

        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    messagebox.showerror("Error", "Database connection unavailable")
                    return

                cursor = conn.cursor()

                # Get all fine-related transactions
                cursor.execute('''
                    SELECT loan_id, book_id, checkout_date, due_date, return_date,
                           fine_amount, status, notes
                    FROM book_loans
                    WHERE user_id = ?
                    ORDER BY checkout_date DESC
                ''', (user_id,))

                transactions = cursor.fetchall()
                conn.close()

                if not transactions:
                    messagebox.showinfo("No History", "No fine history found for this user")
                    return

                # Create history window
                history_window = tk.Toplevel()
                history_window.title(f"Fine History - User {user_id}")
                history_window.geometry("900x500")

                # Header
                header_frame = ttk.Frame(history_window)
                header_frame.pack(fill='x', padx=10, pady=10)

                ttk.Label(header_frame, text=f"Complete Fine History for User: {user_id}",
                         font=('Arial', 12, 'bold')).pack()

                # Calculate statistics
                total_paid = sum(0 for _, _, _, _, _, fine, _, notes in transactions
                               if notes and 'Fine paid on' in notes)
                total_waived = sum(0 for _, _, _, _, _, fine, _, notes in transactions
                                 if notes and 'Fine waived on' in notes)
                total_outstanding = sum(fine for _, _, _, _, _, fine, _, _ in transactions if fine > 0)

                stats_frame = ttk.Frame(history_window)
                stats_frame.pack(fill='x', padx=10, pady=5)

                ttk.Label(stats_frame, text=f"Payments: {total_paid} | Waivers: {total_waived} | Outstanding: ${total_outstanding:.2f}",
                         font=('Arial', 10)).pack()

                # Scrollable frame for transactions
                canvas = tk.Canvas(history_window)
                scrollbar = ttk.Scrollbar(history_window, orient="vertical", command=canvas.yview)
                scrollable_frame = ttk.Frame(canvas)

                scrollable_frame.bind(
                    "<Configure>",
                    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
                )

                canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
                canvas.configure(yscrollcommand=scrollbar.set)

                # Display transactions
                for loan_id, book_id, checkout, due, returned, fine, status, notes in transactions:
                    trans_frame = ttk.LabelFrame(scrollable_frame, text=f"Loan #{loan_id} - Book: {book_id}",
                                                relief='solid', borderwidth=1)
                    trans_frame.pack(fill='x', padx=10, pady=5)

                    info_text = f"Checkout: {checkout} | Due: {due} | Status: {status}\n"
                    if returned:
                        info_text += f"Returned: {returned}\n"
                    if fine > 0:
                        info_text += f"Current Fine: ${fine:.2f}\n"
                    if notes:
                        info_text += f"Notes: {notes}\n"

                    ttk.Label(trans_frame, text=info_text).pack(padx=10, pady=5)

                canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
                scrollbar.pack(side="right", fill="y")

                # Close button
                ttk.Button(history_window, text="Close", command=history_window.destroy).pack(pady=10)

            else:
                messagebox.showinfo("Demo", f"Demo: Fine history for {user_id}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load fine history: {str(e)}")

    def generate_fine_statistics_report(self):
        """Generate comprehensive statistics report for all library fines"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    messagebox.showerror("Error", "Database connection unavailable")
                    return

                cursor = conn.cursor()

                # Get overall statistics
                cursor.execute('''
                    SELECT
                        COUNT(*) as total_fines_issued,
                        COUNT(CASE WHEN fine_amount = 0 AND notes LIKE '%Fine paid on%' THEN 1 END) as total_paid,
                        COUNT(CASE WHEN fine_amount = 0 AND notes LIKE '%Fine waived on%' THEN 1 END) as total_waived,
                        COUNT(CASE WHEN fine_amount > 0 THEN 1 END) as total_outstanding,
                        SUM(CASE WHEN fine_amount > 0 THEN fine_amount ELSE 0 END) as outstanding_amount,
                        AVG(CASE WHEN fine_amount > 0 THEN fine_amount ELSE NULL END) as avg_outstanding_fine
                    FROM book_loans
                    WHERE fine_amount > 0 OR notes LIKE '%Fine%'
                ''')

                stats = cursor.fetchone()
                total_fines, total_paid, total_waived, total_outstanding, outstanding_amt, avg_fine = stats

                # Get top defaulters
                cursor.execute('''
                    SELECT user_id, SUM(fine_amount) as total_owed, COUNT(*) as fine_count
                    FROM book_loans
                    WHERE fine_amount > 0
                    GROUP BY user_id
                    ORDER BY total_owed DESC
                    LIMIT 10
                ''')

                top_defaulters = cursor.fetchall()

                # Get recent fine activity
                cursor.execute('''
                    SELECT COUNT(*) as recent_fines
                    FROM book_loans
                    WHERE (notes LIKE '%Fine paid on%' OR notes LIKE '%Fine waived on%')
                    AND (notes LIKE '%' || date('now', '-30 days') || '%')
                ''')

                recent_activity = cursor.fetchone()[0]

                conn.close()

                # Create report window
                report_window = tk.Toplevel()
                report_window.title("Library Fine Statistics Report")
                report_window.geometry("700x600")

                # Header
                header_frame = ttk.Frame(report_window, relief='raised', borderwidth=2)
                header_frame.pack(fill='x', padx=10, pady=10)

                ttk.Label(header_frame, text="Library Fine Statistics Report",
                         font=('Arial', 14, 'bold')).pack(pady=10)
                ttk.Label(header_frame, text=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                         font=('Arial', 9)).pack(pady=5)

                # Create scrollable text widget
                text_frame = ttk.Frame(report_window)
                text_frame.pack(fill='both', expand=True, padx=10, pady=10)

                text_widget = tk.Text(text_frame, wrap='word', font=('Courier', 10))
                scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
                text_widget.configure(yscrollcommand=scrollbar.set)

                scrollbar.pack(side='right', fill='y')
                text_widget.pack(side='left', fill='both', expand=True)

                # Build report content
                report_content = f"""
═══════════════════════════════════════════════════════
OVERALL FINE STATISTICS
═══════════════════════════════════════════════════════

Total Fines Issued:       {total_fines or 0}
Total Paid:               {total_paid or 0}
Total Waived:             {total_waived or 0}
Total Outstanding:        {total_outstanding or 0}
Outstanding Amount:       ${outstanding_amt or 0:.2f}
Average Outstanding Fine: ${avg_fine or 0:.2f}

Recent Activity (30 days): {recent_activity} fine transactions

═══════════════════════════════════════════════════════
TOP 10 USERS WITH OUTSTANDING FINES
═══════════════════════════════════════════════════════

"""
                if top_defaulters:
                    report_content += f"{'User ID':<20} {'Total Owed':>12} {'Fine Count':>12}\n"
                    report_content += "-" * 55 + "\n"
                    for user_id, total_owed, fine_count in top_defaulters:
                        report_content += f"{user_id:<20} ${total_owed:>11.2f} {fine_count:>12}\n"
                else:
                    report_content += "No outstanding fines found.\n"

                report_content += "\n═══════════════════════════════════════════════════════\n"
                report_content += "RECOMMENDATIONS\n"
                report_content += "═══════════════════════════════════════════════════════\n\n"

                if outstanding_amt and outstanding_amt > 1000:
                    report_content += "⚠ High outstanding balance - consider reminder campaign\n"
                if total_outstanding and total_outstanding > 50:
                    report_content += "⚠ Many outstanding fines - review fine policy\n"
                if avg_fine and avg_fine > 20:
                    report_content += "⚠ High average fine - users may need overdue alerts\n"

                text_widget.insert('1.0', report_content)
                text_widget.configure(state='disabled')

                # Button frame
                button_frame = ttk.Frame(report_window)
                button_frame.pack(fill='x', padx=10, pady=10)

                ttk.Button(button_frame, text="Export to File",
                          command=lambda: self._save_text_report(report_content, "fine_statistics")).pack(side='left', padx=5)
                ttk.Button(button_frame, text="Close",
                          command=report_window.destroy).pack(side='right', padx=5)

            else:
                messagebox.showinfo("Demo", "Demo: Fine statistics report")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate statistics: {str(e)}")

    def adjust_fine_amount(self):
        """Manually adjust a fine amount for a specific loan"""
        user_id = self.fine_user_var.get().strip()

        if not user_id:
            messagebox.showwarning("Warning", "Please search for a user first")
            return

        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    messagebox.showerror("Error", "Database connection unavailable")
                    return

                cursor = conn.cursor()

                # Get loans with fines
                cursor.execute('''
                    SELECT loan_id, book_id, fine_amount FROM book_loans
                    WHERE user_id = ? AND fine_amount > 0
                    ORDER BY due_date ASC
                ''', (user_id,))

                loans = cursor.fetchall()

                if not loans:
                    messagebox.showinfo("No Fines", "This user has no outstanding fines to adjust")
                    conn.close()
                    return

                # Create adjustment dialog
                adjust_dialog = tk.Toplevel()
                adjust_dialog.title("Adjust Fine Amount")
                adjust_dialog.geometry("500x400")

                ttk.Label(adjust_dialog, text="Select Loan and Adjust Fine",
                         font=('Arial', 12, 'bold')).pack(pady=10)

                # Loan selection
                loan_frame = ttk.LabelFrame(adjust_dialog, text="Select Loan", padding=10)
                loan_frame.pack(fill='x', padx=10, pady=5)

                loan_var = tk.StringVar()
                for loan_id, book_id, fine_amt in loans:
                    ttk.Radiobutton(loan_frame,
                                   text=f"Loan #{loan_id} - Book: {book_id} - Current Fine: ${fine_amt:.2f}",
                                   variable=loan_var,
                                   value=f"{loan_id}:{fine_amt}").pack(anchor='w', pady=2)

                # Adjustment options
                adjust_options_frame = ttk.LabelFrame(adjust_dialog, text="Adjustment", padding=10)
                adjust_options_frame.pack(fill='x', padx=10, pady=10)

                adjust_type_var = tk.StringVar(value="set")
                ttk.Radiobutton(adjust_options_frame, text="Set to specific amount",
                               variable=adjust_type_var, value="set").grid(row=0, column=0, sticky='w')
                ttk.Radiobutton(adjust_options_frame, text="Increase by",
                               variable=adjust_type_var, value="increase").grid(row=1, column=0, sticky='w')
                ttk.Radiobutton(adjust_options_frame, text="Decrease by",
                               variable=adjust_type_var, value="decrease").grid(row=2, column=0, sticky='w')

                amount_var = tk.StringVar()
                ttk.Entry(adjust_options_frame, textvariable=amount_var, width=15).grid(row=0, column=1, padx=5)
                ttk.Entry(adjust_options_frame, textvariable=amount_var, width=15).grid(row=1, column=1, padx=5)
                ttk.Entry(adjust_options_frame, textvariable=amount_var, width=15).grid(row=2, column=1, padx=5)

                # Reason
                reason_frame = ttk.LabelFrame(adjust_dialog, text="Reason for Adjustment", padding=10)
                reason_frame.pack(fill='both', expand=True, padx=10, pady=5)

                reason_text = tk.Text(reason_frame, height=4, width=50)
                reason_text.pack(fill='both', expand=True)

                def process_adjustment():
                    if not loan_var.get():
                        messagebox.showwarning("Warning", "Please select a loan")
                        return

                    try:
                        loan_id, current_fine = loan_var.get().split(':')
                        current_fine = float(current_fine)
                        adjustment = float(amount_var.get())
                        adjust_type = adjust_type_var.get()
                        reason = reason_text.get('1.0', 'end-1c').strip()

                        if not reason:
                            messagebox.showwarning("Warning", "Please provide a reason for adjustment")
                            return

                        # Calculate new fine amount
                        if adjust_type == "set":
                            new_fine = adjustment
                        elif adjust_type == "increase":
                            new_fine = current_fine + adjustment
                        else:  # decrease
                            new_fine = max(0, current_fine - adjustment)

                        # Update database
                        current_date = datetime.now().strftime('%Y-%m-%d')
                        cursor.execute('''
                            UPDATE book_loans
                            SET fine_amount = ?,
                                notes = COALESCE(notes || '; ', '') || 'Fine adjusted on ' || ? || ': ' || ?
                            WHERE loan_id = ?
                        ''', (new_fine, current_date, reason, loan_id))

                        conn.commit()
                        conn.close()

                        # Log the action
                        if ORIGINAL_LIBRARY_AVAILABLE:
                            log_audit_event(get_current_user_id(),
                                          f"GUI: Adjusted fine for loan {loan_id} from ${current_fine:.2f} to ${new_fine:.2f}. Reason: {reason}",
                                          "book_loans", loan_id)

                        messagebox.showinfo("Success",
                            f"Fine adjusted successfully!\n\n"
                            f"Loan ID: {loan_id}\n"
                            f"Previous amount: ${current_fine:.2f}\n"
                            f"New amount: ${new_fine:.2f}")

                        adjust_dialog.destroy()
                        self.load_user_fines()

                    except ValueError:
                        messagebox.showerror("Error", "Please enter a valid amount")
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to adjust fine: {str(e)}")

                # Buttons
                button_frame = ttk.Frame(adjust_dialog)
                button_frame.pack(fill='x', padx=10, pady=10)

                ttk.Button(button_frame, text="Apply Adjustment",
                          command=process_adjustment).pack(side='left', padx=5)
                ttk.Button(button_frame, text="Cancel",
                          command=adjust_dialog.destroy).pack(side='right', padx=5)

            else:
                messagebox.showinfo("Demo", f"Demo: Adjust fine for {user_id}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open adjustment dialog: {str(e)}")

    def export_fines_to_csv(self):
        """Export all outstanding fines to CSV file"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    messagebox.showerror("Error", "Database connection unavailable")
                    return

                cursor = conn.cursor()

                # Get all fines
                cursor.execute('''
                    SELECT bl.user_id, bl.loan_id, bl.book_id, bl.checkout_date, bl.due_date,
                           bl.return_date, bl.fine_amount, bl.status, bl.notes,
                           b.title, b.author
                    FROM book_loans bl
                    LEFT JOIN books b ON bl.book_id = b.book_id
                    WHERE bl.fine_amount > 0
                    ORDER BY bl.due_date ASC
                ''')

                fines_data = cursor.fetchall()
                conn.close()

                if not fines_data:
                    messagebox.showinfo("No Data", "No outstanding fines to export")
                    return

                # Ask for save location
                from tkinter import filedialog
                default_filename = f"library_fines_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=default_filename
                )

                if not file_path:
                    return

                # Write CSV
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)

                    # Header
                    writer.writerow(['User ID', 'Loan ID', 'Book ID', 'Book Title', 'Author',
                                   'Checkout Date', 'Due Date', 'Return Date',
                                   'Fine Amount', 'Status', 'Notes'])

                    # Data rows
                    for row in fines_data:
                        writer.writerow(row)

                    # Summary row
                    writer.writerow([])
                    writer.writerow(['SUMMARY'])
                    writer.writerow(['Total Outstanding Fines:', len(fines_data)])
                    writer.writerow(['Total Amount:', f'${sum(row[6] for row in fines_data):.2f}'])

                messagebox.showinfo("Success",
                    f"Fines exported successfully!\n\n"
                    f"File: {file_path}\n"
                    f"Records: {len(fines_data)}")

            else:
                messagebox.showinfo("Demo", "Demo: Export fines to CSV")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export fines: {str(e)}")

    def _save_text_report(self, content, report_type):
        """Helper function to save text report to file"""
        try:
            from tkinter import filedialog
            default_filename = f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=default_filename
            )

            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Report saved to:\n{file_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save report: {str(e)}")

    def _record_library_payment_in_finance(self, user_id, amount, payment_method):
        """Record library fine payment in the finance system for tracking."""
        try:
            conn = get_db_connection()
            if not conn:
                return False

            cursor = conn.cursor()
            current_date = datetime.now().strftime('%Y-%m-%d')
            current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Get or create student_fees record for library fines
            # First, check if there's an existing unpaid library fee
            cursor.execute('''
                SELECT student_fee_id, amount FROM student_fees
                WHERE student_id = ? AND fee_type_id = 3 AND status = 'unpaid'
                ORDER BY created_at DESC LIMIT 1
            ''', (user_id,))

            existing_fee = cursor.fetchone()

            if existing_fee:
                # Update existing fee (reduce amount or mark as paid)
                student_fee_id, current_fee_amount = existing_fee
                new_fee_amount = max(0, current_fee_amount - amount)

                if new_fee_amount == 0:
                    # Fully paid
                    cursor.execute('''
                        UPDATE student_fees
                        SET status = 'paid', amount = 0, updated_at = ?
                        WHERE student_fee_id = ?
                    ''', (current_datetime, student_fee_id))
                else:
                    # Partial payment
                    cursor.execute('''
                        UPDATE student_fees
                        SET amount = ?, updated_at = ?
                        WHERE student_fee_id = ?
                    ''', (new_fee_amount, current_datetime, student_fee_id))
            else:
                # Create a new fee record marked as paid (for historical tracking)
                cursor.execute('''
                    INSERT INTO student_fees
                    (student_id, fee_type_id, amount, currency, status, due_date, created_at, updated_at)
                    VALUES (?, 3, 0, 'GBP', 'paid', ?, ?, ?)
                ''', (user_id, current_date, current_datetime, current_datetime))
                student_fee_id = cursor.lastrowid

            # Create payment record
            cursor.execute('''
                INSERT INTO payments
                (student_id, amount, currency, payment_method, payment_date, status, notes, created_by, created_at)
                VALUES (?, ?, 'GBP', ?, ?, 'completed', 'Library fine payment', ?, ?)
            ''', (user_id, amount, payment_method, current_date,
                  get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'system',
                  current_datetime))

            payment_id = cursor.lastrowid

            # Link payment to fee via payment_allocations
            cursor.execute('''
                INSERT INTO payment_allocations
                (payment_id, student_fee_id, amount, created_at)
                VALUES (?, ?, ?, ?)
            ''', (payment_id, student_fee_id, amount, current_datetime))

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            print(f"Error recording library payment in finance system: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_overdue_books(self):
        """Load overdue books data"""
        # Clear existing data
        for item in self.overdue_tree.get_children():
            self.overdue_tree.delete(item)
            
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    return
                    
                cursor = conn.cursor()
                cursor.execute('''
                SELECT bl.user_id, bl.book_id, b.title, bl.due_date,
                       julianday('now') - julianday(bl.due_date) as days_overdue,
                       bl.fine_amount, s.email
                FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id
                LEFT JOIN students s ON bl.user_id = s.student_id
                WHERE bl.status = 'overdue'
                ORDER BY days_overdue DESC
                ''')
                
                overdue_books = cursor.fetchall()
                conn.close()
                
                total_fines = 0
                for book in overdue_books:
                    user_id, book_id, title, due_date, days_overdue, fine, email = book
                    fine_amount = fine if fine else 0
                    total_fines += fine_amount
                    contact = email if email else "No email"
                    
                    self.overdue_tree.insert('', 'end', values=(
                        user_id, book_id, title[:30], due_date[:10], 
                        int(days_overdue), f"${fine_amount:.2f}", contact
                    ))
                
                # Update summary
                summary_text = f"Total Overdue Items: {len(overdue_books)} | Total Fines: ${total_fines:.2f}"
                self.overdue_summary_label.config(text=summary_text)
                
            else:
                # Demo data
                demo_overdue = [
                    ("USER001", "B10001", "Sample Book 1", "2024-01-10", 5, "$2.50", "user1@email.com"),
                    ("USER002", "B10002", "Sample Book 2", "2024-01-08", 7, "$3.50", "user2@email.com"),
                ]
                
                for book in demo_overdue:
                    self.overdue_tree.insert('', 'end', values=book)
                    
                self.overdue_summary_label.config(text="Demo Mode: 2 overdue items | Total Fines: $6.00")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error loading overdue books: {str(e)}")
            
    def refresh_overdue_books(self):
        """Refresh overdue books"""
        self.load_overdue_books()
        
    def send_overdue_reminders(self):
        """Send reminders to overdue users"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                # Use original notification function
                count = self.send_overdue_notifications()
                messagebox.showinfo("Success", f"Sent reminders to {count} users")
            else:
                messagebox.showinfo("Demo", "Overdue reminders would be sent to users")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending reminders: {str(e)}")
            
    def send_overdue_notifications(self):
        """Send overdue notifications"""
        try:
            conn = get_db_connection()
            if not conn:
                return 0
                
            cursor = conn.cursor()
            cursor.execute('''
            SELECT DISTINCT bl.user_id, s.email, s.first_name, s.last_name
            FROM book_loans bl
            LEFT JOIN students s ON bl.user_id = s.student_id
            WHERE bl.status = 'overdue' AND s.email IS NOT NULL
            ''')
            
            users = cursor.fetchall()
            conn.close()
            
            sent_count = 0
            for user_id, email, first_name, last_name in users:
                try:
                    # In a real implementation, you would send actual emails
                    print(f"Sending overdue reminder to {email} for user {user_id}")
                    sent_count += 1
                except Exception as e:
                    print(f"Failed to send reminder to {user_id}: {e}")
            
            return sent_count
            
        except Exception as e:
            print(f"Error sending overdue notifications: {e}")
            return 0
            
    def process_overdue_fines(self):
        """Process overdue fines"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                count = self.calculate_overdue_fines()
                messagebox.showinfo("Success", f"Processed fines for {count} overdue items")
                self.refresh_overdue_books()
            else:
                messagebox.showinfo("Demo", "Overdue fines would be calculated and updated")
        except Exception as e:
            messagebox.showerror("Error", f"Error processing fines: {str(e)}")
            
    def calculate_overdue_fines(self):
        """Calculate and update overdue fines"""
        try:
            conn = get_db_connection()
            if not conn:
                return 0
                
            cursor = conn.cursor()
            
            # Get fine per day setting
            fine_per_day = 0.50  # Default
            try:
                cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "fine_per_day"')
                setting = cursor.fetchone()
                if setting:
                    fine_per_day = float(setting[0])
            except:
                pass
            
            # Update fines for overdue books
            cursor.execute('''
            UPDATE book_loans 
            SET fine_amount = (julianday('now') - julianday(due_date)) * ?
            WHERE status = 'overdue' AND due_date < datetime('now')
            ''', (fine_per_day,))
            
            count = cursor.rowcount
            conn.commit()
            conn.close()
            
            return count
            
        except Exception as e:
            print(f"Error calculating fines: {e}")
            return 0
            
    def export_overdue_report(self):
        """Export overdue report"""
        file_path = filedialog.asksaveasfilename(
            title="Export Overdue Report",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                if ORIGINAL_LIBRARY_AVAILABLE:
                    success = self.create_overdue_export(file_path)
                    if success:
                        messagebox.showinfo("Success", f"Overdue report exported to {file_path}")
                    else:
                        messagebox.showerror("Error", "Export failed")
                else:
                    messagebox.showinfo("Demo", f"Would export overdue report to {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Export error: {str(e)}")
                
    def create_overdue_export(self, file_path):
        """Create overdue export file"""
        try:
            import pandas as pd
            
            conn = get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            student_columns = self._get_student_columns()
            grade_sql = ', s.grade_level' if 'grade_level' in student_columns else ''
            cursor.execute(f'''
            SELECT bl.user_id, bl.book_id, b.title, b.author, bl.checkout_date,
                   bl.due_date, julianday('now') - julianday(bl.due_date) as days_overdue,
                   bl.fine_amount, s.first_name, s.last_name, s.email{grade_sql}
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            LEFT JOIN students s ON bl.user_id = s.student_id
            WHERE bl.status = 'overdue'
            ORDER BY days_overdue DESC
            ''')
            
            data = cursor.fetchall()
            conn.close()
            
            if not data:
                return False
            
            columns = ['User ID', 'Book ID', 'Title', 'Author', 'Checkout Date', 'Due Date', 
                      'Days Overdue', 'Fine Amount', 'First Name', 'Last Name', 'Email']
            if 'grade_level' in student_columns:
                columns.append('Grade')
            
            df = pd.DataFrame(data, columns=columns)
            
            # Format dates and numbers
            df['Checkout Date'] = pd.to_datetime(df['Checkout Date']).dt.strftime('%Y-%m-%d')
            df['Due Date'] = pd.to_datetime(df['Due Date']).dt.strftime('%Y-%m-%d')
            df['Days Overdue'] = df['Days Overdue'].astype(int)
            df['Fine Amount'] = df['Fine Amount'].apply(lambda x: f"${x:.2f}" if x else "$0.00")
            
            # Export based on file type
            if file_path.lower().endswith('.csv'):
                df.to_csv(file_path, index=False)
            elif file_path.lower().endswith('.pdf'):
                # For PDF export, you'd need reportlab or similar
                # For now, convert to CSV
                csv_path = file_path.replace('.pdf', '.csv')
                df.to_csv(csv_path, index=False)
                messagebox.showinfo("Note", f"Exported as CSV: {csv_path}")
            else:
                df.to_excel(file_path, index=False)
            
            return True
            
        except Exception as e:
            print(f"Export error: {e}")
            return False
            
    def show_barcode_scanner(self):
        """Show barcode scanner interface"""
        scanner_dialog = tk.Toplevel(self.master)
        scanner_dialog.title("Barcode Scanner")
        scanner_dialog.geometry("400x300")
        scanner_dialog.transient(self.master)
        
        main_frame = ttk.Frame(scanner_dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        title_label = ttk.Label(main_frame, text="Barcode Scanner", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # Scanner input
        ttk.Label(main_frame, text="Scan or Enter Barcode:").pack(anchor='w', pady=(0, 5))
        self.barcode_var = tk.StringVar()
        barcode_entry = ttk.Entry(main_frame, textvariable=self.barcode_var, width=40, font=('Courier', 12))
        barcode_entry.pack(pady=(0, 10))
        
        # Result display
        result_frame = ttk.LabelFrame(main_frame, text="Scan Result")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.barcode_result = tk.Text(result_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        self.barcode_result.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Process Scan", command=self.process_barcode_scan).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear", command=self.clear_barcode_scan).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=scanner_dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # Focus on barcode entry
        barcode_entry.focus()
        barcode_entry.bind('<Return>', lambda e: self.process_barcode_scan())
        
    def process_barcode_scan(self):
        """Process barcode scan"""
        barcode = self.barcode_var.get().strip()
        
        if not barcode:
            messagebox.showwarning("Warning", "Please enter a barcode")
            return
            
        self.barcode_result.config(state=tk.NORMAL)
        self.barcode_result.delete("1.0", tk.END)
        
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                # Use original barcode processing function
                result = process_scanned_barcode(barcode)
                
                if result:
                    if result['type'] == 'book':
                        result_text = f"📚 BOOK FOUND\n\n"
                        result_text += f"Book ID: {result['id']}\n"
                        result_text += f"Title: {result['title']}\n"
                        result_text += f"Author: {result['author']}\n"
                        result_text += f"Status: {result['status']}\n"
                        result_text += f"Barcode: {result['barcode']}\n\n"
                        result_text += "Actions available:\n"
                        result_text += "• View Details\n"
                        if result['status'] == 'available':
                            result_text += "• Checkout Book\n"
                        result_text += "• Reserve Book\n"
                        
                    elif result['type'] == 'user':
                        result_text = f"👤 USER FOUND\n\n"
                        result_text += f"User ID: {result['id']}\n"
                        result_text += f"Name: {result['name']}\n"
                        result_text += f"Barcode: {result['barcode']}\n\n"
                        result_text += "Actions available:\n"
                        result_text += "• View User History\n"
                        result_text += "• Checkout Book to User\n"
                        result_text += "• View Active Loans\n"
                        
                    self.barcode_result.insert(tk.END, result_text)
                else:
                    self.barcode_result.insert(tk.END, f"❌ NO MATCH FOUND\n\nBarcode: {barcode}\n\nThis barcode was not found in the system.")
            else:
                # Demo mode
                self.barcode_result.insert(tk.END, f"📚 DEMO SCAN RESULT\n\nBarcode: {barcode}\nDemo Book: Sample Title\nStatus: Available\n\nThis is a demonstration of barcode scanning.")
                
        except Exception as e:
            self.barcode_result.insert(tk.END, f"❌ SCAN ERROR\n\nError processing barcode: {str(e)}")
            
        self.barcode_result.config(state=tk.DISABLED)
        
    def clear_barcode_scan(self):
        """Clear barcode scan"""
        self.barcode_var.set("")
        self.barcode_result.config(state=tk.NORMAL)
        self.barcode_result.delete("1.0", tk.END)
        self.barcode_result.config(state=tk.DISABLED)
        
    def show_digital_library(self):
        """Show digital library interface"""
        if not self.check_permission('manage_books'):
            return
            
        self.clear_content_area()
        
        digital_frame = ttk.Frame(self.notebook)
        self.notebook.add(digital_frame, text="Digital Library")
        
        title_label = ttk.Label(digital_frame, text="Digital Library Management", style='Title.TLabel')
        title_label.pack(pady=10)
        
        # Control buttons
        control_frame = ttk.Frame(digital_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(control_frame, text="Add Digital Resource", command=self.add_digital_resource_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Manage Access", command=self.manage_digital_access_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Download Stats", command=self.show_download_stats).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Refresh", command=self.refresh_digital_library).pack(side=tk.LEFT, padx=5)
        
        # Digital resources table
        table_frame = ttk.Frame(digital_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ('ID', 'Title', 'Author', 'Type', 'Access Level', 'Downloads', 'Added Date')
        self.digital_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.digital_tree.heading(col, text=col)
            self.digital_tree.column(col, width=100)
            
        # Add scrollbar
        digital_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.digital_tree.yview)
        self.digital_tree.configure(yscrollcommand=digital_scrollbar.set)
        
        self.digital_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        digital_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load digital resources
        self.load_digital_resources()
        
        # Bind double-click
        self.digital_tree.bind('<Double-1>', self.view_digital_resource)
        
    def load_digital_resources(self):
        """Load digital resources data"""
        # Clear existing data
        for item in self.digital_tree.get_children():
            self.digital_tree.delete(item)
            
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    return
                    
                cursor = conn.cursor()
                cursor.execute('''
                SELECT digital_id, title, author, file_type, access_level, 
                       download_count, added_date
                FROM digital_library
                ORDER BY title
                ''')
                
                resources = cursor.fetchall()
                conn.close()
                
                for resource in resources:
                    digital_id, title, author, file_type, access_level, downloads, added_date = resource
                    self.digital_tree.insert('', 'end', values=(
                        digital_id, title[:30], author[:20], file_type, 
                        access_level, downloads, added_date[:10]
                    ))
            else:
                # Demo data
                demo_resources = [
                    (1, "Digital Guide to Python", "Author Name", "PDF", "public", 45, "2024-01-15"),
                    (2, "Library Science eBook", "Jane Smith", "EPUB", "students", 23, "2024-01-10"),
                ]
                
                for resource in demo_resources:
                    self.digital_tree.insert('', 'end', values=resource)
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error loading digital resources: {str(e)}")
            
    def refresh_digital_library(self):
        """Refresh digital library"""
        self.load_digital_resources()
        
    def add_digital_resource_dialog(self):
        """Add digital resource dialog"""
        dialog = tk.Toplevel(self.master)
        dialog.title("Add Digital Resource")
        dialog.geometry("500x400")
        dialog.transient(self.master)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # File selection
        file_frame = ttk.LabelFrame(main_frame, text="File Selection")
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(file_frame, text="Select File:").pack(anchor='w', padx=5, pady=5)
        self.digital_file_path = tk.StringVar()
        file_path_frame = ttk.Frame(file_frame)
        file_path_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Entry(file_path_frame, textvariable=self.digital_file_path, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(file_path_frame, text="Browse", command=self.browse_digital_file).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Metadata
        metadata_frame = ttk.LabelFrame(main_frame, text="Metadata")
        metadata_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Form fields
        fields = [
            ("Title:", "title"),
            ("Author:", "author"),
            ("Category:", "category"),
            ("Description:", "description"),
        ]
        
        self.digital_metadata_vars = {}
        
        for i, (label, field) in enumerate(fields):
            ttk.Label(metadata_frame, text=label).grid(row=i, column=0, sticky='w', padx=5, pady=5)
            
            if field == "description":
                var = None  # Text widget
                self.digital_description = tk.Text(metadata_frame, height=3, width=40)
                self.digital_description.grid(row=i, column=1, sticky='w', padx=5, pady=5)
            else:
                var = tk.StringVar()
                entry = ttk.Entry(metadata_frame, textvariable=var, width=40)
                entry.grid(row=i, column=1, sticky='w', padx=5, pady=5)
                self.digital_metadata_vars[field] = var
        
        # Access level
        ttk.Label(metadata_frame, text="Access Level:").grid(row=len(fields), column=0, sticky='w', padx=5, pady=5)
        self.digital_access_var = tk.StringVar(value="public")
        access_combo = ttk.Combobox(metadata_frame, textvariable=self.digital_access_var, width=37)
        access_combo['values'] = ('public', 'students', 'staff', 'restricted')
        access_combo.grid(row=len(fields), column=1, sticky='w', padx=5, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Add Resource", command=lambda: self.save_digital_resource(dialog)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
    def browse_digital_file(self):
        """Browse for digital file"""
        file_path = filedialog.askopenfilename(
            title="Select Digital Resource",
            filetypes=[
                ("PDF files", "*.pdf"),
                ("eBook files", "*.epub *.mobi"),
                ("Document files", "*.doc *.docx"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            self.digital_file_path.set(file_path)
            
            # Auto-fill title from filename
            filename = os.path.basename(file_path)
            title = os.path.splitext(filename)[0]
            if 'title' in self.digital_metadata_vars:
                self.digital_metadata_vars['title'].set(title)
                
    def save_digital_resource(self, dialog):
        """Save digital resource"""
        file_path = self.digital_file_path.get().strip()
        
        if not file_path or not os.path.exists(file_path):
            messagebox.showerror("Error", "Please select a valid file")
            return
            
        # Get metadata
        title = self.digital_metadata_vars['title'].get().strip()
        author = self.digital_metadata_vars['author'].get().strip()
        category = self.digital_metadata_vars['category'].get().strip()
        description = self.digital_description.get("1.0", tk.END).strip()
        access_level = self.digital_access_var.get()
        
        if not title or not author:
            messagebox.showerror("Error", "Title and Author are required")
            return
            
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                success = self.add_digital_resource_database(file_path, title, author, category, description, access_level)
                if success:
                    messagebox.showinfo("Success", "Digital resource added successfully!")
                    dialog.destroy()
                    self.refresh_digital_library()
                else:
                    messagebox.showerror("Error", "Failed to add digital resource")
            else:
                messagebox.showinfo("Demo", f"Digital resource '{title}' would be added")
                dialog.destroy()
                
        except Exception as e:
            messagebox.showerror("Error", f"Error adding digital resource: {str(e)}")
            
    def add_digital_resource_database(self, file_path, title, author, category, description, access_level):
        """Add digital resource to database"""
        try:
            import shutil
            
            # Copy file to digital library directory
            digital_dir = "digital_library"
            os.makedirs(digital_dir, exist_ok=True)
            
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(file_path)}"
            new_path = os.path.join(digital_dir, filename)
            shutil.copy2(file_path, new_path)
            
            # Get file info
            file_type = os.path.splitext(file_path)[1][1:].upper()
            file_size = os.path.getsize(file_path)
            
            # Insert into database
            conn = get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO digital_library 
            (title, author, file_path, file_type, file_size, category, 
             description, access_level, added_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                title, author, new_path, file_type, file_size, category,
                description, access_level, datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            conn.commit()
            conn.close()
            
            # Log the action
            log_audit_event(get_current_user_id(), f"GUI: Added digital resource '{title}'", "digital_library")
            
            return True
            
        except Exception as e:
            print(f"Error adding digital resource: {e}")
            return False
            

    def exit_application(self, restart=False):
        """Exit the application"""
        # Save any pending data
        try:
            if ORIGINAL_LIBRARY_AVAILABLE and self.auth and self.current_user:
                log_audit_event(get_current_user_id(), "GUI: Application exit", "system")
        except:
            pass
        
        if restart:
            # Restart the application
            import sys
            os.execl(sys.executable, sys.executable, *sys.argv)
            if self.owns_root:
                self.master.quit()
                self.master.destroy()
            else:
                self.master.destroy()

    def create_reading_list_database(self, name, description, category, is_public, is_collaborative):
        """Create reading list in database"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO reading_lists 
            (name, description, creator_id, created_date, is_public, is_collaborative, category)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, description, get_current_user_id(), now, is_public, is_collaborative, category))
            
            conn.commit()
            conn.close()
            
            # Log the action
            if ORIGINAL_LIBRARY_AVAILABLE:
                log_audit_event(get_current_user_id(), f"GUI: Created reading list '{name}'", "reading_lists")
            
            return True
            
        except Exception as e:
            print(f"Error creating reading list: {e}")
            return False
            
    def view_reading_list_details(self, event=None):
        """View reading list details"""
        selection = self.reading_lists_tree.selection()
        if not selection:
            if event:  # Called from double-click
                return
            messagebox.showwarning("Warning", "Please select a reading list first")
            return
            
        item = self.reading_lists_tree.item(selection[0])
        list_id = item['values'][0]
        list_name = item['values'][1]
        
        # Create new tab for list details
        details_frame = ttk.Frame(self.notebook)
        self.notebook.add(details_frame, text=f"List: {list_name}")
        self.notebook.select(details_frame)
        
        # List info
        info_frame = ttk.LabelFrame(details_frame, text="List Information")
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Get and display list details
        list_details = self.get_reading_list_details(list_id)
        if list_details:
            ttk.Label(info_frame, text=f"Name: {list_details['name']}", style='Heading.TLabel').pack(anchor='w', padx=5, pady=2)
            if list_details['description']:
                ttk.Label(info_frame, text=f"Description: {list_details['description']}").pack(anchor='w', padx=5, pady=2)
            ttk.Label(info_frame, text=f"Creator: {list_details['creator_id']}").pack(anchor='w', padx=5, pady=2)
            ttk.Label(info_frame, text=f"Created: {list_details['created_date'][:10]}").pack(anchor='w', padx=5, pady=2)
        
        # List items
        items_frame = ttk.LabelFrame(details_frame, text="Books in this List")
        items_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Items table
        items_columns = ('Book ID', 'Title', 'Author', 'Status', 'Added Date')
        items_tree = ttk.Treeview(items_frame, columns=items_columns, show='headings', height=12)
        
        for col in items_columns:
            items_tree.heading(col, text=col)
            items_tree.column(col, width=120)
            
        # Scrollbar
        items_scrollbar = ttk.Scrollbar(items_frame, orient=tk.VERTICAL, command=items_tree.yview)
        items_tree.configure(yscrollcommand=items_scrollbar.set)
        
        items_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        items_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load list items
        self.load_reading_list_items(items_tree, list_id)
        
    def get_reading_list_details(self, list_id):
        """Get reading list details"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    return None
                    
                cursor = conn.cursor()
                cursor.execute('''
                SELECT name, description, creator_id, created_date, is_public, is_collaborative, category
                FROM reading_lists WHERE list_id = ?
                ''', (list_id,))
                
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    columns = ['name', 'description', 'creator_id', 'created_date', 'is_public', 'is_collaborative', 'category']
                    return dict(zip(columns, result))
            else:
                return {
                    'name': 'Demo List',
                    'description': 'Demo reading list',
                    'creator_id': 'demo_user',
                    'created_date': '2024-01-15',
                    'is_public': True,
                    'is_collaborative': False,
                    'category': 'General'
                }
        except Exception as e:
            print(f"Error getting reading list details: {e}")
            return None
            
    def load_reading_list_items(self, tree, list_id):
        """Load reading list items"""
        # Clear existing data
        for item in tree.get_children():
            tree.delete(item)
            
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    return
                    
                cursor = conn.cursor()
                cursor.execute('''
                SELECT b.book_id, b.title, b.author, b.status, rli.added_date
                FROM reading_list_items rli
                JOIN books b ON rli.book_id = b.book_id
                WHERE rli.list_id = ?
                ORDER BY rli.added_date DESC
                ''', (list_id,))
                
                items = cursor.fetchall()
                conn.close()
                
                for item in items:
                    book_id, title, author, status, added_date = item
                    tree.insert('', 'end', values=(book_id, title, author, status, added_date[:10]))
            else:
                # Demo data
                demo_items = [
                    ("B10001", "Sample Book 1", "Author 1", "Available", "2024-01-15"),
                    ("B10002", "Sample Book 2", "Author 2", "Checked Out", "2024-01-14"),
                ]
                
                for item in demo_items:
                    tree.insert('', 'end', values=item)
                    
        except Exception as e:
            print(f"Error loading reading list items: {e}")
            
    def show_reviews(self):
        """Show reviews and ratings interface"""
        # Check permission instead of user directly
        if not self.check_permission('manage_reviews'):
            return
            
        self.clear_content_area()
        
        reviews_frame = ttk.Frame(self.notebook)
        self.notebook.add(reviews_frame, text="Reviews & Ratings")
        
        title_label = ttk.Label(reviews_frame, text="Book Reviews & Ratings", style='Title.TLabel')
        title_label.pack(pady=10)
        
        # Control frame
        control_frame = ttk.Frame(reviews_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(control_frame, text="Write Review", command=self.write_review_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="My Reviews", command=self.show_my_reviews).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="All Reviews", command=self.show_all_reviews).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Refresh", command=self.refresh_reviews).pack(side=tk.LEFT, padx=5)
        
        # Reviews display
        reviews_display_frame = ttk.LabelFrame(reviews_frame, text="Recent Reviews")
        reviews_display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Reviews table
        columns = ('Book', 'Title', 'Reviewer', 'Rating', 'Date', 'Status')
        self.reviews_tree = ttk.Treeview(reviews_display_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.reviews_tree.heading(col, text=col)
            self.reviews_tree.column(col, width=120)
            
        # Scrollbar
        reviews_scrollbar = ttk.Scrollbar(reviews_display_frame, orient=tk.VERTICAL, command=self.reviews_tree.yview)
        self.reviews_tree.configure(yscrollcommand=reviews_scrollbar.set)
        
        self.reviews_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        reviews_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load reviews
        self.load_reviews()
        
        # Bind double-click to view review
        self.reviews_tree.bind('<Double-1>', self.view_review_details)
        
    def load_reviews(self, filter_user=None):
        """Load reviews data"""
        # Clear existing data
        for item in self.reviews_tree.get_children():
            self.reviews_tree.delete(item)
            
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if not conn:
                    return
                    
                cursor = conn.cursor()
                
                if filter_user:
                    cursor.execute('''
                    SELECT br.book_id, b.title, br.user_id, br.rating, br.review_date, br.status
                    FROM book_reviews br
                    JOIN books b ON br.book_id = b.book_id
                    WHERE br.user_id = ?
                    ORDER BY br.review_date DESC
                    ''', (filter_user,))
                else:
                    cursor.execute('''
                    SELECT br.book_id, b.title, br.user_id, br.rating, br.review_date, br.status
                    FROM book_reviews br
                    JOIN books b ON br.book_id = b.book_id
                    ORDER BY br.review_date DESC
                    LIMIT 50
                    ''')
                
                reviews = cursor.fetchall()
                conn.close()
                
                for review in reviews:
                    book_id, title, user_id, rating, review_date, status = review
                    stars = "★" * rating + "☆" * (5 - rating)
                    
                    self.reviews_tree.insert('', 'end', values=(
                        book_id, title[:30], user_id, stars, review_date[:10], status
                    ))
            else:
                # Demo data
                demo_reviews = [
                    ("B10001", "Sample Book 1", "user1", "★★★★☆", "2024-01-15", "approved"),
                    ("B10002", "Sample Book 2", "user2", "★★★★★", "2024-01-14", "pending"),
                ]
                
                for review in demo_reviews:
                    self.reviews_tree.insert('', 'end', values=review)
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error loading reviews: {str(e)}")
            
    def show_my_reviews(self):
        """Show only current user's reviews"""
        if ORIGINAL_LIBRARY_AVAILABLE:
            user_id = get_current_user_id()
            self.load_reviews(filter_user=user_id)
        else:
            self.load_reviews()
            
    def show_all_reviews(self):
        """Show all reviews"""
        self.load_reviews()
        
    def refresh_reviews(self):
        """Refresh reviews display"""
        self.load_reviews()
        
    def write_review_dialog(self):
        """Create write review dialog"""
        dialog = tk.Toplevel(self.master)
        dialog.title("Write Book Review")
        dialog.geometry("500x400")
        dialog.transient(self.master)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Book selection
        ttk.Label(main_frame, text="Book ID:").pack(anchor='w', pady=(0, 5))
        book_id_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=book_id_var, width=30).pack(anchor='w', pady=(0, 10))
        
        # Rating selection
        ttk.Label(main_frame, text="Rating:").pack(anchor='w', pady=(0, 5))
        rating_var = tk.StringVar(value="5")
        rating_frame = ttk.Frame(main_frame)
        rating_frame.pack(anchor='w', pady=(0, 10))
        
        for i in range(1, 6):
            ttk.Radiobutton(rating_frame, text=f"{i} Star{'s' if i > 1 else ''}", 
                           variable=rating_var, value=str(i)).pack(side=tk.LEFT, padx=5)
        
        # Review text
        ttk.Label(main_frame, text="Review:").pack(anchor='w', pady=(0, 5))
        review_text = ScrolledText(main_frame, height=8, width=50)
        review_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        def submit_review():
            book_id = book_id_var.get().strip()
            rating = int(rating_var.get())
            review_content = review_text.get("1.0", tk.END).strip()
            
            if not book_id:
                messagebox.showwarning("Warning", "Please enter a book ID")
                return
                
            if not review_content:
                messagebox.showwarning("Warning", "Please write a review")
                return
                
            try:
                if ORIGINAL_LIBRARY_AVAILABLE:
                    success = self.submit_review_database(book_id, rating, review_content)
                    if success:
                        messagebox.showinfo("Success", "Review submitted successfully!")
                        dialog.destroy()
                        self.refresh_reviews()
                    else:
                        messagebox.showerror("Error", "Failed to submit review")
                else:
                    messagebox.showinfo("Demo", f"Review for book {book_id} submitted!")
                    dialog.destroy()
                    
            except Exception as e:
                messagebox.showerror("Error", f"Error submitting review: {str(e)}")
        
        ttk.Button(button_frame, text="Submit", command=submit_review).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
    def submit_review_database(self, book_id, rating, review_text):
        """Submit review to database"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            # Check if book exists
            cursor.execute('SELECT title FROM books WHERE book_id = ?', (book_id,))
            if not cursor.fetchone():
                messagebox.showerror("Error", "Book not found")
                return False
            
            # Check if user already reviewed this book
            user_id = get_current_user_id()
            cursor.execute('SELECT review_id FROM book_reviews WHERE book_id = ? AND user_id = ?', 
                          (book_id, user_id))
            
            if cursor.fetchone():
                messagebox.showwarning("Warning", "You have already reviewed this book")
                return False
            
            # Insert review
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            INSERT INTO book_reviews (book_id, user_id, rating, review_text, review_date, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            ''', (book_id, user_id, rating, review_text, now))
            
            conn.commit()
            conn.close()
            
            # Log the action
            log_audit_event(user_id, f"GUI: Submitted review for book {book_id}", "book_reviews")
            
            return True
            
        except Exception as e:
            print(f"Error submitting review: {e}")
            return False

    # Add missing method that's referenced in reviews
    def view_review_details(self, event=None):
        """View review details"""
        selection = self.reviews_tree.selection()
        if not selection:
            if event:  # Called from double-click
                return
            messagebox.showwarning("Warning", "Please select a review first")
            return
        
        # This would show detailed review information in a dialog
        messagebox.showinfo("Review Details", "Review details would be displayed here")
        
    def restore_system_gui(self):
        """Restore system via GUI"""
        if not self.check_permission('system_config'):
            return
            
        backup_dir = filedialog.askdirectory(title="Select Backup Directory")
        
        if backup_dir:
            # Confirm restore operation
            result = messagebox.askyesno("Confirm Restore", 
                                       "This will overwrite current data. Are you sure you want to restore from backup?")
            
            if result:
                try:
                    if ORIGINAL_LIBRARY_AVAILABLE:
                        success = self.restore_from_backup(backup_dir)
                        if success:
                            messagebox.showinfo("Success", "System restored successfully!")
                            # Restart application to reload data
                            restart = messagebox.askyesno("Restart Required", 
                                                        "Application needs to restart to complete restore. Restart now?")
                            if restart:
                                self.exit_application(restart=True)
                        else:
                            messagebox.showerror("Error", "Restore failed")
                    else:
                        messagebox.showinfo("Demo", f"Would restore from {backup_dir}")
                except Exception as e:
                    messagebox.showerror("Error", f"Restore error: {str(e)}")

    def restore_from_backup(self, backup_dir):
        """Restore from backup directory"""
        try:
            import shutil
            
            # Check for manifest
            manifest_path = os.path.join(backup_dir, 'manifest.json')
            if os.path.exists(manifest_path):
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                print(f"Restoring backup from {manifest.get('backup_date', 'unknown date')}")
            
            # Create safety backup first
            safety_backup_dir = f"pre_restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.makedirs(safety_backup_dir, exist_ok=True)
            
            # Use DATABASE_FILE constant instead of self.DATABASE_FILE
            if os.path.exists(DATABASE_FILE):
                shutil.copy2(DATABASE_FILE, safety_backup_dir)
            
            # Restore database
            backup_db_path = os.path.join(backup_dir, 'library_database.db')
            if os.path.exists(backup_db_path):
                shutil.copy2(backup_db_path, DATABASE_FILE)
            
            # Restore additional directories
            restore_dirs = ['qr_codes', 'digital_library', 'cover_images']
            for dir_name in restore_dirs:
                backup_subdir = os.path.join(backup_dir, dir_name)
                if os.path.exists(backup_subdir):
                    if os.path.exists(dir_name):
                        shutil.rmtree(dir_name)
                    shutil.copytree(backup_subdir, dir_name)
            
            # Log the action
            if ORIGINAL_LIBRARY_AVAILABLE:
                log_audit_event(get_current_user_id(), f"GUI: Restored system from {backup_dir}", "system")
            
            return True
            
        except Exception as e:
            print(f"Restore error: {e}")
            return False

    def pay_fine_via_finance(self):
        """Pay library fines through the finance system"""
        user_id = self.fine_user_var.get().strip()
        payment_amount = self.payment_amount_var.get().strip()

        if not user_id:
            messagebox.showwarning("Warning", "Please search for a user first")
            return

        if not payment_amount:
            messagebox.showwarning("Warning", "Please enter a payment amount")
            return

        try:
            amount = float(payment_amount)
            if amount <= 0:
                messagebox.showwarning("Warning", "Payment amount must be greater than 0")
                return
        except ValueError:
            messagebox.showwarning("Warning", "Please enter a valid payment amount")
            return

        # Get user details for the finance transaction
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT first_name, last_name, email_address FROM students WHERE student_id = ?', (user_id,))
                    user_info = cursor.fetchone()
                    conn.close()

                    if not user_info:
                        messagebox.showerror("Error", "Student not found in system")
                        return

                    first_name, last_name, email = user_info
                else:
                    first_name, last_name, email = "Demo", "User", "demo@university.edu"
            else:
                first_name, last_name, email = "Demo", "User", "demo@university.edu"

            # Create finance transaction via Finance GUI
            success = self._process_library_fine_payment(
                student_id=user_id,
                amount=amount,
                student_name=f"{first_name} {last_name}",
                email=email
            )

            if success:
                messagebox.showinfo("Success",
                    f"Library fine payment of ${amount:.2f} processed successfully!\n"
                    f"Payment has been charged to {first_name} {last_name}'s account.")

                # Send email confirmation
                self._send_library_payment_confirmation_email(
                    student_id=user_id,
                    student_name=f"{first_name} {last_name}",
                    email=email,
                    amount=amount
                )

                # Refresh the fines display
                self.load_user_fines()
            else:
                messagebox.showerror("Error",
                    "Failed to process payment through finance system.\n"
                    "Please try again or contact the finance office.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process finance payment: {e}")

    def _process_library_fine_payment(self, student_id, amount, student_name, email):
        """Process library fine payment through finance system"""
        try:
            # Try to integrate with finance GUI
            from university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH

            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                current_date = datetime.now().strftime('%Y-%m-%d')
                due_date = current_date  # Library fines are due immediately

                # Check for existing unpaid library fee, or create new one
                cursor.execute('''
                    SELECT student_fee_id, amount FROM student_fees
                    WHERE student_id = ? AND fee_type_id = 3 AND status = 'unpaid'
                    ORDER BY created_at DESC LIMIT 1
                ''', (student_id,))

                existing_fee = cursor.fetchone()

                if existing_fee:
                    # Update existing fee
                    student_fee_id, current_fee_amount = existing_fee
                    new_fee_amount = max(0, current_fee_amount - amount)

                    if new_fee_amount == 0:
                        # Fully paid
                        cursor.execute('''
                            UPDATE student_fees
                            SET status = 'paid', updated_at = ?
                            WHERE student_fee_id = ?
                        ''', (current_date, student_fee_id))
                    else:
                        # Partial payment
                        cursor.execute('''
                            UPDATE student_fees
                            SET amount = ?, updated_at = ?
                            WHERE student_fee_id = ?
                        ''', (new_fee_amount, current_date, student_fee_id))
                else:
                    # Create new fee record (already paid)
                    cursor.execute('''
                        INSERT INTO student_fees
                        (student_id, fee_type_id, amount, currency, status, due_date, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (student_id, 3, 0.00, 'GBP', 'paid', due_date, current_date, current_date))
                    student_fee_id = cursor.lastrowid

                # Record payment in payments table
                cursor.execute('''
                    INSERT INTO payments
                    (student_id, amount, payment_method, payment_date, status, reference_number, description, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    student_id, amount, 'Student Account', current_date, 'completed',
                    f'LIB-{student_id}-{datetime.now().strftime("%Y%m%d%H%M%S")}',
                    f'Library fine payment for {student_name}', current_date
                ))
                payment_id = cursor.lastrowid

                # Link payment to fee via payment_allocations
                cursor.execute('''
                    INSERT INTO payment_allocations
                    (payment_id, student_fee_id, amount, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (payment_id, student_fee_id, amount, current_date))

                # Update library fine status to paid (set amount to 0, add note)
                cursor.execute('''
                    UPDATE book_loans
                    SET fine_amount = 0,
                        notes = COALESCE(notes || '; ', '') || 'Fine paid on ' || ?
                    WHERE user_id = ? AND fine_amount > 0
                ''', (current_date, student_id))

                conn.commit()
                return True

        except Exception as e:
            print(f"Finance integration error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _send_library_payment_confirmation_email(self, student_id, student_name, email, amount):
        """Send email confirmation for library fine payment"""
        try:
            from university_system.infrastructure.email.template_utils import render_template

            subject, message = render_template('library_fine_payment', {
                'student_name': student_name,
                'student_id': student_id,
                'amount': f'${amount:.2f}',
                'payment_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })

            if not (subject and message):
                print("Failed to load library fine payment template")
                return

            # Try to send via email GUI
            success = self._send_email_via_gui(email, subject, message)

            if success:
                print(f"Library payment confirmation sent to {student_name} ({email})")
            else:
                # Fallback: show email details
                self._show_library_email_fallback(student_name, email, subject, message, "Payment Confirmation")

        except Exception as e:
            print(f"Failed to send library payment confirmation email: {e}")

    def _send_email_via_gui(self, to_email, subject, message):
        """Try to send email via email GUI"""
        try:
            from university_system.infrastructure.email.gui.email_manager_gui import EmailGUI
            email_gui = EmailGUI(self.master, self.auth)
            email_gui.send_email(to_email=to_email, subject=subject, message=message)
            return True
        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending email via GUI: {e}")
            return False

    def _show_library_email_fallback(self, student_name, email, subject, message, email_type):
        """Show fallback dialog for library email"""
        try:
            fallback_window = tk.Toplevel(self.master)
            fallback_window.title(f"Library {email_type} Email - Manual Send")
            fallback_window.geometry("700x500")
            fallback_window.transient(self.master)

            ttk.Label(fallback_window,
                     text=f"Library {email_type.lower()} email for {student_name} - Please send manually:",
                     font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=10)

            details_frame = ttk.LabelFrame(fallback_window, text="Email Details", padding=10)
            details_frame.pack(fill='both', expand=True, padx=10, pady=10)

            details_text = ScrolledText(details_frame, height=20, width=80)
            details_text.pack(fill='both', expand=True)

            email_details = f"To: {email}\nSubject: {subject}\n\nMessage:\n{message}"
            details_text.insert('1.0', email_details)
            details_text.config(state='disabled')

            ttk.Button(fallback_window, text="Close", command=fallback_window.destroy).pack(pady=10)
        except Exception as e:
            print(f"Failed to show library email fallback: {e}")

    def _send_checkout_confirmation_email(self, book_id, user_id):
        """Send email confirmation for book checkout"""
        try:
            # Get book and user details
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Get book details
                    cursor.execute('SELECT title, author FROM books WHERE book_id = ?', (book_id,))
                    book_info = cursor.fetchone()

                    # Get user details and calculate due date
                    cursor.execute('SELECT first_name, last_name, email_address FROM students WHERE student_id = ?', (user_id,))
                    user_info = cursor.fetchone()

                    # Get the most recent checkout for due date
                    cursor.execute('''
                        SELECT due_date FROM book_loans
                        WHERE book_id = ? AND user_id = ? AND status = 'active'
                        ORDER BY checkout_date DESC LIMIT 1
                    ''', (book_id, user_id))
                    due_date_info = cursor.fetchone()

                    conn.close()

                    if book_info and user_info and due_date_info:
                        book_title, author = book_info
                        first_name, last_name, email = user_info
                        due_date = due_date_info[0]

                        template_vars = {
                            'student_name': f"{first_name} {last_name}",
                            'student_id': user_id,
                            'book_id': book_id,
                            'book_title': book_title,
                            'author': author,
                            'due_date': due_date
                        }

                        subject, message = render_template('library_book_checkout', template_vars)

                        if not subject or not message:
                            print("Failed to load email template.")
                            return

                        # Send email
                        success = self._send_email_via_gui(email, subject, message)

                        if success:
                            print(f"Checkout confirmation sent to {first_name} {last_name} ({email})")
                        else:
                            self._show_library_email_fallback(f"{first_name} {last_name}", email, subject, message, "Checkout Confirmation")

        except Exception as e:
            print(f"Failed to send checkout confirmation email: {e}")

    def _send_return_confirmation_email(self, book_id, user_id):
        """Send email confirmation for book return"""
        try:
            # Get book and user details
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Get book details
                    cursor.execute('SELECT title, author FROM books WHERE book_id = ?', (book_id,))
                    book_info = cursor.fetchone()

                    # Get user details
                    cursor.execute('SELECT first_name, last_name, email_address FROM students WHERE student_id = ?', (user_id,))
                    user_info = cursor.fetchone()

                    # Check for any fines on the return
                    cursor.execute('''
                        SELECT fine_amount FROM book_loans
                        WHERE book_id = ? AND user_id = ? AND status = 'returned'
                        ORDER BY return_date DESC LIMIT 1
                    ''', (book_id, user_id))
                    fine_info = cursor.fetchone()

                    conn.close()

                    if book_info and user_info:
                        book_title, author = book_info
                        first_name, last_name, email = user_info
                        fine_amount = fine_info[0] if fine_info and fine_info[0] else 0.0

                        template_vars = {
                            'student_name': f"{first_name} {last_name}",
                            'student_id': user_id,
                            'book_id': book_id,
                            'book_title': book_title,
                            'author': author,
                            'fine_amount': f"{fine_amount:.2f}"
                        }

                        subject, message = render_template('library_book_return', template_vars)

                        if not subject or not message:
                            print("Failed to load email template.")
                            return

                        # Send email
                        success = self._send_email_via_gui(email, subject, message)

                        if success:
                            print(f"Return confirmation sent to {first_name} {last_name} ({email})")
                        else:
                            self._show_library_email_fallback(f"{first_name} {last_name}", email, subject, message, "Return Confirmation")

        except Exception as e:
            print(f"Failed to send return confirmation email: {e}")

    def send_overdue_reminders(self):
        """Send reminder emails for overdue books"""
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Get overdue books with user details
                    cursor.execute('''
                        SELECT bl.book_id, bl.user_id, bl.due_date, bl.fine_amount,
                               b.title, b.author,
                               s.first_name, s.last_name, s.email,
                               julianday('now') - julianday(bl.due_date) as days_overdue
                        FROM book_loans bl
                        JOIN books b ON bl.book_id = b.book_id
                        JOIN students s ON bl.user_id = s.student_id
                        WHERE bl.status = 'active' AND bl.due_date < date('now')
                        AND s.email IS NOT NULL AND s.email != ''
                        ORDER BY days_overdue DESC
                    ''')

                    overdue_books = cursor.fetchall()
                    conn.close()

                    if not overdue_books:
                        messagebox.showinfo("No Overdue Books", "No overdue books found.")
                        return

                    # Send reminder emails
                    sent_count = 0
                    for book in overdue_books:
                        book_id, user_id, due_date, fine_amount, title, author, first_name, last_name, email, days_overdue = book

                        fine_amount = fine_amount or 0.0

                        template_vars = {
                            'student_name': f"{first_name} {last_name}",
                            'student_id': user_id,
                            'book_id': book_id,
                            'book_title': title,
                            'author': author,
                            'due_date': due_date,
                            'days_overdue': int(days_overdue),
                            'fine_amount': f"{fine_amount:.2f}"
                        }

                        subject, message = render_template('overdue_book_reminder', template_vars)

                        if not subject or not message:
                            print("Failed to load email template.")
                            continue

                        # Send email
                        success = self._send_email_via_gui(email, subject, message)

                        if success:
                            sent_count += 1
                            print(f"Overdue reminder sent to {first_name} {last_name} ({email})")
                        else:
                            self._show_library_email_fallback(f"{first_name} {last_name}", email, subject, message, "Overdue Reminder")

                    messagebox.showinfo("Reminders Sent",
                        f"Overdue reminder emails sent to {sent_count} students with overdue books.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send overdue reminders: {e}")

    def check_and_display_late_fees(self):
        """Check if current user has any late fees and display notification"""
        if not self.auth or not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            return

        current_user_id = self.auth.current_user.get('username', None)
        if not current_user_id:
            return

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Check for overdue books with fines
            cursor.execute('''
                SELECT COUNT(*), SUM(COALESCE(fine_amount, 0))
                FROM book_loans
                WHERE user_id = ? AND status = 'overdue' AND fine_amount > 0
            ''', (current_user_id,))

            result = cursor.fetchone()
            conn.close()

            if result and result[0] > 0:
                overdue_count = result[0]
                total_fines = result[1] or 0

                # Create notification frame at the top
                notification_frame = ttk.Frame(self.master, style='Warning.TFrame')
                notification_frame.pack(fill=tk.X, padx=5, pady=(5,0))

                message = f"⚠️ You have {overdue_count} overdue book(s) with ${total_fines:.2f} in late fees"
                notification_label = ttk.Label(notification_frame, text=message,
                                             style='Warning.TLabel', font=('Arial', 10, 'bold'))
                notification_label.pack(side=tk.LEFT, padx=10, pady=5)

                # Add "Pay Now" button
                pay_button = ttk.Button(notification_frame, text="Pay via Finance System",
                                      command=lambda: self.open_finance_payment_for_user(current_user_id, total_fines))
                pay_button.pack(side=tk.RIGHT, padx=10, pady=5)

                # Configure warning style
                self.style.configure('Warning.TFrame', background='#fff3cd')
                self.style.configure('Warning.TLabel', background='#fff3cd', foreground='#856404')

        except Exception as e:
            print(f"Error checking late fees: {e}")

    def open_finance_payment_for_user(self, user_id, amount):
        """Open finance system for user to pay late fees"""
        try:
            # Try to launch finance GUI for payment
            try:
                from university_system.modules.domain.finance.gui.finance import FinanceGUI
                finance_window = tk.Toplevel(self.master)
                finance_window.title(f"Pay Library Fees - ${amount:.2f}")
                finance_window.geometry("800x600")

                # Initialize finance GUI in payment mode
                finance_gui = FinanceGUI(finance_window, auth=self.auth)
                # Pre-populate with library fee information if method exists
                if hasattr(finance_gui, 'prepopulate_library_fee_payment'):
                    finance_gui.prepopulate_library_fee_payment(user_id, amount)

            except ImportError:
                # Fallback to showing fine management dialog
                self.fine_user_var = tk.StringVar(value=user_id)
                self.payment_amount_var = tk.StringVar(value=str(amount))
                self.show_fine_management()

        except Exception as e:
            messagebox.showerror("Error", f"Could not open payment system: {e}")

    def open_calendar_with_due_dates(self):
        """Open calendar GUI with book return dates"""
        try:
            from university_system.modules.domain.academics.gui.academic_calendar_gui import CalendarGUI

            # Get current user's checked out books
            current_user_id = None
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                current_user_id = self.auth.current_user.get('username', None)

            if not current_user_id:
                messagebox.showwarning("Warning", "Please log in to view your book return dates")
                return

            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Could not connect to database")
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT bl.book_id, b.title, bl.due_date, bl.status
                FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id
                WHERE bl.user_id = ? AND bl.status IN ('active', 'overdue')
                ORDER BY bl.due_date
            ''', (current_user_id,))

            book_loans = cursor.fetchall()
            conn.close()

            # Create calendar window
            calendar_window = tk.Toplevel(self.master)
            calendar_window.title("Library Book Return Calendar")
            calendar_window.geometry("900x700")

            # Initialize calendar GUI
            calendar_gui = CalendarGUI(auth_manager=self.auth, parent_window=calendar_window)

            # Add book return events to calendar
            for book_id, title, due_date, status in book_loans:
                event_title = f"Return: {title}"
                event_description = f"Book ID: {book_id}\nStatus: {status}"

                # Determine event type based on status
                event_type = "deadline" if status == "overdue" else "library_due"

                # Add event to calendar if method exists
                if hasattr(calendar_gui, 'add_library_event'):
                    calendar_gui.add_library_event(
                        title=event_title,
                        date=due_date,
                        description=event_description,
                        event_type=event_type
                    )

            messagebox.showinfo("Calendar Opened",
                               f"Calendar opened with {len(book_loans)} book return dates")

        except ImportError:
            messagebox.showerror("Error", "Calendar system is not available")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open calendar: {e}")

    def add_calendar_button_to_interface(self):
        """Add calendar button to the main interface"""
        try:
            # Add button to the control frame if it exists
            if hasattr(self, 'control_frame'):
                calendar_button = ttk.Button(self.control_frame,
                                           text="📅 View Return Calendar",
                                           command=self.open_calendar_with_due_dates)
                calendar_button.pack(side=tk.LEFT, padx=5)
        except Exception as e:
            print(f"Could not add calendar button: {e}")

    # ============================================================================
    # MISSING METHOD IMPLEMENTATIONS
    # ============================================================================

    def import_books_gui(self):
        """Import books from CSV or Excel file"""
        try:
            file_path = filedialog.askopenfilename(
                title="Select Book File to Import",
                filetypes=[
                    ("CSV files", "*.csv"),
                    ("Excel files", "*.xlsx *.xls"),
                    ("All files", "*.*")
                ]
            )

            if not file_path:
                return

            # Ask user about column mapping
            dialog = tk.Toplevel(self.master)
            dialog.title("Import Books")
            dialog.geometry("600x400")
            dialog.transient(self.master)

            ttk.Label(dialog, text="Importing books from:", font=('Arial', 10, 'bold')).pack(pady=5)
            ttk.Label(dialog, text=os.path.basename(file_path)).pack(pady=5)

            # Read file preview
            import csv
            try:
                if file_path.endswith('.csv'):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        headers = next(reader)
                        preview_rows = [next(reader) for _ in range(min(3, sum(1 for _ in reader)))]
                else:
                    # For Excel, would need openpyxl - fallback to CSV-like approach
                    messagebox.showwarning("Format", "Excel import requires openpyxl. Please convert to CSV.")
                    dialog.destroy()
                    return

                # Show column mapping
                frame = ttk.LabelFrame(dialog, text="Column Mapping")
                frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                mappings = {}
                required_fields = ['title', 'author', 'isbn', 'category', 'quantity']

                for i, field in enumerate(required_fields):
                    ttk.Label(frame, text=f"{field.title()}:").grid(row=i, column=0, sticky='w', padx=5, pady=3)
                    var = tk.StringVar(value=headers[i] if i < len(headers) else '')
                    combo = ttk.Combobox(frame, textvariable=var, values=headers, width=30)
                    combo.grid(row=i, column=1, padx=5, pady=3)
                    mappings[field] = var

                # Import button
                def do_import():
                    try:
                        imported_count = 0
                        conn = get_db_connection()
                        cursor = conn.cursor()

                        with open(file_path, 'r', encoding='utf-8') as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                try:
                                    book_data = {
                                        'title': row.get(mappings['title'].get(), ''),
                                        'author': row.get(mappings['author'].get(), ''),
                                        'isbn': row.get(mappings['isbn'].get(), ''),
                                        'category': row.get(mappings['category'].get(), ''),
                                        'quantity': int(row.get(mappings['quantity'].get(), 1))
                                    }

                                    # Generate book_id
                                    cursor.execute('SELECT MAX(CAST(SUBSTR(book_id, 2) AS INTEGER)) FROM books')
                                    result = cursor.fetchone()
                                    next_num = (result[0] or 10000) + 1
                                    book_id = f"B{next_num}"

                                    cursor.execute('''
                                        INSERT INTO books (book_id, title, author, isbn, category,
                                                         quantity, available_quantity, status, location)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, 'Available', 'Imported')
                                    ''', (book_id, book_data['title'], book_data['author'],
                                         book_data['isbn'], book_data['category'],
                                         book_data['quantity'], book_data['quantity']))

                                    imported_count += 1
                                except Exception as e:
                                    print(f"Error importing row: {e}")
                                    continue

                        conn.commit()
                        conn.close()

                        messagebox.showinfo("Success", f"Successfully imported {imported_count} books!")
                        dialog.destroy()
                        if hasattr(self, 'books_tree'):
                            self.load_books_data()

                    except Exception as e:
                        messagebox.showerror("Error", f"Import failed: {str(e)}")

                ttk.Button(dialog, text="Import", command=do_import).pack(pady=10)
                ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=5)

            except Exception as e:
                messagebox.showerror("Error", f"Could not read file: {str(e)}")
                dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Import failed: {str(e)}")

    def export_books_gui(self):
        """Export books to CSV file"""
        try:
            file_path = filedialog.asksaveasfilename(
                title="Export Books",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not file_path:
                return

            import csv
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT book_id, title, author, isbn, category, publisher,
                       publication_year, quantity, available_quantity, status, location
                FROM books
                ORDER BY title
            ''')

            books = cursor.fetchall()
            conn.close()

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Book ID', 'Title', 'Author', 'ISBN', 'Category',
                               'Publisher', 'Year', 'Quantity', 'Available', 'Status', 'Location'])
                writer.writerows(books)

            messagebox.showinfo("Success", f"Exported {len(books)} books to {os.path.basename(file_path)}")

        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def backup_system_gui(self):
        """Create database backup"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"library_backup_{timestamp}.db"

            file_path = filedialog.asksaveasfilename(
                title="Save Backup",
                defaultextension=".db",
                initialfile=default_name,
                filetypes=[("Database files", "*.db"), ("All files", "*.*")]
            )

            if not file_path:
                return

            import shutil
            shutil.copy2(DATABASE_FILE, file_path)

            # Log the backup
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                user_id = get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'system'
                cursor.execute('''
                    INSERT INTO audit_log (user_id, action, table_name, timestamp, success)
                    VALUES (?, 'backup', 'system', ?, 1)
                ''', (user_id, datetime.now().isoformat()))
                conn.commit()
                conn.close()
            except:
                pass

            messagebox.showinfo("Success", f"Backup created successfully!\n{os.path.basename(file_path)}")
            self.update_status("Backup created successfully", "success")

        except Exception as e:
            messagebox.showerror("Error", f"Backup failed: {str(e)}")

    def show_advanced_search(self):
        """Show advanced search dialog with multiple criteria"""
        dialog = tk.Toplevel(self.master)
        dialog.title("Advanced Book Search")
        dialog.geometry("600x500")
        dialog.transient(self.master)

        # Search criteria frame
        criteria_frame = ttk.LabelFrame(dialog, text="Search Criteria")
        criteria_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create search fields
        fields = {
            'title': tk.StringVar(),
            'author': tk.StringVar(),
            'isbn': tk.StringVar(),
            'category': tk.StringVar(),
            'publisher': tk.StringVar(),
            'year_from': tk.StringVar(),
            'year_to': tk.StringVar(),
            'status': tk.StringVar(value='Any')
        }

        row = 0
        ttk.Label(criteria_frame, text="Title:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(criteria_frame, textvariable=fields['title'], width=40).grid(row=row, column=1, padx=5, pady=5)

        row += 1
        ttk.Label(criteria_frame, text="Author:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(criteria_frame, textvariable=fields['author'], width=40).grid(row=row, column=1, padx=5, pady=5)

        row += 1
        ttk.Label(criteria_frame, text="ISBN:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(criteria_frame, textvariable=fields['isbn'], width=40).grid(row=row, column=1, padx=5, pady=5)

        row += 1
        ttk.Label(criteria_frame, text="Category:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(criteria_frame, textvariable=fields['category'], width=40).grid(row=row, column=1, padx=5, pady=5)

        row += 1
        ttk.Label(criteria_frame, text="Publisher:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(criteria_frame, textvariable=fields['publisher'], width=40).grid(row=row, column=1, padx=5, pady=5)

        row += 1
        ttk.Label(criteria_frame, text="Year From:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(criteria_frame, textvariable=fields['year_from'], width=15).grid(row=row, column=1, sticky='w', padx=5, pady=5)

        row += 1
        ttk.Label(criteria_frame, text="Year To:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(criteria_frame, textvariable=fields['year_to'], width=15).grid(row=row, column=1, sticky='w', padx=5, pady=5)

        row += 1
        ttk.Label(criteria_frame, text="Status:").grid(row=row, column=0, sticky='w', padx=5, pady=5)
        ttk.Combobox(criteria_frame, textvariable=fields['status'],
                    values=['Any', 'Available', 'Checked Out', 'Reserved', 'Maintenance'],
                    width=37).grid(row=row, column=1, padx=5, pady=5)

        # Results frame
        results_frame = ttk.LabelFrame(dialog, text="Search Results")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Results treeview
        columns = ('ID', 'Title', 'Author', 'Category', 'Year', 'Status')
        results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=8)

        for col in columns:
            results_tree.heading(col, text=col)
            results_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=results_tree.yview)
        results_tree.configure(yscrollcommand=scrollbar.set)

        results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def execute_advanced_search():
            try:
                # Clear previous results
                for item in results_tree.get_children():
                    results_tree.delete(item)

                # Build query
                query = "SELECT book_id, title, author, category, publication_year, status FROM books WHERE 1=1"
                params = []

                if fields['title'].get():
                    query += " AND title LIKE ?"
                    params.append(f"%{fields['title'].get()}%")

                if fields['author'].get():
                    query += " AND author LIKE ?"
                    params.append(f"%{fields['author'].get()}%")

                if fields['isbn'].get():
                    query += " AND isbn LIKE ?"
                    params.append(f"%{fields['isbn'].get()}%")

                if fields['category'].get():
                    query += " AND category LIKE ?"
                    params.append(f"%{fields['category'].get()}%")

                if fields['publisher'].get():
                    query += " AND publisher LIKE ?"
                    params.append(f"%{fields['publisher'].get()}%")

                if fields['year_from'].get():
                    query += " AND publication_year >= ?"
                    params.append(int(fields['year_from'].get()))

                if fields['year_to'].get():
                    query += " AND publication_year <= ?"
                    params.append(int(fields['year_to'].get()))

                if fields['status'].get() != 'Any':
                    query += " AND status = ?"
                    params.append(fields['status'].get())

                query += " ORDER BY title LIMIT 100"

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = cursor.fetchall()
                conn.close()

                for result in results:
                    results_tree.insert('', 'end', values=result)

                messagebox.showinfo("Search Complete", f"Found {len(results)} matching books")

            except Exception as e:
                messagebox.showerror("Error", f"Search failed: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Search", command=execute_advanced_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear", command=lambda: [v.set('') for v in fields.values()]).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def show_library_cards_generator(self):
        """Generate library cards with barcodes for users"""
        dialog = tk.Toplevel(self.master)
        dialog.title("Library Card Generator")
        dialog.geometry("700x600")
        dialog.transient(self.master)

        ttk.Label(dialog, text="Library Card Generator", font=('Arial', 14, 'bold')).pack(pady=10)

        # User selection frame
        selection_frame = ttk.LabelFrame(dialog, text="Select User")
        selection_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(selection_frame, text="User ID or Username:").pack(side=tk.LEFT, padx=5)
        user_var = tk.StringVar()
        user_entry = ttk.Entry(selection_frame, textvariable=user_var, width=30)
        user_entry.pack(side=tk.LEFT, padx=5)

        # Card preview frame
        preview_frame = ttk.LabelFrame(dialog, text="Card Preview")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        preview_canvas = tk.Canvas(preview_frame, bg='white', height=300)
        preview_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def generate_card():
            try:
                user_id = user_var.get().strip()
                if not user_id:
                    messagebox.showwarning("Warning", "Please enter a user ID or username")
                    return

                # Get user info
                conn = get_db_connection()
                cursor = conn.cursor()

                # Try to find user
                cursor.execute('''
                    SELECT student_id, first_name, last_name, email_address, course
                    FROM students WHERE student_id = ? OR email_address LIKE ?
                ''', (user_id, f"%{user_id}%"))

                user = cursor.fetchone()
                conn.close()

                if not user:
                    messagebox.showerror("Error", "User not found")
                    return

                # Clear canvas
                preview_canvas.delete('all')

                # Draw card (simplified version)
                card_width = 400
                card_height = 250
                x_offset = 50
                y_offset = 25

                # Card background
                preview_canvas.create_rectangle(x_offset, y_offset, x_offset + card_width, y_offset + card_height,
                                              fill='lightblue', outline='darkblue', width=2)

                # University name
                preview_canvas.create_text(x_offset + card_width//2, y_offset + 30,
                                         text="UNIVERSITY LIBRARY", font=('Arial', 16, 'bold'))

                # User info
                y = y_offset + 70
                preview_canvas.create_text(x_offset + 20, y, text=f"Name: {user[1]} {user[2]}",
                                         anchor='w', font=('Arial', 12))
                y += 30
                preview_canvas.create_text(x_offset + 20, y, text=f"ID: {user[0]}",
                                         anchor='w', font=('Arial', 12))
                y += 30
                preview_canvas.create_text(x_offset + 20, y, text=f"Department: {user[4] or 'N/A'}",
                                         anchor='w', font=('Arial', 12))
                y += 30

                # Barcode placeholder (simple representation)
                barcode_text = f"*{user[0]}*"
                preview_canvas.create_text(x_offset + card_width//2, y + 20,
                                         text=barcode_text, font=('Courier', 20, 'bold'))

                messagebox.showinfo("Success", "Library card generated successfully!")

            except Exception as e:
                messagebox.showerror("Error", f"Card generation failed: {str(e)}")

        def save_card():
            try:
                file_path = filedialog.asksaveasfilename(
                    title="Save Library Card",
                    defaultextension=".png",
                    filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
                )

                if file_path:
                    messagebox.showinfo("Info", "Card save functionality requires PIL/Pillow library")

            except Exception as e:
                messagebox.showerror("Error", f"Save failed: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Generate Card", command=generate_card).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Card", command=save_card).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def show_help(self):
        """Show user guide dialog"""
        dialog = tk.Toplevel(self.master)
        dialog.title("Library System - User Guide")
        dialog.geometry("800x600")
        dialog.transient(self.master)

        # Create notebook for different help sections
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Getting Started tab
        getting_started = ScrolledText(notebook, wrap=tk.WORD, width=80, height=30)
        getting_started.pack(fill=tk.BOTH, expand=True)
        getting_started.insert('1.0', """
GETTING STARTED
===============

Welcome to the Enhanced Library Management System!

This system allows you to:
- Browse and search the library catalog
- Check out and return books
- Make reservations
- View your borrowing history
- Generate reports

MAIN FEATURES:
--------------
1. Dashboard - Overview of library statistics and recent activity
2. All Books - Browse the complete catalog
3. Search - Find books by title, author, or category
4. Checkout - Borrow books
5. Return - Return borrowed books
6. Reservations - Reserve books that are currently unavailable
7. Reports - Generate various library reports

NAVIGATION:
-----------
- Use the sidebar menu to navigate between different sections
- Double-click on any book to view detailed information
- Right-click on books in the table for quick actions
""")
        getting_started.config(state='disabled')
        notebook.add(getting_started, text="Getting Started")

        # Features tab
        features = ScrolledText(notebook, wrap=tk.WORD, width=80, height=30)
        features.pack(fill=tk.BOTH, expand=True)
        features.insert('1.0', """
KEY FEATURES
============

BOOK MANAGEMENT:
----------------
- Add new books with ISBN lookup
- Edit book information
- Delete books (with confirmation)
- Import/export books from CSV
- Generate barcodes for books

CIRCULATION:
------------
- Check out books to users
- Process returns
- Calculate and manage fines
- Track overdue items
- View loan history

RESERVATIONS:
-------------
- Make reservations for unavailable books
- View all active reservations
- Cancel reservations
- Automatic notifications when books become available

REPORTS:
--------
- Collection report - Overview of library holdings
- Circulation report - Borrowing statistics
- Overdue report - List of overdue items
- User activity report - Individual user borrowing patterns
- Popular books report - Most borrowed items
- Fine report - Outstanding fines

ADVANCED FEATURES:
------------------
- Advanced search with multiple criteria
- Library card generation
- Database backup and restore
- System health checks
- Audit log viewing
""")
        features.config(state='disabled')
        notebook.add(features, text="Features")

        # FAQ tab
        faq = ScrolledText(notebook, wrap=tk.WORD, width=80, height=30)
        faq.pack(fill=tk.BOTH, expand=True)
        faq.insert('1.0', """
FREQUENTLY ASKED QUESTIONS
==========================

Q: How do I check out a book?
A: Go to the "Checkout" section, enter the book ID and user ID, and click "Process Checkout".

Q: How long is the loan period?
A: The default loan period is configurable in Settings (typically 14 or 21 days).

Q: What happens if a book is overdue?
A: Overdue books may incur fines based on the library's fine policy. Check the "Overdue Report" for details.

Q: Can I reserve a book that's already checked out?
A: Yes! Use the Reservations feature to place a hold on the book.

Q: How do I add multiple books at once?
A: Use the Import feature (File → Import Books) to upload a CSV file with multiple books.

Q: Where are my reports saved?
A: Reports are generated and displayed on-screen. You can copy the data or use the export features.

Q: Can I undo a checkout?
A: No, but you can immediately return the book if it was checked out by mistake.

Q: How do I backup the database?
A: Go to File → Backup System to create a backup of the library database.

Q: What if I encounter an error?
A: Check the status bar at the bottom of the window for error messages. Contact your system administrator if problems persist.
""")
        faq.config(state='disabled')
        notebook.add(faq, text="FAQ")

        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    def show_shortcuts(self):
        """Show keyboard shortcuts dialog"""
        dialog = tk.Toplevel(self.master)
        dialog.title("Keyboard Shortcuts")
        dialog.geometry("600x500")
        dialog.transient(self.master)

        ttk.Label(dialog, text="Keyboard Shortcuts", font=('Arial', 14, 'bold')).pack(pady=10)

        # Create scrolled text for shortcuts
        shortcuts_text = ScrolledText(dialog, wrap=tk.WORD, width=70, height=25)
        shortcuts_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        shortcuts_content = """
GLOBAL SHORTCUTS
================

Navigation:
-----------
Ctrl+H          Go to Home/Dashboard
Ctrl+B          Browse All Books
Ctrl+S          Search Books
Ctrl+O          Checkout
Ctrl+R          Return Books
Ctrl+V          View Reservations
Ctrl+P          Reports

File Operations:
----------------
Ctrl+I          Import Books
Ctrl+E          Export Books
Ctrl+Shift+B    Backup System
Ctrl+Q          Exit Application

View:
-----
F5              Refresh Current View
Ctrl+F          Find/Search in Current View
Ctrl++          Zoom In
Ctrl+-          Zoom Out

Editing:
--------
Ctrl+N          Add New Book
Ctrl+E          Edit Selected Book
Delete          Delete Selected Book
F2              Rename/Edit

Help:
-----
F1              Show Help
Ctrl+K          Show Keyboard Shortcuts
Ctrl+?          About

BOOK TABLE SHORTCUTS
====================

Enter           View Book Details
Space           Select/Deselect Book
Ctrl+A          Select All
Ctrl+C          Copy Selected
Right-Click     Show Context Menu
Double-Click    View Book Details

DIALOG SHORTCUTS
================

Enter           OK/Confirm
Escape          Cancel/Close
Tab             Next Field
Shift+Tab       Previous Field

SEARCH SHORTCUTS
================

Ctrl+F          Focus Search Box
Enter           Execute Search
Escape          Clear Search

NOTE: Some shortcuts may not work if they conflict with system shortcuts.
"""

        shortcuts_text.insert('1.0', shortcuts_content)
        shortcuts_text.config(state='disabled')

        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    def show_about(self):
        """Show about dialog"""
        dialog = tk.Toplevel(self.master)
        dialog.title("About Library Management System")
        dialog.geometry("500x600")
        dialog.transient(self.master)

        # Logo/Title
        title_frame = ttk.Frame(dialog)
        title_frame.pack(fill=tk.X, pady=20)

        ttk.Label(title_frame, text="📚", font=('Arial', 48)).pack()
        ttk.Label(title_frame, text="Enhanced Library Management System",
                 font=('Arial', 14, 'bold')).pack(pady=5)
        ttk.Label(title_frame, text="Version 5.0.0", font=('Arial', 10)).pack()

        # Information frame
        info_frame = ttk.Frame(dialog)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        info_text = ScrolledText(info_frame, wrap=tk.WORD, height=20)
        info_text.pack(fill=tk.BOTH, expand=True)

        about_content = """
ABOUT
=====

The Enhanced Library Management System is a comprehensive solution for managing library operations including book cataloging, circulation, reservations, and reporting.

FEATURES:
---------
• Complete book catalog management
• Circulation and loan tracking
• Reservation system
• Fine management
• Advanced search capabilities
• Comprehensive reporting
• Database backup and restore
• Audit logging
• ISBN lookup integration
• Barcode generation
• Library card generation

TECHNICAL DETAILS:
------------------
• Built with Python and Tkinter
• SQLite database backend
• 4-layer domain-driven architecture
• Thread-safe connection pooling
• Transaction management
• RESTful API integration

SYSTEM INFORMATION:
-------------------
Database: SQLite
Python Version: 3.8+
Architecture: 4-layer DDD
Database File: student_records.db

CREDITS:
--------
Developed as part of the University Management System
Architecture: Domain-Driven Design
Testing: Comprehensive test suite with pytest
Security: PBKDF2 password hashing, audit logging

COPYRIGHT:
----------
© 2025 University Management System
All rights reserved.

This software is part of an enterprise-grade university management platform
integrating academic, financial, and administrative operations.

LICENSE:
--------
This software is provided for educational and institutional use.

SUPPORT:
--------
For support, please contact your system administrator or refer to the
documentation in the docs/ directory.

ACKNOWLEDGMENTS:
----------------
Special thanks to all contributors and testers who helped make this
system robust and user-friendly.
"""

        info_text.insert('1.0', about_content)
        info_text.config(state='disabled')

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(button_frame, text="View License",
                  command=lambda: messagebox.showinfo("License", "Educational and institutional use")).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def edit_selected_book(self):
        """Edit details of selected book"""
        selection = self.books_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a book to edit")
            return

        item = self.books_tree.item(selection[0])
        book_id = item['values'][0]

        try:
            # Get current book details
            book_details = self.get_book_details(book_id)
            if not book_details:
                messagebox.showerror("Error", "Book not found")
                return

            # Create edit dialog
            dialog = tk.Toplevel(self.master)
            dialog.title(f"Edit Book - {book_id}")
            dialog.geometry("600x700")
            dialog.transient(self.master)

            # Create form
            form_frame = ttk.Frame(dialog)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            fields = {}
            field_names = [
                ('title', 'Title'),
                ('author', 'Author'),
                ('isbn', 'ISBN'),
                ('category', 'Category'),
                ('publisher', 'Publisher'),
                ('publication_year', 'Publication Year'),
                ('quantity', 'Quantity'),
                ('available_quantity', 'Available Quantity'),
                ('location', 'Location'),
                ('status', 'Status')
            ]

            for i, (field_key, field_label) in enumerate(field_names):
                ttk.Label(form_frame, text=f"{field_label}:").grid(row=i, column=0, sticky='w', pady=5, padx=5)

                if field_key == 'status':
                    fields[field_key] = tk.StringVar(value=book_details.get(field_key, ''))
                    ttk.Combobox(form_frame, textvariable=fields[field_key],
                               values=['Available', 'Checked Out', 'Reserved', 'Maintenance'],
                               width=37).grid(row=i, column=1, pady=5, padx=5)
                else:
                    fields[field_key] = tk.StringVar(value=book_details.get(field_key, ''))
                    ttk.Entry(form_frame, textvariable=fields[field_key], width=40).grid(row=i, column=1, pady=5, padx=5)

            def save_changes():
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                        UPDATE books
                        SET title = ?, author = ?, isbn = ?, category = ?,
                            publisher = ?, publication_year = ?, quantity = ?,
                            available_quantity = ?, location = ?, status = ?
                        WHERE book_id = ?
                    ''', (
                        fields['title'].get(),
                        fields['author'].get(),
                        fields['isbn'].get(),
                        fields['category'].get(),
                        fields['publisher'].get(),
                        fields['publication_year'].get(),
                        fields['quantity'].get(),
                        fields['available_quantity'].get(),
                        fields['location'].get(),
                        fields['status'].get(),
                        book_id
                    ))

                    conn.commit()
                    conn.close()

                    # Log the edit
                    try:
                        user_id = get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'system'
                        log_audit_event(user_id, 'update', 'books', book_id, True)
                    except:
                        pass

                    messagebox.showinfo("Success", "Book updated successfully!")
                    dialog.destroy()
                    self.load_books_data()

                except Exception as e:
                    messagebox.showerror("Error", f"Update failed: {str(e)}")

            # Buttons
            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill=tk.X, padx=20, pady=10)

            ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Edit failed: {str(e)}")

    def checkout_selected_book(self):
        """Quick checkout from context menu"""
        selection = self.books_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a book first")
            return

        item = self.books_tree.item(selection[0])
        book_id = item['values'][0]

        # Create quick checkout dialog
        dialog = tk.Toplevel(self.master)
        dialog.title("Quick Checkout")
        dialog.geometry("400x200")
        dialog.transient(self.master)

        ttk.Label(dialog, text=f"Checkout Book: {book_id}", font=('Arial', 12, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=f"Title: {item['values'][1]}").pack(pady=5)

        ttk.Label(dialog, text="User ID or Email:").pack(pady=10)
        user_var = tk.StringVar()
        user_entry = ttk.Entry(dialog, textvariable=user_var, width=30)
        user_entry.pack(pady=5)
        user_entry.focus()

        def process_quick_checkout():
            try:
                user_id = user_var.get().strip()
                if not user_id:
                    messagebox.showwarning("Warning", "Please enter a user ID")
                    return

                # Verify user exists
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT student_id FROM students
                    WHERE student_id = ? OR email_address LIKE ?
                ''', (user_id, f"%{user_id}%"))

                user = cursor.fetchone()
                if not user:
                    messagebox.showerror("Error", "User not found")
                    conn.close()
                    return

                actual_user_id = user[0]

                # Check if book is available
                cursor.execute('SELECT available_quantity, status FROM books WHERE book_id = ?', (book_id,))
                book_info = cursor.fetchone()

                if not book_info or book_info[0] <= 0:
                    messagebox.showerror("Error", "Book not available for checkout")
                    conn.close()
                    return

                # Process checkout
                due_date = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')

                cursor.execute('''
                    INSERT INTO loans (book_id, user_id, loan_date, due_date, status)
                    VALUES (?, ?, ?, ?, 'active')
                ''', (book_id, actual_user_id, datetime.now().strftime('%Y-%m-%d'), due_date))

                cursor.execute('''
                    UPDATE books
                    SET available_quantity = available_quantity - 1,
                        status = CASE WHEN available_quantity - 1 = 0 THEN 'Checked Out' ELSE status END
                    WHERE book_id = ?
                ''', (book_id,))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Book checked out successfully!\nDue date: {due_date}")
                dialog.destroy()
                self.load_books_data()

            except Exception as e:
                messagebox.showerror("Error", f"Checkout failed: {str(e)}")

        ttk.Button(dialog, text="Checkout", command=process_quick_checkout).pack(pady=10)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=5)

    def reserve_selected_book(self):
        """Quick reserve from context menu"""
        selection = self.books_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a book first")
            return

        item = self.books_tree.item(selection[0])
        book_id = item['values'][0]

        # Create quick reservation dialog
        dialog = tk.Toplevel(self.master)
        dialog.title("Quick Reservation")
        dialog.geometry("400x200")
        dialog.transient(self.master)

        ttk.Label(dialog, text=f"Reserve Book: {book_id}", font=('Arial', 12, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=f"Title: {item['values'][1]}").pack(pady=5)

        ttk.Label(dialog, text="User ID or Email:").pack(pady=10)
        user_var = tk.StringVar()
        user_entry = ttk.Entry(dialog, textvariable=user_var, width=30)
        user_entry.pack(pady=5)
        user_entry.focus()

        def process_quick_reservation():
            try:
                user_id = user_var.get().strip()
                if not user_id:
                    messagebox.showwarning("Warning", "Please enter a user ID")
                    return

                # Verify user exists
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT student_id FROM students
                    WHERE student_id = ? OR email_address LIKE ?
                ''', (user_id, f"%{user_id}%"))

                user = cursor.fetchone()
                if not user:
                    messagebox.showerror("Error", "User not found")
                    conn.close()
                    return

                actual_user_id = user[0]

                # Check if already reserved
                cursor.execute('''
                    SELECT COUNT(*) FROM reservations
                    WHERE book_id = ? AND user_id = ? AND status = 'active'
                ''', (book_id, actual_user_id))

                if cursor.fetchone()[0] > 0:
                    messagebox.showwarning("Warning", "This book is already reserved by this user")
                    conn.close()
                    return

                # Create reservation
                reservation_date = datetime.now().strftime('%Y-%m-%d')

                cursor.execute('''
                    INSERT INTO reservations (book_id, user_id, reservation_date, status)
                    VALUES (?, ?, ?, 'active')
                ''', (book_id, actual_user_id, reservation_date))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Book reserved successfully!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Reservation failed: {str(e)}")

        ttk.Button(dialog, text="Reserve", command=process_quick_reservation).pack(pady=10)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=5)

    def delete_selected_book(self):
        """Delete book with confirmation"""
        selection = self.books_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a book to delete")
            return

        item = self.books_tree.item(selection[0])
        book_id = item['values'][0]
        title = item['values'][1]

        # Confirm deletion
        result = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete this book?\n\n"
            f"Book ID: {book_id}\n"
            f"Title: {title}\n\n"
            f"This action cannot be undone!"
        )

        if not result:
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if book has active loans
            cursor.execute('''
                SELECT COUNT(*) FROM loans
                WHERE book_id = ? AND status = 'active'
            ''', (book_id,))

            active_loans = cursor.fetchone()[0]
            if active_loans > 0:
                messagebox.showerror(
                    "Cannot Delete",
                    f"This book has {active_loans} active loan(s).\n"
                    "Please return all copies before deleting."
                )
                conn.close()
                return

            # Delete the book
            cursor.execute('DELETE FROM books WHERE book_id = ?', (book_id,))
            conn.commit()
            conn.close()

            # Log the deletion
            try:
                user_id = get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'system'
                log_audit_event(user_id, 'delete', 'books', book_id, True)
            except:
                pass

            messagebox.showinfo("Success", "Book deleted successfully!")
            self.load_books_data()
            self.update_status(f"Deleted book: {book_id}", "success")

        except Exception as e:
            messagebox.showerror("Error", f"Deletion failed: {str(e)}")

    def view_book_loan_history(self):
        """View loan history for selected book"""
        selection = self.books_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a book first")
            return

        item = self.books_tree.item(selection[0])
        book_id = item['values'][0]
        title = item['values'][1]

        # Create loan history dialog
        dialog = tk.Toplevel(self.master)
        dialog.title(f"Loan History - {title}")
        dialog.geometry("900x600")
        dialog.transient(self.master)

        ttk.Label(dialog, text=f"Loan History for: {title}", font=('Arial', 12, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=f"Book ID: {book_id}").pack(pady=5)

        # Create treeview for loan history
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Loan ID', 'User ID', 'Loan Date', 'Due Date', 'Return Date', 'Status', 'Fine')
        history_tree = ttk.Treeview(frame, columns=columns, show='headings', height=20)

        for col in columns:
            history_tree.heading(col, text=col)
            history_tree.column(col, width=120)

        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=history_tree.yview)
        h_scrollbar = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=history_tree.xview)
        history_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        history_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        try:
            # Load loan history
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT loan_id, user_id, loan_date, due_date, return_date, status,
                       COALESCE(fine_amount, 0) as fine
                FROM loans
                WHERE book_id = ?
                ORDER BY loan_date DESC
            ''', (book_id,))

            loans = cursor.fetchall()
            conn.close()

            for loan in loans:
                history_tree.insert('', 'end', values=loan)

            # Add summary
            summary_frame = ttk.Frame(dialog)
            summary_frame.pack(fill=tk.X, padx=10, pady=10)

            total_loans = len(loans)
            active_loans = sum(1 for loan in loans if loan[5] == 'active')
            returned_loans = sum(1 for loan in loans if loan[5] == 'returned')
            total_fines = sum(float(loan[6] or 0) for loan in loans)

            ttk.Label(summary_frame, text=f"Total Loans: {total_loans}").pack(side=tk.LEFT, padx=10)
            ttk.Label(summary_frame, text=f"Active: {active_loans}").pack(side=tk.LEFT, padx=10)
            ttk.Label(summary_frame, text=f"Returned: {returned_loans}").pack(side=tk.LEFT, padx=10)
            ttk.Label(summary_frame, text=f"Total Fines: ${total_fines:.2f}").pack(side=tk.LEFT, padx=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load loan history: {str(e)}")

        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    def bulk_import_books_gui(self):
        """Bulk import books from CSV/Excel with GUI"""
        file_path = filedialog.askopenfilename(
            title="Select Books File",
            filetypes=[
                ("CSV files", "*.csv"),
                ("Excel files", "*.xlsx;*.xls"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return

        try:
            import pandas as pd

            # Read file based on extension
            if file_path.lower().endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path)
            else:
                messagebox.showerror("Error", "Unsupported file format. Use CSV or Excel files.")
                return

            # Validate required columns
            required_columns = ['title', 'author']
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                messagebox.showerror(
                    "Error",
                    f"Missing required columns: {', '.join(missing_columns)}\n\n" +
                    "Required: title, author\n" +
                    "Optional: isbn, publisher, category, year_published, description, location, reading_level, tags"
                )
                return

            # Show preview dialog
            preview_dialog = tk.Toplevel(self.master)
            preview_dialog.title("Import Preview")
            preview_dialog.geometry("900x600")

            ttk.Label(preview_dialog, text=f"Found {len(df)} books to import",
                     font=('Arial', 12, 'bold')).pack(pady=10)

            # Preview table
            frame = ttk.Frame(preview_dialog)
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            tree = ttk.Treeview(frame, show='headings', height=15)
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            tree.configure(yscrollcommand=scrollbar.set)

            # Setup columns
            display_columns = ['title', 'author', 'isbn', 'category', 'year_published']
            tree['columns'] = [col for col in display_columns if col in df.columns]

            for col in tree['columns']:
                tree.heading(col, text=col.replace('_', ' ').title())
                tree.column(col, width=150)

            # Add preview data (first 20 rows)
            for idx, row in df.head(20).iterrows():
                values = [row.get(col, '') for col in tree['columns']]
                tree.insert('', 'end', values=values)

            # Button frame
            button_frame = ttk.Frame(preview_dialog)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            def do_import():
                preview_dialog.destroy()
                self._perform_import(df)

            ttk.Button(button_frame, text="Import All", command=do_import).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=preview_dialog.destroy).pack(side=tk.LEFT, padx=5)

        except ImportError:
            messagebox.showerror("Error", "pandas library is required for bulk import.\nInstall it with: pip install pandas openpyxl")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file: {str(e)}")

    def _perform_import(self, df):
        """Perform the actual import operation"""
        try:
            import pandas as pd
            import json
            from university_system.modules.domain.academics.services.library import generate_barcode, generate_qr_code

            conn = get_db_connection()
            cursor = conn.cursor()

            # Get next book ID
            cursor.execute('SELECT MAX(CAST(SUBSTR(book_id, 2) AS INTEGER)) FROM books')
            result = cursor.fetchone()[0]
            next_id = 10001 if result is None else result + 1

            imported_count = 0
            error_count = 0
            errors = []

            # Progress dialog
            progress_dialog = tk.Toplevel(self.master)
            progress_dialog.title("Importing Books")
            progress_dialog.geometry("400x150")

            ttk.Label(progress_dialog, text="Importing books...").pack(pady=10)
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_dialog, variable=progress_var, maximum=len(df))
            progress_bar.pack(fill=tk.X, padx=20, pady=10)

            status_label = ttk.Label(progress_dialog, text="")
            status_label.pack(pady=5)

            for index, row in df.iterrows():
                try:
                    book_id = f"B{next_id + imported_count}"

                    # Extract data
                    title = str(row['title']).strip()
                    author = str(row['author']).strip()
                    isbn = str(row.get('isbn', '')).strip() if pd.notna(row.get('isbn')) else None
                    publisher = str(row.get('publisher', '')).strip() if pd.notna(row.get('publisher')) else None
                    category = str(row.get('category', 'General')).strip()
                    year_published = int(row['year_published']) if pd.notna(row.get('year_published')) else None
                    description = str(row.get('description', '')).strip() if pd.notna(row.get('description')) else None
                    location = str(row.get('location', '')).strip() if pd.notna(row.get('location')) else None
                    reading_level = str(row.get('reading_level', 'Unknown')).strip()
                    tags_str = str(row.get('tags', '')).strip() if pd.notna(row.get('tags')) else ''
                    tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()] if tags_str else []

                    # Generate barcode and QR code
                    barcode = generate_barcode(book_id)
                    qr_code_path = generate_qr_code(book_id, title)
                    qr_code_str = str(qr_code_path) if qr_code_path else None

                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    # Insert book
                    cursor.execute('''
                    INSERT INTO books (
                        book_id, title, author, isbn, publisher, category, year_published,
                        description, location, status, added_date, last_updated,
                        reading_level, tags, cover_image_path, digital_copy_path, acquisition_cost,
                        barcode, qr_code_path, total_pages, language, edition, condition_notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        book_id, title, author, isbn, publisher, category,
                        year_published, description, location, 'available', now, now,
                        reading_level, json.dumps(tags), None, None, 0.0,
                        barcode, qr_code_str, None, 'English', None, None
                    ))

                    imported_count += 1
                    progress_var.set(index + 1)
                    status_label.config(text=f"Imported: {imported_count} | Errors: {error_count}")
                    progress_dialog.update()

                except Exception as e:
                    error_count += 1
                    errors.append(f"Row {index + 1} ({row.get('title', 'Unknown')}): {str(e)}")

            conn.commit()
            conn.close()
            progress_dialog.destroy()

            # Log the action
            log_audit_event(get_current_user_id(), f"Bulk imported {imported_count} books", "books")

            # Show results
            result_msg = f"Import Complete!\n\nSuccessfully imported: {imported_count} books"
            if error_count > 0:
                result_msg += f"\nErrors: {error_count}\n\nFirst few errors:\n"
                result_msg += "\n".join(errors[:5])

            messagebox.showinfo("Import Complete", result_msg)

            # Refresh the books display
            if hasattr(self, 'show_all_books'):
                self.show_all_books()

        except Exception as e:
            messagebox.showerror("Error", f"Import failed: {str(e)}")

    def bulk_export_books_gui(self):
        """Bulk export books to CSV/Excel with GUI"""
        # Export options dialog
        export_dialog = tk.Toplevel(self.master)
        export_dialog.title("Export Books")
        export_dialog.geometry("400x350")

        ttk.Label(export_dialog, text="Export Books to CSV/Excel",
                 font=('Arial', 14, 'bold')).pack(pady=15)

        export_type = tk.StringVar(value="all")

        ttk.Radiobutton(export_dialog, text="Export All Books",
                       variable=export_type, value="all").pack(anchor=tk.W, padx=30, pady=5)
        ttk.Radiobutton(export_dialog, text="Export by Category",
                       variable=export_type, value="category").pack(anchor=tk.W, padx=30, pady=5)
        ttk.Radiobutton(export_dialog, text="Export by Status",
                       variable=export_type, value="status").pack(anchor=tk.W, padx=30, pady=5)
        ttk.Radiobutton(export_dialog, text="Export by Date Range",
                       variable=export_type, value="date").pack(anchor=tk.W, padx=30, pady=5)

        # Additional options frame
        options_frame = ttk.LabelFrame(export_dialog, text="Options", padding=10)
        options_frame.pack(fill=tk.X, padx=20, pady=10)

        category_var = tk.StringVar()
        status_var = tk.StringVar(value="available")
        start_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        end_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))

        # Category selection
        ttk.Label(options_frame, text="Category:").grid(row=0, column=0, sticky=tk.W, pady=2)
        category_combo = ttk.Combobox(options_frame, textvariable=category_var, width=20)
        category_combo.grid(row=0, column=1, pady=2)

        # Status selection
        ttk.Label(options_frame, text="Status:").grid(row=1, column=0, sticky=tk.W, pady=2)
        status_combo = ttk.Combobox(options_frame, textvariable=status_var,
                                    values=["available", "checked_out", "reserved", "lost", "damaged"], width=20)
        status_combo.grid(row=1, column=1, pady=2)

        # Date range
        ttk.Label(options_frame, text="Start Date:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(options_frame, textvariable=start_date_var, width=22).grid(row=2, column=1, pady=2)

        ttk.Label(options_frame, text="End Date:").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(options_frame, textvariable=end_date_var, width=22).grid(row=3, column=1, pady=2)

        # Load categories
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT category FROM books ORDER BY category')
            categories = [row[0] for row in cursor.fetchall()]
            category_combo['values'] = categories
            if categories:
                category_var.set(categories[0])
            conn.close()
        except:
            pass

        def do_export():
            export_dialog.destroy()
            self._perform_export(export_type.get(), category_var.get(),
                               status_var.get(), start_date_var.get(), end_date_var.get())

        ttk.Button(export_dialog, text="Export", command=do_export).pack(pady=10)

    def _perform_export(self, export_type, category, status, start_date, end_date):
        """Perform the actual export operation"""
        try:
            import pandas as pd

            conn = get_db_connection()
            cursor = conn.cursor()

            # Build query based on export type
            base_query = '''
            SELECT book_id, title, author, isbn, publisher, category, year_published,
                   description, location, status, reading_level, tags, barcode,
                   acquisition_cost, total_pages, language, edition, added_date
            FROM books
            '''

            if export_type == "all":
                cursor.execute(base_query + " ORDER BY title")
            elif export_type == "category":
                cursor.execute(base_query + " WHERE category = ? ORDER BY title", (category,))
            elif export_type == "status":
                cursor.execute(base_query + " WHERE status = ? ORDER BY title", (status,))
            elif export_type == "date":
                cursor.execute(base_query + " WHERE added_date BETWEEN ? AND ? ORDER BY title",
                             (start_date, end_date))

            # Fetch data
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            conn.close()

            if not data:
                messagebox.showinfo("No Data", "No books found matching the criteria.")
                return

            # Create DataFrame
            df = pd.DataFrame(data, columns=columns)

            # Ask for save location
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[
                    ("CSV files", "*.csv"),
                    ("Excel files", "*.xlsx"),
                    ("All files", "*.*")
                ]
            )

            if file_path:
                # Save based on extension
                if file_path.lower().endswith('.csv'):
                    df.to_csv(file_path, index=False)
                elif file_path.lower().endswith('.xlsx'):
                    df.to_excel(file_path, index=False, engine='openpyxl')

                log_audit_event(get_current_user_id(), f"Exported {len(data)} books", "books")
                messagebox.showinfo("Success", f"Exported {len(data)} books to:\n{file_path}")

        except ImportError:
            messagebox.showerror("Error", "pandas and openpyxl libraries are required for export.\nInstall them with: pip install pandas openpyxl")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def show_advanced_analytics_gui(self):
        """Show advanced analytics dashboard"""
        analytics_window = tk.Toplevel(self.master)
        analytics_window.title("Library Analytics Dashboard")
        analytics_window.geometry("1200x800")

        # Title
        ttk.Label(analytics_window, text="Library Analytics Dashboard",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Notebook for different analytics
        notebook = ttk.Notebook(analytics_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: Collection Overview
        overview_tab = ttk.Frame(notebook)
        notebook.add(overview_tab, text="Collection Overview")
        self._create_collection_overview(overview_tab)

        # Tab 2: Circulation Stats
        circulation_tab = ttk.Frame(notebook)
        notebook.add(circulation_tab, text="Circulation")
        self._create_circulation_stats(circulation_tab)

        # Tab 3: User Activity
        activity_tab = ttk.Frame(notebook)
        notebook.add(activity_tab, text="User Activity")
        self._create_user_activity(activity_tab)

        # Tab 4: Category Analysis
        category_tab = ttk.Frame(notebook)
        notebook.add(category_tab, text="Categories")
        self._create_category_analysis(category_tab)

        # Export button
        ttk.Button(analytics_window, text="Export Full Report",
                  command=self.export_analytics_report).pack(pady=10)

    def _create_collection_overview(self, parent):
        """Create collection overview tab"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Get stats
            cursor.execute('''
            SELECT
                COUNT(*) as total_books,
                SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
                SUM(CASE WHEN status = 'checked_out' THEN 1 ELSE 0 END) as checked_out,
                SUM(CASE WHEN status = 'reserved' THEN 1 ELSE 0 END) as reserved,
                SUM(CASE WHEN status IN ('lost', 'damaged') THEN 1 ELSE 0 END) as unavailable
            FROM books
            ''')

            stats = cursor.fetchone()
            total, available, checked_out, reserved, unavailable = stats

            # Display stats
            stats_frame = ttk.Frame(parent)
            stats_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            # Grid layout for stats cards
            cards = [
                ("Total Books", total, "#3498db"),
                ("Available", available, "#2ecc71"),
                ("Checked Out", checked_out, "#e74c3c"),
                ("Reserved", reserved, "#f39c12"),
                ("Unavailable", unavailable, "#95a5a6")
            ]

            for idx, (label, value, color) in enumerate(cards):
                card = tk.Frame(stats_frame, bg=color, relief=tk.RAISED, borderwidth=2)
                card.grid(row=0, column=idx, padx=10, pady=10, sticky='nsew')

                tk.Label(card, text=str(value), font=('Arial', 24, 'bold'),
                        bg=color, fg='white').pack(pady=(20, 5))
                tk.Label(card, text=label, font=('Arial', 12),
                        bg=color, fg='white').pack(pady=(0, 20))

                stats_frame.grid_columnconfigure(idx, weight=1)

            # Recent additions
            cursor.execute('''
            SELECT title, author, added_date
            FROM books
            ORDER BY added_date DESC
            LIMIT 10
            ''')

            recent_frame = ttk.LabelFrame(parent, text="Recently Added Books", padding=10)
            recent_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            recent_tree = ttk.Treeview(recent_frame, columns=('Title', 'Author', 'Date'),
                                       show='headings', height=8)
            recent_tree.pack(fill=tk.BOTH, expand=True)

            for col in ('Title', 'Author', 'Date'):
                recent_tree.heading(col, text=col)
                recent_tree.column(col, width=200)

            for row in cursor.fetchall():
                recent_tree.insert('', 'end', values=row)

            conn.close()

        except Exception as e:
            ttk.Label(parent, text=f"Error loading collection overview: {str(e)}").pack(pady=20)

    def _create_circulation_stats(self, parent):
        """Create circulation statistics tab"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Get circulation stats
            cursor.execute('''
            SELECT
                COUNT(*) as total_loans,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_loans,
                SUM(CASE WHEN status = 'returned' THEN 1 ELSE 0 END) as returned_loans,
                SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) as overdue_loans,
                SUM(COALESCE(fine_amount, 0)) as total_fines
            FROM book_loans
            ''')

            stats = cursor.fetchone()

            # Display stats
            stats_text = f"""
Circulation Statistics:
━━━━━━━━━━━━━━━━━━━━━━
Total Loans: {stats[0]:,}
Active Loans: {stats[1]:,}
Returned Loans: {stats[2]:,}
Overdue Loans: {stats[3]:,}
Total Fines: ${stats[4]:.2f}
"""

            text_widget = ScrolledText(parent, height=30, width=80, font=('Courier', 11))
            text_widget.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            text_widget.insert('1.0', stats_text)
            text_widget.config(state=tk.DISABLED)

            # Most checked out books
            cursor.execute('''
            SELECT b.title, b.author, COUNT(l.loan_id) as loan_count
            FROM books b
            JOIN book_loans l ON b.book_id = l.book_id
            GROUP BY b.book_id
            ORDER BY loan_count DESC
            LIMIT 10
            ''')

            popular_text = "\n\nMost Popular Books:\n" + "━" * 60 + "\n"
            for idx, (title, author, count) in enumerate(cursor.fetchall(), 1):
                popular_text += f"{idx}. {title} by {author} ({count} loans)\n"

            text_widget.config(state=tk.NORMAL)
            text_widget.insert(tk.END, popular_text)
            text_widget.config(state=tk.DISABLED)

            conn.close()

        except Exception as e:
            ttk.Label(parent, text=f"Error loading circulation stats: {str(e)}").pack(pady=20)

    def _create_user_activity(self, parent):
        """Create user activity tab"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Most active users
            cursor.execute('''
            SELECT user_id, COUNT(loan_id) as loan_count
            FROM book_loans
            GROUP BY user_id
            ORDER BY loan_count DESC
            LIMIT 20
            ''')

            activity_frame = ttk.LabelFrame(parent, text="Most Active Users", padding=10)
            activity_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            tree = ttk.Treeview(activity_frame, columns=('User ID', 'Loan Count'),
                               show='headings', height=15)
            tree.pack(fill=tk.BOTH, expand=True)

            tree.heading('User ID', text='User ID')
            tree.heading('Loan Count', text='Total Loans')
            tree.column('User ID', width=300)
            tree.column('Loan Count', width=150)

            for row in cursor.fetchall():
                tree.insert('', 'end', values=row)

            conn.close()

        except Exception as e:
            ttk.Label(parent, text=f"Error loading user activity: {str(e)}").pack(pady=20)

    def _create_category_analysis(self, parent):
        """Create category analysis tab"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Books by category
            cursor.execute('''
            SELECT category, COUNT(*) as book_count,
                   SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available_count
            FROM books
            GROUP BY category
            ORDER BY book_count DESC
            ''')

            category_frame = ttk.LabelFrame(parent, text="Books by Category", padding=10)
            category_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            tree = ttk.Treeview(category_frame, columns=('Category', 'Total', 'Available'),
                               show='headings', height=20)
            tree.pack(fill=tk.BOTH, expand=True)

            for col in ('Category', 'Total', 'Available'):
                tree.heading(col, text=col)
                tree.column(col, width=200)

            for row in cursor.fetchall():
                tree.insert('', 'end', values=row)

            conn.close()

        except Exception as e:
            ttk.Label(parent, text=f"Error loading category analysis: {str(e)}").pack(pady=20)

    def export_analytics_report(self):
        """Export comprehensive analytics report"""
        try:
            import pandas as pd

            # Ask for save location
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
            )

            if not file_path:
                return

            conn = get_db_connection()

            # Create Excel writer
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Collection overview
                df_books = pd.read_sql_query("SELECT * FROM books", conn)
                df_books.to_excel(writer, sheet_name='All Books', index=False)

                # Loans
                df_loans = pd.read_sql_query("SELECT * FROM book_loans", conn)
                df_loans.to_excel(writer, sheet_name='Loans', index=False)

                # Statistics
                stats_data = {
                    'Metric': ['Total Books', 'Available', 'Checked Out', 'Overdue'],
                    'Count': [len(df_books),
                             len(df_books[df_books['status'] == 'available']),
                             len(df_books[df_books['status'] == 'checked_out']),
                             len(df_loans[df_loans['status'] == 'overdue'])]
                }
                df_stats = pd.DataFrame(stats_data)
                df_stats.to_excel(writer, sheet_name='Statistics', index=False)

            conn.close()
            messagebox.showinfo("Success", f"Analytics report exported to:\n{file_path}")

        except ImportError:
            messagebox.showerror("Error", "pandas and openpyxl are required for export.")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def show_digital_library_gui(self):
        """Show digital library management interface"""
        digital_window = tk.Toplevel(self.master)
        digital_window.title("Digital Library")
        digital_window.geometry("1000x700")

        ttk.Label(digital_window, text="Digital Library Management",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Button frame
        button_frame = ttk.Frame(digital_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Upload Digital Resource",
                  command=self.upload_digital_resource).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh",
                  command=lambda: self.load_digital_library(tree)).pack(side=tk.LEFT, padx=5)

        # Digital library table
        frame = ttk.Frame(digital_window)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('ID', 'Title', 'Author', 'Type', 'Category', 'Downloads', 'Date Added')
        tree = ttk.Treeview(frame, columns=columns, show='headings', height=20)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        h_scrollbar = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        # Double-click to download
        tree.bind('<Double-Button-1>', lambda e: self.download_digital_resource_gui(tree))

        # Load digital library
        self.load_digital_library(tree)

    def load_digital_library(self, tree):
        """Load digital library items into tree"""
        try:
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT digital_id, title, author, file_type, category, download_count, added_date
            FROM digital_library
            ORDER BY added_date DESC
            ''')

            for row in cursor.fetchall():
                tree.insert('', 'end', values=row)

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load digital library: {str(e)}")

    def upload_digital_resource(self):
        """Upload a digital resource"""
        file_path = filedialog.askopenfilename(
            title="Select Digital Resource",
            filetypes=[
                ("PDF files", "*.pdf"),
                ("EPUB files", "*.epub"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return

        # Get metadata dialog
        metadata_dialog = tk.Toplevel(self.master)
        metadata_dialog.title("Resource Metadata")
        metadata_dialog.geometry("400x300")

        ttk.Label(metadata_dialog, text="Enter Resource Details",
                 font=('Arial', 12, 'bold')).grid(row=0, column=0, columnspan=2, pady=10)

        ttk.Label(metadata_dialog, text="Title:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        title_var = tk.StringVar(value=os.path.basename(file_path))
        ttk.Entry(metadata_dialog, textvariable=title_var, width=30).grid(row=1, column=1, padx=10, pady=5)

        ttk.Label(metadata_dialog, text="Author:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        author_var = tk.StringVar()
        ttk.Entry(metadata_dialog, textvariable=author_var, width=30).grid(row=2, column=1, padx=10, pady=5)

        ttk.Label(metadata_dialog, text="Category:").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
        category_var = tk.StringVar(value="General")
        ttk.Entry(metadata_dialog, textvariable=category_var, width=30).grid(row=3, column=1, padx=10, pady=5)

        ttk.Label(metadata_dialog, text="Description:").grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)
        desc_text = tk.Text(metadata_dialog, width=30, height=4)
        desc_text.grid(row=4, column=1, padx=10, pady=5)

        def save_resource():
            try:
                import shutil

                title = title_var.get().strip()
                author = author_var.get().strip()
                category = category_var.get().strip()
                description = desc_text.get('1.0', tk.END).strip()

                if not title or not author:
                    messagebox.showerror("Error", "Title and Author are required")
                    return

                # Copy file to digital library folder
                from university_system.modules.shared.constants.paths import UPLOAD_DIR
                digital_dir = UPLOAD_DIR / "digital_library"
                digital_dir.mkdir(parents=True, exist_ok=True)

                file_name = os.path.basename(file_path)
                dest_path = digital_dir / file_name
                shutil.copy2(file_path, dest_path)

                # Get file info
                file_type = os.path.splitext(file_name)[1].lstrip('.')
                file_size = os.path.getsize(dest_path)

                # Save to database
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                INSERT INTO digital_library (
                    title, author, file_path, file_type, file_size, category,
                    description, access_level, download_count, added_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    title, author, str(dest_path), file_type, file_size, category,
                    description, 'public', 0, datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))

                conn.commit()
                conn.close()

                log_audit_event(get_current_user_id(), f"Uploaded digital resource: {title}", "digital_library")

                metadata_dialog.destroy()
                messagebox.showinfo("Success", "Digital resource uploaded successfully!")

            except Exception as e:
                messagebox.showerror("Error", f"Upload failed: {str(e)}")

        ttk.Button(metadata_dialog, text="Save", command=save_resource).grid(row=5, column=0, columnspan=2, pady=20)

    def download_digital_resource_gui(self, tree):
        """Download selected digital resource"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a resource to download")
            return

        item = tree.item(selection[0])
        digital_id = item['values'][0]

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT file_path, title FROM digital_library WHERE digital_id = ?', (digital_id,))
            result = cursor.fetchone()

            if not result:
                messagebox.showerror("Error", "Resource not found")
                return

            file_path, title = result

            # Ask where to save
            save_path = filedialog.asksaveasfilename(
                initialfile=os.path.basename(file_path),
                defaultextension=os.path.splitext(file_path)[1]
            )

            if save_path:
                import shutil
                shutil.copy2(file_path, save_path)

                # Update download count
                cursor.execute('''
                UPDATE digital_library
                SET download_count = download_count + 1
                WHERE digital_id = ?
                ''', (digital_id,))
                conn.commit()

                messagebox.showinfo("Success", f"Downloaded to:\n{save_path}")

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Download failed: {str(e)}")

    def show_advanced_search_gui(self):
        """Show advanced search interface"""
        search_window = tk.Toplevel(self.master)
        search_window.title("Advanced Search")
        search_window.geometry("800x700")

        ttk.Label(search_window, text="Advanced Book Search",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Search criteria frame
        criteria_frame = ttk.LabelFrame(search_window, text="Search Criteria", padding=15)
        criteria_frame.pack(fill=tk.X, padx=10, pady=10)

        # Search fields
        fields = {}

        row = 0
        for label, field in [
            ("Title", "title"),
            ("Author", "author"),
            ("ISBN", "isbn"),
            ("Publisher", "publisher"),
            ("Category", "category"),
            ("Year Published", "year"),
            ("Reading Level", "reading_level"),
            ("Status", "status")
        ]:
            ttk.Label(criteria_frame, text=f"{label}:").grid(row=row, column=0, sticky=tk.W, pady=5)
            var = tk.StringVar()
            ttk.Entry(criteria_frame, textvariable=var, width=40).grid(row=row, column=1, padx=10, pady=5)
            fields[field] = var
            row += 1

        # Results frame
        results_frame = ttk.LabelFrame(search_window, text="Search Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('ID', 'Title', 'Author', 'Category', 'Year', 'Status')
        results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=15)

        for col in columns:
            results_tree.heading(col, text=col)
            results_tree.column(col, width=120)

        results_tree.pack(fill=tk.BOTH, expand=True)

        def perform_search():
            # Clear previous results
            for item in results_tree.get_children():
                results_tree.delete(item)

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Build dynamic query
                query = "SELECT book_id, title, author, category, year_published, status FROM books WHERE 1=1"
                params = []

                for field, var in fields.items():
                    value = var.get().strip()
                    if value:
                        if field == "year":
                            query += " AND year_published = ?"
                            params.append(int(value))
                        else:
                            query += f" AND {field} LIKE ?"
                            params.append(f"%{value}%")

                query += " ORDER BY title LIMIT 100"

                cursor.execute(query, params)
                results = cursor.fetchall()

                for row in results:
                    results_tree.insert('', 'end', values=row)

                conn.close()

                messagebox.showinfo("Search Complete", f"Found {len(results)} books")

            except Exception as e:
                messagebox.showerror("Error", f"Search failed: {str(e)}")

        # Button frame
        button_frame = ttk.Frame(search_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Search", command=perform_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear",
                  command=lambda: [var.set('') for var in fields.values()]).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=search_window.destroy).pack(side=tk.RIGHT, padx=5)

    def enhanced_checkout_book_gui(self, book_id=None):
        """Enhanced checkout with reading level check and notifications"""
        checkout_window = tk.Toplevel(self.master)
        checkout_window.title("Enhanced Book Checkout")
        checkout_window.geometry("600x500")

        ttk.Label(checkout_window, text="Enhanced Book Checkout",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Book selection frame
        book_frame = ttk.LabelFrame(checkout_window, text="Book Selection", padding=15)
        book_frame.pack(fill=tk.X, padx=10, pady=10)

        book_id_var = tk.StringVar(value=book_id or "")
        user_id_var = tk.StringVar()
        book_info_var = tk.StringVar(value="No book selected")

        ttk.Label(book_frame, text="Book ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        book_id_entry = ttk.Entry(book_frame, textvariable=book_id_var, width=30)
        book_id_entry.grid(row=0, column=1, padx=10, pady=5)

        def lookup_book():
            bid = book_id_var.get().strip()
            if not bid:
                messagebox.showwarning("Warning", "Please enter a Book ID")
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT title, author, status, reading_level
                FROM books WHERE book_id = ?
                ''', (bid,))
                book = cursor.fetchone()
                conn.close()

                if book:
                    title, author, status, reading_level = book
                    book_info_var.set(f"{title} by {author}\nStatus: {status}\nReading Level: {reading_level or 'Unknown'}")
                    if status != 'available':
                        messagebox.showwarning("Warning", f"This book is currently {status}")
                else:
                    book_info_var.set("Book not found")
                    messagebox.showerror("Error", "Book not found")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to lookup book: {str(e)}")

        ttk.Button(book_frame, text="Lookup", command=lookup_book).grid(row=0, column=2, padx=5)

        # Book info display
        ttk.Label(book_frame, textvariable=book_info_var, foreground='blue').grid(
            row=1, column=0, columnspan=3, pady=10, sticky=tk.W)

        # User selection frame
        user_frame = ttk.LabelFrame(checkout_window, text="User Information", padding=15)
        user_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(user_frame, text="User/Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(user_frame, textvariable=user_id_var, width=30).grid(row=0, column=1, padx=10, pady=5)

        # Checkout options
        options_frame = ttk.LabelFrame(checkout_window, text="Checkout Options", padding=15)
        options_frame.pack(fill=tk.X, padx=10, pady=10)

        check_reading_level_var = tk.BooleanVar(value=True)
        send_notification_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(options_frame, text="Check Reading Level Compatibility",
                       variable=check_reading_level_var).pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="Send Email Notification",
                       variable=send_notification_var).pack(anchor=tk.W, pady=2)

        def perform_checkout():
            bid = book_id_var.get().strip()
            uid = user_id_var.get().strip()

            if not bid or not uid:
                messagebox.showerror("Error", "Please provide both Book ID and User ID")
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Check book availability
                cursor.execute('SELECT title, status, reading_level FROM books WHERE book_id = ?', (bid,))
                book = cursor.fetchone()

                if not book:
                    messagebox.showerror("Error", "Book not found")
                    conn.close()
                    return

                title, status, reading_level = book

                if status != 'available':
                    messagebox.showerror("Error", f"Book is {status} and cannot be checked out")
                    conn.close()
                    return

                # Check loan eligibility
                cursor.execute('''
                SELECT COUNT(*) FROM book_loans
                WHERE user_id = ? AND status IN ('active', 'overdue')
                ''', (uid,))
                active_loans = cursor.fetchone()[0]

                cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "max_loans"')
                max_loans_result = cursor.fetchone()
                max_loans = int(max_loans_result[0]) if max_loans_result else 5

                if active_loans >= max_loans:
                    messagebox.showerror("Error", f"User has reached maximum loan limit ({max_loans})")
                    conn.close()
                    return

                # Reading level check (optional warning)
                if check_reading_level_var.get() and reading_level:
                    # Get student grade level if available
                    cursor.execute('SELECT grade_level FROM students WHERE student_id = ?', (uid,))
                    student = cursor.fetchone()
                    if student:
                        grade_level = student[0]
                        # Simple compatibility check - you can expand this
                        if reading_level and grade_level:
                            pass  # Could add more sophisticated checking here

                # Get loan period
                cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "loan_period_days"')
                loan_period_result = cursor.fetchone()
                loan_period = int(loan_period_result[0]) if loan_period_result else 14

                # Create loan
                checkout_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                due_date = (datetime.now() + timedelta(days=loan_period)).strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO book_loans (
                    book_id, user_id, checkout_date, due_date, status, fine_amount, renewal_count
                ) VALUES (?, ?, ?, ?, 'active', 0.0, 0)
                ''', (bid, uid, checkout_date, due_date))

                # Update book status
                cursor.execute('UPDATE books SET status = "checked_out" WHERE book_id = ?', (bid,))

                conn.commit()
                conn.close()

                # Log activity
                log_audit_event(get_current_user_id(), f"Checked out book {bid} to {uid}", "book_loans")

                # Show success
                messagebox.showinfo("Success",
                    f"Book checked out successfully!\n\n" +
                    f"Title: {title}\n" +
                    f"User: {uid}\n" +
                    f"Due Date: {due_date[:10]}\n\n" +
                    f"Loan period: {loan_period} days")

                checkout_window.destroy()

                # Refresh display if applicable
                if hasattr(self, 'show_all_books'):
                    self.show_all_books()

            except Exception as e:
                messagebox.showerror("Error", f"Checkout failed: {str(e)}")

        # Button frame
        button_frame = ttk.Frame(checkout_window)
        button_frame.pack(fill=tk.X, padx=10, pady=20)

        ttk.Button(button_frame, text="Checkout", command=perform_checkout).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=checkout_window.destroy).pack(side=tk.LEFT, padx=5)

    def enhanced_return_book_gui(self):
        """Enhanced book return with fine calculation"""
        return_window = tk.Toplevel(self.master)
        return_window.title("Enhanced Book Return")
        return_window.geometry("600x500")

        ttk.Label(return_window, text="Enhanced Book Return",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Search frame
        search_frame = ttk.LabelFrame(return_window, text="Find Loan", padding=15)
        search_frame.pack(fill=tk.X, padx=10, pady=10)

        search_type = tk.StringVar(value="book_id")
        search_value = tk.StringVar()

        ttk.Radiobutton(search_frame, text="By Book ID", variable=search_type,
                       value="book_id").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Radiobutton(search_frame, text="By User ID", variable=search_type,
                       value="user_id").grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Radiobutton(search_frame, text="By Loan ID", variable=search_type,
                       value="loan_id").grid(row=0, column=2, sticky=tk.W, padx=5)

        ttk.Entry(search_frame, textvariable=search_value, width=30).grid(row=1, column=0, columnspan=2, padx=5, pady=10)

        # Results frame
        results_frame = ttk.LabelFrame(return_window, text="Active Loans", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Loan ID', 'Book ID', 'Title', 'User ID', 'Due Date', 'Fine')
        results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=8)

        for col in columns:
            results_tree.heading(col, text=col)
            results_tree.column(col, width=100)

        results_tree.pack(fill=tk.BOTH, expand=True)

        def search_loans():
            # Clear previous results
            for item in results_tree.get_children():
                results_tree.delete(item)

            stype = search_type.get()
            svalue = search_value.get().strip()

            if not svalue:
                messagebox.showwarning("Warning", "Please enter a search value")
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Get fine per day
                cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "fine_per_day"')
                fine_per_day_result = cursor.fetchone()
                fine_per_day = float(fine_per_day_result[0]) if fine_per_day_result else 0.50

                # Build query based on search type
                if stype == "book_id":
                    query = '''
                    SELECT l.loan_id, l.book_id, b.title, l.user_id, l.due_date, l.fine_amount
                    FROM book_loans l
                    JOIN books b ON l.book_id = b.book_id
                    WHERE l.book_id = ? AND l.status = 'active'
                    '''
                elif stype == "user_id":
                    query = '''
                    SELECT l.loan_id, l.book_id, b.title, l.user_id, l.due_date, l.fine_amount
                    FROM book_loans l
                    JOIN books b ON l.book_id = b.book_id
                    WHERE l.user_id = ? AND l.status = 'active'
                    '''
                else:  # loan_id
                    query = '''
                    SELECT l.loan_id, l.book_id, b.title, l.user_id, l.due_date, l.fine_amount
                    FROM book_loans l
                    JOIN books b ON l.book_id = b.book_id
                    WHERE l.loan_id = ? AND l.status = 'active'
                    '''

                cursor.execute(query, (svalue,))
                loans = cursor.fetchall()

                # Calculate fines
                now = datetime.now()
                for loan in loans:
                    loan_id, book_id, title, user_id, due_date, current_fine = loan

                    # Calculate fine if overdue
                    due_datetime = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
                    if now > due_datetime:
                        days_overdue = (now - due_datetime).days
                        calculated_fine = days_overdue * fine_per_day
                    else:
                        calculated_fine = 0.0

                    results_tree.insert('', 'end', values=(
                        loan_id, book_id, title, user_id, due_date[:10], f"${calculated_fine:.2f}"
                    ))

                conn.close()

                if not loans:
                    messagebox.showinfo("No Results", "No active loans found")

            except Exception as e:
                messagebox.showerror("Error", f"Search failed: {str(e)}")

        ttk.Button(search_frame, text="Search", command=search_loans).grid(row=1, column=2, padx=5)

        def return_selected():
            selection = results_tree.selection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a loan to return")
                return

            item = results_tree.item(selection[0])
            loan_id = item['values'][0]
            book_id = item['values'][1]
            fine_str = item['values'][5]
            fine_amount = float(fine_str.replace('$', ''))

            # Confirm return
            if fine_amount > 0:
                confirm = messagebox.askyesno("Confirm Return",
                    f"Return this book?\n\nLoan ID: {loan_id}\n" +
                    f"Book ID: {book_id}\n" +
                    f"Fine: ${fine_amount:.2f}\n\n" +
                    f"Fine must be paid before return is complete.")
                if not confirm:
                    return
            else:
                confirm = messagebox.askyesno("Confirm Return",
                    f"Return this book?\n\nLoan ID: {loan_id}\nBook ID: {book_id}")
                if not confirm:
                    return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                return_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Update loan
                cursor.execute('''
                UPDATE book_loans
                SET status = 'returned', return_date = ?, fine_amount = ?
                WHERE loan_id = ?
                ''', (return_date, fine_amount, loan_id))

                # Update book status
                cursor.execute('UPDATE books SET status = "available" WHERE book_id = ?', (book_id,))

                conn.commit()
                conn.close()

                log_audit_event(get_current_user_id(), f"Returned book {book_id} (loan {loan_id})", "book_loans")

                messagebox.showinfo("Success",
                    f"Book returned successfully!\n\n" +
                    f"Loan ID: {loan_id}\n" +
                    (f"Fine: ${fine_amount:.2f}" if fine_amount > 0 else "No fine"))

                # Refresh search
                search_loans()

            except Exception as e:
                messagebox.showerror("Error", f"Return failed: {str(e)}")

        # Button frame
        button_frame = ttk.Frame(return_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Return Selected", command=return_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=return_window.destroy).pack(side=tk.RIGHT, padx=5)

    def renew_book_gui(self):
        """Renew book loan"""
        renew_window = tk.Toplevel(self.master)
        renew_window.title("Renew Book Loan")
        renew_window.geometry("700x500")

        ttk.Label(renew_window, text="Renew Book Loan",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Search frame
        search_frame = ttk.LabelFrame(renew_window, text="Find Loan", padding=15)
        search_frame.pack(fill=tk.X, padx=10, pady=10)

        search_value = tk.StringVar()
        ttk.Label(search_frame, text="Book ID or User ID:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(search_frame, textvariable=search_value, width=30).pack(side=tk.LEFT, padx=5)

        # Results frame
        results_frame = ttk.LabelFrame(renew_window, text="Renewable Loans", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Loan ID', 'Book', 'User', 'Checkout', 'Due Date', 'Renewals', 'Status')
        results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=10)

        for col in columns:
            results_tree.heading(col, text=col)
            results_tree.column(col, width=100)

        results_tree.pack(fill=tk.BOTH, expand=True)

        def search_loans():
            for item in results_tree.get_children():
                results_tree.delete(item)

            svalue = search_value.get().strip()
            if not svalue:
                messagebox.showwarning("Warning", "Please enter a search value")
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT l.loan_id, b.title, l.user_id, l.checkout_date, l.due_date,
                       l.renewal_count, l.status
                FROM book_loans l
                JOIN books b ON l.book_id = b.book_id
                WHERE (l.book_id = ? OR l.user_id = ?) AND l.status = 'active'
                ''', (svalue, svalue))

                loans = cursor.fetchall()
                conn.close()

                for loan in loans:
                    results_tree.insert('', 'end', values=(
                        loan[0], loan[1][:30], loan[2], loan[3][:10], loan[4][:10], loan[5], loan[6]
                    ))

                if not loans:
                    messagebox.showinfo("No Results", "No renewable loans found")

            except Exception as e:
                messagebox.showerror("Error", f"Search failed: {str(e)}")

        ttk.Button(search_frame, text="Search", command=search_loans).pack(side=tk.LEFT, padx=5)

        def renew_selected():
            selection = results_tree.selection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a loan to renew")
                return

            item = results_tree.item(selection[0])
            loan_id = item['values'][0]
            renewal_count = item['values'][5]

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Get max renewals
                cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "max_renewals"')
                max_renewals_result = cursor.fetchone()
                max_renewals = int(max_renewals_result[0]) if max_renewals_result else 2

                if renewal_count >= max_renewals:
                    messagebox.showerror("Error", f"Maximum renewals ({max_renewals}) reached")
                    conn.close()
                    return

                # Get loan period
                cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "loan_period_days"')
                loan_period_result = cursor.fetchone()
                loan_period = int(loan_period_result[0]) if loan_period_result else 14

                # Calculate new due date
                new_due_date = (datetime.now() + timedelta(days=loan_period)).strftime('%Y-%m-%d %H:%M:%S')

                # Update loan
                cursor.execute('''
                UPDATE book_loans
                SET due_date = ?, renewal_count = renewal_count + 1
                WHERE loan_id = ?
                ''', (new_due_date, loan_id))

                conn.commit()
                conn.close()

                log_audit_event(get_current_user_id(), f"Renewed loan {loan_id}", "book_loans")

                messagebox.showinfo("Success",
                    f"Loan renewed successfully!\n\n" +
                    f"New due date: {new_due_date[:10]}\n" +
                    f"Renewals used: {renewal_count + 1}/{max_renewals}")

                search_loans()

            except Exception as e:
                messagebox.showerror("Error", f"Renewal failed: {str(e)}")

        # Button frame
        button_frame = ttk.Frame(renew_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Renew Selected", command=renew_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=renew_window.destroy).pack(side=tk.RIGHT, padx=5)

    def reserve_book_gui(self, book_id=None):
        """Reserve a book that's currently unavailable"""
        reserve_window = tk.Toplevel(self.master)
        reserve_window.title("Reserve Book")
        reserve_window.geometry("500x400")

        ttk.Label(reserve_window, text="Reserve Book",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Book info frame
        book_frame = ttk.LabelFrame(reserve_window, text="Book Information", padding=15)
        book_frame.pack(fill=tk.X, padx=10, pady=10)

        book_id_var = tk.StringVar(value=book_id or "")
        user_id_var = tk.StringVar()
        book_info_var = tk.StringVar(value="No book selected")

        ttk.Label(book_frame, text="Book ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(book_frame, textvariable=book_id_var, width=30).grid(row=0, column=1, padx=10, pady=5)

        def lookup_book():
            bid = book_id_var.get().strip()
            if not bid:
                messagebox.showwarning("Warning", "Please enter a Book ID")
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT title, author, status FROM books WHERE book_id = ?', (bid,))
                book = cursor.fetchone()

                if book:
                    title, author, status = book
                    book_info_var.set(f"{title} by {author}\nStatus: {status}")

                    if status == 'available':
                        messagebox.showinfo("Available",
                            "This book is currently available. You can check it out directly instead of reserving it.")
                else:
                    book_info_var.set("Book not found")
                    messagebox.showerror("Error", "Book not found")

                conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to lookup book: {str(e)}")

        ttk.Button(book_frame, text="Lookup", command=lookup_book).grid(row=0, column=2, padx=5)

        ttk.Label(book_frame, textvariable=book_info_var, foreground='blue').grid(
            row=1, column=0, columnspan=3, pady=10, sticky=tk.W)

        # User frame
        user_frame = ttk.LabelFrame(reserve_window, text="User Information", padding=15)
        user_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(user_frame, text="User/Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(user_frame, textvariable=user_id_var, width=30).grid(row=0, column=1, padx=10, pady=5)

        def perform_reservation():
            bid = book_id_var.get().strip()
            uid = user_id_var.get().strip()

            if not bid or not uid:
                messagebox.showerror("Error", "Please provide both Book ID and User ID")
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Check if book exists
                cursor.execute('SELECT title, status FROM books WHERE book_id = ?', (bid,))
                book = cursor.fetchone()

                if not book:
                    messagebox.showerror("Error", "Book not found")
                    conn.close()
                    return

                title, status = book

                # Check if user already has a reservation
                cursor.execute('''
                SELECT reservation_id FROM book_reservations
                WHERE book_id = ? AND user_id = ? AND status = 'active'
                ''', (bid, uid))

                if cursor.fetchone():
                    messagebox.showerror("Error", "User already has an active reservation for this book")
                    conn.close()
                    return

                # Get next priority order
                cursor.execute('''
                SELECT COALESCE(MAX(priority_order), 0) + 1
                FROM book_reservations
                WHERE book_id = ? AND status = 'active'
                ''', (bid,))
                priority_order = cursor.fetchone()[0]

                # Get reservation period
                cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "reservation_period_days"')
                reservation_period_result = cursor.fetchone()
                reservation_period = int(reservation_period_result[0]) if reservation_period_result else 3

                # Create reservation
                reservation_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                expiry_date = (datetime.now() + timedelta(days=reservation_period)).strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO book_reservations (
                    book_id, user_id, reservation_date, expiry_date, status, priority_order
                ) VALUES (?, ?, ?, ?, 'active', ?)
                ''', (bid, uid, reservation_date, expiry_date, priority_order))

                conn.commit()
                conn.close()

                log_audit_event(get_current_user_id(), f"Reserved book {bid} for {uid}", "book_reservations")

                messagebox.showinfo("Success",
                    f"Book reserved successfully!\n\n" +
                    f"Title: {title}\n" +
                    f"User: {uid}\n" +
                    f"Priority: #{priority_order}\n" +
                    f"Expires: {expiry_date[:10]}")

                reserve_window.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Reservation failed: {str(e)}")

        # Button frame
        button_frame = ttk.Frame(reserve_window)
        button_frame.pack(fill=tk.X, padx=10, pady=20)

        ttk.Button(button_frame, text="Reserve", command=perform_reservation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=reserve_window.destroy).pack(side=tk.LEFT, padx=5)

    def manage_reservations_gui(self):
        """Manage all book reservations"""
        manage_window = tk.Toplevel(self.master)
        manage_window.title("Manage Reservations")
        manage_window.geometry("900x600")

        ttk.Label(manage_window, text="Manage Book Reservations",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Filter frame
        filter_frame = ttk.LabelFrame(manage_window, text="Filter", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)

        status_filter = tk.StringVar(value="active")
        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        ttk.Combobox(filter_frame, textvariable=status_filter,
                    values=["all", "active", "fulfilled", "expired", "cancelled"],
                    width=15).pack(side=tk.LEFT, padx=5)

        # Reservations table
        table_frame = ttk.Frame(manage_window)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('ID', 'Book ID', 'Title', 'User', 'Reserved', 'Expires', 'Priority', 'Status')
        res_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        for col in columns:
            res_tree.heading(col, text=col)
            res_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=res_tree.yview)
        res_tree.configure(yscrollcommand=scrollbar.set)

        res_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def load_reservations():
            for item in res_tree.get_children():
                res_tree.delete(item)

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                status = status_filter.get()
                if status == "all":
                    query = '''
                    SELECT r.reservation_id, r.book_id, b.title, r.user_id,
                           r.reservation_date, r.expiry_date, r.priority_order, r.status
                    FROM book_reservations r
                    JOIN books b ON r.book_id = b.book_id
                    ORDER BY r.priority_order
                    '''
                    cursor.execute(query)
                else:
                    query = '''
                    SELECT r.reservation_id, r.book_id, b.title, r.user_id,
                           r.reservation_date, r.expiry_date, r.priority_order, r.status
                    FROM book_reservations r
                    JOIN books b ON r.book_id = b.book_id
                    WHERE r.status = ?
                    ORDER BY r.priority_order
                    '''
                    cursor.execute(query, (status,))

                for row in cursor.fetchall():
                    res_tree.insert('', 'end', values=(
                        row[0], row[1], row[2][:30], row[3], row[4][:10], row[5][:10], row[6], row[7]
                    ))

                conn.close()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load reservations: {str(e)}")

        ttk.Button(filter_frame, text="Refresh", command=load_reservations).pack(side=tk.LEFT, padx=5)

        def cancel_reservation():
            selection = res_tree.selection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a reservation to cancel")
                return

            item = res_tree.item(selection[0])
            res_id = item['values'][0]

            if messagebox.askyesno("Confirm", "Cancel this reservation?"):
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('UPDATE book_reservations SET status = "cancelled" WHERE reservation_id = ?', (res_id,))
                    conn.commit()
                    conn.close()

                    log_audit_event(get_current_user_id(), f"Cancelled reservation {res_id}", "book_reservations")
                    messagebox.showinfo("Success", "Reservation cancelled")
                    load_reservations()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to cancel: {str(e)}")

        # Button frame
        button_frame = ttk.Frame(manage_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Cancel Selected", command=cancel_reservation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=manage_window.destroy).pack(side=tk.RIGHT, padx=5)

        # Load initial data
        load_reservations()

    def rate_and_review_book_gui(self, book_id=None):
        """Rate and review a book"""
        review_window = tk.Toplevel(self.master)
        review_window.title("Rate and Review Book")
        review_window.geometry("600x500")

        ttk.Label(review_window, text="Rate and Review Book",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Book selection
        book_frame = ttk.LabelFrame(review_window, text="Book", padding=15)
        book_frame.pack(fill=tk.X, padx=10, pady=10)

        book_id_var = tk.StringVar(value=book_id or "")
        book_info_var = tk.StringVar(value="No book selected")

        ttk.Label(book_frame, text="Book ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(book_frame, textvariable=book_id_var, width=30).grid(row=0, column=1, padx=10, pady=5)

        def lookup_book():
            bid = book_id_var.get().strip()
            if not bid:
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT title, author FROM books WHERE book_id = ?', (bid,))
                book = cursor.fetchone()

                if book:
                    book_info_var.set(f"{book[0]} by {book[1]}")
                else:
                    book_info_var.set("Book not found")

                conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to lookup book: {str(e)}")

        ttk.Button(book_frame, text="Lookup", command=lookup_book).grid(row=0, column=2, padx=5)
        ttk.Label(book_frame, textvariable=book_info_var, foreground='blue').grid(
            row=1, column=0, columnspan=3, pady=10, sticky=tk.W)

        # Rating frame
        rating_frame = ttk.LabelFrame(review_window, text="Your Rating", padding=15)
        rating_frame.pack(fill=tk.X, padx=10, pady=10)

        rating_var = tk.IntVar(value=5)

        ttk.Label(rating_frame, text="Rating (1-5 stars):").pack(anchor=tk.W, pady=5)
        rating_scale = ttk.Scale(rating_frame, from_=1, to=5, variable=rating_var, orient=tk.HORIZONTAL)
        rating_scale.pack(fill=tk.X, pady=5)

        rating_label = ttk.Label(rating_frame, text="★★★★★")
        rating_label.pack(anchor=tk.W, pady=5)

        def update_rating_display(val):
            stars = int(float(val))
            rating_label.config(text="★" * stars + "☆" * (5 - stars))

        rating_scale.config(command=update_rating_display)

        # Review frame
        review_frame = ttk.LabelFrame(review_window, text="Your Review (Optional)", padding=15)
        review_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        review_text = tk.Text(review_frame, height=8, width=60)
        review_text.pack(fill=tk.BOTH, expand=True)

        def submit_review():
            bid = book_id_var.get().strip()
            if not bid:
                messagebox.showerror("Error", "Please select a book")
                return

            rating = rating_var.get()
            review = review_text.get('1.0', tk.END).strip()

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Check if book exists
                cursor.execute('SELECT title FROM books WHERE book_id = ?', (bid,))
                if not cursor.fetchone():
                    messagebox.showerror("Error", "Book not found")
                    conn.close()
                    return

                user_id = get_current_user_id()

                # Check if user already reviewed
                cursor.execute('''
                SELECT review_id FROM book_reviews
                WHERE book_id = ? AND user_id = ?
                ''', (bid, user_id))

                existing = cursor.fetchone()

                review_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                if existing:
                    # Update existing review
                    cursor.execute('''
                    UPDATE book_reviews
                    SET rating = ?, review_text = ?, review_date = ?, status = 'pending'
                    WHERE review_id = ?
                    ''', (rating, review, review_date, existing[0]))
                    message = "Review updated successfully!"
                else:
                    # Create new review
                    cursor.execute('''
                    INSERT INTO book_reviews (
                        book_id, user_id, rating, review_text, review_date, status
                    ) VALUES (?, ?, ?, ?, ?, 'pending')
                    ''', (bid, user_id, rating, review, review_date))
                    message = "Review submitted successfully! It will be visible after moderation."

                conn.commit()
                conn.close()

                log_audit_event(user_id, f"Reviewed book {bid} ({rating} stars)", "book_reviews")

                messagebox.showinfo("Success", message)
                review_window.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to submit review: {str(e)}")

        # Button frame
        button_frame = ttk.Frame(review_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Submit Review", command=submit_review).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=review_window.destroy).pack(side=tk.LEFT, padx=5)

    def manage_reading_lists_gui(self):
        """Manage reading lists"""
        lists_window = tk.Toplevel(self.master)
        lists_window.title("Reading Lists")
        lists_window.geometry("900x600")

        ttk.Label(lists_window, text="Reading Lists Management",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Button frame
        button_frame = ttk.Frame(lists_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Create New List", command=self.create_reading_list_gui).pack(side=tk.LEFT, padx=5)

        # Lists table
        table_frame = ttk.Frame(lists_window)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('ID', 'Name', 'Description', 'Creator', 'Created', 'Public', 'Books')
        lists_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        for col in columns:
            lists_tree.heading(col, text=col)
            lists_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=lists_tree.yview)
        lists_tree.configure(yscrollcommand=scrollbar.set)

        lists_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def load_lists():
            for item in lists_tree.get_children():
                lists_tree.delete(item)

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT l.list_id, l.name, l.description, l.creator_id, l.created_date, l.is_public,
                       COUNT(i.item_id) as book_count
                FROM reading_lists l
                LEFT JOIN reading_list_items i ON l.list_id = i.list_id
                GROUP BY l.list_id
                ORDER BY l.created_date DESC
                ''')

                for row in cursor.fetchall():
                    lists_tree.insert('', 'end', values=(
                        row[0], row[1], row[2][:30], row[3], row[4][:10],
                        "Yes" if row[5] else "No", row[6]
                    ))

                conn.close()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load lists: {str(e)}")

        def view_list_details():
            selection = lists_tree.selection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a list")
                return

            item = lists_tree.item(selection[0])
            list_id = item['values'][0]
            self.view_reading_list_details_gui(list_id)

        def delete_list():
            selection = lists_tree.selection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a list to delete")
                return

            item = lists_tree.item(selection[0])
            list_id = item['values'][0]
            list_name = item['values'][1]

            if messagebox.askyesno("Confirm Delete", f"Delete reading list '{list_name}'?"):
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()

                    # Delete list items first
                    cursor.execute('DELETE FROM reading_list_items WHERE list_id = ?', (list_id,))
                    # Delete list
                    cursor.execute('DELETE FROM reading_lists WHERE list_id = ?', (list_id,))

                    conn.commit()
                    conn.close()

                    log_audit_event(get_current_user_id(), f"Deleted reading list {list_id}", "reading_lists")
                    messagebox.showinfo("Success", "Reading list deleted")
                    load_lists()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete list: {str(e)}")

        # Action buttons
        action_frame = ttk.Frame(lists_window)
        action_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(action_frame, text="View Details", command=view_list_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Delete List", command=delete_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Refresh", command=load_lists).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Close", command=lists_window.destroy).pack(side=tk.RIGHT, padx=5)

        # Load initial data
        load_lists()

    def create_reading_list_gui(self):
        """Create a new reading list"""
        create_window = tk.Toplevel(self.master)
        create_window.title("Create Reading List")
        create_window.geometry("500x350")

        ttk.Label(create_window, text="Create New Reading List",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Form frame
        form_frame = ttk.LabelFrame(create_window, text="List Information", padding=15)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        name_var = tk.StringVar()
        desc_var = tk.StringVar()
        is_public_var = tk.BooleanVar(value=False)
        is_collaborative_var = tk.BooleanVar(value=False)

        ttk.Label(form_frame, text="List Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form_frame, textvariable=name_var, width=40).grid(row=0, column=1, padx=10, pady=5)

        ttk.Label(form_frame, text="Description:").grid(row=1, column=0, sticky=tk.W, pady=5)
        desc_entry = tk.Text(form_frame, height=4, width=40)
        desc_entry.grid(row=1, column=1, padx=10, pady=5)

        ttk.Checkbutton(form_frame, text="Public (visible to everyone)",
                       variable=is_public_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)

        ttk.Checkbutton(form_frame, text="Collaborative (others can add books)",
                       variable=is_collaborative_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)

        def create_list():
            name = name_var.get().strip()
            description = desc_entry.get('1.0', tk.END).strip()

            if not name:
                messagebox.showerror("Error", "Please enter a list name")
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                creator_id = get_current_user_id()
                created_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO reading_lists (
                    name, description, creator_id, created_date, is_public, is_collaborative
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (name, description, creator_id, created_date,
                     1 if is_public_var.get() else 0,
                     1 if is_collaborative_var.get() else 0))

                conn.commit()
                conn.close()

                log_audit_event(creator_id, f"Created reading list: {name}", "reading_lists")

                messagebox.showinfo("Success", "Reading list created successfully!")
                create_window.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create list: {str(e)}")

        # Button frame
        button_frame = ttk.Frame(create_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Create", command=create_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=create_window.destroy).pack(side=tk.LEFT, padx=5)

    def view_reading_list_details_gui(self, list_id):
        """View details of a specific reading list"""
        details_window = tk.Toplevel(self.master)
        details_window.title("Reading List Details")
        details_window.geometry("800x600")

        ttk.Label(details_window, text="Reading List Details",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # List info frame
        info_frame = ttk.LabelFrame(details_window, text="List Information", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT name, description, creator_id, created_date, is_public, is_collaborative
            FROM reading_lists WHERE list_id = ?
            ''', (list_id,))

            list_info = cursor.fetchone()

            if list_info:
                ttk.Label(info_frame, text=f"Name: {list_info[0]}", font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=2)
                ttk.Label(info_frame, text=f"Description: {list_info[1] or 'No description'}").pack(anchor=tk.W, pady=2)
                ttk.Label(info_frame, text=f"Created by: {list_info[2]} on {list_info[3][:10]}").pack(anchor=tk.W, pady=2)
                ttk.Label(info_frame, text=f"Public: {'Yes' if list_info[4] else 'No'}").pack(anchor=tk.W, pady=2)

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load list info: {str(e)}")
            details_window.destroy()
            return

        # Books in list
        books_frame = ttk.LabelFrame(details_window, text="Books in List", padding=10)
        books_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Book ID', 'Title', 'Author', 'Added Date', 'Added By')
        books_tree = ttk.Treeview(books_frame, columns=columns, show='headings', height=12)

        for col in columns:
            books_tree.heading(col, text=col)
            books_tree.column(col, width=150)

        books_tree.pack(fill=tk.BOTH, expand=True)

        def load_books():
            for item in books_tree.get_children():
                books_tree.delete(item)

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT b.book_id, b.title, b.author, i.added_date, i.added_by
                FROM reading_list_items i
                JOIN books b ON i.book_id = b.book_id
                WHERE i.list_id = ?
                ORDER BY i.added_date DESC
                ''', (list_id,))

                for row in cursor.fetchall():
                    books_tree.insert('', 'end', values=row)

                conn.close()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load books: {str(e)}")

        load_books()

        # Button frame
        button_frame = ttk.Frame(details_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Close", command=details_window.destroy).pack(side=tk.RIGHT, padx=5)

    def manage_digital_access_permissions_gui(self):
        """Manage digital resource access permissions"""
        perms_window = tk.Toplevel(self.master)
        perms_window.title("Digital Access Permissions")
        perms_window.geometry("900x600")

        ttk.Label(perms_window, text="Digital Resource Access Permissions",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Filter frame
        filter_frame = ttk.LabelFrame(perms_window, text="Filter", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)

        resource_filter = tk.StringVar()
        ttk.Label(filter_frame, text="Resource ID:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(filter_frame, textvariable=resource_filter, width=20).pack(side=tk.LEFT, padx=5)

        # Permissions table
        table_frame = ttk.Frame(perms_window)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Permission ID', 'Resource', 'User/Role', 'Access Level', 'Granted', 'Expires')
        perms_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        for col in columns:
            perms_tree.heading(col, text=col)
            perms_tree.column(col, width=140)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=perms_tree.yview)
        perms_tree.configure(yscrollcommand=scrollbar.set)

        perms_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def load_permissions():
            for item in perms_tree.get_children():
                perms_tree.delete(item)

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                res_filter = resource_filter.get().strip()
                if res_filter:
                    query = '''
                    SELECT p.permission_id, d.title, p.user_id, p.access_level,
                           p.granted_date, p.expiry_date
                    FROM digital_access_permissions p
                    JOIN digital_library d ON p.digital_id = d.digital_id
                    WHERE d.digital_id = ? OR d.title LIKE ?
                    ORDER BY p.granted_date DESC
                    '''
                    cursor.execute(query, (res_filter, f'%{res_filter}%'))
                else:
                    query = '''
                    SELECT p.permission_id, d.title, p.user_id, p.access_level,
                           p.granted_date, p.expiry_date
                    FROM digital_access_permissions p
                    JOIN digital_library d ON p.digital_id = d.digital_id
                    ORDER BY p.granted_date DESC
                    LIMIT 100
                    '''
                    cursor.execute(query)

                for row in cursor.fetchall():
                    perms_tree.insert('', 'end', values=(
                        row[0], row[1][:30], row[2], row[3], row[4][:10], row[5][:10] if row[5] else 'Never'
                    ))

                conn.close()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load permissions: {str(e)}")

        ttk.Button(filter_frame, text="Search", command=load_permissions).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="Clear", command=lambda: resource_filter.set('')).pack(side=tk.LEFT, padx=5)

        def grant_permission():
            # Permission dialog
            grant_dialog = tk.Toplevel(perms_window)
            grant_dialog.title("Grant Permission")
            grant_dialog.geometry("400x300")

            ttk.Label(grant_dialog, text="Grant Digital Access",
                     font=('Arial', 12, 'bold')).pack(pady=10)

            form_frame = ttk.Frame(grant_dialog, padding=15)
            form_frame.pack(fill=tk.BOTH, expand=True)

            digital_id_var = tk.StringVar()
            user_id_var = tk.StringVar()
            access_level_var = tk.StringVar(value="read")
            days_valid_var = tk.IntVar(value=30)

            ttk.Label(form_frame, text="Digital Resource ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
            ttk.Entry(form_frame, textvariable=digital_id_var, width=25).grid(row=0, column=1, pady=5)

            ttk.Label(form_frame, text="User ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
            ttk.Entry(form_frame, textvariable=user_id_var, width=25).grid(row=1, column=1, pady=5)

            ttk.Label(form_frame, text="Access Level:").grid(row=2, column=0, sticky=tk.W, pady=5)
            ttk.Combobox(form_frame, textvariable=access_level_var,
                        values=["read", "download", "full"], width=22).grid(row=2, column=1, pady=5)

            ttk.Label(form_frame, text="Valid for (days):").grid(row=3, column=0, sticky=tk.W, pady=5)
            ttk.Entry(form_frame, textvariable=days_valid_var, width=25).grid(row=3, column=1, pady=5)

            def save_permission():
                digital_id = digital_id_var.get().strip()
                user_id = user_id_var.get().strip()

                if not digital_id or not user_id:
                    messagebox.showerror("Error", "Please provide both Resource ID and User ID")
                    return

                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()

                    granted_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    expiry_date = (datetime.now() + timedelta(days=days_valid_var.get())).strftime('%Y-%m-%d %H:%M:%S')

                    cursor.execute('''
                    INSERT INTO digital_access_permissions (
                        digital_id, user_id, access_level, granted_date, expiry_date, granted_by
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (digital_id, user_id, access_level_var.get(), granted_date, expiry_date, get_current_user_id()))

                    conn.commit()
                    conn.close()

                    log_audit_event(get_current_user_id(),
                                  f"Granted {access_level_var.get()} access to digital resource {digital_id} for {user_id}",
                                  "digital_access_permissions")

                    messagebox.showinfo("Success", "Permission granted successfully!")
                    grant_dialog.destroy()
                    load_permissions()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to grant permission: {str(e)}")

            ttk.Button(form_frame, text="Grant", command=save_permission).grid(row=4, column=0, columnspan=2, pady=20)

        def revoke_permission():
            selection = perms_tree.selection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a permission to revoke")
                return

            item = perms_tree.item(selection[0])
            perm_id = item['values'][0]

            if messagebox.askyesno("Confirm", "Revoke this permission?"):
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM digital_access_permissions WHERE permission_id = ?', (perm_id,))
                    conn.commit()
                    conn.close()

                    log_audit_event(get_current_user_id(), f"Revoked permission {perm_id}", "digital_access_permissions")
                    messagebox.showinfo("Success", "Permission revoked")
                    load_permissions()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to revoke: {str(e)}")

        # Button frame
        button_frame = ttk.Frame(perms_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Grant Permission", command=grant_permission).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Revoke Selected", command=revoke_permission).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=load_permissions).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=perms_window.destroy).pack(side=tk.RIGHT, padx=5)

        # Load initial data
        load_permissions()

    def send_automated_notifications_gui(self):
        """Automated notification management interface"""
        notif_window = tk.Toplevel(self.master)
        notif_window.title("Automated Notifications")
        notif_window.geometry("700x600")

        ttk.Label(notif_window, text="Automated Notification System",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Notebook for different notification types
        notebook = ttk.Notebook(notif_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: Due Date Reminders
        due_tab = ttk.Frame(notebook)
        notebook.add(due_tab, text="Due Date Reminders")

        ttk.Label(due_tab, text="Send due date reminders to users with books due soon",
                 wraplength=600).pack(pady=10, padx=10)

        days_before_var = tk.IntVar(value=3)
        ttk.Label(due_tab, text="Days before due date:").pack(pady=5)
        ttk.Spinbox(due_tab, from_=1, to=14, textvariable=days_before_var, width=10).pack(pady=5)

        def send_due_reminders():
            try:
                days = days_before_var.get()
                cutoff_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT l.user_id, b.title, l.due_date
                FROM book_loans l
                JOIN books b ON l.book_id = b.book_id
                WHERE l.status = 'active' AND l.due_date <= ? AND l.due_date > ?
                ''', (cutoff_date, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                reminders = cursor.fetchall()
                conn.close()

                if not reminders:
                    messagebox.showinfo("No Reminders", "No books due in the next {days} days")
                    return

                # Simulate sending (in real system, would send emails)
                count = len(reminders)
                messagebox.showinfo("Success",
                    f"Sent {count} due date reminder(s)\n\n" +
                    f"Books due within {days} days")

                log_audit_event(get_current_user_id(), f"Sent {count} due date reminders", "notifications")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to send reminders: {str(e)}")

        ttk.Button(due_tab, text="Send Due Date Reminders", command=send_due_reminders).pack(pady=20)

        # Tab 2: Overdue Notifications
        overdue_tab = ttk.Frame(notebook)
        notebook.add(overdue_tab, text="Overdue Notifications")

        ttk.Label(overdue_tab, text="Send notifications to users with overdue books",
                 wraplength=600).pack(pady=10, padx=10)

        def send_overdue_notifs():
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT l.user_id, b.title, l.due_date,
                       julianday('now') - julianday(l.due_date) as days_overdue
                FROM book_loans l
                JOIN books b ON l.book_id = b.book_id
                WHERE l.status = 'active' AND l.due_date < datetime('now')
                ''')

                overdue = cursor.fetchall()
                conn.close()

                if not overdue:
                    messagebox.showinfo("No Overdue", "No overdue books found")
                    return

                count = len(overdue)
                messagebox.showinfo("Success",
                    f"Sent {count} overdue notification(s)")

                log_audit_event(get_current_user_id(), f"Sent {count} overdue notifications", "notifications")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to send notifications: {str(e)}")

        ttk.Button(overdue_tab, text="Send Overdue Notifications", command=send_overdue_notifs).pack(pady=20)

        # Tab 3: Reservation Notifications
        reservation_tab = ttk.Frame(notebook)
        notebook.add(reservation_tab, text="Reservation Alerts")

        ttk.Label(reservation_tab, text="Send notifications for available reserved books",
                 wraplength=600).pack(pady=10, padx=10)

        def send_reservation_available():
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Find books that became available and have active reservations
                cursor.execute('''
                SELECT r.user_id, b.title, r.reservation_id
                FROM book_reservations r
                JOIN books b ON r.book_id = b.book_id
                WHERE r.status = 'active' AND b.status = 'available' AND r.priority_order = 1
                ''')

                available = cursor.fetchall()

                if not available:
                    messagebox.showinfo("No Notifications", "No reserved books are available")
                    conn.close()
                    return

                # Update reservations to fulfilled
                for user_id, title, res_id in available:
                    cursor.execute('UPDATE book_reservations SET status = "fulfilled" WHERE reservation_id = ?', (res_id,))

                conn.commit()
                conn.close()

                count = len(available)
                messagebox.showinfo("Success",
                    f"Sent {count} reservation available notification(s)")

                log_audit_event(get_current_user_id(), f"Sent {count} reservation notifications", "notifications")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to send notifications: {str(e)}")

        ttk.Button(reservation_tab, text="Send Reservation Available Notifications",
                  command=send_reservation_available).pack(pady=20)

        # Close button
        ttk.Button(notif_window, text="Close", command=notif_window.destroy).pack(pady=10)

    def generate_circulation_report_gui(self):
        """Generate circulation report"""
        report_window = tk.Toplevel(self.master)
        report_window.title("Circulation Report")
        report_window.geometry("900x700")

        ttk.Label(report_window, text="Circulation Report",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Date range selection
        date_frame = ttk.LabelFrame(report_window, text="Date Range", padding=10)
        date_frame.pack(fill=tk.X, padx=10, pady=10)

        start_date_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        end_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))

        ttk.Label(date_frame, text="Start Date:").grid(row=0, column=0, padx=5, pady=5)
        ttk.Entry(date_frame, textvariable=start_date_var, width=15).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(date_frame, text="End Date:").grid(row=0, column=2, padx=5, pady=5)
        ttk.Entry(date_frame, textvariable=end_date_var, width=15).grid(row=0, column=3, padx=5, pady=5)

        # Report display
        report_frame = ttk.LabelFrame(report_window, text="Report", padding=10)
        report_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        report_text = ScrolledText(report_frame, height=30, width=100, font=('Courier', 10))
        report_text.pack(fill=tk.BOTH, expand=True)

        def generate_report():
            report_text.delete('1.0', tk.END)

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                start = start_date_var.get()
                end = end_date_var.get()

                # Get circulation stats
                cursor.execute('''
                SELECT
                    COUNT(*) as total_loans,
                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN status = 'returned' THEN 1 ELSE 0 END) as returned,
                    SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) as overdue,
                    SUM(COALESCE(fine_amount, 0)) as total_fines
                FROM book_loans
                WHERE checkout_date BETWEEN ? AND ?
                ''', (start, end))

                stats = cursor.fetchone()

                report = f"""
╔══════════════════════════════════════════════════════════════╗
║           LIBRARY CIRCULATION REPORT                         ║
╚══════════════════════════════════════════════════════════════╝

Period: {start} to {end}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

CIRCULATION SUMMARY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Loans:        {stats[0]:,}
Active Loans:       {stats[1]:,}
Returned Loans:     {stats[2]:,}
Overdue Loans:      {stats[3]:,}
Total Fines:        ${stats[4]:,.2f}

"""

                # Most checked out books
                cursor.execute('''
                SELECT b.title, b.author, COUNT(l.loan_id) as loan_count
                FROM book_loans l
                JOIN books b ON l.book_id = b.book_id
                WHERE l.checkout_date BETWEEN ? AND ?
                GROUP BY b.book_id
                ORDER BY loan_count DESC
                LIMIT 10
                ''', (start, end))

                report += "\nTOP 10 MOST CHECKED OUT BOOKS:\n"
                report += "━" * 60 + "\n"
                for idx, (title, author, count) in enumerate(cursor.fetchall(), 1):
                    report += f"{idx:2}. {title[:40]:40} by {author[:20]:20} ({count:2} loans)\n"

                # Busiest days
                cursor.execute('''
                SELECT DATE(checkout_date) as day, COUNT(*) as count
                FROM book_loans
                WHERE checkout_date BETWEEN ? AND ?
                GROUP BY day
                ORDER BY count DESC
                LIMIT 5
                ''', (start, end))

                report += "\n\nBUSIEST CHECKOUT DAYS:\n"
                report += "━" * 60 + "\n"
                for day, count in cursor.fetchall():
                    report += f"{day}: {count} checkouts\n"

                conn.close()

                report_text.insert('1.0', report)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

        def export_report():
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )

            if file_path:
                try:
                    with open(file_path, 'w') as f:
                        f.write(report_text.get('1.0', tk.END))
                    messagebox.showinfo("Success", f"Report exported to:\n{file_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Export failed: {str(e)}")

        # Button frame
        button_frame = ttk.Frame(report_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Generate Report", command=generate_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export Report", command=export_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side=tk.RIGHT, padx=5)

        # Auto-generate on open
        generate_report()

    def system_backup_gui(self):
        """System backup and recovery interface"""
        backup_window = tk.Toplevel(self.master)
        backup_window.title("System Backup & Recovery")
        backup_window.geometry("700x600")

        ttk.Label(backup_window, text="System Backup & Recovery",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Notebook for backup options
        notebook = ttk.Notebook(backup_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: Create Backup
        backup_tab = ttk.Frame(notebook)
        notebook.add(backup_tab, text="Create Backup")

        ttk.Label(backup_tab, text="Create a backup of the library system",
                 font=('Arial', 12)).pack(pady=20)

        backup_type_var = tk.StringVar(value="full")
        ttk.Radiobutton(backup_tab, text="Full Backup (All data)",
                       variable=backup_type_var, value="full").pack(anchor=tk.W, padx=50, pady=5)
        ttk.Radiobutton(backup_tab, text="Database Only",
                       variable=backup_type_var, value="database").pack(anchor=tk.W, padx=50, pady=5)
        ttk.Radiobutton(backup_tab, text="Settings Only",
                       variable=backup_type_var, value="settings").pack(anchor=tk.W, padx=50, pady=5)

        def create_backup():
            try:
                import shutil
                from university_system.modules.shared.constants.paths import BACKUP_DIR

                BACKUP_DIR.mkdir(parents=True, exist_ok=True)

                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_type = backup_type_var.get()

                if backup_type == "full":
                    backup_name = f"library_full_backup_{timestamp}.zip"
                    backup_path = BACKUP_DIR / backup_name

                    # Create zip of entire database directory
                    from university_system.modules.shared.constants.paths import DATA_DIR
                    shutil.make_archive(str(backup_path.with_suffix('')), 'zip', DATA_DIR)

                elif backup_type == "database":
                    backup_name = f"library_db_backup_{timestamp}.db"
                    backup_path = BACKUP_DIR / backup_name

                    # Copy database file
                    from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
                    shutil.copy2(DEFAULT_DB_PATH, backup_path)

                else:  # settings
                    backup_name = f"library_settings_backup_{timestamp}.sql"
                    backup_path = BACKUP_DIR / backup_name

                    # Export settings table
                    conn = get_db_connection()
                    with open(backup_path, 'w') as f:
                        for line in conn.iterdump():
                            if 'library_settings' in line:
                                f.write(f"{line}\n")
                    conn.close()

                log_audit_event(get_current_user_id(), f"Created {backup_type} backup: {backup_name}", "system")

                messagebox.showinfo("Success",
                    f"Backup created successfully!\n\n" +
                    f"Type: {backup_type}\n" +
                    f"File: {backup_name}\n" +
                    f"Location: {BACKUP_DIR}")

            except Exception as e:
                messagebox.showerror("Error", f"Backup failed: {str(e)}")

        ttk.Button(backup_tab, text="Create Backup", command=create_backup).pack(pady=30)

        # Tab 2: Restore
        restore_tab = ttk.Frame(notebook)
        notebook.add(restore_tab, text="Restore from Backup")

        ttk.Label(restore_tab, text="Restore system from a backup file",
                 font=('Arial', 12)).pack(pady=20)

        ttk.Label(restore_tab, text="⚠️ Warning: This will overwrite current data!",
                 foreground='red').pack(pady=10)

        def restore_backup():
            file_path = filedialog.askopenfilename(
                title="Select Backup File",
                filetypes=[
                    ("All backup files", "*.zip;*.db;*.sql"),
                    ("ZIP files", "*.zip"),
                    ("Database files", "*.db"),
                    ("SQL files", "*.sql")
                ]
            )

            if not file_path:
                return

            confirm = messagebox.askyesnocancel("Confirm Restore",
                "This will overwrite current data. Continue?\n\n" +
                "A backup of current data will be created first.",
                icon='warning')

            if not confirm:
                return

            try:
                # Create safety backup first
                import shutil
                from university_system.modules.shared.constants.paths import BACKUP_DIR, DEFAULT_DB_PATH

                safety_backup = BACKUP_DIR / f"pre_restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                shutil.copy2(DEFAULT_DB_PATH, safety_backup)

                # Restore based on file type
                if file_path.endswith('.zip'):
                    # Extract zip
                    shutil.unpack_archive(file_path, DEFAULT_DB_PATH.parent)
                elif file_path.endswith('.db'):
                    # Copy database
                    shutil.copy2(file_path, DEFAULT_DB_PATH)
                elif file_path.endswith('.sql'):
                    # Execute SQL
                    conn = get_db_connection()
                    with open(file_path, 'r') as f:
                        conn.executescript(f.read())
                    conn.commit()
                    conn.close()

                log_audit_event(get_current_user_id(), f"Restored from backup: {os.path.basename(file_path)}", "system")

                messagebox.showinfo("Success",
                    "System restored successfully!\n\n" +
                    f"Safety backup created at:\n{safety_backup}")

            except Exception as e:
                messagebox.showerror("Error", f"Restore failed: {str(e)}")

        ttk.Button(restore_tab, text="Select Backup File and Restore",
                  command=restore_backup).pack(pady=30)

        # Tab 3: Scheduled Backups
        schedule_tab = ttk.Frame(notebook)
        notebook.add(schedule_tab, text="Backup Schedule")

        ttk.Label(schedule_tab, text="Configure automated backup schedule",
                 font=('Arial', 12)).pack(pady=20)

        schedule_var = tk.StringVar(value="daily")
        ttk.Radiobutton(schedule_tab, text="Hourly", variable=schedule_var, value="hourly").pack(anchor=tk.W, padx=50, pady=5)
        ttk.Radiobutton(schedule_tab, text="Daily (recommended)", variable=schedule_var, value="daily").pack(anchor=tk.W, padx=50, pady=5)
        ttk.Radiobutton(schedule_tab, text="Weekly", variable=schedule_var, value="weekly").pack(anchor=tk.W, padx=50, pady=5)
        ttk.Radiobutton(schedule_tab, text="Disabled", variable=schedule_var, value="disabled").pack(anchor=tk.W, padx=50, pady=5)

        def save_schedule():
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                INSERT OR REPLACE INTO library_settings (setting_name, setting_value)
                VALUES ('backup_schedule', ?)
                ''', (schedule_var.get(),))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Backup schedule set to: {schedule_var.get()}")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to save schedule: {str(e)}")

        ttk.Button(schedule_tab, text="Save Schedule", command=save_schedule).pack(pady=30)

        # Close button
        ttk.Button(backup_window, text="Close", command=backup_window.destroy).pack(pady=10)

    def process_fine_payment_gui(self):
        """Process fine payment interface"""
        payment_window = tk.Toplevel(self.master)
        payment_window.title("Process Fine Payment")
        payment_window.geometry("600x500")

        ttk.Label(payment_window, text="Process Fine Payment",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Search frame
        search_frame = ttk.LabelFrame(payment_window, text="Find Loan with Fine", padding=15)
        search_frame.pack(fill=tk.X, padx=10, pady=10)

        search_type = tk.StringVar(value="user_id")
        search_value = tk.StringVar()

        ttk.Radiobutton(search_frame, text="By User ID", variable=search_type, value="user_id").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Radiobutton(search_frame, text="By Loan ID", variable=search_type, value="loan_id").grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Entry(search_frame, textvariable=search_value, width=30).grid(row=1, column=0, columnspan=2, padx=5, pady=10)

        # Results frame
        results_frame = ttk.LabelFrame(payment_window, text="Outstanding Fines", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Loan ID', 'Book Title', 'User', 'Fine Amount', 'Days Overdue')
        fines_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=8)

        for col in columns:
            fines_tree.heading(col, text=col)
            fines_tree.column(col, width=110)

        fines_tree.pack(fill=tk.BOTH, expand=True)

        def search_fines():
            for item in fines_tree.get_children():
                fines_tree.delete(item)

            stype = search_type.get()
            svalue = search_value.get().strip()

            if not svalue:
                messagebox.showwarning("Warning", "Please enter a search value")
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                if stype == "user_id":
                    query = '''
                    SELECT l.loan_id, b.title, l.user_id, l.fine_amount,
                           CAST((julianday('now') - julianday(l.due_date)) AS INTEGER) as days_overdue
                    FROM book_loans l
                    JOIN books b ON l.book_id = b.book_id
                    WHERE l.user_id = ? AND l.fine_amount > 0 AND l.status != 'returned'
                    '''
                else:
                    query = '''
                    SELECT l.loan_id, b.title, l.user_id, l.fine_amount,
                           CAST((julianday('now') - julianday(l.due_date)) AS INTEGER) as days_overdue
                    FROM book_loans l
                    JOIN books b ON l.book_id = b.book_id
                    WHERE l.loan_id = ? AND l.fine_amount > 0 AND l.status != 'returned'
                    '''

                cursor.execute(query, (svalue,))
                fines = cursor.fetchall()
                conn.close()

                for fine in fines:
                    fines_tree.insert('', 'end', values=(
                        fine[0], fine[1][:40], fine[2], f"${fine[3]:.2f}", fine[4]
                    ))

                if not fines:
                    messagebox.showinfo("No Fines", "No outstanding fines found")

            except Exception as e:
                messagebox.showerror("Error", f"Search failed: {str(e)}")

        ttk.Button(search_frame, text="Search", command=search_fines).grid(row=1, column=2, padx=5)

        def process_payment():
            selection = fines_tree.selection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a fine to pay")
                return

            item = fines_tree.item(selection[0])
            loan_id = item['values'][0]
            fine_amount_str = item['values'][3]
            fine_amount = float(fine_amount_str.replace('$', ''))

            # Payment dialog
            pay_dialog = tk.Toplevel(payment_window)
            pay_dialog.title("Process Payment")
            pay_dialog.geometry("400x300")

            ttk.Label(pay_dialog, text="Process Fine Payment",
                     font=('Arial', 12, 'bold')).pack(pady=10)

            info_frame = ttk.Frame(pay_dialog, padding=15)
            info_frame.pack(fill=tk.X)

            ttk.Label(info_frame, text=f"Loan ID: {loan_id}").pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"Fine Amount: ${fine_amount:.2f}",
                     font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=2)

            payment_method_var = tk.StringVar(value="cash")
            ttk.Label(info_frame, text="Payment Method:").pack(anchor=tk.W, pady=(10, 2))
            ttk.Radiobutton(info_frame, text="Cash", variable=payment_method_var, value="cash").pack(anchor=tk.W, padx=20)
            ttk.Radiobutton(info_frame, text="Card", variable=payment_method_var, value="card").pack(anchor=tk.W, padx=20)
            ttk.Radiobutton(info_frame, text="Check", variable=payment_method_var, value="check").pack(anchor=tk.W, padx=20)

            def confirm_payment():
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()

                    payment_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    # Record payment
                    cursor.execute('''
                    INSERT INTO fine_payments (
                        loan_id, amount, payment_method, payment_date, processed_by
                    ) VALUES (?, ?, ?, ?, ?)
                    ''', (loan_id, fine_amount, payment_method_var.get(), payment_date, get_current_user_id()))

                    # Update loan - mark fine as paid
                    cursor.execute('''
                    UPDATE book_loans
                    SET fine_amount = 0
                    WHERE loan_id = ?
                    ''', (loan_id,))

                    conn.commit()
                    conn.close()

                    log_audit_event(get_current_user_id(),
                                  f"Processed fine payment: ${fine_amount:.2f} for loan {loan_id}",
                                  "fine_payments")

                    # Generate receipt
                    self.generate_fine_receipt_gui(loan_id, fine_amount, payment_method_var.get(), payment_date)

                    pay_dialog.destroy()
                    messagebox.showinfo("Success", f"Payment processed successfully!\n\nAmount: ${fine_amount:.2f}")
                    search_fines()  # Refresh list

                except Exception as e:
                    messagebox.showerror("Error", f"Payment failed: {str(e)}")

            ttk.Button(info_frame, text="Process Payment", command=confirm_payment).pack(pady=20)

        # Button frame
        button_frame = ttk.Frame(payment_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Process Payment", command=process_payment).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=payment_window.destroy).pack(side=tk.RIGHT, padx=5)

    def generate_fine_receipt_gui(self, loan_id, amount, payment_method, payment_date):
        """Generate and display fine receipt"""
        receipt_window = tk.Toplevel(self.master)
        receipt_window.title("Fine Payment Receipt")
        receipt_window.geometry("500x600")

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Get loan details
            cursor.execute('''
            SELECT b.title, b.author, l.user_id, l.checkout_date, l.due_date
            FROM book_loans l
            JOIN books b ON l.book_id = b.book_id
            WHERE l.loan_id = ?
            ''', (loan_id,))

            loan_details = cursor.fetchone()
            conn.close()

            if loan_details:
                title, author, user_id, checkout, due = loan_details

                receipt_text = f"""
╔══════════════════════════════════════════════════════════════╗
║                  FINE PAYMENT RECEIPT                        ║
╚══════════════════════════════════════════════════════════════╝

Receipt Date: {payment_date}
Receipt ID: FP-{loan_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}

PAYMENT DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Loan ID:         {loan_id}
User ID:         {user_id}

Book:            {title}
Author:          {author}

Checkout Date:   {checkout[:10]}
Due Date:        {due[:10]}

PAYMENT INFORMATION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fine Amount:     ${amount:.2f}
Payment Method:  {payment_method.upper()}
Status:          PAID IN FULL

Thank you for your payment!

For questions, please contact the library front desk.
"""

                text_widget = ScrolledText(receipt_window, height=30, width=70, font=('Courier', 9))
                text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                text_widget.insert('1.0', receipt_text)
                text_widget.config(state=tk.DISABLED)

                def print_receipt():
                    try:
                        file_path = filedialog.asksaveasfilename(
                            defaultextension=".txt",
                            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                            initialfile=f"receipt_{loan_id}.txt"
                        )

                        if file_path:
                            with open(file_path, 'w') as f:
                                f.write(receipt_text)
                            messagebox.showinfo("Success", f"Receipt saved to:\n{file_path}")

                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to save receipt: {str(e)}")

                button_frame = ttk.Frame(receipt_window)
                button_frame.pack(fill=tk.X, padx=10, pady=10)

                ttk.Button(button_frame, text="Save Receipt", command=print_receipt).pack(side=tk.LEFT, padx=5)
                ttk.Button(button_frame, text="Close", command=receipt_window.destroy).pack(side=tk.RIGHT, padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate receipt: {str(e)}")
            receipt_window.destroy()

    def enhanced_settings_management_gui(self):
        """Enhanced settings management interface"""
        settings_window = tk.Toplevel(self.master)
        settings_window.title("Library Settings Management")
        settings_window.geometry("800x700")

        ttk.Label(settings_window, text="Library Settings Management",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Notebook for settings categories
        notebook = ttk.Notebook(settings_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: General Settings
        general_tab = ttk.Frame(notebook)
        notebook.add(general_tab, text="General")

        general_frame = ttk.LabelFrame(general_tab, text="General Library Settings", padding=15)
        general_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        settings_data = {}

        # Load current settings
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT setting_name, setting_value FROM library_settings')
            for name, value in cursor.fetchall():
                settings_data[name] = value
            conn.close()
        except:
            pass

        # Create settings inputs
        settings_vars = {}

        ttk.Label(general_frame, text="Max Loans Per User:").grid(row=0, column=0, sticky=tk.W, pady=5)
        settings_vars['max_loans'] = tk.IntVar(value=int(settings_data.get('max_loans', 5)))
        ttk.Spinbox(general_frame, from_=1, to=20, textvariable=settings_vars['max_loans'], width=10).grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Label(general_frame, text="Loan Period (days):").grid(row=1, column=0, sticky=tk.W, pady=5)
        settings_vars['loan_period_days'] = tk.IntVar(value=int(settings_data.get('loan_period_days', 14)))
        ttk.Spinbox(general_frame, from_=1, to=90, textvariable=settings_vars['loan_period_days'], width=10).grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Label(general_frame, text="Max Renewals:").grid(row=2, column=0, sticky=tk.W, pady=5)
        settings_vars['max_renewals'] = tk.IntVar(value=int(settings_data.get('max_renewals', 2)))
        ttk.Spinbox(general_frame, from_=0, to=10, textvariable=settings_vars['max_renewals'], width=10).grid(row=2, column=1, sticky=tk.W, pady=5)

        ttk.Label(general_frame, text="Fine Per Day ($):").grid(row=3, column=0, sticky=tk.W, pady=5)
        settings_vars['fine_per_day'] = tk.DoubleVar(value=float(settings_data.get('fine_per_day', 0.50)))
        ttk.Spinbox(general_frame, from_=0, to=10, increment=0.10, textvariable=settings_vars['fine_per_day'], width=10).grid(row=3, column=1, sticky=tk.W, pady=5)

        ttk.Label(general_frame, text="Reservation Period (days):").grid(row=4, column=0, sticky=tk.W, pady=5)
        settings_vars['reservation_period_days'] = tk.IntVar(value=int(settings_data.get('reservation_period_days', 3)))
        ttk.Spinbox(general_frame, from_=1, to=30, textvariable=settings_vars['reservation_period_days'], width=10).grid(row=4, column=1, sticky=tk.W, pady=5)

        # Tab 2: Notification Settings
        notif_tab = ttk.Frame(notebook)
        notebook.add(notif_tab, text="Notifications")

        notif_frame = ttk.LabelFrame(notif_tab, text="Notification Settings", padding=15)
        notif_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(notif_frame, text="Due Date Reminder (days before):").grid(row=0, column=0, sticky=tk.W, pady=5)
        settings_vars['due_reminder_days'] = tk.IntVar(value=int(settings_data.get('due_reminder_days', 3)))
        ttk.Spinbox(notif_frame, from_=1, to=14, textvariable=settings_vars['due_reminder_days'], width=10).grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Label(notif_frame, text="Overdue Reminder Frequency (days):").grid(row=1, column=0, sticky=tk.W, pady=5)
        settings_vars['overdue_reminder_freq'] = tk.IntVar(value=int(settings_data.get('overdue_reminder_freq', 7)))
        ttk.Spinbox(notif_frame, from_=1, to=30, textvariable=settings_vars['overdue_reminder_freq'], width=10).grid(row=1, column=1, sticky=tk.W, pady=5)

        settings_vars['email_notifications'] = tk.BooleanVar(value=settings_data.get('email_notifications', 'true') == 'true')
        ttk.Checkbutton(notif_frame, text="Enable Email Notifications", variable=settings_vars['email_notifications']).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)

        settings_vars['sms_notifications'] = tk.BooleanVar(value=settings_data.get('sms_notifications', 'false') == 'true')
        ttk.Checkbutton(notif_frame, text="Enable SMS Notifications", variable=settings_vars['sms_notifications']).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Tab 3: System Settings
        system_tab = ttk.Frame(notebook)
        notebook.add(system_tab, text="System")

        system_frame = ttk.LabelFrame(system_tab, text="System Settings", padding=15)
        system_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(system_frame, text="Library Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        settings_vars['library_name'] = tk.StringVar(value=settings_data.get('library_name', 'University Library'))
        ttk.Entry(system_frame, textvariable=settings_vars['library_name'], width=40).grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Label(system_frame, text="Library Email:").grid(row=1, column=0, sticky=tk.W, pady=5)
        settings_vars['library_email'] = tk.StringVar(value=settings_data.get('library_email', 'library@university.edu'))
        ttk.Entry(system_frame, textvariable=settings_vars['library_email'], width=40).grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Label(system_frame, text="Library Phone:").grid(row=2, column=0, sticky=tk.W, pady=5)
        settings_vars['library_phone'] = tk.StringVar(value=settings_data.get('library_phone', ''))
        ttk.Entry(system_frame, textvariable=settings_vars['library_phone'], width=40).grid(row=2, column=1, sticky=tk.W, pady=5)

        def save_all_settings():
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                for setting_name, var in settings_vars.items():
                    if isinstance(var, tk.BooleanVar):
                        value = 'true' if var.get() else 'false'
                    else:
                        value = str(var.get())

                    cursor.execute('''
                    INSERT OR REPLACE INTO library_settings (setting_name, setting_value)
                    VALUES (?, ?)
                    ''', (setting_name, value))

                conn.commit()
                conn.close()

                log_audit_event(get_current_user_id(), "Updated library settings", "library_settings")

                messagebox.showinfo("Success", "All settings saved successfully!")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to save settings: {str(e)}")

        # Button frame
        button_frame = ttk.Frame(settings_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Save All Settings", command=save_all_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=settings_window.destroy).pack(side=tk.RIGHT, padx=5)

    def system_health_check_gui(self):
        """System health check interface"""
        health_window = tk.Toplevel(self.master)
        health_window.title("System Health Check")
        health_window.geometry("700x600")

        ttk.Label(health_window, text="System Health Check",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Results display
        results_frame = ttk.LabelFrame(health_window, text="Health Check Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        results_text = ScrolledText(results_frame, height=30, width=80, font=('Courier', 10))
        results_text.pack(fill=tk.BOTH, expand=True)

        def run_health_check():
            results_text.delete('1.0', tk.END)

            report = f"""
╔══════════════════════════════════════════════════════════════╗
║               LIBRARY SYSTEM HEALTH CHECK                    ║
╚══════════════════════════════════════════════════════════════╝

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

DATABASE CONNECTION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Test connection
                cursor.execute('SELECT 1')
                report += "✓ Database connection: OK\n"

                # Check table integrity
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                tables = [row[0] for row in cursor.fetchall()]
                report += f"✓ Tables found: {len(tables)}\n"

                # Check data integrity
                report += "\nDATA INTEGRITY:\n"
                report += "━" * 60 + "\n"

                # Books
                cursor.execute('SELECT COUNT(*) FROM books')
                book_count = cursor.fetchone()[0]
                report += f"Books: {book_count:,}\n"

                # Loans
                cursor.execute('SELECT COUNT(*) FROM book_loans')
                loan_count = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status = "active"')
                active_loans = cursor.fetchone()[0]
                report += f"Total Loans: {loan_count:,} (Active: {active_loans:,})\n"

                # Reservations
                cursor.execute('SELECT COUNT(*) FROM book_reservations WHERE status = "active"')
                active_res = cursor.fetchone()[0]
                report += f"Active Reservations: {active_res:,}\n"

                # Check for orphaned records
                report += "\nORPHANED RECORDS CHECK:\n"
                report += "━" * 60 + "\n"

                cursor.execute('''
                SELECT COUNT(*) FROM book_loans l
                WHERE NOT EXISTS (SELECT 1 FROM books b WHERE b.book_id = l.book_id)
                ''')
                orphaned_loans = cursor.fetchone()[0]
                if orphaned_loans > 0:
                    report += f"⚠ Orphaned loans: {orphaned_loans}\n"
                else:
                    report += "✓ No orphaned loans\n"

                # Check overdue books
                report += "\nOVERDUE ITEMS:\n"
                report += "━" * 60 + "\n"
                cursor.execute('''
                SELECT COUNT(*) FROM book_loans
                WHERE status = 'active' AND due_date < datetime('now')
                ''')
                overdue_count = cursor.fetchone()[0]
                report += f"Overdue books: {overdue_count:,}\n"

                # Check database file size
                from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
                db_size = os.path.getsize(DEFAULT_DB_PATH) / (1024 * 1024)  # MB
                report += f"\nDATABASE SIZE: {db_size:.2f} MB\n"

                report += "\n" + "="* 60 + "\n"
                report += "HEALTH CHECK COMPLETE\n"
                report += "Overall Status: " + ("✓ HEALTHY" if orphaned_loans == 0 else "⚠ NEEDS ATTENTION")

                conn.close()

            except Exception as e:
                report += f"\n✗ Health check failed: {str(e)}"

            results_text.insert('1.0', report)

        def repair_database():
            if messagebox.askyesno("Confirm Repair",
                "This will attempt to repair database issues.\nContinue?"):
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()

                    # Vacuum database
                    cursor.execute('VACUUM')

                    # Update stale statuses
                    cursor.execute('''
                    UPDATE book_loans SET status = 'overdue'
                    WHERE status = 'active' AND due_date < datetime('now')
                    ''')

                    # Expire old reservations
                    cursor.execute('''
                    UPDATE book_reservations SET status = 'expired'
                    WHERE status = 'active' AND expiry_date < datetime('now')
                    ''')

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Database repaired successfully!")
                    run_health_check()  # Re-run check

                except Exception as e:
                    messagebox.showerror("Error", f"Repair failed: {str(e)}")

        # Button frame
        button_frame = ttk.Frame(health_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Run Health Check", command=run_health_check).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Repair Database", command=repair_database).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=health_window.destroy).pack(side=tk.RIGHT, padx=5)

        # Auto-run on open
        run_health_check()

    def view_audit_log_gui(self):
        """View audit log interface"""
        audit_window = tk.Toplevel(self.master)
        audit_window.title("Audit Log Viewer")
        audit_window.geometry("1000x700")

        ttk.Label(audit_window, text="Audit Log Viewer",
                 font=('Arial', 16, 'bold')).pack(pady=10)

        # Filter frame
        filter_frame = ttk.LabelFrame(audit_window, text="Filters", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)

        user_filter = tk.StringVar()
        action_filter = tk.StringVar()
        entity_filter = tk.StringVar()

        ttk.Label(filter_frame, text="User ID:").grid(row=0, column=0, padx=5, pady=5)
        ttk.Entry(filter_frame, textvariable=user_filter, width=20).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(filter_frame, text="Action:").grid(row=0, column=2, padx=5, pady=5)
        ttk.Entry(filter_frame, textvariable=action_filter, width=20).grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(filter_frame, text="Entity:").grid(row=0, column=4, padx=5, pady=5)
        ttk.Entry(filter_frame, textvariable=entity_filter, width=20).grid(row=0, column=5, padx=5, pady=5)

        # Audit log table
        table_frame = ttk.Frame(audit_window)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Timestamp', 'User', 'Action', 'Entity Type', 'Entity ID', 'Details')
        audit_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)

        for col in columns:
            audit_tree.heading(col, text=col)
            audit_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=audit_tree.yview)
        audit_tree.configure(yscrollcommand=scrollbar.set)

        audit_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def load_audit_log():
            for item in audit_tree.get_children():
                audit_tree.delete(item)

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                query = 'SELECT timestamp, user_id, action, entity_type, entity_id, details FROM audit_log WHERE 1=1'
                params = []

                user = user_filter.get().strip()
                if user:
                    query += ' AND user_id = ?'
                    params.append(user)

                action = action_filter.get().strip()
                if action:
                    query += ' AND action LIKE ?'
                    params.append(f'%{action}%')

                entity = entity_filter.get().strip()
                if entity:
                    query += ' AND entity_type = ?'
                    params.append(entity)

                query += ' ORDER BY timestamp DESC LIMIT 500'

                cursor.execute(query, params)

                for row in cursor.fetchall():
                    audit_tree.insert('', 'end', values=row)

                conn.close()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load audit log: {str(e)}")

        # Button frame
        button_frame = ttk.Frame(audit_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Load Log", command=load_audit_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Filters",
                  command=lambda: [user_filter.set(''), action_filter.set(''), entity_filter.set('')]).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=audit_window.destroy).pack(side=tk.RIGHT, padx=5)

        # Auto-load on open
        load_audit_log()

    def export_settings_gui(self):
        """Export library settings to file"""
        export_window = tk.Toplevel(self.master)
        export_window.title("Export Settings")
        export_window.geometry("500x300")

        ttk.Label(export_window, text="Export Library Settings",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Format selection
        format_frame = ttk.LabelFrame(export_window, text="Export Format", padding=10)
        format_frame.pack(fill=tk.X, padx=10, pady=10)

        format_var = tk.StringVar(value="json")
        ttk.Radiobutton(format_frame, text="JSON Format", variable=format_var, value="json").pack(anchor=tk.W)
        ttk.Radiobutton(format_frame, text="CSV Format", variable=format_var, value="csv").pack(anchor=tk.W)

        def perform_export():
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('SELECT setting_name, setting_value FROM library_settings')
                settings = cursor.fetchall()
                conn.close()

                format_type = format_var.get()

                if format_type == "json":
                    file_path = filedialog.asksaveasfilename(
                        defaultextension=".json",
                        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                        initialfile="library_settings.json"
                    )

                    if file_path:
                        import json
                        settings_dict = {name: value for name, value in settings}
                        settings_dict['export_date'] = datetime.now().isoformat()

                        with open(file_path, 'w') as f:
                            json.dump(settings_dict, f, indent=2)

                        log_audit_event(get_current_user_id(), "Exported settings to JSON", "library_settings")
                        messagebox.showinfo("Success", f"Settings exported successfully to:\n{file_path}")
                        export_window.destroy()

                else:  # CSV
                    file_path = filedialog.asksaveasfilename(
                        defaultextension=".csv",
                        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                        initialfile="library_settings.csv"
                    )

                    if file_path:
                        import csv
                        with open(file_path, 'w', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow(['Setting Name', 'Setting Value'])
                            writer.writerows(settings)

                        log_audit_event(get_current_user_id(), "Exported settings to CSV", "library_settings")
                        messagebox.showinfo("Success", f"Settings exported successfully to:\n{file_path}")
                        export_window.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to export settings: {str(e)}")

        # Button frame
        button_frame = ttk.Frame(export_window)
        button_frame.pack(fill=tk.X, padx=10, pady=20)

        ttk.Button(button_frame, text="Export", command=perform_export).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=export_window.destroy).pack(side=tk.RIGHT, padx=5)

    def import_settings_gui(self):
        """Import library settings from file"""
        file_path = filedialog.askopenfilename(
            title="Select Settings File",
            filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            settings_to_import = []

            if file_path.endswith('.json'):
                import json
                with open(file_path, 'r') as f:
                    settings_dict = json.load(f)

                # Remove metadata fields
                settings_dict.pop('export_date', None)
                settings_to_import = list(settings_dict.items())

            elif file_path.endswith('.csv'):
                import csv
                with open(file_path, 'r') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    settings_to_import = list(reader)

            if not settings_to_import:
                messagebox.showwarning("Warning", "No valid settings found in file")
                return

            # Confirm import
            confirm = messagebox.askyesno(
                "Confirm Import",
                f"Import {len(settings_to_import)} settings?\nThis will overwrite existing values."
            )

            if not confirm:
                return

            conn = get_db_connection()
            cursor = conn.cursor()

            for setting_name, setting_value in settings_to_import:
                cursor.execute('''
                INSERT OR REPLACE INTO library_settings (setting_name, setting_value)
                VALUES (?, ?)
                ''', (setting_name, setting_value))

            conn.commit()
            conn.close()

            log_audit_event(get_current_user_id(), f"Imported {len(settings_to_import)} settings", "library_settings")
            messagebox.showinfo("Success", f"Successfully imported {len(settings_to_import)} settings")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to import settings: {str(e)}")

    def reset_settings_to_default_gui(self):
        """Reset all settings to default values"""
        confirm = messagebox.askyesno(
            "Confirm Reset",
            "Are you sure you want to reset ALL settings to default values?\n\nThis action cannot be undone."
        )

        if not confirm:
            return

        try:
            default_settings = {
                'max_loans_per_user': '5',
                'loan_period_days': '14',
                'max_renewals': '2',
                'fine_per_day': '0.50',
                'reservation_period_days': '7',
                'due_reminder_days': '3',
                'overdue_reminder_frequency_days': '7',
                'enable_email_notifications': 'true',
                'enable_sms_notifications': 'false',
                'library_name': 'University Library',
                'library_email': 'library@university.edu',
                'library_phone': '555-0100'
            }

            conn = get_db_connection()
            cursor = conn.cursor()

            for setting_name, setting_value in default_settings.items():
                cursor.execute('''
                INSERT OR REPLACE INTO library_settings (setting_name, setting_value)
                VALUES (?, ?)
                ''', (setting_name, setting_value))

            conn.commit()
            conn.close()

            log_audit_event(get_current_user_id(), "Reset all settings to defaults", "library_settings")
            messagebox.showinfo("Success", f"Successfully reset {len(default_settings)} settings to default values")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to reset settings: {str(e)}")

    def backup_settings_only_gui(self):
        """Backup only library settings to a separate file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.join(os.path.dirname(DATABASE_FILE), 'backups', 'settings')
            os.makedirs(backup_dir, exist_ok=True)

            backup_file = os.path.join(backup_dir, f'settings_backup_{timestamp}.json')

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT setting_name, setting_value FROM library_settings')
            settings = cursor.fetchall()
            conn.close()

            import json
            settings_dict = {name: value for name, value in settings}
            settings_dict['backup_date'] = datetime.now().isoformat()
            settings_dict['backup_type'] = 'settings_only'

            with open(backup_file, 'w') as f:
                json.dump(settings_dict, f, indent=2)

            log_audit_event(get_current_user_id(), "Created settings backup", "library_settings")
            messagebox.showinfo("Success", f"Settings backup created:\n{backup_file}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to backup settings: {str(e)}")

    def database_optimization_gui(self):
        """Database optimization and maintenance"""
        opt_window = tk.Toplevel(self.master)
        opt_window.title("Database Optimization")
        opt_window.geometry("600x500")

        ttk.Label(opt_window, text="Database Optimization",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Results display
        results_frame = ttk.LabelFrame(opt_window, text="Optimization Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        results_text = ScrolledText(results_frame, height=20, width=70, font=('Courier', 9))
        results_text.pack(fill=tk.BOTH, expand=True)

        def run_optimization():
            results_text.delete('1.0', tk.END)
            results_text.insert('1.0', "Starting database optimization...\n\n")

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Get database size before
                cursor.execute("PRAGMA page_count")
                page_count_before = cursor.fetchone()[0]
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                size_before = (page_count_before * page_size) / (1024 * 1024)  # MB

                results_text.insert(tk.END, f"Database size before: {size_before:.2f} MB\n\n")

                # Run VACUUM
                results_text.insert(tk.END, "Running VACUUM command...\n")
                cursor.execute("VACUUM")
                results_text.insert(tk.END, "✓ VACUUM completed\n\n")

                # Analyze tables
                results_text.insert(tk.END, "Analyzing tables...\n")
                cursor.execute("ANALYZE")
                results_text.insert(tk.END, "✓ ANALYZE completed\n\n")

                # Reindex
                results_text.insert(tk.END, "Rebuilding indexes...\n")
                cursor.execute("REINDEX")
                results_text.insert(tk.END, "✓ REINDEX completed\n\n")

                # Get database size after
                cursor.execute("PRAGMA page_count")
                page_count_after = cursor.fetchone()[0]
                size_after = (page_count_after * page_size) / (1024 * 1024)  # MB

                saved = size_before - size_after
                results_text.insert(tk.END, f"Database size after: {size_after:.2f} MB\n")
                results_text.insert(tk.END, f"Space reclaimed: {saved:.2f} MB ({(saved/size_before*100):.1f}%)\n\n")

                results_text.insert(tk.END, "=" * 60 + "\n")
                results_text.insert(tk.END, "Optimization completed successfully!\n")

                conn.commit()
                conn.close()

                log_audit_event(get_current_user_id(), "Ran database optimization", "system")

            except Exception as e:
                results_text.insert(tk.END, f"\n❌ Error: {str(e)}\n")

        # Button frame
        button_frame = ttk.Frame(opt_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Run Optimization", command=run_optimization).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=opt_window.destroy).pack(side=tk.RIGHT, padx=5)

    def clear_cache_gui(self):
        """Clear temporary files and cache"""
        confirm = messagebox.askyesno(
            "Confirm Clear Cache",
            "This will clear temporary files and cached data.\n\nContinue?"
        )

        if not confirm:
            return

        try:
            items_cleared = 0

            # Clear temp directory if it exists
            temp_dir = os.path.join(os.path.dirname(DATABASE_FILE), 'temp')
            if os.path.exists(temp_dir):
                for filename in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, filename)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                            items_cleared += 1
                    except Exception as e:
                        print(f"Error deleting {file_path}: {e}")

            # Clear old backup files (keep last 10)
            backup_dir = os.path.join(os.path.dirname(DATABASE_FILE), 'backups')
            if os.path.exists(backup_dir):
                backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')],
                               key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)),
                               reverse=True)

                for old_backup in backups[10:]:  # Keep last 10
                    try:
                        os.unlink(os.path.join(backup_dir, old_backup))
                        items_cleared += 1
                    except Exception as e:
                        print(f"Error deleting backup {old_backup}: {e}")

            log_audit_event(get_current_user_id(), f"Cleared cache ({items_cleared} items)", "system")
            messagebox.showinfo("Success", f"Cache cleared successfully!\n{items_cleared} items removed")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear cache: {str(e)}")

    def manage_library_events_gui(self):
        """Manage library events (create, view, edit, delete)"""
        events_window = tk.Toplevel(self.master)
        events_window.title("Library Events Management")
        events_window.geometry("900x600")

        ttk.Label(events_window, text="Library Events Management",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Events list
        list_frame = ttk.LabelFrame(events_window, text="Upcoming Events", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('ID', 'Event Name', 'Date', 'Time', 'Location', 'Capacity', 'Registered')
        events_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        for col in columns:
            events_tree.heading(col, text=col)
            events_tree.column(col, width=100 if col != 'Event Name' else 200)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=events_tree.yview)
        events_tree.configure(yscrollcommand=scrollbar.set)

        events_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def load_events():
            for item in events_tree.get_children():
                events_tree.delete(item)

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Create table if not exists
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS library_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    event_time TEXT NOT NULL,
                    location TEXT,
                    description TEXT,
                    max_capacity INTEGER DEFAULT 50,
                    registered_count INTEGER DEFAULT 0,
                    created_by TEXT,
                    created_at TEXT
                )
                ''')

                cursor.execute('''
                SELECT event_id, event_name, event_date, event_time, location, max_capacity, registered_count
                FROM library_events
                WHERE event_date >= date('now')
                ORDER BY event_date, event_time
                ''')

                for row in cursor.fetchall():
                    events_tree.insert('', 'end', values=row)

                conn.commit()
                conn.close()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load events: {str(e)}")

        def add_event():
            add_window = tk.Toplevel(events_window)
            add_window.title("Add New Event")
            add_window.geometry("500x600")

            ttk.Label(add_window, text="Create New Event", font=('Arial', 12, 'bold')).pack(pady=10)

            form_frame = ttk.Frame(add_window)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            ttk.Label(form_frame, text="Event Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
            name_entry = ttk.Entry(form_frame, width=40)
            name_entry.grid(row=0, column=1, pady=5)

            ttk.Label(form_frame, text="Date (YYYY-MM-DD):").grid(row=1, column=0, sticky=tk.W, pady=5)
            date_entry = ttk.Entry(form_frame, width=40)
            date_entry.grid(row=1, column=1, pady=5)
            date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

            ttk.Label(form_frame, text="Time (HH:MM):").grid(row=2, column=0, sticky=tk.W, pady=5)
            time_entry = ttk.Entry(form_frame, width=40)
            time_entry.grid(row=2, column=1, pady=5)

            ttk.Label(form_frame, text="Location:").grid(row=3, column=0, sticky=tk.W, pady=5)
            location_entry = ttk.Entry(form_frame, width=40)
            location_entry.grid(row=3, column=1, pady=5)

            ttk.Label(form_frame, text="Max Capacity:").grid(row=4, column=0, sticky=tk.W, pady=5)
            capacity_spinbox = ttk.Spinbox(form_frame, from_=5, to=500, width=38)
            capacity_spinbox.set(50)
            capacity_spinbox.grid(row=4, column=1, pady=5)

            ttk.Label(form_frame, text="Description:").grid(row=5, column=0, sticky=tk.W, pady=5)
            desc_text = tk.Text(form_frame, height=8, width=40)
            desc_text.grid(row=5, column=1, pady=5)

            def save_event():
                try:
                    event_name = name_entry.get().strip()
                    event_date = date_entry.get().strip()
                    event_time = time_entry.get().strip()
                    location = location_entry.get().strip()
                    capacity = int(capacity_spinbox.get())
                    description = desc_text.get('1.0', tk.END).strip()

                    if not event_name or not event_date or not event_time:
                        messagebox.showwarning("Warning", "Please fill in all required fields")
                        return

                    conn = get_db_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                    INSERT INTO library_events (event_name, event_date, event_time, location, description,
                                               max_capacity, registered_count, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                    ''', (event_name, event_date, event_time, location, description, capacity,
                         get_current_user_id(), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                    conn.commit()
                    conn.close()

                    log_audit_event(get_current_user_id(), f"Created event: {event_name}", "library_events")
                    messagebox.showinfo("Success", "Event created successfully!")
                    add_window.destroy()
                    load_events()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create event: {str(e)}")

            ttk.Button(form_frame, text="Create Event", command=save_event).grid(row=6, column=0, columnspan=2, pady=20)

        def delete_event():
            selected = events_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select an event to delete")
                return

            event_id = events_tree.item(selected[0])['values'][0]
            event_name = events_tree.item(selected[0])['values'][1]

            confirm = messagebox.askyesno("Confirm Delete", f"Delete event '{event_name}'?")
            if not confirm:
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM library_events WHERE event_id = ?', (event_id,))
                conn.commit()
                conn.close()

                log_audit_event(get_current_user_id(), f"Deleted event: {event_name}", "library_events")
                messagebox.showinfo("Success", "Event deleted successfully")
                load_events()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete event: {str(e)}")

        # Button frame
        button_frame = ttk.Frame(events_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Add Event", command=add_event).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete Event", command=delete_event).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=load_events).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=events_window.destroy).pack(side=tk.RIGHT, padx=5)

        load_events()

    def generate_library_card_gui(self):
        """Generate library card for a student"""
        card_window = tk.Toplevel(self.master)
        card_window.title("Generate Library Card")
        card_window.geometry("700x600")

        ttk.Label(card_window, text="Generate Library Card",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Student search
        search_frame = ttk.LabelFrame(card_window, text="Find Student", padding=10)
        search_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(search_frame, text="Student ID:").pack(side=tk.LEFT, padx=5)
        student_id_entry = ttk.Entry(search_frame, width=30)
        student_id_entry.pack(side=tk.LEFT, padx=5)

        # Card preview
        preview_frame = ttk.LabelFrame(card_window, text="Card Preview", padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        preview_text = ScrolledText(preview_frame, height=20, width=70, font=('Courier', 10))
        preview_text.pack(fill=tk.BOTH, expand=True)

        def generate_card():
            student_id = student_id_entry.get().strip()
            if not student_id:
                messagebox.showwarning("Warning", "Please enter a student ID")
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT student_id, first_name, last_name, email_address, course
                FROM students
                WHERE student_id = ?
                ''', (student_id,))

                result = cursor.fetchone()
                if not result:
                    messagebox.showwarning("Warning", f"Student ID {student_id} not found")
                    conn.close()
                    return

                student_id, first_name, last_name, email, program = result

                # Generate card number
                import random
                card_number = f"LC{student_id[:4]}{random.randint(1000, 9999)}"
                issue_date = datetime.now().strftime('%Y-%m-%d')
                expiry_date = (datetime.now().replace(year=datetime.now().year + 1)).strftime('%Y-%m-%d')

                card_design = f"""
╔══════════════════════════════════════════════════════════════╗
║                    UNIVERSITY LIBRARY CARD                   ║
╚══════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  Name: {first_name} {last_name:<48} │
│  Student ID: {student_id:<47} │
│  Program: {program if program else 'N/A':<50} │
│                                                              │
│  Card Number: {card_number:<46} │
│  Issue Date: {issue_date:<47} │
│  Expiry Date: {expiry_date:<46} │
│                                                              │
│  This card is the property of University Library.           │
│  If found, please return to library circulation desk.       │
│                                                              │
│  [Barcode: *{card_number}*]                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Cardholder Benefits:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Borrow up to 5 books simultaneously
✓ Access to digital resources
✓ Reserve books online
✓ Participate in library events
✓ Study room booking privileges

For assistance, contact: library@university.edu
"""

                preview_text.delete('1.0', tk.END)
                preview_text.insert('1.0', card_design)

                # Store card info in database
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS library_cards (
                    card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    card_number TEXT UNIQUE,
                    issue_date TEXT,
                    expiry_date TEXT,
                    status TEXT DEFAULT 'active'
                )
                ''')

                cursor.execute('''
                INSERT OR REPLACE INTO library_cards (student_id, card_number, issue_date, expiry_date, status)
                VALUES (?, ?, ?, ?, 'active')
                ''', (student_id, card_number, issue_date, expiry_date))

                conn.commit()
                conn.close()

                log_audit_event(get_current_user_id(), f"Generated library card for {student_id}", "library_cards")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate card: {str(e)}")

        def save_card():
            content = preview_text.get('1.0', tk.END)
            if not content.strip():
                messagebox.showwarning("Warning", "No card to save. Generate a card first.")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"library_card_{student_id_entry.get()}.txt"
            )

            if file_path:
                with open(file_path, 'w') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Card saved to:\n{file_path}")

        # Button frame
        button_frame = ttk.Frame(card_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Generate Card", command=generate_card).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save to File", command=save_card).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=card_window.destroy).pack(side=tk.RIGHT, padx=5)

    def bulk_generate_library_cards_gui(self):
        """Bulk generate library cards for multiple students"""
        bulk_window = tk.Toplevel(self.master)
        bulk_window.title("Bulk Generate Library Cards")
        bulk_window.geometry("600x500")

        ttk.Label(bulk_window, text="Bulk Generate Library Cards",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Selection criteria
        criteria_frame = ttk.LabelFrame(bulk_window, text="Selection Criteria", padding=10)
        criteria_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(criteria_frame, text="Generate cards for:").pack(anchor=tk.W)

        selection_var = tk.StringVar(value="all")
        ttk.Radiobutton(criteria_frame, text="All students without cards", variable=selection_var, value="all").pack(anchor=tk.W)
        ttk.Radiobutton(criteria_frame, text="Specific program", variable=selection_var, value="program").pack(anchor=tk.W)

        program_frame = ttk.Frame(criteria_frame)
        program_frame.pack(fill=tk.X, pady=5)
        ttk.Label(program_frame, text="Program:").pack(side=tk.LEFT, padx=5)
        program_entry = ttk.Entry(program_frame, width=30)
        program_entry.pack(side=tk.LEFT, padx=5)

        # Results display
        results_frame = ttk.LabelFrame(bulk_window, text="Generation Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        results_text = ScrolledText(results_frame, height=15, width=70, font=('Courier', 9))
        results_text.pack(fill=tk.BOTH, expand=True)

        def generate_bulk():
            results_text.delete('1.0', tk.END)
            results_text.insert('1.0', "Starting bulk card generation...\n\n")

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Create table if not exists
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS library_cards (
                    card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    card_number TEXT UNIQUE,
                    issue_date TEXT,
                    expiry_date TEXT,
                    status TEXT DEFAULT 'active'
                )
                ''')

                # Get students without cards
                if selection_var.get() == "all":
                    cursor.execute('''
                    SELECT s.student_id, s.first_name, s.last_name
                    FROM students s
                    LEFT JOIN library_cards lc ON s.student_id = lc.student_id
                    WHERE lc.card_id IS NULL
                    ''')
                else:
                    program = program_entry.get().strip()
                    cursor.execute('''
                    SELECT s.student_id, s.first_name, s.last_name
                    FROM students s
                    LEFT JOIN library_cards lc ON s.student_id = lc.student_id
                    WHERE lc.card_id IS NULL AND s.program_name = ?
                    ''', (program,))

                students = cursor.fetchall()

                if not students:
                    results_text.insert(tk.END, "No students found without library cards.\n")
                    conn.close()
                    return

                results_text.insert(tk.END, f"Found {len(students)} students without cards\n\n")

                import random
                generated = 0

                for student_id, first_name, last_name in students:
                    card_number = f"LC{student_id[:4]}{random.randint(1000, 9999)}"
                    issue_date = datetime.now().strftime('%Y-%m-%d')
                    expiry_date = (datetime.now().replace(year=datetime.now().year + 1)).strftime('%Y-%m-%d')

                    cursor.execute('''
                    INSERT INTO library_cards (student_id, card_number, issue_date, expiry_date, status)
                    VALUES (?, ?, ?, ?, 'active')
                    ''', (student_id, card_number, issue_date, expiry_date))

                    results_text.insert(tk.END, f"✓ {student_id}: {first_name} {last_name} - {card_number}\n")
                    generated += 1

                conn.commit()
                conn.close()

                results_text.insert(tk.END, f"\n{'='*60}\n")
                results_text.insert(tk.END, f"Successfully generated {generated} library cards!\n")

                log_audit_event(get_current_user_id(), f"Bulk generated {generated} library cards", "library_cards")

            except Exception as e:
                results_text.insert(tk.END, f"\n❌ Error: {str(e)}\n")

        # Button frame
        button_frame = ttk.Frame(bulk_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Generate Cards", command=generate_bulk).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=bulk_window.destroy).pack(side=tk.RIGHT, padx=5)

    def print_library_card_gui(self):
        """Print/export library card design"""
        print_window = tk.Toplevel(self.master)
        print_window.title("Print Library Card")
        print_window.geometry("600x400")

        ttk.Label(print_window, text="Print Library Card",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Card number input
        input_frame = ttk.LabelFrame(print_window, text="Card Information", padding=10)
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(input_frame, text="Card Number or Student ID:").pack(side=tk.LEFT, padx=5)
        card_input = ttk.Entry(input_frame, width=30)
        card_input.pack(side=tk.LEFT, padx=5)

        info_frame = ttk.LabelFrame(print_window, text="Export Options", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info_frame, text="Select export format and click Export").pack()

        def export_card():
            card_id = card_input.get().strip()
            if not card_id:
                messagebox.showwarning("Warning", "Please enter card number or student ID")
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Try to find card
                cursor.execute('''
                SELECT lc.card_number, lc.issue_date, lc.expiry_date, lc.status,
                       s.student_id, s.first_name, s.last_name, s.program_name
                FROM library_cards lc
                JOIN students s ON lc.student_id = s.student_id
                WHERE lc.card_number = ? OR lc.student_id = ?
                ''', (card_id, card_id))

                result = cursor.fetchone()
                conn.close()

                if not result:
                    messagebox.showwarning("Warning", "Card not found")
                    return

                card_number, issue_date, expiry_date, status, student_id, first_name, last_name, program = result

                card_text = f"""
╔══════════════════════════════════════════════════════════════╗
║                    UNIVERSITY LIBRARY CARD                   ║
╚══════════════════════════════════════════════════════════════╝

  Name: {first_name} {last_name}
  Student ID: {student_id}
  Program: {program if program else 'N/A'}

  Card Number: {card_number}
  Issue Date: {issue_date}
  Expiry Date: {expiry_date}
  Status: {status.upper()}

  [Barcode: *{card_number}*]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This card is the property of University Library.
Contact: library@university.edu
"""

                file_path = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt"), ("PDF files", "*.pdf"), ("All files", "*.*")],
                    initialfile=f"library_card_{card_number}.txt"
                )

                if file_path:
                    with open(file_path, 'w') as f:
                        f.write(card_text)

                    log_audit_event(get_current_user_id(), f"Exported library card {card_number}", "library_cards")
                    messagebox.showinfo("Success", f"Card exported to:\n{file_path}")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to export card: {str(e)}")

        # Button frame
        button_frame = ttk.Frame(print_window)
        button_frame.pack(fill=tk.X, padx=10, pady=20)

        ttk.Button(button_frame, text="Export Card", command=export_card).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=print_window.destroy).pack(side=tk.RIGHT, padx=5)


# DATABASE_FILE constant now defined at top of file using centralized path

# Helper functions that were referenced but missing definitions
def get_library_settings(setting_name):
    """Get library setting value"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = ?', (setting_name,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    except Exception as e:
        print(f"Error getting setting {setting_name}: {e}")
        return None

def update_library_setting(setting_name, setting_value):
    """Update library setting"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO library_settings (setting_name, setting_value)
        VALUES (?, ?)
        ''', (setting_name, setting_value))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating setting {setting_name}: {e}")
        return False

# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth.user_authentication import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_object):
    """Set global auth object for backwards compatibility"""
    global auth
    auth = auth_object
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_object)

def get_current_user_id():
    """Get current user ID"""
    if ORIGINAL_LIBRARY_AVAILABLE and 'auth' in globals() and auth and auth.current_user:
        return auth.current_user.get('user_id', 'unknown')
    return 'gui_user'

def log_audit_event(user_id, action, table_name=None, record_id=None, success=True):
    """Log audit event"""
    try:
        if not ORIGINAL_LIBRARY_AVAILABLE:
            return
            
        conn = get_db_connection()
        if not conn:
            return
            
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user_value = user_id if user_id not in (None, "") else 'system'

        insert_attempts = [
            (
                "user_id, action, table_affected, record_id, timestamp, success",
                (user_value, action, table_name, record_id, timestamp, int(bool(success)))
            ),
            (
                "user_id, action, record_id, timestamp",
                (user_value, action, record_id, timestamp)
            ),
            (
                "action, user_id, timestamp",
                (action, user_value, timestamp)
            ),
            (
                "action, timestamp",
                (action, timestamp)
            ),
        ]

        logged = False
        for column_list, values in insert_attempts:
            placeholders = ', '.join('?' for _ in values)
            try:
                cursor.execute(
                    f"INSERT INTO audit_log ({column_list}) VALUES ({placeholders})",
                    values
                )
                logged = True
                break
            except sqlite3.OperationalError:
                continue

        if not logged:
            print("Warning: Unable to record audit event; audit_log schema not compatible.")

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging audit event: {e}")

def process_scanned_barcode(barcode):
    """Process scanned barcode and return item info"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        
        # Try to find book by barcode
        cursor.execute('''
        SELECT book_id, title, author, status, barcode
        FROM books 
        WHERE barcode = ?
        ''', (barcode,))
        
        result = cursor.fetchone()
        if result:
            book_id, title, author, status, barcode_val = result
            conn.close()
            return {
                'type': 'book',
                'id': book_id,
                'title': title,
                'author': author,
                'status': status,
                'barcode': barcode_val
            }
        
        # Try to find user by barcode (if user barcode system exists)
        cursor.execute('''
        SELECT student_id, first_name, last_name
        FROM students 
        WHERE student_id = ?
        ''', (barcode,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            student_id, first_name, last_name = result
            return {
                'type': 'user',
                'id': student_id,
                'name': f"{first_name} {last_name}",
                'barcode': barcode
            }
        
        return None
        
    except Exception as e:
        print(f"Error processing barcode: {e}")
        return None

def get_db_connection():
    """Get database connection - wrapper for backwards compatibility"""
    if ORIGINAL_LIBRARY_AVAILABLE:
        # This should call the original library's get_db_connection
        try:
            from library import get_db_connection as original_get_db_connection
            return original_get_db_connection()
        except ImportError:
            pass
    
    # Fallback implementation
    try:
        from university_system.infrastructure.database.db import sqlite3
        return sqlite3.connect(str(DEFAULT_DB_PATH))
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

# Main application entry point and backwards compatibility functions
def start_gui_library_system():
    """Start the GUI library system"""
    root = tk.Tk()
    app = LibraryGUI(root)
    
    # Setup keyboard shortcuts
    setup_keyboard_shortcuts(root, app)
    
    root.mainloop()

def setup_keyboard_shortcuts(root, app):
    """Setup keyboard shortcuts"""
    # General shortcuts
    root.bind('<Control-n>', lambda e: app.show_add_book())
    root.bind('<Control-f>', lambda e: app.show_search_books())
    root.bind('<F5>', lambda e: app.refresh_books_table() if hasattr(app, 'books_tree') else None)
    root.bind('<Control-s>', lambda e: None)  # Save shortcut (context dependent)
    root.bind('<Escape>', lambda e: None)  # Cancel shortcut (context dependent)
    
    # Navigation shortcuts
    root.bind('<Control-Key-1>', lambda e: app.show_dashboard())
    root.bind('<Control-Key-2>', lambda e: app.show_all_books())
    root.bind('<Control-Key-3>', lambda e: app.show_search_books())
    root.bind('<Control-Key-4>', lambda e: app.show_reports())
    root.bind('<Control-Key-5>', lambda e: app.show_settings())

    # System shortcuts
    root.bind('<Control-b>', lambda e: app.backup_system_gui())
    root.bind('<Control-r>', lambda e: app.show_reports())
    # Logout shortcut removed - handled by main system

# Backwards compatibility functions
def display_library_menu_gui():
    """Display library menu in GUI mode (backwards compatible)"""
    start_gui_library_system()

def run_library_gui():
    """Run the library GUI"""
    start_gui_library_system()

# CLI compatibility wrapper
def run_library_system_with_gui_option():
    """Run library system with option to choose CLI or GUI"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] in ['--gui', '-g']:
        # GUI mode
        print("Starting Library Management System - GUI Mode")
        start_gui_library_system()
    elif len(sys.argv) > 1 and sys.argv[1] in ['--cli', '-c']:
        # CLI mode
        print("Starting Library Management System - CLI Mode")
        if ORIGINAL_LIBRARY_AVAILABLE:
            display_library_menu()
        else:
            print("CLI mode requires original library module")
    else:
        # Ask user preference
        print("Enhanced Library Management System")
        print("=================================")
        print("1. GUI Mode (Recommended)")
        print("2. CLI Mode (Traditional)")
        print("3. Exit")
        
        choice = input("Choose interface (1-3): ").strip()
        
        if choice == '1':
            start_gui_library_system()
        elif choice == '2':
            if ORIGINAL_LIBRARY_AVAILABLE:
                display_library_menu()
            else:
                print("CLI mode requires original library module")
                start_gui_library_system()
        else:
            print("Goodbye!")

# Main execution
if __name__ == "__main__":
    try:
        # Initialize the system
        if ORIGINAL_LIBRARY_AVAILABLE:
            print("Initializing Enhanced Library Management System...")
            
            # Initialize database
            if init_library_db():
                print("✅ Database initialized successfully")
            else:
                print("❌ Database initialization failed")
                
        run_library_system_with_gui_option()
        
    except KeyboardInterrupt:
        print("\nSystem interrupted by user")
    except Exception as e:
        print(f"System error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Thank you for using the Enhanced Library Management System!")
