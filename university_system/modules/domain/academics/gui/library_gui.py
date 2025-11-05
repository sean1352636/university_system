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
        """Create the application menu bar"""
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Import Books", command=self.import_books_gui)
        file_menu.add_command(label="Export Books", command=self.export_books_gui)
        file_menu.add_separator()
        file_menu.add_command(label="Backup System", command=self.backup_system_gui)
        file_menu.add_command(label="Restore System", command=self.restore_system_gui)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.exit_application)
        file_menu.add_separator()
        file_menu.add_command(label="Export Statistics", command=self.generate_library_statistics_export)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Settings", command=self.show_settings)
        edit_menu.add_command(label="User Preferences", command=self.show_user_preferences)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Dashboard", command=self.show_dashboard)
        view_menu.add_command(label="All Books", command=self.show_all_books)
        view_menu.add_command(label="Overdue Items", command=self.show_overdue_books)
        view_menu.add_command(label="📅 Book Return Calendar", command=self.open_calendar_with_due_dates)
        view_menu.add_command(label="Reports", command=self.show_reports)
        view_menu.add_separator()
        view_menu.add_command(label="System Maintenance", command=self.library_maintenance_gui)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Advanced Search", command=self.show_advanced_search)
        tools_menu.add_command(label="Barcode Scanner", command=self.show_barcode_scanner)
        tools_menu.add_command(label="Reading Lists", command=self.show_reading_lists)
        tools_menu.add_command(label="Digital Library", command=self.show_digital_library)
        tools_menu.add_command(label="Loan History", command=self.view_loan_history_gui)
        tools_menu.add_command(label="Fine Management", command=self.show_fine_management)
        tools_menu.add_command(label="System Health Check", command=self.quick_system_health_check)
        tools_menu.add_command(label="Library Card Generator", command=self.show_library_cards_generator)
        tools_menu.add_command(label="Barcode Generator", command=self.show_barcode_generator)
    
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
        dialog = tk.Toplevel(self.master)
        dialog.title("Checkout Book")
        dialog.geometry("500x400")
        dialog.transient(self.master)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
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
        
        # User selection
        user_frame = ttk.LabelFrame(main_frame, text="User Information")
        user_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(user_frame, text="User Type:").pack(anchor='w', padx=5, pady=5)
        self.user_type_var = tk.StringVar(value="Student")
        ttk.Radiobutton(user_frame, text="Student", variable=self.user_type_var, value="Student").pack(anchor='w', padx=20)
        ttk.Radiobutton(user_frame, text="Staff", variable=self.user_type_var, value="Staff").pack(anchor='w', padx=20)
        
        ttk.Label(user_frame, text="User ID:").pack(anchor='w', padx=5, pady=5)
        self.checkout_user_var = tk.StringVar()
        user_entry = ttk.Entry(user_frame, textvariable=self.checkout_user_var, width=30)
        user_entry.pack(anchor='w', padx=5, pady=5)
        
        ttk.Button(user_frame, text="Verify User", command=self.verify_checkout_user).pack(anchor='w', padx=5, pady=5)
        
        # User details display
        self.checkout_user_info = tk.Text(user_frame, height=3, wrap=tk.WORD, state=tk.DISABLED)
        self.checkout_user_info.pack(fill=tk.X, padx=5, pady=5)
        
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
            conn.close()
            
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
                success = self.return_book_database()
                
                if success:
                    messagebox.showinfo("Success", "Book returned successfully!")

                    # Send return confirmation email
                    self._send_return_confirmation_email(self.selected_return_book_id, self.selected_user_id_return)

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
                       s.email{grade_sql}
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
        """Placeholder for card usage report."""
        self._show_report_not_available("Library Card Usage Report")

    def generate_health_report(self):
        """Placeholder for system health report."""
        self._show_report_not_available("System Health Report")

    def generate_maintenance_report(self):
        """Placeholder for maintenance activity report."""
        self._show_report_not_available("Maintenance Activity Report")
        
    def show_statistics_dashboard(self):
        """Show statistics dashboard"""
        self.report_text.delete("1.0", tk.END)
        
        try:
            stats_data = self.get_library_statistics()
            self.report_text.insert(tk.END, stats_data)
        except Exception as e:
            self.report_text.insert(tk.END, f"Error loading statistics: {str(e)}")
            
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
        self.reading_lists_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)
        
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
        if not self.current_user:
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
                    cursor.execute('SELECT first_name, last_name, email FROM students WHERE student_id = ?', (user_id,))
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

                # Add fee to student_fees table
                fee_id = f"LIB_{student_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                current_date = datetime.now().strftime('%Y-%m-%d')
                due_date = current_date  # Library fines are due immediately

                cursor.execute('''
                    INSERT INTO student_fees
                    (fee_id, student_id, fee_type, amount, due_date, description, paid_status, created_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    fee_id, student_id, 'Library Fine', amount, due_date,
                    f'Library late return fine for {student_name}', 'Paid', current_date
                ))

                # Record payment in payments table if it exists
                try:
                    payment_id = f"PAY_{fee_id}"
                    cursor.execute('''
                        INSERT INTO payments
                        (payment_id, student_id, amount, payment_method, payment_date, status, description)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        payment_id, student_id, amount, 'Student Account', current_date, 'completed',
                        f'Library fine payment for {student_name}'
                    ))
                except sqlite3.Error:
                    # Payments table might not exist, continue anyway
                    pass

                # Update library fine status to paid
                cursor.execute('''
                    UPDATE book_loans
                    SET fine_paid = 1, fine_paid_date = ?
                    WHERE user_id = ? AND fine_amount > 0 AND status != 'returned'
                ''', (current_date, student_id))

                conn.commit()
                return True

        except Exception as e:
            print(f"Finance integration error: {e}")
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
                    cursor.execute('SELECT first_name, last_name, email FROM students WHERE student_id = ?', (user_id,))
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
                    cursor.execute('SELECT first_name, last_name, email FROM students WHERE student_id = ?', (user_id,))
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
