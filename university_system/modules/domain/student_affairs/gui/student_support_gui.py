import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import tkinter.font as tkFont
from datetime import datetime, timedelta
import json
import os
import threading
import webbrowser
from typing import Dict, List, Optional, Any
from university_system.infrastructure.database.db import sqlite3
from pathlib import Path
import logging
from university_system.modules.shared.constants import paths

# Import activity logger for audit trail
try:
    from university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

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
    from university_system.modules.domain.student_affairs.services.student_support import (
        # Core constants and enums
        SUPPORT_CATEGORIES, TICKET_PRIORITIES, TICKET_STATUSES,
        NotificationType, TicketSentiment, FileType,
        # Main classes
        EnhancedStudentSupport, SupportConfig,
        # Utility functions
        setup_enhanced_logging, audit_action,
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
        from university_system.modules.domain.student_affairs.services.student_support import (
            SUPPORT_CATEGORIES, TICKET_PRIORITIES, TICKET_STATUSES,
            EnhancedStudentSupport, SupportConfig, display_support_menu
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
    validate_ticket_permissions = lambda *args, **kwargs: True
    format_ticket_status_display = lambda x: str(x)
    format_priority_display = lambda x: str(x)
    format_file_size = lambda x: f"{x} bytes"
    truncate_text = lambda x, length=100: x[:length] if len(x) > length else x
    handle_support_error = lambda *args, **kwargs: None

class StudentSupportGUI:
    def __init__(self, root, auth_system=None):
        self.root = root
        self.root.title("🎓 Enhanced Student Support Portal")
        self.root.geometry("1800x1050")
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
        from university_system.infrastructure.shared_context import get_auth
        auth = get_auth()
        if not auth.is_logged_in():
            messagebox.showerror("Authentication Required",
                "Please log in through the main University System GUI.\n\n"
                "Run: python run.py --gui")
            self.root.destroy()
            return

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
            text="🏠 Return to Homescreen",
            command=self.return_to_main_menu
        )
        return_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        # Main container with padding
        self.main_frame = ttk.Frame(self.root, padding="10")
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
        sidebar_container.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
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
        self.create_nav_button("📊 Dashboard", self.show_dashboard)
        
        # Common features
        self.create_nav_button("🔍 Search", self.show_search)
        self.create_nav_button("❓ FAQs", self.show_faqs)
        self.create_nav_button("📚 Knowledge Base", self.show_knowledge_base)
        self.create_nav_button("📋 Resources", self.show_resources)
        
        # Role-based features
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            user_role = getattr(self.auth.current_user, 'role', 'user') if hasattr(self.auth.current_user, 'role') else self.auth.current_user.get('role', 'user')
            
            if user_role == 'student':
                ttk.Separator(self.nav_frame, orient='horizontal').pack(fill="x", pady=10)
                self.create_nav_button("Create Ticket", self.show_create_ticket)
                self.create_nav_button("My Tickets", self.show_my_tickets)
                self.create_nav_button("Templates", self.show_ticket_templates)
                self.create_nav_button("Submit Rating", self.show_satisfaction_rating)  # NEW
                
            elif user_role in ('staff', 'admin'):
                ttk.Separator(self.nav_frame, orient='horizontal').pack(fill="x", pady=10)
                self.create_nav_button("All Tickets", self.show_all_tickets)
                self.create_nav_button("Reports", self.show_reports)
                self.create_nav_button("Manage Templates", self.show_manage_templates)
                self.create_nav_button("Manage KB", self.show_manage_kb)
                self.create_nav_button("Bulk Operations", self.show_bulk_operations)
                self.create_nav_button("Export Data", self.show_export_data_dialog)  # NEW
                self.create_nav_button("User Management", self.show_user_management)         
        # Settings
        ttk.Separator(self.nav_frame, orient='horizontal').pack(fill="x", pady=10)
        self.create_nav_button("⚙️ Preferences", self.show_preferences)
        self.create_nav_button("🔔 Notifications", self.show_notifications)
        
        # Refresh button
        refresh_frame = ttk.Frame(self.sidebar, padding="10")
        refresh_frame.pack(side="bottom", fill="x")
        ttk.Button(refresh_frame, text="🔄 Refresh", command=self.refresh_data).pack(fill="x")
        ttk.Button(refresh_frame, text="🏠 Return to Homescreen", command=self.return_to_main_menu).pack(fill="x", pady=(8, 0))

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

        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(0, weight=1)

        # Create notebook for multiple views within the scrollable content
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Initialize with dashboard
        self.show_dashboard()

    def create_status_bar(self):
        """Create status bar"""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))
        
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        
        ttk.Label(self.status_frame, textvariable=self.status_var).pack(side="left")
        
        # System status indicator
        self.system_status = ttk.Label(self.status_frame, text="🟢 Online")
        self.system_status.pack(side="right")

    def create_menu(self):
        """Create application menu"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Ticket", command=self.show_create_ticket)
        file_menu.add_separator()
        file_menu.add_command(label="Export Data", command=self.show_export_dialog)
        file_menu.add_separator()
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Dashboard", command=self.show_dashboard)
        view_menu.add_command(label="All Tickets", command=self.show_all_tickets)
        view_menu.add_command(label="Search", command=self.show_search)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Preferences", command=self.show_preferences)
        tools_menu.add_command(label="Refresh Data", command=self.refresh_data)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_help)
        help_menu.add_command(label="About", command=self.show_about)
    
    def clear_content(self):
        """Clear all notebook tabs"""
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)
    

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            root_widget = self.root if hasattr(self, 'root') else self.master
            if isinstance(root_widget, tk.Toplevel):
                # Just close the child window
                root_widget.destroy()
            else:
                # Running standalone, need to create main GUI
                root_widget.destroy()
                from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def load_dashboard(self):
        """Load dashboard data"""
        if not self.support:
            return

        if not self.auth or not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            return

        try:
            # Get user ID (try 'id' first, fallback to 'user_id', then default to None)
            user_id = self.auth.current_user.get('id') or self.auth.current_user.get('user_id')
            user_role = self.auth.current_user.get('role', 'student')

            self.dashboard_data = self.support.get_dashboard_data(
                user_role,
                user_id
            )
            self.update_status("Dashboard loaded")
        except Exception as e:
            self.update_status(f"Error loading dashboard: {e}")
            self.dashboard_data = {}
            print(f"Dashboard error: {e}")
            import traceback
            traceback.print_exc()
    
    def show_dashboard(self):
        """Display dashboard"""
        self.clear_content()
        
        dashboard_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(dashboard_frame, text="📊 Dashboard")
        
        # Create scrollable area
        canvas = tk.Canvas(dashboard_frame, bg=self.colors['background'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(dashboard_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        scroll_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(scroll_window, width=e.width)
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Dashboard content - authentication already checked in __init__
        if not self.auth or not self.auth.current_user:
            return
        
        # Load fresh data
        self.load_dashboard()
        
        # Title
        title_frame = ttk.Frame(scrollable_frame, padding="10")
        title_frame.pack(fill="x")
        
        ttk.Label(title_frame, text="📊 Support Portal Dashboard", 
                 style='Title.TLabel').pack(side="left")
        
        # Welcome message
        welcome_text = f"Welcome back, {self.auth.current_user['username']}!"
        ttk.Label(title_frame, text=welcome_text, 
                 font=('Segoe UI', 12)).pack(side="right")
        
        # Create dashboard widgets based on role
        if self.auth.current_user['role'] == 'student':
            self.create_student_dashboard(scrollable_frame)
        else:
            self.create_staff_dashboard(scrollable_frame)
        
        # Common widgets
        self.create_notifications_widget(scrollable_frame)
        self.create_quick_actions_widget(scrollable_frame)
    
    def create_student_dashboard(self, parent):
        """Create student-specific dashboard widgets"""
        # Ticket statistics
        stats_frame = ttk.LabelFrame(parent, text="📊 Your Tickets", padding="10")
        stats_frame.pack(fill="x", padx=10, pady=5)
        
        stats = self.dashboard_data.get('ticket_stats', {})
        
        stats_text = f"Open: {stats.get('Open', 0)} | "
        stats_text += f"In Progress: {stats.get('In Progress', 0)} | "
        stats_text += f"Resolved: {stats.get('Resolved', 0)}"
        
        ttk.Label(stats_frame, text=stats_text, font=('Segoe UI', 11)).pack()
        
        # Recent tickets
        recent_frame = ttk.LabelFrame(parent, text="📋 Recent Tickets", padding="10")
        recent_frame.pack(fill="x", padx=10, pady=5)
        
        recent_tickets = self.dashboard_data.get('recent_tickets', [])
        if recent_tickets:
            for ticket in recent_tickets[:3]:
                ticket_frame = ttk.Frame(recent_frame)
                ticket_frame.pack(fill="x", pady=2)
                
                status_emoji = {'Open': '🟢', 'In Progress': '⏳', 'Resolved': '✅', 'Closed': '🔒'}.get(ticket['status'], '❓')
                ticket_text = f"{status_emoji} #{ticket['ticket_id']} - {ticket['title'][:50]}..."
                
                ttk.Label(ticket_frame, text=ticket_text).pack(side="left")
                ttk.Button(ticket_frame, text="View", 
                          command=lambda t=ticket['ticket_id']: self.view_ticket_details(t)).pack(side="right")
        else:
            ttk.Label(recent_frame, text="No recent tickets").pack()
        
        # Featured resources
        resources_frame = ttk.LabelFrame(parent, text="⭐ Featured Resources", padding="10")
        resources_frame.pack(fill="x", padx=10, pady=5)
        
        featured_resources = self.dashboard_data.get('featured_resources', [])
        if featured_resources:
            for resource in featured_resources[:3]:
                resource_frame = ttk.Frame(resources_frame)
                resource_frame.pack(fill="x", pady=2)
                
                ttk.Label(resource_frame, text=f"📄 {resource['title']}").pack(side="left")
                ttk.Button(resource_frame, text="Open", 
                          command=lambda r=resource: self.open_resource(r)).pack(side="right")
        else:
            ttk.Label(resources_frame, text="No featured resources available").pack()
    
    def create_staff_dashboard(self, parent):
        """Create staff-specific dashboard widgets"""
        # Performance metrics
        metrics_frame = ttk.LabelFrame(parent, text="📈 Performance Metrics", padding="10")
        metrics_frame.pack(fill="x", padx=10, pady=5)
        
        metrics = self.dashboard_data.get('performance_metrics', {})
        
        metrics_text = f"Monthly Tickets: {metrics.get('total_tickets_month', 0)} | "
        metrics_text += f"Avg Resolution: {metrics.get('avg_resolution_time', 0)} days | "
        metrics_text += f"Resolution Rate: {metrics.get('resolution_rate', 0)}%"
        
        ttk.Label(metrics_frame, text=metrics_text, font=('Segoe UI', 11)).pack()
        
        # Assigned tickets
        assigned_frame = ttk.LabelFrame(parent, text="👨‍💼 Assigned Tickets", padding="10")
        assigned_frame.pack(fill="x", padx=10, pady=5)
        
        assigned_stats = self.dashboard_data.get('assigned_stats', {})
        assigned_text = f"Open: {assigned_stats.get('Open', 0)} | "
        assigned_text += f"In Progress: {assigned_stats.get('In Progress', 0)}"
        
        ttk.Label(assigned_frame, text=assigned_text, font=('Segoe UI', 11)).pack()
        
        # High priority tickets
        priority_frame = ttk.LabelFrame(parent, text="🚨 Priority Tickets", padding="10")
        priority_frame.pack(fill="x", padx=10, pady=5)
        
        priority_tickets = self.dashboard_data.get('priority_tickets', [])
        if priority_tickets:
            for ticket in priority_tickets[:5]:
                ticket_frame = ttk.Frame(priority_frame)
                ticket_frame.pack(fill="x", pady=2)
                
                priority_emoji = {'Critical': '🔴', 'Urgent': '🟠', 'High': '🟡'}.get(ticket['priority'], '⚪')
                ticket_text = f"{priority_emoji} #{ticket['ticket_id']} - {ticket['title'][:40]}..."
                
                ttk.Label(ticket_frame, text=ticket_text).pack(side="left")
                ttk.Button(ticket_frame, text="Assign to Me", 
                          command=lambda t=ticket['ticket_id']: self.assign_ticket_to_me(t)).pack(side="right")
        else:
            ttk.Label(priority_frame, text="No high priority tickets").pack()
    
    def create_notifications_widget(self, parent):
        """Create notifications widget"""
        notifications_frame = ttk.LabelFrame(parent, text="🔔 Recent Notifications", padding="10")
        notifications_frame.pack(fill="x", padx=10, pady=5)
        
        notifications = self.dashboard_data.get('notifications', [])
        if notifications:
            for notif in notifications[:3]:
                notif_frame = ttk.Frame(notifications_frame)
                notif_frame.pack(fill="x", pady=2)
                
                status_icon = "📫" if notif['is_read'] else "📬"
                notif_text = f"{status_icon} {notif['title']}"
                
                ttk.Label(notif_frame, text=notif_text).pack(side="left")
                ttk.Label(notif_frame, text=notif['created'], 
                         font=('Segoe UI', 9), foreground=self.colors['text_secondary']).pack(side="right")
        else:
            ttk.Label(notifications_frame, text="No recent notifications").pack()
    
    def create_quick_actions_widget(self, parent):
        """Create quick actions widget"""
        actions_frame = ttk.LabelFrame(parent, text="⚡ Quick Actions", padding="10")
        actions_frame.pack(fill="x", padx=10, pady=5)
        
        # Create grid of action buttons
        actions_grid = ttk.Frame(actions_frame)
        actions_grid.pack(fill="x")
        
        if self.auth.current_user['role'] == 'student':
            actions = [
                ("🎫 Create Ticket", self.show_create_ticket),
                ("📋 My Tickets", self.show_my_tickets),
                ("🔍 Search", self.show_search),
                ("❓ Browse FAQs", self.show_faqs)
            ]
        else:
            actions = [
                ("🎫 View All Tickets", self.show_all_tickets),
                ("📊 Generate Report", self.show_reports),
                ("🔧 Manage Templates", self.show_manage_templates),
                ("📦 Bulk Operations", self.show_bulk_operations)
            ]
        
        for i, (text, command) in enumerate(actions):
            row, col = i // 2, i % 2
            ttk.Button(actions_grid, text=text, command=command).grid(
                row=row, column=col, padx=5, pady=5, sticky="ew")
        
        actions_grid.columnconfigure(0, weight=1)
        actions_grid.columnconfigure(1, weight=1)
    
    def show_search(self):
        """Show advanced search interface"""
        self.clear_content()
        
        search_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(search_frame, text="🔍 Advanced Search")
        
        # Search form
        form_frame = ttk.LabelFrame(search_frame, text="Search Parameters", padding="10")
        form_frame.pack(fill="x", pady=(0, 10))
        
        # Search query
        ttk.Label(form_frame, text="Search Query:").grid(row=0, column=0, sticky="w", pady=5)
        self.search_query = ttk.Entry(form_frame, width=50)
        self.search_query.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=5)
        self.search_query.bind('<Return>', lambda e: self.perform_search())
        
        # Search type
        ttk.Label(form_frame, text="Search In:").grid(row=1, column=0, sticky="w", pady=5)
        self.search_type = ttk.Combobox(form_frame, values=[
            "Everything", "Tickets", "FAQs", "Resources", "Knowledge Base"
        ], state="readonly")
        self.search_type.set("Everything")
        self.search_type.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=5)
        
        # Search button
        search_btn_frame = ttk.Frame(form_frame)
        search_btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Button(search_btn_frame, text="🔍 Search", 
                  command=self.perform_search, style='Primary.TButton').pack()
        
        form_frame.columnconfigure(1, weight=1)
        
        # Results area
        self.search_results_frame = ttk.LabelFrame(search_frame, text="Search Results", padding="10")
        self.search_results_frame.pack(fill="both", expand=True)
        
        # Results notebook
        self.results_notebook = ttk.Notebook(self.search_results_frame)
        self.results_notebook.pack(fill="both", expand=True)
    
    def perform_search(self):
        """Perform advanced search"""
        query = self.search_query.get().strip()
        if not query:
            messagebox.showwarning("Search", "Please enter a search query")
            return
        
        if not self.support:
            messagebox.showerror("Error", "Support system not initialized")
            return
        
        # Clear previous results
        for tab in self.results_notebook.tabs():
            self.results_notebook.forget(tab)
        
        search_type_map = {
            "Everything": "global",
            "Tickets": "tickets", 
            "FAQs": "faqs",
            "Resources": "resources",
            "Knowledge Base": "kb"
        }
        
        search_type = search_type_map.get(self.search_type.get(), "global")
        
        try:
            self.update_status(f"Searching for '{query}'...")
            results = self.support.advanced_search(query, search_type)
            self.display_search_results(results)
            self.update_status(f"Search completed for '{query}'")
        except Exception as e:
            messagebox.showerror("Search Error", f"Search failed: {e}")
            self.update_status("Search failed")
    
    def display_search_results(self, results):
        """Display search results in tabs"""
        total_results = 0
        
        # Tickets results
        if 'tickets' in results:
            tickets = results['tickets'].get('tickets', [])
            if tickets:
                self.create_tickets_results_tab(tickets)
                total_results += len(tickets)
        
        # FAQs results
        if 'faqs' in results:
            faqs = results['faqs']
            if faqs:
                self.create_faqs_results_tab(faqs)
                total_results += len(faqs)
        
        # Resources results
        if 'resources' in results:
            resources = results['resources']
            if resources:
                self.create_resources_results_tab(resources)
                total_results += len(resources)
        
        # Knowledge base results
        if 'kb_articles' in results:
            articles = results['kb_articles']
            if articles:
                self.create_kb_results_tab(articles)
                total_results += len(articles)
        
        # Suggestions
        if 'suggestions' in results and results['suggestions']:
            self.create_suggestions_tab(results['suggestions'])
        
        if total_results == 0:
            # No results found
            no_results_frame = ttk.Frame(self.results_notebook, padding="20")
            self.results_notebook.add(no_results_frame, text="No Results")
            
            ttk.Label(no_results_frame, text="🔍 No results found", 
                     style='Title.TLabel').pack(pady=20)
            ttk.Label(no_results_frame, text="Try different keywords or check spelling").pack()
        
        self.search_results_frame.config(text=f"Search Results ({total_results} found)")
    
    def create_tickets_results_tab(self, tickets):
        """Create tickets results tab"""
        tickets_frame = ttk.Frame(self.results_notebook, padding="10")
        self.results_notebook.add(tickets_frame, text=f"🎫 Tickets ({len(tickets)})")
        
        # Create treeview for tickets
        columns = ('ID', 'Title', 'Status', 'Priority', 'Category', 'Created')
        tree = ttk.Treeview(tickets_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        tree.heading('ID', text='ID')
        tree.heading('Title', text='Title')
        tree.heading('Status', text='Status')
        tree.heading('Priority', text='Priority')
        tree.heading('Category', text='Category')
        tree.heading('Created', text='Created')
        
        tree.column('ID', width=80)
        tree.column('Title', width=300)
        tree.column('Status', width=100)
        tree.column('Priority', width=100)
        tree.column('Category', width=120)
        tree.column('Created', width=150)
        
        # Add tickets to tree
        for ticket in tickets:
            tree.insert('', 'end', values=(
                ticket['ticket_id'],
                ticket['title'][:50] + ('...' if len(ticket['title']) > 50 else ''),
                ticket['status'],
                ticket['priority'],
                ticket['category'],
                ticket['created_datetime']
            ))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tickets_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Double-click to view ticket
        tree.bind('<Double-1>', lambda e: self.on_ticket_double_click(tree))
    
    def create_faqs_results_tab(self, faqs):
        """Create FAQs results tab"""
        faqs_frame = ttk.Frame(self.results_notebook, padding="10")
        self.results_notebook.add(faqs_frame, text=f"❓ FAQs ({len(faqs)})")
        
        # Create scrollable list
        canvas = tk.Canvas(faqs_frame)
        scrollbar = ttk.Scrollbar(faqs_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add FAQs
        for faq in faqs:
            faq_frame = ttk.LabelFrame(scrollable_frame, text=f"Q: {faq['question']}", padding="10")
            faq_frame.pack(fill="x", padx=5, pady=5)
            
            # FAQ details
            details_text = f"Category: {faq['category']} | Views: {faq.get('view_count', 0)} | Helpful: {faq.get('helpful_votes', 0)}"
            ttk.Label(faq_frame, text=details_text, font=('Segoe UI', 9), 
                     foreground=self.colors['text_secondary']).pack(anchor="w")
            
            # Answer preview
            answer_preview = faq['answer'][:200] + ('...' if len(faq['answer']) > 200 else '')
            ttk.Label(faq_frame, text=answer_preview, wraplength=600).pack(anchor="w", pady=(5, 0))
            
            # View full answer button
            ttk.Button(faq_frame, text="View Full Answer", 
                      command=lambda f=faq: self.show_faq_detail(f)).pack(anchor="w", pady=(5, 0))
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_resources_results_tab(self, resources):
        """Create resources results tab"""
        resources_frame = ttk.Frame(self.results_notebook, padding="10")
        self.results_notebook.add(resources_frame, text=f"📋 Resources ({len(resources)})")
        
        # Create scrollable list
        canvas = tk.Canvas(resources_frame)
        scrollbar = ttk.Scrollbar(resources_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add resources
        for resource in resources:
            resource_frame = ttk.LabelFrame(scrollable_frame, text=f"📄 {resource['title']}", padding="10")
            resource_frame.pack(fill="x", padx=5, pady=5)
            
            # Resource details
            details_text = f"Category: {resource['category']} | Accesses: {resource.get('access_count', 0)}"
            ttk.Label(resource_frame, text=details_text, font=('Segoe UI', 9),
                     foreground=self.colors['text_secondary']).pack(anchor="w")
            
            # Description
            ttk.Label(resource_frame, text=resource['description'], wraplength=600).pack(anchor="w", pady=(5, 0))
            
            # Action buttons
            btn_frame = ttk.Frame(resource_frame)
            btn_frame.pack(anchor="w", pady=(5, 0))
            
            if resource.get('url'):
                ttk.Button(btn_frame, text="Open URL", 
                          command=lambda r=resource: self.open_url(r['url'])).pack(side="left", padx=(0, 5))
            
            if resource.get('file_path'):
                ttk.Button(btn_frame, text="Open File", 
                          command=lambda r=resource: self.open_file(r['file_path'])).pack(side="left")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_kb_results_tab(self, articles):
        """Create knowledge base results tab"""
        kb_frame = ttk.Frame(self.results_notebook, padding="10")
        self.results_notebook.add(kb_frame, text=f"📚 Knowledge Base ({len(articles)})")
        
        # Create scrollable list
        canvas = tk.Canvas(kb_frame)
        scrollbar = ttk.Scrollbar(kb_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add articles
        for article in articles:
            article_frame = ttk.LabelFrame(scrollable_frame, text=f"📖 {article['title']}", padding="10")
            article_frame.pack(fill="x", padx=5, pady=5)
            
            # Article details
            details_text = f"Category: {article['category']} | Views: {article.get('view_count', 0)} | Helpful: {article.get('helpful_votes', 0)}"
            ttk.Label(article_frame, text=details_text, font=('Segoe UI', 9),
                     foreground=self.colors['text_secondary']).pack(anchor="w")
            
            # Summary or content preview
            if article.get('summary'):
                ttk.Label(article_frame, text=article['summary'], wraplength=600).pack(anchor="w", pady=(5, 0))
            else:
                content_preview = article['content'][:200] + ('...' if len(article['content']) > 200 else '')
                ttk.Label(article_frame, text=content_preview, wraplength=600).pack(anchor="w", pady=(5, 0))
            
            # View full article button
            ttk.Button(article_frame, text="View Full Article", 
                      command=lambda a=article: self.show_article_detail(a)).pack(anchor="w", pady=(5, 0))
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_suggestions_tab(self, suggestions):
        """Create suggestions tab"""
        suggestions_frame = ttk.Frame(self.results_notebook, padding="10")
        self.results_notebook.add(suggestions_frame, text="💡 Suggestions")
        
        ttk.Label(suggestions_frame, text="💡 Search Suggestions", 
                 style='Heading.TLabel').pack(anchor="w", pady=(0, 10))
        
        for suggestion in suggestions:
            suggestion_frame = ttk.Frame(suggestions_frame)
            suggestion_frame.pack(fill="x", pady=2)
            
            ttk.Label(suggestion_frame, text=f"💭 {suggestion}").pack(side="left")
            ttk.Button(suggestion_frame, text="Search", 
                      command=lambda s=suggestion: self.search_suggestion(s)).pack(side="right")
    
    def show_create_ticket(self):
        """Show create ticket interface"""
        self.clear_content()
        
        create_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(create_frame, text="🎫 Create Ticket")
        
        # Check authentication
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] != 'student':
            ttk.Label(create_frame, text="❌ Only students can create tickets", 
                     style='Title.TLabel').pack(pady=20)
            return
        
        # Create scrollable form
        canvas = tk.Canvas(create_frame)
        scrollbar = ttk.Scrollbar(create_frame, orient="vertical", command=canvas.yview)
        form_frame = ttk.Frame(canvas)
        
        form_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=form_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Title
        ttk.Label(form_frame, text="🎫 Create Support Ticket", 
                 style='Title.TLabel').pack(pady=(0, 20))
        
        # Template selection
        template_frame = ttk.LabelFrame(form_frame, text="📋 Templates (Optional)", padding="10")
        template_frame.pack(fill="x", pady=(0, 10))
        
        self.selected_template = tk.StringVar()
        self.template_combo = ttk.Combobox(template_frame, textvariable=self.selected_template, 
                                          state="readonly", width=50)
        
        # Load templates
        try:
            templates = self.support.get_ticket_templates() if self.support else []
            template_values = ["Create from scratch"] + [f"{t['name']} ({t['category']})" for t in templates]
            self.template_combo['values'] = template_values
            self.template_combo.set("Create from scratch")
            self.template_data = {"Create from scratch": None}
            for t in templates:
                self.template_data[f"{t['name']} ({t['category']})"] = t
        except Exception as e:
            self.template_combo['values'] = ["Create from scratch"]
            self.template_combo.set("Create from scratch")
            self.template_data = {"Create from scratch": None}
        
        self.template_combo.pack(fill="x")
        self.template_combo.bind('<<ComboboxSelected>>', self.on_template_selected)
        
        # Title field
        title_frame = ttk.LabelFrame(form_frame, text="📝 Title *", padding="10")
        title_frame.pack(fill="x", pady=(0, 10))
        
        self.title_entry = ttk.Entry(title_frame, width=80)
        self.title_entry.pack(fill="x")
        
        # Category field
        category_frame = ttk.LabelFrame(form_frame, text="📂 Category *", padding="10")
        category_frame.pack(fill="x", pady=(0, 10))
        
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(category_frame, textvariable=self.category_var, 
                                          values=SUPPORT_CATEGORIES, state="readonly")
        self.category_combo.set("Other")
        self.category_combo.pack(fill="x")
        
        # Priority field
        priority_frame = ttk.LabelFrame(form_frame, text="🔥 Priority", padding="10")
        priority_frame.pack(fill="x", pady=(0, 10))
        
        self.priority_var = tk.StringVar()
        self.priority_combo = ttk.Combobox(priority_frame, textvariable=self.priority_var,
                                          values=TICKET_PRIORITIES, state="readonly")
        self.priority_combo.set("Medium")
        self.priority_combo.pack(fill="x")
        
        # Description field
        desc_frame = ttk.LabelFrame(form_frame, text="📄 Description *", padding="10")
        desc_frame.pack(fill="x", pady=(0, 10))
        
        self.description_text = scrolledtext.ScrolledText(desc_frame, height=8, wrap=tk.WORD)
        self.description_text.pack(fill="both", expand=True)
        
        # Tags field
        tags_frame = ttk.LabelFrame(form_frame, text="🏷️ Tags (comma-separated)", padding="10")
        tags_frame.pack(fill="x", pady=(0, 10))
        
        self.tags_entry = ttk.Entry(tags_frame, width=80)
        self.tags_entry.pack(fill="x")
        
        # Attachments
        attachments_frame = ttk.LabelFrame(form_frame, text="📎 Attachments", padding="10")
        attachments_frame.pack(fill="x", pady=(0, 10))
        
        self.attachments = []
        self.attachments_listbox = tk.Listbox(attachments_frame, height=3)
        self.attachments_listbox.pack(fill="x", pady=(0, 5))
        
        attach_btn_frame = ttk.Frame(attachments_frame)
        attach_btn_frame.pack(fill="x")
        
        ttk.Button(attach_btn_frame, text="➕ Add File", 
                  command=self.add_attachment).pack(side="left", padx=(0, 5))
        ttk.Button(attach_btn_frame, text="➖ Remove", 
                  command=self.remove_attachment).pack(side="left")
        
        # Buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(fill="x", pady=20)
        
        ttk.Button(button_frame, text="🎫 Create Ticket", 
                  command=self.create_ticket, style='Primary.TButton').pack(side="left", padx=(0, 10))
        ttk.Button(button_frame, text="🔄 Reset Form", 
                  command=self.reset_create_form).pack(side="left", padx=(0, 10))
        ttk.Button(button_frame, text="❌ Cancel", 
                  command=self.show_dashboard).pack(side="left")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def on_template_selected(self, event=None):
        """Handle template selection"""
        template_name = self.selected_template.get()
        template = self.template_data.get(template_name)
        
        if template:
            # Fill form with template data
            self.title_entry.delete(0, tk.END)
            self.title_entry.insert(0, template['title_template'])
            
            self.category_var.set(template['category'])
            self.priority_var.set(template['priority'])
            
            self.description_text.delete(1.0, tk.END)
            self.description_text.insert(1.0, template['description_template'])
    
    def add_attachment(self):
        """Add file attachment"""
        file_path = filedialog.askopenfilename(
            title="Select File to Attach",
            filetypes=[("All Files", "*.*")]
        )
        
        if file_path:
            # Check file size (10MB limit)
            file_size = os.path.getsize(file_path)
            if file_size > 10 * 1024 * 1024:
                messagebox.showerror("File Too Large", "File size must be less than 10MB")
                return
            
            # Read file data
            try:
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                
                attachment = {
                    'filename': os.path.basename(file_path),
                    'data': file_data,
                    'mime_type': 'application/octet-stream'  # Default MIME type
                }
                
                self.attachments.append(attachment)
                self.attachments_listbox.insert(tk.END, attachment['filename'])
                
            except Exception as e:
                messagebox.showerror("File Error", f"Could not read file: {e}")
    
    def remove_attachment(self):
        """Remove selected attachment"""
        selection = self.attachments_listbox.curselection()
        if selection:
            index = selection[0]
            self.attachments.pop(index)
            self.attachments_listbox.delete(index)
    
    def create_ticket(self):
        """Create the support ticket"""
        # Validate form
        title = self.title_entry.get().strip()
        if not title:
            messagebox.showerror("Validation Error", "Title is required")
            return
        
        description = self.description_text.get(1.0, tk.END).strip()
        if not description:
            messagebox.showerror("Validation Error", "Description is required")
            return
        
        category = self.category_var.get()
        priority = self.priority_var.get()
        
        # Parse tags
        tags_text = self.tags_entry.get().strip()
        tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()] if tags_text else []
        
        # Get student ID
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                messagebox.showerror("Error", "No student ID associated with your account")
                return
            
            student_id = result[0]
            
        except Exception as e:
            messagebox.showerror("Database Error", f"Could not get student ID: {e}")
            return
        
        # Create ticket
        try:
            self.update_status("Creating ticket...")
            
            # Get template ID if template was used
            template_id = None
            template_name = self.selected_template.get()
            if template_name != "Create from scratch":
                template = self.template_data.get(template_name)
                template_id = template['template_id'] if template else None
            
            ticket_id = self.support.create_support_ticket(
                student_id=student_id,
                title=title,
                description=description,
                category=category,
                priority=priority,
                template_id=template_id,
                attachments=self.attachments,
                tags=tags
            )
            
            messagebox.showinfo("Success", f"Support ticket #{ticket_id} created successfully!")
            self.update_status(f"Ticket #{ticket_id} created")
            
            # Reset form and show ticket details
            self.reset_create_form()
            self.view_ticket_details(ticket_id)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create ticket: {e}")
            self.update_status("Ticket creation failed")
    
    def reset_create_form(self):
        """Reset the create ticket form"""
        self.title_entry.delete(0, tk.END)
        self.description_text.delete(1.0, tk.END)
        self.tags_entry.delete(0, tk.END)
        self.category_var.set("Other")
        self.priority_var.set("Medium")
        self.selected_template.set("Create from scratch")
        self.attachments.clear()
        self.attachments_listbox.delete(0, tk.END)
    
    def show_my_tickets(self):
        """Show student's tickets"""
        self.clear_content()
        
        tickets_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tickets_frame, text="📋 My Tickets")
        
        # Check authentication
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] != 'student':
            ttk.Label(tickets_frame, text="❌ Access denied", 
                     style='Title.TLabel').pack(pady=20)
            return
        
        # Title and filters
        header_frame = ttk.Frame(tickets_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(header_frame, text="📋 My Support Tickets", 
                 style='Title.TLabel').pack(side="left")
        
        ttk.Button(header_frame, text="🔄 Refresh", 
                  command=self.refresh_my_tickets).pack(side="right")
        
        # Filters
        filter_frame = ttk.LabelFrame(tickets_frame, text="🔍 Filters", padding="10")
        filter_frame.pack(fill="x", pady=(0, 10))
        
        filter_grid = ttk.Frame(filter_frame)
        filter_grid.pack(fill="x")
        
        # Status filter
        ttk.Label(filter_grid, text="Status:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.my_tickets_status_filter = ttk.Combobox(filter_grid, values=[
            "All", "Open", "In Progress", "Resolved", "Closed"
        ], state="readonly", width=15)
        self.my_tickets_status_filter.set("All")
        self.my_tickets_status_filter.grid(row=0, column=1, padx=(0, 10))
        
        # Search filter
        ttk.Label(filter_grid, text="Search:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        self.my_tickets_search = ttk.Entry(filter_grid, width=30)
        self.my_tickets_search.grid(row=0, column=3, padx=(0, 10))
        self.my_tickets_search.bind('<Return>', lambda e: self.refresh_my_tickets())
        
        ttk.Button(filter_grid, text="Apply", 
                  command=self.refresh_my_tickets).grid(row=0, column=4)
        
        # Tickets list
        self.my_tickets_frame = ttk.Frame(tickets_frame)
        self.my_tickets_frame.pack(fill="both", expand=True)
        
        # Load tickets
        self.refresh_my_tickets()
    
    def refresh_my_tickets(self):
        """Refresh my tickets list"""
        # Clear existing content
        for widget in self.my_tickets_frame.winfo_children():
            widget.destroy()
        
        # Get student ID
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                ttk.Label(self.my_tickets_frame, text="❌ No student ID found").pack(pady=20)
                return
            
            student_id = result[0]
            
        except Exception as e:
            ttk.Label(self.my_tickets_frame, text=f"❌ Database error: {e}").pack(pady=20)
            return
        
        # Build filters
        filters = {}
        status_filter = self.my_tickets_status_filter.get()
        if status_filter != "All":
            filters['status'] = status_filter
        
        search_text = self.my_tickets_search.get().strip()
        if search_text:
            filters['search'] = search_text
        
        # Get tickets
        try:
            result = self.support.get_student_tickets(student_id, filters, page=1, per_page=50)
            tickets = result['tickets']
            
            if not tickets:
                ttk.Label(self.my_tickets_frame, text="📭 No tickets found").pack(pady=20)
                return
            
            # Create tickets table
            columns = ('ID', 'Title', 'Status', 'Priority', 'Category', 'Created', 'Updated')
            tree = ttk.Treeview(self.my_tickets_frame, columns=columns, show='headings', height=20)
            
            # Configure columns
            for col in columns:
                tree.heading(col, text=col)
            
            tree.column('ID', width=80)
            tree.column('Title', width=300)
            tree.column('Status', width=100)
            tree.column('Priority', width=100)
            tree.column('Category', width=120)
            tree.column('Created', width=150)
            tree.column('Updated', width=150)
            
            # Add tickets
            for ticket in tickets:
                tree.insert('', 'end', values=(
                    ticket['ticket_id'],
                    ticket['title'][:50] + ('...' if len(ticket['title']) > 50 else ''),
                    ticket['status'],
                    ticket['priority'],
                    ticket['category'],
                    ticket['created_datetime'],
                    ticket.get('last_updated_datetime', 'N/A')
                ))
            
            # Scrollbar
            scrollbar = ttk.Scrollbar(self.my_tickets_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            # Double-click to view
            tree.bind('<Double-1>', lambda e: self.on_ticket_double_click(tree))
            
            # Context menu
            tree.bind('<Button-3>', lambda e: self.show_ticket_context_menu(e, tree))
            
            self.update_status(f"Loaded {len(tickets)} tickets")
            
        except Exception as e:
            ttk.Label(self.my_tickets_frame, text=f"❌ Error loading tickets: {e}").pack(pady=20)
    
    def show_all_tickets(self):
        """Show all tickets (staff only)"""
        self.clear_content()
        
        tickets_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tickets_frame, text="🎫 All Tickets")
        
        # Check permissions
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] not in ('staff', 'admin'):
            ttk.Label(tickets_frame, text="❌ Staff access required", 
                     style='Title.TLabel').pack(pady=20)
            return
        
        # Title and controls
        header_frame = ttk.Frame(tickets_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(header_frame, text="🎫 All Support Tickets", 
                 style='Title.TLabel').pack(side="left")
        
        control_frame = ttk.Frame(header_frame)
        control_frame.pack(side="right")
        
        ttk.Button(control_frame, text="🔄 Refresh", 
                  command=self.refresh_all_tickets).pack(side="left", padx=(0, 5))
        ttk.Button(control_frame, text="📊 Reports", 
                  command=self.show_reports).pack(side="left", padx=(0, 5))
        ttk.Button(control_frame, text="📦 Bulk Ops", 
                  command=self.show_bulk_operations).pack(side="left")
        
        # Advanced filters
        filter_frame = ttk.LabelFrame(tickets_frame, text="🔍 Advanced Filters", padding="10")
        filter_frame.pack(fill="x", pady=(0, 10))
        
        filter_grid = ttk.Frame(filter_frame)
        filter_grid.pack(fill="x")
        
        # Row 1
        ttk.Label(filter_grid, text="Status:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.all_tickets_status = ttk.Combobox(filter_grid, values=[
            "All"] + TICKET_STATUSES, state="readonly", width=12)
        self.all_tickets_status.set("All")
        self.all_tickets_status.grid(row=0, column=1, padx=(0, 10))
        
        ttk.Label(filter_grid, text="Priority:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        self.all_tickets_priority = ttk.Combobox(filter_grid, values=[
            "All"] + TICKET_PRIORITIES, state="readonly", width=12)
        self.all_tickets_priority.set("All")
        self.all_tickets_priority.grid(row=0, column=3, padx=(0, 10))
        
        ttk.Label(filter_grid, text="Category:").grid(row=0, column=4, sticky="w", padx=(0, 5))
        self.all_tickets_category = ttk.Combobox(filter_grid, values=[
            "All"] + SUPPORT_CATEGORIES, state="readonly", width=15)
        self.all_tickets_category.set("All")
        self.all_tickets_category.grid(row=0, column=5, padx=(0, 10))
        
        # Row 2
        ttk.Label(filter_grid, text="Assigned to:").grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(5, 0))
        self.all_tickets_assigned = ttk.Entry(filter_grid, width=15)
        self.all_tickets_assigned.grid(row=1, column=1, padx=(0, 10), pady=(5, 0))
        
        ttk.Label(filter_grid, text="Search:").grid(row=1, column=2, sticky="w", padx=(0, 5), pady=(5, 0))
        self.all_tickets_search = ttk.Entry(filter_grid, width=20)
        self.all_tickets_search.grid(row=1, column=3, columnspan=2, sticky="ew", padx=(0, 10), pady=(5, 0))
        self.all_tickets_search.bind('<Return>', lambda e: self.refresh_all_tickets())
        
        ttk.Button(filter_grid, text="Apply Filters", 
                  command=self.refresh_all_tickets).grid(row=1, column=5, pady=(5, 0))
        
        filter_grid.columnconfigure(4, weight=1)
        
        # Quick filter buttons
        quick_frame = ttk.Frame(filter_frame)
        quick_frame.pack(fill="x", pady=(10, 0))
        
        ttk.Button(quick_frame, text="🔥 High Priority", 
                  command=lambda: self.apply_quick_filter('priority', 'High')).pack(side="left", padx=(0, 5))
        ttk.Button(quick_frame, text="❌ Unassigned", 
                  command=lambda: self.apply_quick_filter('assigned', 'none')).pack(side="left", padx=(0, 5))
        ttk.Button(quick_frame, text="🚨 Escalated", 
                  command=lambda: self.apply_quick_filter('status', 'Escalated')).pack(side="left", padx=(0, 5))
        ttk.Button(quick_frame, text="🔄 Clear Filters", 
                  command=self.clear_all_filters).pack(side="left", padx=(0, 5))
        
        # Tickets list
        self.all_tickets_frame = ttk.Frame(tickets_frame)
        self.all_tickets_frame.pack(fill="both", expand=True)
        
        # Load tickets
        self.refresh_all_tickets()
    
    def apply_quick_filter(self, filter_type, value):
        """Apply quick filter"""
        if filter_type == 'priority':
            self.all_tickets_priority.set(value)
        elif filter_type == 'status':
            self.all_tickets_status.set(value)
        elif filter_type == 'assigned':
            if value == 'none':
                self.all_tickets_assigned.delete(0, tk.END)
                self.all_tickets_assigned.insert(0, 'UNASSIGNED')
        
        self.refresh_all_tickets()
    
    def clear_all_filters(self):
        """Clear all filters"""
        self.all_tickets_status.set("All")
        self.all_tickets_priority.set("All")
        self.all_tickets_category.set("All")
        self.all_tickets_assigned.delete(0, tk.END)
        self.all_tickets_search.delete(0, tk.END)
        self.refresh_all_tickets()
    
    def refresh_all_tickets(self):
        """Refresh all tickets list"""
        # Clear existing content
        for widget in self.all_tickets_frame.winfo_children():
            widget.destroy()
        
        # Build filters
        filters = {}
        
        status = self.all_tickets_status.get()
        if status != "All":
            filters['status'] = status
        
        priority = self.all_tickets_priority.get()
        if priority != "All":
            filters['priority'] = priority
        
        category = self.all_tickets_category.get()
        if category != "All":
            filters['category'] = category
        
        assigned = self.all_tickets_assigned.get().strip()
        if assigned:
            if assigned.upper() == 'UNASSIGNED':
                filters['assigned_to'] = None
            else:
                filters['assigned_to'] = assigned
        
        search = self.all_tickets_search.get().strip()
        if search:
            filters['search'] = search
        
        # Get tickets
        try:
            result = self.support.get_student_tickets(None, filters, page=1, per_page=100)
            tickets = result['tickets']
            
            if not tickets:
                ttk.Label(self.all_tickets_frame, text="📭 No tickets found with current filters").pack(pady=20)
                return
            
            # Create tickets table with enhanced columns
            columns = ('ID', 'Title', 'Student', 'Status', 'Priority', 'Category', 'Assigned', 'Created', 'Updated')
            tree = ttk.Treeview(self.all_tickets_frame, columns=columns, show='headings', height=25)
            
            # Configure columns
            for col in columns:
                tree.heading(col, text=col)
            
            tree.column('ID', width=60)
            tree.column('Title', width=250)
            tree.column('Student', width=100)
            tree.column('Status', width=100)
            tree.column('Priority', width=80)
            tree.column('Category', width=120)
            tree.column('Assigned', width=100)
            tree.column('Created', width=120)
            tree.column('Updated', width=120)
            
            # Add tickets with color coding
            for ticket in tickets:
                # Color coding based on priority
                tags = []
                if ticket['priority'] == 'Critical':
                    tags.append('critical')
                elif ticket['priority'] == 'Urgent':
                    tags.append('urgent')
                elif ticket['priority'] == 'High':
                    tags.append('high')
                
                # Add sentiment tag
                if ticket.get('sentiment') == 'frustrated':
                    tags.append('frustrated')
                
                tree.insert('', 'end', values=(
                    ticket['ticket_id'],
                    ticket['title'][:40] + ('...' if len(ticket['title']) > 40 else ''),
                    ticket['student_id'],
                    ticket['status'],
                    ticket['priority'],
                    ticket['category'],
                    ticket.get('assigned_to', 'Unassigned'),
                    ticket['created_datetime'][:16],
                    ticket.get('last_updated_datetime', 'N/A')[:16]
                ), tags=tags)
            
            # Configure tag colors
            tree.tag_configure('critical', background='#fee2e2', foreground='#dc2626')
            tree.tag_configure('urgent', background='#fed7aa', foreground='#ea580c')
            tree.tag_configure('high', background='#fef3c7', foreground='#d97706')
            tree.tag_configure('frustrated', background='#fce7f3', foreground='#be185d')
            
            # Scrollbars
            v_scrollbar = ttk.Scrollbar(self.all_tickets_frame, orient='vertical', command=tree.yview)
            h_scrollbar = ttk.Scrollbar(self.all_tickets_frame, orient='horizontal', command=tree.xview)
            tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
            
            tree.grid(row=0, column=0, sticky='nsew')
            v_scrollbar.grid(row=0, column=1, sticky='ns')
            h_scrollbar.grid(row=1, column=0, sticky='ew')
            
            self.all_tickets_frame.columnconfigure(0, weight=1)
            self.all_tickets_frame.rowconfigure(0, weight=1)
            
            # Bind events
            tree.bind('<Double-1>', lambda e: self.on_ticket_double_click(tree))
            tree.bind('<Button-3>', lambda e: self.show_staff_ticket_context_menu(e, tree))
            
            self.update_status(f"Loaded {len(tickets)} tickets")
            
        except Exception as e:
            ttk.Label(self.all_tickets_frame, text=f"❌ Error loading tickets: {e}").pack(pady=20)
    
    def view_ticket_details(self, ticket_id):
        """View detailed ticket information"""
        try:
            ticket = self.support.get_ticket_details(ticket_id)
            self.show_ticket_detail_window(ticket)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load ticket details: {e}")
    
    def show_ticket_detail_window(self, ticket):
        """Show ticket details in a new window"""
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"🎫 Ticket #{ticket['ticket_id']} - {ticket['title']}")
        detail_window.geometry("1200x850")
        detail_window.transient(self.root)
        
        # Create notebook for different sections
        detail_notebook = ttk.Notebook(detail_window, padding="10")
        detail_notebook.pack(fill="both", expand=True)
        
        # Overview tab
        overview_frame = ttk.Frame(detail_notebook, padding="10")
        detail_notebook.add(overview_frame, text="📋 Overview")
        
        self.create_ticket_overview(overview_frame, ticket)
        
        # Responses tab
        responses_frame = ttk.Frame(detail_notebook, padding="10")
        detail_notebook.add(responses_frame, text=f"💬 Responses ({len(ticket.get('responses', []))})")
        
        self.create_ticket_responses(responses_frame, ticket)
        
        # Attachments tab
        attachments = ticket.get('attachments', [])
        if attachments:
            attachments_frame = ttk.Frame(detail_notebook, padding="10")
            detail_notebook.add(attachments_frame, text=f"📎 Attachments ({len(attachments)})")
            
            self.create_ticket_attachments(attachments_frame, attachments)
        
        # Actions tab (for staff)
        if self.auth.current_user['role'] in ('staff', 'admin'):
            actions_frame = ttk.Frame(detail_notebook, padding="10")
            detail_notebook.add(actions_frame, text="🔧 Actions")
            
            self.create_ticket_actions(actions_frame, ticket, detail_window)
    
    def create_ticket_overview(self, parent, ticket):
        """Create ticket overview section"""
        # Header info
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill="x", pady=(0, 20))
        
        title_label = ttk.Label(header_frame, text=f"🎫 #{ticket['ticket_id']}: {ticket['title']}", 
                               style='Title.TLabel')
        title_label.pack(anchor="w")
        
        # Details grid
        details_frame = ttk.LabelFrame(parent, text="📊 Ticket Details", padding="15")
        details_frame.pack(fill="x", pady=(0, 10))
        
        details_grid = ttk.Frame(details_frame)
        details_grid.pack(fill="x")
        
        # Left column
        left_frame = ttk.Frame(details_grid)
        left_frame.pack(side="left", fill="both", expand=True)
        
        details = [
            ("👤 Student ID:", ticket['student_id']),
            ("📊 Status:", ticket['status']),
            ("🔥 Priority:", ticket['priority']),
            ("📂 Category:", ticket['category']),
            ("📅 Created:", ticket['created_datetime']),
        ]
        
        for i, (label, value) in enumerate(details):
            ttk.Label(left_frame, text=label, font=('Segoe UI', 9, 'bold')).grid(
                row=i, column=0, sticky="w", pady=2, padx=(0, 10))
            ttk.Label(left_frame, text=str(value)).grid(
                row=i, column=1, sticky="w", pady=2)
        
        # Right column
        right_frame = ttk.Frame(details_grid)
        right_frame.pack(side="right", fill="both", expand=True)
        
        right_details = [
            ("👨‍💼 Assigned to:", ticket.get('assigned_to', 'Unassigned')),
            ("⏰ Last Updated:", ticket.get('last_updated_datetime', 'N/A')),
            ("🎯 Resolution ETA:", ticket.get('estimated_resolution', 'N/A')),
            ("😊 Sentiment:", ticket.get('sentiment', 'neutral').title()),
            ("⭐ Satisfaction:", f"{ticket.get('satisfaction_rating', 'N/A')}/5" if ticket.get('satisfaction_rating') else 'N/A'),
        ]
        
        for i, (label, value) in enumerate(right_details):
            ttk.Label(right_frame, text=label, font=('Segoe UI', 9, 'bold')).grid(
                row=i, column=0, sticky="w", pady=2, padx=(0, 10))
            ttk.Label(right_frame, text=str(value)).grid(
                row=i, column=1, sticky="w", pady=2)
        
        # Tags
        if ticket.get('tags'):
            tags = json.loads(ticket['tags']) if isinstance(ticket['tags'], str) else ticket['tags']
            if tags:
                tags_frame = ttk.Frame(details_frame)
                tags_frame.pack(fill="x", pady=(10, 0))
                
                ttk.Label(tags_frame, text="🏷️ Tags:", font=('Segoe UI', 9, 'bold')).pack(side="left")
                for tag in tags:
                    tag_label = tk.Label(tags_frame, text=tag, bg="#e5e7eb", fg="#374151", 
                                       padx=8, pady=2, relief="solid", borderwidth=1)
                    tag_label.pack(side="left", padx=(5, 0))
        
        # Description
        desc_frame = ttk.LabelFrame(parent, text="📄 Description", padding="15")
        desc_frame.pack(fill="both", expand=True)
        
        desc_text = scrolledtext.ScrolledText(desc_frame, height=10, wrap=tk.WORD, state='disabled')
        desc_text.pack(fill="both", expand=True)
        
        desc_text.config(state='normal')
        desc_text.insert(1.0, ticket['description'])
        desc_text.config(state='disabled')
    
    def create_ticket_responses(self, parent, ticket):
        """Create ticket responses section"""
        responses = ticket.get('responses', [])
        
        if not responses:
            ttk.Label(parent, text="💬 No responses yet", style='Heading.TLabel').pack(pady=20)
            return
        
        # Create scrollable responses
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add responses
        for i, response in enumerate(responses):
            response_frame = ttk.LabelFrame(scrollable_frame, padding="10")
            response_frame.pack(fill="x", padx=5, pady=5)
            
            # Response header
            header_frame = ttk.Frame(response_frame)
            header_frame.pack(fill="x", pady=(0, 10))
            
            # Role badge
            role_color = {"staff": "#3b82f6", "admin": "#dc2626", "student": "#16a34a", "system": "#6b7280"}
            role_bg = role_color.get(response['responder_role'], "#6b7280")
            
            role_label = tk.Label(header_frame, text=response['responder_role'].upper(), 
                                bg=role_bg, fg="white", padx=8, pady=2, 
                                font=('Segoe UI', 8, 'bold'))
            role_label.pack(side="left")
            
            # Auto-generated and internal indicators
            if response.get('is_auto_generated'):
                auto_label = tk.Label(header_frame, text="🤖 AUTO", bg="#f59e0b", fg="white", 
                                    padx=6, pady=2, font=('Segoe UI', 8, 'bold'))
                auto_label.pack(side="left", padx=(5, 0))
            
            if response.get('is_internal'):
                internal_label = tk.Label(header_frame, text="🔒 INTERNAL", bg="#ef4444", fg="white", 
                                        padx=6, pady=2, font=('Segoe UI', 8, 'bold'))
                internal_label.pack(side="left", padx=(5, 0))
            
            # Timestamp
            ttk.Label(header_frame, text=response['response_datetime'], 
                     font=('Segoe UI', 9), foreground=self.colors['text_secondary']).pack(side="right")
            
            # Response text
            response_text = scrolledtext.ScrolledText(response_frame, height=6, wrap=tk.WORD, state='disabled')
            response_text.pack(fill="x", pady=(5, 0))
            
            response_text.config(state='normal')
            response_text.insert(1.0, response['response_text'])
            response_text.config(state='disabled')
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add response button (if permitted)
        if self.can_respond_to_ticket(ticket):
            add_response_btn = ttk.Button(parent, text="💬 Add Response", 
                                        command=lambda: self.show_add_response_dialog(ticket))
            add_response_btn.pack(side="bottom", pady=(10, 0))
    
    def create_ticket_attachments(self, parent, attachments):
        """Create ticket attachments section"""
        # Attachments list
        for attachment in attachments:
            att_frame = ttk.Frame(parent)
            att_frame.pack(fill="x", pady=5)
            
            # File icon based on type
            file_icons = {
                'image': '🖼️',
                'document': '📄',
                'video': '🎥',
                'other': '📎'
            }
            icon = file_icons.get(attachment.get('file_type', 'other'), '📎')
            
            # File info
            size_mb = attachment['file_size'] / (1024 * 1024)
            file_info = f"{icon} {attachment['original_filename']} ({size_mb:.1f}MB)"
            
            ttk.Label(att_frame, text=file_info).pack(side="left")
            
            # Upload info
            upload_info = f"Uploaded by {attachment['uploaded_by']} on {attachment['uploaded_datetime']}"
            ttk.Label(att_frame, text=upload_info, font=('Segoe UI', 9), 
                     foreground=self.colors['text_secondary']).pack(side="left", padx=(10, 0))
            
            # Download button
            ttk.Button(att_frame, text="📥 Download", 
                      command=lambda a=attachment: self.download_attachment(a)).pack(side="right")
    
    def create_ticket_actions(self, parent, ticket, window):
        """Create ticket actions section for staff"""
        # Status update
        status_frame = ttk.LabelFrame(parent, text="📊 Update Status", padding="10")
        status_frame.pack(fill="x", pady=(0, 10))
        
        status_grid = ttk.Frame(status_frame)
        status_grid.pack(fill="x")
        
        ttk.Label(status_grid, text="New Status:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        
        self.new_status_var = tk.StringVar(value=ticket['status'])
        status_combo = ttk.Combobox(status_grid, textvariable=self.new_status_var, 
                                   values=TICKET_STATUSES, state="readonly")
        status_combo.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        
        ttk.Button(status_grid, text="Update Status", 
                  command=lambda: self.update_ticket_status_action(ticket['ticket_id'], window)).grid(row=0, column=2)
        
        status_grid.columnconfigure(1, weight=1)
        
        # Assignment
        assign_frame = ttk.LabelFrame(parent, text="👨‍💼 Assignment", padding="10")
        assign_frame.pack(fill="x", pady=(0, 10))
        
        assign_grid = ttk.Frame(assign_frame)
        assign_grid.pack(fill="x")
        
        ttk.Label(assign_grid, text="Assign to:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        
        self.assign_to_var = tk.StringVar(value=ticket.get('assigned_to', ''))
        assign_entry = ttk.Entry(assign_grid, textvariable=self.assign_to_var)
        assign_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        
        ttk.Button(assign_grid, text="Assign to Me", 
                  command=lambda: self.assign_to_var.set(self.auth.current_user['username'])).grid(row=0, column=2, padx=(0, 10))
        
        ttk.Button(assign_grid, text="Update Assignment", 
                  command=lambda: self.update_ticket_assignment(ticket['ticket_id'], window)).grid(row=0, column=3)
        
        assign_grid.columnconfigure(1, weight=1)
        
        # Quick actions
        actions_frame = ttk.LabelFrame(parent, text="⚡ Quick Actions", padding="10")
        actions_frame.pack(fill="x", pady=(0, 10))
        
        actions_grid = ttk.Frame(actions_frame)
        actions_grid.pack(fill="x")
        
        ttk.Button(actions_grid, text="📝 Add Internal Note", 
                  command=lambda: self.show_add_internal_note_dialog(ticket)).grid(row=0, column=0, padx=(0, 5), pady=2)
        
        ttk.Button(actions_grid, text="📋 Use Template", 
                  command=lambda: self.show_response_template_dialog(ticket)).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Button(actions_grid, text="📊 View History", 
                  command=lambda: self.show_ticket_history(ticket['ticket_id'])).grid(row=0, column=2, padx=5, pady=2)
        
        ttk.Button(actions_grid, text="🔗 Merge Ticket", 
                  command=lambda: self.show_merge_dialog(ticket)).grid(row=1, column=0, padx=(0, 5), pady=2)
        
        ttk.Button(actions_grid, text="⚡ Escalate", 
                  command=lambda: self.escalate_ticket(ticket['ticket_id'])).grid(row=1, column=1, padx=5, pady=2)
        
        ttk.Button(actions_grid, text="📤 Export", 
                  command=lambda: self.export_ticket(ticket)).grid(row=1, column=2, padx=5, pady=2)
    
    def show_faqs(self):
        """Show FAQs interface"""
        self.clear_content()
        
        faqs_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(faqs_frame, text="❓ FAQs")
        
        # Title and search
        header_frame = ttk.Frame(faqs_frame)
        header_frame.pack(fill="x", pady=(0, 15))
        
        ttk.Label(header_frame, text="❓ Frequently Asked Questions", 
                 style='Title.TLabel').pack(side="left")
        
        search_frame = ttk.Frame(header_frame)
        search_frame.pack(side="right")
        
        self.faq_search = ttk.Entry(search_frame, width=30, font=('Segoe UI', 10))
        self.faq_search.pack(side="left", padx=(0, 5))
        self.faq_search.bind('<Return>', lambda e: self.search_faqs())
        
        ttk.Button(search_frame, text="🔍 Search", command=self.search_faqs).pack(side="left")
        
        # Categories
        categories_frame = ttk.LabelFrame(faqs_frame, text="📂 Browse by Category", padding="10")
        categories_frame.pack(fill="x", pady=(0, 15))
        
        self.faq_categories_frame = ttk.Frame(categories_frame)
        self.faq_categories_frame.pack(fill="x")
        
        # FAQs display area
        self.faqs_display_frame = ttk.Frame(faqs_frame)
        self.faqs_display_frame.pack(fill="both", expand=True)
        
        # Load FAQs
        self.load_faqs()
    
    def load_faqs(self):
        """Load and display FAQs"""
        try:
            # Get FAQ categories
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Check if FAQs table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='faqs'")
            if not cursor.fetchone():
                ttk.Label(self.faqs_display_frame, text="📭 No FAQs available").pack(pady=20)
                conn.close()
                return
            
            cursor.execute('SELECT DISTINCT category FROM faqs ORDER BY category')
            categories = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            # Clear existing category buttons
            for widget in self.faq_categories_frame.winfo_children():
                widget.destroy()
            
            # Create category buttons
            ttk.Button(self.faq_categories_frame, text="📋 All Categories", 
                      command=lambda: self.show_faqs_by_category(None)).pack(side="left", padx=(0, 5))
            
            for category in categories:
                ttk.Button(self.faq_categories_frame, text=f"📂 {category}", 
                          command=lambda c=category: self.show_faqs_by_category(c)).pack(side="left", padx=5)
            
            # Show all FAQs by default
            self.show_faqs_by_category(None)
            
        except Exception as e:
            ttk.Label(self.faqs_display_frame, text=f"❌ Error loading FAQs: {e}").pack(pady=20)
    
    def show_faqs_by_category(self, category):
        """Show FAQs filtered by category"""
        self._faq_last_mode = 'category'
        self._faq_last_category = category
        self._faq_last_query = None

        if hasattr(self, 'faq_search'):
            self.faq_search.delete(0, tk.END)
        
        # Clear display area
        for widget in self.faqs_display_frame.winfo_children():
            widget.destroy()
        
        try:
            # Get FAQs
            if self.support:
                filters = {'category': category} if category else None
                faqs = self.support._search_faqs('', filters)
            else:
                faqs = []
            
            if not faqs:
                ttk.Label(self.faqs_display_frame, text="📭 No FAQs found").pack(pady=20)
                return
            
            # Create scrollable FAQ list
            canvas = tk.Canvas(self.faqs_display_frame)
            scrollbar = ttk.Scrollbar(self.faqs_display_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Add FAQs
            for faq in faqs:
                self.create_faq_item(scrollable_frame, faq)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
        except Exception as e:
            ttk.Label(self.faqs_display_frame, text=f"❌ Error loading FAQs: {e}").pack(pady=20)
    
    def create_faq_item(self, parent, faq):
        """Create a single FAQ item"""
        faq_frame = ttk.LabelFrame(parent, text=f"❓ {faq['question']}", padding="10")
        faq_frame.pack(fill="x", padx=5, pady=5)
        
        # FAQ stats
        stats_text = f"📂 {faq['category']} | 👁️ {faq.get('view_count', 0)} views | 👍 {faq.get('helpful_votes', 0)} helpful"
        ttk.Label(faq_frame, text=stats_text, font=('Segoe UI', 9), 
                 foreground=self.colors['text_secondary']).pack(anchor="w")
        
        # Answer (collapsed by default)
        answer_frame = ttk.Frame(faq_frame)
        
        # Toggle button
        toggle_frame = ttk.Frame(faq_frame)
        toggle_frame.pack(fill="x", pady=(10, 0))
        
        def toggle_answer():
            if answer_frame.winfo_viewable():
                answer_frame.pack_forget()
                toggle_btn.config(text="▶️ Show Answer")
            else:
                answer_frame.pack(fill="x", pady=(10, 0), before=toggle_frame)
                toggle_btn.config(text="🔽 Hide Answer")
        
        toggle_btn = ttk.Button(toggle_frame, text="▶️ Show Answer", command=toggle_answer)
        toggle_btn.pack(side="left")
        
        # Helpful button
        ttk.Button(toggle_frame, text="👍 Helpful", 
                  command=lambda: self.mark_faq_helpful(faq['faq_id'])).pack(side="right")
        
        # Answer content (initially hidden)
        answer_text = scrolledtext.ScrolledText(answer_frame, height=6, wrap=tk.WORD, state='disabled')
        answer_text.pack(fill="x")
        
        answer_text.config(state='normal')
        answer_text.insert(1.0, faq['answer'])
        answer_text.config(state='disabled')
    
    def search_faqs(self):
        """Search FAQs"""
        query = self.faq_search.get().strip()
        if not query:
            self.show_faqs_by_category(None)
            return
        
        self._faq_last_mode = 'search'
        self._faq_last_query = query
        self._faq_last_category = None
    
        # Clear display area
        for widget in self.faqs_display_frame.winfo_children():
            widget.destroy()
        
        try:
            if self.support:
                faqs = self.support._search_faqs(query, None)
            else:
                faqs = []
            
            if not faqs:
                ttk.Label(self.faqs_display_frame, text=f"🔍 No FAQs found for '{query}'").pack(pady=20)
                return
            
            # Show search results
            results_label = ttk.Label(self.faqs_display_frame, 
                                    text=f"🔍 Search Results for '{query}' ({len(faqs)} found)", 
                                    style='Heading.TLabel')
            results_label.pack(anchor="w", pady=(0, 10))
            
            # Create scrollable results
            canvas = tk.Canvas(self.faqs_display_frame)
            scrollbar = ttk.Scrollbar(self.faqs_display_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Add search results
            for faq in faqs:
                self.create_faq_item(scrollable_frame, faq)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
        except Exception as e:
            ttk.Label(self.faqs_display_frame, text=f"❌ Error searching FAQs: {e}").pack(pady=20)
            
    def show_preferences(self):
        """Show user preferences interface"""
        self.clear_content()
        
        prefs_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(prefs_frame, text="⚙️ Preferences")
        
        ttk.Label(prefs_frame, text="⚙️ User Preferences", 
                 style='Title.TLabel').pack(pady=(0, 20))
        
        # Get current preferences
        try:
            if self.support:
                current_prefs = self.support.get_user_preferences()
            else:
                current_prefs = {}
        except:
            current_prefs = {}
        
        # Preferences form
        form_frame = ttk.LabelFrame(prefs_frame, text="Notification Settings", padding="15")
        form_frame.pack(fill="x", pady=(0, 10))
        
        # Notification preferences
        self.email_notifications_var = tk.BooleanVar(value=current_prefs.get('email_notifications', True))
        ttk.Checkbutton(form_frame, text="📧 Email Notifications", 
                       variable=self.email_notifications_var).pack(anchor="w", pady=2)
        
        self.in_app_notifications_var = tk.BooleanVar(value=current_prefs.get('in_app_notifications', True))
        ttk.Checkbutton(form_frame, text="🔔 In-App Notifications", 
                       variable=self.in_app_notifications_var).pack(anchor="w", pady=2)
        
        self.push_notifications_var = tk.BooleanVar(value=current_prefs.get('push_notifications', True))
        ttk.Checkbutton(form_frame, text="📱 Push Notifications", 
                       variable=self.push_notifications_var).pack(anchor="w", pady=2)
        
        # Digest frequency
        digest_frame = ttk.Frame(form_frame)
        digest_frame.pack(fill="x", pady=(10, 0))
        
        ttk.Label(digest_frame, text="📅 Digest Frequency:").pack(side="left")
        self.digest_frequency_var = tk.StringVar(value=current_prefs.get('digest_frequency', 'daily'))
        digest_combo = ttk.Combobox(digest_frame, textvariable=self.digest_frequency_var,
                                   values=['immediate', 'daily', 'weekly'], state="readonly")
        digest_combo.pack(side="left", padx=(10, 0))
        
        # Display preferences
        display_frame = ttk.LabelFrame(prefs_frame, text="Display Settings", padding="15")
        display_frame.pack(fill="x", pady=(0, 10))
        
        # Theme
        theme_frame = ttk.Frame(display_frame)
        theme_frame.pack(fill="x", pady=2)
        
        ttk.Label(theme_frame, text="🎨 Theme:").pack(side="left")
        self.theme_var = tk.StringVar(value=current_prefs.get('theme', 'light'))
        theme_combo = ttk.Combobox(theme_frame, textvariable=self.theme_var,
                                  values=['light', 'dark'], state="readonly")
        theme_combo.pack(side="left", padx=(10, 0))
        
        # Language
        language_frame = ttk.Frame(display_frame)
        language_frame.pack(fill="x", pady=2)
        
        ttk.Label(language_frame, text="🌐 Language:").pack(side="left")
        self.language_var = tk.StringVar(value=current_prefs.get('language', 'en'))
        language_combo = ttk.Combobox(language_frame, textvariable=self.language_var,
                                     values=['en', 'es', 'fr', 'de'], state="readonly")
        language_combo.pack(side="left", padx=(10, 0))
        
        # Timezone
        timezone_frame = ttk.Frame(display_frame)
        timezone_frame.pack(fill="x", pady=2)
        
        ttk.Label(timezone_frame, text="🕐 Timezone:").pack(side="left")
        self.timezone_var = tk.StringVar(value=current_prefs.get('timezone', 'UTC'))
        timezone_entry = ttk.Entry(timezone_frame, textvariable=self.timezone_var, width=20)
        timezone_entry.pack(side="left", padx=(10, 0))
        
        # Save button
        ttk.Button(prefs_frame, text="💾 Save Preferences", 
                  command=self.save_preferences, style='Primary.TButton').pack(pady=20)
    
    def save_preferences(self):
        """Save user preferences"""
        try:
            preferences = {
                'email_notifications': self.email_notifications_var.get(),
                'in_app_notifications': self.in_app_notifications_var.get(),
                'push_notifications': self.push_notifications_var.get(),
                'digest_frequency': self.digest_frequency_var.get(),
                'theme': self.theme_var.get(),
                'language': self.language_var.get(),
                'timezone': self.timezone_var.get()
            }
            
            if self.support:
                self.support.update_user_preferences(preferences)
                messagebox.showinfo("Success", "Preferences saved successfully!")
                self.update_status("Preferences saved")
            else:
                messagebox.showerror("Error", "Support system not available")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save preferences: {e}")
        
    def show_notifications(self):
        """Show notifications interface"""
        self.clear_content()
        
        notifications_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(notifications_frame, text="🔔 Notifications")
        
        # Header
        header_frame = ttk.Frame(notifications_frame)
        header_frame.pack(fill="x", pady=(0, 15))
        
        ttk.Label(header_frame, text="🔔 Notifications", 
                 style='Title.TLabel').pack(side="left")
        
        # Mark all as read button
        ttk.Button(header_frame, text="📫 Mark All Read", 
                  command=self.mark_all_notifications_read).pack(side="right")
        
        # Filter options
        filter_frame = ttk.Frame(notifications_frame)
        filter_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(filter_frame, text="Filter:").pack(side="left")
        
        self.notification_filter_var = tk.StringVar(value="All")
        filter_combo = ttk.Combobox(filter_frame, textvariable=self.notification_filter_var,
                                   values=["All", "Unread", "Read"], state="readonly")
        filter_combo.pack(side="left", padx=(10, 0))
        filter_combo.bind('<<ComboboxSelected>>', lambda e: self.load_notifications())
        
        # Notifications display
        self.notifications_display_frame = ttk.Frame(notifications_frame)
        self.notifications_display_frame.pack(fill="both", expand=True)
        
        # Load notifications
        self.load_notifications()
    
    def load_notifications(self):
        """Load and display notifications"""
        # Clear display
        for widget in self.notifications_display_frame.winfo_children():
            widget.destroy()
        
        try:
            # Get notifications (using dashboard data for now)
            notifications = self.dashboard_data.get('notifications', [])
            
            # Apply filter
            filter_value = self.notification_filter_var.get()
            if filter_value == "Unread":
                notifications = [n for n in notifications if not n.get('is_read', False)]
            elif filter_value == "Read":
                notifications = [n for n in notifications if n.get('is_read', False)]
            
            if not notifications:
                ttk.Label(self.notifications_display_frame, text="📭 No notifications").pack(pady=20)
                return
            
            # Create scrollable notifications list
            canvas = tk.Canvas(self.notifications_display_frame)
            scrollbar = ttk.Scrollbar(self.notifications_display_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Add notifications
            for notification in notifications:
                self.create_notification_item(scrollable_frame, notification)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
        except Exception as e:
            ttk.Label(self.notifications_display_frame, text=f"❌ Error loading notifications: {e}").pack(pady=20)
    
    def create_notification_item(self, parent, notification):
        """Create a notification item"""
        # Frame with background color based on read status
        bg_color = "#f8fafc" if notification.get('is_read') else "#dbeafe"
        
        notif_frame = tk.Frame(parent, bg=bg_color, relief="solid", bd=1)
        notif_frame.pack(fill="x", padx=5, pady=2)
        
        content_frame = ttk.Frame(notif_frame)
        content_frame.pack(fill="x", padx=10, pady=8)
        
        # Status icon and title
        header_frame = ttk.Frame(content_frame)
        header_frame.pack(fill="x")
        
        status_icon = "📫" if notification.get('is_read') else "📬"
        title_text = f"{status_icon} {notification['title']}"
        
        ttk.Label(header_frame, text=title_text, font=('Segoe UI', 10, 'bold')).pack(side="left")
        
        # Timestamp
        ttk.Label(header_frame, text=notification['created'], font=('Segoe UI', 9),
                 foreground=self.colors['text_secondary']).pack(side="right")
        
        # Message
        if notification.get('message'):
            ttk.Label(content_frame, text=notification['message'], wraplength=700).pack(anchor="w", pady=(5, 0))
        
        # Actions
        if not notification.get('is_read'):
            action_frame = ttk.Frame(content_frame)
            action_frame.pack(anchor="w", pady=(5, 0))
            
            ttk.Button(action_frame, text="✓ Mark as Read", 
                      command=lambda: self.mark_notification_read(notification)).pack(side="left", padx=(0, 5))
    
    def mark_notification_read(self, notification):
        """Mark a notification as read"""
        notification_id = notification.get('notification_id') or notification.get('id')
        user_id, _ = self._get_current_user_identity()

        if not notification_id:
            messagebox.showerror("Error", "Notification identifier missing.")
            return

        if not user_id:
            messagebox.showerror("Error", "You must be signed in to update notifications.")
            return

        try:
            success = False
            if self.support and hasattr(self.support, 'mark_notification_read'):
                success = self.support.mark_notification_read(notification_id, user_id=user_id)
            else:
                def update_notification(conn):
                    cursor = conn.cursor()
                    cursor.execute(
                        '''
                        UPDATE notifications
                        SET is_read = 1, read_datetime = ?
                        WHERE notification_id = ? AND user_id = ?
                        ''',
                        (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), notification_id, user_id)
                    )
                    return cursor.rowcount
                success = self._safe_db_call(update_notification) > 0

            if not success:
                messagebox.showwarning("Notification", "Notification was already marked as read or no longer exists.")
                return

            notification['is_read'] = True
            self.load_dashboard()
            self.load_notifications()
            self.update_status("Notification marked as read")
        except Exception as e:
            messagebox.showerror("Error", f"Could not mark notification as read: {e}")
    
    def mark_all_notifications_read(self):
        """Mark all notifications as read"""
        user_id, _ = self._get_current_user_identity()
        if not user_id:
            messagebox.showerror("Error", "You must be signed in to update notifications.")
            return

        try:
            def bulk_update(conn):
                cursor = conn.cursor()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    '''
                    UPDATE notifications
                    SET is_read = 1,
                        read_datetime = COALESCE(read_datetime, ?)
                    WHERE user_id = ? AND is_read = 0
                    ''',
                    (timestamp, user_id)
                )
                return cursor.rowcount

            updated = 0
            if self.support and hasattr(self.support, 'get_user_notifications'):
                notifications = self.support.get_user_notifications(user_id=user_id, unread_only=True)
                for notif in notifications:
                    if self.support.mark_notification_read(notif['notification_id'], user_id=user_id):
                        updated += 1
            else:
                updated = self._safe_db_call(bulk_update)

            self.load_dashboard()
            self.load_notifications()
            self.update_status("All notifications marked as read")
            messagebox.showinfo("Success", f"Marked {updated} notification(s) as read.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not mark notifications as read: {e}")
    
    # Additional helper methods
    def on_ticket_double_click(self, tree):
        """Handle double-click on ticket in tree view"""
        selection = tree.selection()
        if selection:
            item = tree.item(selection[0])
            ticket_id = item['values'][0]  # First column is ticket ID
            self.view_ticket_details(ticket_id)
    
    def show_ticket_context_menu(self, event, tree):
        """Show context menu for ticket"""
        # Create context menu
        context_menu = tk.Menu(self.root, tearoff=0)
        
        # Get selected item
        item = tree.identify_row(event.y)
        if item:
            tree.selection_set(item)
            ticket_data = tree.item(item)
            ticket_id = ticket_data['values'][0]
            
            context_menu.add_command(label="👁️ View Details", 
                                   command=lambda: self.view_ticket_details(ticket_id))
            context_menu.add_command(label="💬 Add Response", 
                                   command=lambda: self.show_add_response_dialog_by_id(ticket_id))
            
            if self.auth.current_user['role'] in ('staff', 'admin'):
                context_menu.add_separator()
                context_menu.add_command(label="📊 Update Status", 
                                       command=lambda: self.show_status_update_dialog(ticket_id))
                context_menu.add_command(label="👨‍💼 Assign to Me", 
                                       command=lambda: self.assign_ticket_to_me(ticket_id))
            
            # Show menu
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()
    
    def show_staff_ticket_context_menu(self, event, tree):
        """Show staff-specific context menu"""
        self.show_ticket_context_menu(event, tree)  # Use same menu for now
    
    def assign_ticket_to_me(self, ticket_id):
        """Assign ticket to current user"""
        user_id, username = self._get_current_user_identity()
        if not user_id or not username:
            messagebox.showerror("Error", "You must be signed in to assign tickets.")
            return

        role = self.auth.current_user.get('role') if self.auth and self.auth.current_user else None
        if role not in ('staff', 'admin'):
            messagebox.showwarning("Permission Denied", "Only staff members can self-assign tickets.")
            return

        try:
            def assign(conn):
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT assigned_to, status
                    FROM support_tickets
                    WHERE ticket_id = ?
                    ''',
                    (ticket_id,)
                )
                row = cursor.fetchone()
                if not row:
                    return {'updated': False, 'reason': 'not_found'}

                current_assignee, status = row
                if current_assignee == username:
                    return {'updated': False, 'reason': 'already_assigned'}

                if status in ('Resolved', 'Closed'):
                    return {'updated': False, 'reason': 'closed'}

                new_status = status
                if status is None or status.lower() in ('open', 'new', 'unassigned', 'pending'):
                    new_status = 'In Progress'

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    '''
                    UPDATE support_tickets
                    SET assigned_to = ?, status = ?, last_updated_datetime = ?
                    WHERE ticket_id = ?
                    ''',
                    (username, new_status, timestamp, ticket_id)
                )
                return {'updated': cursor.rowcount > 0, 'new_status': new_status}

            result = self._safe_db_call(assign)

            if not result['updated']:
                reason = result.get('reason')
                if reason == 'not_found':
                    messagebox.showerror("Error", f"Ticket #{ticket_id} was not found.")
                elif reason == 'already_assigned':
                    messagebox.showinfo("Information", "You are already assigned to this ticket.")
                elif reason == 'closed':
                    messagebox.showwarning("Ticket Closed", "Closed or resolved tickets cannot be reassigned.")
                else:
                    messagebox.showwarning("No Changes", "Ticket assignment was not updated.")
                return

            messagebox.showinfo("Success", f"Ticket #{ticket_id} assigned to you (status: {result['new_status']}).")
            self.refresh_data()
        except Exception as e:
            messagebox.showerror("Error", f"Could not assign ticket: {e}")
    
    def show_add_response_dialog(self, ticket):
        """Show dialog to add response to ticket"""
        response_dialog = tk.Toplevel(self.root)
        response_dialog.title(f"💬 Add Response to Ticket #{ticket['ticket_id']}")
        response_dialog.geometry("800x600")
        response_dialog.transient(self.root)
        response_dialog.grab_set()
        
        # Dialog content
        form_frame = ttk.Frame(response_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)
        
        ttk.Label(form_frame, text=f"Adding response to: {ticket['title']}", 
                 style='Heading.TLabel').pack(anchor="w", pady=(0, 15))
        
        # Response text
        ttk.Label(form_frame, text="Response:").pack(anchor="w")
        response_text = scrolledtext.ScrolledText(form_frame, height=12, wrap=tk.WORD)
        response_text.pack(fill="both", expand=True, pady=(5, 15))
        
        # Options
        options_frame = ttk.Frame(form_frame)
        options_frame.pack(fill="x", pady=(0, 15))
        
        # Internal note checkbox (for staff)
        if self.auth.current_user['role'] in ('staff', 'admin'):
            self.is_internal_var = tk.BooleanVar()
            ttk.Checkbutton(options_frame, text="🔒 Internal note (staff only)", 
                           variable=self.is_internal_var).pack(side="left")
        
        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x")
        
        def submit_response():
            text = response_text.get(1.0, tk.END).strip()
            if not text:
                messagebox.showerror("Error", "Response cannot be empty")
                return
            
            try:
                is_internal = getattr(self, 'is_internal_var', tk.BooleanVar()).get()
                self.support.add_ticket_response(ticket['ticket_id'], text, is_internal=is_internal)
                messagebox.showinfo("Success", "Response added successfully!")
                response_dialog.destroy()
                self.refresh_data()
            except Exception as e:
                messagebox.showerror("Error", f"Could not add response: {e}")
        
        ttk.Button(btn_frame, text="💬 Add Response", command=submit_response, 
                  style='Primary.TButton').pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=response_dialog.destroy).pack(side="left")
    
    def show_add_response_dialog_by_id(self, ticket_id):
        """Show add response dialog by ticket ID"""
        try:
            ticket = self.support.get_ticket_details(ticket_id)
            self.show_add_response_dialog(ticket)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load ticket: {e}")
    
    def can_respond_to_ticket(self, ticket):
        """Check if current user can respond to ticket"""
        if not self.auth or not self.auth.current_user:
            return False
        
        user_role = self.auth.current_user['role']
        
        # Staff can always respond
        if user_role in ('staff', 'admin'):
            return True
        
        # Students can respond to their own tickets
        if user_role == 'student':
            try:
                from university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
                result = cursor.fetchone()
                conn.close()
                
                if result and result[0] == ticket['student_id']:
                    return True
            except:
                pass
        
        return False
    
    def download_attachment(self, attachment):
        """Download ticket attachment"""
        try:
            file_info = self.support.download_attachment(attachment['attachment_id'])
            
            # Save file dialog
            filename = filedialog.asksaveasfilename(
                title="Save Attachment",
                initialname=file_info['filename'],
                defaultextension=os.path.splitext(file_info['filename'])[1]
            )
            
            if filename:
                with open(filename, 'wb') as f:
                    f.write(file_info['data'])
                
                messagebox.showinfo("Success", f"File saved as {filename}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Could not download attachment: {e}")
    
    def open_url(self, url):
        """Open URL in web browser"""
        try:
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open URL: {e}")
    
    def open_file(self, file_path):
        """Open file with default application"""
        try:
            if os.path.exists(file_path):
                os.startfile(file_path)  # Windows
            else:
                messagebox.showerror("Error", "File not found")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file: {e}")
    
    def open_resource(self, resource):
        """Open support resource"""
        if resource.get('url'):
            self.open_url(resource['url'])
        elif resource.get('file_path'):
            self.open_file(resource['file_path'])
        else:
            messagebox.showinfo("Resource", f"Resource: {resource['title']}\n\n{resource['description']}")
    
    def search_suggestion(self, suggestion):
        """Search using a suggestion"""
        self.search_query.delete(0, tk.END)
        self.search_query.insert(0, suggestion)
        self.perform_search()
    
    def show_faq_detail(self, faq):
        """Show FAQ detail in popup"""
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"❓ {faq['question']}")
        detail_window.geometry("900x650")
        detail_window.transient(self.root)
        
        # Content
        content_frame = ttk.Frame(detail_window, padding="20")
        content_frame.pack(fill="both", expand=True)
        
        # Question
        ttk.Label(content_frame, text=faq['question'], style='Heading.TLabel').pack(anchor="w", pady=(0, 10))
        
        # Metadata
        meta_text = f"📂 {faq['category']} | 👁️ {faq.get('view_count', 0)} views | 👍 {faq.get('helpful_votes', 0)} helpful"
        ttk.Label(content_frame, text=meta_text, font=('Segoe UI', 9), 
                 foreground=self.colors['text_secondary']).pack(anchor="w", pady=(0, 15))
        
        # Answer
        ttk.Label(content_frame, text="Answer:", font=('Segoe UI', 10, 'bold')).pack(anchor="w")
        
        answer_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, state='disabled')
        answer_text.pack(fill="both", expand=True, pady=(5, 15))
        
        answer_text.config(state='normal')
        answer_text.insert(1.0, faq['answer'])
        answer_text.config(state='disabled')
        
        # Feedback
        feedback_frame = ttk.Frame(content_frame)
        feedback_frame.pack(fill="x")
        
        ttk.Button(feedback_frame, text="👍 Helpful", 
                  command=lambda: self.mark_faq_helpful(faq['faq_id'])).pack(side="left", padx=(0, 10))
        ttk.Button(feedback_frame, text="❌ Close", command=detail_window.destroy).pack(side="right")
    
    def show_manage_templates(self):
        """Show template management interface (staff only)"""
        self.clear_content()

        templates_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(templates_frame, text="🔧 Manage Templates")

        # Check permissions
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] not in ('staff', 'admin'):
            ttk.Label(templates_frame, text="❌ Staff access required",
                     style='Title.TLabel').pack(pady=20)
            return

        ttk.Label(templates_frame, text="🔧 Template Management",
                 style='Title.TLabel').pack(pady=(0, 20))

        # Create notebook for ticket and response templates
        template_notebook = ttk.Notebook(templates_frame)
        template_notebook.pack(fill=tk.BOTH, expand=True)

        # Ticket Templates Tab
        ticket_template_frame = ttk.Frame(template_notebook, padding=10)
        template_notebook.add(ticket_template_frame, text="🎫 Ticket Templates")

        # Ticket templates controls
        ticket_controls = ttk.Frame(ticket_template_frame)
        ticket_controls.pack(fill=tk.X, pady=10)

        ttk.Button(ticket_controls, text="➕ Create Ticket Template",
                  command=lambda: self.create_ticket_template()).pack(side=tk.LEFT, padx=5)
        ttk.Button(ticket_controls, text="✏️ Edit Template",
                  command=lambda: self.edit_ticket_template()).pack(side=tk.LEFT, padx=5)
        ttk.Button(ticket_controls, text="🗑️ Delete Template",
                  command=lambda: self.delete_ticket_template()).pack(side=tk.LEFT, padx=5)
        ttk.Button(ticket_controls, text="🔄 Refresh",
                  command=lambda: self.refresh_ticket_templates()).pack(side=tk.LEFT, padx=5)

        # Ticket templates list
        ticket_list_frame = ttk.LabelFrame(ticket_template_frame, text="Ticket Templates", padding=10)
        ticket_list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        columns = ("ID", "Name", "Category", "Priority", "Created By", "Created Date", "Usage Count")
        self.ticket_templates_tree = ttk.Treeview(ticket_list_frame, columns=columns, show="headings", height=12)

        # Configure columns
        self.ticket_templates_tree.column("ID", width=50)
        self.ticket_templates_tree.column("Name", width=200)
        self.ticket_templates_tree.column("Category", width=120)
        self.ticket_templates_tree.column("Priority", width=80)
        self.ticket_templates_tree.column("Created By", width=100)
        self.ticket_templates_tree.column("Created Date", width=150)
        self.ticket_templates_tree.column("Usage Count", width=100)

        for col in columns:
            self.ticket_templates_tree.heading(col, text=col)

        scrollbar = ttk.Scrollbar(ticket_list_frame, orient=tk.VERTICAL, command=self.ticket_templates_tree.yview)
        self.ticket_templates_tree.configure(yscrollcommand=scrollbar.set)
        self.ticket_templates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Response Templates Tab
        response_template_frame = ttk.Frame(template_notebook, padding=10)
        template_notebook.add(response_template_frame, text="💬 Response Templates")

        # Response templates controls
        response_controls = ttk.Frame(response_template_frame)
        response_controls.pack(fill=tk.X, pady=10)

        ttk.Button(response_controls, text="➕ Create Response Template",
                  command=lambda: self.create_response_template()).pack(side=tk.LEFT, padx=5)
        ttk.Button(response_controls, text="✏️ Edit Template",
                  command=lambda: self.edit_response_template()).pack(side=tk.LEFT, padx=5)
        ttk.Button(response_controls, text="🗑️ Delete Template",
                  command=lambda: self.delete_response_template()).pack(side=tk.LEFT, padx=5)
        ttk.Button(response_controls, text="🔄 Refresh",
                  command=lambda: self.refresh_response_templates()).pack(side=tk.LEFT, padx=5)

        # Response templates list
        response_list_frame = ttk.LabelFrame(response_template_frame, text="Response Templates", padding=10)
        response_list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        columns = ("ID", "Name", "Subject", "Category", "Created By", "Created Date", "Usage Count")
        self.response_templates_tree = ttk.Treeview(response_list_frame, columns=columns, show="headings", height=12)

        # Configure columns
        self.response_templates_tree.column("ID", width=50)
        self.response_templates_tree.column("Name", width=180)
        self.response_templates_tree.column("Subject", width=200)
        self.response_templates_tree.column("Category", width=120)
        self.response_templates_tree.column("Created By", width=100)
        self.response_templates_tree.column("Created Date", width=150)
        self.response_templates_tree.column("Usage Count", width=100)

        for col in columns:
            self.response_templates_tree.heading(col, text=col)

        scrollbar = ttk.Scrollbar(response_list_frame, orient=tk.VERTICAL, command=self.response_templates_tree.yview)
        self.response_templates_tree.configure(yscrollcommand=scrollbar.set)
        self.response_templates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load templates
        self.refresh_ticket_templates()
        self.refresh_response_templates()

    def refresh_ticket_templates(self):
        """Refresh ticket templates list"""
        try:
            # Clear existing items
            for item in self.ticket_templates_tree.get_children():
                self.ticket_templates_tree.delete(item)

            # Load from database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT template_id, name, category, priority, created_by,
                       created_datetime, usage_count
                FROM ticket_templates
                ORDER BY created_datetime DESC
            ''')

            templates = cursor.fetchall()
            conn.close()

            # Add to tree
            for template in templates:
                self.ticket_templates_tree.insert('', tk.END, values=(
                    template['template_id'],
                    template['name'],
                    template['category'],
                    template['priority'],
                    template['created_by'],
                    template['created_datetime'],
                    template['usage_count'] or 0
                ))

            self.update_status(f"Loaded {len(templates)} ticket templates")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load ticket templates: {e}")

    def refresh_response_templates(self):
        """Refresh response templates list"""
        try:
            # Clear existing items
            for item in self.response_templates_tree.get_children():
                self.response_templates_tree.delete(item)

            # Load from database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT template_id, name, subject, category, created_by,
                       created_datetime, usage_count
                FROM response_templates
                ORDER BY created_datetime DESC
            ''')

            templates = cursor.fetchall()
            conn.close()

            # Add to tree
            for template in templates:
                self.response_templates_tree.insert('', tk.END, values=(
                    template['template_id'],
                    template['name'],
                    template['subject'],
                    template['category'] or 'General',
                    template['created_by'],
                    template['created_datetime'],
                    template['usage_count'] or 0
                ))

            self.update_status(f"Loaded {len(templates)} response templates")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load response templates: {e}")

    def create_ticket_template(self):
        """Create a new ticket template"""
        dialog = tk.Toplevel(self.root)
        dialog.title("➕ Create Ticket Template")
        dialog.geometry("600x550")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text="➕ Create Ticket Template", style='Heading.TLabel').pack(pady=(0, 20))

        # Name
        ttk.Label(form_frame, text="Template Name:").pack(anchor="w")
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, width=50).pack(fill="x", pady=(5, 10))

        # Category
        ttk.Label(form_frame, text="Category:").pack(anchor="w")
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, values=SUPPORT_CATEGORIES, state="readonly", width=47)
        category_combo.pack(fill="x", pady=(5, 10))
        if SUPPORT_CATEGORIES:
            category_combo.current(0)

        # Priority
        ttk.Label(form_frame, text="Priority:").pack(anchor="w")
        priority_var = tk.StringVar()
        priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, values=TICKET_PRIORITIES, state="readonly", width=47)
        priority_combo.pack(fill="x", pady=(5, 10))
        if TICKET_PRIORITIES:
            priority_combo.current(1)  # Default to Medium

        # Title Template
        ttk.Label(form_frame, text="Title Template:").pack(anchor="w")
        title_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=title_var, width=50).pack(fill="x", pady=(5, 10))

        # Description Template
        ttk.Label(form_frame, text="Description Template:").pack(anchor="w")
        desc_text = scrolledtext.ScrolledText(form_frame, height=8, width=50)
        desc_text.pack(fill="both", expand=True, pady=(5, 10))

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        def save_template():
            name = name_var.get().strip()
            category = category_var.get()
            priority = priority_var.get()
            title_template = title_var.get().strip()
            description_template = desc_text.get("1.0", tk.END).strip()

            if not all([name, category, priority, title_template, description_template]):
                messagebox.showerror("Error", "All fields are required")
                return

            try:
                template_id = self.support.create_ticket_template(
                    name, title_template, description_template, category, priority
                )
                messagebox.showinfo("Success", f"Ticket template created successfully (ID: {template_id})")
                dialog.destroy()
                self.refresh_ticket_templates()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create template: {e}")

        ttk.Button(btn_frame, text="💾 Save", command=save_template).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy).pack(side="left")

    def edit_ticket_template(self):
        """Edit selected ticket template"""
        selection = self.ticket_templates_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a template to edit")
            return

        item = self.ticket_templates_tree.item(selection[0])
        template_id = item['values'][0]

        # Load template data
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM ticket_templates WHERE template_id = ?', (template_id,))
            template = cursor.fetchone()
            conn.close()

            if not template:
                messagebox.showerror("Error", "Template not found")
                return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load template: {e}")
            return

        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"✏️ Edit Ticket Template #{template_id}")
        dialog.geometry("600x550")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text=f"✏️ Edit Ticket Template #{template_id}", style='Heading.TLabel').pack(pady=(0, 20))

        # Name
        ttk.Label(form_frame, text="Template Name:").pack(anchor="w")
        name_var = tk.StringVar(value=template['name'])
        ttk.Entry(form_frame, textvariable=name_var, width=50).pack(fill="x", pady=(5, 10))

        # Category
        ttk.Label(form_frame, text="Category:").pack(anchor="w")
        category_var = tk.StringVar(value=template['category'])
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, values=SUPPORT_CATEGORIES, state="readonly", width=47)
        category_combo.pack(fill="x", pady=(5, 10))

        # Priority
        ttk.Label(form_frame, text="Priority:").pack(anchor="w")
        priority_var = tk.StringVar(value=template['priority'])
        priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, values=TICKET_PRIORITIES, state="readonly", width=47)
        priority_combo.pack(fill="x", pady=(5, 10))

        # Title Template
        ttk.Label(form_frame, text="Title Template:").pack(anchor="w")
        title_var = tk.StringVar(value=template['title_template'])
        ttk.Entry(form_frame, textvariable=title_var, width=50).pack(fill="x", pady=(5, 10))

        # Description Template
        ttk.Label(form_frame, text="Description Template:").pack(anchor="w")
        desc_text = scrolledtext.ScrolledText(form_frame, height=8, width=50)
        desc_text.insert("1.0", template['description_template'])
        desc_text.pack(fill="both", expand=True, pady=(5, 10))

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        def save_changes():
            name = name_var.get().strip()
            category = category_var.get()
            priority = priority_var.get()
            title_template = title_var.get().strip()
            description_template = desc_text.get("1.0", tk.END).strip()

            if not all([name, category, priority, title_template, description_template]):
                messagebox.showerror("Error", "All fields are required")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE ticket_templates
                    SET name = ?, title_template = ?, description_template = ?,
                        category = ?, priority = ?
                    WHERE template_id = ?
                ''', (name, title_template, description_template, category, priority, template_id))
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Template updated successfully")
                dialog.destroy()
                self.refresh_ticket_templates()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update template: {e}")

        ttk.Button(btn_frame, text="💾 Save Changes", command=save_changes).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy).pack(side="left")

    def delete_ticket_template(self):
        """Delete selected ticket template"""
        selection = self.ticket_templates_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a template to delete")
            return

        item = self.ticket_templates_tree.item(selection[0])
        template_id = item['values'][0]
        template_name = item['values'][1]

        if not messagebox.askyesno("Confirm Delete",
                                   f"Are you sure you want to delete template '{template_name}'?\n\nThis action cannot be undone."):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('DELETE FROM ticket_templates WHERE template_id = ?', (template_id,))
            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Template deleted successfully")
            self.refresh_ticket_templates()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete template: {e}")

    def create_response_template(self):
        """Create a new response template"""
        dialog = tk.Toplevel(self.root)
        dialog.title("➕ Create Response Template")
        dialog.geometry("600x550")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text="➕ Create Response Template", style='Heading.TLabel').pack(pady=(0, 20))

        # Name
        ttk.Label(form_frame, text="Template Name:").pack(anchor="w")
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, width=50).pack(fill="x", pady=(5, 10))

        # Subject
        ttk.Label(form_frame, text="Subject:").pack(anchor="w")
        subject_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=subject_var, width=50).pack(fill="x", pady=(5, 10))

        # Category
        ttk.Label(form_frame, text="Category (optional):").pack(anchor="w")
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, values=SUPPORT_CATEGORIES, state="readonly", width=47)
        category_combo.pack(fill="x", pady=(5, 10))

        # Content
        ttk.Label(form_frame, text="Content:").pack(anchor="w")
        ttk.Label(form_frame, text="Use variables: {student_name}, {ticket_id}, {ticket_title}",
                 font=('Segoe UI', 8), foreground='gray').pack(anchor="w")
        content_text = scrolledtext.ScrolledText(form_frame, height=10, width=50)
        content_text.pack(fill="both", expand=True, pady=(5, 10))

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        def save_template():
            name = name_var.get().strip()
            subject = subject_var.get().strip()
            category = category_var.get() or None
            content = content_text.get("1.0", tk.END).strip()

            if not all([name, subject, content]):
                messagebox.showerror("Error", "Name, subject, and content are required")
                return

            try:
                template_id = self.support.create_response_template(
                    name, subject, content, category, ['student_name', 'ticket_id', 'ticket_title']
                )
                messagebox.showinfo("Success", f"Response template created successfully (ID: {template_id})")
                dialog.destroy()
                self.refresh_response_templates()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create template: {e}")

        ttk.Button(btn_frame, text="💾 Save", command=save_template).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy).pack(side="left")

    def edit_response_template(self):
        """Edit selected response template"""
        selection = self.response_templates_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a template to edit")
            return

        item = self.response_templates_tree.item(selection[0])
        template_id = item['values'][0]

        # Load template data
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM response_templates WHERE template_id = ?', (template_id,))
            template = cursor.fetchone()
            conn.close()

            if not template:
                messagebox.showerror("Error", "Template not found")
                return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load template: {e}")
            return

        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"✏️ Edit Response Template #{template_id}")
        dialog.geometry("600x550")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text=f"✏️ Edit Response Template #{template_id}", style='Heading.TLabel').pack(pady=(0, 20))

        # Name
        ttk.Label(form_frame, text="Template Name:").pack(anchor="w")
        name_var = tk.StringVar(value=template['name'])
        ttk.Entry(form_frame, textvariable=name_var, width=50).pack(fill="x", pady=(5, 10))

        # Subject
        ttk.Label(form_frame, text="Subject:").pack(anchor="w")
        subject_var = tk.StringVar(value=template['subject'])
        ttk.Entry(form_frame, textvariable=subject_var, width=50).pack(fill="x", pady=(5, 10))

        # Category
        ttk.Label(form_frame, text="Category (optional):").pack(anchor="w")
        category_var = tk.StringVar(value=template['category'] or '')
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, values=SUPPORT_CATEGORIES, state="readonly", width=47)
        category_combo.pack(fill="x", pady=(5, 10))

        # Content
        ttk.Label(form_frame, text="Content:").pack(anchor="w")
        content_text = scrolledtext.ScrolledText(form_frame, height=10, width=50)
        content_text.insert("1.0", template['content'])
        content_text.pack(fill="both", expand=True, pady=(5, 10))

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        def save_changes():
            name = name_var.get().strip()
            subject = subject_var.get().strip()
            category = category_var.get() or None
            content = content_text.get("1.0", tk.END).strip()

            if not all([name, subject, content]):
                messagebox.showerror("Error", "Name, subject, and content are required")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE response_templates
                    SET name = ?, subject = ?, content = ?, category = ?
                    WHERE template_id = ?
                ''', (name, subject, content, category, template_id))
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Template updated successfully")
                dialog.destroy()
                self.refresh_response_templates()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update template: {e}")

        ttk.Button(btn_frame, text="💾 Save Changes", command=save_changes).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy).pack(side="left")

    def delete_response_template(self):
        """Delete selected response template"""
        selection = self.response_templates_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a template to delete")
            return

        item = self.response_templates_tree.item(selection[0])
        template_id = item['values'][0]
        template_name = item['values'][1]

        if not messagebox.askyesno("Confirm Delete",
                                   f"Are you sure you want to delete template '{template_name}'?\n\nThis action cannot be undone."):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('DELETE FROM response_templates WHERE template_id = ?', (template_id,))
            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Template deleted successfully")
            self.refresh_response_templates()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete template: {e}")
    
    def show_manage_kb(self):
        """Show knowledge base management interface (staff only)"""
        self.clear_content()

        kb_mgmt_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(kb_mgmt_frame, text="📖 Manage KB")

        # Check permissions
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] not in ('staff', 'admin'):
            ttk.Label(kb_mgmt_frame, text="❌ Staff access required",
                     style='Title.TLabel').pack(pady=20)
            return

        ttk.Label(kb_mgmt_frame, text="📖 Knowledge Base Management",
                 style='Title.TLabel').pack(pady=(0, 20))

        # Knowledge base management UI
        kb_controls = ttk.Frame(kb_mgmt_frame)
        kb_controls.pack(fill=tk.X, pady=10)

        ttk.Button(kb_controls, text="➕ Add Article", command=self.add_kb_article).pack(side=tk.LEFT, padx=5)
        ttk.Button(kb_controls, text="✏️ Edit Article", command=self.edit_kb_article).pack(side=tk.LEFT, padx=5)
        ttk.Button(kb_controls, text="📢 Publish Article", command=self.publish_kb_article).pack(side=tk.LEFT, padx=5)
        ttk.Button(kb_controls, text="🗑️ Delete Article", command=self.delete_kb_article).pack(side=tk.LEFT, padx=5)
        ttk.Button(kb_controls, text="🔄 Refresh", command=self.refresh_kb_articles).pack(side=tk.LEFT, padx=5)

        # Search and filter frame
        search_frame = ttk.Frame(kb_mgmt_frame)
        search_frame.pack(fill=tk.X, pady=10)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        self.kb_search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.kb_search_var, width=30).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="🔍 Search", command=self.search_kb_articles).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="🔄 Clear", command=self.clear_kb_search).pack(side=tk.LEFT, padx=5)

        # Show all toggle
        self.kb_show_all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(search_frame, text="Show Unpublished", variable=self.kb_show_all_var,
                       command=self.refresh_kb_articles).pack(side=tk.LEFT, padx=10)

        # KB articles list
        kb_list_frame = ttk.LabelFrame(kb_mgmt_frame, text="Knowledge Base Articles", padding=10)
        kb_list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        columns = ("ID", "Title", "Category", "Status", "Views", "Helpful", "Author", "Last Updated")
        self.kb_tree = ttk.Treeview(kb_list_frame, columns=columns, show="headings", height=12)

        # Configure columns
        self.kb_tree.column("ID", width=50)
        self.kb_tree.column("Title", width=250)
        self.kb_tree.column("Category", width=120)
        self.kb_tree.column("Status", width=100)
        self.kb_tree.column("Views", width=70)
        self.kb_tree.column("Helpful", width=70)
        self.kb_tree.column("Author", width=100)
        self.kb_tree.column("Last Updated", width=150)

        for col in columns:
            self.kb_tree.heading(col, text=col)

        # Double-click to view
        self.kb_tree.bind('<Double-1>', lambda e: self.view_kb_article_details())

        scrollbar = ttk.Scrollbar(kb_list_frame, orient=tk.VERTICAL, command=self.kb_tree.yview)
        self.kb_tree.configure(yscrollcommand=scrollbar.set)
        self.kb_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load articles
        self.refresh_kb_articles()

    def refresh_kb_articles(self):
        """Refresh KB articles list"""
        try:
            # Clear existing items
            for item in self.kb_tree.get_children():
                self.kb_tree.delete(item)

            # Load from database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build query based on filters
            show_unpublished = self.kb_show_all_var.get()
            if show_unpublished:
                query = 'SELECT * FROM kb_articles ORDER BY created_datetime DESC'
            else:
                query = 'SELECT * FROM kb_articles WHERE is_published = 1 ORDER BY created_datetime DESC'

            cursor.execute(query)
            articles = cursor.fetchall()
            conn.close()

            # Add to tree
            for article in articles:
                status = "Published" if article['is_published'] else "Draft"
                self.kb_tree.insert('', tk.END, values=(
                    article['article_id'],
                    article['title'],
                    article['category'],
                    status,
                    article['view_count'] or 0,
                    article['helpful_votes'] or 0,
                    article['author_id'],
                    article['created_datetime']
                ))

            self.update_status(f"Loaded {len(articles)} KB articles")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load KB articles: {e}")

    def search_kb_articles(self):
        """Search KB articles"""
        query = self.kb_search_var.get().strip()
        if not query:
            self.refresh_kb_articles()
            return

        try:
            # Clear existing items
            for item in self.kb_tree.get_children():
                self.kb_tree.delete(item)

            # Search in database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            search_query = f"%{query}%"
            show_unpublished = self.kb_show_all_var.get()

            if show_unpublished:
                cursor.execute('''
                    SELECT * FROM kb_articles
                    WHERE title LIKE ? OR content LIKE ? OR category LIKE ? OR search_keywords LIKE ?
                    ORDER BY created_datetime DESC
                ''', (search_query, search_query, search_query, search_query))
            else:
                cursor.execute('''
                    SELECT * FROM kb_articles
                    WHERE (title LIKE ? OR content LIKE ? OR category LIKE ? OR search_keywords LIKE ?)
                    AND is_published = 1
                    ORDER BY created_datetime DESC
                ''', (search_query, search_query, search_query, search_query))

            articles = cursor.fetchall()
            conn.close()

            # Add to tree
            for article in articles:
                status = "Published" if article['is_published'] else "Draft"
                self.kb_tree.insert('', tk.END, values=(
                    article['article_id'],
                    article['title'],
                    article['category'],
                    status,
                    article['view_count'] or 0,
                    article['helpful_votes'] or 0,
                    article['author_id'],
                    article['created_datetime']
                ))

            self.update_status(f"Found {len(articles)} articles matching '{query}'")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to search KB articles: {e}")

    def clear_kb_search(self):
        """Clear KB search"""
        self.kb_search_var.set('')
        self.refresh_kb_articles()

    def add_kb_article(self):
        """Create a new KB article"""
        dialog = tk.Toplevel(self.root)
        dialog.title("➕ Create KB Article")
        dialog.geometry("700x600")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text="➕ Create Knowledge Base Article", style='Heading.TLabel').pack(pady=(0, 20))

        # Title
        ttk.Label(form_frame, text="Title:").pack(anchor="w")
        title_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=title_var, width=60).pack(fill="x", pady=(5, 10))

        # Category
        ttk.Label(form_frame, text="Category:").pack(anchor="w")
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, values=SUPPORT_CATEGORIES, state="readonly", width=57)
        category_combo.pack(fill="x", pady=(5, 10))
        if SUPPORT_CATEGORIES:
            category_combo.current(0)

        # Summary
        ttk.Label(form_frame, text="Summary (optional):").pack(anchor="w")
        summary_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=summary_var, width=60).pack(fill="x", pady=(5, 10))

        # Tags
        ttk.Label(form_frame, text="Tags (comma-separated):").pack(anchor="w")
        tags_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=tags_var, width=60).pack(fill="x", pady=(5, 10))

        # Content
        ttk.Label(form_frame, text="Content:").pack(anchor="w")
        content_text = scrolledtext.ScrolledText(form_frame, height=12, width=60)
        content_text.pack(fill="both", expand=True, pady=(5, 10))

        # Publish immediately checkbox
        publish_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, text="Publish immediately", variable=publish_var).pack(anchor="w", pady=5)

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        def save_article():
            title = title_var.get().strip()
            category = category_var.get()
            summary = summary_var.get().strip() or None
            tags_str = tags_var.get().strip()
            tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else None
            content = content_text.get("1.0", tk.END).strip()
            is_published = publish_var.get()

            if not all([title, category, content]):
                messagebox.showerror("Error", "Title, category, and content are required")
                return

            try:
                article_id = self.support.create_kb_article(
                    title, content, category, summary, tags, is_published
                )
                status = "published" if is_published else "created as draft"
                messagebox.showinfo("Success", f"KB article {status} successfully (ID: {article_id})")
                dialog.destroy()
                self.refresh_kb_articles()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create article: {e}")

        ttk.Button(btn_frame, text="💾 Save", command=save_article).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy).pack(side="left")

    def edit_kb_article(self):
        """Edit selected KB article"""
        selection = self.kb_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an article to edit")
            return

        item = self.kb_tree.item(selection[0])
        article_id = item['values'][0]

        # Load article data
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM kb_articles WHERE article_id = ?', (article_id,))
            article = cursor.fetchone()
            conn.close()

            if not article:
                messagebox.showerror("Error", "Article not found")
                return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load article: {e}")
            return

        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"✏️ Edit KB Article #{article_id}")
        dialog.geometry("700x600")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text=f"✏️ Edit KB Article #{article_id}", style='Heading.TLabel').pack(pady=(0, 20))

        # Title
        ttk.Label(form_frame, text="Title:").pack(anchor="w")
        title_var = tk.StringVar(value=article['title'])
        ttk.Entry(form_frame, textvariable=title_var, width=60).pack(fill="x", pady=(5, 10))

        # Category
        ttk.Label(form_frame, text="Category:").pack(anchor="w")
        category_var = tk.StringVar(value=article['category'])
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, values=SUPPORT_CATEGORIES, state="readonly", width=57)
        category_combo.pack(fill="x", pady=(5, 10))

        # Summary
        ttk.Label(form_frame, text="Summary (optional):").pack(anchor="w")
        summary_var = tk.StringVar(value=article['summary'] or '')
        ttk.Entry(form_frame, textvariable=summary_var, width=60).pack(fill="x", pady=(5, 10))

        # Tags
        ttk.Label(form_frame, text="Tags (comma-separated):").pack(anchor="w")
        try:
            tags_list = json.loads(article['tags']) if article['tags'] else []
            tags_str = ', '.join(tags_list)
        except:
            tags_str = ''
        tags_var = tk.StringVar(value=tags_str)
        ttk.Entry(form_frame, textvariable=tags_var, width=60).pack(fill="x", pady=(5, 10))

        # Content
        ttk.Label(form_frame, text="Content:").pack(anchor="w")
        content_text = scrolledtext.ScrolledText(form_frame, height=12, width=60)
        content_text.insert("1.0", article['content'])
        content_text.pack(fill="both", expand=True, pady=(5, 10))

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        def save_changes():
            title = title_var.get().strip()
            category = category_var.get()
            summary = summary_var.get().strip() or None
            tags_str = tags_var.get().strip()
            tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []
            content = content_text.get("1.0", tk.END).strip()

            if not all([title, category, content]):
                messagebox.showerror("Error", "Title, category, and content are required")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE kb_articles
                    SET title = ?, content = ?, summary = ?, category = ?, tags = ?
                    WHERE article_id = ?
                ''', (title, content, summary, category, json.dumps(tags), article_id))
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Article updated successfully")
                dialog.destroy()
                self.refresh_kb_articles()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update article: {e}")

        ttk.Button(btn_frame, text="💾 Save Changes", command=save_changes).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy).pack(side="left")

    def publish_kb_article(self):
        """Publish selected KB article"""
        selection = self.kb_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an article to publish")
            return

        item = self.kb_tree.item(selection[0])
        article_id = item['values'][0]
        article_title = item['values'][1]
        status = item['values'][3]

        if status == "Published":
            messagebox.showinfo("Info", "This article is already published")
            return

        if not messagebox.askyesno("Confirm Publish",
                                   f"Publish article '{article_title}'?\n\nThis will make it visible to all users."):
            return

        try:
            self.support.publish_kb_article(article_id)
            messagebox.showinfo("Success", "Article published successfully")
            self.refresh_kb_articles()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to publish article: {e}")

    def delete_kb_article(self):
        """Delete selected KB article"""
        selection = self.kb_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an article to delete")
            return

        item = self.kb_tree.item(selection[0])
        article_id = item['values'][0]
        article_title = item['values'][1]

        if not messagebox.askyesno("Confirm Delete",
                                   f"Are you sure you want to delete article '{article_title}'?\n\nThis action cannot be undone."):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('DELETE FROM kb_articles WHERE article_id = ?', (article_id,))
            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Article deleted successfully")
            self.refresh_kb_articles()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete article: {e}")

    def view_kb_article_details(self):
        """View detailed information about a KB article"""
        selection = self.kb_tree.selection()
        if not selection:
            return

        item = self.kb_tree.item(selection[0])
        article_id = item['values'][0]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM kb_articles WHERE article_id = ?', (article_id,))
            article = cursor.fetchone()
            conn.close()

            if not article:
                messagebox.showerror("Error", "Article not found")
                return

            # Create detail window
            detail_window = tk.Toplevel(self.root)
            detail_window.title(f"📖 {article['title']}")
            detail_window.geometry("800x700")

            # Scrollable frame
            canvas = tk.Canvas(detail_window)
            scrollbar = ttk.Scrollbar(detail_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas, padding="20")

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Article details
            ttk.Label(scrollable_frame, text=article['title'], font=('Segoe UI', 16, 'bold')).pack(anchor="w", pady=(0, 10))

            # Metadata
            meta_frame = ttk.Frame(scrollable_frame)
            meta_frame.pack(fill="x", pady=(0, 20))

            ttk.Label(meta_frame, text=f"📁 Category: {article['category']}", font=('Segoe UI', 10)).pack(anchor="w")
            ttk.Label(meta_frame, text=f"📊 Status: {'Published' if article['is_published'] else 'Draft'}", font=('Segoe UI', 10)).pack(anchor="w")
            ttk.Label(meta_frame, text=f"👀 Views: {article['view_count'] or 0}", font=('Segoe UI', 10)).pack(anchor="w")
            ttk.Label(meta_frame, text=f"👍 Helpful Votes: {article['helpful_votes'] or 0}", font=('Segoe UI', 10)).pack(anchor="w")

            # Tags
            if article['tags']:
                try:
                    tags = json.loads(article['tags'])
                    if tags:
                        tags_text = ', '.join(tags)
                        ttk.Label(meta_frame, text=f"🏷️ Tags: {tags_text}", font=('Segoe UI', 10)).pack(anchor="w")
                except:
                    pass

            # Summary
            if article['summary']:
                ttk.Label(scrollable_frame, text="Summary:", font=('Segoe UI', 11, 'bold')).pack(anchor="w", pady=(10, 5))
                summary_text = tk.Text(scrollable_frame, wrap=tk.WORD, height=3, font=('Segoe UI', 10))
                summary_text.insert("1.0", article['summary'])
                summary_text.config(state='disabled')
                summary_text.pack(fill="x", pady=(0, 10))

            # Content
            ttk.Label(scrollable_frame, text="Content:", font=('Segoe UI', 11, 'bold')).pack(anchor="w", pady=(10, 5))
            content_text = tk.Text(scrollable_frame, wrap=tk.WORD, height=20, font=('Segoe UI', 10))
            content_text.insert("1.0", article['content'])
            content_text.config(state='disabled')
            content_text.pack(fill="both", expand=True)

            # Pack canvas and scrollbar
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load article details: {e}")
    
    def show_bulk_operations(self):
        """Show bulk operations interface (staff only)"""
        self.clear_content()

        bulk_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(bulk_frame, text="📦 Bulk Operations")

        # Check permissions
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] not in ('staff', 'admin'):
            ttk.Label(bulk_frame, text="❌ Staff access required",
                     style='Title.TLabel').pack(pady=20)
            return

        ttk.Label(bulk_frame, text="📦 Bulk Operations",
                 style='Title.TLabel').pack(pady=(0, 20))

        # Bulk operations UI
        bulk_notebook = ttk.Notebook(bulk_frame)
        bulk_notebook.pack(fill=tk.BOTH, expand=True, pady=10)

        # Bulk Assign Tab
        bulk_assign_frame = ttk.Frame(bulk_notebook, padding=10)
        bulk_notebook.add(bulk_assign_frame, text="👤 Bulk Assign")

        ttk.Label(bulk_assign_frame, text="Assign multiple tickets to a staff member", font=('Segoe UI', 11, 'bold')).pack(pady=10)

        # Ticket IDs
        ttk.Label(bulk_assign_frame, text="Ticket IDs (comma-separated):").pack(anchor='w', padx=10, pady=(10, 5))
        self.bulk_assign_tickets_var = tk.StringVar()
        ttk.Entry(bulk_assign_frame, textvariable=self.bulk_assign_tickets_var, width=60).pack(fill=tk.X, padx=10, pady=5)

        # Staff member
        ttk.Label(bulk_assign_frame, text="Assign To (username):").pack(anchor='w', padx=10, pady=(10, 5))
        self.bulk_assign_staff_var = tk.StringVar()
        ttk.Entry(bulk_assign_frame, textvariable=self.bulk_assign_staff_var, width=60).pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(bulk_assign_frame, text="📋 Assign Tickets", command=self.perform_bulk_assign).pack(pady=20)

        # Bulk Status Update Tab
        bulk_status_frame = ttk.Frame(bulk_notebook, padding=10)
        bulk_notebook.add(bulk_status_frame, text="📊 Bulk Status")

        ttk.Label(bulk_status_frame, text="Update status for multiple tickets", font=('Segoe UI', 11, 'bold')).pack(pady=10)

        # Ticket IDs
        ttk.Label(bulk_status_frame, text="Ticket IDs (comma-separated):").pack(anchor='w', padx=10, pady=(10, 5))
        self.bulk_status_tickets_var = tk.StringVar()
        ttk.Entry(bulk_status_frame, textvariable=self.bulk_status_tickets_var, width=60).pack(fill=tk.X, padx=10, pady=5)

        # Status
        ttk.Label(bulk_status_frame, text="New Status:").pack(anchor='w', padx=10, pady=(10, 5))
        self.bulk_status_var = tk.StringVar()
        status_combo = ttk.Combobox(bulk_status_frame, textvariable=self.bulk_status_var, values=TICKET_STATUSES, state="readonly", width=57)
        status_combo.pack(fill=tk.X, padx=10, pady=5)
        if TICKET_STATUSES:
            status_combo.current(0)

        ttk.Button(bulk_status_frame, text="🔄 Update Status", command=self.perform_bulk_status_update).pack(pady=20)

        # Bulk Priority Update Tab
        bulk_priority_frame = ttk.Frame(bulk_notebook, padding=10)
        bulk_notebook.add(bulk_priority_frame, text="⚡ Bulk Priority")

        ttk.Label(bulk_priority_frame, text="Update priority for multiple tickets", font=('Segoe UI', 11, 'bold')).pack(pady=10)

        # Ticket IDs
        ttk.Label(bulk_priority_frame, text="Ticket IDs (comma-separated):").pack(anchor='w', padx=10, pady=(10, 5))
        self.bulk_priority_tickets_var = tk.StringVar()
        ttk.Entry(bulk_priority_frame, textvariable=self.bulk_priority_tickets_var, width=60).pack(fill=tk.X, padx=10, pady=5)

        # Priority
        ttk.Label(bulk_priority_frame, text="New Priority:").pack(anchor='w', padx=10, pady=(10, 5))
        self.bulk_priority_var = tk.StringVar()
        priority_combo = ttk.Combobox(bulk_priority_frame, textvariable=self.bulk_priority_var, values=TICKET_PRIORITIES, state="readonly", width=57)
        priority_combo.pack(fill=tk.X, padx=10, pady=5)
        if TICKET_PRIORITIES:
            priority_combo.current(0)

        ttk.Button(bulk_priority_frame, text="⚡ Update Priority", command=self.perform_bulk_priority_update).pack(pady=20)

        # Bulk Category Update Tab
        bulk_category_frame = ttk.Frame(bulk_notebook, padding=10)
        bulk_notebook.add(bulk_category_frame, text="📂 Bulk Category")

        ttk.Label(bulk_category_frame, text="Update category for multiple tickets", font=('Segoe UI', 11, 'bold')).pack(pady=10)

        # Ticket IDs
        ttk.Label(bulk_category_frame, text="Ticket IDs (comma-separated):").pack(anchor='w', padx=10, pady=(10, 5))
        self.bulk_category_tickets_var = tk.StringVar()
        ttk.Entry(bulk_category_frame, textvariable=self.bulk_category_tickets_var, width=60).pack(fill=tk.X, padx=10, pady=5)

        # Category
        ttk.Label(bulk_category_frame, text="New Category:").pack(anchor='w', padx=10, pady=(10, 5))
        self.bulk_category_var = tk.StringVar()
        category_combo = ttk.Combobox(bulk_category_frame, textvariable=self.bulk_category_var, values=SUPPORT_CATEGORIES, state="readonly", width=57)
        category_combo.pack(fill=tk.X, padx=10, pady=5)
        if SUPPORT_CATEGORIES:
            category_combo.current(0)

        ttk.Button(bulk_category_frame, text="📂 Update Category", command=self.perform_bulk_category_update).pack(pady=20)

    def perform_bulk_assign(self):
        """Perform bulk ticket assignment"""
        tickets_str = self.bulk_assign_tickets_var.get().strip()
        staff_username = self.bulk_assign_staff_var.get().strip()

        if not tickets_str or not staff_username:
            messagebox.showerror("Error", "Please provide ticket IDs and staff username")
            return

        try:
            # Parse ticket IDs
            ticket_ids = [int(tid.strip()) for tid in tickets_str.split(',')]

            if not messagebox.askyesno("Confirm Bulk Assign",
                                       f"Assign {len(ticket_ids)} tickets to {staff_username}?"):
                return

            # Perform bulk update
            updated_count = self.support.bulk_update_tickets(ticket_ids, {'assigned_to': staff_username})

            messagebox.showinfo("Success", f"Successfully assigned {updated_count} tickets to {staff_username}")
            self.bulk_assign_tickets_var.set('')
            self.bulk_assign_staff_var.set('')

        except ValueError:
            messagebox.showerror("Error", "Invalid ticket IDs. Please use comma-separated numbers.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to perform bulk assign: {e}")

    def perform_bulk_status_update(self):
        """Perform bulk status update"""
        tickets_str = self.bulk_status_tickets_var.get().strip()
        new_status = self.bulk_status_var.get()

        if not tickets_str or not new_status:
            messagebox.showerror("Error", "Please provide ticket IDs and status")
            return

        try:
            # Parse ticket IDs
            ticket_ids = [int(tid.strip()) for tid in tickets_str.split(',')]

            if not messagebox.askyesno("Confirm Bulk Update",
                                       f"Update status to '{new_status}' for {len(ticket_ids)} tickets?"):
                return

            # Perform bulk update
            updated_count = self.support.bulk_update_tickets(ticket_ids, {'status': new_status})

            messagebox.showinfo("Success", f"Successfully updated status for {updated_count} tickets")
            self.bulk_status_tickets_var.set('')

        except ValueError:
            messagebox.showerror("Error", "Invalid ticket IDs. Please use comma-separated numbers.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to perform bulk status update: {e}")

    def perform_bulk_priority_update(self):
        """Perform bulk priority update"""
        tickets_str = self.bulk_priority_tickets_var.get().strip()
        new_priority = self.bulk_priority_var.get()

        if not tickets_str or not new_priority:
            messagebox.showerror("Error", "Please provide ticket IDs and priority")
            return

        try:
            # Parse ticket IDs
            ticket_ids = [int(tid.strip()) for tid in tickets_str.split(',')]

            if not messagebox.askyesno("Confirm Bulk Update",
                                       f"Update priority to '{new_priority}' for {len(ticket_ids)} tickets?"):
                return

            # Perform bulk update
            updated_count = self.support.bulk_update_tickets(ticket_ids, {'priority': new_priority})

            messagebox.showinfo("Success", f"Successfully updated priority for {updated_count} tickets")
            self.bulk_priority_tickets_var.set('')

        except ValueError:
            messagebox.showerror("Error", "Invalid ticket IDs. Please use comma-separated numbers.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to perform bulk priority update: {e}")

    def perform_bulk_category_update(self):
        """Perform bulk category update"""
        tickets_str = self.bulk_category_tickets_var.get().strip()
        new_category = self.bulk_category_var.get()

        if not tickets_str or not new_category:
            messagebox.showerror("Error", "Please provide ticket IDs and category")
            return

        try:
            # Parse ticket IDs
            ticket_ids = [int(tid.strip()) for tid in tickets_str.split(',')]

            if not messagebox.askyesno("Confirm Bulk Update",
                                       f"Update category to '{new_category}' for {len(ticket_ids)} tickets?"):
                return

            # Perform bulk update
            updated_count = self.support.bulk_update_tickets(ticket_ids, {'category': new_category})

            messagebox.showinfo("Success", f"Successfully updated category for {updated_count} tickets")
            self.bulk_category_tickets_var.set('')

        except ValueError:
            messagebox.showerror("Error", "Invalid ticket IDs. Please use comma-separated numbers.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to perform bulk category update: {e}")
    
    def show_export_dialog(self):
        """Show data export dialog with advanced filters"""
        export_dialog = tk.Toplevel(self.root)
        export_dialog.title("📤 Export Data")
        export_dialog.geometry("500x650")
        export_dialog.transient(self.root)
        export_dialog.grab_set()

        # Scrollable frame
        canvas = tk.Canvas(export_dialog)
        scrollbar = ttk.Scrollbar(export_dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, padding="20")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        ttk.Label(scrollable_frame, text="📤 Export Data", style='Heading.TLabel').pack(pady=(0, 20))

        # Export type
        ttk.Label(scrollable_frame, text="Export Type:").pack(anchor="w")
        export_type_var = tk.StringVar(value="tickets")

        export_options = [
            ("🎫 Tickets", "tickets"),
            ("💬 Responses", "responses"),
            ("📊 Metrics", "metrics")
        ]

        for text, value in export_options:
            ttk.Radiobutton(scrollable_frame, text=text, variable=export_type_var,
                           value=value).pack(anchor="w", pady=2)

        # Filters Section
        filters_frame = ttk.LabelFrame(scrollable_frame, text="Filters (Optional)", padding="10")
        filters_frame.pack(fill="x", pady=(20, 10))

        # Date Range Filters
        ttk.Label(filters_frame, text="Date From (YYYY-MM-DD):").pack(anchor="w")
        date_from_var = tk.StringVar()
        ttk.Entry(filters_frame, textvariable=date_from_var, width=40).pack(fill="x", pady=(5, 10))

        ttk.Label(filters_frame, text="Date To (YYYY-MM-DD):").pack(anchor="w")
        date_to_var = tk.StringVar()
        ttk.Entry(filters_frame, textvariable=date_to_var, width=40).pack(fill="x", pady=(5, 10))

        # Status Filter (for tickets)
        ttk.Label(filters_frame, text="Status (for tickets):").pack(anchor="w")
        status_var = tk.StringVar()
        status_combo = ttk.Combobox(filters_frame, textvariable=status_var,
                                    values=['All'] + TICKET_STATUSES, state="readonly", width=37)
        status_combo.set('All')
        status_combo.pack(fill="x", pady=(5, 10))

        # Category Filter (for tickets)
        ttk.Label(filters_frame, text="Category (for tickets):").pack(anchor="w")
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(filters_frame, textvariable=category_var,
                                      values=['All'] + SUPPORT_CATEGORIES, state="readonly", width=37)
        category_combo.set('All')
        category_combo.pack(fill="x", pady=(5, 10))

        # Priority Filter (for tickets)
        ttk.Label(filters_frame, text="Priority (for tickets):").pack(anchor="w")
        priority_var = tk.StringVar()
        priority_combo = ttk.Combobox(filters_frame, textvariable=priority_var,
                                      values=['All'] + TICKET_PRIORITIES, state="readonly", width=37)
        priority_combo.set('All')
        priority_combo.pack(fill="x", pady=(5, 10))

        # Format
        ttk.Label(scrollable_frame, text="Format:").pack(anchor="w", pady=(10, 5))
        format_var = tk.StringVar(value="csv")

        format_frame = ttk.Frame(scrollable_frame)
        format_frame.pack(anchor="w")

        ttk.Radiobutton(format_frame, text="CSV", variable=format_var,
                       value="csv").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(format_frame, text="JSON", variable=format_var,
                       value="json").pack(side="left")

        # Buttons
        btn_frame = ttk.Frame(scrollable_frame)
        btn_frame.pack(fill="x", pady=(20, 0))

        def start_export():
            export_type = export_type_var.get()
            format_type = format_var.get()

            # Build filters
            filters = {}

            date_from = date_from_var.get().strip()
            if date_from:
                filters['date_from'] = date_from

            date_to = date_to_var.get().strip()
            if date_to:
                filters['date_to'] = date_to

            status = status_var.get()
            if status and status != 'All':
                filters['status'] = status

            category = category_var.get()
            if category and category != 'All':
                filters['category'] = category

            priority = priority_var.get()
            if priority and priority != 'All':
                filters['priority'] = priority

            export_dialog.destroy()
            self.perform_export(export_type, format_type, filters)

        ttk.Button(btn_frame, text="📤 Export", command=start_export,
                  style='Primary.TButton').pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=export_dialog.destroy).pack(side="left")

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def perform_export(self, export_type, format_type, filters=None):
        """Perform data export with optional filters"""
        try:
            # Get filename
            filename = filedialog.asksaveasfilename(
                title="Save Export",
                defaultextension=f".{format_type}",
                filetypes=[(f"{format_type.upper()} files", f"*.{format_type}"), ("All files", "*.*")]
            )

            if not filename:
                return

            self.update_status(f"Exporting {export_type} data...")

            # Export data with filters
            exported_data = self.support.export_data(export_type, filters or {}, format_type)

            with open(filename, 'w') as f:
                f.write(exported_data)

            filter_info = f" with {len(filters)} filter(s)" if filters else ""
            messagebox.showinfo("Export Complete", f"Data exported to {filename}{filter_info}")
            self.update_status("Export completed")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export data: {e}")
            self.update_status("Export failed")
    
    def refresh_data(self):
        """Refresh all data"""
        try:
            self.update_status("Refreshing data...")
            
            # Reload dashboard data
            self.load_dashboard()
            
            # Refresh current view
            current_tab = self.notebook.tab(self.notebook.select(), "text")
            
            if "Dashboard" in current_tab:
                self.show_dashboard()
            elif "My Tickets" in current_tab:
                if hasattr(self, 'refresh_my_tickets'):
                    self.refresh_my_tickets()
            elif "All Tickets" in current_tab:
                if hasattr(self, 'refresh_all_tickets'):
                    self.refresh_all_tickets()
            elif "FAQs" in current_tab:
                if hasattr(self, 'load_faqs'):
                    self.load_faqs()
            elif "Knowledge Base" in current_tab:
                if hasattr(self, 'load_knowledge_base'):
                    self.load_knowledge_base()
            elif "Notifications" in current_tab:
                if hasattr(self, 'load_notifications'):
                    self.load_notifications()
            
            self.update_status("Data refreshed")
            
        except Exception as e:
            self.update_status(f"Refresh failed: {e}")

    def update_status(self, message):
        """Update status bar message"""
        try:
            if hasattr(self, 'status_var') and self.status_var:
                self.status_var.set(message)
                self.root.update_idletasks()
        except Exception:
            # If status_var doesn't exist yet, just ignore the update
            pass

    def escalate_ticket(self, ticket_id):
        """Escalate a ticket"""
        try:
            # Update ticket status to escalated
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            escalation_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            UPDATE support_tickets 
            SET status = 'Escalated', escalated_at = ?, last_updated_datetime = ?
            WHERE ticket_id = ?
            ''', (escalation_time, escalation_time, ticket_id))
            
            # Add escalation response
            cursor.execute('''
            INSERT INTO ticket_responses (
                ticket_id, responder_id, responder_role, response_text,
                response_datetime, is_auto_generated
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                ticket_id, auth.current_user['id'], auth.current_user['role'],
                f'Ticket escalated to supervisor by {auth.current_user["username"]}',
                escalation_time, 1
            ))
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", f"Ticket #{ticket_id} escalated successfully!")
            self.refresh_data()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not escalate ticket: {e}")

    def show_merge_dialog(self, ticket):
        """Show dialog to merge tickets"""
        merge_dialog = tk.Toplevel(self.root)
        merge_dialog.title("Merge Tickets")
        merge_dialog.geometry("400x300")
        merge_dialog.transient(self.root)
        merge_dialog.grab_set()
        
        form_frame = ttk.Frame(merge_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)
        
        ttk.Label(form_frame, text=f"Merge into Ticket #{ticket['ticket_id']}", 
                 style='Heading.TLabel').pack(pady=(0, 15))
        
        ttk.Label(form_frame, text="Secondary ticket IDs (comma-separated):").pack(anchor="w")
        secondary_ids_entry = ttk.Entry(form_frame, width=40)
        secondary_ids_entry.pack(fill="x", pady=(5, 10))
        
        ttk.Label(form_frame, text="Merge reason:").pack(anchor="w")
        reason_text = scrolledtext.ScrolledText(form_frame, height=4, wrap=tk.WORD)
        reason_text.pack(fill="both", expand=True, pady=(5, 15))
        
        def perform_merge():
            secondary_ids = secondary_ids_entry.get().strip()
            reason = reason_text.get(1.0, tk.END).strip()
            
            if not secondary_ids or not reason:
                messagebox.showerror("Error", "Please provide secondary ticket IDs and reason")
                return
            
            try:
                ids = [int(id.strip()) for id in secondary_ids.split(',')]
                self.support.merge_tickets(ticket['ticket_id'], ids, reason)
                messagebox.showinfo("Success", "Tickets merged successfully!")
                merge_dialog.destroy()
                self.refresh_data()
            except Exception as e:
                messagebox.showerror("Error", f"Could not merge tickets: {e}")
        
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x")
        
        ttk.Button(btn_frame, text="Merge Tickets", command=perform_merge).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=merge_dialog.destroy).pack(side="left")

    def export_ticket(self, ticket):
        """Export individual ticket data"""
        try:
            filename = filedialog.asksaveasfilename(
                title="Export Ticket",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("Text files", "*.txt")]
            )
            
            if not filename:
                return
            
            # Get full ticket details
            ticket_details = self.support.get_ticket_details(ticket['ticket_id'])
            
            if filename.endswith('.json'):
                with open(filename, 'w') as f:
                    json.dump(ticket_details, f, indent=2, default=str)
            else:
                # Export as formatted text
                with open(filename, 'w') as f:
                    f.write(f"Ticket #{ticket_details['ticket_id']}\n")
                    f.write("=" * 50 + "\n")
                    f.write(f"Title: {ticket_details['title']}\n")
                    f.write(f"Student: {ticket_details['student_id']}\n")
                    f.write(f"Status: {ticket_details['status']}\n")
                    f.write(f"Priority: {ticket_details['priority']}\n")
                    f.write(f"Category: {ticket_details['category']}\n")
                    f.write(f"Created: {ticket_details['created_datetime']}\n")
                    f.write(f"\nDescription:\n{ticket_details['description']}\n")
                    
                    if ticket_details.get('responses'):
                        f.write(f"\nResponses:\n")
                        for response in ticket_details['responses']:
                            f.write(f"\n[{response['response_datetime']}] {response['responder_role']}:\n")
                            f.write(f"{response['response_text']}\n")
            
            messagebox.showinfo("Success", f"Ticket exported to {filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not export ticket: {e}")

    def show_ticket_history(self, ticket_id):
        """Show complete ticket history in a new window"""
        try:
            history = self.support.get_ticket_history(ticket_id)
            
            history_window = tk.Toplevel(self.root)
            history_window.title(f"Ticket #{ticket_id} History")
            history_window.geometry("1000x700")
            history_window.transient(self.root)
            
            # Create scrollable timeline
            canvas = tk.Canvas(history_window)
            scrollbar = ttk.Scrollbar(history_window, orient="vertical", command=canvas.yview)
            timeline_frame = ttk.Frame(canvas)
            
            timeline_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=timeline_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Title
            title_frame = ttk.Frame(timeline_frame, padding="10")
            title_frame.pack(fill="x")
            
            ttk.Label(title_frame, text=f"Complete History for Ticket #{ticket_id}", 
                     style='Title.TLabel').pack()
            
            # Timeline events
            timeline = history['timeline']
            for event in timeline:
                event_frame = ttk.LabelFrame(timeline_frame, padding="10")
                event_frame.pack(fill="x", padx=10, pady=5)
                
                event_type = event['type']
                data = event['data']
                
                if event_type == 'creation':
                    event_frame.config(text=f"Created - {event['datetime']}")
                    ttk.Label(event_frame, text=f"Title: {data['title']}").pack(anchor="w")
                    ttk.Label(event_frame, text=f"Description: {data['description'][:100]}...").pack(anchor="w")
                    
                elif event_type == 'response':
                    responder = data['responder_role']
                    is_internal = data.get('is_internal', False)
                    is_auto = data.get('is_auto_generated', False)
                    
                    tags = []
                    if is_internal:
                        tags.append("INTERNAL")
                    if is_auto:
                        tags.append("AUTO")
                    
                    tag_text = f" [{', '.join(tags)}]" if tags else ""
                    event_frame.config(text=f"Response by {responder}{tag_text} - {event['datetime']}")
                    
                    ttk.Label(event_frame, text=data['response_text'][:150] + "...").pack(anchor="w")
                    
                elif event_type == 'attachment':
                    event_frame.config(text=f"Attachment Added - {event['datetime']}")
                    ttk.Label(event_frame, text=f"File: {data['original_filename']}").pack(anchor="w")
                    
                elif event_type == 'audit':
                    event_frame.config(text=f"System Event - {event['datetime']}")
                    ttk.Label(event_frame, text=f"Action: {data['action']}").pack(anchor="w")
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not load ticket history: {e}")

    def show_add_internal_note_dialog(self, ticket):
        """Show dialog to add internal note"""
        note_dialog = tk.Toplevel(self.root)
        note_dialog.title(f"Add Internal Note - Ticket #{ticket['ticket_id']}")
        note_dialog.geometry("700x450")
        note_dialog.transient(self.root)
        note_dialog.grab_set()
        
        form_frame = ttk.Frame(note_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)
        
        ttk.Label(form_frame, text="Internal Note (Staff Only)", 
                 style='Heading.TLabel').pack(pady=(0, 15))
        
        note_text = scrolledtext.ScrolledText(form_frame, height=8, wrap=tk.WORD)
        note_text.pack(fill="both", expand=True, pady=(0, 15))
        
        def add_note():
            text = note_text.get(1.0, tk.END).strip()
            if not text:
                messagebox.showerror("Error", "Note cannot be empty")
                return
            
            try:
                self.support.add_ticket_response(ticket['ticket_id'], text, is_internal=True)
                messagebox.showinfo("Success", "Internal note added successfully!")
                note_dialog.destroy()
                self.refresh_data()
            except Exception as e:
                messagebox.showerror("Error", f"Could not add note: {e}")
        
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x")
        
        ttk.Button(btn_frame, text="Add Note", command=add_note).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=note_dialog.destroy).pack(side="left")

    def show_response_template_dialog(self, ticket):
        """Show dialog to use response template"""
        template_dialog = tk.Toplevel(self.root)
        template_dialog.title("Use Response Template")
        template_dialog.geometry("800x600")
        template_dialog.transient(self.root)
        template_dialog.grab_set()
        
        form_frame = ttk.Frame(template_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)
        
        ttk.Label(form_frame, text="Select Response Template", 
                 style='Heading.TLabel').pack(pady=(0, 15))
        
        # Get templates
        templates = self.support.get_response_templates()
        
        if not templates:
            ttk.Label(form_frame, text="No response templates available").pack()
            ttk.Button(form_frame, text="Close", command=template_dialog.destroy).pack(pady=10)
            return
        
        # Template selection
        template_frame = ttk.LabelFrame(form_frame, text="Templates", padding="10")
        template_frame.pack(fill="x", pady=(0, 10))
        
        template_var = tk.StringVar()
        template_combo = ttk.Combobox(template_frame, textvariable=template_var, state="readonly")
        template_combo['values'] = [f"{t['name']} - {t.get('category', 'General')}" for t in templates]
        template_combo.pack(fill="x")
        
        # Preview area
        preview_frame = ttk.LabelFrame(form_frame, text="Preview", padding="10")
        preview_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        preview_text = scrolledtext.ScrolledText(preview_frame, height=8, wrap=tk.WORD, state='disabled')
        preview_text.pack(fill="both", expand=True)
        
        def update_preview(event=None):
            selection = template_combo.current()
            if selection >= 0:
                template = templates[selection]
                preview_text.config(state='normal')
                preview_text.delete(1.0, tk.END)
                preview_text.insert(1.0, template['content'])
                preview_text.config(state='disabled')
        
        template_combo.bind('<<ComboboxSelected>>', update_preview)
        
        def use_template():
            selection = template_combo.current()
            if selection < 0:
                messagebox.showerror("Error", "Please select a template")
                return
            
            template = templates[selection]
            template_dialog.destroy()
            
            # Show add response dialog with template pre-filled
            self.show_add_response_dialog_with_template(ticket, template)
        
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x")
        
        ttk.Button(btn_frame, text="Use Template", command=use_template).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=template_dialog.destroy).pack(side="left")

    def show_add_response_dialog_with_template(self, ticket, template):
        """Show add response dialog with template pre-filled"""
        response_dialog = tk.Toplevel(self.root)
        response_dialog.title(f"Add Response - Ticket #{ticket['ticket_id']}")
        response_dialog.geometry("800x600")
        response_dialog.transient(self.root)
        response_dialog.grab_set()
        
        form_frame = ttk.Frame(response_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)
        
        ttk.Label(form_frame, text=f"Using template: {template['name']}", 
                 style='Heading.TLabel').pack(anchor="w", pady=(0, 15))
        
        # Response text with template content
        ttk.Label(form_frame, text="Response:").pack(anchor="w")
        response_text = scrolledtext.ScrolledText(form_frame, height=12, wrap=tk.WORD)
        response_text.pack(fill="both", expand=True, pady=(5, 15))
        response_text.insert(1.0, template['content'])
        
        # Options
        options_frame = ttk.Frame(form_frame)
        options_frame.pack(fill="x", pady=(0, 15))
        
        if auth.current_user['role'] in ('staff', 'admin'):
            self.is_internal_var = tk.BooleanVar()
            ttk.Checkbutton(options_frame, text="Internal note (staff only)", 
                           variable=self.is_internal_var).pack(side="left")
        
        def submit_response():
            text = response_text.get(1.0, tk.END).strip()
            if not text:
                messagebox.showerror("Error", "Response cannot be empty")
                return
            
            try:
                is_internal = getattr(self, 'is_internal_var', tk.BooleanVar()).get()
                self.support.add_ticket_response(
                    ticket['ticket_id'], text, 
                    template_id=template['template_id'], 
                    is_internal=is_internal
                )
                messagebox.showinfo("Success", "Response added successfully!")
                response_dialog.destroy()
                self.refresh_data()
            except Exception as e:
                messagebox.showerror("Error", f"Could not add response: {e}")
        
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x")
        
        ttk.Button(btn_frame, text="Add Response", command=submit_response).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=response_dialog.destroy).pack(side="left")

    def show_status_update_dialog(self, ticket_id):
        """Show dialog to update ticket status"""
        status_dialog = tk.Toplevel(self.root)
        status_dialog.title(f"Update Status - Ticket #{ticket_id}")
        status_dialog.geometry("400x250")
        status_dialog.transient(self.root)
        status_dialog.grab_set()
        
        form_frame = ttk.Frame(status_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)
        
        ttk.Label(form_frame, text="Update Ticket Status", 
                 style='Heading.TLabel').pack(pady=(0, 15))
        
        # Status selection
        ttk.Label(form_frame, text="New Status:").pack(anchor="w")
        status_var = tk.StringVar()
        status_combo = ttk.Combobox(form_frame, textvariable=status_var, 
                                   values=TICKET_STATUSES, state="readonly")
        status_combo.pack(fill="x", pady=(5, 10))
        
        # Resolution notes
        ttk.Label(form_frame, text="Resolution Notes (optional):").pack(anchor="w")
        notes_text = scrolledtext.ScrolledText(form_frame, height=4, wrap=tk.WORD)
        notes_text.pack(fill="both", expand=True, pady=(5, 15))
        
        def update_status():
            new_status = status_var.get()
            if not new_status:
                messagebox.showerror("Error", "Please select a status")
                return
            
            notes = notes_text.get(1.0, tk.END).strip() or None
            
            try:
                self.support.update_ticket_status(ticket_id, new_status, notes)
                messagebox.showinfo("Success", f"Status updated to {new_status}")
                status_dialog.destroy()
                self.refresh_data()
            except Exception as e:
                messagebox.showerror("Error", f"Could not update status: {e}")
        
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x")
        
        ttk.Button(btn_frame, text="Update Status", command=update_status).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=status_dialog.destroy).pack(side="left")

    def show_satisfaction_rating(self):
        """Show satisfaction rating dialog for resolved tickets"""
        if not auth or not auth.current_user or auth.current_user['role'] != 'student':
            messagebox.showerror("Error", "Only students can submit satisfaction ratings")
            return
        
        rating_dialog = tk.Toplevel(self.root)
        rating_dialog.title("Submit Satisfaction Rating")
        rating_dialog.geometry("700x550")
        rating_dialog.transient(self.root)
        rating_dialog.grab_set()
        
        form_frame = ttk.Frame(rating_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)
        
        ttk.Label(form_frame, text="Rate Your Support Experience", 
                 style='Title.TLabel').pack(pady=(0, 20))
        
        # Get resolved tickets for this student
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                messagebox.showerror("Error", "No student ID found")
                rating_dialog.destroy()
                return
            
            student_id = result[0]
            filters = {'status': 'Resolved'}
            result = self.support.get_student_tickets(student_id, filters, page=1, per_page=50)
            resolved_tickets = result['tickets']
            
            if not resolved_tickets:
                ttk.Label(form_frame, text="No resolved tickets to rate").pack()
                ttk.Button(form_frame, text="Close", command=rating_dialog.destroy).pack(pady=10)
                return
            
            # Ticket selection
            ttk.Label(form_frame, text="Select Ticket:").pack(anchor="w")
            ticket_var = tk.StringVar()
            ticket_combo = ttk.Combobox(form_frame, textvariable=ticket_var, state="readonly")
            ticket_combo['values'] = [f"#{t['ticket_id']} - {t['title']}" for t in resolved_tickets]
            ticket_combo.pack(fill="x", pady=(5, 10))
            
            # Rating
            ttk.Label(form_frame, text="Rating (1-5 stars):").pack(anchor="w")
            rating_var = tk.IntVar(value=5)
            rating_frame = ttk.Frame(form_frame)
            rating_frame.pack(anchor="w", pady=(5, 10))
            
            for i in range(1, 6):
                ttk.Radiobutton(rating_frame, text=f"{i} star{'s' if i > 1 else ''}", 
                               variable=rating_var, value=i).pack(side="left", padx=(0, 10))
            
            # Feedback
            ttk.Label(form_frame, text="Additional Feedback (optional):").pack(anchor="w")
            feedback_text = scrolledtext.ScrolledText(form_frame, height=6, wrap=tk.WORD)
            feedback_text.pack(fill="both", expand=True, pady=(5, 15))
            
            def submit_rating():
                selection = ticket_combo.current()
                if selection < 0:
                    messagebox.showerror("Error", "Please select a ticket")
                    return
                
                ticket = resolved_tickets[selection]
                rating = rating_var.get()
                feedback = feedback_text.get(1.0, tk.END).strip() or None
                
                try:
                    self.support.submit_satisfaction_rating(ticket['ticket_id'], rating, feedback)
                    messagebox.showinfo("Success", "Thank you for your feedback!")
                    rating_dialog.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Could not submit rating: {e}")
            
            btn_frame = ttk.Frame(form_frame)
            btn_frame.pack(fill="x")
            
            ttk.Button(btn_frame, text="Submit Rating", command=submit_rating).pack(side="left", padx=(0, 10))
            ttk.Button(btn_frame, text="Cancel", command=rating_dialog.destroy).pack(side="left")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not load tickets: {e}")
            rating_dialog.destroy()

    def show_export_data_dialog(self):
        """Show enhanced data export dialog"""
        if not auth or not auth.current_user or auth.current_user['role'] not in ('staff', 'admin'):
            messagebox.showerror("Error", "Staff access required")
            return
        
        export_dialog = tk.Toplevel(self.root)
        export_dialog.title("Export Data")
        export_dialog.geometry("700x550")
        export_dialog.transient(self.root)
        export_dialog.grab_set()
        
        form_frame = ttk.Frame(export_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)
        
        ttk.Label(form_frame, text="Export Data", style='Title.TLabel').pack(pady=(0, 20))
        
        # Export type
        ttk.Label(form_frame, text="Export Type:").pack(anchor="w")
        export_type_var = tk.StringVar(value="tickets")
        
        export_options = [
            ("Tickets", "tickets"),
            ("Responses", "responses"), 
            ("Metrics", "metrics"),
            ("User Data", "users"),
            ("System Logs", "logs")
        ]
        
        for text, value in export_options:
            ttk.Radiobutton(form_frame, text=text, variable=export_type_var, 
                           value=value).pack(anchor="w", pady=2)
        
        # Date range
        date_frame = ttk.LabelFrame(form_frame, text="Date Range (Optional)", padding="10")
        date_frame.pack(fill="x", pady=(10, 0))
        
        ttk.Label(date_frame, text="From:").grid(row=0, column=0, sticky="w")
        from_date = ttk.Entry(date_frame, width=12)
        from_date.grid(row=0, column=1, padx=(5, 10))
        from_date.insert(0, (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d'))
        
        ttk.Label(date_frame, text="To:").grid(row=0, column=2, sticky="w") 
        to_date = ttk.Entry(date_frame, width=12)
        to_date.grid(row=0, column=3, padx=(5, 0))
        to_date.insert(0, datetime.datetime.now().strftime('%Y-%m-%d'))
        
        # Format
        format_frame = ttk.LabelFrame(form_frame, text="Format", padding="10")
        format_frame.pack(fill="x", pady=(10, 0))
        
        format_var = tk.StringVar(value="csv")
        ttk.Radiobutton(format_frame, text="CSV", variable=format_var, value="csv").pack(side="left")
        ttk.Radiobutton(format_frame, text="JSON", variable=format_var, value="json").pack(side="left", padx=(10, 0))
        ttk.Radiobutton(format_frame, text="Excel", variable=format_var, value="xlsx").pack(side="left", padx=(10, 0))
        
        def start_export():
            export_type = export_type_var.get()
            format_type = format_var.get()
            date_from = from_date.get().strip() or None
            date_to = to_date.get().strip() or None
            
            filters = {}
            if date_from:
                filters['date_from'] = date_from
            if date_to:
                filters['date_to'] = date_to
            
            export_dialog.destroy()
            self.perform_enhanced_export(export_type, filters, format_type)
        
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x", pady=(20, 0))
        
        ttk.Button(btn_frame, text="Export", command=start_export).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=export_dialog.destroy).pack(side="left")

    def show_user_management(self):
        """Show user management interface (admin only)"""
        if not auth or not auth.current_user or auth.current_user['role'] != 'admin':
            messagebox.showerror("Error", "Admin access required")
            return
        
        self.clear_content()
        
        user_mgmt_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(user_mgmt_frame, text="User Management")
        
        ttk.Label(user_mgmt_frame, text="User Management", 
                 style='Title.TLabel').pack(pady=(0, 20))
        
        # User list
        users_frame = ttk.LabelFrame(user_mgmt_frame, text="System Users", padding="10")
        users_frame.pack(fill="both", expand=True)
        
        # Create treeview for users
        columns = ('ID', 'Username', 'Role', 'Student ID', 'Status', 'Last Login')
        user_tree = ttk.Treeview(users_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            user_tree.heading(col, text=col)
            user_tree.column(col, width=100)
        
        # Load users
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, role, student_id FROM users ORDER BY username')
            users = cursor.fetchall()
            conn.close()
            
            for user in users:
                user_tree.insert('', 'end', values=(
                    user[0], user[1], user[2], user[3] or 'N/A', 'Active', 'N/A'
                ))
        except Exception as e:
            ttk.Label(users_frame, text=f"Error loading users: {e}").pack()
        
        user_tree.pack(fill="both", expand=True, pady=(0, 10))
        
        # User actions
        actions_frame = ttk.Frame(users_frame)
        actions_frame.pack(fill="x")
        
        ttk.Button(actions_frame, text="Reset Password", 
                  command=lambda: self.reset_user_password(user_tree)).pack(side="left", padx=(0, 5))
        ttk.Button(actions_frame, text="Change Role", 
                  command=lambda: self.change_user_role(user_tree)).pack(side="left", padx=(0, 5))
        ttk.Button(actions_frame, text="Deactivate User", 
                  command=lambda: self.deactivate_user(user_tree)).pack(side="left")

    def reset_user_password(self, user_tree):
        """Reset user password"""
        selection = user_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a user")
            return
        
        user_data = user_tree.item(selection[0])['values']
        username = user_data[1]
        user_id, admin_username = self._get_current_user_identity()
        permissions = self.auth.current_user.get('permissions', []) if self.auth and self.auth.current_user else []
        
        if self.auth and self.auth.current_user:
            if 'manage_users' not in permissions and self.auth.current_user['username'] != admin_username:
                messagebox.showerror("Permission Denied", "You do not have permission to reset passwords.")
                return
        else:
            messagebox.showerror("Error", "Authentication required to reset passwords.")
            return
        
        if messagebox.askyesno("Confirm", f"Reset password for user '{username}'?"):
            try:
                if not hasattr(self.auth, '_generate_temp_password') or not hasattr(self.auth, '_hash_password'):
                    raise RuntimeError("Authentication system does not support password resets.")

                temp_password = self.auth._generate_temp_password()
                salt, password_hash = self.auth._hash_password(temp_password)
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                conn = sqlite3.connect(self.auth.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id FROM user_accounts WHERE username = ?',
                    (username,)
                )
                row = cursor.fetchone()
                if not row:
                    conn.close()
                    messagebox.showerror("Error", f"User account for '{username}' not found.")
                    return

                account_id = row[0]
                cursor.execute(
                    '''
                    UPDATE user_accounts
                    SET password_hash = ?, salt = ?, updated_at = ?, password_reset_required = 1
                    WHERE id = ?
                    ''',
                    (password_hash, salt, timestamp, account_id)
                )
                conn.commit()
                conn.close()

                if hasattr(self.auth, '_log_activity'):
                    self.auth._log_activity(
                        self.auth.current_user['username'],
                        f"Password reset for user: {username}",
                        user_id=self.auth.current_user.get('id')
                    )

                messagebox.showinfo(
                    "Success",
                    f"Password reset for {username}.\nTemporary password: {temp_password}\nThe user will be prompted to change it on next login."
                )
            except Exception as e:
                messagebox.showerror("Error", f"Could not reset password: {e}")

    def change_user_role(self, user_tree):
        """Change user role"""
        selection = user_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a user")
            return
        
        user_data = user_tree.item(selection[0])['values']
        user_id = user_data[0]
        username = user_data[1]
        current_role = user_data[2]
        
        role_dialog = tk.Toplevel(self.root)
        role_dialog.title(f"Change Role - {username}")
        role_dialog.geometry("300x200")
        role_dialog.transient(self.root)
        role_dialog.grab_set()
        
        form_frame = ttk.Frame(role_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)
        
        ttk.Label(form_frame, text=f"Change role for {username}:").pack(pady=(0, 10))
        ttk.Label(form_frame, text=f"Current role: {current_role}").pack(pady=(0, 10))
        
        role_var = tk.StringVar(value=current_role)
        for role in ['student', 'staff', 'admin']:
            ttk.Radiobutton(form_frame, text=role.title(), variable=role_var, value=role).pack(anchor="w")
        
        def save_role():
            new_role = role_var.get()
            if new_role == current_role:
                role_dialog.destroy()
                return

            try:
                # Use auth system to update user role if available
                if self.auth:
                    success = self.auth.update_user(user_id, role=new_role)

                    if not success:
                        messagebox.showerror("Error", "Failed to update role via auth system")
                        return
                else:
                    # Fallback to direct DB access
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
                    conn.commit()
                    conn.close()

                # Log activity
                if ACTIVITY_LOGGER_AVAILABLE:
                    log_activity('update', 'user_role', user_id=user_id, details={
                        'username': username,
                        'old_role': current_role,
                        'new_role': new_role
                    })

                messagebox.showinfo("Success", f"Role changed to {new_role}")
                role_dialog.destroy()
                self.show_user_management()  # Refresh
            except Exception as e:
                messagebox.showerror("Error", f"Could not change role: {e}")
        
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x", pady=(20, 0))
        
        ttk.Button(btn_frame, text="Save", command=save_role).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=role_dialog.destroy).pack(side="left")

    def perform_enhanced_export(self, export_type, filters, format_type):
        """Perform enhanced data export"""
        try:
            filename = filedialog.asksaveasfilename(
                title="Save Export",
                defaultextension=f".{format_type}",
                filetypes=[(f"{format_type.upper()} files", f"*.{format_type}"), ("All files", "*.*")]
            )
            
            if not filename:
                return
            
            self.update_status(f"Exporting {export_type} data...")
            
            # Use existing export functionality
            exported_data = self.support.export_data(export_type, filters, format_type)
            
            with open(filename, 'w') as f:
                f.write(exported_data)
            
            messagebox.showinfo("Export Complete", f"Data exported to {filename}")
            self.update_status("Export completed")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export data: {e}")
            self.update_status("Export failed")

    def update_ticket_assignment(self, ticket_id, window):
        """Update ticket assignment"""
        try:
            assigned_to = self.assign_to_var.get().strip()
            
            # Update in database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            update_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            UPDATE support_tickets 
            SET assigned_to = ?, last_updated_datetime = ?
            WHERE ticket_id = ?
            ''', (assigned_to, update_time, ticket_id))
            
            # Add system response
            cursor.execute('''
            INSERT INTO ticket_responses (
                ticket_id, responder_id, responder_role, response_text,
                response_datetime, is_auto_generated
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                ticket_id, auth.current_user['id'], auth.current_user['role'],
                f"Ticket assigned to {assigned_to}" if assigned_to else "Ticket unassigned",
                update_time, 1
            ))
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", f"Ticket assignment updated")
            window.destroy()
            self.refresh_data()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not update assignment: {e}")

    def update_ticket_status_action(self, ticket_id, window):
        """Update ticket status from actions tab"""
        try:
            new_status = self.new_status_var.get()
            if not new_status:
                messagebox.showerror("Error", "Please select a status")
                return
            
            self.support.update_ticket_status(ticket_id, new_status)
            messagebox.showinfo("Success", f"Status updated to {new_status}")
            window.destroy()
            self.refresh_data()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not update status: {e}")

    def perform_bulk_status_update(self, support, tickets):
        """Perform bulk status update from ticket list"""
        print("\n📊 BULK STATUS UPDATE FROM LIST")
        print("="*40)
        
        # Status selection
        print("\nNew Status:")
        for i, status in enumerate(TICKET_STATUSES, 1):
            print(f"{i}. {status}")
        
        status_choice = input(f"Select new status (1-{len(TICKET_STATUSES)}): ").strip()
        if not status_choice.isdigit() or not 1 <= int(status_choice) <= len(TICKET_STATUSES):
            print("❌ Invalid status choice.")
            return
        
        new_status = TICKET_STATUSES[int(status_choice) - 1]
        
        # Get ticket IDs to update
        ticket_ids_input = input("Enter ticket numbers to update (comma-separated) or 'all' for all tickets: ").strip()
        
        if ticket_ids_input.lower() == 'all':
            ticket_ids = [t['ticket_id'] for t in tickets]
        else:
            try:
                ticket_ids = [int(id.strip()) for id in ticket_ids_input.split(',')]
                # Validate ticket IDs are in the current list
                valid_ids = [t['ticket_id'] for t in tickets]
                ticket_ids = [tid for tid in ticket_ids if tid in valid_ids]
            except ValueError:
                print("❌ Invalid ticket IDs.")
                return
        
        if not ticket_ids:
            print("❌ No valid ticket IDs provided.")
            return
        
        # Confirm operation
        print(f"\n📋 Updating {len(ticket_ids)} tickets to status '{new_status}'")
        confirm = input("Confirm bulk status update? (y/n): ").lower()
        
        if confirm == 'y':
            try:
                updates = {'status': new_status}
                updated_count = support.bulk_update_tickets(ticket_ids, updates)
                print(f"✅ Successfully updated status for {updated_count} tickets")
            except Exception as e:
                print(f"❌ Error during bulk status update: {e}")
        else:
            print("❌ Bulk status update cancelled.")

    def bulk_operations_menu(support):
        """Enhanced bulk operations menu (staff only)"""
        try:
            print("\n📦 BULK OPERATIONS")
            print("="*40)
            
            print("1. Bulk assign tickets")
            print("2. Bulk update ticket status")
            print("3. Bulk update ticket priority")
            print("4. Bulk update ticket category")
            print("5. Merge tickets")
            print("6. Bulk export tickets")
            print("7. Bulk close resolved tickets")
            print("8. Back")
            
            choice = input("\nSelect operation: ").strip()
            
            if choice == '1':
                bulk_assign_tickets_menu(support)
            elif choice == '2':
                bulk_update_status_menu(support)
            elif choice == '3':
                bulk_update_priority_menu(support)
            elif choice == '4':
                bulk_update_category_menu(support)
            elif choice == '5':
                merge_tickets_menu(support)
            elif choice == '6':
                bulk_export_tickets_menu(support)
            elif choice == '7':
                bulk_close_resolved_tickets(support)
            elif choice == '8':
                return
            else:
                print("❌ Invalid choice.")
        
        except Exception as e:
            print(f"❌ Error in bulk operations: {e}")
        
        input("\nPress Enter to continue...")

    def bulk_close_resolved_tickets(support):
        """Bulk close all resolved tickets older than X days"""
        print("\n🔒 BULK CLOSE RESOLVED TICKETS")
        print("="*40)
        
        days_old = input("Close resolved tickets older than how many days? [7]: ").strip()
        if not days_old:
            days_old = 7
        else:
            try:
                days_old = int(days_old)
            except ValueError:
                print("❌ Invalid number of days.")
                return
        
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days_old)).strftime('%Y-%m-%d')
        
        try:
            # Get resolved tickets older than cutoff
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT ticket_id, title FROM support_tickets 
            WHERE status = 'Resolved' AND resolved_at < ?
            ''', (cutoff_date,))
            
            tickets_to_close = cursor.fetchall()
            conn.close()
            
            if not tickets_to_close:
                print(f"📭 No resolved tickets older than {days_old} days found.")
                return
            
            print(f"\n📋 Found {len(tickets_to_close)} resolved tickets to close:")
            for ticket_id, title in tickets_to_close[:5]:
                print(f"  #{ticket_id} - {title[:50]}...")
            
            if len(tickets_to_close) > 5:
                print(f"  ... and {len(tickets_to_close) - 5} more")
            
            confirm = input(f"\nClose {len(tickets_to_close)} resolved tickets? (y/n): ").lower()
            
            if confirm == 'y':
                ticket_ids = [t[0] for t in tickets_to_close]
                updates = {'status': 'Closed'}
                updated_count = support.bulk_update_tickets(ticket_ids, updates)
                print(f"✅ Successfully closed {updated_count} tickets")
            else:
                print("❌ Bulk close cancelled.")
        
        except Exception as e:
            print(f"❌ Error during bulk close: {e}")

    def bulk_export_tickets_menu(support):
        """Bulk export tickets with advanced filters"""
        print("\n📤 BULK EXPORT TICKETS")
        print("="*40)
        
        # Build filters
        filters = {}
        
        print("Build export filters (press Enter to skip):")
        
        status = input(f"Status ({', '.join(TICKET_STATUSES)}): ").strip()
        if status and status in TICKET_STATUSES:
            filters['status'] = status
        
        category = input(f"Category ({', '.join(SUPPORT_CATEGORIES)}): ").strip()
        if category and category in SUPPORT_CATEGORIES:
            filters['category'] = category
        
        priority = input(f"Priority ({', '.join(TICKET_PRIORITIES)}): ").strip()
        if priority and priority in TICKET_PRIORITIES:
            filters['priority'] = priority
        
        date_from = input("From date (YYYY-MM-DD): ").strip()
        if date_from:
            filters['date_from'] = date_from
        
        date_to = input("To date (YYYY-MM-DD): ").strip()
        if date_to:
            filters['date_to'] = date_to
        
        # Format selection
        print("\nExport formats:")
        print("1. CSV")
        print("2. JSON")
        print("3. Excel (XLSX)")
        
        format_choice = input("Select format (1-3): ").strip()
        format_map = {'1': 'csv', '2': 'json', '3': 'xlsx'}
        export_format = format_map.get(format_choice, 'csv')
        
        try:
            # Export data
            print(f"\n📊 Exporting filtered tickets as {export_format.upper()}...")
            exported_data = support.export_data('tickets', filters, export_format)
            
            # Save to file
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"bulk_tickets_export_{timestamp}.{export_format}"
            
            with open(filename, 'w') as f:
                f.write(exported_data)
            
            print(f"✅ Tickets exported to {filename}")
            
        except Exception as e:
            print(f"❌ Error exporting tickets: {e}")

    def show_ticket_templates(self):
        """Show ticket templates for students"""
        self.clear_content()
        
        templates_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(templates_frame, text="📄 Templates")
        
        ttk.Label(templates_frame, text="📄 Ticket Templates", 
                 style='Title.TLabel').pack(pady=(0, 20))
        
        # Get available templates
        try:
            templates = self.support.get_ticket_templates()
            
            if not templates:
                ttk.Label(templates_frame, text="📭 No templates available").pack(pady=20)
                return
            
            # Create scrollable template list
            canvas = tk.Canvas(templates_frame)
            scrollbar = ttk.Scrollbar(templates_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Add templates
            for template in templates:
                template_frame = ttk.LabelFrame(scrollable_frame, text=f"📋 {template['name']}", padding="10")
                template_frame.pack(fill="x", padx=5, pady=5)
                
                # Template info
                info_text = f"📂 Category: {template['category']} | 🔥 Priority: {template['priority']}"
                info_text += f" | 📈 Used {template.get('usage_count', 0)} times"
                ttk.Label(template_frame, text=info_text, 
                         font=('Segoe UI', 9), foreground=self.colors['text_secondary']).pack(anchor="w")
                
                # Title template preview
                ttk.Label(template_frame, text=f"Title: {template['title_template']}", 
                         font=('Segoe UI', 10, 'bold')).pack(anchor="w", pady=(5, 0))
                
                # Description preview
                desc_preview = template['description_template'][:150] + ('...' if len(template['description_template']) > 150 else '')
                ttk.Label(template_frame, text=desc_preview, wraplength=700).pack(anchor="w", pady=(2, 5))
                
                # Use template button
                ttk.Button(template_frame, text="Use This Template", 
                          command=lambda t=template: self.use_template(t)).pack(anchor="w")
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
        except Exception as e:
            ttk.Label(templates_frame, text=f"❌ Error loading templates: {e}").pack(pady=20)

    def use_template(self, template):
        """Use a selected template to create a ticket"""
        try:
            # Switch to create ticket tab with template pre-filled
            self.selected_template_data = template
            self.show_create_ticket()
            
            # Pre-fill the form
            if hasattr(self, 'title_entry'):
                self.title_entry.delete(0, tk.END)
                self.title_entry.insert(0, template['title_template'])
            
            if hasattr(self, 'description_text'):
                self.description_text.delete(1.0, tk.END)
                self.description_text.insert(1.0, template['description_template'])
            
            if hasattr(self, 'category_var'):
                self.category_var.set(template['category'])
            
            if hasattr(self, 'priority_var'):
                self.priority_var.set(template['priority'])
            
            messagebox.showinfo("Template Loaded", f"Template '{template['name']}' has been loaded. You can customize it before submitting.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not use template: {e}")
    
    def show_help(self):
        """Show help dialog"""
        help_dialog = tk.Toplevel(self.root)
        help_dialog.title("📖 User Guide")
        help_dialog.geometry("800x650")
        help_dialog.transient(self.root)
        
        # Help content
        help_content = """
🎓 Enhanced Student Support Portal - User Guide

📊 DASHBOARD
- View your ticket statistics and recent activity
- Access quick actions and notifications
- See system status and important announcements

🎫 TICKETS
- Create new support tickets with attachments
- Track your existing tickets and responses
- Use templates for common issues
- Receive notifications on updates

🔍 SEARCH
- Search across tickets, FAQs, resources, and knowledge base
- Use filters to narrow down results
- Get AI-powered suggestions

❓ FAQs & 📚 KNOWLEDGE BASE
- Browse frequently asked questions
- Access detailed articles and guides
- Rate content as helpful
- Search for specific topics

📋 RESOURCES
- Access support documents and files
- Browse by category
- Download helpful materials

⚙️ PREFERENCES
- Customize notification settings
- Change display preferences
- Set your timezone and language

🔔 NOTIFICATIONS
- View all your notifications
- Mark as read/unread
- Filter by type and status

For additional help, contact the support team.
        """
        
        text_widget = scrolledtext.ScrolledText(help_dialog, wrap=tk.WORD, state='disabled', padding=10)
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)
        
        text_widget.config(state='normal')
        text_widget.insert(1.0, help_content)
        text_widget.config(state='disabled')
        
        # Close button
        ttk.Button(help_dialog, text="❌ Close", command=help_dialog.destroy).pack(pady=10)
    
    def show_about(self):
        """Show about dialog"""
        about_text = """
🎓 Enhanced Student Support Portal
Version 2.0

A comprehensive support system for educational institutions.

Features:
• Advanced ticket management
• Knowledge base and FAQs
• Real-time notifications
• Reporting and analytics
• Mobile-friendly interface

© 2024 Student Support System
        """
        
        messagebox.showinfo("About", about_text)

    def show_preferences(self):
        """Show user preferences interface"""
        self.clear_content()
        
        prefs_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(prefs_frame, text="⚙️ Preferences")
        
        ttk.Label(prefs_frame, text="⚙️ User Preferences", 
                 style='Title.TLabel').pack(pady=(0, 20))
        
        # Get current preferences
        try:
            if self.support:
                current_prefs = self.support.get_user_preferences()
            else:
                current_prefs = {}
        except:
            current_prefs = {}
        
        # Preferences form
        form_frame = ttk.LabelFrame(prefs_frame, text="Notification Settings", padding="15")
        form_frame.pack(fill="x", pady=(0, 10))
        
        # Notification preferences
        self.email_notifications_var = tk.BooleanVar(value=current_prefs.get('email_notifications', True))
        ttk.Checkbutton(form_frame, text="📧 Email Notifications", 
                       variable=self.email_notifications_var).pack(anchor="w", pady=2)
        
        self.in_app_notifications_var = tk.BooleanVar(value=current_prefs.get('in_app_notifications', True))
        ttk.Checkbutton(form_frame, text="🔔 In-App Notifications", 
                       variable=self.in_app_notifications_var).pack(anchor="w", pady=2)
        
        self.push_notifications_var = tk.BooleanVar(value=current_prefs.get('push_notifications', True))
        ttk.Checkbutton(form_frame, text="📱 Push Notifications", 
                       variable=self.push_notifications_var).pack(anchor="w", pady=2)
        
        # Digest frequency
        digest_frame = ttk.Frame(form_frame)
        digest_frame.pack(fill="x", pady=(10, 0))
        
        ttk.Label(digest_frame, text="📅 Digest Frequency:").pack(side="left")
        self.digest_frequency_var = tk.StringVar(value=current_prefs.get('digest_frequency', 'daily'))
        digest_combo = ttk.Combobox(digest_frame, textvariable=self.digest_frequency_var,
                                   values=['immediate', 'daily', 'weekly'], state="readonly")
        digest_combo.pack(side="left", padx=(10, 0))
        
        # Display preferences
        display_frame = ttk.LabelFrame(prefs_frame, text="Display Settings", padding="15")
        display_frame.pack(fill="x", pady=(0, 10))
        
        # Theme
        theme_frame = ttk.Frame(display_frame)
        theme_frame.pack(fill="x", pady=2)
        
        ttk.Label(theme_frame, text="🎨 Theme:").pack(side="left")
        self.theme_var = tk.StringVar(value=current_prefs.get('theme', 'light'))
        theme_combo = ttk.Combobox(theme_frame, textvariable=self.theme_var,
                                  values=['light', 'dark'], state="readonly")
        theme_combo.pack(side="left", padx=(10, 0))
        
        # Language
        language_frame = ttk.Frame(display_frame)
        language_frame.pack(fill="x", pady=2)
        
        ttk.Label(language_frame, text="🌐 Language:").pack(side="left")
        self.language_var = tk.StringVar(value=current_prefs.get('language', 'en'))
        language_combo = ttk.Combobox(language_frame, textvariable=self.language_var,
                                     values=['en', 'es', 'fr', 'de'], state="readonly")
        language_combo.pack(side="left", padx=(10, 0))
        
        # Timezone
        timezone_frame = ttk.Frame(display_frame)
        timezone_frame.pack(fill="x", pady=2)
        
        ttk.Label(timezone_frame, text="🕐 Timezone:").pack(side="left")
        self.timezone_var = tk.StringVar(value=current_prefs.get('timezone', 'UTC'))
        timezone_entry = ttk.Entry(timezone_frame, textvariable=self.timezone_var, width=20)
        timezone_entry.pack(side="left", padx=(10, 0))
        
        # Save button
        ttk.Button(prefs_frame, text="💾 Save Preferences", 
                  command=self.save_preferences, style='Primary.TButton').pack(pady=20)

    def save_preferences(self):
        """Save user preferences"""
        try:
            preferences = {
                'email_notifications': self.email_notifications_var.get(),
                'in_app_notifications': self.in_app_notifications_var.get(),
                'push_notifications': self.push_notifications_var.get(),
                'digest_frequency': self.digest_frequency_var.get(),
                'theme': self.theme_var.get(),
                'language': self.language_var.get(),
                'timezone': self.timezone_var.get()
            }
            
            if self.support:
                self.support.update_user_preferences(preferences)
                messagebox.showinfo("Success", "Preferences saved successfully!")
                self.update_status("Preferences saved")
            else:
                messagebox.showerror("Error", "Support system not available")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save preferences: {e}")

    def mark_faq_helpful(self, faq_id):
        """Mark FAQ as helpful"""
        try:
            def update(conn):
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    UPDATE faqs
                    SET helpful_votes = COALESCE(helpful_votes, 0) + 1
                    WHERE faq_id = ?
                    ''',
                    (faq_id,)
                )
                return cursor.rowcount

            updated = self._safe_db_call(update)
            if updated:
                messagebox.showinfo("Thank You", "Thank you for your feedback!")
                self.update_status("Marked FAQ as helpful")
                self.load_dashboard()
                self._refresh_faq_view()
            else:
                messagebox.showwarning("Notice", "FAQ entry not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not record feedback: {e}")
    
    def _refresh_faq_view(self):
        """Refresh the FAQ view based on the last interaction."""
        try:
            if getattr(self, '_faq_last_mode', 'category') == 'search' and self._faq_last_query:
                if hasattr(self, 'faq_search'):
                    self.faq_search.delete(0, tk.END)
                    self.faq_search.insert(0, self._faq_last_query)
                self.search_faqs()
            else:
                self.show_faqs_by_category(getattr(self, '_faq_last_category', None))
        except Exception:
            self.load_faqs()

    def show_knowledge_base(self):
        """Show knowledge base interface"""
        self.clear_content()
        
        kb_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(kb_frame, text="📚 Knowledge Base")
        
        # Title and controls
        header_frame = ttk.Frame(kb_frame)
        header_frame.pack(fill="x", pady=(0, 15))
        
        ttk.Label(header_frame, text="📚 Knowledge Base", 
                 style='Title.TLabel').pack(side="left")
        
        # Search
        search_frame = ttk.Frame(header_frame)
        search_frame.pack(side="right")
        
        self.kb_search = ttk.Entry(search_frame, width=30, font=('Segoe UI', 10))
        self.kb_search.pack(side="left", padx=(0, 5))
        self.kb_search.bind('<Return>', lambda e: self.search_knowledge_base())
        
        ttk.Button(search_frame, text="🔍 Search", command=self.search_knowledge_base).pack(side="left")
        
        # Categories and filters
        filter_frame = ttk.LabelFrame(kb_frame, text="📂 Browse Articles", padding="10")
        filter_frame.pack(fill="x", pady=(0, 15))
        
        filter_grid = ttk.Frame(filter_frame)
        filter_grid.pack(fill="x")
        
        ttk.Label(filter_grid, text="Category:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.kb_category_filter = ttk.Combobox(filter_grid, values=[
            "All", "Technical", "Academic", "Financial Aid", "Housing", "General"
        ], state="readonly")
        self.kb_category_filter.set("All")
        self.kb_category_filter.grid(row=0, column=1, padx=(0, 10))
        self.kb_category_filter.bind('<<ComboboxSelected>>', lambda e: self.load_knowledge_base())
        
        ttk.Label(filter_grid, text="Sort by:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        self.kb_sort_filter = ttk.Combobox(filter_grid, values=[
            "Most Recent", "Most Viewed", "Most Helpful", "Alphabetical"
        ], state="readonly")
        self.kb_sort_filter.set("Most Recent")
        self.kb_sort_filter.grid(row=0, column=3, padx=(0, 10))
        self.kb_sort_filter.bind('<<ComboboxSelected>>', lambda e: self.load_knowledge_base())
        
        ttk.Button(filter_grid, text="🔄 Refresh", 
                  command=self.load_knowledge_base).grid(row=0, column=4)
        
        # Articles display area
        self.kb_display_frame = ttk.Frame(kb_frame)
        self.kb_display_frame.pack(fill="both", expand=True)
        
        # Load articles
        self.load_knowledge_base()

    def load_knowledge_base(self):
        """Load knowledge base articles"""
        self._kb_last_mode = 'list'
        self._kb_last_search = ''
        # Clear display area
        for widget in self.kb_display_frame.winfo_children():
            widget.destroy()
        
        try:
            if not self.support:
                ttk.Label(self.kb_display_frame, text="❌ Support system not available").pack(pady=20)
                return
            
            # Get filter values
            category = self.kb_category_filter.get()
            category_filter = None if category == "All" else category
            
            articles = self.support.get_kb_articles(category=category_filter, published_only=True)
            
            # Sort articles
            sort_by = self.kb_sort_filter.get()
            if sort_by == "Most Viewed":
                articles.sort(key=lambda x: x.get('view_count', 0), reverse=True)
            elif sort_by == "Most Helpful":
                articles.sort(key=lambda x: x.get('helpful_votes', 0), reverse=True)
            elif sort_by == "Alphabetical":
                articles.sort(key=lambda x: x['title'])
            else:  # Most Recent
                articles.sort(key=lambda x: x.get('published_datetime', ''), reverse=True)
            
            if not articles:
                ttk.Label(self.kb_display_frame, text="📭 No articles found").pack(pady=20)
                return
            
            # Create scrollable articles list
            canvas = tk.Canvas(self.kb_display_frame)
            scrollbar = ttk.Scrollbar(self.kb_display_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Add articles
            for article in articles:
                self.create_kb_article_item(scrollable_frame, article)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
        except Exception as e:
            ttk.Label(self.kb_display_frame, text=f"❌ Error loading articles: {e}").pack(pady=20)

    def create_kb_article_item(self, parent, article):
        """Create a knowledge base article item"""
        article_frame = ttk.LabelFrame(parent, text=f"📖 {article['title']}", padding="10")
        article_frame.pack(fill="x", padx=5, pady=5)
        
        # Article metadata
        meta_frame = ttk.Frame(article_frame)
        meta_frame.pack(fill="x", pady=(0, 10))
        
        # Left side - category and stats
        left_meta = ttk.Frame(meta_frame)
        left_meta.pack(side="left")
        
        meta_text = f"📂 {article['category']} | 👁️ {article.get('view_count', 0)} views | 👍 {article.get('helpful_votes', 0)} helpful"
        ttk.Label(left_meta, text=meta_text, font=('Segoe UI', 9), 
                 foreground=self.colors['text_secondary']).pack(anchor="w")
        
        # Right side - published date
        if article.get('published_datetime'):
            ttk.Label(meta_frame, text=f"📅 Published: {article['published_datetime'][:10]}", 
                     font=('Segoe UI', 9), foreground=self.colors['text_secondary']).pack(side="right")
        
        # Summary or content preview
        if article.get('summary'):
            summary_text = article['summary']
        else:
            summary_text = article['content'][:200] + ('...' if len(article['content']) > 200 else '')
        
        ttk.Label(article_frame, text=summary_text, wraplength=800).pack(anchor="w", pady=(0, 10))
        
        # Tags
        if article.get('tags'):
            tags = article['tags'] if isinstance(article['tags'], list) else json.loads(article.get('tags', '[]'))
            if tags:
                tags_frame = ttk.Frame(article_frame)
                tags_frame.pack(fill="x", pady=(0, 10))
                
                ttk.Label(tags_frame, text="🏷️ Tags:", font=('Segoe UI', 9, 'bold')).pack(side="left")
                for tag in tags[:5]:  # Show max 5 tags
                    tag_label = tk.Label(tags_frame, text=tag, bg="#e5e7eb", fg="#374151", 
                                       padx=6, pady=2, relief="solid", borderwidth=1, 
                                       font=('Segoe UI', 8))
                    tag_label.pack(side="left", padx=(5, 0))
        
        # Action buttons
        btn_frame = ttk.Frame(article_frame)
        btn_frame.pack(fill="x")
        
        ttk.Button(btn_frame, text="📖 Read Full Article", 
                  command=lambda: self.show_article_detail(article)).pack(side="left", padx=(0, 5))
        
        ttk.Button(btn_frame, text="👍 Helpful", 
                  command=lambda: self.mark_article_helpful(article['article_id'])).pack(side="left")

    def search_knowledge_base(self):
        """Search knowledge base articles"""
        query = self.kb_search.get().strip()
        if not query:
            self.load_knowledge_base()
            return
        
        self._kb_last_mode = 'search'
        self._kb_last_search = query
    
        # Clear display area
        for widget in self.kb_display_frame.winfo_children():
            widget.destroy()
        
        try:
            if self.support:
                articles = self.support._search_knowledge_base(query, None)
            else:
                articles = []
            
            if not articles:
                ttk.Label(self.kb_display_frame, text=f"🔍 No articles found for '{query}'").pack(pady=20)
                return
            
            # Show search results
            results_label = ttk.Label(self.kb_display_frame, 
                                    text=f"🔍 Search Results for '{query}' ({len(articles)} found)", 
                                    style='Heading.TLabel')
            results_label.pack(anchor="w", pady=(0, 10))
            
            # Create scrollable results
            canvas = tk.Canvas(self.kb_display_frame)
            scrollbar = ttk.Scrollbar(self.kb_display_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Add search results
            for article in articles:
                self.create_kb_article_item(scrollable_frame, article)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
        except Exception as e:
            ttk.Label(self.kb_display_frame, text=f"❌ Error searching articles: {e}").pack(pady=20)

    def show_article_detail(self, article):
        """Show full article in a new window"""
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"📖 {article['title']}")
        detail_window.geometry("1000x750")
        detail_window.transient(self.root)
        
        # Create scrollable content
        canvas = tk.Canvas(detail_window)
        scrollbar = ttk.Scrollbar(detail_window, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas)
        
        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Article header
        header_frame = ttk.Frame(content_frame, padding="20")
        header_frame.pack(fill="x")
        
        ttk.Label(header_frame, text=article['title'], style='Title.TLabel').pack(anchor="w")
        
        # Metadata
        meta_text = f"📂 {article['category']} | ✍️ {article['author_id']} | 📅 {article.get('published_datetime', 'Not published')}"
        ttk.Label(header_frame, text=meta_text, font=('Segoe UI', 10), 
                 foreground=self.colors['text_secondary']).pack(anchor="w", pady=(5, 0))
        
        stats_text = f"👁️ {article.get('view_count', 0)} views | 👍 {article.get('helpful_votes', 0)} helpful | 👎 {article.get('not_helpful_votes', 0)} not helpful"
        ttk.Label(header_frame, text=stats_text, font=('Segoe UI', 9), 
                 foreground=self.colors['text_secondary']).pack(anchor="w", pady=(2, 0))
        
        # Content
        content_text_frame = ttk.Frame(content_frame, padding="20")
        content_text_frame.pack(fill="both", expand=True)
        
        content_text = scrolledtext.ScrolledText(content_text_frame, wrap=tk.WORD, state='disabled')
        content_text.pack(fill="both", expand=True)
        
        content_text.config(state='normal')
        content_text.insert(1.0, article['content'])
        content_text.config(state='disabled')
        
        # Feedback buttons
        feedback_frame = ttk.Frame(content_frame, padding="20")
        feedback_frame.pack(fill="x")
        
        ttk.Label(feedback_frame, text="Was this article helpful?", font=('Segoe UI', 10, 'bold')).pack(anchor="w")
        
        btn_frame = ttk.Frame(feedback_frame)
        btn_frame.pack(anchor="w", pady=(5, 0))
        
        ttk.Button(btn_frame, text="👍 Yes, helpful", 
                  command=lambda: self.mark_article_helpful(article['article_id'])).pack(side="left", padx=(0, 10))
        
        ttk.Button(btn_frame, text="👎 Not helpful", 
                  command=lambda: self.mark_article_not_helpful(article['article_id'])).pack(side="left")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def mark_article_helpful(self, article_id):
        """Mark article as helpful"""
        try:
            def update(conn):
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    UPDATE kb_articles
                    SET helpful_votes = COALESCE(helpful_votes, 0) + 1
                    WHERE article_id = ?
                    ''',
                    (article_id,)
                )
                return cursor.rowcount

            updated = self._safe_db_call(update)
            if updated:
                messagebox.showinfo("Thank You", "Thank you for your feedback!")
                self.update_status("Marked article as helpful")
                self.load_dashboard()
                self._refresh_kb_view()
            else:
                messagebox.showwarning("Notice", "Article not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not record feedback: {e}")

    def mark_article_not_helpful(self, article_id):
        """Mark article as not helpful"""
        try:
            def update(conn):
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    UPDATE kb_articles
                    SET not_helpful_votes = COALESCE(not_helpful_votes, 0) + 1
                    WHERE article_id = ?
                    ''',
                    (article_id,)
                )
                return cursor.rowcount

            updated = self._safe_db_call(update)
            if updated:
                messagebox.showinfo("Thank You", "Thank you for your feedback!")
                self.update_status("Recorded article feedback")
                self.load_dashboard()
                self._refresh_kb_view()
            else:
                messagebox.showwarning("Notice", "Article not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not record feedback: {e}")

    def _refresh_kb_view(self):
        """Refresh knowledge base view respecting the last interaction."""
        try:
            if getattr(self, '_kb_last_mode', 'list') == 'search' and self._kb_last_search:
                if hasattr(self, 'kb_search'):
                    self.kb_search.delete(0, tk.END)
                    self.kb_search.insert(0, self._kb_last_search)
                self.search_knowledge_base()
            else:
                self.load_knowledge_base()
        except Exception:
            self.load_knowledge_base()

    def show_resources(self):
        """Show support resources interface"""
        self.clear_content()
        
        resources_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(resources_frame, text="📋 Resources")

        header_frame = ttk.Frame(resources_frame)
        header_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(header_frame, text="📋 Support Resources",
                  style='Title.TLabel').pack(side="left")

        controls_frame = ttk.Frame(header_frame)
        controls_frame.pack(side="right")

        self.resource_search_var = tk.StringVar()
        search_entry = ttk.Entry(controls_frame, width=30,
                                 textvariable=self.resource_search_var,
                                 font=('Segoe UI', 10))
        search_entry.pack(side="left", padx=(0, 5))
        search_entry.bind('<Return>', lambda _: self._load_resources())

        ttk.Button(controls_frame, text="🔍 Search",
                   command=self._load_resources).pack(side="left")

        ttk.Button(controls_frame, text="🔄 Refresh",
                   command=self._refresh_resource_filters).pack(side="left", padx=(5, 0))

        filter_frame = ttk.LabelFrame(resources_frame, text="Filters", padding=10)
        filter_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(filter_frame, text="Category:").grid(row=0, column=0, sticky="w")
        self.resource_category_var = tk.StringVar(value="All")
        self.resource_category_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.resource_category_var,
            state="readonly",
            width=25
        )
        self.resource_category_combo.grid(row=0, column=1, padx=(5, 15))
        self.resource_category_combo.bind(
            '<<ComboboxSelected>>',
            lambda _: self._load_resources()
        )

        ttk.Label(filter_frame, text="Type:").grid(row=0, column=2, sticky="w")
        self.resource_type_var = tk.StringVar(value="All")
        type_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.resource_type_var,
            values=["All", "Article", "Document", "Video", "Link"],
            state="readonly",
            width=20
        )
        type_combo.grid(row=0, column=3, padx=(5, 0))
        type_combo.bind('<<ComboboxSelected>>', lambda _: self._load_resources())

        ttk.Button(filter_frame, text="Clear Filters",
                   command=lambda: self._reset_resource_filters()).grid(row=0, column=4, padx=(15, 0))

        content_frame = ttk.Frame(resources_frame)
        content_frame.pack(fill="both", expand=True)

        columns = ("Title", "Category", "Type", "Accesses", "Updated")
        self.resources_tree = ttk.Treeview(content_frame, columns=columns, show="headings", height=16)
        for col in columns:
            width = 220 if col == "Title" else 140
            self.resources_tree.heading(col, text=col)
            self.resources_tree.column(col, width=width, anchor="w")

        self.resources_tree.pack(side="left", fill="both", expand=True)
        self.resources_tree.bind('<<TreeviewSelect>>', self._on_resource_select)
        self.resources_tree.bind('<Double-1>', lambda _: self._open_selected_resource())

        scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=self.resources_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.resources_tree.configure(yscrollcommand=scrollbar.set)

        detail_frame = ttk.LabelFrame(resources_frame, text="Resource Details", padding=10)
        detail_frame.pack(fill="x", pady=(15, 0))

        self.resource_detail_text = scrolledtext.ScrolledText(detail_frame, height=6, wrap=tk.WORD, state='disabled')
        self.resource_detail_text.pack(fill="x", expand=True, pady=(0, 10))

        action_frame = ttk.Frame(detail_frame)
        action_frame.pack(fill="x")

        self.resource_link_button = ttk.Button(action_frame, text="Open Resource",
                                               command=self._open_selected_resource,
                                               state='disabled')
        self.resource_link_button.pack(side="left")

        ttk.Button(action_frame, text="Copy Link",
                   command=self._copy_resource_link).pack(side="left", padx=5)

        self._load_resource_categories()
        self._load_resources()

    def show_ticket_templates(self):
        """Show ticket templates for students"""
        self.clear_content()
        
        templates_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(templates_frame, text="📄 Templates")

        header_frame = ttk.Frame(templates_frame)
        header_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(header_frame, text="📄 Ticket Templates",
                  style='Title.TLabel').pack(side="left")

        search_frame = ttk.Frame(header_frame)
        search_frame.pack(side="right")

        self.template_search_var = tk.StringVar()
        template_search_entry = ttk.Entry(search_frame, width=30,
                                          textvariable=self.template_search_var,
                                          font=('Segoe UI', 10))
        template_search_entry.pack(side="left", padx=(0, 5))
        template_search_entry.bind('<Return>', lambda _: self._load_templates())

        ttk.Button(search_frame, text="🔍 Search",
                   command=self._load_templates).pack(side="left")

        ttk.Button(search_frame, text="🔄 Refresh",
                   command=self._refresh_template_filters).pack(side="left", padx=(5, 0))

        filter_frame = ttk.LabelFrame(templates_frame, text="Filters", padding=10)
        filter_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(filter_frame, text="Category:").grid(row=0, column=0, sticky="w")
        self.template_category_var = tk.StringVar(value="All")
        self.template_category_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.template_category_var,
            state="readonly",
            width=25
        )
        self.template_category_combo.grid(row=0, column=1, padx=(5, 15))
        self.template_category_combo.bind('<<ComboboxSelected>>', lambda _: self._load_templates())

        ttk.Label(filter_frame, text="Priority:").grid(row=0, column=2, sticky="w")
        self.template_priority_var = tk.StringVar(value="All")
        priority_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.template_priority_var,
            values=["All"] + TICKET_PRIORITIES if TICKET_PRIORITIES else ["All"],
            state="readonly",
            width=20
        )
        priority_combo.grid(row=0, column=3, padx=(5, 0))
        priority_combo.bind('<<ComboboxSelected>>', lambda _: self._load_templates())

        ttk.Button(filter_frame, text="Clear Filters",
                   command=self._reset_template_filters).grid(row=0, column=4, padx=(15, 0))

        content_frame = ttk.Frame(templates_frame)
        content_frame.pack(fill="both", expand=True)

        template_columns = ("Name", "Category", "Priority", "Usage", "Created")
        self.templates_tree = ttk.Treeview(content_frame, columns=template_columns, show="headings", height=16)
        for col in template_columns:
            width = 220 if col == "Name" else 140
            self.templates_tree.heading(col, text=col)
            self.templates_tree.column(col, width=width, anchor="w")

        self.templates_tree.pack(side="left", fill="both", expand=True)
        self.templates_tree.bind('<<TreeviewSelect>>', self._on_template_select)

        template_scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=self.templates_tree.yview)
        template_scrollbar.pack(side="right", fill="y")
        self.templates_tree.configure(yscrollcommand=template_scrollbar.set)

        detail_frame = ttk.LabelFrame(templates_frame, text="Template Details", padding=10)
        detail_frame.pack(fill="x", pady=(15, 0))

        self.template_title_var = tk.StringVar(value="Select a template to view details.")
        ttk.Label(detail_frame, textvariable=self.template_title_var,
                  font=('Segoe UI', 10, 'bold')).pack(anchor="w", pady=(0, 8))

        self.template_body_text = scrolledtext.ScrolledText(detail_frame, height=6, wrap=tk.WORD, state='disabled')
        self.template_body_text.pack(fill="x", expand=True, pady=(0, 10))

        template_action_frame = ttk.Frame(detail_frame)
        template_action_frame.pack(fill="x")

        ttk.Button(template_action_frame, text="Copy Title",
                   command=self._copy_template_title).pack(side="left")
        ttk.Button(template_action_frame, text="Copy Description",
                   command=self._copy_template_description).pack(side="left", padx=5)

        self._load_template_categories()
        self._load_templates()

    def _load_resource_categories(self):
        """Load resource categories into the category combobox."""
        try:
            def fetch(conn):
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT category FROM support_resources ORDER BY category')
                return [row[0] for row in cursor.fetchall()]

            categories = self._safe_db_call(fetch)
            values = ["All"] + categories if categories else ["All"]
            self.resource_category_combo['values'] = values
            if self.resource_category_var.get() not in values:
                self.resource_category_var.set("All")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load resource categories: {exc}")
            self.resource_category_combo['values'] = ["All"]
            self.resource_category_var.set("All")

    def _refresh_resource_filters(self):
        self._load_resource_categories()
        self._load_resources()

    def _reset_resource_filters(self):
        self.resource_search_var.set("")
        self.resource_category_var.set("All")
        self.resource_type_var.set("All")
        self._refresh_resource_filters()

    def _load_resources(self):
        """Fetch and display support resources."""
        try:
            category = self.resource_category_var.get()
            resource_type = self.resource_type_var.get()
            search = self.resource_search_var.get().strip()

            def fetch(conn):
                cursor = conn.cursor()
                query = '''
                    SELECT resource_id, title, category, content_type, access_count,
                           COALESCE(updated_datetime, created_datetime) as updated_at,
                           description, url, file_path, requires_auth, tags
                    FROM support_resources
                '''
                conditions = []
                params = []

                if category and category != "All":
                    conditions.append("category = ?")
                    params.append(category)

                if resource_type and resource_type != "All":
                    conditions.append("LOWER(content_type) = ?")
                    params.append(resource_type.lower())

                if search:
                    conditions.append("""
                        (LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(tags) LIKE ?)
                    """)
                    like_term = f"%{search.lower()}%"
                    params.extend([like_term, like_term, like_term])

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                query += " ORDER BY updated_at DESC"

                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

            resources = self._safe_db_call(fetch) or []
            self.resource_records = {res['resource_id']: res for res in resources}

            for item in self.resources_tree.get_children():
                self.resources_tree.delete(item)

            for res in resources:
                content_type = (res.get('content_type') or 'Unknown').title()
                updated = res.get('updated_at') or ''
                self.resources_tree.insert(
                    '',
                    tk.END,
                    iid=str(res['resource_id']),
                    values=(
                        res['title'],
                        res['category'],
                        content_type,
                        res.get('access_count', 0),
                        updated[:16] if updated else '—'
                    )
                )

            if not resources:
                self.resource_detail_text.config(state='normal')
                self.resource_detail_text.delete(1.0, tk.END)
                self.resource_detail_text.insert(1.0, "No resources found matching the current filters.")
                self.resource_detail_text.config(state='disabled')
                self.resource_link_button.config(state='disabled')
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load resources: {exc}")

    def _on_resource_select(self, event=None):
        """Display details for the selected resource."""
        selection = self.resources_tree.selection()
        if not selection:
            self.resource_link_button.config(state='disabled')
            return

        resource_id = int(selection[0])
        resource = self.resource_records.get(resource_id)
        if not resource:
            self.resource_link_button.config(state='disabled')
            return

        details = [
            f"Title: {resource['title']}",
            f"Category: {resource['category']}",
            f"Type: {resource.get('content_type', 'Unknown')}",
            f"Accesses: {resource.get('access_count', 0)}",
            f"Updated: {resource.get('updated_at', '—')}",
        ]
        if resource.get('requires_auth'):
            details.append("Access: 🔒 Login required")
        if resource.get('url'):
            details.append(f"URL: {resource['url']}")
        if resource.get('file_path'):
            details.append(f"File: {resource['file_path']}")
        if resource.get('description'):
            details.append(f"\nDescription:\n{resource['description']}")
        if resource.get('tags'):
            tags = resource['tags']
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except json.JSONDecodeError:
                    tags = [tags]
            if tags:
                details.append(f"\nTags: {', '.join(tags)}")

        self.resource_detail_text.config(state='normal')
        self.resource_detail_text.delete(1.0, tk.END)
        self.resource_detail_text.insert(1.0, "\n".join(details))
        self.resource_detail_text.config(state='disabled')

        if resource.get('url') or resource.get('file_path'):
            self.resource_link_button.config(state='normal')
        else:
            self.resource_link_button.config(state='disabled')

    def _open_selected_resource(self):
        """Open the selected resource via URL or local file."""
        selection = self.resources_tree.selection()
        if not selection:
            return

        resource = self.resource_records.get(int(selection[0]))
        if not resource:
            return

        if resource.get('requires_auth') and not self.auth.current_user:
            messagebox.showwarning("Restricted", "Please sign in to access this resource.")
            return

        if resource.get('url'):
            try:
                webbrowser.open(resource['url'])
                self.update_status("Opening resource URL")
            except Exception as exc:
                messagebox.showerror("Error", f"Could not open URL: {exc}")
            return

        if resource.get('file_path'):
            self.open_file(resource['file_path'])
            return

        messagebox.showinfo("Resource", "No link or downloadable file is associated with this resource.")

    def _copy_resource_link(self):
        """Copy the selected resource URL to the clipboard."""
        selection = self.resources_tree.selection()
        if not selection:
            messagebox.showwarning("Copy Link", "Select a resource first.")
            return

        resource = self.resource_records.get(int(selection[0]))
        if resource and resource.get('url'):
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(resource['url'])
                self.update_status("Resource link copied to clipboard")
            except Exception as exc:
                messagebox.showerror("Error", f"Could not copy link: {exc}")
        else:
            messagebox.showwarning("Copy Link", "The selected resource does not have a URL.")

    def _load_template_categories(self):
        """Load template categories into the category combobox."""
        try:
            def fetch(conn):
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT category FROM ticket_templates ORDER BY category')
                return [row[0] for row in cursor.fetchall()]

            categories = self._safe_db_call(fetch)
            values = ["All"] + categories if categories else ["All"]
            self.template_category_combo['values'] = values
            if self.template_category_var.get() not in values:
                self.template_category_var.set("All")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load template categories: {exc}")
            self.template_category_combo['values'] = ["All"]
            self.template_category_var.set("All")

    def _refresh_template_filters(self):
        self._load_template_categories()
        self._load_templates()

    def _reset_template_filters(self):
        self.template_search_var.set("")
        self.template_category_var.set("All")
        self.template_priority_var.set("All")
        self._refresh_template_filters()

    def _load_templates(self):
        """Fetch and display ticket templates."""
        try:
            category = self.template_category_var.get()
            priority = self.template_priority_var.get()
            search = self.template_search_var.get().strip()

            def fetch(conn):
                cursor = conn.cursor()
                query = '''
                    SELECT template_id, name, category, priority, created_datetime,
                           usage_count, title_template, description_template, created_by
                    FROM ticket_templates
                    WHERE is_active = 1
                '''
                conditions = []
                params = []

                if category and category != "All":
                    conditions.append("category = ?")
                    params.append(category)

                if priority and priority != "All":
                    conditions.append("priority = ?")
                    params.append(priority)

                if search:
                    conditions.append("(LOWER(name) LIKE ? OR LOWER(description_template) LIKE ?)")
                    like_term = f"%{search.lower()}%"
                    params.extend([like_term, like_term])

                if conditions:
                    query += " AND " + " AND ".join(conditions)

                query += " ORDER BY created_datetime DESC"
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

            templates = self._safe_db_call(fetch) or []
            self.template_records = {tpl['template_id']: tpl for tpl in templates}

            for item in self.templates_tree.get_children():
                self.templates_tree.delete(item)

            for tpl in templates:
                created = tpl.get('created_datetime') or ''
                self.templates_tree.insert(
                    '',
                    tk.END,
                    iid=str(tpl['template_id']),
                    values=(
                        tpl['name'],
                        tpl['category'],
                        tpl['priority'],
                        tpl.get('usage_count', 0),
                        created[:16] if created else '—'
                    )
                )

            if not templates:
                self.template_title_var.set("No templates found.")
                self.template_body_text.config(state='normal')
                self.template_body_text.delete(1.0, tk.END)
                self.template_body_text.insert(1.0, "Adjust your filters or create new templates.")
                self.template_body_text.config(state='disabled')
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load ticket templates: {exc}")

    def _on_template_select(self, event=None):
        """Display details for the selected ticket template."""
        selection = self.templates_tree.selection()
        if not selection:
            self.selected_template_id = None
            return

        template_id = int(selection[0])
        template = self.template_records.get(template_id)
        if not template:
            self.selected_template_id = None
            return

        self.selected_template_id = template_id

        self.template_title_var.set(f"{template['name']} • {template['category']} • {template['priority']}")
        body_text = template.get('description_template') or ''
        title_text = template.get('title_template') or ''

        detail = f"Title Template:\n{title_text}\n\nDescription Template:\n{body_text}"
        self.template_body_text.config(state='normal')
        self.template_body_text.delete(1.0, tk.END)
        self.template_body_text.insert(1.0, detail)
        self.template_body_text.config(state='disabled')

    def _copy_template_title(self):
        """Copy the selected template title to clipboard."""
        if not getattr(self, 'selected_template_id', None):
            messagebox.showwarning("Copy Title", "Select a template first.")
            return
        template = self.template_records.get(self.selected_template_id)
        if not template:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(template.get('title_template', ''))
            self.update_status("Template title copied to clipboard")
        except Exception as exc:
            messagebox.showerror("Error", f"Could not copy title: {exc}")

    def _copy_template_description(self):
        """Copy the selected template description to clipboard."""
        if not getattr(self, 'selected_template_id', None):
            messagebox.showwarning("Copy Description", "Select a template first.")
            return
        template = self.template_records.get(self.selected_template_id)
        if not template:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(template.get('description_template', ''))
            self.update_status("Template description copied to clipboard")
        except Exception as exc:
            messagebox.showerror("Error", f"Could not copy description: {exc}")

    def show_reports(self):
        """Show reports interface (staff only)"""
        self.clear_content()
        
        reports_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(reports_frame, text="📊 Reports")
        
        # Check permissions
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] not in ('staff', 'admin'):
            ttk.Label(reports_frame, text="❌ Staff access required", 
                     style='Title.TLabel').pack(pady=20)
            return
        
        # Reports interface
        ttk.Label(reports_frame, text="📊 Support Reports", 
                 style='Title.TLabel').pack(pady=(0, 20))
        
        # Report types
        report_types = [
            ("📊 Ticket Summary Report", "ticket_summary"),
            ("📈 Performance Report", "performance"),
            ("⭐ Satisfaction Report", "satisfaction"),
            ("📂 Category Analysis", "category_analysis")
        ]
        
        for name, report_type in report_types:
            btn_frame = ttk.Frame(reports_frame)
            btn_frame.pack(fill="x", pady=5)
            
            ttk.Button(btn_frame, text=name, 
                      command=lambda rt=report_type: self.generate_report(rt)).pack(side="left")
            
            # Add description
            descriptions = {
                "ticket_summary": "Overview of tickets by status, category, and priority",
                "performance": "Staff performance metrics and resolution times",
                "satisfaction": "Customer satisfaction ratings and feedback",
                "category_analysis": "Analysis of tickets by support category"
            }
            
            ttk.Label(btn_frame, text=descriptions.get(report_type, ""), 
                     foreground=self.colors['text_secondary']).pack(side="left", padx=(10, 0))

    def generate_report(self, report_type):
        """Generate a report"""
        # Show date range dialog
        date_dialog = tk.Toplevel(self.root)
        date_dialog.title("📅 Report Date Range")
        date_dialog.geometry("400x200")
        date_dialog.transient(self.root)
        date_dialog.grab_set()
        
        # Date range form
        form_frame = ttk.Frame(date_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)
        
        ttk.Label(form_frame, text="Select Report Date Range", style='Heading.TLabel').pack(pady=(0, 20))
        
        # Start date
        ttk.Label(form_frame, text="Start Date (YYYY-MM-DD):").pack(anchor="w")
        start_date_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        start_entry = ttk.Entry(form_frame, textvariable=start_date_var, width=20)
        start_entry.pack(fill="x", pady=(5, 10))
        
        # End date
        ttk.Label(form_frame, text="End Date (YYYY-MM-DD):").pack(anchor="w")
        end_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        end_entry = ttk.Entry(form_frame, textvariable=end_date_var, width=20)
        end_entry.pack(fill="x", pady=(5, 20))
        
        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x")
        
        def generate():
            start_date = start_date_var.get()
            end_date = end_date_var.get()
            date_dialog.destroy()
            self.run_report_generation(report_type, start_date, end_date)
        
        ttk.Button(btn_frame, text="📊 Generate Report", command=generate).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=date_dialog.destroy).pack(side="left")

    def run_report_generation(self, report_type, start_date, end_date):
        """Run report generation in background"""
        def generate_in_background():
            try:
                self.update_status(f"Generating {report_type} report...")
                
                date_range = {'start': start_date, 'end': end_date}
                report_data = self.support.generate_reports(report_type, date_range)
                
                # Show report in new window
                self.root.after(0, lambda: self.show_report_window(report_type, report_data, date_range))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Report Error", f"Failed to generate report: {e}"))
                self.root.after(0, lambda: self.update_status("Report generation failed"))
        
        # Run in background thread
        threading.Thread(target=generate_in_background, daemon=True).start()

    def show_report_window(self, report_type, report_data, date_range):
        """Show generated report in a new window"""
        report_window = tk.Toplevel(self.root)
        report_window.title(f"📊 {report_type.replace('_', ' ').title()} Report")
        report_window.geometry("1200x850")
        
        # Create notebook for different views
        report_notebook = ttk.Notebook(report_window, padding="10")
        report_notebook.pack(fill="both", expand=True)
        
        # Summary tab
        summary_frame = ttk.Frame(report_notebook, padding="10")
        report_notebook.add(summary_frame, text="📋 Summary")
        
        self.create_report_summary(summary_frame, report_type, report_data, date_range)
        
        # Data tab
        data_frame = ttk.Frame(report_notebook, padding="10")
        report_notebook.add(data_frame, text="📊 Data")
        
        self.create_report_data_view(data_frame, report_data)
        
        # Export tab
        export_frame = ttk.Frame(report_notebook, padding="10")
        report_notebook.add(export_frame, text="📤 Export")
        
        self.create_report_export_options(export_frame, report_type, report_data)
        
        self.update_status(f"{report_type} report generated successfully")

    def create_report_summary(self, parent, report_type, report_data, date_range):
        """Create report summary view"""
        # Title
        title_text = f"📊 {report_type.replace('_', ' ').title()} Report"
        ttk.Label(parent, text=title_text, style='Title.TLabel').pack(pady=(0, 10))
        
        # Date range
        date_text = f"📅 Period: {date_range['start']} to {date_range['end']}"
        ttk.Label(parent, text=date_text, font=('Segoe UI', 10)).pack(pady=(0, 20))
        
        # Key metrics based on report type
        if report_type == 'ticket_summary':
            metrics = [
                ("📊 Total Tickets", str(report_data.get('total_tickets', 0))),
                ("🟢 Open", str(report_data.get('status_breakdown', {}).get('Open', 0))),
                ("⏳ In Progress", str(report_data.get('status_breakdown', {}).get('In Progress', 0))),
                ("✅ Resolved", str(report_data.get('status_breakdown', {}).get('Resolved', 0))),
            ]
        elif report_type == 'performance':
            stats = report_data.get('resolution_stats', {})
            metrics = [
                ("⏱️ Avg Resolution Time", f"{stats.get('avg_hours', 0):.1f} hours"),
                ("✅ Resolved Tickets", str(stats.get('resolved_count', 0))),
                ("⚡ Fastest Resolution", f"{stats.get('min_hours', 0):.1f} hours"),
                ("🐌 Slowest Resolution", f"{stats.get('max_hours', 0):.1f} hours"),
            ]
        elif report_type == 'satisfaction':
            metrics = [
                ("⭐ Average Rating", f"{report_data.get('avg_rating', 0):.2f}/5"),
                ("📊 Response Rate", f"{report_data.get('response_rate', 0):.1f}%"),
                ("📝 Total Responses", str(report_data.get('total_responses', 0))),
            ]
        else:
            metrics = []
        
        # Display metrics in a grid
        if metrics:
            metrics_frame = ttk.LabelFrame(parent, text="📈 Key Metrics", padding="15")
            metrics_frame.pack(fill="x", pady=(0, 20))
            
            metrics_grid = ttk.Frame(metrics_frame)
            metrics_grid.pack()
            
            for i, (label, value) in enumerate(metrics):
                row, col = i // 2, i % 2
                
                metric_frame = ttk.Frame(metrics_grid)
                metric_frame.grid(row=row, column=col, padx=20, pady=10, sticky="w")
                
                ttk.Label(metric_frame, text=label, font=('Segoe UI', 10)).pack()
                ttk.Label(metric_frame, text=value, font=('Segoe UI', 14, 'bold'), 
                         foreground=self.colors['primary']).pack()

    def create_report_data_view(self, parent, report_data):
        """Create detailed data view"""
        # Create scrollable text area for JSON data
        data_text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, state='disabled')
        data_text.pack(fill="both", expand=True)
        
        # Format and display data
        data_text.config(state='normal')
        data_text.insert(1.0, json.dumps(report_data, indent=2, default=str))
        data_text.config(state='disabled')

    def create_report_export_options(self, parent, report_type, report_data):
        """Create report export options"""
        ttk.Label(parent, text="📤 Export Options", style='Heading.TLabel').pack(pady=(0, 20))
        
        # Export format selection
        format_frame = ttk.LabelFrame(parent, text="Format", padding="10")
        format_frame.pack(fill="x", pady=(0, 10))
        
        self.export_format_var = tk.StringVar(value="JSON")
        
        for fmt in ["JSON", "CSV", "TXT"]:
            ttk.Radiobutton(format_frame, text=fmt, variable=self.export_format_var, 
                           value=fmt).pack(side="left", padx=10)
        
        # Export button
        ttk.Button(parent, text="💾 Export Report", 
                  command=lambda: self.export_report_data(report_type, report_data)).pack(pady=20)

    def export_report_data(self, report_type, report_data):
        """Export report data to file"""
        format_type = self.export_format_var.get().lower()
        
        # File dialog
        filename = filedialog.asksaveasfilename(
            title="Save Report",
            defaultextension=f".{format_type}",
            filetypes=[(f"{format_type.upper()} files", f"*.{format_type}"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        try:
            if format_type == "json":
                with open(filename, 'w') as f:
                    json.dump(report_data, f, indent=2, default=str)
            elif format_type == "csv":
                # Convert to CSV format (simplified)
                with open(filename, 'w') as f:
                    f.write("Report Type,Data\n")
                    f.write(f"{report_type},{json.dumps(report_data, default=str)}\n")
            else:  # TXT
                with open(filename, 'w') as f:
                    f.write(f"Report: {report_type}\n")
                    f.write("=" * 50 + "\n")
                    f.write(json.dumps(report_data, indent=2, default=str))
            
            messagebox.showinfo("Export Complete", f"Report exported to {filename}")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export report: {e}")


# Main GUI launcher function that maintains backwards compatibility
def launch_student_support_gui():
    """Launch the GUI version of the student support system"""
    try:
        # Initialize the GUI
        root = tk.Tk()
        app = StudentSupportGUI(root)
        
        # Start the GUI event loop
        root.mainloop()
        
    except Exception as e:
        # Fallback to CLI if GUI fails
        print(f"GUI initialization failed: {e}")
        print("Falling back to command-line interface...")
        
        # Import and run CLI version
        try:
            display_support_menu()
        except Exception as cli_error:
            print(f"CLI fallback also failed: {cli_error}")
            print("Please check your installation and try again.")


# Enhanced CLI integration for backwards compatibility
def enhanced_display_support_menu():
    """Enhanced version of display_support_menu with GUI option"""
    print("\n" + "="*60)
    print("🎓 STUDENT SUPPORT PORTAL")
    print("="*60)
    
    # Check if GUI is available
    gui_available = True
    try:
        import tkinter
    except ImportError:
        gui_available = False
    
    print("Interface Options:")
    if gui_available:
        print("1. 🖥️  Launch GUI Interface")
        print("2. 💻 Use Command Line Interface")
        print("3. ❌ Exit")
        
        choice = input("\nChoose interface (1-3): ").strip()
        
        if choice == "1":
            launch_student_support_gui()
            return
        elif choice == "2":
            # Continue to CLI
            pass
        elif choice == "3":
            return
        else:
            print("Invalid choice. Using CLI interface.")
    else:
        print("GUI not available. Using command line interface.")
    
    # Run original CLI
    display_support_menu()


# Backwards compatibility wrapper
def display_enhanced_support_portal():
    """Main entry point that chooses between GUI and CLI"""
    global auth
    
    # Initialize authentication if not already done
    if auth is None:
        try:
            from university_system.infrastructure.auth.user_authentication import UserAuth
            auth = UserAuth()
        except ImportError:
            print("Warning: Could not initialize authentication system")
            auth = None
    
    # Check if user is logged in
    if not auth or not auth.current_user:
        print("⚠️  Please log in first to access the support portal.")
        return
    
    # Launch enhanced interface
    enhanced_display_support_menu()


# Additional utility functions for GUI/CLI bridge
class SupportPortalLauncher:
    """
    Utility class to launch support portal in different modes
    Provides a clean interface for integration with other systems
    """
    
    def __init__(self, auth_system=None):
        self.auth = auth_system
        global auth
        if auth_system:
            auth = auth_system
    
    def launch_gui(self):
        """Launch GUI interface"""
        return launch_student_support_gui()
    
    def launch_cli(self):
        """Launch CLI interface"""
        return display_support_menu()
    
    def launch_auto(self):
        """Automatically choose best interface"""
        try:
            import tkinter
            return self.launch_gui()
        except ImportError:
            return self.launch_cli()
        except Exception:
            return self.launch_cli()
    
    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            root_widget = self.root if hasattr(self, 'root') else self.master
            if isinstance(root_widget, tk.Toplevel):
                # Just close the child window
                root_widget.destroy()
            else:
                # Running standalone, need to create main GUI
                root_widget.destroy()
                from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def is_gui_available(self):
        """Check if GUI is available"""
        try:
            import tkinter
            return True
        except ImportError:
            return False


# Configuration for seamless integration
INTEGRATION_CONFIG = {
    'auto_detect_interface': True,
    'prefer_gui': True,
    'fallback_to_cli': True,
    'show_interface_choice': True,
    'remember_preference': False,  # Could be implemented with config file
}


def configure_integration(**kwargs):
    """Configure integration behavior"""
    global INTEGRATION_CONFIG
    INTEGRATION_CONFIG.update(kwargs)
    return INTEGRATION_CONFIG


# Example usage and testing functions
def test_gui_functionality():
    """Test GUI functionality - for development/debugging"""
    print("Testing GUI functionality...")
    
    try:
        import tkinter as tk
        
        # Test basic GUI creation
        root = tk.Tk()
        root.withdraw()  # Hide window
        
        # Test StudentSupportGUI instantiation
        app = StudentSupportGUI(root)
        
        print("✅ GUI components loaded successfully")
        
        root.destroy()
        return True
        
    except Exception as e:
        print(f"❌ GUI test failed: {e}")
        return False


def test_integration():
    """Test integration with existing system"""
    print("Testing system integration...")
    
    try:
        # Test imports
        from university_system.modules.domain.student_affairs.services.student_support import EnhancedStudentSupport
        print("✅ Enhanced support system imported")
        
        # Test configuration
        config = SupportConfig()
        print("✅ Configuration loaded")
        
        # Test support system instantiation
        support = EnhancedStudentSupport(config)
        print("✅ Support system initialized")
        
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False


# Integration hooks for existing codebase
def integrate_gui_with_existing_system():
    """
    Integration function to seamlessly add GUI to existing system
    Call this from your main application to add GUI support
    """
    
    # Monkey patch the original display_support_menu if it exists
    import sys
    current_module = sys.modules[__name__]
    
    # Try to import original module
    try:
        if 'student_support' in sys.modules:
            original_module = sys.modules['student_support']
            # Replace the original function with enhanced version
            original_module.display_support_menu = enhanced_display_support_menu
            print("✅ GUI integration successful - display_support_menu enhanced")
        
        # Also try refactored path
        if 'refactored.student_support.student_support' in sys.modules:
            original_module = sys.modules['refactored.student_support.student_support']
            original_module.display_support_menu = enhanced_display_support_menu
            print("✅ GUI integration successful - refactored module enhanced")
            
    except Exception as e:
        print(f"⚠️  GUI integration warning: {e}")
        print("GUI features available but not integrated with existing CLI")
    
    return True


# Auto-integration when imported
try:
    integrate_gui_with_existing_system()
except Exception:
    pass  # Silent fail for integration


# Command-line argument support
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--gui":
            launch_student_support_gui()
        elif sys.argv[1] == "--cli":
            display_support_menu()
        elif sys.argv[1] == "--test":
            print("🧪 Running tests...")
            gui_test = test_gui_functionality()
            integration_test = test_integration()
            
            if gui_test and integration_test:
                print("✅ All tests passed!")
            else:
                print("❌ Some tests failed - check logs above")
        elif sys.argv[1] == "--help":
            print("""
Student Support Portal
======================

Usage:
  python student_support_gui.py [option]

Options:
  --gui     Launch GUI interface
  --cli     Use command-line interface
  --test    Run system tests
  --help    Show this help message

If no option is specified, the system will automatically choose
the best available interface.
            """)
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Use --help for available options.")
    else:
        # Default: try GUI first, fallback to CLI
        try:
            import tkinter
            launch_student_support_gui()
        except ImportError:
            print("GUI not available. Using command-line interface...")
            display_support_menu()
        except Exception as e:
            print(f"GUI failed to start: {e}")
            print("Falling back to command-line interface...")
            display_support_menu()


# Export all original functions for backwards compatibility
__all__ = [
    # GUI classes
    'StudentSupportGUI',
    'launch_student_support_gui',
    
    # Enhanced functions
    'enhanced_display_support_menu',
    'display_enhanced_support_portal',
    
    # Utility classes
    'SupportPortalLauncher',
    
    # Configuration
    'INTEGRATION_CONFIG',
    'configure_integration',
    
    # Testing functions
    'test_gui_functionality',
    'test_integration',
    
    # Integration functions
    'integrate_gui_with_existing_system',
    
    # All original functions are still available through imports
    'display_support_menu',
    'display_enhanced_faqs',
    'display_enhanced_resources',
    'view_my_tickets_enhanced',
    'view_all_tickets_enhanced',
    'manage_templates_menu',
    'manage_knowledge_base_menu',
    'show_template_statistics',
    'create_enhanced_ticket',
    'display_ticket_details_enhanced',
    
    # Support system classes
    'EnhancedStudentSupport',
    'SupportConfig',
    'NotificationType',
    'TicketSentiment',
    'FileType',
    
    # Helper functions
    'setup_enhanced_logging',
    'audit_action',
    'validate_ticket_permissions',
    'format_ticket_status_display',
    'format_priority_display',
    'format_file_size',
    'truncate_text',
    'handle_support_error',
]
