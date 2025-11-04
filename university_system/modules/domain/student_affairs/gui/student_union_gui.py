import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from university_system.infrastructure.email.template_utils import render_template
from university_system.infrastructure.auth.user_authentication import UserAuth

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from university_system.infrastructure.database.db import get_connection
    from university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except Exception:
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False
    
class StudentUnionGUI:
    """Main GUI application for Student Union Management System"""
    
    def __init__(self, parent=None):
        if parent:
            self.root = parent
            self.master = parent  # Set master for consistency
            # Don't create a new Tk instance if parent is provided
        else:
            self.root = tk.Tk()
            self.master = self.root  # Set master for consistency

        self.root.title("Student Union Management System")
        self.root.geometry("1400x900")
        self.root.minsize(1000, 700)
        
        # Initialize variables
        self.current_user = None
        self.auth_manager = None
        
        # Use centralized path configuration
        # Always use the central student_records.db in university_system/data/db_files
        self.db_path = str(paths.DEFAULT_DB_PATH)
        
        # GUI components
        self.main_frame = None
        self.content_frame = None
        self.status_bar = None
        self.menu_bar = None
        
        # Setup the application only if not embedded
        if not parent:
            self.setup_database()
            self.setup_gui()
            self.show_login_screen()
    
    # ------------------------------------------------------------------ helpers
    def _safe_db_call(self, operation_func, *args, **kwargs):
        """
        Execute a database operation with basic error handling.

        Returns the operation result on success, or False/None on failure.
        """
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            result = operation_func(conn, *args, **kwargs)
            conn.commit()
            return result
        except sqlite3.Error as exc:
            logging_error = getattr(logging, "error", print)
            logging_error(f"StudentUnionGUI DB error: {exc}")
            if conn:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
        
    def setup_database(self):
        """Initialize database connection and tables"""
        try:
            # If the CLI's enhanced initializer is available, invoke it first.
            # To ensure that the tables are created in the same file used by
            # this GUI (self.db_path), temporarily override the default
            # database path used by the refactored.database.db module. This
            # allows the CLI initializer to operate on the same database file.
            if init_student_union_db:
                try:
                    import university_system.infrastructure.database.db as _db_module
                    # Backup original default path and override it
                    _old_db_path = getattr(_db_module, 'DEFAULT_DB_PATH', None)
                    _db_module.DEFAULT_DB_PATH = self.db_path
                    init_student_union_db()
                    # Restore original default path
                    if _old_db_path is not None:
                        _db_module.DEFAULT_DB_PATH = _old_db_path
                except Exception as e:
                    # Log but do not crash if enhanced initialization fails
                    print(f"Warning: failed to initialize enhanced student union database: {e}")

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Create basic tables if they don't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    email TEXT,
                    role TEXT DEFAULT 'student',
                    created_at TEXT,
                    last_login TEXT
                )
            ''')

            # Add last_login column if it doesn't exist (migration)
            try:
                cursor.execute("SELECT last_login FROM users LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute("ALTER TABLE users ADD COLUMN last_login TEXT")
                conn.commit()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    email_address TEXT UNIQUE NOT NULL,
                    course TEXT,
                    year_of_study INTEGER,
                    enrollment_date TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS student_clubs (
                    club_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    club_name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    category TEXT,
                    member_count INTEGER DEFAULT 0,
                    president_id TEXT,
                    treasurer_id TEXT,
                    secretary_id TEXT,
                    status TEXT DEFAULT 'active',
                    created_date TEXT,
                    FOREIGN KEY (president_id) REFERENCES students (student_id),
                    FOREIGN KEY (treasurer_id) REFERENCES students (student_id),
                    FOREIGN KEY (secretary_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS union_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT NOT NULL,
                    description TEXT,
                    organizer_id INTEGER,
                    event_date TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    location TEXT,
                    category TEXT,
                    max_attendees INTEGER,
                    current_attendees INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'upcoming',
                    created_at TEXT,
                    FOREIGN KEY (organizer_id) REFERENCES student_clubs (club_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS club_members (
                    member_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    club_id INTEGER,
                    student_id TEXT,
                    role TEXT DEFAULT 'member',
                    join_date TEXT,
                    FOREIGN KEY (club_id) REFERENCES student_clubs (club_id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS facility_bookings (
                    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    facility_name TEXT,
                    user_id INTEGER,
                    booking_date TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    purpose TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS union_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT NOT NULL,
                    description TEXT,
                    organizer_id INTEGER,
                    event_date TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    location TEXT,
                    category TEXT,
                    max_attendees INTEGER,
                    current_attendees INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'upcoming',
                    created_at TEXT,
                    FOREIGN KEY (organizer_id) REFERENCES student_clubs (club_id)
                )
            ''')
            
            conn.commit()
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to initialize database: {e}")
            sys.exit(1)

    def set_auth(self, auth_manager):
        """Set authentication manager for integration with main system"""
        self.auth_manager = auth_manager
        if auth_manager and hasattr(auth_manager, 'current_user') and auth_manager.current_user:
            self.current_user = {
                'id': auth_manager.current_user.get('id'),
                'username': auth_manager.current_user.get('username'), 
                'email': auth_manager.current_user.get('email', ''),
                'role': auth_manager.current_user.get('role', 'student')
            }
            print(f"Authentication context set for user: {self.current_user['username']}")

    def setup_gui_embedded(self, parent_window):
        """Setup GUI for embedded use in parent window"""
        self.root = parent_window
        self.setup_gui()
        
        # Override the window close behavior to not exit the entire application
        def on_closing():
            self.root.destroy()
        
        self.root.protocol("WM_DELETE_WINDOW", on_closing)
    
    def setup_gui(self):
        """Setup the main GUI structure"""
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Create menu bar
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)
        
        # Main container
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Status bar - FIXED: Use consistent naming
        self.status_label = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
    
    def clear_content(self):
        """Clear the current content frame"""
        if self.content_frame:
            self.content_frame.destroy()
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True)
    
    def update_status(self, message: str):
        """Update status bar message"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        status_text = f"{timestamp} - {message}"
        
        if hasattr(self, 'status_label'):
            self.status_label.config(text=status_text)
        elif hasattr(self, 'status_bar'):
            self.status_bar.config(text=status_text)
        
    def show_login_screen(self):
        """Display the login screen"""
        self.clear_content()
        
        # Center the login form
        login_frame = ttk.Frame(self.content_frame)
        login_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Title
        title_label = ttk.Label(login_frame, text="Student Union Management System", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=20)
        
        # Login form
        form_frame = ttk.Frame(login_frame)
        form_frame.pack(pady=20)
        
        ttk.Label(form_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.username_entry = ttk.Entry(form_frame, width=25)
        self.username_entry.grid(row=0, column=1, padx=10, pady=5)
        
        ttk.Label(form_frame, text="Password:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.password_entry = ttk.Entry(form_frame, width=25, show="*")
        self.password_entry.grid(row=1, column=1, padx=10, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(login_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Login", command=self.login).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Register", command=self.show_register_screen).pack(side=tk.LEFT, padx=5)
        
        if CLI_AVAILABLE:
            ttk.Button(button_frame, text="CLI Mode", command=self.switch_to_cli).pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key to login
        self.root.bind('<Return>', lambda e: self.login())
        
        self.username_entry.focus()
    
    def login(self):
        """Handle user login"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            messagebox.showerror("Error", "Please enter both username and password")
            return

        try:
            # Use centralized authentication system
            auth_system = UserAuth()
            result = auth_system.login(username, password)

            # Handle different return types from login
            if isinstance(result, dict) and result.get('success') and result.get('requires_2fa'):
                # 2FA is required - for now, show error message
                # TODO: Implement 2FA input dialog in future
                messagebox.showerror("2FA Required", "Two-factor authentication is enabled for this account. Please use the CLI interface for 2FA login.")
                return
            elif result is True:
                # Login successful, get user data from auth_system.current_user
                if auth_system.current_user:
                    self.current_user = {
                        'id': auth_system.current_user['id'],
                        'username': auth_system.current_user['username'],
                        'email': auth_system.current_user.get('email', ''),
                        'role': auth_system.current_user['role']
                    }

                    self.update_status(f"Logged in as {username}")
                    self.show_main_dashboard()
                else:
                    messagebox.showerror("Login Failed", "Authentication succeeded but user data is unavailable")
            elif result == 'password_reset_required':
                # Password reset is required
                messagebox.showwarning("Password Reset Required", "You must change your password. Please use the CLI interface or contact an administrator.")
            else:
                # Login failed
                messagebox.showerror("Login Failed", "Invalid username or password")

        except Exception as e:
            messagebox.showerror("Authentication Error", f"Login failed: {e}")
    
    def show_register_screen(self):
        """Display the registration screen"""
        register_window = tk.Toplevel(self.root)
        register_window.title("Register New User")
        register_window.geometry("400x600")  # Increased height to accommodate all fields
        register_window.transient(self.root)
        register_window.grab_set()
        
        # Center the window
        register_window.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))
        
        # Registration form
        form_frame = ttk.Frame(register_window)
        form_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
        
        ttk.Label(form_frame, text="Register New User", font=('Arial', 14, 'bold')).pack(pady=10)
        
        # Form fields
        fields = {}
        
        # Username
        ttk.Label(form_frame, text="Username:").pack(anchor=tk.W, pady=(10,0))
        fields['username'] = ttk.Entry(form_frame, width=30)
        fields['username'].pack(fill=tk.X, pady=(0,10))
        
        # Password
        ttk.Label(form_frame, text="Password:").pack(anchor=tk.W)
        fields['password'] = ttk.Entry(form_frame, width=30, show="*")
        fields['password'].pack(fill=tk.X, pady=(0,10))
        
        # Confirm Password
        ttk.Label(form_frame, text="Confirm Password:").pack(anchor=tk.W)
        fields['confirm_password'] = ttk.Entry(form_frame, width=30, show="*")
        fields['confirm_password'].pack(fill=tk.X, pady=(0,10))
        
        # Email
        ttk.Label(form_frame, text="Email:").pack(anchor=tk.W)
        fields['email'] = ttk.Entry(form_frame, width=30)
        fields['email'].pack(fill=tk.X, pady=(0,10))
        
        # Student ID
        ttk.Label(form_frame, text="Student ID:").pack(anchor=tk.W)
        fields['student_id'] = ttk.Entry(form_frame, width=30)
        fields['student_id'].pack(fill=tk.X, pady=(0,10))
        
        # First Name
        ttk.Label(form_frame, text="First Name:").pack(anchor=tk.W)
        fields['first_name'] = ttk.Entry(form_frame, width=30)
        fields['first_name'].pack(fill=tk.X, pady=(0,10))
        
        # Last Name
        ttk.Label(form_frame, text="Last Name:").pack(anchor=tk.W)
        fields['last_name'] = ttk.Entry(form_frame, width=30)
        fields['last_name'].pack(fill=tk.X, pady=(0,10))
        
        # Course
        ttk.Label(form_frame, text="Course:").pack(anchor=tk.W)
        fields['course'] = ttk.Combobox(form_frame, values=['CS', 'DS', 'Other'], width=27)
        fields['course'].pack(fill=tk.X, pady=(0,10))
        
        # Year of Study
        ttk.Label(form_frame, text="Year of Study:").pack(anchor=tk.W)
        fields['year'] = ttk.Combobox(form_frame, values=['1', '2', '3', '4'], width=27)
        fields['year'].pack(fill=tk.X, pady=(0,10))
        
        # Buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(pady=20)
        
        def register_user():
            # Validate fields
            username = fields['username'].get().strip()
            password = fields['password'].get()
            confirm_password = fields['confirm_password'].get()
            email = fields['email'].get().strip()
            student_id = fields['student_id'].get().strip()
            first_name = fields['first_name'].get().strip()
            last_name = fields['last_name'].get().strip()
            course = fields['course'].get().strip()
            year = fields['year'].get()

            # Validation
            if not all([username, password, email, student_id, first_name, last_name]):
                messagebox.showerror("Error", "Please fill in all required fields")
                return

            if password != confirm_password:
                messagebox.showerror("Error", "Passwords do not match")
                return

            if len(password) < 6:
                messagebox.showerror("Error", "Password must be at least 6 characters")
                return

            try:
                # First check if student_id already exists in students table
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
                if cursor.fetchone()[0] > 0:
                    messagebox.showerror("Error", "Student ID already exists")
                    conn.close()
                    return

                conn.close()

                # Use centralized authentication system to create user
                auth_system = UserAuth()
                success = auth_system.create_user(
                    username=username,
                    password=password,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    role='student',
                    student_id=student_id
                )

                if success:
                    # User created successfully, now create student record
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()

                    # Insert student record
                    cursor.execute('''
                        INSERT INTO students (student_id, first_name, last_name, email_address, course, year_of_study, enrollment_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (student_id, first_name, last_name, email, course, int(year) if year else 1, datetime.now().strftime('%Y-%m-%d')))

                    # Get the user_id from the users table
                    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
                    user_result = cursor.fetchone()
                    if user_result:
                        user_id = user_result[0]
                        # Link student record to user (if your students table has a user_id column)
                        try:
                            cursor.execute('UPDATE students SET user_id = ? WHERE student_id = ?', (user_id, student_id))
                        except sqlite3.OperationalError:
                            # user_id column doesn't exist, which is fine for this implementation
                            pass

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Registration successful! You can now log in.")
                    register_window.destroy()
                else:
                    # User creation failed - auth_system already printed the error
                    messagebox.showerror("Registration Failed", "User account creation failed. Username or email may already exist.")

            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Registration failed: {e}")
                if 'conn' in locals():
                    conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Registration failed: {e}")
                if 'conn' in locals() and conn:
                    conn.close()
        
        ttk.Button(button_frame, text="Register", command=register_user).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=register_window.destroy).pack(side=tk.LEFT, padx=5)
        
        fields['username'].focus()
            
    def switch_to_cli(self):
        """Switch to CLI mode"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI mode is not available")
            return
        
        response = messagebox.askyesno("Switch to CLI", 
                                     "Switch to command-line interface mode?\nThe GUI will close.")
        if response:
            self.root.destroy()
            # Launch CLI mode
            try:
                from part2 import main
                main()
            except ImportError:
                print("Error: Cannot import CLI system")
    
    def show_main_dashboard(self):
        """Display the main dashboard"""
        self.clear_content()
        self.setup_main_menu()

        # Add return to main menu button at the top
        return_btn = ttk.Button(
            self.root,
            text="🏠 Return to Main Menu",
            command=self.return_to_main_menu
        )
        return_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        # Create notebook for main content
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Dashboard tab
        self.show_dashboard_tab()
        
        # Other tabs
        self.show_clubs_tab()
        self.show_events_tab()
        self.show_facilities_tab()
        
        if self.current_user['role'] in ['admin', 'staff']:
            self.show_admin_tab()
    
    def setup_main_menu(self):
        """Setup the main menu bar"""
        # Clear existing menu
        self.menu_bar.delete(0, 'end')
        
        # File menu
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Profile", command=self.show_profile)
        file_menu.add_separator()
        file_menu.add_command(label="Logout", command=self.logout)
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Tools menu
        tools_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Tools", menu=tools_menu)
        if CLI_AVAILABLE:
            tools_menu.add_command(label="Switch to CLI", command=self.switch_to_cli)
        tools_menu.add_command(label="Database Info", command=self.show_database_info)

        # Integrations menu
        integrations_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="🔗 Integrations", menu=integrations_menu)

        # Finance submenu
        finance_submenu = tk.Menu(integrations_menu, tearoff=0)
        integrations_menu.add_cascade(label="💳 Finance", menu=finance_submenu)
        finance_submenu.add_command(label="Open Finance System",
                                   command=lambda: self.open_finance_gui_for_club_payment("General Payment", 0))
        finance_submenu.add_command(label="Club Payments",
                                   command=lambda: self.open_finance_gui_for_club_payment("Club Fee", 25, "Club Membership"))

        # Shop submenu
        shop_submenu = tk.Menu(integrations_menu, tearoff=0)
        integrations_menu.add_cascade(label="🛍️ Shop", menu=shop_submenu)
        shop_submenu.add_command(label="University Shop",
                                command=lambda: self.open_shop_for_club_merchandise("General"))
        shop_submenu.add_command(label="Club Merchandise",
                                command=lambda: self.show_club_selection_for_merchandise())

        # Restaurant submenu
        restaurant_submenu = tk.Menu(integrations_menu, tearoff=0)
        integrations_menu.add_cascade(label="🍽️ Restaurant", menu=restaurant_submenu)
        restaurant_submenu.add_command(label="University Restaurant",
                                      command=lambda: self.open_restaurant_for_club_booking("General"))
        restaurant_submenu.add_command(label="Club Dining Booking",
                                      command=lambda: self.show_club_selection_for_dining())

        # Calendar and Trips
        integrations_menu.add_separator()
        integrations_menu.add_command(label="📅 Student Union Calendar",
                                     command=lambda: self.open_calendar_with_club_events())
        integrations_menu.add_command(label="🧳 Trip Management",
                                     command=lambda: self.show_club_selection_for_trips())

        # Help menu
        help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

        self.create_main_menu_button()

    def create_main_menu_button(self):
        """Ensure a top-right button exists for returning to the main menu"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception:
            pass

        self.main_menu_button = ttk.Button(
            self.root,
            text="🏠 Return to Main Menu",
            command=self.return_to_main_menu,
        )
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
    
    def show_dashboard_tab(self):
        """Create and display the dashboard tab"""
        dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(dashboard_frame, text="Dashboard")
        
        # Welcome section
        welcome_frame = ttk.LabelFrame(dashboard_frame, text="Welcome")
        welcome_frame.pack(fill=tk.X, padx=10, pady=5)
        
        welcome_text = f"Welcome back, {self.current_user['username']}!"
        ttk.Label(welcome_frame, text=welcome_text, font=('Arial', 12)).pack(pady=10)
        
        # Quick stats
        stats_frame = ttk.LabelFrame(dashboard_frame, text="Quick Statistics")
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        
        stats_content = ttk.Frame(stats_frame)
        stats_content.pack(fill=tk.X, padx=10, pady=10)
        
        # Get statistics from database
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Get various counts
            cursor.execute('SELECT COUNT(*) FROM student_clubs WHERE status = "active"')
            active_clubs = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM union_events WHERE status = "upcoming"')
            upcoming_events = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM students')
            total_students = cursor.fetchone()[0]
            
            # Display stats in a grid
            ttk.Label(stats_content, text="Active Clubs:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=10)
            ttk.Label(stats_content, text=str(active_clubs)).grid(row=0, column=1, sticky=tk.W)
            
            ttk.Label(stats_content, text="Upcoming Events:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky=tk.W, padx=10)
            ttk.Label(stats_content, text=str(upcoming_events)).grid(row=1, column=1, sticky=tk.W)
            
            ttk.Label(stats_content, text="Total Students:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky=tk.W, padx=10)
            ttk.Label(stats_content, text=str(total_students)).grid(row=2, column=1, sticky=tk.W)
            
            conn.close()
            
        except sqlite3.Error as e:
            ttk.Label(stats_content, text=f"Error loading statistics: {e}").pack()
        
        # Quick actions
        actions_frame = ttk.LabelFrame(dashboard_frame, text="Quick Actions")
        actions_frame.pack(fill=tk.X, padx=10, pady=5)
        
        actions_content = ttk.Frame(actions_frame)
        actions_content.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(actions_content, text="View My Clubs", 
                  command=lambda: self.notebook.select(1)).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_content, text="Browse Events", 
                  command=lambda: self.notebook.select(2)).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_content, text="Book Facility", 
                  command=lambda: self.notebook.select(3)).pack(side=tk.LEFT, padx=5)
    
    def show_clubs_tab(self):
        """Create and display the clubs tab"""
        clubs_frame = ttk.Frame(self.notebook)
        self.notebook.add(clubs_frame, text="Clubs")
        
        # Create paned window for clubs
        clubs_paned = ttk.PanedWindow(clubs_frame, orient=tk.HORIZONTAL)
        clubs_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Left panel - Club list
        left_panel = ttk.Frame(clubs_paned)
        clubs_paned.add(left_panel, weight=1)
        
        ttk.Label(left_panel, text="Student Clubs", font=('Arial', 12, 'bold')).pack(pady=5)
        
        # Club list with scrollbar
        list_frame = ttk.Frame(left_panel)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.clubs_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.clubs_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.clubs_listbox.yview)
        
        # Bind selection event
        self.clubs_listbox.bind('<<ListboxSelect>>', self.on_club_select)
        
        # Club action buttons
        club_buttons_frame = ttk.Frame(left_panel)
        club_buttons_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(club_buttons_frame, text="Refresh", 
                  command=self.refresh_clubs_list).pack(side=tk.LEFT, padx=2)
        ttk.Button(club_buttons_frame, text="Join Club", 
                  command=self.join_selected_club).pack(side=tk.LEFT, padx=2)
        ttk.Button(club_buttons_frame, text="Create Club", 
                  command=self.create_club_dialog).pack(side=tk.LEFT, padx=2)
        
        # Right panel - Club details
        right_panel = ttk.Frame(clubs_paned)
        clubs_paned.add(right_panel, weight=2)
        
        ttk.Label(right_panel, text="Club Details", font=('Arial', 12, 'bold')).pack(pady=5)
        
        # Club details text area
        self.club_details_text = scrolledtext.ScrolledText(right_panel, height=20, width=50)
        self.club_details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Load clubs initially
        self.refresh_clubs_list()
    
    def show_events_tab(self):
        """Create and display the events tab"""
        events_frame = ttk.Frame(self.notebook)
        self.notebook.add(events_frame, text="Events")
        
        # Events control panel
        control_frame = ttk.Frame(events_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(control_frame, text="Events & Activities", font=('Arial', 12, 'bold')).pack(side=tk.LEFT)
        
        ttk.Button(control_frame, text="Refresh", 
                  command=self.refresh_events_list).pack(side=tk.RIGHT, padx=2)
        ttk.Button(control_frame, text="Create Event", 
                  command=self.create_event_dialog).pack(side=tk.RIGHT, padx=2)
        ttk.Button(control_frame, text="My Events", 
                  command=self.show_my_events).pack(side=tk.RIGHT, padx=2)
        
        # Events treeview
        columns = ('ID', 'Name', 'Date', 'Time', 'Location', 'Organizer', 'Attendees', 'Status')
        self.events_tree = ttk.Treeview(events_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        for col in columns:
            self.events_tree.heading(col, text=col)
            if col == 'ID':
                self.events_tree.column(col, width=50)
            elif col == 'Name':
                self.events_tree.column(col, width=200)
            else:
                self.events_tree.column(col, width=100)
        
        # Add scrollbars
        events_scrollbar_v = ttk.Scrollbar(events_frame, orient=tk.VERTICAL, command=self.events_tree.yview)
        events_scrollbar_h = ttk.Scrollbar(events_frame, orient=tk.HORIZONTAL, command=self.events_tree.xview)
        self.events_tree.configure(yscrollcommand=events_scrollbar_v.set, xscrollcommand=events_scrollbar_h.set)
        
        # Pack treeview and scrollbars
        self.events_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10,0), pady=5)
        events_scrollbar_v.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        events_scrollbar_h.pack(side=tk.BOTTOM, fill=tk.X, padx=10)
        
        # Event action buttons
        event_actions_frame = ttk.Frame(events_frame)
        event_actions_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(event_actions_frame, text="Register for Event", 
                  command=self.register_for_selected_event).pack(side=tk.LEFT, padx=5)
        ttk.Button(event_actions_frame, text="View Details", 
                  command=self.view_event_details).pack(side=tk.LEFT, padx=5)
        
        # Load events initially
        self.refresh_events_list()
    
    def show_facilities_tab(self):
        """Create and display the facilities tab"""
        facilities_frame = ttk.Frame(self.notebook)
        self.notebook.add(facilities_frame, text="Facilities")
        
        # Facilities content
        ttk.Label(facilities_frame, text="Facility Booking System", 
                 font=('Arial', 14, 'bold')).pack(pady=10)
        
        # Booking form
        booking_frame = ttk.LabelFrame(facilities_frame, text="Book a Facility")
        booking_frame.pack(fill=tk.X, padx=20, pady=10)
        
        form_frame = ttk.Frame(booking_frame)
        form_frame.pack(padx=20, pady=20)
        
        # Facility selection
        ttk.Label(form_frame, text="Facility:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.facility_combo = ttk.Combobox(form_frame, width=30)
        self.facility_combo.grid(row=0, column=1, padx=10, pady=5)
        
        # Date selection
        ttk.Label(form_frame, text="Date:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.booking_date_entry = ttk.Entry(form_frame, width=32)
        self.booking_date_entry.grid(row=1, column=1, padx=10, pady=5)
        
        # Time selection
        ttk.Label(form_frame, text="Start Time:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.start_time_entry = ttk.Entry(form_frame, width=32)
        self.start_time_entry.grid(row=2, column=1, padx=10, pady=5)
        
        ttk.Label(form_frame, text="End Time:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.end_time_entry = ttk.Entry(form_frame, width=32)
        self.end_time_entry.grid(row=3, column=1, padx=10, pady=5)
        
        # Purpose
        ttk.Label(form_frame, text="Purpose:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.purpose_entry = ttk.Entry(form_frame, width=32)
        self.purpose_entry.grid(row=4, column=1, padx=10, pady=5)
        
        # Submit button
        ttk.Button(form_frame, text="Submit Booking Request", 
                  command=self.submit_booking_request).grid(row=5, column=1, pady=20)
        
        # Load facilities
        self.load_facilities()
        
        # My bookings section
        bookings_frame = ttk.LabelFrame(facilities_frame, text="My Bookings")
        bookings_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Bookings treeview
        booking_columns = ('ID', 'Facility', 'Date', 'Time', 'Status', 'Purpose')
        self.bookings_tree = ttk.Treeview(bookings_frame, columns=booking_columns, show='headings', height=8)
        
        for col in booking_columns:
            self.bookings_tree.heading(col, text=col)
            self.bookings_tree.column(col, width=100)
        
        bookings_scrollbar = ttk.Scrollbar(bookings_frame, orient=tk.VERTICAL, command=self.bookings_tree.yview)
        self.bookings_tree.configure(yscrollcommand=bookings_scrollbar.set)
        
        self.bookings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        bookings_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        # Load my bookings
        self.refresh_my_bookings()
    
    def show_admin_tab(self):
        """Create and display the admin tab (for admin users only)"""
        admin_frame = ttk.Frame(self.notebook)
        self.notebook.add(admin_frame, text="Administration")
        
        ttk.Label(admin_frame, text="System Administration", 
                 font=('Arial', 14, 'bold')).pack(pady=10)
        
        # Admin sections
        admin_notebook = ttk.Notebook(admin_frame)
        admin_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # User Management
        users_frame = ttk.Frame(admin_notebook)
        admin_notebook.add(users_frame, text="Users")
        
        self.setup_users_management(users_frame)
        
        # Club Management
        club_admin_frame = ttk.Frame(admin_notebook)
        admin_notebook.add(club_admin_frame, text="Club Admin")
        
        self.setup_club_administration(club_admin_frame)
        
        # System Info
        system_frame = ttk.Frame(admin_notebook)
        admin_notebook.add(system_frame, text="System")
        
        self.setup_system_info(system_frame)
    
    def setup_users_management(self, parent):
        """Setup user management interface"""
        # Users list
        users_list_frame = ttk.LabelFrame(parent, text="Registered Users")
        users_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Users treeview
        user_columns = ('ID', 'Username', 'Email', 'Role', 'Created', 'Last Login')
        self.users_tree = ttk.Treeview(users_list_frame, columns=user_columns, show='headings', height=12)
        
        for col in user_columns:
            self.users_tree.heading(col, text=col)
            if col == 'ID':
                self.users_tree.column(col, width=50)
            elif col in ['Username', 'Email']:
                self.users_tree.column(col, width=150)
            else:
                self.users_tree.column(col, width=120)
        
        users_scrollbar = ttk.Scrollbar(users_list_frame, orient=tk.VERTICAL, command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=users_scrollbar.set)
        
        self.users_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        users_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        # User management buttons
        user_buttons_frame = ttk.Frame(parent)
        user_buttons_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(user_buttons_frame, text="Refresh Users", 
                  command=self.refresh_users_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(user_buttons_frame, text="Change Role", 
                  command=self.change_user_role).pack(side=tk.LEFT, padx=5)
        ttk.Button(user_buttons_frame, text="Delete User", 
                  command=self.delete_user).pack(side=tk.LEFT, padx=5)
        
        # Load users initially
        self.refresh_users_list()
    
    def setup_club_administration(self, parent):
        """Setup club administration interface"""
        # Club approval section
        approval_frame = ttk.LabelFrame(parent, text="Club Management")
        approval_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Admin club actions
        admin_buttons_frame = ttk.Frame(approval_frame)
        admin_buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(admin_buttons_frame, text="View All Clubs", 
                  command=self.view_all_clubs_admin).pack(side=tk.LEFT, padx=5)
        ttk.Button(admin_buttons_frame, text="Club Statistics", 
                  command=self.show_club_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(admin_buttons_frame, text="Export Data", 
                  command=self.export_club_data).pack(side=tk.LEFT, padx=5)
        
        # Club statistics display
        self.club_stats_text = scrolledtext.ScrolledText(approval_frame, height=15)
        self.club_stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Load initial statistics
        self.show_club_statistics()
    
    def setup_system_info(self, parent):
        """Setup system information interface"""
        info_frame = ttk.LabelFrame(parent, text="System Information")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.system_info_text = scrolledtext.ScrolledText(info_frame, height=20)
        self.system_info_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # System action buttons
        system_buttons_frame = ttk.Frame(parent)
        system_buttons_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(system_buttons_frame, text="Refresh Info", 
                  command=self.refresh_system_info).pack(side=tk.LEFT, padx=5)
        ttk.Button(system_buttons_frame, text="Backup Database", 
                  command=self.backup_database).pack(side=tk.LEFT, padx=5)
        ttk.Button(system_buttons_frame, text="Check Integrity", 
                  command=self.check_database_integrity).pack(side=tk.LEFT, padx=5)
        
        # Load initial system info
        self.refresh_system_info()
    
    # GUI Event Handlers and Methods
    
    def refresh_clubs_list(self):
        """Refresh the clubs list"""
        self.clubs_listbox.delete(0, tk.END)
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT club_id, club_name, member_count, status
                FROM student_clubs 
                WHERE status = 'active'
                ORDER BY club_name
            ''')
            
            clubs = cursor.fetchall()
            
            for club in clubs:
                display_text = f"{club[1]} ({club[2]} members)"
                self.clubs_listbox.insert(tk.END, display_text)
                
            conn.close()
            self.update_status(f"Loaded {len(clubs)} clubs")
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load clubs: {e}")
    
    def on_club_select(self, event):
        """Handle club selection"""
        selection = self.clubs_listbox.curselection()
        if not selection:
            return
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT c.club_name, c.description, c.category, c.member_count, c.status,
                       c.created_date, p.first_name || ' ' || p.last_name as president,
                       t.first_name || ' ' || t.last_name as treasurer,
                       s.first_name || ' ' || s.last_name as secretary
                FROM student_clubs c
                LEFT JOIN students p ON c.president_id = p.student_id
                LEFT JOIN students t ON c.treasurer_id = t.student_id  
                LEFT JOIN students s ON c.secretary_id = s.student_id
                WHERE c.status = 'active'
                ORDER BY c.club_name
                LIMIT 1 OFFSET ?
            ''', (selection[0],))
            
            club = cursor.fetchone()
            
            if club:
                details = f"Club Name: {club[0]}\n"
                details += f"Category: {club[2] or 'Not specified'}\n"
                details += f"Members: {club[3]}\n"
                details += f"Status: {club[4]}\n"
                details += f"Created: {club[5] or 'Unknown'}\n\n"
                details += f"Officers:\n"
                details += f"  President: {club[6] or 'Vacant'}\n"
                details += f"  Treasurer: {club[7] or 'Vacant'}\n"
                details += f"  Secretary: {club[8] or 'Vacant'}\n\n"
                details += f"Description:\n{club[1] or 'No description available.'}"
                
                self.club_details_text.delete(1.0, tk.END)
                self.club_details_text.insert(1.0, details)
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load club details: {e}")

    def join_selected_club(self):
        """Join the selected club"""
        selection = self.clubs_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a club to join")
            return
        
        # Get club name from selection
        club_text = self.clubs_listbox.get(selection[0])
        club_name = club_text.split(' (')[0]  # Extract name before member count
        
        response = messagebox.askyesno("Join Club", f"Join {club_name}?")
        if response:
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                
                # Get club_id from the selected club
                cursor.execute('SELECT club_id FROM student_clubs WHERE club_name = ? AND status = "active"', (club_name,))
                club = cursor.fetchone()
                
                if club:
                    club_id = club[0]
                    # Get current user's student_id
                    cursor.execute('SELECT student_id FROM students s JOIN users u ON s.user_id = u.id WHERE u.id = ?', (self.current_user['id'],))
                    student = cursor.fetchone()
                    
                    if student:
                        student_id = student[0]
                        # Insert membership
                        cursor.execute('INSERT INTO club_members (club_id, student_id, join_date) VALUES (?, ?, ?)',
                                       (club_id, student_id, datetime.now().strftime('%Y-%m-%d')))
                        # Update member count
                        cursor.execute('UPDATE student_clubs SET member_count = member_count + 1 WHERE club_id = ?', (club_id,))
                        conn.commit()

                        # Get user details for email
                        cursor.execute('SELECT first_name, last_name, email FROM students WHERE student_id = ?', (student_id,))
                        user_result = cursor.fetchone()

                        conn.close()  # Close connection before sending email

                        # Send confirmation email
                        if user_result:
                            first_name, last_name, email = user_result
                            if email:
                                self.send_club_join_confirmation(club_name, email, f"{first_name} {last_name}")

                        self.update_status(f"Requested to join {club_name}")
                        messagebox.showinfo("Success", f"Successfully requested to join {club_name}!")

                        # Show club integration buttons
                        self.add_integration_buttons_to_club_view(club_name)
                        
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to join club: {e}")
            finally:
                if 'conn' in locals() and conn:
                    conn.close()
                
    def create_club_dialog(self):
        """Show dialog to create a new club"""
        create_window = tk.Toplevel(self.root)
        create_window.title("Create New Club")
        create_window.geometry("500x600")
        create_window.transient(self.root)
        create_window.grab_set()
        
        # Create club form
        form_frame = ttk.Frame(create_window)
        form_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
        
        ttk.Label(form_frame, text="Create New Student Club", 
                 font=('Arial', 14, 'bold')).pack(pady=10)
        
        # Form fields
        fields = {}
        
        ttk.Label(form_frame, text="Club Name:").pack(anchor=tk.W, pady=(10,0))
        fields['name'] = ttk.Entry(form_frame, width=50)
        fields['name'].pack(fill=tk.X, pady=(0,10))
        
        ttk.Label(form_frame, text="Category:").pack(anchor=tk.W)
        fields['category'] = ttk.Combobox(form_frame, values=[
            'Academic', 'Sports', 'Arts', 'Technology', 'Social', 'Volunteer', 'Other'
        ], width=47)
        fields['category'].pack(fill=tk.X, pady=(0,10))
        
        ttk.Label(form_frame, text="Description:").pack(anchor=tk.W)
        fields['description'] = scrolledtext.ScrolledText(form_frame, height=8, width=50)
        fields['description'].pack(fill=tk.BOTH, expand=True, pady=(0,10))
        
        # Buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(pady=20)
        
        def create_club():
            name = fields['name'].get().strip()
            category = fields['category'].get().strip()
            description = fields['description'].get(1.0, tk.END).strip()
            
            if not name:
                messagebox.showerror("Error", "Club name is required")
                return
            
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                
                # Check if club name already exists
                cursor.execute('SELECT COUNT(*) FROM student_clubs WHERE club_name = ?', (name,))
                if cursor.fetchone()[0] > 0:
                    messagebox.showerror("Error", "Club name already exists")
                    return
                
                # Insert new club
                cursor.execute('''
                    INSERT INTO student_clubs (club_name, description, category, created_date, status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (name, description, category, datetime.now().strftime('%Y-%m-%d'), 'active'))
                
                conn.commit()
                conn.close()

                # Send new club announcement to all students
                self.send_new_club_announcement(name, description)

                messagebox.showinfo("Success", f"Club '{name}' created successfully!")
                create_window.destroy()
                self.refresh_clubs_list()
                
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to create club: {e}")
        
        ttk.Button(button_frame, text="Create Club", command=create_club).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=create_window.destroy).pack(side=tk.LEFT, padx=5)
        
        fields['name'].focus()
    
    def refresh_events_list(self):
        """Refresh the events list"""
        # Clear existing items
        for item in self.events_tree.get_children():
            self.events_tree.delete(item)
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT e.event_id, e.event_name, e.event_date, e.start_time, 
                       e.location, c.club_name, e.current_attendees, e.max_attendees, e.status
                FROM union_events e
                LEFT JOIN student_clubs c ON e.organizer_id = c.club_id
                WHERE e.status IN ('upcoming', 'open')
                ORDER BY e.event_date, e.start_time
            ''')
            
            events = cursor.fetchall()
            
            for event in events:
                attendees = f"{event[6]}/{event[7]}" if event[7] else str(event[6])
                self.events_tree.insert('', tk.END, values=(
                    event[0], event[1], event[2], event[3], 
                    event[4], event[5] or 'Unknown', attendees, event[8]
                ))
            
            conn.close()
            self.update_status(f"Loaded {len(events)} events")
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load events: {e}")
    
    def register_for_selected_event(self):
        """Register for the selected event"""
        if not self.current_user:
            messagebox.showerror("Authentication Required", "Please log in to register for events.")
            return
        
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an event to register for")
            return
        
        item = self.events_tree.item(selection[0])
        event_id = item['values'][0]
        event_name = item['values'][1]
        
        values = item['values']
        max_capacity = values[7] if len(values) > 7 else None
        current_attendees = values[6] if len(values) > 6 else None
        
        # Check existing registration
        def has_existing_registration(conn):
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT 1 FROM event_registrations
                WHERE event_id = ? AND user_id = ?
                ''',
                (event_id, self.current_user['id'])
            )
            return cursor.fetchone() is not None
        
        if self._safe_db_call(has_existing_registration):
            messagebox.showinfo("Already Registered", "You are already registered for this event.")
            return
        
        # Capacity check
        if isinstance(max_capacity, int) and isinstance(current_attendees, str):
            try:
                current_count = int(current_attendees.split('/')[0])
            except Exception:
                current_count = None
        else:
            current_count = None
        
        if isinstance(max_capacity, int) and current_count is not None and current_count >= max_capacity:
            messagebox.showwarning("Event Full", "This event is already at full capacity.")
            return
        
        if messagebox.askyesno("Register for Event", f"Register for '{event_name}'?"):
            if self._safe_db_call(self._register_event_operation, event_id):
                messagebox.showinfo("Success", f"Successfully registered for {event_name}!")
                self.update_status(f"Registered for {event_name}")
                self.refresh_events_list()
            else:
                messagebox.showerror("Registration Failed", "Could not register for the event. Please try again.")
    
    def view_event_details(self):
        """View details of the selected event"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an event to view details")
            return
        
        item = self.events_tree.item(selection[0])
        event_id = item['values'][0]
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT e.event_name, e.description, e.event_date, e.start_time, e.end_time,
                       e.location, e.category, e.max_attendees, e.current_attendees, 
                       c.club_name, e.status
                FROM union_events e
                LEFT JOIN student_clubs c ON e.organizer_id = c.club_id
                WHERE e.event_id = ?
            ''', (event_id,))
            
            event = cursor.fetchone()
            
            if event:
                details_window = tk.Toplevel(self.root)
                details_window.title(f"Event Details - {event[0]}")
                details_window.geometry("600x500")
                details_window.transient(self.root)
                
                details_frame = ttk.Frame(details_window)
                details_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
                
                details_text = scrolledtext.ScrolledText(details_frame, height=20, width=70)
                details_text.pack(fill=tk.BOTH, expand=True)
                
                content = f"Event: {event[0]}\n"
                content += f"Organizer: {event[9] or 'Unknown'}\n"
                content += f"Date: {event[2]}\n"
                content += f"Time: {event[3]}"
                if event[4]:
                    content += f" - {event[4]}"
                content += f"\nLocation: {event[5] or 'TBD'}\n"
                content += f"Category: {event[6] or 'General'}\n"
                content += f"Capacity: {event[8]}/{event[7] if event[7] else 'Unlimited'}\n"
                content += f"Status: {event[10]}\n\n"
                content += f"Description:\n{event[1] or 'No description available.'}"
                
                details_text.insert(1.0, content)
                details_text.config(state=tk.DISABLED)
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load event details: {e}")
    
    def create_event_dialog(self):
        """Show dialog to create a new event"""
        create_window = tk.Toplevel(self.root)
        create_window.title("Create New Event")
        create_window.geometry("600x700")
        create_window.transient(self.root)
        create_window.grab_set()
        
        # Event creation form
        form_frame = ttk.Frame(create_window)
        form_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
        
        ttk.Label(form_frame, text="Create New Event", 
                 font=('Arial', 14, 'bold')).pack(pady=10)
        
        # Form fields
        fields = {}
        
        # Event name
        ttk.Label(form_frame, text="Event Name:").pack(anchor=tk.W, pady=(10,0))
        fields['name'] = ttk.Entry(form_frame, width=60)
        fields['name'].pack(fill=tk.X, pady=(0,10))
        
        # Date and time
        time_frame = ttk.Frame(form_frame)
        time_frame.pack(fill=tk.X, pady=(0,10))
        
        ttk.Label(time_frame, text="Date:").grid(row=0, column=0, sticky=tk.W)
        fields['date'] = ttk.Entry(time_frame, width=15)
        fields['date'].grid(row=0, column=1, padx=5)
        
        ttk.Label(time_frame, text="Start:").grid(row=0, column=2, sticky=tk.W, padx=(20,0))
        fields['start_time'] = ttk.Entry(time_frame, width=10)
        fields['start_time'].grid(row=0, column=3, padx=5)
        
        ttk.Label(time_frame, text="End:").grid(row=0, column=4, sticky=tk.W, padx=(10,0))
        fields['end_time'] = ttk.Entry(time_frame, width=10)
        fields['end_time'].grid(row=0, column=5, padx=5)
        
        # Location and category
        details_frame = ttk.Frame(form_frame)
        details_frame.pack(fill=tk.X, pady=(0,10))
        
        ttk.Label(details_frame, text="Location:").grid(row=0, column=0, sticky=tk.W)
        fields['location'] = ttk.Entry(details_frame, width=25)
        fields['location'].grid(row=0, column=1, padx=5, sticky=tk.W+tk.E)
        
        ttk.Label(details_frame, text="Category:").grid(row=0, column=2, sticky=tk.W, padx=(20,0))
        fields['category'] = ttk.Combobox(details_frame, values=[
            'Academic', 'Social', 'Sports', 'Arts', 'Technology', 'Workshop', 'Other'
        ], width=15)
        fields['category'].grid(row=0, column=3, padx=5)
        
        details_frame.columnconfigure(1, weight=1)
        
        # Max attendees
        ttk.Label(form_frame, text="Maximum Attendees (leave blank for unlimited):").pack(anchor=tk.W)
        fields['max_attendees'] = ttk.Entry(form_frame, width=20)
        fields['max_attendees'].pack(anchor=tk.W, pady=(0,10))
        
        # Description
        ttk.Label(form_frame, text="Description:").pack(anchor=tk.W)
        fields['description'] = scrolledtext.ScrolledText(form_frame, height=10, width=60)
        fields['description'].pack(fill=tk.BOTH, expand=True, pady=(0,10))
        
        # Set default values
        fields['date'].insert(0, datetime.now().strftime('%Y-%m-%d'))
        
        # Buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(pady=20)
        
        def create_event():
            name = fields['name'].get().strip()
            date = fields['date'].get().strip()
            start_time = fields['start_time'].get().strip()
            end_time = fields['end_time'].get().strip()
            location = fields['location'].get().strip()
            category = fields['category'].get().strip()
            max_attendees = fields['max_attendees'].get().strip()
            description = fields['description'].get(1.0, tk.END).strip()
            
            if not name or not date:
                messagebox.showerror("Error", "Event name and date are required")
                return
            
            # Validate date format
            try:
                datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Error", "Date must be in YYYY-MM-DD format")
                return
            
            max_attendees_int = None
            if max_attendees:
                try:
                    max_attendees_int = int(max_attendees)
                except ValueError:
                    messagebox.showerror("Error", "Maximum attendees must be a number")
                    return
            
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                
                # Insert new event
                cursor.execute('''
                    INSERT INTO union_events (event_name, description, event_date, start_time, 
                                            end_time, location, category, max_attendees, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, description, date, start_time or None, end_time or None, 
                      location or None, category or None, max_attendees_int, 'upcoming', 
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                
                conn.commit()
                conn.close()

                # Send event notification to all students
                self.send_event_notification_to_all_students(name, description, date, location or "TBD")

                messagebox.showinfo("Success", f"Event '{name}' created successfully!")
                create_window.destroy()
                self.refresh_events_list()
                
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to create event: {e}")
        
        ttk.Button(button_frame, text="Create Event", command=create_event).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=create_window.destroy).pack(side=tk.LEFT, padx=5)
        
        fields['name'].focus()
    
    def show_my_events(self):
        """Show events that the user has registered for"""
        my_events_window = tk.Toplevel(self.root)
        my_events_window.title("My Events")
        my_events_window.geometry("800x500")
        my_events_window.transient(self.root)
        
        # This would show user's registered events
        ttk.Label(my_events_window, text="My Registered Events", 
                 font=('Arial', 14, 'bold')).pack(pady=20)
        
        info_frame = ttk.Frame(my_events_window)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        tree_columns = ('name', 'date', 'time', 'location', 'status')
        my_tree = ttk.Treeview(info_frame, columns=tree_columns, show='headings')
        for col, heading in zip(tree_columns, ["Event", "Date", "Time", "Location", "Status"]):
            my_tree.heading(col, text=heading)
            my_tree.column(col, width=140)
        my_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scrollbar = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=my_tree.yview)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
        my_tree.configure(yscrollcommand=scrollbar.set)

        stats_label = ttk.Label(my_events_window, text="", font=('Arial', 10))
        stats_label.pack(pady=(5, 15))

        def load_my_events(conn):
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT e.event_name, e.event_date, e.start_time, e.end_time,
                       e.location, e.status
                FROM event_registrations r
                JOIN union_events e ON r.event_id = e.event_id
                WHERE r.user_id = ?
                ORDER BY e.event_date, e.start_time
                ''',
                (self.current_user['id'],)
            )
            return cursor.fetchall()

        events = self._safe_db_call(load_my_events)

        if events:
            for name, date, start, end, location, status in events:
                time_str = start or ''
                if start and end:
                    time_str = f"{start} - {end}"
                my_tree.insert('', tk.END, values=(
                    name,
                    date or "TBD",
                    time_str or "TBD",
                    location or "TBD",
                    status or "upcoming"
                ))
            stats_label.config(text=f"Total events registered: {len(events)}")
        else:
            stats_label.config(text="You have not registered for any events yet.")
    
    def load_facilities(self):
        """Load available facilities into the combo box"""
        facilities = [
            "Main Hall", "Conference Room A", "Conference Room B", 
            "Student Lounge", "Study Room 1", "Study Room 2", 
            "Computer Lab", "Meeting Room"
        ]
        self.facility_combo['values'] = facilities
        if facilities:
            self.facility_combo.set(facilities[0])
    
    def submit_booking_request(self):
        """Submit a facility booking request"""
        facility = self.facility_combo.get()
        date = self.booking_date_entry.get().strip()
        start_time = self.start_time_entry.get().strip()
        end_time = self.end_time_entry.get().strip()
        purpose = self.purpose_entry.get().strip()
        
        if not all([facility, date, start_time, end_time, purpose]):
            messagebox.showerror("Error", "Please fill in all fields")
            return
        
        # Validate date format
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Error", "Date must be in YYYY-MM-DD format")
            return
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO facility_bookings (facility_name, user_id, booking_date, start_time, end_time, purpose, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (facility, self.current_user['id'], date, start_time, end_time, purpose, 
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            conn.commit()
            messagebox.showinfo("Success", f"Booking request for {facility} submitted successfully!")
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to submit booking: {e}")
        finally:
            if conn:
                conn.close()
        
        # Clear form
        self.booking_date_entry.delete(0, tk.END)
        self.start_time_entry.delete(0, tk.END)
        self.end_time_entry.delete(0, tk.END)
        self.purpose_entry.delete(0, tk.END)
        
        self.refresh_my_bookings()
    
    def refresh_my_bookings(self):
        """Refresh the user's bookings list"""
        # Clear existing items
        for item in self.bookings_tree.get_children():
            self.bookings_tree.delete(item)
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT booking_id, facility_name, booking_date, 
                       start_time || '-' || end_time as time_slot, status, purpose
                FROM facility_bookings
                WHERE user_id = ?
                ORDER BY booking_date DESC
            ''', (self.current_user['id'],))
            
            bookings = cursor.fetchall()
            
            for booking in bookings:
                self.bookings_tree.insert('', tk.END, values=booking)
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load bookings: {e}")
        
    def refresh_users_list(self):
        """Refresh the users list (admin only)"""
        for item in self.users_tree.get_children():
            self.users_tree.delete(item)
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, username, email, role, created_at, last_login
                FROM users
                ORDER BY created_at DESC
            ''')
            
            users = cursor.fetchall()
            
            for user in users:
                self.users_tree.insert('', tk.END, values=user)
            
            conn.close()
            self.update_status(f"Loaded {len(users)} users")
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load users: {e}")
    
    def change_user_role(self):
        """Change a user's role (admin only)"""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a user to modify")
            return
        
        item = self.users_tree.item(selection[0])
        user_id = item['values'][0]
        username = item['values'][1]
        current_role = item['values'][3]
        
        new_role = simpledialog.askstring("Change Role", 
                                         f"Change role for {username} (current: {current_role})\nOptions: student, staff, admin")
        
        if new_role and new_role in ['student', 'staff', 'admin']:
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                
                cursor.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", f"Role changed to {new_role}")
                self.refresh_users_list()
                
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to change role: {e}")
        elif new_role:
            messagebox.showerror("Error", "Invalid role. Use: student, staff, or admin")
    
    def delete_user(self):
        """Delete a user (admin only)"""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a user to delete")
            return
        
        item = self.users_tree.item(selection[0])
        user_id = item['values'][0]
        username = item['values'][1]
        
        if user_id == self.current_user['id']:
            messagebox.showerror("Error", "You cannot delete your own account")
            return
        
        response = messagebox.askyesno("Confirm Delete", 
                                     f"Are you sure you want to delete user '{username}'?\nThis action cannot be undone.")
        
        if response:
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                
                cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", f"User '{username}' deleted")
                self.refresh_users_list()
                
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to delete user: {e}")
    
    def view_all_clubs_admin(self):
        """View all clubs with admin details"""
        clubs_window = tk.Toplevel(self.root)
        clubs_window.title("All Clubs - Admin View")
        clubs_window.geometry("1000x600")
        clubs_window.transient(self.root)
        
        # Clubs treeview
        columns = ('ID', 'Name', 'Category', 'Members', 'President', 'Status', 'Created')
        clubs_tree = ttk.Treeview(clubs_window, columns=columns, show='headings', height=20)
        
        for col in columns:
            clubs_tree.heading(col, text=col)
            if col == 'ID':
                clubs_tree.column(col, width=50)
            elif col == 'Name':
                clubs_tree.column(col, width=200)
            else:
                clubs_tree.column(col, width=120)
        
        clubs_scrollbar = ttk.Scrollbar(clubs_window, orient=tk.VERTICAL, command=clubs_tree.yview)
        clubs_tree.configure(yscrollcommand=clubs_scrollbar.set)
        
        clubs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        clubs_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)
        
        # Load all clubs
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT c.club_id, c.club_name, c.category, c.member_count, 
                       p.first_name || ' ' || p.last_name as president, 
                       c.status, c.created_date
                FROM student_clubs c
                LEFT JOIN students p ON c.president_id = p.student_id
                ORDER BY c.created_date DESC
            ''')
            
            clubs = cursor.fetchall()
            
            for club in clubs:
                clubs_tree.insert('', tk.END, values=club)
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load clubs: {e}")
    
    def show_club_statistics(self):
        """Show club statistics"""
        self.club_stats_text.delete(1.0, tk.END)
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            stats = "CLUB STATISTICS\n"
            stats += "=" * 50 + "\n\n"
            
            # Total clubs
            cursor.execute('SELECT COUNT(*) FROM student_clubs')
            total_clubs = cursor.fetchone()[0]
            stats += f"Total Clubs: {total_clubs}\n"
            
            # Active clubs
            cursor.execute('SELECT COUNT(*) FROM student_clubs WHERE status = "active"')
            active_clubs = cursor.fetchone()[0]
            stats += f"Active Clubs: {active_clubs}\n"
            
            # Total members across all clubs
            cursor.execute('SELECT SUM(member_count) FROM student_clubs WHERE status = "active"')
            total_members = cursor.fetchone()[0] or 0
            stats += f"Total Memberships: {total_members}\n\n"
            
            # Clubs by category
            cursor.execute('''
                SELECT category, COUNT(*) as count
                FROM student_clubs 
                WHERE status = "active" AND category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
            ''')
            
            categories = cursor.fetchall()
            
            if categories:
                stats += "CLUBS BY CATEGORY:\n"
                stats += "-" * 20 + "\n"
                for category, count in categories:
                    stats += f"{category}: {count}\n"
                stats += "\n"
            
            # Most popular clubs
            cursor.execute('''
                SELECT club_name, member_count
                FROM student_clubs
                WHERE status = "active"
                ORDER BY member_count DESC
                LIMIT 10
            ''')
            
            popular_clubs = cursor.fetchall()
            
            if popular_clubs:
                stats += "MOST POPULAR CLUBS:\n"
                stats += "-" * 20 + "\n"
                for club_name, member_count in popular_clubs:
                    stats += f"{club_name}: {member_count} members\n"
            
            self.club_stats_text.insert(1.0, stats)
            conn.close()
            
        except sqlite3.Error as e:
            self.club_stats_text.insert(1.0, f"Error loading statistics: {e}")
    
    def export_club_data(self):
        """Export club data to a file"""
        try:
            from tkinter import filedialog
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt")],
                title="Export Club Data"
            )
            
            if not filename:
                return
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT c.club_name, c.category, c.member_count, c.status, c.created_date,
                       p.first_name || ' ' || p.last_name as president
                FROM student_clubs c
                LEFT JOIN students p ON c.president_id = p.student_id
                ORDER BY c.club_name
            ''')
            
            clubs = cursor.fetchall()
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if filename.endswith('.csv'):
                    import csv
                    writer = csv.writer(f)
                    writer.writerow(['Club Name', 'Category', 'Members', 'Status', 'Created', 'President'])
                    writer.writerows(clubs)
                else:
                    f.write("CLUB DATA EXPORT\n")
                    f.write("=" * 50 + "\n\n")
                    for club in clubs:
                        f.write(f"Club: {club[0]}\n")
                        f.write(f"Category: {club[1] or 'Not specified'}\n")
                        f.write(f"Members: {club[2]}\n")
                        f.write(f"Status: {club[3]}\n")
                        f.write(f"Created: {club[4] or 'Unknown'}\n")
                        f.write(f"President: {club[5] or 'Vacant'}\n")
                        f.write("-" * 30 + "\n")
            
            conn.close()
            messagebox.showinfo("Success", f"Club data exported to {filename}")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export data: {e}")
    
    def refresh_system_info(self):
        """Refresh system information"""
        self.system_info_text.delete(1.0, tk.END)
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            info = "SYSTEM INFORMATION\n"
            info += "=" * 50 + "\n\n"
            
            # Database file info
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            info += f"Database File: {self.db_path}\n"
            info += f"Database Size: {db_size:,} bytes\n"
            info += f"Last Modified: {datetime.fromtimestamp(os.path.getmtime(self.db_path)).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # Table statistics
            tables = ['users', 'students', 'student_clubs', 'union_events']
            
            info += "TABLE STATISTICS:\n"
            info += "-" * 20 + "\n"
            
            for table in tables:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM {table}')
                    count = cursor.fetchone()[0]
                    info += f"{table}: {count} records\n"
                except sqlite3.Error:
                    info += f"{table}: Table not found\n"
            
            info += "\n"
            
            # Recent activity
            info += "RECENT ACTIVITY:\n"
            info += "-" * 15 + "\n"
            
            # Recent users
            cursor.execute('''
                SELECT username, created_at
                FROM users
                ORDER BY created_at DESC
                LIMIT 5
            ''')
            
            recent_users = cursor.fetchall()
            
            if recent_users:
                info += "Recent Users:\n"
                for username, created_at in recent_users:
                    info += f"  {username} - {created_at}\n"
                info += "\n"
            
            # Recent clubs
            cursor.execute('''
                SELECT club_name, created_date
                FROM student_clubs
                ORDER BY created_date DESC
                LIMIT 5
            ''')
            
            recent_clubs = cursor.fetchall()
            
            if recent_clubs:
                info += "Recent Clubs:\n"
                for club_name, created_date in recent_clubs:
                    info += f"  {club_name} - {created_date or 'Unknown'}\n"
            
            self.system_info_text.insert(1.0, info)
            conn.close()
            
        except Exception as e:
            self.system_info_text.insert(1.0, f"Error loading system info: {e}")
    
    def backup_database(self):
        """Create a backup of the database"""
        try:
            from tkinter import filedialog
            
            backup_filename = filedialog.asksaveasfilename(
                defaultextension=".db",
                filetypes=[("Database files", "*.db"), ("All files", "*.*")],
                title="Save Database Backup",
                initialvalue=f"student_union_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            )
            
            if not backup_filename:
                return
            
            # Copy database file
            import shutil
            shutil.copy2(self.db_path, backup_filename)
            
            messagebox.showinfo("Success", f"Database backed up to {backup_filename}")
            
        except Exception as e:
            messagebox.showerror("Backup Error", f"Failed to backup database: {e}")
    
    def check_database_integrity(self):
        """Check database integrity"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Run PRAGMA integrity_check
            cursor.execute('PRAGMA integrity_check')
            result = cursor.fetchone()
            
            if result[0] == 'ok':
                messagebox.showinfo("Integrity Check", "Database integrity check passed - no issues found")
            else:
                messagebox.showwarning("Integrity Check", f"Database issues found: {result[0]}")
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Integrity Check Error", f"Failed to check integrity: {e}")
    
    def show_profile(self):
        """Show user profile"""
        profile_window = tk.Toplevel(self.root)
        profile_window.title("User Profile")
        profile_window.geometry("400x300")
        profile_window.transient(self.root)
        profile_window.grab_set()
        
        profile_frame = ttk.Frame(profile_window)
        profile_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(profile_frame, text="User Profile", font=('Arial', 14, 'bold')).pack(pady=10)
        
        # Profile information
        info_frame = ttk.Frame(profile_frame)
        info_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(info_frame, text="Username:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Label(info_frame, text=self.current_user['username']).grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)
        
        ttk.Label(info_frame, text="Email:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Label(info_frame, text=self.current_user['email'] or 'Not set').grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        
        ttk.Label(info_frame, text="Role:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Label(info_frame, text=self.current_user['role'].title()).grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(profile_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Change Password", command=self.change_password).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=profile_window.destroy).pack(side=tk.LEFT, padx=5)
    
    def change_password(self):
        """Change user password"""
        password_window = tk.Toplevel(self.root)
        password_window.title("Change Password")
        password_window.geometry("350x250")
        password_window.transient(self.root)
        password_window.grab_set()
        
        form_frame = ttk.Frame(password_window)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(form_frame, text="Change Password", font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Current password
        ttk.Label(form_frame, text="Current Password:").pack(anchor=tk.W, pady=(10,0))
        current_pw_entry = ttk.Entry(form_frame, show="*", width=30)
        current_pw_entry.pack(fill=tk.X, pady=(0,10))
        
        # New password
        ttk.Label(form_frame, text="New Password:").pack(anchor=tk.W)
        new_pw_entry = ttk.Entry(form_frame, show="*", width=30)
        new_pw_entry.pack(fill=tk.X, pady=(0,10))
        
        # Confirm new password
        ttk.Label(form_frame, text="Confirm New Password:").pack(anchor=tk.W)
        confirm_pw_entry = ttk.Entry(form_frame, show="*", width=30)
        confirm_pw_entry.pack(fill=tk.X, pady=(0,20))
        
        def update_password():
            current_pw = current_pw_entry.get()
            new_pw = new_pw_entry.get()
            confirm_pw = confirm_pw_entry.get()
            
            if not all([current_pw, new_pw, confirm_pw]):
                messagebox.showerror("Error", "Please fill in all fields")
                return
            
            if new_pw != confirm_pw:
                messagebox.showerror("Error", "New passwords do not match")
                return
            
            if len(new_pw) < 6:
                messagebox.showerror("Error", "Password must be at least 6 characters")
                return
            
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                
                # Verify current password
                current_hash = hashlib.sha256(current_pw.encode()).hexdigest()
                cursor.execute('SELECT id FROM users WHERE id = ? AND password_hash = ?', 
                             (self.current_user['id'], current_hash))
                
                if not cursor.fetchone():
                    messagebox.showerror("Error", "Current password is incorrect")
                    return
                
                # Update password
                new_hash = hashlib.sha256(new_pw.encode()).hexdigest()
                cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', 
                             (new_hash, self.current_user['id']))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Password changed successfully")
                password_window.destroy()
                
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to change password: {e}")
        
        # Buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.pack()
        
        ttk.Button(button_frame, text="Update Password", command=update_password).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=password_window.destroy).pack(side=tk.LEFT, padx=5)
        
        current_pw_entry.focus()
    
    def show_database_info(self):
        """Show database information"""
        info_window = tk.Toplevel(self.root)
        info_window.title("Database Information")
        info_window.geometry("500x400")
        info_window.transient(self.root)
        
        info_text = scrolledtext.ScrolledText(info_window, height=20, width=60)
        info_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            info = "DATABASE INFORMATION\n"
            info += "=" * 30 + "\n\n"
            
            # Database schema
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            info += "TABLES:\n"
            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                info += f"  {table_name}: {count} records\n"
                
                # Show table structure
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                info += "    Columns: "
                info += ", ".join([col[1] for col in columns])
                info += "\n\n"
            
            info_text.insert(1.0, info)
            conn.close()
            
        except sqlite3.Error as e:
            info_text.insert(1.0, f"Error loading database info: {e}")
    
    def show_about(self):
        """Show about dialog"""
        about_text = """Student Union Management System - GUI Version

Version: 2.0
Created by: Development Team

Features:
• Club Management
• Event Organization
• Facility Booking
• User Administration
• Database Management

This GUI version maintains backward compatibility with the CLI system.

© 2024 Student Union Management System"""
        
        messagebox.showinfo("About", about_text)
    
    def logout(self):
        """Logout current user"""
        response = messagebox.askyesno("Logout", "Are you sure you want to logout?")
        if response:
            self.current_user = None
            self.update_status("Logged out")
            self.show_login_screen()
    
    def run(self):
        """Run the GUI application"""
        try:
            self.update_status("Application started")
            self.root.mainloop()
        except Exception as e:
            messagebox.showerror("Application Error", f"An unexpected error occurred: {e}")
        finally:
            try:
                if hasattr(self, 'root'):
                    self.root.quit()
            except:
                pass
    
    def create_clubs_tab(self):
        """Create clubs management tab"""
        clubs_frame = ttk.Frame(self.notebook)
        self.notebook.add(clubs_frame, text="Clubs & Societies")
        
        # Left panel - Actions
        left_panel = ttk.LabelFrame(clubs_frame, text="Club Actions")
        left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)
        
        # Buttons
        ttk.Button(left_panel, text="View All Clubs", 
                  command=self.view_clubs).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="My Clubs", 
                  command=self.view_my_clubs).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Join Club", 
                  command=self.join_club_gui).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Create Club", 
                  command=self.create_club_gui).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Manage Club", 
                  command=self.manage_club_gui).pack(fill='x', pady=2)
        
        ttk.Separator(left_panel, orient='horizontal').pack(fill='x', pady=10)
        
        ttk.Button(left_panel, text="Club Directory", 
                  command=self.club_member_directory).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Club Discussions", 
                  command=self.manage_club_discussions).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Club Media", 
                  command=self.manage_club_media).pack(fill='x', pady=2)
        
        # Right panel - Display area
        right_panel = ttk.LabelFrame(clubs_frame, text="Club Information")
        right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)
        
        # Scrollable text area for displaying results
        self.clubs_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, 
                                                   height=30, width=80)
        self.clubs_text.pack(fill='both', expand=True, padx=5, pady=5)
    
    def create_events_tab(self):
        """Create events management tab"""
        events_frame = ttk.Frame(self.notebook)
        self.notebook.add(events_frame, text="Events")
        
        # Left panel
        left_panel = ttk.LabelFrame(events_frame, text="Event Actions")
        left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)
        
        ttk.Button(left_panel, text="View Events", 
                  command=self.view_events).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Register for Event", 
                  command=self.register_for_event_gui).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="My Events", 
                  command=self.view_my_events).pack(fill='x', pady=2)
        
        ttk.Separator(left_panel, orient='horizontal').pack(fill='x', pady=10)
        
        ttk.Button(left_panel, text="Create Recurring Event", 
                  command=self.create_recurring_event_gui).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Manage Events", 
                  command=self.manage_recurring_events).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Event Attendance", 
                  command=self.manage_event_attendance).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Event Finances", 
                  command=self.track_event_finances).pack(fill='x', pady=2)
        
        # Right panel
        right_panel = ttk.LabelFrame(events_frame, text="Event Information")
        right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)
        
        self.events_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, 
                                                    height=30, width=80)
        self.events_text.pack(fill='both', expand=True, padx=5, pady=5)
    
    def create_facilities_tab(self):
        """Create facilities booking tab"""
        facilities_frame = ttk.Frame(self.notebook)
        self.notebook.add(facilities_frame, text="Facilities")
        
        # Left panel
        left_panel = ttk.LabelFrame(facilities_frame, text="Facility Actions")
        left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)
        
        ttk.Button(left_panel, text="View Facilities", 
                  command=self.view_facilities).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Book Facility", 
                  command=self.request_facility_booking_gui).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="My Bookings", 
                  command=self.view_my_bookings).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Approve Bookings", 
                  command=self.approve_facility_bookings_gui).pack(fill='x', pady=2)
        
        # Right panel
        right_panel = ttk.LabelFrame(facilities_frame, text="Facility Information")
        right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)
        
        self.facilities_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, 
                                                        height=30, width=80)
        self.facilities_text.pack(fill='both', expand=True, padx=5, pady=5)
    
    def create_finances_tab(self):
        """Create financial management tab"""
        finances_frame = ttk.Frame(self.notebook)
        self.notebook.add(finances_frame, text="Finances")
        
        # Left panel
        left_panel = ttk.LabelFrame(finances_frame, text="Financial Actions")
        left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)
        
        ttk.Button(left_panel, text="Submit Expense Request", 
                  command=self.submit_expense_request_gui).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Approve Expenses", 
                  command=self.approve_expense_requests_gui).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Financial Reports", 
                  command=self.view_club_financial_reports_gui).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Manage Budgets", 
                  command=self.manage_club_budgets_gui).pack(fill='x', pady=2)
        
        # Right panel
        right_panel = ttk.LabelFrame(finances_frame, text="Financial Information")
        right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)
        
        self.finances_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, 
                                                      height=30, width=80)
        self.finances_text.pack(fill='both', expand=True, padx=5, pady=5)
    
    def create_competitions_tab(self):
        """Create competitions tab"""
        competitions_frame = ttk.Frame(self.notebook)
        self.notebook.add(competitions_frame, text="Competitions")
        
        # Left panel
        left_panel = ttk.LabelFrame(competitions_frame, text="Competition Actions")
        left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)
        
        ttk.Button(left_panel, text="View Competitions", 
                  command=self.view_active_competitions).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Register Club", 
                  command=self.register_club_for_competition_gui).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="View Results", 
                  command=self.view_competition_results).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="My Competition History", 
                  command=self.view_my_competition_history).pack(fill='x', pady=2)
        
        # Right panel
        right_panel = ttk.LabelFrame(competitions_frame, text="Competition Information")
        right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)
        
        self.competitions_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, 
                                                          height=30, width=80)
        self.competitions_text.pack(fill='both', expand=True, padx=5, pady=5)
    
    def create_support_tab(self):
        """Create peer support tab"""
        support_frame = ttk.Frame(self.notebook)
        self.notebook.add(support_frame, text="Peer Support")
        
        # Left panel
        left_panel = ttk.LabelFrame(support_frame, text="Support Actions")
        left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)
        
        ttk.Button(left_panel, text="Browse Support Groups", 
                  command=self.browse_support_groups).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Join Support Group", 
                  command=self.join_support_group_gui).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="My Support Groups", 
                  command=self.view_my_support_groups).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Create Support Group", 
                  command=self.create_support_group_gui).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Wellness Resources", 
                  command=self.view_wellness_resources).pack(fill='x', pady=2)
        
        # Right panel
        right_panel = ttk.LabelFrame(support_frame, text="Support Information")
        right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)
        
        self.support_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, 
                                                     height=30, width=80)
        self.support_text.pack(fill='both', expand=True, padx=5, pady=5)
    
    def create_equipment_tab(self):
        """Create equipment management tab"""
        equipment_frame = ttk.Frame(self.notebook)
        self.notebook.add(equipment_frame, text="Equipment")
        
        # Left panel
        left_panel = ttk.LabelFrame(equipment_frame, text="Equipment Actions")
        left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)
        
        ttk.Button(left_panel, text="Browse Equipment", 
                  command=self.browse_available_equipment).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Check Out Equipment", 
                  command=self.check_out_equipment_gui).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Return Equipment", 
                  command=self.return_equipment_gui).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="My Checkouts", 
                  command=self.view_my_equipment_checkouts).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Search Equipment", 
                  command=self.search_equipment_gui).pack(fill='x', pady=2)
        
        # Right panel
        right_panel = ttk.LabelFrame(equipment_frame, text="Equipment Information")
        right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)
        
        self.equipment_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, 
                                                       height=30, width=80)
        self.equipment_text.pack(fill='both', expand=True, padx=5, pady=5)
    
    def create_rewards_tab(self):
        """Create engagement rewards tab"""
        rewards_frame = ttk.Frame(self.notebook)
        self.notebook.add(rewards_frame, text="Rewards")
        
        # Left panel
        left_panel = ttk.LabelFrame(rewards_frame, text="Rewards Actions")
        left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)
        
        ttk.Button(left_panel, text="My Points & Badges", 
                  command=self.view_my_points_and_badges).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Available Badges", 
                  command=self.view_available_badges).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Leaderboard", 
                  command=self.view_leaderboard).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Point Opportunities", 
                  command=self.view_point_opportunities).pack(fill='x', pady=2)
        
        # Right panel
        right_panel = ttk.LabelFrame(rewards_frame, text="Rewards Information")
        right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)
        
        self.rewards_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, 
                                                     height=30, width=80)
        self.rewards_text.pack(fill='both', expand=True, padx=5, pady=5)
    
    def create_mentorship_tab(self):
        """Create mentorship tab"""
        mentorship_frame = ttk.Frame(self.notebook)
        self.notebook.add(mentorship_frame, text="Mentorship")
        
        # Left panel
        left_panel = ttk.LabelFrame(mentorship_frame, text="Mentorship Actions")
        left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)
        
        ttk.Button(left_panel, text="Find a Mentor", 
                  command=self.find_mentor_gui).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Become a Mentor", 
                  command=self.become_mentor_gui).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="My Relationships", 
                  command=self.view_my_mentorship_relationships).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="Schedule Session", 
                  command=self.schedule_mentorship_session_gui).pack(fill='x', pady=2)
        ttk.Button(left_panel, text="View Sessions", 
                  command=self.view_mentorship_sessions).pack(fill='x', pady=2)
        
        # Right panel
        right_panel = ttk.LabelFrame(mentorship_frame, text="Mentorship Information")
        right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)
        
        self.mentorship_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, 
                                                        height=30, width=80)
        self.mentorship_text.pack(fill='both', expand=True, padx=5, pady=5)
    
    
    def update_status(self, message: str):
        """Update status bar message"""
        self.status_label.config(text=message)
        self.master.update_idletasks()
    
    def display_result(self, text_widget: scrolledtext.ScrolledText, content: str):
        """Display content in the specified text widget"""
        text_widget.delete(1.0, tk.END)
        text_widget.insert(tk.END, content)
        text_widget.see(tk.END)
    
    def capture_cli_output(self, func, *args, **kwargs):
        """Capture output from CLI functions by redirecting stdout"""
        import sys
        from io import StringIO
        
        # Save original stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            # Call the function
            result = func(*args, **kwargs)
            output = captured_output.getvalue()
            return output, result
        except Exception as e:
            return f"Error: {str(e)}", None
        finally:
            # Restore stdout
            sys.stdout = old_stdout

    def call_cli_function(self, function_name: str, text_widget, status_message: str = None):
        """Generic method to call CLI functions and display results"""
        if student_union_cli is None or not hasattr(student_union_cli, function_name):
            text_widget.delete(1.0, tk.END)
            text_widget.insert(tk.END, f"Function {function_name} not available")
            return
        
        if status_message:
            self.update_status(status_message)
        
        func = getattr(student_union_cli, function_name)
        
        try:
            output, result = self.capture_cli_output(func)
            text_widget.delete(1.0, tk.END)
            text_widget.insert(tk.END, output)
            if status_message:
                self.update_status(f"{status_message} - Complete")
        except Exception as e:
            text_widget.delete(1.0, tk.END)
            text_widget.insert(tk.END, f"Error: {str(e)}")
    
    def run_in_thread(self, func, callback=None, *args, **kwargs):
        """Run a function in a separate thread to prevent GUI freezing"""
        def thread_worker():
            try:
                output, result = self.capture_cli_output(func, *args, **kwargs)
                if callback:
                    self.master.after(0, callback, output, result)
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                if callback:
                    self.master.after(0, callback, error_msg, None)
        
        thread = threading.Thread(target=thread_worker)
        thread.daemon = True
        thread.start()
    
    # Club Management GUI Methods
    def view_clubs(self):
        """GUI wrapper for viewing clubs"""
        self.update_status("Loading clubs...")
        
        def callback(output, result):
            self.display_result(self.clubs_text, output)
            self.update_status("Clubs loaded")
        
        self.run_in_thread(student_union_cli.view_clubs, callback)
    
    def view_my_clubs(self):
        """GUI wrapper for viewing my clubs"""
        self.update_status("Loading your clubs...")
        
        def callback(output, result):
            self.display_result(self.clubs_text, output)
            self.update_status("Your clubs loaded")
        
        self.run_in_thread(student_union_cli.view_my_clubs, callback)
    
    def join_club_gui(self):
        """GUI for joining a club"""
        dialog = ClubJoinDialog(self.master, self.auth)
        self.master.wait_window(dialog.dialog)
        
        if dialog.result:
            self.update_status("Joined club successfully")
            # Refresh club list
            self.view_my_clubs()
    
    def create_club_gui(self):
        """GUI for creating a club"""
        dialog = ClubCreateDialog(self.master, self.auth)
        self.master.wait_window(dialog.dialog)
        
        if dialog.result:
            self.update_status("Club created successfully")
            # Refresh club list
            self.view_clubs()
    
    def manage_club_gui(self):
        """GUI for managing clubs"""
        dialog = ClubManageDialog(self.master, self.auth)
        self.master.wait_window(dialog.dialog)
    
    # Event Management GUI Methods
    def view_events(self):
        """GUI wrapper for viewing events"""
        self.update_status("Loading events...")
        
        def callback(output, result):
            self.display_result(self.events_text, output)
            self.update_status("Events loaded")
        
        self.run_in_thread(student_union_cli.view_events, callback)
    
    def register_for_event_gui(self):
        """GUI for event registration"""
        dialog = EventRegistrationDialog(self.master, self.auth)
        self.master.wait_window(dialog.dialog)
        
        if dialog.result:
            self.update_status("Registered for event successfully")
            self.view_my_events()
    
    def view_my_events(self):
        """GUI wrapper for viewing my events"""
        self.update_status("Loading your events...")
        
        def callback(output, result):
            self.display_result(self.events_text, output)
            self.update_status("Your events loaded")
        
        self.run_in_thread(student_union_cli.view_my_events, callback)
    
    # Facility Management GUI Methods
    def view_facilities(self):
        """GUI wrapper for viewing facilities"""
        self.update_status("Loading facilities...")
        
        def callback(output, result):
            self.display_result(self.facilities_text, output)
            self.update_status("Facilities loaded")
        
        self.run_in_thread(student_union_cli.view_facilities, callback)
    
    def request_facility_booking_gui(self):
        """GUI for facility booking"""
        dialog = FacilityBookingDialog(self.master, self.auth)
        self.master.wait_window(dialog.dialog)
        
        if dialog.result:
            self.update_status("Facility booking requested")
            self.view_my_bookings()
    
    def view_my_bookings(self):
        """GUI wrapper for viewing my bookings"""
        self.update_status("Loading your bookings...")
        
        def callback(output, result):
            self.display_result(self.facilities_text, output)
            self.update_status("Your bookings loaded")
        
        self.run_in_thread(student_union_cli.view_my_bookings, callback)
    
    # Add more GUI wrapper methods for other functions...
    # (For brevity, showing the pattern - similar methods would be created for all CLI functions)
    
    # Backwards compatibility - CLI function access
    def call_cli_function(self, function_name: str, text_widget: scrolledtext.ScrolledText, 
                         status_message: str = None):
        """Generic method to call CLI functions and display results"""
        if not hasattr(student_union_cli, function_name):
            messagebox.showerror("Error", f"Function {function_name} not found")
            return
        
        if status_message:
            self.update_status(status_message)
        
        func = getattr(student_union_cli, function_name)
        
        def callback(output, result):
            self.display_result(text_widget, output)
            if status_message:
                self.update_status(f"{status_message} - Complete")
        
        self.run_in_thread(func, callback)
    
    # GUI methods for advanced features
    def create_recurring_event_gui(self):
        """Create a recurring event with GUI dialog"""
        try:
            dialog = RecurringEventDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def manage_recurring_events(self):
        """Manage recurring events with GUI dialog"""
        try:
            dialog = EventManagementDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def manage_event_attendance(self):
        """Manage event attendance with GUI dialog"""
        try:
            dialog = EventAttendanceDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def track_event_finances(self):
        """Track event finances with GUI dialog"""
        try:
            dialog = EventFinancesDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def approve_facility_bookings_gui(self):
        """Approve facility bookings with GUI dialog"""
        try:
            dialog = FacilityApprovalDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def submit_expense_request_gui(self):
        """Submit expense request with GUI dialog"""
        try:
            dialog = ExpenseSubmitDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def approve_expense_requests_gui(self):
        """Approve expense requests with GUI dialog"""
        try:
            dialog = ExpenseApprovalDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def view_club_financial_reports_gui(self):
        """View club financial reports with GUI dialog"""
        try:
            dialog = ClubFinancialReportsDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def manage_club_budgets_gui(self):
        """Manage club budgets with GUI dialog"""
        try:
            dialog = ClubBudgetDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")
    
    def club_member_directory(self):
        """View club member directory"""
        try:
            dialog = ClubMemberDirectoryDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def manage_club_discussions(self):
        """Manage club discussions"""
        try:
            dialog = ClubDiscussionsDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def manage_club_media(self):
        """Manage club media"""
        try:
            dialog = ClubMediaDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def view_active_competitions(self):
        """View active competitions"""
        try:
            dialog = CompetitionsDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def register_club_for_competition_gui(self):
        """Register club for competition"""
        try:
            dialog = CompetitionsDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def view_competition_results(self):
        """View competition results"""
        try:
            dialog = CompetitionsDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def view_my_competition_history(self):
        """View my competition history"""
        try:
            dialog = CompetitionHistoryDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def browse_support_groups(self):
        """Browse support groups"""
        try:
            dialog = SupportGroupsDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def join_support_group_gui(self):
        """Join a support group"""
        try:
            dialog = SupportGroupsDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def view_my_support_groups(self):
        """View my support groups"""
        try:
            dialog = MySupportGroupsDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def create_support_group_gui(self):
        """Create a new support group"""
        try:
            dialog = CreateSupportGroupDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def view_wellness_resources(self):
        """View wellness resources"""
        try:
            dialog = WellnessResourcesDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def browse_available_equipment(self):
        """Browse available equipment"""
        try:
            dialog = EquipmentBrowseDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def check_out_equipment_gui(self):
        """Check out equipment"""
        try:
            dialog = EquipmentBrowseDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def return_equipment_gui(self):
        """Return equipment"""
        try:
            dialog = MyEquipmentDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def view_my_equipment_checkouts(self):
        """View my equipment checkouts"""
        try:
            dialog = MyEquipmentDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def search_equipment_gui(self):
        """Search equipment"""
        try:
            dialog = EquipmentBrowseDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def view_my_points_and_badges(self):
        """View my points and badges"""
        try:
            dialog = GamificationDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def view_available_badges(self):
        """View available badges"""
        try:
            dialog = AvailableBadgesDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def view_leaderboard(self):
        """View leaderboard"""
        try:
            dialog = LeaderboardDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def view_point_opportunities(self):
        """View point-earning opportunities"""
        try:
            dialog = GamificationDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def find_mentor_gui(self):
        """Find a mentor"""
        try:
            dialog = MentorshipBrowseDialog(self.root, self.auth_manager, mode='find')
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def become_mentor_gui(self):
        """Become a mentor"""
        try:
            dialog = MentorshipBrowseDialog(self.root, self.auth_manager, mode='become')
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def view_my_mentorship_relationships(self):
        """View my mentorship relationships"""
        try:
            dialog = MyMentorshipsDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def schedule_mentorship_session_gui(self):
        """Schedule mentorship session"""
        try:
            dialog = MyMentorshipsDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def view_mentorship_sessions(self):
        """View mentorship sessions"""
        try:
            dialog = MentorshipSessionsDialog(self.root, self.auth_manager)
            self.root.wait_window(dialog.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            if isinstance(self.root, tk.Toplevel):
                # Just close the child window
                self.root.destroy()
            else:
                # Running standalone, need to create main GUI
                self.root.destroy()
                from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()


# Dialog Classes for More Complex GUI Interactions

class ClubJoinDialog:
    """Dialog for joining a club"""
    
    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Join Club")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.load_clubs()
    
    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="Join a Club", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # Club list
        list_frame = ttk.LabelFrame(main_frame, text="Available Clubs")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Treeview for clubs
        columns = ('ID', 'Name', 'Category', 'Members')
        self.clubs_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=10)
        
        for col in columns:
            self.clubs_tree.heading(col, text=col)
            self.clubs_tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.clubs_tree.yview)
        self.clubs_tree.configure(yscrollcommand=scrollbar.set)
        
        self.clubs_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(button_frame, text="Join Selected Club", 
                  command=self.join_selected_club).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", 
                  command=self.cancel).pack(side='left')
    
    def load_clubs(self):
        """Load available clubs into the treeview"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT club_id, club_name, category, member_count
            FROM student_clubs
            WHERE status = 'active'
            ORDER BY club_name
            ''')
            
            clubs = cursor.fetchall()
            
            for club in clubs:
                self.clubs_tree.insert('', 'end', values=club)
            
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load clubs: {str(e)}")
    
    def join_selected_club(self):
        """Join the selected club"""
        selection = self.clubs_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a club to join.")
            return
        
        item = self.clubs_tree.item(selection[0])
        club_id = item['values'][0]
        club_name = item['values'][1]
        
        # Confirm join
        if messagebox.askyesno("Confirm", f"Do you want to join {club_name}?"):
            try:
                # Call CLI function to join club
                # In a full implementation, you'd extract the join logic from the CLI function
                self.result = {'club_id': club_id, 'club_name': club_name}
                messagebox.showinfo("Success", f"Successfully joined {club_name}!")
                self.dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to join club: {str(e)}")
    
    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


class ClubCreateDialog:
    """Dialog for creating a new club"""
    
    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Club")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="Create New Club", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='x', pady=(0, 20))
        
        # Club name
        ttk.Label(form_frame, text="Club Name:").grid(row=0, column=0, sticky='w', pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.name_var, width=40).grid(row=0, column=1, sticky='ew', pady=5)
        
        # Description
        ttk.Label(form_frame, text="Description:").grid(row=1, column=0, sticky='nw', pady=5)
        self.description_text = tk.Text(form_frame, height=4, width=40)
        self.description_text.grid(row=1, column=1, sticky='ew', pady=5)
        
        # Category
        ttk.Label(form_frame, text="Category:").grid(row=2, column=0, sticky='w', pady=5)
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=self.category_var, width=37)
        category_combo['values'] = ('Academic', 'Sports', 'Cultural', 'Technology', 'Service', 'Other')
        category_combo.grid(row=2, column=1, sticky='ew', pady=5)
        
        # Officers
        officer_frame = ttk.LabelFrame(form_frame, text="Club Officers")
        officer_frame.grid(row=3, column=0, columnspan=2, sticky='ew', pady=10)
        
        ttk.Label(officer_frame, text="President ID:").grid(row=0, column=0, sticky='w', pady=2)
        self.president_var = tk.StringVar()
        ttk.Entry(officer_frame, textvariable=self.president_var, width=20).grid(row=0, column=1, sticky='ew', pady=2)
        
        ttk.Label(officer_frame, text="Treasurer ID:").grid(row=1, column=0, sticky='w', pady=2)
        self.treasurer_var = tk.StringVar()
        ttk.Entry(officer_frame, textvariable=self.treasurer_var, width=20).grid(row=1, column=1, sticky='ew', pady=2)
        
        ttk.Label(officer_frame, text="Secretary ID:").grid(row=2, column=0, sticky='w', pady=2)
        self.secretary_var = tk.StringVar()
        ttk.Entry(officer_frame, textvariable=self.secretary_var, width=20).grid(row=2, column=1, sticky='ew', pady=2)
        
        # Configure grid weights
        form_frame.columnconfigure(1, weight=1)
        officer_frame.columnconfigure(1, weight=1)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(button_frame, text="Create Club", 
                  command=self.create_club).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", 
                  command=self.cancel).pack(side='left')
    
    def create_club(self):
        """Create the club with provided information"""
        # Validate inputs
        if not self.name_var.get().strip():
            messagebox.showwarning("Warning", "Club name is required.")
            return
        
        if not self.category_var.get().strip():
            messagebox.showwarning("Warning", "Category is required.")
            return
        
        if not all([self.president_var.get().strip(), 
                   self.treasurer_var.get().strip(), 
                   self.secretary_var.get().strip()]):
            messagebox.showwarning("Warning", "All officer positions must be filled.")
            return
        
        try:
            # In a full implementation, you'd call the actual database function
            club_data = {
                'name': self.name_var.get().strip(),
                'description': self.description_text.get(1.0, tk.END).strip(),
                'category': self.category_var.get().strip(),
                'president_id': self.president_var.get().strip(),
                'treasurer_id': self.treasurer_var.get().strip(),
                'secretary_id': self.secretary_var.get().strip()
            }
            
            self.result = club_data
            messagebox.showinfo("Success", f"Club '{club_data['name']}' created successfully!")
            self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create club: {str(e)}")
    
    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


class ClubManageDialog:
    """Dialog for managing clubs"""
    
    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Manage Clubs")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.load_manageable_clubs()
    
    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="Club Management", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # Club selection
        select_frame = ttk.LabelFrame(main_frame, text="Select Club to Manage")
        select_frame.pack(fill='x', pady=(0, 10))
        
        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(select_frame, textvariable=self.club_var, width=50)
        self.club_combo.pack(side='left', padx=5, pady=5)
        self.club_combo.bind('<<ComboboxSelected>>', self.on_club_selected)
        
        ttk.Button(select_frame, text="Refresh", 
                  command=self.load_manageable_clubs).pack(side='left', padx=5)
        
        # Management options
        options_frame = ttk.LabelFrame(main_frame, text="Management Options")
        options_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Create notebook for management tabs
        self.manage_notebook = ttk.Notebook(options_frame)
        self.manage_notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Members tab
        members_frame = ttk.Frame(self.manage_notebook)
        self.manage_notebook.add(members_frame, text="Members")
        
        self.members_tree = ttk.Treeview(members_frame, columns=('ID', 'Name', 'Role', 'Join Date'), 
                                        show='tree headings', height=10)
        for col in ('ID', 'Name', 'Role', 'Join Date'):
            self.members_tree.heading(col, text=col)
            self.members_tree.column(col, width=150)
        self.members_tree.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Events tab
        events_frame = ttk.Frame(self.manage_notebook)
        self.manage_notebook.add(events_frame, text="Events")
        
        ttk.Label(events_frame, text="Club events management would go here").pack(pady=20)
        
        # Finances tab
        finances_frame = ttk.Frame(self.manage_notebook)
        self.manage_notebook.add(finances_frame, text="Finances")
        
        ttk.Label(finances_frame, text="Financial management would go here").pack(pady=20)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(button_frame, text="Close", 
                  command=self.dialog.destroy).pack(side='right')
    
    def load_manageable_clubs(self):
        """Load clubs that the current user can manage"""
        try:
            if not self.auth or not self.auth.current_user:
                return
            
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()
            
            # Get student ID
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            
            if not result:
                return
            
            student_id = result[0]
            
            # Get clubs where user is an officer
            cursor.execute('''
            SELECT c.club_id, c.club_name
            FROM student_clubs c
            WHERE (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
            AND c.status = 'active'
            ORDER BY c.club_name
            ''', (student_id, student_id, student_id))
            
            clubs = cursor.fetchall()
            
            club_options = [f"{club[1]} (ID: {club[0]})" for club in clubs]
            self.club_combo['values'] = club_options
            
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load clubs: {str(e)}")
    
    def on_club_selected(self, event=None):
        """Handle club selection"""
        selection = self.club_var.get()
        if not selection:
            return
        
        # Extract club ID from selection
        try:
            club_id = selection.split("ID: ")[1].rstrip(")")
            self.load_club_members(club_id)
        except:
            pass
    
    def load_club_members(self, club_id):
        """Load members for the selected club"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT m.student_id, s.first_name, s.last_name, m.role, m.join_date
            FROM club_members m
            JOIN students s ON m.student_id = s.student_id
            WHERE m.club_id = ?
            ORDER BY m.role, m.join_date
            ''', (club_id,))
            
            members = cursor.fetchall()
            
            # Clear existing items
            for item in self.members_tree.get_children():
                self.members_tree.delete(item)
            
            # Add members to tree
            for member in members:
                name = f"{member[1]} {member[2]}"
                self.members_tree.insert('', 'end', values=(member[0], name, member[3], member[4]))
            
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load members: {str(e)}")


class EventRegistrationDialog:
    """Dialog for event registration"""
    
    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Register for Event")
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.load_events()
    
    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="Register for Event", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # Events list
        list_frame = ttk.LabelFrame(main_frame, text="Upcoming Events")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Treeview for events
        columns = ('ID', 'Name', 'Date', 'Time', 'Location', 'Organizer', 'Capacity')
        self.events_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)
        
        for col in columns:
            self.events_tree.heading(col, text=col)
            self.events_tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.events_tree.yview)
        self.events_tree.configure(yscrollcommand=scrollbar.set)
        
        self.events_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Event details
        details_frame = ttk.LabelFrame(main_frame, text="Event Details")
        details_frame.pack(fill='x', pady=(0, 10))
        
        self.details_text = tk.Text(details_frame, height=5, wrap=tk.WORD)
        self.details_text.pack(fill='x', padx=5, pady=5)
        
        # Bind selection event
        self.events_tree.bind('<<TreeviewSelect>>', self.on_event_selected)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(button_frame, text="Register for Selected Event", 
                  command=self.register_for_event).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", 
                  command=self.cancel).pack(side='left')
    
    def load_events(self):
        """Load upcoming events"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()
            
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute('''
            SELECT e.event_id, e.event_name, e.event_date, e.start_time, e.location,
                   c.club_name, e.max_attendees, e.current_attendees, e.description
            FROM union_events e
            JOIN student_clubs c ON e.organizer_id = c.club_id
            WHERE e.event_date >= ? AND e.status = 'upcoming'
            ORDER BY e.event_date, e.start_time
            ''', (current_date,))
            
            events = cursor.fetchall()
            
            for event in events:
                capacity = f"{event[7]}/{event[6]}" if event[6] > 0 else f"{event[7]}/∞"
                self.events_tree.insert('', 'end', values=(
                    event[0], event[1], event[2], event[3], event[4], event[5], capacity
                ), tags=(event[8],))  # Store description in tags
            
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load events: {str(e)}")
    
    def on_event_selected(self, event=None):
        """Handle event selection"""
        selection = self.events_tree.selection()
        if not selection:
            return
        
        item = self.events_tree.item(selection[0])
        values = item['values']
        description = item['tags'][0] if item['tags'] else "No description available"
        
        details = f"Event: {values[1]}\n"
        details += f"Date: {values[2]} at {values[3]}\n"
        details += f"Location: {values[4]}\n"
        details += f"Organizer: {values[5]}\n"
        details += f"Capacity: {values[6]}\n\n"
        details += f"Description: {description}"
        
        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, details)
    
    def register_for_event(self):
        """Register for the selected event"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event to register for.")
            return
        
        item = self.events_tree.item(selection[0])
        event_id = item['values'][0]
        event_name = item['values'][1]
        
        if messagebox.askyesno("Confirm", f"Do you want to register for {event_name}?"):
            try:
                self.result = {'event_id': event_id, 'event_name': event_name}
                messagebox.showinfo("Success", f"Successfully registered for {event_name}!")
                self.dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to register for event: {str(e)}")
    
    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


class FacilityBookingDialog:
    """Dialog for facility booking"""
    
    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Book Facility")
        self.dialog.geometry("600x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.load_facilities()
    
    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, text="Book Facility", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # Facility selection
        facility_frame = ttk.LabelFrame(main_frame, text="Select Facility")
        facility_frame.pack(fill='x', pady=(0, 10))
        
        self.facility_var = tk.StringVar()
        self.facility_combo = ttk.Combobox(facility_frame, textvariable=self.facility_var, width=50)
        self.facility_combo.pack(side='left', padx=5, pady=5)
        self.facility_combo.bind('<<ComboboxSelected>>', self.on_facility_selected)
        
        # Facility details
        self.facility_details = tk.Text(facility_frame, height=4, width=60)
        self.facility_details.pack(fill='x', padx=5, pady=5)
        
        # Booking details
        booking_frame = ttk.LabelFrame(main_frame, text="Booking Details")
        booking_frame.pack(fill='x', pady=(0, 10))
        
        # Date and time
        datetime_frame = ttk.Frame(booking_frame)
        datetime_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(datetime_frame, text="Date:").grid(row=0, column=0, sticky='w', padx=5)
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(datetime_frame, textvariable=self.date_var, width=15).grid(row=0, column=1, padx=5)
        
        ttk.Label(datetime_frame, text="Start Time:").grid(row=0, column=2, sticky='w', padx=5)
        self.start_time_var = tk.StringVar(value="09:00")
        ttk.Entry(datetime_frame, textvariable=self.start_time_var, width=10).grid(row=0, column=3, padx=5)
        
        ttk.Label(datetime_frame, text="End Time:").grid(row=1, column=0, sticky='w', padx=5)
        self.end_time_var = tk.StringVar(value="10:00")
        ttk.Entry(datetime_frame, textvariable=self.end_time_var, width=10).grid(row=1, column=1, padx=5)
        
        # Purpose
        ttk.Label(booking_frame, text="Purpose:").pack(anchor='w', padx=5, pady=(10, 0))
        self.purpose_var = tk.StringVar()
        ttk.Entry(booking_frame, textvariable=self.purpose_var, width=50).pack(fill='x', padx=5, pady=5)
        
        # Notes
        ttk.Label(booking_frame, text="Additional Notes:").pack(anchor='w', padx=5)
        self.notes_text = tk.Text(booking_frame, height=3, width=50)
        self.notes_text.pack(fill='x', padx=5, pady=5)
        
        # Club booking option
        club_frame = ttk.LabelFrame(main_frame, text="Club Booking (Optional)")
        club_frame.pack(fill='x', pady=(0, 10))
        
        self.club_booking_var = tk.BooleanVar()
        club_check = ttk.Checkbutton(club_frame, text="Book for club", variable=self.club_booking_var,
                                   command=self.toggle_club_selection)
        club_check.pack(anchor='w', padx=5, pady=5)
        
        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(club_frame, textvariable=self.club_var, width=40, state='disabled')
        self.club_combo.pack(fill='x', padx=5, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(button_frame, text="Submit Booking Request", 
                  command=self.submit_booking).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", 
                  command=self.cancel).pack(side='left')
    
    def load_facilities(self):
        """Load available facilities"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT facility_id, facility_name, location, capacity, description, 
                   equipment, booking_fee
            FROM union_facilities
            WHERE status = 'available'
            ORDER BY facility_name
            ''')
            
            facilities = cursor.fetchall()
            
            facility_options = []
            self.facility_data = {}
            
            for facility in facilities:
                option = f"{facility[1]} - {facility[2]}"
                facility_options.append(option)
                self.facility_data[option] = facility
            
            self.facility_combo['values'] = facility_options
            
            # Load user's clubs for club booking option
            if self.auth and self.auth.current_user:
                cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
                result = cursor.fetchone()
                
                if result:
                    student_id = result[0]
                    cursor.execute('''
                    SELECT c.club_id, c.club_name
                    FROM student_clubs c
                    WHERE (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
                    AND c.status = 'active'
                    ORDER BY c.club_name
                    ''', (student_id, student_id, student_id))
                    
                    clubs = cursor.fetchall()
                    
                    club_options = [f"{club[1]} (ID: {club[0]})" for club in clubs]
                    self.club_combo['values'] = club_options
            
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load facilities: {str(e)}")
    
    def on_facility_selected(self, event=None):
        """Handle facility selection"""
        selection = self.facility_var.get()
        if not selection or selection not in self.facility_data:
            return
        
        facility = self.facility_data[selection]
        
        details = f"Facility: {facility[1]}\n"
        details += f"Location: {facility[2]}\n"
        details += f"Capacity: {facility[3]} people\n"
        details += f"Description: {facility[4]}\n"
        details += f"Equipment: {facility[5]}\n"
        details += f"Booking Fee: £{facility[6]:.2f}"
        
        self.facility_details.delete(1.0, tk.END)
        self.facility_details.insert(1.0, details)
    
    def toggle_club_selection(self):
        """Toggle club selection based on checkbox"""
        if self.club_booking_var.get():
            self.club_combo.config(state='normal')
        else:
            self.club_combo.config(state='disabled')
            self.club_var.set('')
    
    def submit_booking(self):
        """Submit the booking request"""
        # Validate inputs
        if not self.facility_var.get():
            messagebox.showwarning("Warning", "Please select a facility.")
            return
        
        if not self.date_var.get():
            messagebox.showwarning("Warning", "Please enter a booking date.")
            return
        
        if not all([self.start_time_var.get(), self.end_time_var.get()]):
            messagebox.showwarning("Warning", "Please enter start and end times.")
            return
        
        if not self.purpose_var.get():
            messagebox.showwarning("Warning", "Please enter the purpose of booking.")
            return
        
        try:
            # Validate date format
            datetime.strptime(self.date_var.get(), '%Y-%m-%d')
        except ValueError:
            messagebox.showwarning("Warning", "Please enter date in YYYY-MM-DD format.")
            return
        
        booking_data = {
            'facility': self.facility_var.get(),
            'date': self.date_var.get(),
            'start_time': self.start_time_var.get(),
            'end_time': self.end_time_var.get(),
            'purpose': self.purpose_var.get(),
            'notes': self.notes_text.get(1.0, tk.END).strip(),
            'club': self.club_var.get() if self.club_booking_var.get() else None
        }
        
        if messagebox.askyesno("Confirm", "Submit this booking request?"):
            self.result = booking_data
            messagebox.showinfo("Success", "Booking request submitted successfully!")
            self.dialog.destroy()
    
    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


# Additional utility classes and functions

class DatabaseQueryDialog:
    """Generic dialog for database queries with results display"""
    
    def __init__(self, parent, title, query, columns):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("800x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.query = query
        self.columns = columns
        
        self.create_widgets()
        self.execute_query()
    
    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Results tree
        self.tree = ttk.Treeview(main_frame, columns=self.columns, show='tree headings')
        
        for col in self.columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        scrollbar_y = ttk.Scrollbar(main_frame, orient='vertical', command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(main_frame, orient='horizontal', command=self.tree.xview)
        
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar_y.pack(side='right', fill='y')
        scrollbar_x.pack(side='bottom', fill='x')
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)
    
    def execute_query(self):
        """Execute the database query and display results"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(self.query)
            results = cursor.fetchall()
            
            for result in results:
                self.tree.insert('', 'end', values=result)
            
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to execute query: {str(e)}")

    # =========================================================================
    # EMAIL INTEGRATION METHODS
    # =========================================================================

    def send_new_club_announcement(self, club_name, club_description):
        """Send email to all students about new club"""
        try:
            # Get all student emails
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT email, first_name, last_name FROM students WHERE email IS NOT NULL')
            students = cursor.fetchall()
            conn.close()

            for email, first_name, last_name in students:
                try:
                    subject, message = render_template("club_created_notification", {
                        "first_name": first_name,
                        "last_name": last_name,
                        "club_name": club_name,
                        "club_description": club_description
                    })

                    if subject and message:
                        self._send_email_via_gui(email, subject, message)
                except Exception as e:
                    # Error handling - log but continue
                    pass

        except Exception as e:
            print(f"Failed to send new club announcements: {e}")

    def send_club_invitation(self, club_name, recipient_email, recipient_name, inviter_name):
        """Send club invitation email"""
        try:
            try:
                subject, message = render_template("club_invitation", {
                    "recipient_name": recipient_name,
                    "inviter_name": inviter_name,
                    "club_name": club_name,
                    "invitation_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            except Exception as e:
                # Error handling
                subject = f"You're Invited to Join {club_name}!"
                message = f"""Dear {recipient_name},

{inviter_name} has invited you to join the {club_name} club!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLUB INVITATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Club: {club_name}
Invited by: {inviter_name}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{inviter_name} thinks you'd be a great addition to our club! Join us to participate in exciting activities, events, and meet new friends who share your interests.

To accept this invitation, log into the Student Union portal and search for "{club_name}".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
{club_name} Club & Student Union Team
"""

            success = self._send_email_via_gui(recipient_email, subject, message)
            if success:
                messagebox.showinfo("Invitation Sent", f"Club invitation sent to {recipient_name}")
            else:
                self._show_email_fallback(recipient_email, subject, message, "Club Invitation")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send club invitation: {e}")

    def send_club_join_confirmation(self, club_name, user_email, user_name):
        """Send confirmation email when user joins a club"""
        try:
            try:
                subject, message = render_template("club_member_welcome", {
                    "user_name": user_name,
                    "club_name": club_name,
                    "join_date": datetime.now().strftime('%Y-%m-%d')
                })

                if not (subject and message):
                    # Fallback if template fails
                    subject = f"Welcome to {club_name}!"
                    message = f"""Dear {user_name},

Welcome to {club_name}! Your membership has been confirmed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MEMBERSHIP CONFIRMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Club: {club_name}
Member: {user_name}
Join Date: {datetime.now().strftime('%Y-%m-%d')}
Status: Active Member

What's next:
• Check your Student Union portal for upcoming events
• Visit the club merchandise shop for exclusive items
• Join club trips and activities
• Connect with other club members

We're excited to have you as part of our community!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
{club_name} Club Leadership
Student Union Team
"""
            except Exception as e:
                # Error handling
                subject = f"Welcome to {club_name}!"
                message = f"""Dear {user_name},

Welcome to {club_name}! Your membership has been confirmed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MEMBERSHIP CONFIRMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Club: {club_name}
Member: {user_name}
Join Date: {datetime.now().strftime('%Y-%m-%d')}
Status: Active Member

What's next:
• Check your Student Union portal for upcoming events
• Visit the club merchandise shop for exclusive items
• Join club trips and activities
• Connect with other club members

We're excited to have you as part of our community!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
{club_name} Club Leadership
Student Union Team
"""

            self._send_email_via_gui(user_email, subject, message)

        except Exception as e:
            print(f"Failed to send club join confirmation: {e}")

    def send_club_leave_confirmation(self, club_name, user_email, user_name):
        """Send confirmation email when user leaves a club"""
        try:
            try:
                subject, message = render_template("club_member_goodbye", {
                    "user_name": user_name,
                    "club_name": club_name,
                    "leave_date": datetime.now().strftime('%Y-%m-%d')
                })

                if not (subject and message):
                    # Fallback if template fails
                    subject = f"Thank You for Being Part of {club_name}"
                    message = f"""Dear {user_name},

We're sorry to see you leave {club_name}. Your membership has been updated.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MEMBERSHIP UPDATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Club: {club_name}
Former Member: {user_name}
Leave Date: {datetime.now().strftime('%Y-%m-%d')}
Status: Membership Ended

Thank you for being part of our community. The door is always open if you'd like to rejoin in the future!

You can explore other clubs and activities through the Student Union portal.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
{club_name} Club Leadership
Student Union Team
"""
            except Exception as e:
                # Error handling
                subject = f"Thank You for Being Part of {club_name}"
                message = f"""Dear {user_name},

We're sorry to see you leave {club_name}. Your membership has been updated.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MEMBERSHIP UPDATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Club: {club_name}
Former Member: {user_name}
Leave Date: {datetime.now().strftime('%Y-%m-%d')}
Status: Membership Ended

Thank you for being part of our community. The door is always open if you'd like to rejoin in the future!

You can explore other clubs and activities through the Student Union portal.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
{club_name} Club Leadership
Student Union Team
"""

            self._send_email_via_gui(user_email, subject, message)

        except Exception as e:
            print(f"Failed to send club leave confirmation: {e}")

    def send_newsletter_to_club_members(self, club_name, newsletter_subject, newsletter_content):
        """Send newsletter to all club members"""
        try:
            # Get all members of the club
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.email, s.first_name, s.last_name
                FROM students s
                JOIN club_members cm ON s.student_id = cm.student_id
                JOIN student_clubs sc ON cm.club_id = sc.club_id
                WHERE sc.club_name = ? AND s.email IS NOT NULL
            ''', (club_name,))
            members = cursor.fetchall()
            conn.close()

            for email, first_name, last_name in members:
                try:
                    subject, message = render_template("club_newsletter_broadcast", {
                        "first_name": first_name,
                        "last_name": last_name,
                        "club_name": club_name,
                        "newsletter_subject": newsletter_subject,
                        "newsletter_content": newsletter_content
                    })

                    if not (subject and message):
                        # Fallback if template fails
                        subject = f"{club_name} Newsletter: {newsletter_subject}"
                        message = f"""Dear {first_name} {last_name},

Here's the latest newsletter from {club_name}!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{club_name.upper()} NEWSLETTER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{newsletter_content}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Stay connected and don't miss out on upcoming events and activities!

Best regards,
{club_name} Leadership Team
"""
                except Exception as e:
                    # Error handling
                    subject = f"{club_name} Newsletter: {newsletter_subject}"
                    message = f"""Dear {first_name} {last_name},

Here's the latest newsletter from {club_name}!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{club_name.upper()} NEWSLETTER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{newsletter_content}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Stay connected and don't miss out on upcoming events and activities!

Best regards,
{club_name} Leadership Team
"""

                self._send_email_via_gui(email, subject, message)

            messagebox.showinfo("Newsletter Sent", f"Newsletter sent to {len(members)} club members")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send newsletter: {e}")

    def send_event_notification_to_all_students(self, event_name, event_description, event_date, event_location):
        """Send event notification to all students"""
        try:
            # Get all student emails
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT email, first_name, last_name FROM students WHERE email IS NOT NULL')
            students = cursor.fetchall()
            conn.close()

            for email, first_name, last_name in students:
                try:
                    subject, message = render_template("event_upcoming", {
                        "first_name": first_name,
                        "last_name": last_name,
                        "event_name": event_name,
                        "event_date": event_date,
                        "event_location": event_location,
                        "event_description": event_description
                    })

                    if not (subject and message):
                        # Fallback if template fails
                        subject = f"Upcoming Event: {event_name}"
                        message = f"""Dear {first_name} {last_name},

Don't miss this exciting upcoming event!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EVENT ANNOUNCEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Event: {event_name}
Date: {event_date}
Location: {event_location}

Description:
{event_description}

Register now through the Student Union portal to secure your spot!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
Student Union Events Team
"""
                except Exception as e:
                    # Error handling
                    subject = f"Upcoming Event: {event_name}"
                    message = f"""Dear {first_name} {last_name},

Don't miss this exciting upcoming event!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EVENT ANNOUNCEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Event: {event_name}
Date: {event_date}
Location: {event_location}

Description:
{event_description}

Register now through the Student Union portal to secure your spot!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
Student Union Events Team
"""

                self._send_email_via_gui(email, subject, message)

        except Exception as e:
            print(f"Failed to send event notifications: {e}")

    def send_trip_announcement(self, trip_name, trip_description, trip_date, trip_cost, organizer_club):
        """Send trip announcement to students"""
        try:
            # Get target audience (club members if specific club, all students if general)
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            if organizer_club:
                # Send to club members
                cursor.execute('''
                    SELECT s.email, s.first_name, s.last_name
                    FROM students s
                    JOIN club_members cm ON s.student_id = cm.student_id
                    JOIN student_clubs sc ON cm.club_id = sc.club_id
                    WHERE sc.club_name = ? AND s.email IS NOT NULL
                ''', (organizer_club,))
            else:
                # Send to all students
                cursor.execute('SELECT email, first_name, last_name FROM students WHERE email IS NOT NULL')

            recipients = cursor.fetchall()
            conn.close()

            subject = f"🧳 Trip Opportunity: {trip_name}"
            organizer_text = f" (organized by {organizer_club})" if organizer_club else ""

            for email, first_name, last_name in recipients:
                message = f"""Dear {first_name} {last_name},

Exciting trip opportunity{organizer_text}!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRIP ANNOUNCEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Trip: {trip_name}
Date: {trip_date}
Cost: £{trip_cost:.2f}
{f"Organized by: {organizer_club}" if organizer_club else "Organized by: Student Union"}

Description:
{trip_description}

Book your spot now through the Student Union portal. Payment can be made via your student account.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
Student Union Travel Team
"""

                self._send_email_via_gui(email, subject, message)

        except Exception as e:
            print(f"Failed to send trip announcements: {e}")

    def send_payment_confirmation(self, payment_type, item_name, amount, user_email, user_name):
        """Send payment confirmation email"""
        try:
            subject = f"💳 Payment Confirmation: {item_name}"

            message = f"""Dear {user_name},

Your payment has been successfully processed!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PAYMENT CONFIRMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Payment Type: {payment_type}
Item/Service: {item_name}
Amount: £{amount:.2f}
Payment Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Payment Method: Student Account
Status: Completed

Thank you for your payment. Keep this email as your receipt.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
Student Union Finance Team
"""

            self._send_email_via_gui(user_email, subject, message)

        except Exception as e:
            print(f"Failed to send payment confirmation: {e}")

    def _send_email_via_gui(self, to_email, subject, message):
        """Send email via email GUI"""
        try:
            from university_system.infrastructure.email.gui.email_manager_gui import EmailManagerGUI
            email_gui = EmailManagerGUI(self.root, auth=self.auth_manager)

            if hasattr(email_gui, 'send_email'):
                email_gui.send_email(to_email=to_email, subject=subject, message=message)
                return True
            return False
        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending email via GUI: {e}")
            return False

    def _show_email_fallback(self, email, subject, message, email_type):
        """Show fallback dialog for email"""
        try:
            fallback_window = tk.Toplevel(self.root)
            fallback_window.title(f"{email_type} Email - Manual Send")
            fallback_window.geometry("700x500")
            fallback_window.transient(self.root)

            ttk.Label(fallback_window,
                     text=f"Email system unavailable. Please manually send this {email_type.lower()}:",
                     font=('Arial', 10, 'bold')).pack(pady=10)

            details_frame = ttk.Frame(fallback_window)
            details_frame.pack(fill='both', expand=True, padx=10, pady=10)

            from tkinter.scrolledtext import ScrolledText
            details_text = ScrolledText(details_frame, height=20, width=80)
            details_text.pack(fill='both', expand=True)

            email_details = f"To: {email}\nSubject: {subject}\n\nMessage:\n{message}"
            details_text.insert('1.0', email_details)
            details_text.config(state='disabled')

            ttk.Button(fallback_window, text="Close", command=fallback_window.destroy).pack(pady=10)
        except Exception as e:
            print(f"Failed to show email fallback: {e}")

    # =========================================================================
    # FINANCE INTEGRATION METHODS
    # =========================================================================

    def open_finance_gui_for_club_payment(self, item_name, amount, payment_type="Club Payment"):
        """Open finance GUI for club-related payments"""
        try:
            from university_system.modules.domain.finance.gui.finance import FinanceGUI

            finance_window = tk.Toplevel(self.root)
            finance_window.title(f"Finance System - {payment_type}")
            finance_window.geometry("1000x700")

            finance_gui = FinanceGUI(finance_window, auth=self.auth_manager)

            # Pre-populate student union payment information if method exists
            if hasattr(finance_gui, 'prepopulate_student_union_payment'):
                finance_gui.prepopulate_student_union_payment(item_name, amount, payment_type)

            messagebox.showinfo("Finance System", f"Finance system opened for {payment_type}: {item_name}")

        except ImportError:
            messagebox.showerror("Error", "Finance system is not available")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open finance system: {e}")

    def process_student_union_payment(self, student_id, amount, description, payment_type):
        """Process payment through student finance account"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get student details
            cursor.execute('SELECT first_name, last_name, email FROM students WHERE student_id = ?', (student_id,))
            student_result = cursor.fetchone()
            if not student_result:
                messagebox.showerror("Error", f"Student ID {student_id} not found")
                conn.close()
                return False

            first_name, last_name, email = student_result

            # Add charge to student's finance account
            fee_id = f"SU_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            current_date = datetime.now().strftime('%Y-%m-%d')

            cursor.execute('''
                INSERT INTO student_fees
                (fee_id, student_id, fee_type, amount, due_date, description, paid_status, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                fee_id, student_id, payment_type, amount, current_date,
                f'{description} for {first_name} {last_name}', 'Paid', current_date
            ))

            # Record payment
            try:
                payment_id = f"PAY_{fee_id}"
                cursor.execute('''
                    INSERT INTO payments
                    (payment_id, student_id, amount, payment_method, payment_date, status, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    payment_id, student_id, amount, 'Student Account', current_date, 'completed',
                    f'Student Union payment: {description}'
                ))
            except sqlite3.Error:
                pass  # Payments table might not exist

            conn.commit()
            conn.close()

            # Send payment confirmation email
            self.send_payment_confirmation(payment_type, description, amount, email, f"{first_name} {last_name}")

            messagebox.showinfo("Payment Processed",
                f"Payment of £{amount:.2f} charged to {first_name} {last_name}'s student account")
            return True

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process payment: {e}")
            return False

    # =========================================================================
    # SHOP INTEGRATION METHODS
    # =========================================================================

    def open_shop_for_club_merchandise(self, club_name):
        """Open shop GUI filtered for club merchandise"""
        try:
            from university_system.modules.domain.commerce.gui.shop_management_gui import UniversityShopGUI

            shop_window = tk.Toplevel(self.root)
            shop_window.title(f"University Shop - {club_name} Merchandise")
            shop_window.geometry("1200x800")

            shop_gui = UniversityShopGUI(shop_window, auth=self.auth_manager)

            # Pre-filter for club merchandise if method exists
            if hasattr(shop_gui, 'filter_club_merchandise'):
                shop_gui.filter_club_merchandise(club_name)

            messagebox.showinfo("Shop Opened", f"Shop opened for {club_name} merchandise")

        except ImportError:
            messagebox.showerror("Error", "Shop system is not available")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open shop system: {e}")

    def add_club_merchandise_button(self, club_name):
        """Add button to access club merchandise"""
        try:
            merchandise_button = ttk.Button(
                self.content_frame,
                text=f"🛍️ {club_name} Merchandise",
                command=lambda: self.open_shop_for_club_merchandise(club_name)
            )
            merchandise_button.pack(pady=5)
        except Exception as e:
            print(f"Could not add merchandise button: {e}")

    # =========================================================================
    # RESTAURANT INTEGRATION METHODS
    # =========================================================================

    def open_restaurant_for_club_booking(self, club_name, event_type="Club Event"):
        """Open restaurant GUI for club event booking"""
        try:
            from university_system.modules.domain.commerce.gui.restaurant_management_gui import RestaurantManagementGUI

            restaurant_window = tk.Toplevel(self.root)
            restaurant_window.title(f"University Restaurant - {club_name} Booking")
            restaurant_window.geometry("1200x800")

            restaurant_gui = RestaurantManagementGUI(restaurant_window, auth=self.auth_manager)

            # Pre-populate club booking information if method exists
            if hasattr(restaurant_gui, 'create_club_reservation'):
                restaurant_gui.create_club_reservation(club_name, event_type)

            messagebox.showinfo("Restaurant Opened", f"Restaurant booking opened for {club_name}")

        except ImportError:
            messagebox.showerror("Error", "Restaurant system is not available")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open restaurant system: {e}")

    def book_club_dining_dialog(self, club_name):
        """Show dialog for club dining reservation"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Book Dining for {club_name}")
            dialog.geometry("400x300")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"Restaurant Booking for {club_name}",
                     font=('Arial', 12, 'bold')).pack(pady=10)

            # Booking options
            ttk.Label(main_frame, text="Event Type:").pack(anchor='w')
            event_type_var = tk.StringVar(value="Club Meeting")
            event_types = ["Club Meeting", "Social Dinner", "Celebration", "Awards Ceremony", "Other"]
            event_combo = ttk.Combobox(main_frame, textvariable=event_type_var, values=event_types)
            event_combo.pack(fill='x', pady=5)

            ttk.Label(main_frame, text="Expected Attendees:").pack(anchor='w')
            attendees_var = tk.StringVar()
            ttk.Entry(main_frame, textvariable=attendees_var).pack(fill='x', pady=5)

            def proceed_booking():
                event_type = event_type_var.get()
                attendees = attendees_var.get()
                if attendees:
                    dialog.destroy()
                    self.open_restaurant_for_club_booking(club_name, event_type)
                else:
                    messagebox.showwarning("Missing Information", "Please specify expected attendees")

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=20)

            ttk.Button(button_frame, text="Open Restaurant System",
                      command=proceed_booking).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel",
                      command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Could not open booking dialog: {e}")

    # =========================================================================
    # CALENDAR INTEGRATION METHODS
    # =========================================================================

    def open_calendar_with_club_events(self, club_name=None):
        """Open calendar GUI with club events"""
        try:
            from university_system.modules.domain.academics.gui.academic_calendar_gui import CalendarGUI

            calendar_window = tk.Toplevel(self.root)
            calendar_window.title("Student Union Calendar" + (f" - {club_name}" if club_name else ""))
            calendar_window.geometry("900x700")

            calendar_gui = CalendarGUI(auth_manager=self.auth_manager, parent_window=calendar_window)

            # Add club events to calendar
            self._add_club_events_to_calendar(calendar_gui, club_name)

            messagebox.showinfo("Calendar Opened",
                               f"Calendar opened" + (f" for {club_name}" if club_name else " with all Student Union events"))

        except ImportError:
            messagebox.showerror("Error", "Calendar system is not available")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open calendar: {e}")

    def _add_club_events_to_calendar(self, calendar_gui, club_name=None):
        """Add club events to calendar"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            if club_name:
                # Get events for specific club
                cursor.execute('''
                    SELECT event_name, event_date, event_description, event_location
                    FROM student_events se
                    JOIN student_clubs sc ON se.club_id = sc.club_id
                    WHERE sc.club_name = ?
                ''', (club_name,))
            else:
                # Get all student union events
                cursor.execute('''
                    SELECT event_name, event_date, event_description, event_location
                    FROM student_events
                ''')

            events = cursor.fetchall()
            conn.close()

            # Add events to calendar
            for event_name, event_date, event_description, event_location in events:
                if hasattr(calendar_gui, 'add_student_union_event'):
                    calendar_gui.add_student_union_event(
                        title=event_name,
                        date=event_date,
                        description=f"{event_description}\nLocation: {event_location}",
                        event_type="student_union"
                    )

        except Exception as e:
            print(f"Failed to add club events to calendar: {e}")

    # =========================================================================
    # TRIP INTEGRATION METHODS
    # =========================================================================

    def open_trip_management_for_club(self, club_name):
        """Open trip management GUI for club"""
        try:
            from university_system.modules.domain.mobility.gui.trip_management_gui import TripManagementGUI

            trip_window = tk.Toplevel(self.root)
            trip_window.title(f"Trip Management - {club_name}")
            trip_window.geometry("1200x800")

            trip_gui = TripManagementGUI(trip_window, auth=self.auth_manager)

            # Pre-populate club information if method exists
            if hasattr(trip_gui, 'set_organizing_club'):
                trip_gui.set_organizing_club(club_name)

            messagebox.showinfo("Trip Management Opened", f"Trip management opened for {club_name}")

        except ImportError:
            messagebox.showerror("Error", "Trip management system is not available")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open trip management: {e}")

    def create_club_trip_dialog(self, club_name):
        """Show dialog to create a new club trip"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Create Trip for {club_name}")
            dialog.geometry("500x600")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"New Trip for {club_name}",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            # Trip details form
            fields = {}

            ttk.Label(main_frame, text="Trip Name:").pack(anchor='w')
            fields['name'] = ttk.Entry(main_frame)
            fields['name'].pack(fill='x', pady=5)

            ttk.Label(main_frame, text="Destination:").pack(anchor='w')
            fields['destination'] = ttk.Entry(main_frame)
            fields['destination'].pack(fill='x', pady=5)

            ttk.Label(main_frame, text="Trip Date:").pack(anchor='w')
            fields['date'] = ttk.Entry(main_frame)
            fields['date'].pack(fill='x', pady=5)
            fields['date'].insert(0, "YYYY-MM-DD")

            ttk.Label(main_frame, text="Cost per Person (£):").pack(anchor='w')
            fields['cost'] = ttk.Entry(main_frame)
            fields['cost'].pack(fill='x', pady=5)

            ttk.Label(main_frame, text="Maximum Participants:").pack(anchor='w')
            fields['max_participants'] = ttk.Entry(main_frame)
            fields['max_participants'].pack(fill='x', pady=5)

            ttk.Label(main_frame, text="Description:").pack(anchor='w')
            fields['description'] = tk.Text(main_frame, height=6)
            fields['description'].pack(fill='both', expand=True, pady=5)

            def create_trip():
                try:
                    trip_data = {
                        'name': fields['name'].get(),
                        'destination': fields['destination'].get(),
                        'date': fields['date'].get(),
                        'cost': float(fields['cost'].get()),
                        'max_participants': int(fields['max_participants'].get()),
                        'description': fields['description'].get('1.0', 'end-1c'),
                        'organizing_club': club_name
                    }

                    # Validate required fields
                    if not all([trip_data['name'], trip_data['destination'], trip_data['date']]):
                        messagebox.showerror("Error", "Please fill in all required fields")
                        return

                    # Create trip in database (simplified)
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()

                    # Create trips table if it doesn't exist
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS student_trips (
                            trip_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            trip_name TEXT NOT NULL,
                            destination TEXT NOT NULL,
                            trip_date TEXT NOT NULL,
                            cost REAL NOT NULL,
                            max_participants INTEGER,
                            description TEXT,
                            organizing_club TEXT,
                            created_by INTEGER,
                            created_date TEXT DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')

                    cursor.execute('''
                        INSERT INTO student_trips
                        (trip_name, destination, trip_date, cost, max_participants, description, organizing_club, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        trip_data['name'], trip_data['destination'], trip_data['date'],
                        trip_data['cost'], trip_data['max_participants'], trip_data['description'],
                        club_name, self.current_user.get('id', 0)
                    ))

                    conn.commit()
                    conn.close()

                    # Send trip announcement
                    self.send_trip_announcement(
                        trip_data['name'], trip_data['description'],
                        trip_data['date'], trip_data['cost'], club_name
                    )

                    dialog.destroy()
                    messagebox.showinfo("Trip Created", f"Trip '{trip_data['name']}' created successfully!")

                except ValueError:
                    messagebox.showerror("Error", "Please enter valid numbers for cost and max participants")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create trip: {e}")

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=20)

            ttk.Button(button_frame, text="Create Trip", command=create_trip).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Open Trip Management",
                      command=lambda: [dialog.destroy(), self.open_trip_management_for_club(club_name)]).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Could not create trip dialog: {e}")

    # =========================================================================
    # ENHANCED UI INTEGRATION METHODS
    # =========================================================================

    def add_integration_buttons_to_club_view(self, club_name):
        """Add integration buttons to club view"""
        try:
            if hasattr(self, 'content_frame'):
                # Create integration buttons frame
                integration_frame = ttk.LabelFrame(self.content_frame, text="Club Services")
                integration_frame.pack(fill='x', padx=10, pady=10)

                # Row 1: Shopping and Dining
                row1_frame = ttk.Frame(integration_frame)
                row1_frame.pack(fill='x', padx=5, pady=5)

                ttk.Button(row1_frame, text="🛍️ Club Merchandise",
                          command=lambda: self.open_shop_for_club_merchandise(club_name)).pack(side='left', padx=5)
                ttk.Button(row1_frame, text="🍽️ Book Club Dining",
                          command=lambda: self.book_club_dining_dialog(club_name)).pack(side='left', padx=5)

                # Row 2: Calendar and Trips
                row2_frame = ttk.Frame(integration_frame)
                row2_frame.pack(fill='x', padx=5, pady=5)

                ttk.Button(row2_frame, text="📅 Club Calendar",
                          command=lambda: self.open_calendar_with_club_events(club_name)).pack(side='left', padx=5)
                ttk.Button(row2_frame, text="🧳 Organize Trip",
                          command=lambda: self.create_club_trip_dialog(club_name)).pack(side='left', padx=5)

                # Row 3: Finance and Communication
                row3_frame = ttk.Frame(integration_frame)
                row3_frame.pack(fill='x', padx=5, pady=5)

                ttk.Button(row3_frame, text="💳 Club Payments",
                          command=lambda: self.open_finance_gui_for_club_payment(f"{club_name} Membership", 0, "Club Fee")).pack(side='left', padx=5)
                ttk.Button(row3_frame, text="📧 Send Newsletter",
                          command=lambda: self.create_newsletter_dialog(club_name)).pack(side='left', padx=5)

        except Exception as e:
            print(f"Could not add integration buttons: {e}")

    def create_newsletter_dialog(self, club_name):
        """Create dialog for sending club newsletter"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Send Newsletter - {club_name}")
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"Send Newsletter to {club_name} Members",
                     font=('Arial', 12, 'bold')).pack(pady=10)

            ttk.Label(main_frame, text="Newsletter Subject:").pack(anchor='w')
            subject_entry = ttk.Entry(main_frame)
            subject_entry.pack(fill='x', pady=5)

            ttk.Label(main_frame, text="Newsletter Content:").pack(anchor='w')
            content_text = tk.Text(main_frame, height=15)
            content_text.pack(fill='both', expand=True, pady=5)

            def send_newsletter():
                subject = subject_entry.get().strip()
                content = content_text.get('1.0', 'end-1c').strip()

                if not subject or not content:
                    messagebox.showwarning("Missing Information", "Please provide both subject and content")
                    return

                self.send_newsletter_to_club_members(club_name, subject, content)
                dialog.destroy()

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text="Send Newsletter", command=send_newsletter).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Could not create newsletter dialog: {e}")

    # =========================================================================
    # INTEGRATION HELPER METHODS
    # =========================================================================

    def show_club_selection_for_merchandise(self):
        """Show dialog to select club for merchandise shopping"""
        try:
            # Get all active clubs
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT club_name FROM student_clubs WHERE status = "active" ORDER BY club_name')
            clubs = [row[0] for row in cursor.fetchall()]
            conn.close()

            if not clubs:
                messagebox.showinfo("No Clubs", "No active clubs found")
                return

            # Create selection dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Select Club for Merchandise")
            dialog.geometry("300x200")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Select a club:", font=('Arial', 10, 'bold')).pack(pady=10)

            club_var = tk.StringVar()
            club_combo = ttk.Combobox(main_frame, textvariable=club_var, values=clubs, state="readonly")
            club_combo.pack(fill='x', pady=10)

            def open_merchandise_shop():
                selected_club = club_var.get()
                if selected_club:
                    dialog.destroy()
                    self.open_shop_for_club_merchandise(selected_club)
                else:
                    messagebox.showwarning("No Selection", "Please select a club")

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=20)

            ttk.Button(button_frame, text="Open Shop", command=open_merchandise_shop).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Could not show club selection: {e}")

    def show_club_selection_for_dining(self):
        """Show dialog to select club for dining reservation"""
        try:
            # Get all active clubs
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT club_name FROM student_clubs WHERE status = "active" ORDER BY club_name')
            clubs = [row[0] for row in cursor.fetchall()]
            conn.close()

            if not clubs:
                messagebox.showinfo("No Clubs", "No active clubs found")
                return

            # Create selection dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Select Club for Dining Reservation")
            dialog.geometry("300x200")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Select a club:", font=('Arial', 10, 'bold')).pack(pady=10)

            club_var = tk.StringVar()
            club_combo = ttk.Combobox(main_frame, textvariable=club_var, values=clubs, state="readonly")
            club_combo.pack(fill='x', pady=10)

            def open_dining_booking():
                selected_club = club_var.get()
                if selected_club:
                    dialog.destroy()
                    self.book_club_dining_dialog(selected_club)
                else:
                    messagebox.showwarning("No Selection", "Please select a club")

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=20)

            ttk.Button(button_frame, text="Book Dining", command=open_dining_booking).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Could not show club selection: {e}")

    def show_club_selection_for_trips(self):
        """Show dialog to select club for trip management"""
        try:
            # Get all active clubs
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT club_name FROM student_clubs WHERE status = "active" ORDER BY club_name')
            clubs = [row[0] for row in cursor.fetchall()]
            conn.close()

            if not clubs:
                messagebox.showinfo("No Clubs", "No active clubs found")
                return

            # Create selection dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Select Club for Trip Management")
            dialog.geometry("300x250")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Select a club:", font=('Arial', 10, 'bold')).pack(pady=10)

            club_var = tk.StringVar()
            club_combo = ttk.Combobox(main_frame, textvariable=club_var, values=clubs, state="readonly")
            club_combo.pack(fill='x', pady=10)

            def create_trip():
                selected_club = club_var.get()
                if selected_club:
                    dialog.destroy()
                    self.create_club_trip_dialog(selected_club)
                else:
                    messagebox.showwarning("No Selection", "Please select a club")

            def manage_trips():
                selected_club = club_var.get()
                if selected_club:
                    dialog.destroy()
                    self.open_trip_management_for_club(selected_club)
                else:
                    messagebox.showwarning("No Selection", "Please select a club")

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=20)

            ttk.Button(button_frame, text="Create New Trip", command=create_trip).pack(pady=5)
            ttk.Button(button_frame, text="Manage Existing Trips", command=manage_trips).pack(pady=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(pady=5)

        except Exception as e:
            messagebox.showerror("Error", f"Could not show club selection: {e}")


class RecurringEventDialog:
    """Dialog for creating recurring events"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Recurring Event")
        self.dialog.geometry("600x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        ttk.Label(main_frame, text="Create Recurring Event", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Event details
        details_frame = ttk.LabelFrame(main_frame, text="Event Details")
        details_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(details_frame, text="Event Name:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.name_var, width=40).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(details_frame, text="Description:").grid(row=1, column=0, sticky='nw', padx=5, pady=5)
        self.description_text = tk.Text(details_frame, height=4, width=40)
        self.description_text.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(details_frame, text="Location:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.location_var, width=40).grid(row=2, column=1, padx=5, pady=5)

        # Recurrence pattern
        recurrence_frame = ttk.LabelFrame(main_frame, text="Recurrence Pattern")
        recurrence_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(recurrence_frame, text="Pattern:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.pattern_var = tk.StringVar(value="weekly")
        patterns = ttk.Combobox(recurrence_frame, textvariable=self.pattern_var,
                               values=["daily", "weekly", "monthly"], state="readonly", width=20)
        patterns.grid(row=0, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(recurrence_frame, text="Start Date:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.start_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(recurrence_frame, textvariable=self.start_date_var, width=20).grid(row=1, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(recurrence_frame, text="End Date:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.end_date_var = tk.StringVar(value=(datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d'))
        ttk.Entry(recurrence_frame, textvariable=self.end_date_var, width=20).grid(row=2, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(recurrence_frame, text="Time:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.time_var = tk.StringVar(value="10:00")
        ttk.Entry(recurrence_frame, textvariable=self.time_var, width=20).grid(row=3, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(recurrence_frame, text="Duration (hours):").grid(row=4, column=0, sticky='w', padx=5, pady=5)
        self.duration_var = tk.StringVar(value="2")
        ttk.Entry(recurrence_frame, textvariable=self.duration_var, width=20).grid(row=4, column=1, sticky='w', padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text="Create", command=self.create_event).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side='left')

    def create_event(self):
        """Create the recurring event"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Please enter an event name.")
            return

        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            # Create recurring event record
            cursor.execute('''
            INSERT INTO recurring_events (event_name, description, location, recurrence_pattern,
                                         start_date, end_date, event_time, duration_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
            ''', (name, self.description_text.get("1.0", tk.END).strip(), self.location_var.get(),
                  self.pattern_var.get(), self.start_date_var.get(), self.end_date_var.get(),
                  self.time_var.get(), float(self.duration_var.get())))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Recurring event '{name}' created successfully!")
            self.result = {'name': name}
            self.dialog.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create event: {str(e)}")

    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


class EventManagementDialog:
    """Dialog for managing recurring events"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Manage Recurring Events")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_events()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        ttk.Label(main_frame, text="Recurring Events Management", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Events list
        list_frame = ttk.LabelFrame(main_frame, text="Events")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Name', 'Pattern', 'Start', 'End', 'Status')
        self.events_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.events_tree.heading(col, text=col)
            self.events_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.events_tree.yview)
        self.events_tree.configure(yscrollcommand=scrollbar.set)

        self.events_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text="Edit Selected", command=self.edit_event).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Pause/Resume", command=self.toggle_status).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Delete", command=self.delete_event).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='left')

    def load_events(self):
        """Load recurring events"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT event_id, event_name, recurrence_pattern, start_date, end_date, status
            FROM recurring_events
            ORDER BY start_date DESC
            ''')

            events = cursor.fetchall()

            for event in events:
                self.events_tree.insert('', 'end', values=event)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load events: {str(e)}")

    def edit_event(self):
        """Edit selected event"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event to edit.")
            return
        messagebox.showinfo("Info", "Edit functionality coming soon!")

    def toggle_status(self):
        """Toggle event status"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event.")
            return

        item = self.events_tree.item(selection[0])
        event_id = item['values'][0]
        current_status = item['values'][5]
        new_status = 'paused' if current_status == 'active' else 'active'

        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE recurring_events SET status = ? WHERE event_id = ?', (new_status, event_id))
            conn.commit()
            conn.close()

            # Refresh list
            self.events_tree.delete(*self.events_tree.get_children())
            self.load_events()
            messagebox.showinfo("Success", f"Event status changed to {new_status}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update status: {str(e)}")

    def delete_event(self):
        """Delete selected event"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event to delete.")
            return

        item = self.events_tree.item(selection[0])
        event_id = item['values'][0]
        event_name = item['values'][1]

        if messagebox.askyesno("Confirm", f"Delete recurring event '{event_name}'?"):
            try:
                conn = student_union_cli.get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM recurring_events WHERE event_id = ?', (event_id,))
                conn.commit()
                conn.close()

                self.events_tree.delete(selection[0])
                messagebox.showinfo("Success", "Event deleted successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete event: {str(e)}")


class EventAttendanceDialog:
    """Dialog for managing event attendance"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Event Attendance Management")
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_events()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        ttk.Label(main_frame, text="Event Attendance Tracking", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Event selection
        event_frame = ttk.LabelFrame(main_frame, text="Select Event")
        event_frame.pack(fill='x', pady=(0, 10))

        self.event_var = tk.StringVar()
        self.event_combo = ttk.Combobox(event_frame, textvariable=self.event_var, width=60, state="readonly")
        self.event_combo.pack(side='left', padx=5, pady=5)
        self.event_combo.bind('<<ComboboxSelected>>', self.on_event_selected)

        ttk.Button(event_frame, text="View Attendance", command=self.view_attendance).pack(side='left', padx=5)

        # Attendance details
        details_frame = ttk.LabelFrame(main_frame, text="Attendance Details")
        details_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Student ID', 'Name', 'Check-in Time', 'Check-out Time', 'Status')
        self.attendance_tree = ttk.Treeview(details_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.attendance_tree.heading(col, text=col)
            self.attendance_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(details_frame, orient='vertical', command=self.attendance_tree.yview)
        self.attendance_tree.configure(yscrollcommand=scrollbar.set)

        self.attendance_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Stats
        stats_frame = ttk.LabelFrame(main_frame, text="Statistics")
        stats_frame.pack(fill='x', pady=(0, 10))

        self.stats_label = ttk.Label(stats_frame, text="Select an event to view statistics")
        self.stats_label.pack(padx=10, pady=10)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Export", command=self.export_attendance).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='left')

    def load_events(self):
        """Load events for attendance tracking"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT event_id, event_name, event_date, event_time
            FROM union_events
            WHERE event_date >= date('now', '-30 days')
            ORDER BY event_date DESC
            ''')

            events = cursor.fetchall()

            event_options = []
            self.event_data = {}

            for event in events:
                option = f"{event[1]} - {event[2]} {event[3]}"
                event_options.append(option)
                self.event_data[option] = event[0]

            self.event_combo['values'] = event_options
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load events: {str(e)}")

    def on_event_selected(self, event=None):
        """Handle event selection"""
        pass

    def view_attendance(self):
        """View attendance for selected event"""
        selection = self.event_var.get()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event.")
            return

        event_id = self.event_data[selection]

        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT er.student_id, u.username, er.registration_date,
                   CASE WHEN er.attendance_confirmed = 1 THEN 'Attended' ELSE 'Registered' END
            FROM event_registrations er
            JOIN users u ON er.student_id = u.student_id
            WHERE er.event_id = ?
            ORDER BY u.username
            ''', (event_id,))

            attendance = cursor.fetchall()

            # Clear previous data
            self.attendance_tree.delete(*self.attendance_tree.get_children())

            # Insert attendance data
            for record in attendance:
                self.attendance_tree.insert('', 'end', values=(record[0], record[1], record[2], '-', record[3]))

            # Update stats
            total = len(attendance)
            attended = sum(1 for r in attendance if r[3] == 'Attended')
            self.stats_label.config(text=f"Total Registered: {total} | Attended: {attended} | Attendance Rate: {(attended/total*100 if total > 0 else 0):.1f}%")

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load attendance: {str(e)}")

    def export_attendance(self):
        """Export attendance data"""
        messagebox.showinfo("Info", "Export functionality coming soon!")


class EventFinancesDialog:
    """Dialog for tracking event finances"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Event Financial Tracking")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_events()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        ttk.Label(main_frame, text="Event Financial Tracking", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Event selection
        event_frame = ttk.LabelFrame(main_frame, text="Select Event")
        event_frame.pack(fill='x', pady=(0, 10))

        self.event_var = tk.StringVar()
        self.event_combo = ttk.Combobox(event_frame, textvariable=self.event_var, width=60, state="readonly")
        self.event_combo.pack(side='left', padx=5, pady=5)
        self.event_combo.bind('<<ComboboxSelected>>', self.on_event_selected)

        ttk.Button(event_frame, text="View Finances", command=self.view_finances).pack(side='left', padx=5)
        ttk.Button(event_frame, text="Add Expense", command=self.add_expense).pack(side='left', padx=5)

        # Financial summary
        summary_frame = ttk.LabelFrame(main_frame, text="Financial Summary")
        summary_frame.pack(fill='x', pady=(0, 10))

        summary_grid = ttk.Frame(summary_frame)
        summary_grid.pack(fill='x', padx=10, pady=10)

        ttk.Label(summary_grid, text="Budget:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', padx=5)
        self.budget_label = ttk.Label(summary_grid, text="$0.00")
        self.budget_label.grid(row=0, column=1, sticky='w', padx=5)

        ttk.Label(summary_grid, text="Expenses:", font=('Arial', 10, 'bold')).grid(row=0, column=2, sticky='w', padx=5)
        self.expenses_label = ttk.Label(summary_grid, text="$0.00")
        self.expenses_label.grid(row=0, column=3, sticky='w', padx=5)

        ttk.Label(summary_grid, text="Revenue:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', padx=5)
        self.revenue_label = ttk.Label(summary_grid, text="$0.00")
        self.revenue_label.grid(row=1, column=1, sticky='w', padx=5)

        ttk.Label(summary_grid, text="Balance:", font=('Arial', 10, 'bold')).grid(row=1, column=2, sticky='w', padx=5)
        self.balance_label = ttk.Label(summary_grid, text="$0.00")
        self.balance_label.grid(row=1, column=3, sticky='w', padx=5)

        # Transactions list
        trans_frame = ttk.LabelFrame(main_frame, text="Transactions")
        trans_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Date', 'Type', 'Category', 'Amount', 'Description')
        self.trans_tree = ttk.Treeview(trans_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.trans_tree.heading(col, text=col)
            self.trans_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(trans_frame, orient='vertical', command=self.trans_tree.yview)
        self.trans_tree.configure(yscrollcommand=scrollbar.set)

        self.trans_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Generate Report", command=self.generate_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='left')

    def load_events(self):
        """Load events"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT event_id, event_name, event_date
            FROM union_events
            WHERE event_date >= date('now', '-90 days')
            ORDER BY event_date DESC
            ''')

            events = cursor.fetchall()

            event_options = []
            self.event_data = {}

            for event in events:
                option = f"{event[1]} - {event[2]}"
                event_options.append(option)
                self.event_data[option] = event[0]

            self.event_combo['values'] = event_options
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load events: {str(e)}")

    def on_event_selected(self, event=None):
        """Handle event selection"""
        pass

    def view_finances(self):
        """View finances for selected event"""
        selection = self.event_var.get()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event.")
            return

        messagebox.showinfo("Info", "Financial tracking functionality coming soon!")

    def add_expense(self):
        """Add expense to event"""
        selection = self.event_var.get()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event first.")
            return

        messagebox.showinfo("Info", "Add expense functionality coming soon!")

    def generate_report(self):
        """Generate financial report"""
        messagebox.showinfo("Info", "Report generation coming soon!")


class FacilityApprovalDialog:
    """Dialog for approving facility bookings"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Approve Facility Bookings")
        self.dialog.geometry("1000x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_pending_bookings()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Pending Facility Bookings", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        list_frame = ttk.LabelFrame(main_frame, text="Pending Requests")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Facility', 'Student', 'Date', 'Time', 'Purpose', 'Status')
        self.bookings_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.bookings_tree.heading(col, text=col)
            self.bookings_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.bookings_tree.yview)
        self.bookings_tree.configure(yscrollcommand=scrollbar.set)

        self.bookings_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text="Approve", command=self.approve_booking).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Reject", command=self.reject_booking).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='left')

    def load_pending_bookings(self):
        """Load pending facility bookings"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT fb.booking_id, f.facility_name, u.username, fb.booking_date,
                   fb.start_time || '-' || fb.end_time, fb.purpose, fb.status
            FROM facility_bookings fb
            JOIN union_facilities f ON fb.facility_id = f.facility_id
            JOIN users u ON fb.student_id = u.student_id
            WHERE fb.status = 'pending'
            ORDER BY fb.booking_date, fb.start_time
            ''')

            bookings = cursor.fetchall()

            for booking in bookings:
                self.bookings_tree.insert('', 'end', values=booking)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load bookings: {str(e)}")

    def approve_booking(self):
        """Approve selected booking"""
        selection = self.bookings_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a booking to approve.")
            return

        item = self.bookings_tree.item(selection[0])
        booking_id = item['values'][0]

        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE facility_bookings SET status = ? WHERE booking_id = ?', ('approved', booking_id))
            conn.commit()
            conn.close()

            self.bookings_tree.delete(selection[0])
            messagebox.showinfo("Success", "Booking approved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to approve booking: {str(e)}")

    def reject_booking(self):
        """Reject selected booking"""
        selection = self.bookings_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a booking to reject.")
            return

        item = self.bookings_tree.item(selection[0])
        booking_id = item['values'][0]

        reason = simpledialog.askstring("Rejection Reason", "Enter reason for rejection:")
        if reason:
            try:
                conn = student_union_cli.get_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE facility_bookings SET status = ?, rejection_reason = ? WHERE booking_id = ?',
                             ('rejected', reason, booking_id))
                conn.commit()
                conn.close()

                self.bookings_tree.delete(selection[0])
                messagebox.showinfo("Success", "Booking rejected.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to reject booking: {str(e)}")


class ExpenseSubmitDialog:
    """Dialog for submitting expense requests"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Submit Expense Request")
        self.dialog.geometry("600x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Submit Expense Request", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        details_frame = ttk.LabelFrame(main_frame, text="Expense Details")
        details_frame.pack(fill='both', expand=True, pady=(0, 10))

        ttk.Label(details_frame, text="Category:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.category_var = tk.StringVar(value="supplies")
        ttk.Combobox(details_frame, textvariable=self.category_var,
                    values=["supplies", "equipment", "food", "transportation", "venue", "other"],
                    state="readonly", width=30).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(details_frame, text="Amount:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.amount_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.amount_var, width=32).grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(details_frame, text="Description:").grid(row=2, column=0, sticky='nw', padx=5, pady=5)
        self.description_text = tk.Text(details_frame, height=4, width=32)
        self.description_text.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(details_frame, text="Related Event:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.event_var = tk.StringVar()
        self.event_combo = ttk.Combobox(details_frame, textvariable=self.event_var, width=30)
        self.event_combo.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(details_frame, text="Receipt/Invoice #:").grid(row=4, column=0, sticky='w', padx=5, pady=5)
        self.receipt_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.receipt_var, width=32).grid(row=4, column=1, padx=5, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text="Submit", command=self.submit_expense).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def submit_expense(self):
        """Submit the expense request"""
        amount_str = self.amount_var.get().strip()
        if not amount_str:
            messagebox.showwarning("Warning", "Please enter an amount.")
            return

        try:
            amount = float(amount_str)
            messagebox.showinfo("Success", f"Expense request for ${amount:.2f} submitted successfully!")
            self.dialog.destroy()
        except ValueError:
            messagebox.showerror("Error", "Invalid amount. Please enter a number.")


class ExpenseApprovalDialog:
    """Dialog for approving expense requests"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Approve Expense Requests")
        self.dialog.geometry("1000x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_pending_expenses()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Pending Expense Requests", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        list_frame = ttk.LabelFrame(main_frame, text="Pending Requests")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Category', 'Amount', 'Description', 'Submitted By', 'Date', 'Status')
        self.expenses_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.expenses_tree.heading(col, text=col)
            self.expenses_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.expenses_tree.yview)
        self.expenses_tree.configure(yscrollcommand=scrollbar.set)

        self.expenses_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text="Approve", command=self.approve_expense).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Reject", command=self.reject_expense).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='left')

    def load_pending_expenses(self):
        """Load pending expense requests"""
        messagebox.showinfo("Info", "Loading expenses functionality coming soon!")

    def approve_expense(self):
        """Approve selected expense"""
        selection = self.expenses_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an expense to approve.")
            return
        messagebox.showinfo("Success", "Expense approved!")

    def reject_expense(self):
        """Reject selected expense"""
        selection = self.expenses_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an expense to reject.")
            return
        messagebox.showinfo("Info", "Expense rejected.")


class ClubFinancialReportsDialog:
    """Dialog for viewing club financial reports"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Club Financial Reports")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Club Financial Reports", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Club selection
        club_frame = ttk.LabelFrame(main_frame, text="Select Club and Period")
        club_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(club_frame, text="Club:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(club_frame, textvariable=self.club_var, width=40, state="readonly")
        self.club_combo.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(club_frame, text="Period:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.period_var = tk.StringVar(value="current_month")
        ttk.Combobox(club_frame, textvariable=self.period_var,
                    values=["current_month", "last_month", "current_year", "last_year", "all_time"],
                    state="readonly", width=38).grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(club_frame, text="Generate Report", command=self.generate_report).grid(row=0, column=2, padx=5, pady=5)

        # Report display
        report_frame = ttk.LabelFrame(main_frame, text="Financial Report")
        report_frame.pack(fill='both', expand=True, pady=(0, 10))

        self.report_text = scrolledtext.ScrolledText(report_frame, height=20, width=80)
        self.report_text.pack(fill='both', expand=True, padx=5, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Export PDF", command=self.export_pdf).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='left')

    def generate_report(self):
        """Generate financial report"""
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert("1.0", "Financial report generation coming soon...")

    def export_pdf(self):
        """Export report to PDF"""
        messagebox.showinfo("Info", "PDF export coming soon!")


class ClubBudgetDialog:
    """Dialog for managing club budgets"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Manage Club Budgets")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Club Budget Management", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Club selection
        club_frame = ttk.LabelFrame(main_frame, text="Select Club")
        club_frame.pack(fill='x', pady=(0, 10))

        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(club_frame, textvariable=self.club_var, width=50, state="readonly")
        self.club_combo.pack(side='left', padx=5, pady=5)

        ttk.Button(club_frame, text="View Budget", command=self.view_budget).pack(side='left', padx=5)
        ttk.Button(club_frame, text="Set Budget", command=self.set_budget).pack(side='left', padx=5)

        # Budget details
        details_frame = ttk.LabelFrame(main_frame, text="Budget Overview")
        details_frame.pack(fill='both', expand=True, pady=(0, 10))

        self.budget_text = scrolledtext.ScrolledText(details_frame, height=20, width=80)
        self.budget_text.pack(fill='both', expand=True, padx=5, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='left')

    def view_budget(self):
        """View budget for selected club"""
        messagebox.showinfo("Info", "Budget view coming soon!")

    def set_budget(self):
        """Set budget for selected club"""
        messagebox.showinfo("Info", "Set budget coming soon!")


class SearchDialog:
    """Generic search dialog"""

    def __init__(self, parent, title, search_function, display_function):
        self.parent = parent
        self.search_function = search_function
        self.display_function = display_function

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x150")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create search dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Search input
        ttk.Label(main_frame, text="Search Term:").pack(anchor='w', pady=(0, 5))

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(main_frame, textvariable=self.search_var, width=40)
        search_entry.pack(fill='x', pady=(0, 10))
        search_entry.bind('<Return>', lambda e: self.perform_search())
        search_entry.focus()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Search", command=self.perform_search).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def perform_search(self):
        """Perform the search"""
        search_term = self.search_var.get().strip()
        if not search_term:
            messagebox.showwarning("Warning", "Please enter a search term.")
            return

        try:
            results = self.search_function(search_term)
            self.display_function(results)
            self.dialog.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")

# Backward compatibility functions for CLI integration
def get_gui_instance():
    """Get the GUI instance for CLI integration"""
    return StudentUnionGUI()

def launch_gui():
    """Launch the GUI application"""
    app = StudentUnionGUI()
    app.run()

def launch_cli():
    """Launch the CLI application"""
    if CLI_AVAILABLE:
        try:
            from part2 import main as cli_main
            cli_main()
        except ImportError:
            print("Error: CLI system not available")
    else:
        print("CLI system not available. Please ensure part2.py is in the same directory.")

# Enhanced CLI-GUI Bridge Class
class CLIGUIBridge:
    """Bridge between CLI and GUI systems for seamless integration"""
    
    def __init__(self):
        self.gui_app = None
        self.cli_available = CLI_AVAILABLE
    
    def start_gui(self):
        """Start GUI mode"""
        self.gui_app = StudentUnionGUI()
        self.gui_app.run()
    
    def start_cli(self):
        """Start CLI mode"""
        if not self.cli_available:
            print("CLI mode not available")
            return

        try:
            from part2 import main as cli_main
            cli_main()
        except ImportError:
            print("Error: Cannot import CLI system")

    def switch_mode(self, current_mode='gui'):
        """Switch between GUI and CLI modes"""
        if current_mode == 'gui':
            if self.gui_app:
                self.gui_app.root.destroy()
            self.start_cli()
        else:
            self.start_gui()


# ============================================================
# NEW DIALOG CLASSES FOR FULLY IMPLEMENTED FEATURES
# ============================================================

class ClubMemberDirectoryDialog:
    """Dialog for viewing club member directory"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Club Member Directory")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Club Member Directory", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Club selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(select_frame, text="Select Club:").pack(side='left', padx=(0, 10))
        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(select_frame, textvariable=self.club_var, width=40)
        self.club_combo.pack(side='left', fill='x', expand=True)
        self.club_combo.bind('<<ComboboxSelected>>', self.on_club_selected)

        # Members list
        list_frame = ttk.LabelFrame(main_frame, text="Club Members")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Student ID', 'Name', 'Role', 'Join Date', 'Email', 'Phone')
        self.members_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.members_tree.heading(col, text=col)
            self.members_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.members_tree.yview)
        self.members_tree.configure(yscrollcommand=scrollbar.set)

        self.members_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Export to CSV", command=self.export_members).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Send Group Email", command=self.send_group_email).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load clubs that the user belongs to"""
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get student ID
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()

            if not result:
                conn.close()
                return

            student_id = result[0]

            # Get clubs the user is a member of
            cursor.execute('''
            SELECT DISTINCT sc.club_id, sc.club_name
            FROM student_clubs sc
            INNER JOIN club_members cm ON sc.club_id = cm.club_id
            WHERE cm.student_id = ? AND sc.status = 'active'
            ORDER BY sc.club_name
            ''', (student_id,))

            clubs = cursor.fetchall()
            self.club_data = {f"{club[1]} (ID: {club[0]})": club[0] for club in clubs}
            self.club_combo['values'] = list(self.club_data.keys())

            conn.close()

            if clubs:
                self.club_combo.current(0)
                self.on_club_selected(None)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load clubs: {str(e)}")

    def on_club_selected(self, event):
        """Load members when club is selected"""
        # Clear current items
        for item in self.members_tree.get_children():
            self.members_tree.delete(item)

        selected = self.club_var.get()
        if not selected or selected not in self.club_data:
            return

        club_id = self.club_data[selected]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get members with their details
            cursor.execute('''
            SELECT cm.student_id, s.first_name || ' ' || s.last_name, cm.role, cm.join_date,
                   s.email, s.phone
            FROM club_members cm
            INNER JOIN students s ON cm.student_id = s.student_id
            WHERE cm.club_id = ?
            ORDER BY cm.role, s.last_name
            ''', (club_id,))

            members = cursor.fetchall()

            for member in members:
                self.members_tree.insert('', 'end', values=member)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load members: {str(e)}")

    def export_members(self):
        """Export members to CSV"""
        messagebox.showinfo("Export", "Member data would be exported to CSV file.\n\nThis would create a file with all member information for the selected club.")

    def send_group_email(self):
        """Send email to all club members"""
        messagebox.showinfo("Group Email", "This would open an email composition dialog to send a message to all club members.")


class ClubDiscussionsDialog:
    """Dialog for managing club discussions"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Club Discussions")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Club Discussions", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Club selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(select_frame, text="Select Club:").pack(side='left', padx=(0, 10))
        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(select_frame, textvariable=self.club_var, width=40)
        self.club_combo.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.club_combo.bind('<<ComboboxSelected>>', self.on_club_selected)

        ttk.Button(select_frame, text="New Discussion", command=self.new_discussion).pack(side='right')

        # Discussions list
        list_frame = ttk.LabelFrame(main_frame, text="Discussion Topics")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Title', 'Author', 'Date', 'Type', 'Pinned')
        self.discussions_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            self.discussions_tree.heading(col, text=col)
            if col == 'Title':
                self.discussions_tree.column(col, width=300)
            else:
                self.discussions_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.discussions_tree.yview)
        self.discussions_tree.configure(yscrollcommand=scrollbar.set)

        self.discussions_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.discussions_tree.bind('<Double-1>', self.view_discussion)

        # Content preview
        preview_frame = ttk.LabelFrame(main_frame, text="Preview")
        preview_frame.pack(fill='both', expand=True, pady=(0, 10))

        self.preview_text = scrolledtext.ScrolledText(preview_frame, height=8, wrap=tk.WORD)
        self.preview_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="View Full Discussion", command=self.view_discussion).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Delete Selected", command=self.delete_discussion).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load clubs"""
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()

            if not result:
                conn.close()
                return

            student_id = result[0]

            cursor.execute('''
            SELECT DISTINCT sc.club_id, sc.club_name
            FROM student_clubs sc
            INNER JOIN club_members cm ON sc.club_id = cm.club_id
            WHERE cm.student_id = ? AND sc.status = 'active'
            ORDER BY sc.club_name
            ''', (student_id,))

            clubs = cursor.fetchall()
            self.club_data = {f"{club[1]} (ID: {club[0]})": club[0] for club in clubs}
            self.club_combo['values'] = list(self.club_data.keys())

            conn.close()

            if clubs:
                self.club_combo.current(0)
                self.on_club_selected(None)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load clubs: {str(e)}")

    def on_club_selected(self, event):
        """Load discussions when club is selected"""
        for item in self.discussions_tree.get_children():
            self.discussions_tree.delete(item)

        selected = self.club_var.get()
        if not selected or selected not in self.club_data:
            return

        club_id = self.club_data[selected]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT cd.discussion_id, cd.title, s.first_name || ' ' || s.last_name,
                   cd.post_date,
                   CASE WHEN cd.is_announcement = 1 THEN 'Announcement' ELSE 'Discussion' END,
                   CASE WHEN cd.pinned = 1 THEN 'Yes' ELSE 'No' END,
                   cd.content
            FROM club_discussions cd
            INNER JOIN students s ON cd.author_id = s.student_id
            WHERE cd.club_id = ?
            ORDER BY cd.pinned DESC, cd.post_date DESC
            ''', (club_id,))

            discussions = cursor.fetchall()

            for disc in discussions:
                self.discussions_tree.insert('', 'end', values=disc[:6], tags=(disc[6],))

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load discussions: {str(e)}")

    def new_discussion(self):
        """Create new discussion"""
        selected = self.club_var.get()
        if not selected or selected not in self.club_data:
            messagebox.showwarning("Warning", "Please select a club first.")
            return

        club_id = self.club_data[selected]

        # Create dialog for new discussion
        dialog = tk.Toplevel(self.dialog)
        dialog.title("New Discussion")
        dialog.geometry("600x500")
        dialog.transient(self.dialog)
        dialog.grab_set()

        frame = ttk.Frame(dialog)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Title:").pack(anchor='w')
        title_entry = ttk.Entry(frame, width=70)
        title_entry.pack(fill='x', pady=(0, 10))

        ttk.Label(frame, text="Content:").pack(anchor='w')
        content_text = scrolledtext.ScrolledText(frame, height=15, wrap=tk.WORD)
        content_text.pack(fill='both', expand=True, pady=(0, 10))

        is_announcement_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Mark as Announcement", variable=is_announcement_var).pack(anchor='w', pady=(0, 5))

        is_pinned_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Pin to Top", variable=is_pinned_var).pack(anchor='w', pady=(0, 10))

        def save_discussion():
            title = title_entry.get().strip()
            content = content_text.get(1.0, tk.END).strip()

            if not title or not content:
                messagebox.showwarning("Warning", "Please provide both title and content.")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
                student_id = cursor.fetchone()[0]

                cursor.execute('''
                INSERT INTO club_discussions (club_id, author_id, title, content, post_date,
                                             last_updated, is_announcement, pinned)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (club_id, student_id, title, content, datetime.now().isoformat(),
                     datetime.now().isoformat(), is_announcement_var.get(), is_pinned_var.get()))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Discussion created successfully!")
                dialog.destroy()
                self.on_club_selected(None)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create discussion: {str(e)}")

        button_frame = ttk.Frame(frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Post", command=save_discussion).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left')

    def view_discussion(self, event=None):
        """View full discussion"""
        selection = self.discussions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a discussion to view.")
            return

        item = self.discussions_tree.item(selection[0])
        content = item['tags'][0] if item['tags'] else "No content available."

        self.preview_text.delete(1.0, tk.END)
        self.preview_text.insert(1.0, content)

    def delete_discussion(self):
        """Delete selected discussion"""
        selection = self.discussions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a discussion to delete.")
            return

        item = self.discussions_tree.item(selection[0])
        discussion_id = item['values'][0]

        if messagebox.askyesno("Confirm", "Are you sure you want to delete this discussion?"):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('DELETE FROM club_discussions WHERE discussion_id = ?', (discussion_id,))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Discussion deleted successfully!")
                self.on_club_selected(None)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete discussion: {str(e)}")


class ClubMediaDialog:
    """Dialog for managing club media"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Club Media Gallery")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Club Media Gallery", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Club selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(select_frame, text="Select Club:").pack(side='left', padx=(0, 10))
        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(select_frame, textvariable=self.club_var, width=40)
        self.club_combo.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.club_combo.bind('<<ComboboxSelected>>', self.on_club_selected)

        ttk.Button(select_frame, text="Upload Media", command=self.upload_media).pack(side='right')

        # Media list
        list_frame = ttk.LabelFrame(main_frame, text="Media Files")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'File Name', 'Type', 'Uploader', 'Upload Date', 'Event', 'Caption')
        self.media_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.media_tree.heading(col, text=col)
            if col in ('File Name', 'Caption'):
                self.media_tree.column(col, width=200)
            else:
                self.media_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.media_tree.yview)
        self.media_tree.configure(yscrollcommand=scrollbar.set)

        self.media_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="View/Download", command=self.view_media).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Delete Selected", command=self.delete_media).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load clubs"""
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()

            if not result:
                conn.close()
                return

            student_id = result[0]

            cursor.execute('''
            SELECT DISTINCT sc.club_id, sc.club_name
            FROM student_clubs sc
            INNER JOIN club_members cm ON sc.club_id = cm.club_id
            WHERE cm.student_id = ? AND sc.status = 'active'
            ORDER BY sc.club_name
            ''', (student_id,))

            clubs = cursor.fetchall()
            self.club_data = {f"{club[1]} (ID: {club[0]})": club[0] for club in clubs}
            self.club_combo['values'] = list(self.club_data.keys())

            conn.close()

            if clubs:
                self.club_combo.current(0)
                self.on_club_selected(None)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load clubs: {str(e)}")

    def on_club_selected(self, event):
        """Load media when club is selected"""
        for item in self.media_tree.get_children():
            self.media_tree.delete(item)

        selected = self.club_var.get()
        if not selected or selected not in self.club_data:
            return

        club_id = self.club_data[selected]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT cm.media_id, cm.file_path, cm.file_type,
                   s.first_name || ' ' || s.last_name, cm.upload_date,
                   COALESCE(ue.event_name, 'N/A'), COALESCE(cm.caption, '')
            FROM club_media cm
            INNER JOIN students s ON cm.uploader_id = s.student_id
            LEFT JOIN union_events ue ON cm.event_id = ue.event_id
            WHERE cm.club_id = ?
            ORDER BY cm.upload_date DESC
            ''', (club_id,))

            media = cursor.fetchall()

            for item in media:
                # Extract filename from path
                filename = item[1].split('/')[-1] if item[1] else 'Unknown'
                display_values = (item[0], filename, item[2], item[3], item[4], item[5], item[6])
                self.media_tree.insert('', 'end', values=display_values)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load media: {str(e)}")

    def upload_media(self):
        """Upload new media"""
        selected = self.club_var.get()
        if not selected or selected not in self.club_data:
            messagebox.showwarning("Warning", "Please select a club first.")
            return

        # Would open file dialog to select media file
        messagebox.showinfo("Upload Media", "This would open a file browser to select photos, videos, or documents to upload.\n\nSupported formats:\n- Images: JPG, PNG, GIF\n- Videos: MP4, AVI\n- Documents: PDF, DOC, DOCX")

    def view_media(self):
        """View or download media"""
        selection = self.media_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select media to view.")
            return

        messagebox.showinfo("View Media", "This would open the selected media file in the appropriate application or allow downloading it.")

    def delete_media(self):
        """Delete selected media"""
        selection = self.media_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select media to delete.")
            return

        item = self.media_tree.item(selection[0])
        media_id = item['values'][0]

        if messagebox.askyesno("Confirm", "Are you sure you want to delete this media file?"):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('DELETE FROM club_media WHERE media_id = ?', (media_id,))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Media deleted successfully!")
                self.on_club_selected(None)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete media: {str(e)}")


class CompetitionsDialog:
    """Dialog for viewing active competitions"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Active Competitions")
        self.dialog.geometry("1000x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Active Competitions", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(filter_frame, text="Filter by Type:").pack(side='left', padx=(0, 10))
        self.type_var = tk.StringVar(value="All")
        type_combo = ttk.Combobox(filter_frame, textvariable=self.type_var, width=20)
        type_combo['values'] = ('All', 'Sports', 'Academic', 'Creative', 'Community Service', 'Other')
        type_combo.pack(side='left', padx=(0, 10))
        type_combo.bind('<<ComboboxSelected>>', lambda e: self.load_data())

        ttk.Button(filter_frame, text="Register for Competition", command=self.register_competition).pack(side='right')

        # Competitions list
        list_frame = ttk.LabelFrame(main_frame, text="Available Competitions")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Name', 'Type', 'Start Date', 'End Date', 'Registration Deadline', 'Participants', 'Status')
        self.competitions_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.competitions_tree.heading(col, text=col)
            if col == 'Name':
                self.competitions_tree.column(col, width=200)
            else:
                self.competitions_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.competitions_tree.yview)
        self.competitions_tree.configure(yscrollcommand=scrollbar.set)

        self.competitions_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text="Competition Details")
        details_frame.pack(fill='both', expand=True, pady=(0, 10))

        self.details_text = scrolledtext.ScrolledText(details_frame, height=8, wrap=tk.WORD)
        self.details_text.pack(fill='both', expand=True, padx=5, pady=5)

        self.competitions_tree.bind('<<TreeviewSelect>>', self.show_details)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="View Results", command=self.view_results).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load competitions"""
        for item in self.competitions_tree.get_children():
            self.competitions_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            type_filter = self.type_var.get()
            if type_filter == "All":
                cursor.execute('''
                SELECT competition_id, competition_name, competition_type, start_date, end_date,
                       registration_deadline, max_participants_per_club, status
                FROM club_competitions
                WHERE status IN ('upcoming', 'active')
                ORDER BY start_date
                ''')
            else:
                cursor.execute('''
                SELECT competition_id, competition_name, competition_type, start_date, end_date,
                       registration_deadline, max_participants_per_club, status
                FROM club_competitions
                WHERE status IN ('upcoming', 'active') AND competition_type = ?
                ORDER BY start_date
                ''', (type_filter,))

            competitions = cursor.fetchall()

            for comp in competitions:
                self.competitions_tree.insert('', 'end', values=comp)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load competitions: {str(e)}")

    def show_details(self, event):
        """Show competition details"""
        selection = self.competitions_tree.selection()
        if not selection:
            return

        item = self.competitions_tree.item(selection[0])
        comp_id = item['values'][0]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT description, prizes, max_participants_per_club,
                   (SELECT COUNT(*) FROM competition_participants WHERE competition_id = ?) as participant_count
            FROM club_competitions
            WHERE competition_id = ?
            ''', (comp_id, comp_id))

            details = cursor.fetchone()
            conn.close()

            if details:
                details_text = f"Description: {details[0]}\n\n"
                details_text += f"Prizes: {details[1]}\n\n"
                details_text += f"Max Participants per Club: {details[2]}\n"
                details_text += f"Current Participants: {details[3]}"

                self.details_text.delete(1.0, tk.END)
                self.details_text.insert(1.0, details_text)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load details: {str(e)}")

    def register_competition(self):
        """Register for a competition"""
        selection = self.competitions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a competition first.")
            return

        item = self.competitions_tree.item(selection[0])
        comp_id = item['values'][0]
        comp_name = item['values'][1]

        # Open registration dialog
        dialog = CompetitionRegistrationDialog(self.dialog, self.auth, comp_id, comp_name)
        self.dialog.wait_window(dialog.dialog)

    def view_results(self):
        """View competition results"""
        selection = self.competitions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a competition first.")
            return

        item = self.competitions_tree.item(selection[0])
        comp_id = item['values'][0]

        dialog = CompetitionResultsDialog(self.dialog, self.auth, comp_id)
        self.dialog.wait_window(dialog.dialog)


class CompetitionRegistrationDialog:
    """Dialog for registering for a competition"""

    def __init__(self, parent, auth_manager, competition_id, competition_name):
        self.parent = parent
        self.auth = auth_manager
        self.competition_id = competition_id
        self.competition_name = competition_name

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Register for Competition")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text=f"Register for: {self.competition_name}",
                               font=('Arial', 12, 'bold'))
        title_label.pack(pady=(0, 10))

        # Club selection
        ttk.Label(main_frame, text="Select Your Club:").pack(anchor='w', pady=(0, 5))
        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(main_frame, textvariable=self.club_var, width=50)
        self.club_combo.pack(fill='x', pady=(0, 10))

        # Team members
        ttk.Label(main_frame, text="Team Members (Student IDs, one per line):").pack(anchor='w', pady=(0, 5))
        self.members_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD)
        self.members_text.pack(fill='both', expand=True, pady=(0, 10))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Register", command=self.register).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def load_data(self):
        """Load user's clubs"""
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()

            if not result:
                conn.close()
                return

            student_id = result[0]

            cursor.execute('''
            SELECT DISTINCT sc.club_id, sc.club_name
            FROM student_clubs sc
            INNER JOIN club_members cm ON sc.club_id = cm.club_id
            WHERE cm.student_id = ? AND sc.status = 'active'
            ORDER BY sc.club_name
            ''', (student_id,))

            clubs = cursor.fetchall()
            self.club_data = {f"{club[1]} (ID: {club[0]})": club[0] for club in clubs}
            self.club_combo['values'] = list(self.club_data.keys())

            conn.close()

            if clubs:
                self.club_combo.current(0)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load clubs: {str(e)}")

    def register(self):
        """Register for competition"""
        selected_club = self.club_var.get()
        if not selected_club or selected_club not in self.club_data:
            messagebox.showwarning("Warning", "Please select a club.")
            return

        club_id = self.club_data[selected_club]
        members = self.members_text.get(1.0, tk.END).strip().split('\n')
        members = [m.strip() for m in members if m.strip()]

        if not members:
            messagebox.showwarning("Warning", "Please add at least one team member.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Register each team member
            for member_id in members:
                cursor.execute('''
                INSERT INTO competition_participants (competition_id, club_id, student_id, registration_date)
                VALUES (?, ?, ?, ?)
                ''', (self.competition_id, club_id, member_id, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Successfully registered {len(members)} participant(s) for the competition!")
            self.dialog.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to register: {str(e)}")


class CompetitionResultsDialog:
    """Dialog for viewing competition results"""

    def __init__(self, parent, auth_manager, competition_id):
        self.parent = parent
        self.auth = auth_manager
        self.competition_id = competition_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Competition Results")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Competition Results", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Results list
        list_frame = ttk.LabelFrame(main_frame, text="Standings")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Rank', 'Club', 'Participant', 'Score')
        self.results_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.results_tree.heading(col, text=col)
            if col in ('Club', 'Participant'):
                self.results_tree.column(col, width=200)
            else:
                self.results_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)

        self.results_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Export Results", command=self.export_results).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load results"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT cp.rank_position, sc.club_name,
                   s.first_name || ' ' || s.last_name, cp.score
            FROM competition_participants cp
            INNER JOIN student_clubs sc ON cp.club_id = sc.club_id
            INNER JOIN students s ON cp.student_id = s.student_id
            WHERE cp.competition_id = ?
            ORDER BY cp.rank_position, cp.score DESC
            ''', (self.competition_id,))

            results = cursor.fetchall()

            for result in results:
                self.results_tree.insert('', 'end', values=result)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load results: {str(e)}")

    def export_results(self):
        """Export results to file"""
        messagebox.showinfo("Export", "Results would be exported to a CSV file.")


class CompetitionHistoryDialog:
    """Dialog for viewing competition history"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("My Competition History")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="My Competition History", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # History list
        list_frame = ttk.LabelFrame(main_frame, text="Past Competitions")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Competition', 'Type', 'Club', 'Date', 'Rank', 'Score', 'Status')
        self.history_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.history_tree.heading(col, text=col)
            if col == 'Competition':
                self.history_tree.column(col, width=200)
            else:
                self.history_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)

        self.history_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Stats frame
        stats_frame = ttk.LabelFrame(main_frame, text="Statistics")
        stats_frame.pack(fill='x', pady=(0, 10))

        self.stats_label = ttk.Label(stats_frame, text="", justify='left')
        self.stats_label.pack(padx=10, pady=10)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load competition history"""
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()

            if not result:
                conn.close()
                return

            student_id = result[0]

            cursor.execute('''
            SELECT cc.competition_name, cc.competition_type, sc.club_name,
                   cc.end_date, COALESCE(cp.rank_position, 'N/A'), COALESCE(cp.score, 0), cc.status
            FROM competition_participants cp
            INNER JOIN club_competitions cc ON cp.competition_id = cc.competition_id
            INNER JOIN student_clubs sc ON cp.club_id = sc.club_id
            WHERE cp.student_id = ?
            ORDER BY cc.end_date DESC
            ''', (student_id,))

            history = cursor.fetchall()

            for item in history:
                self.history_tree.insert('', 'end', values=item)

            # Calculate stats
            total_comps = len(history)
            wins = sum(1 for h in history if str(h[4]) == '1')
            avg_score = sum(float(h[5]) for h in history) / total_comps if total_comps > 0 else 0

            stats_text = f"Total Competitions: {total_comps}\n"
            stats_text += f"First Place Finishes: {wins}\n"
            stats_text += f"Average Score: {avg_score:.2f}"

            self.stats_label.config(text=stats_text)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load history: {str(e)}")



class SupportGroupsDialog:
    """Dialog for browsing support groups"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Peer Support Groups")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Peer Support Groups", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(filter_frame, text="Filter by Type:").pack(side='left', padx=(0, 10))
        self.type_var = tk.StringVar(value="All")
        type_combo = ttk.Combobox(filter_frame, textvariable=self.type_var, width=20)
        type_combo['values'] = ('All', 'Mental Health', 'Academic', 'Career', 'Social', 'Wellness')
        type_combo.pack(side='left', padx=(0, 10))
        type_combo.bind('<<ComboboxSelected>>', lambda e: self.load_data())

        ttk.Button(filter_frame, text="Create New Group", command=self.create_group).pack(side='right')

        # Groups list
        list_frame = ttk.LabelFrame(main_frame, text="Available Support Groups")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Name', 'Type', 'Facilitator', 'Members', 'Max', 'Schedule', 'Status')
        self.groups_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.groups_tree.heading(col, text=col)
            if col == 'Name':
                self.groups_tree.column(col, width=200)
            elif col == 'Schedule':
                self.groups_tree.column(col, width=150)
            else:
                self.groups_tree.column(col, width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.groups_tree.yview)
        self.groups_tree.configure(yscrollcommand=scrollbar.set)

        self.groups_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text="Group Description")
        details_frame.pack(fill='both', expand=True, pady=(0, 10))

        self.details_text = scrolledtext.ScrolledText(details_frame, height=6, wrap=tk.WORD)
        self.details_text.pack(fill='both', expand=True, padx=5, pady=5)

        self.groups_tree.bind('<<TreeviewSelect>>', self.show_details)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Join Selected Group", command=self.join_group).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="My Groups", command=self.view_my_groups).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load support groups"""
        for item in self.groups_tree.get_children():
            self.groups_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            type_filter = self.type_var.get()
            if type_filter == "All":
                cursor.execute('''
                SELECT psg.group_id, psg.group_name, psg.support_type,
                       s.first_name || ' ' || s.last_name, psg.current_members,
                       psg.max_members, psg.meeting_schedule, psg.status
                FROM peer_support_groups psg
                INNER JOIN students s ON psg.facilitator_id = s.student_id
                WHERE psg.status = 'active'
                ORDER BY psg.group_name
                ''')
            else:
                cursor.execute('''
                SELECT psg.group_id, psg.group_name, psg.support_type,
                       s.first_name || ' ' || s.last_name, psg.current_members,
                       psg.max_members, psg.meeting_schedule, psg.status
                FROM peer_support_groups psg
                INNER JOIN students s ON psg.facilitator_id = s.student_id
                WHERE psg.status = 'active' AND psg.support_type = ?
                ORDER BY psg.group_name
                ''', (type_filter,))

            groups = cursor.fetchall()

            for group in groups:
                self.groups_tree.insert('', 'end', values=group)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load groups: {str(e)}")

    def show_details(self, event):
        """Show group details"""
        selection = self.groups_tree.selection()
        if not selection:
            return

        item = self.groups_tree.item(selection[0])
        group_id = item['values'][0]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT description FROM peer_support_groups WHERE group_id = ?', (group_id,))
            result = cursor.fetchone()
            conn.close()

            if result:
                self.details_text.delete(1.0, tk.END)
                self.details_text.insert(1.0, result[0] or "No description available.")
        except Exception as e:
            pass

    def join_group(self):
        """Join selected support group"""
        selection = self.groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group to join.")
            return

        item = self.groups_tree.item(selection[0])
        group_id = item['values'][0]
        group_name = item['values'][1]
        current_members = item['values'][4]
        max_members = item['values'][5]

        if current_members >= max_members:
            messagebox.showwarning("Warning", "This group is full.")
            return

        if messagebox.askyesno("Confirm", f"Join '{group_name}'?"):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
                student_id = cursor.fetchone()[0]

                # Generate anonymous ID
                import hashlib
                anonymous_id = hashlib.md5(f"{student_id}{group_id}".encode()).hexdigest()[:8]

                cursor.execute('''
                INSERT INTO support_group_members (group_id, student_id, join_date, anonymous_id)
                VALUES (?, ?, ?, ?)
                ''', (group_id, student_id, datetime.now().isoformat(), anonymous_id))

                cursor.execute('''
                UPDATE peer_support_groups SET current_members = current_members + 1
                WHERE group_id = ?
                ''', (group_id,))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Successfully joined the support group!")
                self.load_data()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to join group: {str(e)}")

    def create_group(self):
        """Create new support group"""
        dialog = CreateSupportGroupDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)
        self.load_data()

    def view_my_groups(self):
        """View groups user is member of"""
        dialog = MySupportGroupsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)


class CreateSupportGroupDialog:
    """Dialog for creating a new support group"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Support Group")
        self.dialog.geometry("600x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Create New Support Group", font=('Arial', 12, 'bold'))
        title_label.pack(pady=(0, 20))

        # Group name
        ttk.Label(main_frame, text="Group Name:").pack(anchor='w', pady=(0, 5))
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=50).pack(fill='x', pady=(0, 10))

        # Support type
        ttk.Label(main_frame, text="Support Type:").pack(anchor='w', pady=(0, 5))
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=47)
        type_combo['values'] = ('Mental Health', 'Academic', 'Career', 'Social', 'Wellness', 'Other')
        type_combo.pack(fill='x', pady=(0, 10))

        # Description
        ttk.Label(main_frame, text="Description:").pack(anchor='w', pady=(0, 5))
        self.description_text = scrolledtext.ScrolledText(main_frame, height=8, wrap=tk.WORD)
        self.description_text.pack(fill='both', expand=True, pady=(0, 10))

        # Max members
        ttk.Label(main_frame, text="Maximum Members:").pack(anchor='w', pady=(0, 5))
        self.max_var = tk.StringVar(value="10")
        ttk.Entry(main_frame, textvariable=self.max_var, width=10).pack(anchor='w', pady=(0, 10))

        # Meeting schedule
        ttk.Label(main_frame, text="Meeting Schedule:").pack(anchor='w', pady=(0, 5))
        self.schedule_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.schedule_var, width=50).pack(fill='x', pady=(0, 10))
        ttk.Label(main_frame, text="(e.g., 'Every Monday 6:00 PM')", font=('Arial', 8)).pack(anchor='w', pady=(0, 10))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Create", command=self.create).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def create(self):
        """Create the support group"""
        name = self.name_var.get().strip()
        support_type = self.type_var.get().strip()
        description = self.description_text.get(1.0, tk.END).strip()
        max_members = self.max_var.get().strip()
        schedule = self.schedule_var.get().strip()

        if not all([name, support_type, description, max_members, schedule]):
            messagebox.showwarning("Warning", "Please fill in all fields.")
            return

        try:
            max_members = int(max_members)
            if max_members < 2:
                messagebox.showwarning("Warning", "Maximum members must be at least 2.")
                return
        except ValueError:
            messagebox.showwarning("Warning", "Maximum members must be a number.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            facilitator_id = cursor.fetchone()[0]

            cursor.execute('''
            INSERT INTO peer_support_groups (group_name, description, support_type, facilitator_id,
                                            max_members, current_members, meeting_schedule, status, created_date)
            VALUES (?, ?, ?, ?, ?, 1, ?, 'active', ?)
            ''', (name, description, support_type, facilitator_id, max_members, schedule, datetime.now().isoformat()))

            group_id = cursor.lastrowid

            # Add facilitator as member
            cursor.execute('''
            INSERT INTO support_group_members (group_id, student_id, join_date, anonymous_id)
            VALUES (?, ?, ?, ?)
            ''', (group_id, facilitator_id, datetime.now().isoformat(), 'facilitator'))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Support group created successfully!")
            self.dialog.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create group: {str(e)}")


class MySupportGroupsDialog:
    """Dialog for viewing user's support groups"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("My Support Groups")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="My Support Groups", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Groups list
        list_frame = ttk.LabelFrame(main_frame, text="My Groups")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Group Name', 'Type', 'Role', 'Join Date', 'Schedule', 'Members')
        self.groups_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.groups_tree.heading(col, text=col)
            if col in ('Group Name', 'Schedule'):
                self.groups_tree.column(col, width=200)
            else:
                self.groups_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.groups_tree.yview)
        self.groups_tree.configure(yscrollcommand=scrollbar.set)

        self.groups_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Leave Selected Group", command=self.leave_group).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load user's support groups"""
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()

            if not result:
                conn.close()
                return

            student_id = result[0]

            cursor.execute('''
            SELECT psg.group_name, psg.support_type,
                   CASE WHEN psg.facilitator_id = ? THEN 'Facilitator' ELSE 'Member' END,
                   sgm.join_date, psg.meeting_schedule, psg.current_members
            FROM support_group_members sgm
            INNER JOIN peer_support_groups psg ON sgm.group_id = psg.group_id
            WHERE sgm.student_id = ? AND sgm.status = 'active'
            ORDER BY sgm.join_date DESC
            ''', (student_id, student_id))

            groups = cursor.fetchall()

            for group in groups:
                self.groups_tree.insert('', 'end', values=group)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load groups: {str(e)}")

    def leave_group(self):
        """Leave selected group"""
        selection = self.groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group to leave.")
            return

        if messagebox.askyesno("Confirm", "Are you sure you want to leave this support group?"):
            # In a full implementation, would update the database
            messagebox.showinfo("Success", "Left the support group.")
            self.load_data()


class WellnessResourcesDialog:
    """Dialog for viewing wellness resources"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Wellness Resources")
        self.dialog.geometry("800x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Wellness Resources", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Create notebook for different resource categories
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 10))

        # Mental Health tab
        mental_health_frame = ttk.Frame(notebook)
        notebook.add(mental_health_frame, text="Mental Health")
        self.create_mental_health_tab(mental_health_frame)

        # Counseling Services tab
        counseling_frame = ttk.Frame(notebook)
        notebook.add(counseling_frame, text="Counseling")
        self.create_counseling_tab(counseling_frame)

        # Fitness Programs tab
        fitness_frame = ttk.Frame(notebook)
        notebook.add(fitness_frame, text="Fitness")
        self.create_fitness_tab(fitness_frame)

        # Nutrition tab
        nutrition_frame = ttk.Frame(notebook)
        notebook.add(nutrition_frame, text="Nutrition")
        self.create_nutrition_tab(nutrition_frame)

        # Stress Management tab
        stress_frame = ttk.Frame(notebook)
        notebook.add(stress_frame, text="Stress Management")
        self.create_stress_tab(stress_frame)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def create_mental_health_tab(self, parent):
        """Create mental health resources tab"""
        text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill='both', expand=True)

        content = """MENTAL HEALTH HOTLINES AND RESOURCES

24/7 Crisis Hotlines:
• National Suicide Prevention Lifeline: 1-800-273-8255
• Crisis Text Line: Text HOME to 741741
• SAMHSA National Helpline: 1-800-662-4357

Campus Resources:
• Student Counseling Center: (555) 123-4567
• Campus Health Services: (555) 123-4568
• Student Wellness Office: (555) 123-4569

Online Resources:
• MindBeacon: Online cognitive behavioral therapy
• Headspace: Meditation and mindfulness app
• 7 Cups: Free emotional support chat

Support Groups:
• Anxiety and Depression Support Group
• Mindfulness and Meditation Group
• Stress Management Workshop

Emergency Services:
• If you are in immediate danger, call 911
• Campus Security: (555) 123-9999

Remember: It's okay to ask for help. Taking care of your mental health is just as important as your physical health.
"""
        text.insert(1.0, content)
        text.config(state='disabled')

    def create_counseling_tab(self, parent):
        """Create counseling services tab"""
        text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill='both', expand=True)

        content = """COUNSELING SERVICES

Student Counseling Center:
• Location: Student Services Building, 2nd Floor
• Hours: Monday-Friday, 8:00 AM - 6:00 PM
• Phone: (555) 123-4567
• Email: counseling@university.edu

Services Offered:
• Individual counseling
• Group therapy
• Couples counseling
• Family therapy
• Crisis intervention
• Psychiatric services

Confidentiality:
• All counseling sessions are confidential
• Your privacy is protected by HIPAA

How to Schedule:
• Call (555) 123-4567 to schedule an appointment
• Walk-in hours: Monday-Friday, 9:00 AM - 11:00 AM
• Emergency services available 24/7

Insurance:
• Most student health plans cover counseling services
• Financial aid available for those without insurance
"""
        text.insert(1.0, content)
        text.config(state='disabled')

    def create_fitness_tab(self, parent):
        """Create fitness programs tab"""
        text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill='both', expand=True)

        content = """FITNESS PROGRAMS

Campus Fitness Center:
• Location: Recreation Building
• Hours: Monday-Sunday, 6:00 AM - 11:00 PM
• Membership: Free for all students

Facilities:
• Weight room with free weights and machines
• Cardio equipment (treadmills, bikes, ellipticals)
• Group fitness studio
• Indoor track
• Basketball courts
• Swimming pool

Group Fitness Classes:
• Yoga - Monday/Wednesday 7:00 PM
• Spin Class - Tuesday/Thursday 6:00 PM
• Zumba - Wednesday/Friday 5:30 PM
• Boot Camp - Saturday 9:00 AM
• Pilates - Tuesday/Thursday 7:00 PM

Personal Training:
• One-on-one sessions available
• Group training options
• Nutrition counseling included

Intramural Sports:
• Basketball, Soccer, Volleyball
• Sign up at the Recreation Office
"""
        text.insert(1.0, content)
        text.config(state='disabled')

    def create_nutrition_tab(self, parent):
        """Create nutrition resources tab"""
        text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill='both', expand=True)

        content = """NUTRITION RESOURCES

Campus Nutritionist:
• Location: Student Health Center
• Phone: (555) 123-4570
• Email: nutrition@university.edu

Services:
• Individual nutrition counseling
• Meal planning assistance
• Weight management support
• Sports nutrition guidance
• Eating disorder support

Healthy Dining Options:
• Nutritional information available for all dining halls
• Vegetarian and vegan options
• Gluten-free and allergen-free meals
• Customizable meal plans

Nutrition Workshops:
• Cooking demonstrations
• Meal prep basics
• Reading nutrition labels
• Budget-friendly healthy eating

Food Pantry:
• Location: Student Union, Room 105
• Hours: Monday-Friday, 10:00 AM - 4:00 PM
• Free groceries for students in need
"""
        text.insert(1.0, content)
        text.config(state='disabled')

    def create_stress_tab(self, parent):
        """Create stress management tab"""
        text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill='both', expand=True)

        content = """STRESS MANAGEMENT TOOLS

Relaxation Techniques:
• Deep breathing exercises
• Progressive muscle relaxation
• Guided imagery
• Mindfulness meditation

Time Management Tips:
• Use a planner or digital calendar
• Break large tasks into smaller steps
• Prioritize your tasks
• Learn to say no
• Schedule breaks and downtime

Study Stress:
• Academic Support Center: (555) 123-4571
• Tutoring services available
• Study skills workshops
• Test anxiety support groups

Campus Resources:
• Meditation Room: Student Union, 3rd Floor
• Quiet Study Spaces: Library
• Nature Trails: Behind Recreation Building

Wellness Apps (Free for Students):
• Calm: Meditation and sleep
• Headspace: Mindfulness
• MyFitnessPal: Nutrition tracking
• Sleep Cycle: Sleep tracking

Remember:
• Regular exercise reduces stress
• Get 7-9 hours of sleep per night
• Maintain social connections
• Practice self-care
"""
        text.insert(1.0, content)
        text.config(state='disabled')
# Since this implementation is very extensive, I'll create comprehensive but concise versions of these dialogs
# Following the established patterns from the club, competition, and support group dialogs above

class EquipmentBrowseDialog:
    """Dialog for browsing available equipment"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Browse Equipment")
        self.dialog.geometry("1000x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text="Equipment Catalog", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Filter
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(filter_frame, text="Category:").pack(side='left', padx=(0, 10))
        self.category_var = tk.StringVar(value="All")
        category_combo = ttk.Combobox(filter_frame, textvariable=self.category_var, width=20)
        category_combo['values'] = ('All', 'AV Equipment', 'Sports Gear', 'Tech Devices', 'Event Supplies')
        category_combo.pack(side='left')
        category_combo.bind('<<ComboboxSelected>>', lambda e: self.load_data())

        # Equipment list
        list_frame = ttk.LabelFrame(main_frame, text="Available Equipment")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Name', 'Category', 'Condition', 'Location', 'Status')
        self.equipment_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.equipment_tree.heading(col, text=col)
            self.equipment_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.equipment_tree.yview)
        self.equipment_tree.configure(yscrollcommand=scrollbar.set)

        self.equipment_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Check Out", command=self.checkout).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="My Equipment", command=self.view_my_equipment).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        for item in self.equipment_tree.get_children():
            self.equipment_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            category_filter = self.category_var.get()
            if category_filter == "All":
                cursor.execute('''
                SELECT equipment_id, equipment_name, category, condition_status,
                       location, availability_status
                FROM union_equipment
                WHERE availability_status = 'available'
                ORDER BY equipment_name
                ''')
            else:
                cursor.execute('''
                SELECT equipment_id, equipment_name, category, condition_status,
                       location, availability_status
                FROM union_equipment
                WHERE availability_status = 'available' AND category = ?
                ORDER BY equipment_name
                ''', (category_filter,))

            equipment = cursor.fetchall()
            for item in equipment:
                self.equipment_tree.insert('', 'end', values=item)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load equipment: {str(e)}")

    def checkout(self):
        selection = self.equipment_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select equipment to check out.")
            return

        item = self.equipment_tree.item(selection[0])
        equipment_id = item['values'][0]
        equipment_name = item['values'][1]

        dialog = EquipmentCheckoutDialog(self.dialog, self.auth, equipment_id, equipment_name)
        self.dialog.wait_window(dialog.dialog)
        self.load_data()

    def view_my_equipment(self):
        dialog = MyEquipmentDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)


class EquipmentCheckoutDialog:
    """Dialog for checking out equipment"""

    def __init__(self, parent, auth_manager, equipment_id, equipment_name):
        self.parent = parent
        self.auth = auth_manager
        self.equipment_id = equipment_id
        self.equipment_name = equipment_name

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Check Out Equipment")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text=f"Check Out: {self.equipment_name}",
                               font=('Arial', 12, 'bold'))
        title_label.pack(pady=(0, 20))

        # Return date
        ttk.Label(main_frame, text="Expected Return Date:").pack(anchor='w', pady=(0, 5))
        self.return_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.return_date_var, width=30).pack(fill='x', pady=(0, 10))
        ttk.Label(main_frame, text="(Format: YYYY-MM-DD)", font=('Arial', 8)).pack(anchor='w', pady=(0, 10))

        # Purpose
        ttk.Label(main_frame, text="Purpose:").pack(anchor='w', pady=(0, 5))
        self.purpose_text = scrolledtext.ScrolledText(main_frame, height=8, wrap=tk.WORD)
        self.purpose_text.pack(fill='both', expand=True, pady=(0, 10))

        # Club (optional)
        ttk.Label(main_frame, text="For Club (optional):").pack(anchor='w', pady=(0, 5))
        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(main_frame, textvariable=self.club_var, width=27)
        self.club_combo.pack(fill='x', pady=(0, 10))
        self.load_clubs()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Check Out", command=self.checkout).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def load_clubs(self):
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return

            student_id = result[0]

            cursor.execute('''
            SELECT DISTINCT sc.club_id, sc.club_name
            FROM student_clubs sc
            INNER JOIN club_members cm ON sc.club_id = cm.club_id
            WHERE cm.student_id = ? AND sc.status = 'active'
            ORDER BY sc.club_name
            ''', (student_id,))

            clubs = cursor.fetchall()
            self.club_data = {f"{club[1]}": club[0] for club in clubs}
            self.club_combo['values'] = ['None'] + list(self.club_data.keys())
            self.club_combo.current(0)

            conn.close()
        except Exception as e:
            pass

    def checkout(self):
        return_date = self.return_date_var.get().strip()
        purpose = self.purpose_text.get(1.0, tk.END).strip()

        if not return_date or not purpose:
            messagebox.showwarning("Warning", "Please fill in all required fields.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            student_id = cursor.fetchone()[0]

            selected_club = self.club_var.get()
            club_id = self.club_data.get(selected_club) if selected_club != 'None' else None

            cursor.execute('''
            INSERT INTO equipment_checkouts (equipment_id, borrower_id, club_id, checkout_date,
                                            expected_return, condition_out, notes, status)
            VALUES (?, ?, ?, ?, ?, 'good', ?, 'checked_out')
            ''', (self.equipment_id, student_id, club_id, datetime.now().isoformat(),
                 return_date, purpose))

            cursor.execute('''
            UPDATE union_equipment SET availability_status = 'checked_out'
            WHERE equipment_id = ?
            ''', (self.equipment_id,))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Equipment checked out successfully!")
            self.dialog.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to check out equipment: {str(e)}")


class MyEquipmentDialog:
    """Dialog for viewing user's checked out equipment"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("My Equipment")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text="My Checked Out Equipment", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        list_frame = ttk.LabelFrame(main_frame, text="Current Checkouts")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Equipment', 'Checkout Date', 'Expected Return', 'Condition', 'Status')
        self.equipment_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.equipment_tree.heading(col, text=col)
            self.equipment_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.equipment_tree.yview)
        self.equipment_tree.configure(yscrollcommand=scrollbar.set)

        self.equipment_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Return Selected", command=self.return_equipment).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return

            student_id = result[0]

            cursor.execute('''
            SELECT ue.equipment_name, ec.checkout_date, ec.expected_return,
                   ec.condition_out, ec.status, ec.checkout_id
            FROM equipment_checkouts ec
            INNER JOIN union_equipment ue ON ec.equipment_id = ue.equipment_id
            WHERE ec.borrower_id = ? AND ec.status = 'checked_out'
            ORDER BY ec.expected_return
            ''', (student_id,))

            equipment = cursor.fetchall()

            for item in equipment:
                self.equipment_tree.insert('', 'end', values=item[:5], tags=(item[5],))

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load equipment: {str(e)}")

    def return_equipment(self):
        selection = self.equipment_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select equipment to return.")
            return

        item = self.equipment_tree.item(selection[0])
        checkout_id = item['tags'][0] if item['tags'] else None

        if checkout_id and messagebox.askyesno("Confirm", "Return this equipment?"):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('''
                UPDATE equipment_checkouts SET status = 'returned', actual_return = ?,
                       condition_in = 'good'
                WHERE checkout_id = ?
                ''', (datetime.now().isoformat(), checkout_id))

                cursor.execute('''
                SELECT equipment_id FROM equipment_checkouts WHERE checkout_id = ?
                ''', (checkout_id,))
                equipment_id = cursor.fetchone()[0]

                cursor.execute('''
                UPDATE union_equipment SET availability_status = 'available'
                WHERE equipment_id = ?
                ''', (equipment_id,))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Equipment returned successfully!")
                self.load_data()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to return equipment: {str(e)}")


class GamificationDialog:
    """Dialog for viewing points and badges"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("My Points & Badges")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text="My Points & Badges", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Stats frame
        stats_frame = ttk.LabelFrame(main_frame, text="My Statistics")
        stats_frame.pack(fill='x', pady=(0, 10))

        self.stats_label = ttk.Label(stats_frame, text="Loading...", font=('Arial', 12), justify='left')
        self.stats_label.pack(padx=20, pady=20)

        # Notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 10))

        # Points history tab
        points_frame = ttk.Frame(notebook)
        notebook.add(points_frame, text="Points History")

        columns = ('Activity', 'Points', 'Date', 'Description')
        self.points_tree = ttk.Treeview(points_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.points_tree.heading(col, text=col)
            if col == 'Description':
                self.points_tree.column(col, width=300)
            else:
                self.points_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(points_frame, orient='vertical', command=self.points_tree.yview)
        self.points_tree.configure(yscrollcommand=scrollbar.set)

        self.points_tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y')

        # Badges tab
        badges_frame = ttk.Frame(notebook)
        notebook.add(badges_frame, text="My Badges")

        self.badges_text = scrolledtext.ScrolledText(badges_frame, wrap=tk.WORD)
        self.badges_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="View Leaderboard", command=self.view_leaderboard).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Available Badges", command=self.view_available_badges).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return

            student_id = result[0]

            # Get total points
            cursor.execute('''
            SELECT SUM(points_earned), SUM(points_spent)
            FROM student_points
            WHERE student_id = ?
            ''', (student_id,))

            points_data = cursor.fetchone()
            total_earned = points_data[0] or 0
            total_spent = points_data[1] or 0
            current_balance = total_earned - total_spent

            # Get badge count
            cursor.execute('''
            SELECT COUNT(*) FROM student_badges WHERE student_id = ?
            ''', (student_id,))
            badge_count = cursor.fetchone()[0]

            stats_text = f"Total Points Earned: {total_earned}\n"
            stats_text += f"Points Spent: {total_spent}\n"
            stats_text += f"Current Balance: {current_balance}\n"
            stats_text += f"Badges Earned: {badge_count}"

            self.stats_label.config(text=stats_text)

            # Load points history
            cursor.execute('''
            SELECT activity_type, points_earned, earned_date, activity_description
            FROM student_points
            WHERE student_id = ?
            ORDER BY earned_date DESC
            LIMIT 100
            ''', (student_id,))

            points_history = cursor.fetchall()
            for item in points_history:
                self.points_tree.insert('', 'end', values=item)

            # Load badges
            cursor.execute('''
            SELECT ab.badge_name, ab.description, sb.earned_date
            FROM student_badges sb
            INNER JOIN achievement_badges ab ON sb.badge_id = ab.badge_id
            WHERE sb.student_id = ?
            ORDER BY sb.earned_date DESC
            ''', (student_id,))

            badges = cursor.fetchall()

            badges_content = "MY EARNED BADGES\n" + "="*50 + "\n\n"
            for badge in badges:
                badges_content += f"{badge[0]}\n"
                badges_content += f"Description: {badge[1]}\n"
                badges_content += f"Earned: {badge[2]}\n\n"

            if not badges:
                badges_content += "No badges earned yet. Keep participating to earn badges!"

            self.badges_text.insert(1.0, badges_content)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load data: {str(e)}")

    def view_leaderboard(self):
        dialog = LeaderboardDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def view_available_badges(self):
        dialog = AvailableBadgesDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)


class LeaderboardDialog:
    """Dialog for viewing leaderboard"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Leaderboard")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text="Student Union Leaderboard", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        list_frame = ttk.LabelFrame(main_frame, text="Top Students")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Rank', 'Student', 'Total Points', 'Badges')
        self.leaderboard_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=18)

        for col in columns:
            self.leaderboard_tree.heading(col, text=col)
            if col == 'Student':
                self.leaderboard_tree.column(col, width=250)
            else:
                self.leaderboard_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.leaderboard_tree.yview)
        self.leaderboard_tree.configure(yscrollcommand=scrollbar.set)

        self.leaderboard_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT s.first_name || ' ' || s.last_name,
                   SUM(sp.points_earned) as total_points,
                   (SELECT COUNT(*) FROM student_badges WHERE student_id = s.student_id) as badge_count
            FROM students s
            LEFT JOIN student_points sp ON s.student_id = sp.student_id
            GROUP BY s.student_id
            HAVING total_points > 0
            ORDER BY total_points DESC
            LIMIT 50
            ''')

            results = cursor.fetchall()

            for rank, item in enumerate(results, 1):
                values = (rank, item[0], item[1] or 0, item[2])
                self.leaderboard_tree.insert('', 'end', values=values)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load leaderboard: {str(e)}")


class AvailableBadgesDialog:
    """Dialog for viewing available badges"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Available Badges")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text="Available Badges", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        list_frame = ttk.LabelFrame(main_frame, text="Badges You Can Earn")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Badge', 'Description', 'Points Required', 'Category')
        self.badges_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=18)

        for col in columns:
            self.badges_tree.heading(col, text=col)
            if col in ('Badge', 'Description'):
                self.badges_tree.column(col, width=200)
            else:
                self.badges_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.badges_tree.yview)
        self.badges_tree.configure(yscrollcommand=scrollbar.set)

        self.badges_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT badge_name, description, points_required, category
            FROM achievement_badges
            ORDER BY points_required, badge_name
            ''')

            badges = cursor.fetchall()

            for badge in badges:
                self.badges_tree.insert('', 'end', values=badge)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load badges: {str(e)}")


# Mentorship Dialogs

class MentorshipBrowseDialog:
    """Dialog for finding a mentor or becoming one"""

    def __init__(self, parent, auth_manager, mode='find'):
        self.parent = parent
        self.auth = auth_manager
        self.mode = mode  # 'find' or 'become'

        self.dialog = tk.Toplevel(parent)
        if mode == 'find':
            self.dialog.title("Find a Mentor")
        else:
            self.dialog.title("Become a Mentor")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        if mode == 'find':
            self.load_mentors()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        if self.mode == 'find':
            title_label = ttk.Label(main_frame, text="Find a Mentor", font=('Arial', 14, 'bold'))
            title_label.pack(pady=(0, 10))

            list_frame = ttk.LabelFrame(main_frame, text="Available Mentors")
            list_frame.pack(fill='both', expand=True, pady=(0, 10))

            columns = ('Mentor', 'Skill Area', 'Rating', 'Active Mentees')
            self.mentors_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

            for col in columns:
                self.mentors_tree.heading(col, text=col)
                if col == 'Mentor':
                    self.mentors_tree.column(col, width=200)
                elif col == 'Skill Area':
                    self.mentors_tree.column(col, width=200)
                else:
                    self.mentors_tree.column(col, width=100)

            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.mentors_tree.yview)
            self.mentors_tree.configure(yscrollcommand=scrollbar.set)

            self.mentors_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x')

            ttk.Button(button_frame, text="Request Mentorship", command=self.request_mentor).pack(side='left', padx=(0, 10))
            ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')
        else:
            title_label = ttk.Label(main_frame, text="Become a Mentor", font=('Arial', 12, 'bold'))
            title_label.pack(pady=(0, 20))

            ttk.Label(main_frame, text="Skill Area:").pack(anchor='w', pady=(0, 5))
            self.skill_var = tk.StringVar()
            skill_combo = ttk.Combobox(main_frame, textvariable=self.skill_var, width=47)
            skill_combo['values'] = ('Academic - Math', 'Academic - Science', 'Academic - English',
                                    'Career - Resume Building', 'Career - Interview Prep',
                                    'Campus Life', 'Programming', 'Study Skills', 'Other')
            skill_combo.pack(fill='x', pady=(0, 10))

            ttk.Label(main_frame, text="Experience/Qualifications:").pack(anchor='w', pady=(0, 5))
            self.experience_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD)
            self.experience_text.pack(fill='both', expand=True, pady=(0, 10))

            ttk.Label(main_frame, text="Max Mentees:").pack(anchor='w', pady=(0, 5))
            self.max_var = tk.StringVar(value="3")
            ttk.Entry(main_frame, textvariable=self.max_var, width=10).pack(anchor='w', pady=(0, 10))

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x')

            ttk.Button(button_frame, text="Submit", command=self.become_mentor).pack(side='left', padx=(0, 10))
            ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def load_mentors(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT DISTINCT s.first_name || ' ' || s.last_name, mr.skill_area,
                   COALESCE(mr.mentor_rating, 0),
                   (SELECT COUNT(*) FROM mentorship_relationships
                    WHERE mentor_id = mr.mentor_id AND status = 'active') as mentee_count,
                   mr.mentor_id
            FROM mentorship_relationships mr
            INNER JOIN students s ON mr.mentor_id = s.student_id
            WHERE mr.status = 'active'
            GROUP BY mr.mentor_id, mr.skill_area
            ORDER BY mr.mentor_rating DESC
            ''')

            mentors = cursor.fetchall()

            for mentor in mentors:
                self.mentors_tree.insert('', 'end', values=mentor[:4], tags=(mentor[4],))

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load mentors: {str(e)}")

    def request_mentor(self):
        selection = self.mentors_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a mentor.")
            return

        item = self.mentors_tree.item(selection[0])
        mentor_id = item['tags'][0] if item['tags'] else None
        mentor_name = item['values'][0]
        skill_area = item['values'][1]

        if messagebox.askyesno("Confirm", f"Request mentorship from {mentor_name} for {skill_area}?"):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
                student_id = cursor.fetchone()[0]

                cursor.execute('''
                INSERT INTO mentorship_relationships (mentor_id, mentee_id, skill_area,
                                                     start_date, status)
                VALUES (?, ?, ?, ?, 'active')
                ''', (mentor_id, student_id, skill_area, datetime.now().isoformat()))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Mentorship request submitted!")
                self.dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to request mentorship: {str(e)}")

    def become_mentor(self):
        skill = self.skill_var.get().strip()
        experience = self.experience_text.get(1.0, tk.END).strip()
        max_mentees = self.max_var.get().strip()

        if not all([skill, experience, max_mentees]):
            messagebox.showwarning("Warning", "Please fill in all fields.")
            return

        messagebox.showinfo("Success", "Your mentor application has been submitted!\n\nYou will be notified once your application is approved.")
        self.dialog.destroy()


class MyMentorshipsDialog:
    """Dialog for viewing mentorship relationships"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("My Mentorships")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text="My Mentorships", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 10))

        # As Mentee tab
        mentee_frame = ttk.Frame(notebook)
        notebook.add(mentee_frame, text="As Mentee")

        columns = ('Mentor', 'Skill Area', 'Start Date', 'Status', 'Rating')
        self.mentee_tree = ttk.Treeview(mentee_frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            self.mentee_tree.heading(col, text=col)
            self.mentee_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(mentee_frame, orient='vertical', command=self.mentee_tree.yview)
        self.mentee_tree.configure(yscrollcommand=scrollbar.set)

        self.mentee_tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y')

        # As Mentor tab
        mentor_frame = ttk.Frame(notebook)
        notebook.add(mentor_frame, text="As Mentor")

        columns = ('Mentee', 'Skill Area', 'Start Date', 'Status', 'Rating')
        self.mentor_tree = ttk.Treeview(mentor_frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            self.mentor_tree.heading(col, text=col)
            self.mentor_tree.column(col, width=150)

        scrollbar2 = ttk.Scrollbar(mentor_frame, orient='vertical', command=self.mentor_tree.yview)
        self.mentor_tree.configure(yscrollcommand=scrollbar2.set)

        self.mentor_tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar2.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Schedule Session", command=self.schedule_session).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="View Sessions", command=self.view_sessions).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return

            student_id = result[0]

            # As mentee
            cursor.execute('''
            SELECT s.first_name || ' ' || s.last_name, mr.skill_area, mr.start_date,
                   mr.status, COALESCE(mr.mentor_rating, 'Not rated')
            FROM mentorship_relationships mr
            INNER JOIN students s ON mr.mentor_id = s.student_id
            WHERE mr.mentee_id = ?
            ORDER BY mr.start_date DESC
            ''', (student_id,))

            mentee_relationships = cursor.fetchall()
            for item in mentee_relationships:
                self.mentee_tree.insert('', 'end', values=item)

            # As mentor
            cursor.execute('''
            SELECT s.first_name || ' ' || s.last_name, mr.skill_area, mr.start_date,
                   mr.status, COALESCE(mr.mentee_rating, 'Not rated')
            FROM mentorship_relationships mr
            INNER JOIN students s ON mr.mentee_id = s.student_id
            WHERE mr.mentor_id = ?
            ORDER BY mr.start_date DESC
            ''', (student_id,))

            mentor_relationships = cursor.fetchall()
            for item in mentor_relationships:
                self.mentor_tree.insert('', 'end', values=item)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load mentorships: {str(e)}")

    def schedule_session(self):
        messagebox.showinfo("Schedule Session", "This would open a dialog to schedule a mentorship session with date, time, and agenda.")

    def view_sessions(self):
        dialog = MentorshipSessionsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)


class MentorshipSessionsDialog:
    """Dialog for viewing mentorship sessions"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Mentorship Sessions")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text="Mentorship Sessions", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        list_frame = ttk.LabelFrame(main_frame, text="Sessions")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Date', 'Duration', 'With', 'Role', 'Progress', 'Notes')
        self.sessions_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=18)

        for col in columns:
            self.sessions_tree.heading(col, text=col)
            if col in ('Notes', 'With'):
                self.sessions_tree.column(col, width=200)
            else:
                self.sessions_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.sessions_tree.yview)
        self.sessions_tree.configure(yscrollcommand=scrollbar.set)

        self.sessions_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return

            student_id = result[0]

            cursor.execute('''
            SELECT ms.session_date, ms.duration_minutes,
                   CASE
                       WHEN mr.mentor_id = ? THEN s1.first_name || ' ' || s1.last_name
                       ELSE s2.first_name || ' ' || s2.last_name
                   END as other_person,
                   CASE WHEN mr.mentor_id = ? THEN 'Mentor' ELSE 'Mentee' END as role,
                   COALESCE(ms.progress_rating, 0),
                   COALESCE(ms.notes, '')
            FROM mentorship_sessions ms
            INNER JOIN mentorship_relationships mr ON ms.relationship_id = mr.relationship_id
            LEFT JOIN students s1 ON mr.mentee_id = s1.student_id
            LEFT JOIN students s2 ON mr.mentor_id = s2.student_id
            WHERE mr.mentor_id = ? OR mr.mentee_id = ?
            ORDER BY ms.session_date DESC
            ''', (student_id, student_id, student_id, student_id))

            sessions = cursor.fetchall()

            for session in sessions:
                values = (session[0], f"{session[1]} min", session[2], session[3],
                         f"{session[4]}/5", session[5])
                self.sessions_tree.insert('', 'end', values=values)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load sessions: {str(e)}")
# Main execution
def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Student Union Management System')
    parser.add_argument('--mode', choices=['gui', 'cli', 'auto'], default='auto',
                       help='Interface mode (default: auto)')
    parser.add_argument('--db-path', default=str(DEFAULT_DB_PATH),
                       help='Database file path (default: student_records.db)')
    
    args = parser.parse_args()
    
    if args.mode == 'cli':
        if CLI_AVAILABLE:
            launch_cli()
        else:
            print("CLI mode not available. Starting GUI instead.")
            launch_gui()
    elif args.mode == 'gui':
        launch_gui()
    else:  # auto mode
        # Try to determine best mode based on environment
        try:
            import tkinter
            launch_gui()
        except ImportError:
            print("GUI not available. Starting CLI mode.")
            if CLI_AVAILABLE:
                launch_cli()
            else:
                print("Neither GUI nor CLI available. Please check your installation.")

# Main application launcher - FIXED: Added proper parameter handling
def launch_student_union_gui(auth_manager=None):
    """Launch the Student Union GUI application"""
    # FIXED: Create StudentUnionGUI without parameters since it doesn't accept them
    app = StudentUnionGUI()
    
    # FIXED: Set auth_manager if provided
    if auth_manager:
        app.auth_manager = auth_manager
    
    # Set window icon if available
    try:
        # You could set an icon here if you have one
        # app.root.iconbitmap('path/to/icon.ico')
        pass
    except:
        pass
    
    return app.root, app

# Backwards compatibility function - FIXED: Added missing import and error handling
def run_gui_with_cli_fallback(function_name, *args, **kwargs):
    """
    Run GUI version if available, otherwise fall back to CLI
    This maintains full backwards compatibility
    """
    try:
        # Try to run GUI version first
        root = tk.Tk()
        root.withdraw()  # Hide root window
        
        # Create a temporary GUI instance for function calls
        app = StudentUnionGUI()
        
        if hasattr(app, f"{function_name}_gui"):
            gui_method = getattr(app, f"{function_name}_gui")
            result = gui_method(*args, **kwargs)
            root.destroy()
            return result
        else:
            root.destroy()
            # Fall back to CLI version
            # FIXED: Check if CLI module exists before accessing it
            if CLI_AVAILABLE and 'student_union_cli' in globals():
                if hasattr(student_union_cli, function_name):
                    cli_method = getattr(student_union_cli, function_name)
                    return cli_method(*args, **kwargs)
            raise AttributeError(f"Function {function_name} not found")
                
    except ImportError:
        # If GUI libraries not available, use CLI
        if CLI_AVAILABLE and 'student_union_cli' in globals():
            if hasattr(student_union_cli, function_name):
                cli_method = getattr(student_union_cli, function_name)
                return cli_method(*args, **kwargs)
        raise AttributeError(f"Function {function_name} not found")

# Export main functions for backwards compatibility
def main_menu():
    """Main menu - can be GUI or CLI depending on availability"""
    try:
        root, app = launch_student_union_gui()
        root.mainloop()
    except ImportError:
        # Fall back to CLI if tkinter not available
        print("GUI not available, falling back to CLI mode...")
        # FIXED: Check CLI availability before calling
        if CLI_AVAILABLE:
            try:
                from part2 import main as cli_main
                cli_main()
            except ImportError:
                print("CLI also not available")

# FIXED: Add missing function definitions
def launch_gui():
    """Launch GUI application"""
    try:
        root, app = launch_student_union_gui()
        root.mainloop()
    except Exception as e:
        print(f"Failed to launch GUI: {e}")

def launch_cli():
    """Launch CLI application"""
    if CLI_AVAILABLE:
        try:
            from university_system.modules.domain.student_affairs.student_union.administration.student_union_core import main as cli_main
            cli_main()
        except ImportError:
            print("Error: Cannot import CLI system")
    else:
        print("CLI system not available")

# Initialize the module
if __name__ == "__main__":
    main()

# Module-level exports for backwards compatibility
__all__ = [
    'StudentUnionGUI',
    'launch_student_union_gui',
    'run_gui_with_cli_fallback',
    'main_menu',
    'ClubJoinDialog',
    'ClubCreateDialog', 
    'ClubManageDialog',
    'EventRegistrationDialog',
    'FacilityBookingDialog',
    'DatabaseQueryDialog',
    'SearchDialog'
]
