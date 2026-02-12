#!/usr/bin/env python3
"""
Academic Misconduct Panel - Case Management System
A professional GUI application for managing academic integrity cases.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
import json
from university_system.infrastructure.database.db import sqlite3
try:
    from university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    # Fallback if i18n module is not available
    def _t(key, default=None, **kwargs):
        return default if default else key.split('.')[-1].replace('_', ' ').title()

# Database and email imports
try:
    from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
except ImportError:
    from pathlib import Path
    DEFAULT_DB_PATH = Path(__file__).resolve().parents[6] / "data" / "db_files" / "student_records.db"

try:
    from university_system.infrastructure.email.email_service import queue_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    queue_email = None

# Authentication imports
try:
    from university_system.infrastructure.shared_context import get_auth, is_auth_initialized
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    is_auth_initialized = lambda: False

# Secure file upload imports
try:
    from university_system.infrastructure.security.file_upload import (
        validate_upload,
        secure_filename,
    )
    SECURE_UPLOAD_AVAILABLE = True
except ImportError:
    SECURE_UPLOAD_AVAILABLE = False
    validate_upload = None
    secure_filename = lambda x: x
    if not AUTH_AVAILABLE:
        get_auth = None

    # Define a dummy auth class for type checking
    class _DummyAuth:
        """Dummy auth class used when auth is not available"""
        pass

def init_misconduct_tables():
    """Create the academic misconduct tables if they don't exist."""
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    # Main cases table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academic_misconduct_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT UNIQUE NOT NULL,
            student_name TEXT NOT NULL,
            student_id TEXT NOT NULL,
            student_email TEXT,
            course TEXT NOT NULL,
            violation_type TEXT NOT NULL,
            status TEXT DEFAULT 'Under Review',
            date_filed TEXT NOT NULL,
            severity TEXT NOT NULL,
            notes TEXT,
            hearing_date TEXT,
            hearing_time TEXT,
            hearing_location TEXT,
            ruling TEXT,
            ruling_rationale TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Case history/timeline table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academic_misconduct_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_description TEXT NOT NULL,
            event_type TEXT DEFAULT 'info',
            created_by TEXT,
            FOREIGN KEY (case_id) REFERENCES academic_misconduct_cases(case_id)
        )
    ''')

    # Evidence table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS academic_misconduct_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT,
            file_size TEXT,
            uploaded_date TEXT NOT NULL,
            uploaded_by TEXT,
            FOREIGN KEY (case_id) REFERENCES academic_misconduct_cases(case_id)
        )
    ''')

    conn.commit()
    conn.close()

class AcademicMisconductPanel:
    """Main application class for the Academic Misconduct Panel."""
    
    def __init__(self, root, auth=None):
        self.root = root

        # Authentication setup
        self.auth = auth
        self.current_user = None

        # Try to get auth from shared context if not provided
        if self.auth is None and AUTH_AVAILABLE and get_auth:
            self.auth = get_auth()

        # Check if user is logged in
        if not self._check_authentication():
            return

        self.root.title(_t("misconduct.window.title", "Academic Misconduct Panel - Case Management System"))
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        # Color scheme - Matches standard program theme
        self.colors = {
            'primary': '#2c3e50',      # Dark blue-gray
            'secondary': '#3498db',     # Blue
            'success': '#27ae60',       # Green
            'warning': '#f39c12',       # Orange
            'danger': '#e74c3c',        # Red
            'light': '#ecf0f1',         # Light gray
            'dark': '#34495e',          # Dark gray
            'info': '#17a2b8',          # Cyan
            'white': '#ffffff',         # White
            'border': '#bdc3c7',        # Gray border
            'text_dark': '#2c3e50',     # Dark text
            'text_muted': '#7f8c8d',    # Muted text
            'bg_header': '#2c3e50',     # Header background
            'bg_sidebar': '#34495e',    # Sidebar background
            'accent': '#3498db',        # Accent color
        }

        self.root.configure(bg=self.colors['light'])

        # Initialize database tables
        init_misconduct_tables()

        # Load cases from database
        self.cases = []
        self.load_cases_from_db()

        self.selected_case = None
        self.setup_styles()
        self.create_widgets()

    def _check_authentication(self):
        """Check if user is authenticated. Returns True if logged in, False otherwise."""
        if not self.auth:
            messagebox.showerror(
                _t("misconduct.auth.required_title", "Authentication Required"),
                _t("misconduct.auth.required_message", "You must be logged in to access the Academic Misconduct Panel.\n\nPlease log in through the main GUI first.")
            )
            self.root.destroy()
            return False

        # Check if using dummy auth (fallback when no real auth is configured)
        # This ensures the panel only works when launched from main GUI with real login
        if _DummyAuth is not None and isinstance(self.auth, _DummyAuth):
            messagebox.showerror(
                _t("misconduct.auth.required_title", "Authentication Required"),
                _t("misconduct.auth.launch_from_gui", "You must be logged in to access the Academic Misconduct Panel.\n\nPlease launch this module from the main GUI after logging in.")
            )
            self.root.destroy()
            return False

        if not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            messagebox.showerror(
                _t("misconduct.auth.not_logged_in_title", "Not Logged In"),
                _t("misconduct.auth.not_logged_in_message", "You are not currently logged in.\n\nPlease log in through the main GUI to access this panel.")
            )
            self.root.destroy()
            return False

        # Store current user info
        self.current_user = self.auth.current_user

        # Check if user has appropriate role (admin, staff, or instructor)
        user_role = self.current_user.get('role', '').lower()
        allowed_roles = ['admin', 'staff', 'instructor', 'administrator']

        if user_role not in allowed_roles:
            messagebox.showerror(
                _t("misconduct.auth.access_denied_title", "Access Denied"),
                _t("misconduct.auth.access_denied_message", "You do not have permission to access the Academic Misconduct Panel.\n\nYour role: {role}\nRequired roles: Admin, Staff, or Instructor", role=user_role)
            )
            self.root.destroy()
            return False

        return True

    def load_cases_from_db(self):
        """Load all cases from the database."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT case_id, student_name, student_id, student_email, course,
                       violation_type, status, date_filed, severity, notes,
                       hearing_date, hearing_time, hearing_location, ruling, ruling_rationale
                FROM academic_misconduct_cases
                ORDER BY date_filed DESC
            ''')
            rows = cursor.fetchall()
            conn.close()

            self.cases = []
            for row in rows:
                self.cases.append({
                    'id': row['case_id'],
                    'student': row['student_name'],
                    'student_id': row['student_id'],
                    'student_email': row['student_email'] or '',
                    'course': row['course'],
                    'type': row['violation_type'],
                    'status': row['status'],
                    'date_filed': row['date_filed'],
                    'severity': row['severity'],
                    'notes': row['notes'] or '',
                    'hearing_date': row['hearing_date'] or '',
                    'hearing_time': row['hearing_time'] or '',
                    'hearing_location': row['hearing_location'] or '',
                    'ruling': row['ruling'] or '',
                    'ruling_rationale': row['ruling_rationale'] or ''
                })
        except Exception as e:
            print(f"Error loading cases from database: {e}")
            self.cases = []

    def refresh_dashboard(self):
        """Refresh the dashboard by reloading cases from database."""
        self.load_cases_from_db()
        self.populate_tree()
        # Also refresh tabs if a case is selected
        if self.selected_case:
            self.refresh_evidence_tab()
        # Always refresh analytics (global data)
        if hasattr(self, 'analytics_content'):
            self.refresh_analytics_tab()

    def save_case_to_db(self, case_data):
        """Save a new case to the database."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO academic_misconduct_cases
                (case_id, student_name, student_id, student_email, course, violation_type,
                 status, date_filed, severity, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                case_data['id'], case_data['student'], case_data['student_id'],
                case_data.get('student_email', ''), case_data['course'], case_data['type'],
                case_data['status'], case_data['date_filed'], case_data['severity'],
                case_data['notes']
            ))

            # Add to history
            cursor.execute('''
                INSERT INTO academic_misconduct_history (case_id, event_date, event_description, event_type)
                VALUES (?, ?, ?, ?)
            ''', (case_data['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  'Case filed', 'info'))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving case to database: {e}")
            return False

    def update_case_in_db(self, case_data):
        """Update an existing case in the database."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE academic_misconduct_cases
                SET student_name=?, student_id=?, student_email=?, course=?, violation_type=?,
                    status=?, severity=?, notes=?, hearing_date=?, hearing_time=?,
                    hearing_location=?, ruling=?, ruling_rationale=?, updated_at=CURRENT_TIMESTAMP
                WHERE case_id=?
            ''', (
                case_data['student'], case_data['student_id'], case_data.get('student_email', ''),
                case_data['course'], case_data['type'], case_data['status'], case_data['severity'],
                case_data['notes'], case_data.get('hearing_date', ''), case_data.get('hearing_time', ''),
                case_data.get('hearing_location', ''), case_data.get('ruling', ''),
                case_data.get('ruling_rationale', ''), case_data['id']
            ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating case in database: {e}")
            return False

    def delete_case_from_db(self, case_id):
        """Delete a case from the database."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('DELETE FROM academic_misconduct_history WHERE case_id=?', (case_id,))
            cursor.execute('DELETE FROM academic_misconduct_evidence WHERE case_id=?', (case_id,))
            cursor.execute('DELETE FROM academic_misconduct_cases WHERE case_id=?', (case_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error deleting case from database: {e}")
            return False

    def add_case_history(self, case_id, description, event_type='info'):
        """Add an entry to case history."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO academic_misconduct_history (case_id, event_date, event_description, event_type)
                VALUES (?, ?, ?, ?)
            ''', (case_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), description, event_type))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error adding case history: {e}")

    def get_case_history(self, case_id):
        """Get history for a specific case."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT event_date, event_description, event_type
                FROM academic_misconduct_history
                WHERE case_id=?
                ORDER BY event_date DESC
            ''', (case_id,))
            rows = cursor.fetchall()
            conn.close()
            return [(row['event_date'], row['event_description'], row['event_type']) for row in rows]
        except Exception as e:
            print(f"Error getting case history: {e}")
            return []

    def get_next_case_id(self):
        """Generate the next case ID."""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM academic_misconduct_cases')
            count = cursor.fetchone()[0]
            conn.close()
            year = datetime.now().year
            return f"AMC-{year}-{str(count + 1).zfill(3)}"
        except Exception:
            year = datetime.now().year
            return f"AMC-{year}-{str(len(self.cases) + 1).zfill(3)}"
        
    def setup_styles(self):
        """Configure ttk styles for the application."""
        style = ttk.Style()
        style.theme_use('clam')

        # Treeview styling
        style.configure(
            "Custom.Treeview",
            background=self.colors['white'],
            foreground=self.colors['text_dark'],
            fieldbackground=self.colors['white'],
            borderwidth=1,
            rowheight=35
        )
        style.configure(
            "Custom.Treeview.Heading",
            background=self.colors['primary'],
            foreground=self.colors['white'],
            borderwidth=0,
            font=('Segoe UI', 10, 'bold')
        )
        style.map(
            "Custom.Treeview",
            background=[('selected', self.colors['secondary'])],
            foreground=[('selected', self.colors['white'])]
        )

        # Notebook styling
        style.configure(
            "Custom.TNotebook",
            background=self.colors['light'],
            borderwidth=0
        )
        style.configure(
            "Custom.TNotebook.Tab",
            background=self.colors['light'],
            foreground=self.colors['text_dark'],
            padding=[20, 10],
            font=('Segoe UI', 10)
        )
        style.map(
            "Custom.TNotebook.Tab",
            background=[('selected', self.colors['white'])],
            foreground=[('selected', self.colors['primary'])],
            expand=[('selected', [1, 1, 1, 0])]
        )
        
    def create_widgets(self):
        """Create and layout all widgets."""
        # Create main sidebar on far left
        self.create_main_sidebar()

        # Create header
        self.create_header()

        # Create main content area
        self.main_content_frame = tk.Frame(self.root, bg=self.colors['light'])
        self.main_content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Create all view frames (hidden by default)
        self.views = {}
        self.current_view = None

        # Dashboard view
        self.create_dashboard_view()

        # Cases view (original case list + details)
        self.create_cases_view()

        # Analytics view
        self.create_analytics_view()

        # Show dashboard by default
        self.show_view('dashboard')

    def create_main_sidebar(self):
        """Create the main navigation sidebar on the far left."""
        self.sidebar = tk.Frame(self.root, bg=self.colors['dark'], width=220)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # Logo/Title section
        logo_frame = tk.Frame(self.sidebar, bg=self.colors['primary'], height=90)
        logo_frame.pack(fill=tk.X)
        logo_frame.pack_propagate(False)

        logo_label = tk.Label(
            logo_frame,
            text=_t("misconduct.panel_header"),
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors['white'],
            bg=self.colors['primary'],
            justify=tk.CENTER
        )
        logo_label.pack(expand=True)

        # Separator
        tk.Frame(self.sidebar, bg=self.colors['border'], height=1).pack(fill=tk.X, pady=5)

        # Scrollable navigation area
        nav_canvas = tk.Canvas(self.sidebar, bg=self.colors['dark'], highlightthickness=0)
        nav_scrollbar = ttk.Scrollbar(self.sidebar, orient=tk.VERTICAL, command=nav_canvas.yview)
        nav_scrollable_frame = tk.Frame(nav_canvas, bg=self.colors['dark'])

        nav_scrollable_frame.bind(
            "<Configure>",
            lambda e: nav_canvas.configure(scrollregion=nav_canvas.bbox("all"))
        )

        nav_canvas.create_window((0, 0), window=nav_scrollable_frame, anchor="nw", width=220)
        nav_canvas.configure(yscrollcommand=nav_scrollbar.set)

        # Navigation buttons
        self.main_nav_buttons = {}

        nav_items = [
            ('dashboard', '📊  Dashboard', 'View overview and statistics'),
            ('cases', '📋  Cases', 'Manage all cases'),
            ('create', '➕  New Case', 'Create a new case'),
            ('analytics', '📈  Analytics', 'View reports and trends'),
            ('sep1', None, None),  # Separator
            ('refresh', '🔄  Refresh', 'Reload all data'),
            ('export', '📥  Export', 'Export data to file'),
            ('sep2', None, None),  # Separator
            ('home', '🏠  Return Home', 'Back to main menu'),
        ]

        for key, text, tooltip in nav_items:
            if key.startswith('sep'):
                # Add separator
                tk.Frame(nav_scrollable_frame, bg=self.colors['border'], height=1).pack(fill=tk.X, pady=10, padx=15)
            else:
                btn = tk.Button(
                    nav_scrollable_frame,
                    text=text,
                    font=('Segoe UI', 10),
                    fg=self.colors['white'],
                    bg=self.colors['dark'],
                    activebackground=self.colors['secondary'],
                    activeforeground=self.colors['white'],
                    relief='flat',
                    anchor='w',
                    padx=20,
                    pady=15,
                    cursor='hand2',
                    command=lambda k=key: self.main_nav_action(k)
                )
                btn.pack(fill=tk.X, pady=2, padx=5)
                self.main_nav_buttons[key] = btn

                # Add hover effects
                btn.bind('<Enter>', lambda e, b=btn, k=key: self._on_main_nav_enter(b, k))
                btn.bind('<Leave>', lambda e, b=btn, k=key: self._on_main_nav_leave(b, k))

        # Pack canvas and scrollbar (before user info)
        nav_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        nav_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, before=nav_canvas)

        # User info at bottom
        user_frame = tk.Frame(self.sidebar, bg=self.colors['dark'])
        user_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20, padx=15)

        username = self.current_user.get('username', 'User') if self.current_user else 'User'
        role = self.current_user.get('role', 'Staff') if self.current_user else 'Staff'

        tk.Label(
            user_frame,
            text=f"👤 {username}",
            font=('Segoe UI', 9, 'bold'),
            fg=self.colors['white'],
            bg=self.colors['dark']
        ).pack(anchor='w')

        tk.Label(
            user_frame,
            text=role,
            font=('Segoe UI', 8),
            fg=self.colors['text_muted'],
            bg=self.colors['dark']
        ).pack(anchor='w')

    def main_nav_action(self, key):
        """Handle main navigation button clicks."""
        if key == 'dashboard':
            self.show_view('dashboard')
        elif key == 'cases':
            self.show_view('cases')
        elif key == 'create':
            self.new_case()
        elif key == 'analytics':
            self.show_view('analytics')
        elif key == 'refresh':
            self.refresh_all_data()
        elif key == 'export':
            self.export_analytics_csv()
        elif key == 'home':
            self.return_to_home()

    def _on_main_nav_enter(self, button, key):
        """Handle mouse enter on main nav button."""
        if self.current_view != key or key in ['create', 'refresh', 'export', 'home']:
            button.configure(bg=self.colors['primary'])

    def _on_main_nav_leave(self, button, key):
        """Handle mouse leave on main nav button."""
        if self.current_view != key or key in ['create', 'refresh', 'export', 'home']:
            button.configure(bg=self.colors['dark'])

    def show_view(self, view_key):
        """Switch to a specific main view."""
        # Hide all views
        for key, frame in self.views.items():
            frame.pack_forget()

        # Show requested view
        if view_key in self.views:
            self.views[view_key].pack(fill=tk.BOTH, expand=True)
            self.current_view = view_key

            # Update button styles
            for key, btn in self.main_nav_buttons.items():
                if key == view_key:
                    btn.configure(
                        bg=self.colors['secondary'],
                        font=('Segoe UI', 10, 'bold')
                    )
                elif key not in ['create', 'refresh', 'export', 'home']:
                    btn.configure(
                        bg=self.colors['dark'],
                        font=('Segoe UI', 10)
                    )

    def refresh_all_data(self):
        """Refresh all data and views."""
        self.load_cases_from_db()
        if hasattr(self, 'tree'):
            self.populate_tree()
        if hasattr(self, 'dashboard_stats_frame'):
            self.update_dashboard_stats()
        if hasattr(self, 'analytics_content'):
            self.refresh_analytics_tab()
        messagebox.showinfo(_t("misconduct.msg_titles.refreshed"), "All data has been refreshed.")

    def create_dashboard_view(self):
        """Create the dashboard view."""
        dashboard_frame = tk.Frame(self.main_content_frame, bg=self.colors['light'])
        self.views['dashboard'] = dashboard_frame

        # This will be populated with dashboard content
        self.create_dashboard_content(dashboard_frame)

    def create_cases_view(self):
        """Create the cases view with unified layout."""
        cases_frame = tk.Frame(self.main_content_frame, bg=self.colors['light'])
        self.views['cases'] = cases_frame

        # Main container
        container = tk.Frame(cases_frame, bg=self.colors['light'])
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title and actions bar
        title_bar = tk.Frame(container, bg=self.colors['light'])
        title_bar.pack(fill=tk.X, pady=(0, 15))

        tk.Label(
            title_bar,
            text=_t("misconduct.sections.case_management"),
            font=('Segoe UI', 18, 'bold'),
            fg=self.colors['primary'],
            bg=self.colors['light']
        ).pack(side=tk.LEFT)

        # Action buttons on right
        actions_frame = tk.Frame(title_bar, bg=self.colors['light'])
        actions_frame.pack(side=tk.RIGHT)

        self.create_button(actions_frame, "➕ New Case", self.new_case, 'primary').pack(side=tk.LEFT, padx=5)
        self.create_button(actions_frame, "🔄 Refresh", lambda: self.refresh_all_data(), 'secondary').pack(side=tk.LEFT, padx=5)

        # Search and filter bar
        search_filter_frame = tk.Frame(container, bg=self.colors['white'], relief='solid', bd=1)
        search_filter_frame.pack(fill=tk.X, pady=(0, 15))

        search_inner = tk.Frame(search_filter_frame, bg=self.colors['white'])
        search_inner.pack(fill=tk.X, padx=15, pady=12)

        # Search box
        search_container = tk.Frame(search_inner, bg=self.colors['white'])
        search_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 15))

        tk.Label(
            search_container,
            text=_t("misconduct.btn.search"),
            font=('Segoe UI', 12),
            fg=self.colors['text_muted'],
            bg=self.colors['white']
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_cases)

        search_entry = tk.Entry(
            search_container,
            textvariable=self.search_var,
            font=('Segoe UI', 10),
            bg=self.colors['light'],
            fg=self.colors['text_dark'],
            insertbackground=self.colors['text_dark'],
            relief='flat',
            bd=0
        )
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=5)
        search_placeholder = "Search by case ID, student name, or violation type..."
        search_entry.insert(0, search_placeholder)
        search_entry.bind('<FocusIn>', lambda e: search_entry.delete(0, tk.END) if search_entry.get() == search_placeholder else None)
        search_entry.bind('<FocusOut>', lambda e: search_entry.insert(0, search_placeholder) if not search_entry.get() else None)

        # Filter dropdown
        tk.Label(
            search_inner,
            text=_t("misconduct.labels.status"),
            font=('Segoe UI', 9),
            fg=self.colors['text_muted'],
            bg=self.colors['white']
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.filter_var = tk.StringVar(value="All")
        filter_dropdown = ttk.Combobox(
            search_inner,
            textvariable=self.filter_var,
            values=["All", "Under Review", "Pending Hearing", "Resolved"],
            state='readonly',
            width=15,
            font=('Segoe UI', 9)
        )
        filter_dropdown.pack(side=tk.LEFT, padx=(0, 10))
        filter_dropdown.bind('<<ComboboxSelected>>', self.filter_cases)

        # Severity filter
        tk.Label(
            search_inner,
            text=_t("misconduct.labels.severity"),
            font=('Segoe UI', 9),
            fg=self.colors['text_muted'],
            bg=self.colors['white']
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.severity_filter_var = tk.StringVar(value="All")
        severity_dropdown = ttk.Combobox(
            search_inner,
            textvariable=self.severity_filter_var,
            values=["All", "Low", "Medium", "High", "Critical"],
            state='readonly',
            width=12,
            font=('Segoe UI', 9)
        )
        severity_dropdown.pack(side=tk.LEFT)
        severity_dropdown.bind('<<ComboboxSelected>>', self.filter_cases)

        # Cases table
        table_frame = tk.Frame(container, bg=self.colors['white'], relief='solid', bd=1)
        table_frame.pack(fill=tk.X, pady=(0, 0))

        # Create treeview with more columns
        columns = ('case_id', 'student', 'violation', 'status', 'severity', 'date')
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show='headings',
            style="Custom.Treeview",
            selectmode='browse',
            height=10
        )

        self.tree.heading('case_id', text=_t('misconduct.columns.case_id'))
        self.tree.heading('student', text=_t('misconduct.columns.student_name'))
        self.tree.heading('violation', text=_t('misconduct.columns.violation_type'))
        self.tree.heading('status', text=_t('misconduct.columns.status'))
        self.tree.heading('severity', text=_t('misconduct.columns.severity'))
        self.tree.heading('date', text=_t('misconduct.columns.date_filed'))

        self.tree.column('case_id', width=120, minwidth=100)
        self.tree.column('student', width=180, minwidth=150)
        self.tree.column('violation', width=200, minwidth=150)
        self.tree.column('status', width=150, minwidth=120)
        self.tree.column('severity', width=100, minwidth=80)
        self.tree.column('date', width=120, minwidth=100)

        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Bind double-click to view details
        self.tree.bind('<Double-1>', lambda e: self.view_case_details())
        self.tree.bind('<<TreeviewSelect>>', self.on_case_select)

        # Action buttons below table
        action_bar = tk.Frame(container, bg=self.colors['light'])
        action_bar.pack(fill=tk.X, pady=(15, 0))

        tk.Label(
            action_bar,
            text=_t("misconduct.labels.double_click_case"),
            font=('Segoe UI', 9, 'italic'),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(side=tk.LEFT)

        action_buttons = tk.Frame(action_bar, bg=self.colors['light'])
        action_buttons.pack(side=tk.RIGHT)

        self.create_button(action_buttons, "👁 View Details", self.view_case_details, 'info').pack(side=tk.LEFT, padx=5)
        self.create_button(action_buttons, "✏ Update Case", self.update_case, 'warning').pack(side=tk.LEFT, padx=5)
        self.create_button(action_buttons, "🗑 Delete", self.delete_case, 'danger').pack(side=tk.LEFT, padx=5)
        self.create_button(action_buttons, "📧 Send Email", self.notify_student, 'secondary').pack(side=tk.LEFT, padx=5)
        self.create_button(action_buttons, "⚖ Schedule Hearing", self.schedule_hearing, 'secondary').pack(side=tk.LEFT, padx=5)

        # Populate the tree
        self.populate_tree()

    def create_analytics_view(self):
        """Create the analytics view."""
        analytics_frame = tk.Frame(self.main_content_frame, bg=self.colors['white'])
        self.views['analytics'] = analytics_frame

        # Create analytics content
        self.create_analytics_tab(analytics_frame)

    def create_dashboard_content(self, parent):
        """Create the dashboard content."""
        # Scroll container
        canvas = tk.Canvas(parent, bg=self.colors['light'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=self.colors['light'])

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=20)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Dashboard title
        title_label = tk.Label(
            scroll_frame,
            text=_t("misconduct.sections.dashboard_overview"),
            font=('Segoe UI', 20, 'bold'),
            fg=self.colors['primary'],
            bg=self.colors['light']
        )
        title_label.pack(anchor='w', pady=(0, 20))

        # Stats cards container
        self.dashboard_stats_frame = tk.Frame(scroll_frame, bg=self.colors['light'])
        self.dashboard_stats_frame.pack(fill=tk.X, pady=(0, 30))

        self.update_dashboard_stats()

        # Recent activity section
        recent_frame = tk.Frame(scroll_frame, bg=self.colors['white'], relief='solid', bd=1)
        recent_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        tk.Label(
            recent_frame,
            text=_t("misconduct.btn.recent_cases"),
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['primary'],
            bg=self.colors['white']
        ).pack(anchor='w', padx=20, pady=15)

        # Get recent 5 cases
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT case_id, student_name, violation_type, status, date_filed, severity
                FROM academic_misconduct_cases
                ORDER BY created_at DESC
                LIMIT 5
            """)
            recent_cases = cursor.fetchall()
            conn.close()

            if recent_cases:
                for case_id, student, violation, status, date_filed, severity in recent_cases:
                    case_card = tk.Frame(recent_frame, bg=self.colors['light'], relief='solid', bd=1)
                    case_card.pack(fill=tk.X, padx=20, pady=5)

                    info_frame = tk.Frame(case_card, bg=self.colors['light'])
                    info_frame.pack(fill=tk.X, padx=15, pady=10)

                    # Case ID and date
                    header_frame = tk.Frame(info_frame, bg=self.colors['light'])
                    header_frame.pack(fill=tk.X)

                    tk.Label(
                        header_frame,
                        text=case_id,
                        font=('Segoe UI', 10, 'bold'),
                        fg=self.colors['primary'],
                        bg=self.colors['light']
                    ).pack(side=tk.LEFT)

                    tk.Label(
                        header_frame,
                        text=date_filed,
                        font=('Segoe UI', 9),
                        fg=self.colors['text_muted'],
                        bg=self.colors['light']
                    ).pack(side=tk.RIGHT)

                    # Details
                    tk.Label(
                        info_frame,
                        text=f"{student} • {violation}",
                        font=('Segoe UI', 9),
                        fg=self.colors['text_dark'],
                        bg=self.colors['light']
                    ).pack(anchor='w', pady=(5, 0))

                    # Status and severity
                    tags_frame = tk.Frame(info_frame, bg=self.colors['light'])
                    tags_frame.pack(anchor='w', pady=(5, 0))

                    status_colors = {
                        'Under Review': self.colors['warning'],
                        'Pending Hearing': self.colors['info'],
                        'Resolved': self.colors['success']
                    }

                    severity_colors = {
                        'Low': self.colors['success'],
                        'Medium': self.colors['info'],
                        'High': self.colors['warning'],
                        'Critical': self.colors['danger']
                    }

                    # Status badge
                    status_badge = tk.Label(
                        tags_frame,
                        text=status,
                        font=('Segoe UI', 8, 'bold'),
                        fg=self.colors['white'],
                        bg=status_colors.get(status, self.colors['text_muted']),
                        padx=8,
                        pady=2
                    )
                    status_badge.pack(side=tk.LEFT, padx=(0, 5))

                    # Severity badge
                    severity_badge = tk.Label(
                        tags_frame,
                        text=severity,
                        font=('Segoe UI', 8, 'bold'),
                        fg=self.colors['white'],
                        bg=severity_colors.get(severity, self.colors['text_muted']),
                        padx=8,
                        pady=2
                    )
                    severity_badge.pack(side=tk.LEFT)
            else:
                tk.Label(
                    recent_frame,
                    text=_t("misconduct.labels.no_cases_found"),
                    font=('Segoe UI', 10),
                    fg=self.colors['text_muted'],
                    bg=self.colors['white']
                ).pack(padx=20, pady=20)

        except Exception as e:
            tk.Label(
                recent_frame,
                text=f"Error loading recent cases: {e}",
                font=('Segoe UI', 10),
                fg=self.colors['danger'],
                bg=self.colors['white']
            ).pack(padx=20, pady=20)

    def update_dashboard_stats(self):
        """Update dashboard statistics cards."""
        # Clear existing stats
        for widget in self.dashboard_stats_frame.winfo_children():
            widget.destroy()

        # Calculate stats
        total_cases = len(self.cases)
        active_cases = len([c for c in self.cases if c['status'] != 'Resolved'])
        resolved_cases = len([c for c in self.cases if c['status'] == 'Resolved'])
        pending_hearings = len([c for c in self.cases if c['status'] == 'Pending Hearing'])
        critical_cases = len([c for c in self.cases if c['severity'] == 'Critical'])

        stats = [
            ("Total Cases", total_cases, self.colors['info'], "📊"),
            ("Active", active_cases, self.colors['warning'], "🔄"),
            ("Resolved", resolved_cases, self.colors['success'], "✅"),
            ("Hearings", pending_hearings, self.colors['secondary'], "⚖️"),
            ("Critical", critical_cases, self.colors['danger'], "⚠️")
        ]

        for i, (label, value, color, icon) in enumerate(stats):
            stat_card = tk.Frame(self.dashboard_stats_frame, bg=color, relief='flat', bd=0, width=180, height=120)
            stat_card.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)
            stat_card.pack_propagate(False)

            tk.Label(
                stat_card,
                text=icon,
                font=('Segoe UI', 24),
                fg=self.colors['white'],
                bg=color
            ).pack(pady=(15, 0))

            tk.Label(
                stat_card,
                text=str(value),
                font=('Segoe UI', 28, 'bold'),
                fg=self.colors['white'],
                bg=color
            ).pack()

            tk.Label(
                stat_card,
                text=label,
                font=('Segoe UI', 10),
                fg=self.colors['white'],
                bg=color
            ).pack(pady=(0, 15))

    def create_header(self):
        """Create the application header."""
        header = tk.Frame(self.root, bg=self.colors['primary'], height=70)
        header.pack(fill=tk.X, padx=0, pady=0)
        header.pack_propagate(False)

        # Logo/Title section (centered)
        title_container = tk.Frame(header, bg=self.colors['primary'])
        title_container.pack(expand=True)

        title = tk.Label(
            title_container,
            text=_t("misconduct.header.title", "Academic Misconduct Panel"),
            font=('Segoe UI', 20, 'bold'),
            fg=self.colors['white'],
            bg=self.colors['primary']
        )
        title.pack()

        subtitle = tk.Label(
            title_container,
            text=_t("misconduct.header.subtitle", "Case Management System"),
            font=('Segoe UI', 10),
            fg=self.colors['light'],
            bg=self.colors['primary']
        )
        subtitle.pack()

        # Current date/time on right
        from datetime import datetime
        current_time = datetime.now().strftime("%B %d, %Y • %I:%M %p")

        time_label = tk.Label(
            header,
            text=current_time,
            font=('Segoe UI', 9),
            fg=self.colors['light'],
            bg=self.colors['primary']
        )
        time_label.pack(side=tk.RIGHT, padx=20)
            
    def create_case_list(self, parent):
        """Create the case list panel."""
        # Header
        header_frame = tk.Frame(parent, bg=self.colors['primary'], height=50)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        tk.Label(
            header_frame,
            text=_t("misconduct.case_list.title", "📋 Case Registry"),
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors['white'],
            bg=self.colors['primary']
        ).pack(side=tk.LEFT, padx=15, pady=10)

        # Search frame
        search_frame = tk.Frame(parent, bg=self.colors['white'], pady=12)
        search_frame.pack(fill=tk.X, padx=15)

        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_cases)

        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=('Segoe UI', 10),
            bg=self.colors['white'],
            fg=self.colors['text_dark'],
            insertbackground=self.colors['text_dark'],
            relief='solid',
            bd=1,
            highlightthickness=0
        )
        search_entry.pack(fill=tk.X, ipady=6)
        search_placeholder = _t("misconduct.case_list.search_placeholder", "🔍 Search cases...")
        search_entry.insert(0, search_placeholder)
        search_entry.bind('<FocusIn>', lambda e: search_entry.delete(0, tk.END) if search_entry.get() == search_placeholder else None)
        search_entry.bind('<FocusOut>', lambda e: search_entry.insert(0, search_placeholder) if not search_entry.get() else None)

        # Filter buttons
        filter_frame = tk.Frame(parent, bg=self.colors['white'])
        filter_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

        self.filter_var = tk.StringVar(value=_t("misconduct.filters.all", "All"))
        filters = [
            _t("misconduct.filters.all", "All"),
            _t("misconduct.filters.under_review", "Under Review"),
            _t("misconduct.filters.pending_hearing", "Pending Hearing"),
            _t("misconduct.filters.resolved", "Resolved")
        ]

        for f in filters:
            btn = tk.Radiobutton(
                filter_frame,
                text=f,
                variable=self.filter_var,
                value=f,
                font=('Segoe UI', 9),
                fg=self.colors['text_dark'],
                bg=self.colors['light'],
                selectcolor=self.colors['secondary'],
                activebackground=self.colors['light'],
                activeforeground=self.colors['white'],
                indicatoron=False,
                padx=10,
                pady=5,
                relief='flat',
                highlightthickness=0,
                command=self.filter_cases
            )
            btn.pack(side=tk.LEFT, padx=2)

        # Action buttons - CRUD operations (pack FIRST so they're visible)
        btn_frame = tk.Frame(parent, bg=self.colors['white'])
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=15, pady=12)

        self.create_button(btn_frame, _t("misconduct.buttons.create", "➕ Create"), self.new_case, 'primary').pack(side=tk.LEFT, padx=(0, 5))
        self.create_button(btn_frame, _t("misconduct.buttons.view", "👁 View"), self.view_case_details, 'info').pack(side=tk.LEFT, padx=(0, 5))
        self.create_button(btn_frame, _t("misconduct.buttons.update", "✏ Update"), self.update_case, 'warning').pack(side=tk.LEFT, padx=(0, 5))
        self.create_button(btn_frame, _t("misconduct.buttons.delete", "🗑 Delete"), self.delete_case, 'danger').pack(side=tk.LEFT, padx=(0, 5))
        self.create_button(btn_frame, _t("misconduct.buttons.refresh", "🔄 Refresh"), self.refresh_dashboard, 'success').pack(side=tk.LEFT)

        # Case list
        list_frame = tk.Frame(parent, bg=self.colors['white'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 5))

        # Treeview
        columns = ('id', 'student', 'type', 'status')
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show='headings',
            style="Custom.Treeview",
            selectmode='browse'
        )

        self.tree.heading('id', text=_t("misconduct.columns.case_id", "Case ID"))
        self.tree.heading('student', text=_t("misconduct.columns.student", "Student"))
        self.tree.heading('type', text=_t("misconduct.columns.type", "Type"))
        self.tree.heading('status', text=_t("misconduct.columns.status", "Status"))

        self.tree.column('id', width=100, minwidth=80)
        self.tree.column('student', width=120, minwidth=100)
        self.tree.column('type', width=130, minwidth=100)
        self.tree.column('status', width=100, minwidth=80)

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind('<<TreeviewSelect>>', self.on_case_select)

        # Populate tree
        self.populate_tree()
        
    def create_case_details(self, parent):
        """Create the case details panel."""
        # Header
        header_frame = tk.Frame(parent, bg=self.colors['primary'], height=50)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        self.detail_header = tk.Label(
            header_frame,
            text=_t("misconduct.details.title", "📄 Case Details"),
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors['white'],
            bg=self.colors['primary']
        )
        self.detail_header.pack(side=tk.LEFT, padx=15, pady=10)

        # Main container for sidebar + content
        main_container = tk.Frame(parent, bg=self.colors['light'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Sidebar navigation panel
        sidebar = tk.Frame(main_container, bg=self.colors['dark'], width=200)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        sidebar.pack_propagate(False)

        # Sidebar header
        sidebar_header = tk.Label(
            sidebar,
            text=_t("misconduct.labels.navigation"),
            font=('Segoe UI', 11, 'bold'),
            fg=self.colors['white'],
            bg=self.colors['dark'],
            pady=15
        )
        sidebar_header.pack(fill=tk.X)

        # Navigation buttons
        self.nav_buttons = {}
        self.current_section = None

        nav_items = [
            ('overview', '📋  Overview', self.show_overview_section),
            ('evidence', '📎  Evidence', self.show_evidence_section),
            ('decision', '⚖  Decision', self.show_decision_section),
            ('history', '📜  History', self.show_history_section),
            ('student_history', '👤  Student History', self.show_student_history_section),
            ('analytics', '📊  Analytics', self.show_analytics_section),
        ]

        for key, text, command in nav_items:
            btn = tk.Button(
                sidebar,
                text=text,
                font=('Segoe UI', 10),
                fg=self.colors['white'],
                bg=self.colors['dark'],
                activebackground=self.colors['secondary'],
                activeforeground=self.colors['white'],
                relief='flat',
                anchor='w',
                padx=20,
                pady=12,
                cursor='hand2',
                command=command
            )
            btn.pack(fill=tk.X, pady=2)
            self.nav_buttons[key] = btn

            # Add hover effects (only for inactive buttons)
            btn.bind('<Enter>', lambda e, b=btn, k=key: self._on_nav_button_enter(b, k))
            btn.bind('<Leave>', lambda e, b=btn, k=key: self._on_nav_button_leave(b, k))

        # Content area
        self.content_container = tk.Frame(main_container, bg=self.colors['white'], relief='solid', bd=1)
        self.content_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create all section frames (hidden by default)
        self.sections = {}

        # Overview section
        overview_frame = tk.Frame(self.content_container, bg=self.colors['white'])
        self.create_overview_tab(overview_frame)
        self.sections['overview'] = overview_frame

        # Evidence section
        evidence_frame = tk.Frame(self.content_container, bg=self.colors['white'])
        self.create_evidence_tab(evidence_frame)
        self.sections['evidence'] = evidence_frame

        # Decision section
        decision_frame = tk.Frame(self.content_container, bg=self.colors['white'])
        self.create_decision_tab(decision_frame)
        self.sections['decision'] = decision_frame

        # History section
        history_frame = tk.Frame(self.content_container, bg=self.colors['white'])
        self.create_history_tab(history_frame)
        self.sections['history'] = history_frame

        # Student History section
        student_history_frame = tk.Frame(self.content_container, bg=self.colors['white'])
        self.create_student_history_tab(student_history_frame)
        self.sections['student_history'] = student_history_frame

        # Analytics section
        analytics_frame = tk.Frame(self.content_container, bg=self.colors['white'])
        self.create_analytics_tab(analytics_frame)
        self.sections['analytics'] = analytics_frame

        # Show overview by default
        self.show_section('overview')

    def show_section(self, section_key):
        """Switch to a specific section."""
        # Hide all sections
        for key, frame in self.sections.items():
            frame.pack_forget()

        # Show the requested section
        if section_key in self.sections:
            self.sections[section_key].pack(fill=tk.BOTH, expand=True)
            self.current_section = section_key

            # Update button styles
            for key, btn in self.nav_buttons.items():
                if key == section_key:
                    # Active button style
                    btn.configure(
                        bg=self.colors['secondary'],
                        fg=self.colors['white'],
                        font=('Segoe UI', 10, 'bold')
                    )
                else:
                    # Inactive button style
                    btn.configure(
                        bg=self.colors['dark'],
                        fg=self.colors['white'],
                        font=('Segoe UI', 10)
                    )

    def show_overview_section(self):
        """Show the overview section."""
        self.show_section('overview')

    def show_evidence_section(self):
        """Show the evidence section."""
        self.show_section('evidence')

    def show_decision_section(self):
        """Show the decision section."""
        self.show_section('decision')

    def show_history_section(self):
        """Show the history section."""
        self.show_section('history')

    def show_student_history_section(self):
        """Show the student history section."""
        self.show_section('student_history')

    def show_analytics_section(self):
        """Show the analytics section."""
        self.show_section('analytics')

    def _on_nav_button_enter(self, button, key):
        """Handle mouse enter on navigation button."""
        # Only apply hover effect if not the active button
        if self.current_section != key:
            button.configure(bg=self.colors['primary'])

    def _on_nav_button_leave(self, button, key):
        """Handle mouse leave on navigation button."""
        # Only remove hover effect if not the active button
        if self.current_section != key:
            button.configure(bg=self.colors['dark'])

    def create_overview_tab(self, parent):
        """Create the overview tab content."""
        # Content frame with scrolling
        canvas = tk.Canvas(parent, bg=self.colors['white'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        self.overview_content = tk.Frame(canvas, bg=self.colors['white'])
        
        self.overview_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.overview_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Placeholder content
        self.overview_fields = {}
        self.create_overview_fields()
        
    def create_overview_fields(self):
        """Create the overview fields."""
        # Clear existing widgets
        for widget in self.overview_content.winfo_children():
            widget.destroy()
            
        padding_frame = tk.Frame(self.overview_content, bg=self.colors['light'])
        padding_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        if not self.selected_case:
            placeholder = tk.Label(
                padding_frame,
                text=_t("misconduct.overview.select_case", "Select a case to view details"),
                font=('Segoe UI', 12),
                fg=self.colors['text_muted'],
                bg=self.colors['light']
            )
            placeholder.pack(expand=True)
            return
            
        case = self.selected_case
        
        # Case info grid
        fields = [
            (_t("misconduct.fields.case_id", "Case ID"), case['id']),
            (_t("misconduct.fields.student_name", "Student Name"), case['student']),
            (_t("misconduct.fields.student_id", "Student ID"), case['student_id']),
            (_t("misconduct.fields.course", "Course"), case['course']),
            (_t("misconduct.fields.violation_type", "Violation Type"), case['type']),
            (_t("misconduct.fields.date_filed", "Date Filed"), case['date_filed']),
            (_t("misconduct.fields.severity", "Severity"), case['severity']),
            (_t("misconduct.fields.status", "Status"), case['status']),
        ]
        
        for i, (label, value) in enumerate(fields):
            row_frame = tk.Frame(padding_frame, bg=self.colors['light'])
            row_frame.pack(fill=tk.X, pady=8)
            
            tk.Label(
                row_frame,
                text=label + ":",
                font=('Segoe UI', 10),
                fg=self.colors['text_muted'],
                bg=self.colors['light'],
                width=15,
                anchor='w'
            ).pack(side=tk.LEFT)
            
            # Special styling for status and severity
            status_label = _t("misconduct.fields.status", "Status")
            severity_label = _t("misconduct.fields.severity", "Severity")
            if label == status_label:
                color = {
                    'Under Review': self.colors['warning'],
                    'Pending Hearing': self.colors['info'],
                    'Resolved': self.colors['success']
                }.get(value, self.colors['text_dark'])
            elif label == severity_label:
                color = {
                    'Minor': self.colors['success'],
                    'Major': self.colors['warning'],
                    'Critical': self.colors['danger']
                }.get(value, self.colors['text_dark'])
            else:
                color = self.colors['text_dark']
                
            value_label = tk.Label(
                row_frame,
                text=value,
                font=('Segoe UI', 10, 'bold') if label in [status_label, severity_label] else ('Segoe UI', 10),
                fg=color,
                bg=self.colors['light'],
                anchor='w'
            )
            value_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
        # Notes section
        notes_frame = tk.Frame(padding_frame, bg=self.colors['light'])
        notes_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

        tk.Label(
            notes_frame,
            text=_t("misconduct.fields.case_notes", "Case Notes:"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 8))
        
        notes_text = scrolledtext.ScrolledText(
            notes_frame,
            font=('Segoe UI', 10),
            bg=self.colors['white'],
            fg=self.colors['text_dark'],
            relief='flat',
            height=6,
            wrap=tk.WORD,
            insertbackground=self.colors['text_dark']
        )
        notes_text.pack(fill=tk.BOTH, expand=True)
        notes_text.insert(tk.END, case['notes'])
        
        # Action buttons
        btn_frame = tk.Frame(padding_frame, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        self.create_button(btn_frame, _t("misconduct.buttons.edit_case", "Edit Case"), self.edit_case, 'primary').pack(side=tk.LEFT, padx=(0, 10))
        self.create_button(btn_frame, _t("misconduct.buttons.notify_student", "Notify Student"), self.notify_student, 'secondary').pack(side=tk.LEFT, padx=(0, 10))
        self.create_button(btn_frame, _t("misconduct.buttons.schedule_hearing", "Schedule Hearing"), self.schedule_hearing, 'secondary').pack(side=tk.LEFT)
        
    def create_evidence_tab(self, parent):
        """Create the evidence tab content."""
        # Store reference to evidence frame for refresh
        self.evidence_parent = parent
        self.evidence_frame = tk.Frame(parent, bg=self.colors['light'])
        self.evidence_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.refresh_evidence_tab()

    def refresh_evidence_tab(self):
        """Refresh the evidence tab with current case data."""
        # Clear existing widgets
        for widget in self.evidence_frame.winfo_children():
            widget.destroy()

        tk.Label(
            self.evidence_frame,
            text=_t("misconduct.evidence.title", "Evidence & Documentation"),
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 15))

        # Load evidence from database for selected case
        evidence_items = []
        if self.selected_case:
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT file_name, file_size, uploaded_date
                    FROM academic_misconduct_evidence
                    WHERE case_id = ?
                    ORDER BY uploaded_date DESC
                ''', (self.selected_case['id'],))
                rows = cursor.fetchall()
                conn.close()

                for row in rows:
                    # Determine icon based on file extension
                    name = row['file_name']
                    ext = name.split('.')[-1].lower() if '.' in name else ''
                    if ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp']:
                        icon = "🖼️"
                    elif ext == 'pdf':
                        icon = "📄"
                    elif ext in ['doc', 'docx']:
                        icon = "📝"
                    else:
                        icon = "📎"
                    evidence_items.append((f"{icon} {name}", f"Uploaded {row['uploaded_date']}", row['file_size']))
            except Exception as e:
                print(f"Error loading evidence: {e}")

        if evidence_items:
            for name, date, size in evidence_items:
                item_frame = tk.Frame(self.evidence_frame, bg=self.colors['white'])
                item_frame.pack(fill=tk.X, pady=5)

                tk.Label(
                    item_frame,
                    text=name,
                    font=('Segoe UI', 10),
                    fg=self.colors['text_dark'],
                    bg=self.colors['white']
                ).pack(side=tk.LEFT, padx=15, pady=12)

                tk.Label(
                    item_frame,
                    text=size,
                    font=('Segoe UI', 9),
                    fg=self.colors['text_muted'],
                    bg=self.colors['white']
                ).pack(side=tk.RIGHT, padx=15)

                tk.Label(
                    item_frame,
                    text=date,
                    font=('Segoe UI', 9),
                    fg=self.colors['text_muted'],
                    bg=self.colors['white']
                ).pack(side=tk.RIGHT, padx=15)
        else:
            # Show message when no evidence
            no_evidence_frame = tk.Frame(self.evidence_frame, bg=self.colors['white'])
            no_evidence_frame.pack(fill=tk.X, pady=20)
            evidence_msg = _t("misconduct.evidence.no_evidence", "No evidence uploaded yet") if self.selected_case else _t("misconduct.evidence.select_case", "Select a case to view evidence")
            tk.Label(
                no_evidence_frame,
                text=evidence_msg,
                font=('Segoe UI', 11),
                fg=self.colors['text_muted'],
                bg=self.colors['white']
            ).pack(padx=20, pady=20)

        # Upload button
        btn_frame = tk.Frame(self.evidence_frame, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        self.create_button(btn_frame, _t("misconduct.buttons.upload_evidence", "Upload Evidence"), self.upload_evidence, 'primary').pack(side=tk.LEFT, padx=(0, 10))
        self.create_button(btn_frame, _t("misconduct.buttons.refresh", "Refresh"), self.refresh_evidence_tab, 'secondary').pack(side=tk.LEFT)
        
    def create_decision_tab(self, parent):
        """Create the decision tab content with scrollbar."""
        # Create canvas with scrollbar for the entire tab
        canvas_frame = tk.Frame(parent, bg=self.colors['light'])
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_frame, bg=self.colors['light'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)

        padding_frame = tk.Frame(canvas, bg=self.colors['light'])

        # Configure canvas scrolling
        def configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        padding_frame.bind("<Configure>", configure_scroll)

        canvas_window = canvas.create_window((0, 0), window=padding_frame, anchor="nw")

        def configure_canvas_width(event):
            canvas.itemconfig(canvas_window, width=event.width - 20)

        canvas.bind("<Configure>", configure_canvas_width)
        canvas.configure(yscrollcommand=scrollbar.set)

        # Enable mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(
            padding_frame,
            text=_t("misconduct.decision.title", "Panel Decision"),
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 15))

        # Decision options
        tk.Label(
            padding_frame,
            text=_t("misconduct.decision.ruling_label", "Ruling:"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 5))

        self.ruling_var = tk.StringVar(value="")
        rulings = [
            (_t("misconduct.rulings.not_responsible", "Not Responsible"), "success"),
            (_t("misconduct.rulings.warning", "Responsible - Warning"), "warning"),
            (_t("misconduct.rulings.grade_penalty", "Responsible - Grade Penalty"), "warning"),
            (_t("misconduct.rulings.course_failure", "Responsible - Course Failure"), "danger"),
            (_t("misconduct.rulings.suspension", "Responsible - Suspension"), "danger"),
            (_t("misconduct.rulings.expulsion", "Responsible - Expulsion"), "danger"),
            (_t("misconduct.rulings.academic_probation", "Responsible - Academic Probation"), "warning"),
            (_t("misconduct.rulings.resubmission", "Responsible - Resubmission Required"), "warning"),
            (_t("misconduct.rulings.dismissed", "Case Dismissed - Insufficient Evidence"), "success"),
            (_t("misconduct.rulings.deferred", "Deferred - Pending Investigation"), "warning"),
        ]

        for ruling, severity in rulings:
            color = self.colors[severity] if severity else self.colors['text_dark']
            rb = tk.Radiobutton(
                padding_frame,
                text=ruling,
                variable=self.ruling_var,
                value=ruling,
                font=('Segoe UI', 10),
                fg=color,
                bg=self.colors['light'],
                selectcolor=self.colors['white'],
                activebackground=self.colors['light'],
                activeforeground=color
            )
            rb.pack(anchor='w', pady=3)

        # Rationale
        tk.Label(
            padding_frame,
            text=_t("misconduct.decision.rationale_label", "Decision Rationale:"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(20, 5))

        self.rationale_text = scrolledtext.ScrolledText(
            padding_frame,
            font=('Segoe UI', 10),
            bg=self.colors['white'],
            fg=self.colors['text_dark'],
            relief='flat',
            height=6,
            wrap=tk.WORD,
            insertbackground=self.colors['text_dark']
        )
        self.rationale_text.pack(fill=tk.X, padx=(0, 10))

        # Submit decision
        btn_frame = tk.Frame(padding_frame, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(20, 10))

        self.create_button(btn_frame, "✓ Submit Decision", self.submit_decision, 'primary').pack(side=tk.LEFT)
        
    def create_history_tab(self, parent):
        """Create the history tab content."""
        # Store reference to history frame for refresh
        self.history_frame = tk.Frame(parent, bg=self.colors['light'])
        self.history_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.refresh_history_tab()

    def refresh_history_tab(self):
        """Refresh the history tab with current case data."""
        # Clear existing widgets
        for widget in self.history_frame.winfo_children():
            widget.destroy()

        tk.Label(
            self.history_frame,
            text=_t("misconduct.sections.case_history_timeline"),
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 15))

        if not self.selected_case:
            tk.Label(
                self.history_frame,
                text=_t("misconduct.labels.select_case_history"),
                font=('Segoe UI', 11),
                fg=self.colors['text_muted'],
                bg=self.colors['light']
            ).pack(pady=20)
            return

        # Get history from database
        events = self.get_case_history(self.selected_case['id'])

        if not events:
            tk.Label(
                self.history_frame,
                text=_t("misconduct.labels.no_history_found"),
                font=('Segoe UI', 11),
                fg=self.colors['text_muted'],
                bg=self.colors['light']
            ).pack(pady=20)
            return

        for date, description, event_type in events:
            event_frame = tk.Frame(self.history_frame, bg=self.colors['light'])
            event_frame.pack(fill=tk.X, pady=8)

            indicator = tk.Frame(event_frame, bg=self.colors.get(event_type, self.colors['info']), width=4)
            indicator.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))

            content_frame = tk.Frame(event_frame, bg=self.colors['light'])
            content_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

            tk.Label(
                content_frame,
                text=date,
                font=('Segoe UI', 9),
                fg=self.colors['text_muted'],
                bg=self.colors['light']
            ).pack(anchor='w')

            tk.Label(
                content_frame,
                text=description,
                font=('Segoe UI', 10),
                fg=self.colors['text_dark'],
                bg=self.colors['light']
            ).pack(anchor='w')
            
    def create_button(self, parent, text, command, style='primary'):
        """Create a styled button."""
        color_map = {
            'primary': (self.colors['secondary'], self.colors['white'], self.colors['primary']),
            'success': (self.colors['success'], self.colors['white'], '#1e8449'),
            'warning': (self.colors['warning'], self.colors['white'], '#d68910'),
            'danger': (self.colors['danger'], self.colors['white'], '#c0392b'),
            'info': (self.colors['info'], self.colors['white'], '#138496'),
            'secondary': (self.colors['light'], self.colors['text_dark'], self.colors['border'])
        }

        bg, fg, hover_bg = color_map.get(style, color_map['secondary'])

        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=('Segoe UI', 9, 'bold'),
            bg=bg,
            fg=fg,
            activebackground=hover_bg,
            activeforeground=fg,
            relief='flat',
            padx=12,
            pady=6,
            cursor='hand2',
            bd=0
        )

        btn.bind('<Enter>', lambda e: btn.configure(bg=hover_bg))
        btn.bind('<Leave>', lambda e: btn.configure(bg=bg))

        return btn
        
    def populate_tree(self):
        """Populate the treeview with case data."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        filter_status = self.filter_var.get()
        filter_severity = self.severity_filter_var.get() if hasattr(self, 'severity_filter_var') else "All"
        search_text = self.search_var.get().lower()

        # Handle placeholders
        if "search" in search_text.lower():
            search_text = ""

        for case in self.cases:
            # Apply status filter
            if filter_status != "All" and case['status'] != filter_status:
                continue

            # Apply severity filter
            if filter_severity != "All" and case['severity'] != filter_severity:
                continue

            # Apply search filter (search in multiple fields)
            if search_text:
                searchable_text = (
                    case['id'].lower() + " " +
                    case['student'].lower() + " " +
                    case['type'].lower()
                )
                if search_text not in searchable_text:
                    continue

            self.tree.insert('', tk.END, values=(
                case['id'],
                case['student'],
                case['type'],
                case['status'],
                case['severity'],
                case['date_filed']
            ))
            
    def filter_cases(self, *args):
        """Filter cases based on search and filter criteria."""
        if not hasattr(self, 'tree') or self.tree is None:
            return
        self.populate_tree()
        
    def on_case_select(self, event):
        """Handle case selection."""
        selected = self.tree.selection()
        if selected:
            item = self.tree.item(selected[0])
            case_id = item['values'][0]

            for case in self.cases:
                if case['id'] == case_id:
                    self.selected_case = case
                    # Note: Case details are shown when user clicks "View Details" button
                    # We just store the selected case here for later use
                    break
                    
    def new_case(self):
        """Create a new case."""
        self.open_case_dialog()
        
    def lookup_student(self, student_id_entry, entries):
        """Look up student by ID and auto-fill details including course."""
        student_id = student_id_entry.get().strip()
        if not student_id:
            messagebox.showwarning(_t("misconduct.msg_titles.missing_id"), "Please enter a Student ID to look up.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            student_name = None
            student_email = None
            student_course = None

            # Try to find student in students table
            cursor.execute('''
                SELECT first_name, last_name, email_address, course FROM students WHERE student_id = ?
            ''', (student_id,))
            student = cursor.fetchone()

            if student:
                # Combine first and last name
                first = student['first_name'] or ''
                last = student['last_name'] or ''
                student_name = f"{first} {last}".strip()
                student_email = student['email_address'] or ''
                student_course = student['course'] or ''
            else:
                # Try users table as fallback
                cursor.execute('''
                    SELECT username, email FROM users WHERE id = ? OR username = ?
                ''', (student_id, student_id))
                user = cursor.fetchone()
                if user:
                    student_name = user['username'] or ''
                    student_email = user['email'] or ''

            # Get enrolled modules for the student (from student_modules table)
            modules_list = []
            try:
                cursor.execute('''
                    SELECT DISTINCT module_code FROM student_modules WHERE student_id = ?
                ''', (student_id,))
                modules = cursor.fetchall()
                modules_list = [m['module_code'] for m in modules]
            except Exception:
                pass

            conn.close()

            if student_name:
                # Clear and fill entries
                if 'student' in entries:
                    entries['student'].delete(0, tk.END)
                    entries['student'].insert(0, student_name)
                if 'student_email' in entries:
                    entries['student_email'].delete(0, tk.END)
                    entries['student_email'].insert(0, student_email)
                if 'course' in entries and student_course:
                    entries['course'].delete(0, tk.END)
                    # Include modules if available
                    course_info = student_course
                    if modules_list:
                        course_info += f" (Modules: {', '.join(modules_list[:5])})"
                    entries['course'].insert(0, course_info)

                info_msg = f"Student '{student_name}' found and details filled."
                if student_course:
                    info_msg += f"\nCourse: {student_course}"
                if modules_list:
                    info_msg += f"\nEnrolled in {len(modules_list)} module(s)"
                messagebox.showinfo(_t("misconduct.msg_titles.found"), info_msg)
            else:
                messagebox.showinfo(_t("misconduct.msg_titles.not_found"), f"No student found with ID '{student_id}'.")

        except Exception as e:
            messagebox.showerror(_t("misconduct.msg_titles.error"), f"Failed to look up student: {str(e)}")

    def get_student_assignments(self, student_id):
        """Get assignments for a student from the database."""
        assignments = []
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # If no student_id provided, get all active assignments
            if not student_id:
                cursor.execute('''
                    SELECT id, title, module_code, due_date
                    FROM assignments
                    WHERE is_active = 1
                    ORDER BY due_date DESC
                    LIMIT 50
                ''')
                assignments = [dict(row) for row in cursor.fetchall()]
            else:
                # Get assignments the student has submitted to
                cursor.execute('''
                    SELECT DISTINCT a.id, a.title, a.module_code, a.due_date,
                           s.file_name as submitted_file
                    FROM assignments a
                    INNER JOIN assignment_submissions s ON a.id = s.assignment_id
                    WHERE s.student_id = ?
                    ORDER BY a.due_date DESC
                    LIMIT 50
                ''', (student_id,))
                assignments = [dict(row) for row in cursor.fetchall()]

                # If no submissions, get assignments from enrolled modules (student_modules table)
                if not assignments:
                    cursor.execute('''
                        SELECT DISTINCT a.id, a.title, a.module_code, a.due_date
                        FROM assignments a
                        INNER JOIN student_modules sm ON a.module_code = sm.module_code
                        WHERE sm.student_id = ?
                        ORDER BY a.due_date DESC
                        LIMIT 50
                    ''', (student_id,))
                    assignments = [dict(row) for row in cursor.fetchall()]

                # If still no assignments, show all active assignments as fallback
                if not assignments:
                    cursor.execute('''
                        SELECT id, title, module_code, due_date
                        FROM assignments
                        WHERE is_active = 1
                        ORDER BY due_date DESC
                        LIMIT 50
                    ''')
                    assignments = [dict(row) for row in cursor.fetchall()]

            conn.close()
        except Exception as e:
            print(f"Error getting assignments: {e}")

        return assignments

    def get_valid_courses(self):
        """Get all valid course/program codes from the database."""
        courses = []
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get from courses table first (main courses/modules)
            cursor.execute('''
                SELECT code, name FROM courses
                WHERE code IS NOT NULL AND status = 'active'
                ORDER BY code
            ''')
            for row in cursor.fetchall():
                courses.append({
                    'code': row['code'],
                    'name': row['name'],
                    'display': f"{row['code']} - {row['name']}"
                })

            existing_codes = {c['code'] for c in courses}

            # Get from degree_programs table
            cursor.execute('''
                SELECT program_code, program_name FROM degree_programs
                WHERE program_code IS NOT NULL AND is_active = 1
                ORDER BY program_code
            ''')
            for row in cursor.fetchall():
                if row['program_code'] not in existing_codes:
                    courses.append({
                        'code': row['program_code'],
                        'name': row['program_name'],
                        'display': f"{row['program_code']} - {row['program_name']}"
                    })
                    existing_codes.add(row['program_code'])

            # Also get distinct courses from students table (in case not in courses or degree_programs)
            cursor.execute('''
                SELECT DISTINCT course FROM students
                WHERE course IS NOT NULL AND course != ''
                ORDER BY course
            ''')
            for row in cursor.fetchall():
                if row['course'] not in existing_codes:
                    courses.append({
                        'code': row['course'],
                        'name': row['course'],
                        'display': row['course']
                    })

            conn.close()
        except Exception as e:
            print(f"Error getting courses: {e}")

        return courses

    def validate_course(self, course_code):
        """Validate if a course/program code exists in the database."""
        if not course_code:
            return False, "Course code is required"

        # Extract just the code if it's in "CODE - Name" or "CODE (Modules: ...)" format
        code = course_code.split(' - ')[0].strip()  # Handle "CODE - Name"
        code = code.split('(')[0].strip()  # Handle "CODE (Modules: ...)"
        code = code.upper()

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check in courses table first (main courses/modules table)
            cursor.execute('''
                SELECT code, name FROM courses
                WHERE UPPER(code) = ? OR UPPER(course_code) = ?
            ''', (code, code))
            result = cursor.fetchone()

            if result:
                conn.close()
                return True, f"Valid course: {result[0]} - {result[1]}"

            # Check in degree_programs table
            cursor.execute('''
                SELECT program_code, program_name FROM degree_programs
                WHERE UPPER(program_code) = ?
            ''', (code,))
            result = cursor.fetchone()

            if result:
                conn.close()
                return True, f"Valid program: {result[0]} - {result[1]}"

            # Also check if it's a course used in students table
            cursor.execute('''
                SELECT DISTINCT course FROM students
                WHERE UPPER(course) = ?
            ''', (code,))
            result = cursor.fetchone()
            conn.close()

            if result:
                return True, f"Valid course: {result[0]}"
            else:
                return False, f"Course '{code}' not found in the system"

        except Exception as e:
            return False, f"Error validating course: {str(e)}"

    def get_assignment_files(self, assignment_id, student_id):
        """Get files submitted for an assignment by a student."""
        files = []
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT file_name, file_path, submitted_at
                FROM assignment_submissions
                WHERE assignment_id = ? AND student_id = ?
            ''', (assignment_id, student_id))
            files = [dict(row) for row in cursor.fetchall()]

            conn.close()
        except Exception as e:
            print(f"Error getting assignment files: {e}")

        return files

    def open_case_dialog(self, edit_mode=False):
        """Open dialog for creating/editing a case."""
        dialog = tk.Toplevel(self.root)
        dialog.title("New Case" if not edit_mode else "Edit Case")
        dialog.geometry("700x800")
        dialog.configure(bg=self.colors['light'])
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (350)
        y = (dialog.winfo_screenheight() // 2) - (400)
        dialog.geometry(f"+{x}+{y}")

        # Main container with scrollbar
        main_frame = tk.Frame(dialog, bg=self.colors['light'])
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas and scrollbar
        canvas = tk.Canvas(main_frame, bg=self.colors['light'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors['light'])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        dialog.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Content inside scrollable frame
        content = tk.Frame(scrollable_frame, bg=self.colors['light'])
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        tk.Label(
            content,
            text=_t("misconduct.btn.new_case") if not edit_mode else "Edit Case",
            font=('Segoe UI', 16, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 20))

        entries = {}

        # Student ID with lookup button
        tk.Label(
            content,
            text=_t("misconduct.labels.student_id"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        id_frame = tk.Frame(content, bg=self.colors['light'])
        id_frame.pack(fill=tk.X)

        student_id_entry = tk.Entry(
            id_frame,
            font=('Segoe UI', 11),
            bg=self.colors['light'],
            fg=self.colors['text_dark'],
            insertbackground=self.colors['text_dark'],
            relief='flat'
        )
        student_id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        entries['student_id'] = student_id_entry

        # Will be set later when assignment dropdown is created
        assignment_loader = {'func': None}

        def lookup_with_assignments():
            self.lookup_student(student_id_entry, entries)
            # Auto-load assignments after lookup
            if assignment_loader['func']:
                assignment_loader['func']()

        lookup_btn = tk.Button(
            id_frame,
            text=_t("misconduct.labels.lookup"),
            font=('Segoe UI', 9),
            bg=self.colors['accent'],
            fg=self.colors['white'],
            relief='flat',
            padx=10,
            cursor='hand2',
            command=lookup_with_assignments
        )
        lookup_btn.pack(side=tk.LEFT, padx=(10, 0), ipady=6)

        if edit_mode and self.selected_case:
            student_id_entry.insert(0, self.selected_case.get('student_id', ''))

        # Other student fields
        other_fields = [
            ("Student Name", "student"),
            ("Student Email", "student_email"),
        ]

        for label, key in other_fields:
            tk.Label(
                content,
                text=label,
                font=('Segoe UI', 10),
                fg=self.colors['text_muted'],
                bg=self.colors['light']
            ).pack(anchor='w', pady=(10, 3))

            entry = tk.Entry(
                content,
                font=('Segoe UI', 11),
                bg=self.colors['light'],
                fg=self.colors['text_dark'],
                insertbackground=self.colors['text_dark'],
                relief='flat'
            )
            entry.pack(fill=tk.X, ipady=8)
            entries[key] = entry

            if edit_mode and self.selected_case:
                entry.insert(0, self.selected_case.get(key, ''))

        # Course field with validation
        tk.Label(
            content,
            text=_t("misconduct.labels.course_module"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        course_frame = tk.Frame(content, bg=self.colors['light'])
        course_frame.pack(fill=tk.X)

        # Get valid courses for combobox
        valid_courses = self.get_valid_courses()
        course_values = [c['display'] for c in valid_courses]

        course_var = tk.StringVar()
        course_combo = ttk.Combobox(
            course_frame,
            textvariable=course_var,
            font=('Segoe UI', 11),
            values=course_values,
            width=40
        )
        course_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        entries['course'] = course_combo

        # Course validation status label
        course_status = tk.Label(
            content,
            text="",
            font=('Segoe UI', 9),
            bg=self.colors['light']
        )
        course_status.pack(anchor='w', pady=(2, 0))

        def validate_course_field():
            course_value = course_combo.get().strip()
            if not course_value:
                course_status.configure(text=_t("misconduct.labels.enter_course_code"), fg=self.colors['warning'])
                return False
            is_valid, message = self.validate_course(course_value)
            if is_valid:
                course_status.configure(text=f"✓ {message}", fg=self.colors['success'])
                return True
            else:
                course_status.configure(text=f"✗ {message}", fg=self.colors['danger'])
                return False

        validate_course_btn = tk.Button(
            course_frame,
            text=_t("misconduct.btn.validate"),
            font=('Segoe UI', 9),
            bg=self.colors['white'],
            fg=self.colors['text_dark'],
            relief='flat',
            padx=10,
            cursor='hand2',
            command=validate_course_field
        )
        validate_course_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Store validation function for use when saving
        entries['validate_course'] = validate_course_field

        if edit_mode and self.selected_case:
            course_combo.set(self.selected_case.get('course', ''))

        # Assignment selection section
        tk.Label(
            content,
            text=_t("misconduct.labels.related_assignment"),
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(20, 3))

        assignment_frame = tk.Frame(content, bg=self.colors['light'])
        assignment_frame.pack(fill=tk.X, pady=(0, 10))

        assignment_var = tk.StringVar(value="")
        assignment_combo = ttk.Combobox(
            assignment_frame,
            textvariable=assignment_var,
            font=('Segoe UI', 10),
            state='readonly',
            width=50
        )
        assignment_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)

        def load_assignments():
            student_id = entries['student_id'].get().strip()
            if student_id:
                assignments = self.get_student_assignments(student_id)
            else:
                # Load all active assignments if no student ID
                assignments = self.get_student_assignments(None)

            if assignments:
                assignment_combo['values'] = [f"{a['id']} - {a['title']}" for a in assignments]
                assignment_combo['state'] = 'readonly'
                if len(assignments) > 0:
                    assignment_combo.set('')  # Clear selection
            else:
                assignment_combo['values'] = ["No assignments found"]
                assignment_combo['state'] = 'readonly'

        # Store reference for auto-loading after lookup
        assignment_loader['func'] = load_assignments

        load_assign_btn = tk.Button(
            assignment_frame,
            text=_t("misconduct.btn.refresh"),
            font=('Segoe UI', 9),
            bg=self.colors['white'],
            fg=self.colors['text_dark'],
            relief='flat',
            padx=10,
            cursor='hand2',
            command=load_assignments
        )
        load_assign_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # Auto-load assignments when dialog opens
        load_assignments()

        # Violation type dropdown
        tk.Label(
            content,
            text=_t("misconduct.labels.violation_type"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        type_var = tk.StringVar()
        type_combo = ttk.Combobox(
            content,
            textvariable=type_var,
            values=["Plagiarism", "Unauthorized Collaboration", "Contract Cheating", "Exam Misconduct", "Fabrication", "Other"],
            font=('Segoe UI', 11),
            state='readonly'
        )
        type_combo.pack(fill=tk.X, ipady=4)

        # Severity dropdown
        tk.Label(
            content,
            text=_t("misconduct.labels.severity").replace(":", ""),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        severity_var = tk.StringVar()
        severity_combo = ttk.Combobox(
            content,
            textvariable=severity_var,
            values=["Minor", "Major", "Critical"],
            font=('Segoe UI', 11),
            state='readonly'
        )
        severity_combo.pack(fill=tk.X, ipady=4)

        # Notes
        tk.Label(
            content,
            text=_t("misconduct.labels.initial_notes"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        notes_text = scrolledtext.ScrolledText(
            content,
            font=('Segoe UI', 10),
            bg=self.colors['light'],
            fg=self.colors['text_dark'],
            relief='flat',
            height=5,
            wrap=tk.WORD,
            insertbackground=self.colors['text_dark']
        )
        notes_text.pack(fill=tk.X)

        def save_case():
            # Validate course (warning only, doesn't block)
            course_value = entries['course'].get().strip()
            if course_value:
                is_valid, message = self.validate_course(course_value)
                if not is_valid:
                    response = messagebox.askyesno(_t("misconduct.msg_titles.course_not_found"),
                        f"{message}\n\nThe course code was not found in the system, but you can still proceed.\n\nDo you want to continue creating this case?",
                        icon='warning'
                    )
                    if not response:
                        return

            # Include assignment info in notes if selected
            assignment_info = ""
            if assignment_var.get() and assignment_var.get() != "No assignments found":
                assignment_info = f"\n\nRelated Assignment: {assignment_var.get()}"

            # Extract just the course code if in "CODE - Name" or "CODE (Modules: ...)" format
            course_code = course_value.split(' - ')[0].strip() if course_value else ''
            course_code = course_code.split('(')[0].strip()

            new_case = {
                'id': self.get_next_case_id(),
                'student': entries['student'].get(),
                'student_id': entries['student_id'].get(),
                'student_email': entries['student_email'].get() if 'student_email' in entries else '',
                'course': course_code,
                'type': type_var.get(),
                'status': 'Under Review',
                'date_filed': datetime.now().strftime('%Y-%m-%d'),
                'severity': severity_var.get(),
                'notes': notes_text.get('1.0', tk.END).strip() + assignment_info
            }

            if all([new_case['student'], new_case['student_id'], new_case['course'], new_case['type'], new_case['severity']]):
                if self.save_case_to_db(new_case):
                    # Add to case history
                    self.add_case_history(new_case['id'], f"Case created: {new_case['type']} violation", 'info')

                    self.load_cases_from_db()
                    self.populate_tree()

                    # Refresh dashboard and analytics
                    if hasattr(self, 'dashboard_stats_frame'):
                        self.update_dashboard_stats()
                    if hasattr(self, 'analytics_content'):
                        self.refresh_analytics_tab()

                    # Send email notification to student
                    student_email = new_case.get('student_email', '').strip()
                    email_sent = False
                    if student_email and EMAIL_AVAILABLE and queue_email:
                        # Build assignment info for email
                        assignment_mention = ""
                        if assignment_var.get() and assignment_var.get() != "No assignments found":
                            assignment_mention = f"\nRelated Assignment: {assignment_var.get()}"

                        try:
                            from university_system.infrastructure.email.template_utils import render_template

                            subject, body = render_template('academics/misconduct_case_filed', {
                                'student_name': new_case['student'],
                                'case_id': new_case['id'],
                                'student_id': new_case['student_id'],
                                'course': new_case['course'],
                                'violation_type': new_case['type'],
                                'severity': new_case['severity'],
                                'date_filed': new_case['date_filed'],
                                'status': new_case['status'],
                                'assignment_mention': assignment_mention
                            })

                            # Fallback if template not found
                            if not subject or not body:
                                subject = f"Academic Misconduct Case Filed - {new_case['id']}"
                                body = f"Dear {new_case['student']},\n\nThis is to inform you that an academic misconduct case has been filed.\n\nCase ID: {new_case['id']}\nCourse: {new_case['course']}\nViolation: {new_case['type']}\n\nPlease contact the Academic Integrity Office.\n\nSincerely,\nAcademic Misconduct Panel"
                        except Exception as e:
                            print(f"Error rendering email template: {e}")
                            subject = f"Academic Misconduct Case Filed - {new_case['id']}"
                            body = f"Dear {new_case['student']},\n\nThis is to inform you that an academic misconduct case has been filed.\n\nCase ID: {new_case['id']}\nCourse: {new_case['course']}\nViolation: {new_case['type']}\n\nPlease contact the Academic Integrity Office.\n\nSincerely,\nAcademic Misconduct Panel"

                        try:
                            success = queue_email(student_email, subject, body)
                            if success:
                                email_sent = True
                                self.add_case_history(new_case['id'], f"Notification email sent to {student_email}", 'info')
                        except Exception as e:
                            print(f"Failed to send case creation email: {e}")

                    dialog.destroy()

                    # Show success message with email status
                    success_msg = f"Case {new_case['id']} created successfully."
                    if email_sent:
                        success_msg += f"\n\nNotification email has been sent to {student_email}."
                    elif student_email:
                        success_msg += f"\n\nWarning: Could not send notification email to {student_email}."
                    else:
                        success_msg += "\n\nNote: No email address on file. Student was not notified."

                    messagebox.showinfo(_t("misconduct.msg_titles.success"), success_msg)
                else:
                    messagebox.showerror(_t("misconduct.msg_titles.error"), "Failed to save case to database.")
            else:
                messagebox.showwarning(_t("misconduct.msg_titles.incomplete"), "Please fill in all required fields.")

        # Buttons
        btn_frame = tk.Frame(content, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        self.create_button(btn_frame, "Cancel", dialog.destroy, 'secondary').pack(side=tk.RIGHT, padx=(10, 0))
        self.create_button(btn_frame, "Save Case", save_case, 'primary').pack(side=tk.RIGHT)
        
    def delete_case(self):
        """Delete the selected case."""
        if not self.selected_case:
            messagebox.showwarning(_t("misconduct.msg_titles.no_selection"), "Please select a case to delete.")
            return

        if messagebox.askyesno(_t("misconduct.msg_titles.confirm_delete"), f"Are you sure you want to delete case {self.selected_case['id']}?\n\nThis action cannot be undone."):
            if self.delete_case_from_db(self.selected_case['id']):
                self.selected_case = None
                self.load_cases_from_db()
                self.populate_tree()

                # Refresh dashboard and analytics
                if hasattr(self, 'dashboard_stats_frame'):
                    self.update_dashboard_stats()
                if hasattr(self, 'analytics_content'):
                    self.refresh_analytics_tab()

                messagebox.showinfo(_t("misconduct.msg_titles.deleted"), "Case deleted successfully.")
            else:
                messagebox.showerror(_t("misconduct.msg_titles.error"), "Failed to delete case from database.")
            
    def edit_case(self):
        """Edit the selected case."""
        if self.selected_case:
            self.open_case_dialog(edit_mode=True)

    def view_case_details(self):
        """View full details of the selected case in a popup window."""
        if not self.selected_case:
            messagebox.showwarning(_t("misconduct.msg_titles.no_selection"), "Please select a case to view.")
            return

        case = self.selected_case

        # Create view dialog - bigger window
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Case Details - {case['id']}")
        dialog.geometry("800x700")
        dialog.configure(bg=self.colors['light'])
        dialog.transient(self.root)

        # Header
        header = tk.Frame(dialog, bg=self.colors['white'], height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text=f"📄 Case {case['id']}",
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['white']
        ).pack(side=tk.LEFT, padx=20, pady=15)

        # Status badge
        status_colors = {
            'Under Review': self.colors['warning'],
            'Pending Hearing': self.colors['info'],
            'Resolved': self.colors['success']
        }
        tk.Label(
            header,
            text=case['status'],
            font=('Segoe UI', 10, 'bold'),
            fg=status_colors.get(case['status'], self.colors['text_dark']),
            bg=self.colors['white']
        ).pack(side=tk.RIGHT, padx=20, pady=15)

        # Content
        content = tk.Frame(dialog, bg=self.colors['light'])
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        # Case details
        details = [
            ("Student Name", case['student']),
            ("Student ID", case['student_id']),
            ("Student Email", case.get('student_email', 'Not provided')),
            ("Course", case['course']),
            ("Violation Type", case['type']),
            ("Severity", case['severity']),
            ("Date Filed", case['date_filed']),
            ("Status", case['status']),
        ]

        if case.get('hearing_date'):
            details.append(("Hearing Date", case['hearing_date']))
        if case.get('hearing_time'):
            details.append(("Hearing Time", case['hearing_time']))
        if case.get('hearing_location'):
            details.append(("Hearing Location", case['hearing_location']))
        if case.get('ruling'):
            details.append(("Ruling", case['ruling']))

        for label, value in details:
            row = tk.Frame(content, bg=self.colors['light'])
            row.pack(fill=tk.X, pady=5)

            tk.Label(
                row,
                text=f"{label}:",
                font=('Segoe UI', 10),
                fg=self.colors['text_muted'],
                bg=self.colors['light'],
                width=15,
                anchor='w'
            ).pack(side=tk.LEFT)

            tk.Label(
                row,
                text=value or 'N/A',
                font=('Segoe UI', 10),
                fg=self.colors['text_dark'],
                bg=self.colors['light'],
                anchor='w'
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Notes section
        tk.Label(
            content,
            text=_t("misconduct.labels.case_notes"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(20, 5))

        notes_frame = tk.Frame(content, bg=self.colors['light'])
        notes_frame.pack(fill=tk.BOTH, expand=True)

        notes_text = scrolledtext.ScrolledText(
            notes_frame,
            font=('Segoe UI', 10),
            bg=self.colors['light'],
            fg=self.colors['text_dark'],
            relief='flat',
            height=6,
            wrap=tk.WORD,
            state='normal'
        )
        notes_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        notes_text.insert(tk.END, case.get('notes', 'No notes available.'))
        notes_text.configure(state='disabled')

        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, padx=30, pady=20)

        self.create_button(btn_frame, "Close", dialog.destroy, 'secondary').pack(side=tk.RIGHT)
        self.create_button(btn_frame, "✏️ Edit Case", lambda: (dialog.destroy(), self.update_case()), 'primary').pack(side=tk.RIGHT, padx=(0, 10))

    def update_case(self):
        """Update/edit the selected case."""
        if not self.selected_case:
            messagebox.showwarning(_t("misconduct.msg_titles.no_selection"), "Please select a case to update.")
            return

        case = self.selected_case

        # Create update dialog - bigger window
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Update Case - {case['id']}")
        dialog.geometry("700x850")
        dialog.configure(bg=self.colors['light'])
        dialog.transient(self.root)
        dialog.grab_set()

        # Main container with scrollbar
        main_frame = tk.Frame(dialog, bg=self.colors['light'])
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas and scrollbar
        canvas = tk.Canvas(main_frame, bg=self.colors['light'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors['light'])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        dialog.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Content inside scrollable frame
        content = tk.Frame(scrollable_frame, bg=self.colors['light'])
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        tk.Label(
            content,
            text=f"Update Case {case['id']}",
            font=('Segoe UI', 16, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 20))

        entries = {}

        # Student ID with lookup button
        tk.Label(
            content,
            text=_t("misconduct.labels.student_id"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        id_frame = tk.Frame(content, bg=self.colors['light'])
        id_frame.pack(fill=tk.X)

        student_id_entry = tk.Entry(
            id_frame,
            font=('Segoe UI', 11),
            bg=self.colors['light'],
            fg=self.colors['text_dark'],
            insertbackground=self.colors['text_dark'],
            relief='flat'
        )
        student_id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        student_id_entry.insert(0, case['student_id'])
        entries['student_id'] = student_id_entry

        lookup_btn = tk.Button(
            id_frame,
            text=_t("misconduct.labels.lookup"),
            font=('Segoe UI', 9),
            bg=self.colors['accent'],
            fg=self.colors['white'],
            relief='flat',
            padx=10,
            cursor='hand2',
            command=lambda: self.lookup_student(student_id_entry, entries)
        )
        lookup_btn.pack(side=tk.LEFT, padx=(10, 0), ipady=6)

        # Other editable fields (excluding Course which has special validation)
        other_fields = [
            ("Student Name", "student", case['student']),
            ("Student Email", "student_email", case.get('student_email', '')),
        ]

        for label, key, value in other_fields:
            tk.Label(
                content,
                text=label,
                font=('Segoe UI', 10),
                fg=self.colors['text_muted'],
                bg=self.colors['light']
            ).pack(anchor='w', pady=(10, 3))

            entry = tk.Entry(
                content,
                font=('Segoe UI', 11),
                bg=self.colors['light'],
                fg=self.colors['text_dark'],
                insertbackground=self.colors['text_dark'],
                relief='flat'
            )
            entry.pack(fill=tk.X, ipady=8)
            entry.insert(0, value)
            entries[key] = entry

        # Course field with validation
        tk.Label(
            content,
            text=_t("misconduct.labels.course_module"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        course_frame = tk.Frame(content, bg=self.colors['light'])
        course_frame.pack(fill=tk.X)

        # Get valid courses for combobox
        valid_courses = self.get_valid_courses()
        course_values = [c['display'] for c in valid_courses]

        course_var = tk.StringVar()
        course_combo = ttk.Combobox(
            course_frame,
            textvariable=course_var,
            font=('Segoe UI', 11),
            values=course_values,
            width=40
        )
        course_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        course_combo.set(case['course'])
        entries['course'] = course_combo

        # Course validation status label
        course_status = tk.Label(
            content,
            text="",
            font=('Segoe UI', 9),
            bg=self.colors['light']
        )
        course_status.pack(anchor='w', pady=(2, 0))

        def validate_course_field():
            course_value = course_combo.get().strip()
            if not course_value:
                course_status.configure(text=_t("misconduct.labels.enter_course_code"), fg=self.colors['warning'])
                return False
            is_valid, message = self.validate_course(course_value)
            if is_valid:
                course_status.configure(text=f"✓ {message}", fg=self.colors['success'])
                return True
            else:
                course_status.configure(text=f"✗ {message}", fg=self.colors['danger'])
                return False

        validate_course_btn = tk.Button(
            course_frame,
            text=_t("misconduct.btn.validate"),
            font=('Segoe UI', 9),
            bg=self.colors['white'],
            fg=self.colors['text_dark'],
            relief='flat',
            padx=10,
            cursor='hand2',
            command=validate_course_field
        )
        validate_course_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Violation type dropdown
        tk.Label(
            content,
            text=_t("misconduct.labels.violation_type"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        type_var = tk.StringVar(value=case['type'])
        type_combo = ttk.Combobox(
            content,
            textvariable=type_var,
            values=["Plagiarism", "Unauthorized Collaboration", "Contract Cheating", "Exam Misconduct", "Fabrication", "Other"],
            font=('Segoe UI', 11),
            state='readonly'
        )
        type_combo.pack(fill=tk.X, ipady=4)

        # Severity dropdown
        tk.Label(
            content,
            text=_t("misconduct.labels.severity").replace(":", ""),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        severity_var = tk.StringVar(value=case['severity'])
        severity_combo = ttk.Combobox(
            content,
            textvariable=severity_var,
            values=["Minor", "Major", "Critical"],
            font=('Segoe UI', 11),
            state='readonly'
        )
        severity_combo.pack(fill=tk.X, ipady=4)

        # Status dropdown
        tk.Label(
            content,
            text=_t("misconduct.labels.status").replace(":", ""),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        status_var = tk.StringVar(value=case['status'])
        status_combo = ttk.Combobox(
            content,
            textvariable=status_var,
            values=["Under Review", "Pending Hearing", "Resolved"],
            font=('Segoe UI', 11),
            state='readonly'
        )
        status_combo.pack(fill=tk.X, ipady=4)

        # Notes
        tk.Label(
            content,
            text=_t("misconduct.sections.notes"),
            font=('Segoe UI', 10),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(10, 3))

        notes_text = scrolledtext.ScrolledText(
            content,
            font=('Segoe UI', 10),
            bg=self.colors['light'],
            fg=self.colors['text_dark'],
            relief='flat',
            height=6,
            wrap=tk.WORD,
            insertbackground=self.colors['text_dark']
        )
        notes_text.pack(fill=tk.X)
        notes_text.insert(tk.END, case.get('notes', ''))

        def save_updates():
            # Validate course (warning only, doesn't block)
            course_value = entries['course'].get().strip()
            if course_value:
                is_valid, message = self.validate_course(course_value)
                if not is_valid:
                    response = messagebox.askyesno(_t("misconduct.msg_titles.course_not_found"),
                        f"{message}\n\nThe course code was not found in the system, but you can still proceed.\n\nDo you want to continue updating this case?",
                        icon='warning'
                    )
                    if not response:
                        return

            # Extract just the course code if in "CODE - Name" or "CODE (Modules: ...)" format
            course_code = course_value.split(' - ')[0].strip() if course_value else ''
            course_code = course_code.split('(')[0].strip()

            updated_case = {
                'id': case['id'],
                'student': entries['student'].get(),
                'student_id': entries['student_id'].get(),
                'student_email': entries['student_email'].get(),
                'course': course_code,
                'type': type_var.get(),
                'severity': severity_var.get(),
                'status': status_var.get(),
                'notes': notes_text.get('1.0', tk.END).strip(),
                'date_filed': case['date_filed'],
                'hearing_date': case.get('hearing_date', ''),
                'hearing_time': case.get('hearing_time', ''),
                'hearing_location': case.get('hearing_location', ''),
                'ruling': case.get('ruling', ''),
                'ruling_rationale': case.get('ruling_rationale', '')
            }

            if all([updated_case['student'], updated_case['student_id'], updated_case['course']]):
                # Track what changed
                changes = []
                if case.get('type') != updated_case['type']:
                    changes.append(f"Violation Type: {case.get('type', 'N/A')} → {updated_case['type']}")
                if case.get('severity') != updated_case['severity']:
                    changes.append(f"Severity: {case.get('severity', 'N/A')} → {updated_case['severity']}")
                if case.get('status') != updated_case['status']:
                    changes.append(f"Status: {case.get('status', 'N/A')} → {updated_case['status']}")
                if case.get('notes', '') != updated_case['notes']:
                    changes.append("Case notes have been updated")

                if self.update_case_in_db(updated_case):
                    change_summary = ", ".join(changes) if changes else "Case details updated"
                    self.add_case_history(case['id'], change_summary, 'info')
                    self.load_cases_from_db()
                    self.populate_tree()

                    # Update selected case reference
                    for c in self.cases:
                        if c['id'] == case['id']:
                            self.selected_case = c
                            break

                    # Refresh dashboard and analytics
                    if hasattr(self, 'dashboard_stats_frame'):
                        self.update_dashboard_stats()
                    if hasattr(self, 'analytics_content'):
                        self.refresh_analytics_tab()

                    # Send email notification about changes
                    student_email = updated_case.get('student_email', '')
                    if student_email and changes and EMAIL_AVAILABLE and queue_email:
                        # Build changes list
                        changes_list = "\n".join([f"• {change}" for change in changes])

                        try:
                            from university_system.infrastructure.email.template_utils import render_template

                            subject, body = render_template('academics/misconduct_case_update', {
                                'student_name': updated_case['student'],
                                'case_id': case['id'],
                                'changes_list': changes_list,
                                'status': updated_case['status'],
                                'violation_type': updated_case['type'],
                                'severity': updated_case['severity']
                            })

                            # Fallback if template not found
                            if not subject or not body:
                                subject = f"Academic Misconduct Case Update - {case['id']}"
                                body = f"Dear {updated_case['student']},\n\nYour academic misconduct case ({case['id']}) has been updated.\n\nChanges:\n{changes_list}\n\nStatus: {updated_case['status']}\n\nRegards,\nAcademic Misconduct Panel"
                        except Exception as e:
                            print(f"Error rendering email template: {e}")
                            subject = f"Academic Misconduct Case Update - {case['id']}"
                            body = f"Dear {updated_case['student']},\n\nYour academic misconduct case ({case['id']}) has been updated.\n\nChanges:\n{changes_list}\n\nStatus: {updated_case['status']}\n\nRegards,\nAcademic Misconduct Panel"

                        try:
                            queue_email(student_email, subject, body)
                            self.add_case_history(case['id'], f"Update notification sent to {student_email}", 'email')
                        except Exception as e:
                            print(f"Failed to send update email: {e}")

                    dialog.destroy()
                    messagebox.showinfo(_t("misconduct.msg_titles.success"), f"Case {case['id']} updated successfully." +
                                       ("\nNotification email sent to student." if student_email and changes and EMAIL_AVAILABLE else ""))
                else:
                    messagebox.showerror(_t("misconduct.msg_titles.error"), "Failed to update case in database.")
            else:
                messagebox.showwarning(_t("misconduct.msg_titles.incomplete"), "Please fill in all required fields.")

        # Buttons
        btn_frame = tk.Frame(content, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        self.create_button(btn_frame, "Cancel", dialog.destroy, 'secondary').pack(side=tk.RIGHT, padx=(10, 0))
        self.create_button(btn_frame, "💾 Save Changes", save_updates, 'primary').pack(side=tk.RIGHT)

    def return_to_home(self):
        """Close this window and return to the main GUI."""
        if messagebox.askyesno(_t("misconduct.msg_titles.confirm"), "Are you sure you want to close the Academic Misconduct Panel?"):
            self.root.destroy()

    def notify_student(self):
        """Send notification to student via email."""
        if not self.selected_case:
            messagebox.showwarning(_t("misconduct.msg_titles.no_selection"), "Please select a case first.")
            return

        # Create notification dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Notify Student")
        dialog.geometry("600x500")
        dialog.configure(bg=self.colors['light'])
        dialog.transient(self.root)
        dialog.grab_set()

        content = tk.Frame(dialog, bg=self.colors['light'])
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        tk.Label(
            content,
            text=_t("misconduct.labels.send_notification"),
            font=('Segoe UI', 16, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 20))

        # Student info
        info_frame = tk.Frame(content, bg=self.colors['light'])
        info_frame.pack(fill=tk.X, pady=(0, 15))

        tk.Label(info_frame, text=f"To: {self.selected_case['student']} ({self.selected_case['student_id']})",
                 font=('Segoe UI', 10), fg=self.colors['text_dark'], bg=self.colors['light']).pack(anchor='w', padx=15, pady=10)

        # Email field
        tk.Label(content, text=_t("misconduct.labels.student_email"), font=('Segoe UI', 10),
                 fg=self.colors['text_muted'], bg=self.colors['light']).pack(anchor='w', pady=(0, 5))

        email_entry = tk.Entry(content, font=('Segoe UI', 11), bg=self.colors['light'],
                               fg=self.colors['text_dark'], insertbackground=self.colors['text_dark'], relief='flat')
        email_entry.pack(fill=tk.X, ipady=8)
        email_entry.insert(0, self.selected_case.get('student_email', ''))

        # Subject
        tk.Label(content, text=_t("misconduct.labels.subject"), font=('Segoe UI', 10),
                 fg=self.colors['text_muted'], bg=self.colors['light']).pack(anchor='w', pady=(15, 5))

        subject_entry = tk.Entry(content, font=('Segoe UI', 11), bg=self.colors['light'],
                                 fg=self.colors['text_dark'], insertbackground=self.colors['text_dark'], relief='flat')
        subject_entry.pack(fill=tk.X, ipady=8)
        subject_entry.insert(0, f"Academic Integrity Case {self.selected_case['id']} - Notification")

        # Message body
        tk.Label(content, text=_t("misconduct.labels.message"), font=('Segoe UI', 10),
                 fg=self.colors['text_muted'], bg=self.colors['light']).pack(anchor='w', pady=(15, 5))

        message_text = scrolledtext.ScrolledText(content, font=('Segoe UI', 10), bg=self.colors['light'],
                                                  fg=self.colors['text_dark'], relief='flat', height=8,
                                                  insertbackground=self.colors['text_dark'])
        message_text.pack(fill=tk.BOTH, expand=True)

        # Default message
        default_msg = f"""Dear {self.selected_case['student']},

This is to inform you that an academic integrity case ({self.selected_case['id']}) has been filed regarding your coursework in {self.selected_case['course']}.

Violation Type: {self.selected_case['type']}
Current Status: {self.selected_case['status']}
Date Filed: {self.selected_case['date_filed']}

Please contact the Office of Academic Integrity to discuss this matter.

Sincerely,
Office of Academic Integrity"""
        message_text.insert(tk.END, default_msg)

        def send_notification():
            email = email_entry.get().strip()
            subject = subject_entry.get().strip()
            message = message_text.get('1.0', tk.END).strip()

            if not email:
                messagebox.showwarning(_t("misconduct.msg_titles.missing_email"), "Please enter the student's email address.")
                return

            if not EMAIL_AVAILABLE or queue_email is None:
                messagebox.showerror(_t("misconduct.msg_titles.email_unavailable"), "Email system is not available.")
                return

            try:
                success = queue_email(email, subject, message)
                if success:
                    # Update case with email and add to history
                    self.selected_case['student_email'] = email
                    self.update_case_in_db(self.selected_case)
                    self.add_case_history(self.selected_case['id'], f"Student notified via email to {email}", 'warning')
                    messagebox.showinfo(_t("misconduct.msg_titles.success"), f"Notification sent to {email}")
                    dialog.destroy()
                else:
                    messagebox.showerror(_t("misconduct.msg_titles.error"), "Failed to send email. Please try again.")
            except Exception as e:
                messagebox.showerror(_t("misconduct.msg_titles.error"), f"Failed to send notification: {str(e)}")

        # Buttons
        btn_frame = tk.Frame(content, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        self.create_button(btn_frame, "Cancel", dialog.destroy, 'secondary').pack(side=tk.RIGHT, padx=(10, 0))
        self.create_button(btn_frame, "📧 Send Email", send_notification, 'primary').pack(side=tk.RIGHT)

    def schedule_hearing(self):
        """Schedule a hearing for the case with calendar selection."""
        if not self.selected_case:
            messagebox.showwarning(_t("misconduct.msg_titles.no_selection"), "Please select a case first.")
            return

        # Create scheduling dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Schedule Hearing")
        dialog.geometry("500x600")
        dialog.configure(bg=self.colors['light'])
        dialog.transient(self.root)
        dialog.grab_set()

        content = tk.Frame(dialog, bg=self.colors['light'])
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        tk.Label(
            content,
            text=_t("misconduct.btn.schedule_hearing"),
            font=('Segoe UI', 16, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 20))

        tk.Label(content, text=f"Case: {self.selected_case['id']} - {self.selected_case['student']}",
                 font=('Segoe UI', 10), fg=self.colors['text_muted'], bg=self.colors['light']).pack(anchor='w', pady=(0, 20))

        # Date selection
        tk.Label(content, text=_t("misconduct.labels.hearing_date"), font=('Segoe UI', 10),
                 fg=self.colors['text_muted'], bg=self.colors['light']).pack(anchor='w', pady=(0, 5))

        date_frame = tk.Frame(content, bg=self.colors['light'])
        date_frame.pack(fill=tk.X, pady=(0, 15))

        # Simple date entry (YYYY-MM-DD format)
        date_entry = tk.Entry(date_frame, font=('Segoe UI', 11), bg=self.colors['light'],
                              fg=self.colors['text_dark'], insertbackground=self.colors['text_dark'],
                              relief='flat', width=15)
        date_entry.pack(side=tk.LEFT, ipady=8)
        date_entry.insert(0, (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))

        tk.Label(date_frame, text=_t("misconduct.labels.date_format"), font=('Segoe UI', 9),
                 fg=self.colors['text_muted'], bg=self.colors['light']).pack(side=tk.LEFT)

        # Quick date buttons
        quick_frame = tk.Frame(content, bg=self.colors['light'])
        quick_frame.pack(fill=tk.X, pady=(0, 15))

        for days, label in [(7, "1 Week"), (14, "2 Weeks"), (21, "3 Weeks")]:
            future_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
            btn = tk.Button(quick_frame, text=label, font=('Segoe UI', 9),
                           bg=self.colors['white'], fg=self.colors['text_muted'],
                           relief='flat', padx=10, pady=5,
                           command=lambda d=future_date: (date_entry.delete(0, tk.END), date_entry.insert(0, d)))
            btn.pack(side=tk.LEFT, padx=(0, 10))

        # Time selection
        tk.Label(content, text=_t("misconduct.labels.hearing_time"), font=('Segoe UI', 10),
                 fg=self.colors['text_muted'], bg=self.colors['light']).pack(anchor='w', pady=(0, 5))

        time_frame = tk.Frame(content, bg=self.colors['light'])
        time_frame.pack(fill=tk.X, pady=(0, 15))

        time_var = tk.StringVar(value="10:00 AM")
        times = ["9:00 AM", "10:00 AM", "11:00 AM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM"]
        time_combo = ttk.Combobox(time_frame, textvariable=time_var, values=times,
                                   font=('Segoe UI', 11), state='readonly', width=12)
        time_combo.pack(side=tk.LEFT)

        # Location
        tk.Label(content, text=_t("misconduct.labels.location"), font=('Segoe UI', 10),
                 fg=self.colors['text_muted'], bg=self.colors['light']).pack(anchor='w', pady=(0, 5))

        location_entry = tk.Entry(content, font=('Segoe UI', 11), bg=self.colors['light'],
                                  fg=self.colors['text_dark'], insertbackground=self.colors['text_dark'], relief='flat')
        location_entry.pack(fill=tk.X, ipady=8)
        location_entry.insert(0, "Academic Integrity Office, Room 201")

        # Student email for notification
        tk.Label(content, text=_t("misconduct.labels.student_email_notification"), font=('Segoe UI', 10),
                 fg=self.colors['text_muted'], bg=self.colors['light']).pack(anchor='w', pady=(15, 5))

        email_entry = tk.Entry(content, font=('Segoe UI', 11), bg=self.colors['light'],
                               fg=self.colors['text_dark'], insertbackground=self.colors['text_dark'], relief='flat')
        email_entry.pack(fill=tk.X, ipady=8)
        email_entry.insert(0, self.selected_case.get('student_email', ''))

        # Send notification checkbox
        send_email_var = tk.BooleanVar(value=True)
        tk.Checkbutton(content, text=_t("misconduct.labels.send_email_notification"), variable=send_email_var,
                       font=('Segoe UI', 10), fg=self.colors['text_muted'], bg=self.colors['light'],
                       selectcolor=self.colors['light'], activebackground=self.colors['light']).pack(anchor='w', pady=(15, 0))

        def schedule():
            hearing_date = date_entry.get().strip()
            hearing_time = time_var.get()
            location = location_entry.get().strip()
            email = email_entry.get().strip()

            if not hearing_date or not hearing_time or not location:
                messagebox.showwarning(_t("misconduct.msg_titles.missing_info"), "Please fill in all fields.")
                return

            # Update case
            self.selected_case['hearing_date'] = hearing_date
            self.selected_case['hearing_time'] = hearing_time
            self.selected_case['hearing_location'] = location
            self.selected_case['status'] = 'Pending Hearing'
            self.selected_case['student_email'] = email

            if self.update_case_in_db(self.selected_case):
                self.add_case_history(self.selected_case['id'],
                                      f"Hearing scheduled for {hearing_date} at {hearing_time} in {location}", 'info')

                # Reload cases and update tree
                self.load_cases_from_db()
                self.populate_tree()

                # Send email notification if requested
                if send_email_var.get() and email and EMAIL_AVAILABLE and queue_email:
                    try:
                        from university_system.infrastructure.email.template_utils import render_template

                        subject, body = render_template('academics/misconduct_hearing_scheduled', {
                            'student_name': self.selected_case['student'],
                            'case_id': self.selected_case['id'],
                            'hearing_date': hearing_date,
                            'hearing_time': hearing_time,
                            'location': location
                        })

                        # Fallback if template not found
                        if not subject or not body:
                            subject = f"Academic Integrity Hearing Scheduled - Case {self.selected_case['id']}"
                            body = f"Dear {self.selected_case['student']},\n\nA hearing has been scheduled for case {self.selected_case['id']}.\n\nDate: {hearing_date}\nTime: {hearing_time}\nLocation: {location}\n\nSincerely,\nOffice of Academic Integrity"
                    except Exception as e:
                        print(f"Error rendering email template: {e}")
                        subject = f"Academic Integrity Hearing Scheduled - Case {self.selected_case['id']}"
                        body = f"Dear {self.selected_case['student']},\n\nA hearing has been scheduled for case {self.selected_case['id']}.\n\nDate: {hearing_date}\nTime: {hearing_time}\nLocation: {location}\n\nSincerely,\nOffice of Academic Integrity"

                    try:
                        if queue_email(email, subject, body):
                            self.add_case_history(self.selected_case['id'],
                                                  f"Hearing notification sent to {email}", 'warning')
                            messagebox.showinfo(_t("misconduct.msg_titles.success"), f"Hearing scheduled and notification sent to {email}")
                        else:
                            messagebox.showinfo(_t("misconduct.msg_titles.partial_success"), "Hearing scheduled, but email notification failed.")
                    except Exception as e:
                        messagebox.showinfo(_t("misconduct.msg_titles.partial_success"), f"Hearing scheduled, but email failed: {str(e)}")
                else:
                    messagebox.showinfo(_t("misconduct.msg_titles.success"), "Hearing scheduled successfully.")

                dialog.destroy()
                self.create_overview_fields()
            else:
                messagebox.showerror(_t("misconduct.msg_titles.error"), "Failed to save hearing details.")

        # Buttons
        btn_frame = tk.Frame(content, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(30, 0))

        self.create_button(btn_frame, "Cancel", dialog.destroy, 'secondary').pack(side=tk.RIGHT, padx=(10, 0))
        self.create_button(btn_frame, "📅 Schedule Hearing", schedule, 'primary').pack(side=tk.RIGHT)
            
    def upload_evidence(self):
        """Upload evidence files for the selected case."""
        if not self.selected_case:
            messagebox.showwarning(_t("misconduct.msg_titles.no_selection"), "Please select a case to upload evidence for.")
            return

        from tkinter import filedialog
        import shutil
        import os

        case = self.selected_case

        # Create evidence upload dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Upload Evidence - {case['id']}")
        dialog.geometry("700x600")
        dialog.configure(bg=self.colors['light'])
        dialog.transient(self.root)
        dialog.grab_set()

        content = tk.Frame(dialog, bg=self.colors['light'])
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        tk.Label(
            content,
            text=f"Evidence for Case {case['id']}",
            font=('Segoe UI', 16, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 20))

        # Current evidence list
        tk.Label(
            content,
            text=_t("misconduct.labels.current_evidence"),
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 10))

        # Evidence list frame with scrollbar
        list_frame = tk.Frame(content, bg=self.colors['light'])
        list_frame.pack(fill=tk.BOTH, expand=True)

        evidence_listbox = tk.Listbox(
            list_frame,
            font=('Segoe UI', 10),
            bg=self.colors['light'],
            fg=self.colors['text_dark'],
            selectbackground=self.colors['accent'],
            selectforeground=self.colors['light'],
            relief='flat',
            height=10
        )
        evidence_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        list_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=evidence_listbox.yview)
        evidence_listbox.configure(yscrollcommand=list_scrollbar.set)
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load existing evidence
        def load_evidence_list():
            evidence_listbox.delete(0, tk.END)
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, file_name, file_size, uploaded_date
                    FROM academic_misconduct_evidence
                    WHERE case_id = ?
                    ORDER BY uploaded_date DESC
                ''', (case['id'],))
                evidence = cursor.fetchall()
                conn.close()

                for e in evidence:
                    evidence_listbox.insert(tk.END, f"{e['file_name']} ({e['file_size']}) - {e['uploaded_date']}")

                if not evidence:
                    evidence_listbox.insert(tk.END, "No evidence files uploaded yet.")
            except Exception as ex:
                evidence_listbox.insert(tk.END, f"Error loading evidence: {str(ex)}")

        load_evidence_list()

        # Selected files for upload
        selected_files = []

        # File selection display
        tk.Label(
            content,
            text=_t("misconduct.labels.files_to_upload"),
            font=('Segoe UI', 10, 'bold'),
            fg=self.colors['text_muted'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(20, 5))

        files_text = scrolledtext.ScrolledText(
            content,
            font=('Segoe UI', 9),
            bg=self.colors['light'],
            fg=self.colors['text_dark'],
            relief='flat',
            height=4,
            wrap=tk.WORD,
            state='disabled'
        )
        files_text.pack(fill=tk.X)

        def select_files():
            nonlocal selected_files
            filetypes = [
                ("All Files", "*.*"),
                ("Documents", "*.pdf *.doc *.docx *.txt"),
                ("Images", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("Spreadsheets", "*.xls *.xlsx *.csv"),
            ]
            files = filedialog.askopenfilenames(
                title="Select Evidence Files",
                filetypes=filetypes
            )
            if files:
                selected_files = list(files)
                files_text.configure(state='normal')
                files_text.delete('1.0', tk.END)
                for f in selected_files:
                    size = os.path.getsize(f)
                    size_str = f"{size / 1024:.1f} KB" if size < 1024*1024 else f"{size / (1024*1024):.1f} MB"
                    files_text.insert(tk.END, f"{os.path.basename(f)} ({size_str})\n")
                files_text.configure(state='disabled')

        def upload_files():
            if not selected_files:
                messagebox.showwarning(_t("misconduct.msg_titles.no_files"), "Please select files to upload first.")
                return

            # Create evidence directory if it doesn't exist
            try:
                evidence_dir = DEFAULT_DB_PATH.parent.parent / "evidence" / case['id'].replace('-', '_')
                evidence_dir.mkdir(parents=True, exist_ok=True)
                # Set restrictive permissions on evidence directory
                try:
                    os.chmod(evidence_dir, 0o700)
                except OSError:
                    pass
            except Exception as ex:
                messagebox.showerror(_t("misconduct.msg_titles.error"), f"Could not create evidence directory: {str(ex)}")
                return

            uploaded_count = 0
            skipped_files = []
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            for file_path in selected_files:
                try:
                    file_name = os.path.basename(file_path)

                    # Read file content for secure validation
                    with open(file_path, 'rb') as f:
                        file_content = f.read()

                    file_size = len(file_content)
                    size_str = f"{file_size / 1024:.1f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.1f} MB"

                    # Validate file using secure upload handler if available
                    if SECURE_UPLOAD_AVAILABLE and validate_upload:
                        validation = validate_upload(file_name, file_content, category='documents')
                        if not validation['valid']:
                            skipped_files.append(f"{file_name}: {validation['error']}")
                            continue
                        safe_name = validation['safe_filename']
                    else:
                        safe_name = secure_filename(file_name)

                    # Copy file to evidence directory with sanitized name
                    dest_path = evidence_dir / safe_name
                    counter = 1
                    while dest_path.exists():
                        name, ext = os.path.splitext(safe_name)
                        dest_path = evidence_dir / f"{name}_{counter}{ext}"
                        counter += 1

                    shutil.copy2(file_path, dest_path)

                    # Set restrictive permissions on uploaded file
                    try:
                        os.chmod(dest_path, 0o600)
                    except OSError:
                        pass

                    # Save to database with sanitized filename
                    cursor.execute('''
                        INSERT INTO academic_misconduct_evidence
                        (case_id, file_name, file_path, file_size, uploaded_date)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (case['id'], safe_name, str(dest_path), size_str,
                          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                    uploaded_count += 1

                except Exception as ex:
                    print(f"Error uploading {file_path}: {ex}")
                    skipped_files.append(f"{os.path.basename(file_path)}: {str(ex)}")

            conn.commit()
            conn.close()

            # Show results
            if uploaded_count > 0:
                self.add_case_history(case['id'], f"{uploaded_count} evidence file(s) uploaded", 'info')
                msg = f"Successfully uploaded {uploaded_count} file(s)."
                if skipped_files:
                    msg += f"\n\n{len(skipped_files)} file(s) skipped due to security validation:\n"
                    msg += "\n".join(skipped_files[:5])  # Show first 5
                    if len(skipped_files) > 5:
                        msg += f"\n... and {len(skipped_files) - 5} more"
                messagebox.showinfo(_t("misconduct.msg_titles.upload_complete"), msg)
                load_evidence_list()

                # Clear selected files
                selected_files.clear()
                files_text.configure(state='normal')
                files_text.delete('1.0', tk.END)
                files_text.configure(state='disabled')
            elif skipped_files:
                messagebox.showwarning(_t("misconduct.msg_titles.upload_failed"),
                    f"All files were rejected due to security validation:\n\n" +
                    "\n".join(skipped_files[:5])
                )
            else:
                messagebox.showerror(_t("misconduct.msg_titles.error"), "No files were uploaded. Please try again.")

        def delete_selected_evidence():
            selection = evidence_listbox.curselection()
            if not selection:
                messagebox.showwarning(_t("misconduct.msg_titles.no_selection"), "Please select an evidence file to delete.")
                return

            selected_text = evidence_listbox.get(selection[0])
            if "No evidence" in selected_text or "Error" in selected_text:
                return

            if messagebox.askyesno(_t("misconduct.msg_titles.confirm_delete"), "Are you sure you want to delete this evidence file?"):
                try:
                    # Get the file name from the listbox text
                    file_name = selected_text.split(" (")[0]

                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()

                    # Get file path for deletion
                    cursor.execute('''
                        SELECT file_path FROM academic_misconduct_evidence
                        WHERE case_id = ? AND file_name = ?
                    ''', (case['id'], file_name))
                    result = cursor.fetchone()

                    if result and result[0]:
                        # Try to delete the physical file
                        try:
                            if os.path.exists(result[0]):
                                os.remove(result[0])
                        except (OSError, IOError):
                            pass

                    # Delete from database
                    cursor.execute('''
                        DELETE FROM academic_misconduct_evidence
                        WHERE case_id = ? AND file_name = ?
                    ''', (case['id'], file_name))

                    conn.commit()
                    conn.close()

                    self.add_case_history(case['id'], f"Evidence file '{file_name}' deleted", 'warning')
                    load_evidence_list()
                    messagebox.showinfo(_t("misconduct.msg_titles.deleted"), "Evidence file deleted successfully.")

                except Exception as ex:
                    messagebox.showerror(_t("misconduct.msg_titles.error"), f"Failed to delete evidence: {str(ex)}")

        # Buttons
        btn_frame = tk.Frame(content, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        self.create_button(btn_frame, "📂 Select Files", select_files, 'secondary').pack(side=tk.LEFT, padx=(0, 10))
        self.create_button(btn_frame, "⬆️ Upload", upload_files, 'primary').pack(side=tk.LEFT, padx=(0, 10))
        self.create_button(btn_frame, "🗑️ Delete Selected", delete_selected_evidence, 'danger').pack(side=tk.LEFT)
        self.create_button(btn_frame, "Close", dialog.destroy, 'secondary').pack(side=tk.RIGHT)
        
    def submit_decision(self):
        """Submit panel decision and notify student."""
        if not self.selected_case:
            messagebox.showwarning(_t("misconduct.msg_titles.no_case_selected"), "Please select a case before submitting a decision.")
            return

        if not self.ruling_var.get():
            messagebox.showwarning(_t("misconduct.msg_titles.no_selection"), "Please select a ruling before submitting.")
            return

        ruling = self.ruling_var.get()
        rationale = self.rationale_text.get('1.0', tk.END).strip() if hasattr(self, 'rationale_text') else ''

        # Confirm before submitting
        if not messagebox.askyesno(_t("misconduct.msg_titles.confirm_decision"),
                                   f"Are you sure you want to submit the following decision?\n\n"
                                   f"Case: {self.selected_case['id']}\n"
                                   f"Student: {self.selected_case['student']}\n"
                                   f"Decision: {ruling}\n\n"
                                   f"This action will notify the student via email."):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Determine new status based on ruling
            if ruling.startswith("Not Responsible") or ruling.startswith("Case Dismissed"):
                new_status = "Closed - Not Responsible"
            elif ruling.startswith("Deferred"):
                new_status = "Under Investigation"
            else:
                new_status = "Closed - Responsible"

            # Update case with decision
            cursor.execute('''
                UPDATE academic_misconduct_cases
                SET ruling = ?, ruling_rationale = ?, status = ?
                WHERE case_id = ?
            ''', (ruling, rationale, new_status, self.selected_case['id']))

            conn.commit()
            conn.close()

            # Add to case history
            self.add_case_history(
                self.selected_case['id'],
                f"Decision rendered: {ruling}",
                'decision'
            )

            # Send email notification to student
            student_email = self.selected_case.get('student_email', '')
            email_sent = False

            if student_email and EMAIL_AVAILABLE and queue_email:
                # Build rationale section if present
                rationale_section = ""
                if rationale:
                    rationale_section = f"\nDecision Rationale:\n{rationale}\n"

                try:
                    from university_system.infrastructure.email.template_utils import render_template

                    subject, body = render_template('academics/misconduct_case_decision', {
                        'student_name': self.selected_case['student'],
                        'case_id': self.selected_case['id'],
                        'violation_type': self.selected_case['type'],
                        'course': self.selected_case['course'],
                        'ruling': ruling,
                        'new_status': new_status,
                        'rationale_section': rationale_section
                    })

                    # Fallback if template not found
                    if not subject or not body:
                        subject = f"Academic Misconduct Case Decision - {self.selected_case['id']}"
                        body = f"Dear {self.selected_case['student']},\n\nThe Academic Misconduct Panel has reached a decision.\n\nCase ID: {self.selected_case['id']}\nRuling: {ruling}\nStatus: {new_status}\n{rationale_section}\nRegards,\nAcademic Misconduct Panel"
                except Exception as e:
                    print(f"Error rendering email template: {e}")
                    subject = f"Academic Misconduct Case Decision - {self.selected_case['id']}"
                    body = f"Dear {self.selected_case['student']},\n\nThe Academic Misconduct Panel has reached a decision.\n\nCase ID: {self.selected_case['id']}\nRuling: {ruling}\nStatus: {new_status}\n{rationale_section}\nRegards,\nAcademic Misconduct Panel"

                try:
                    queue_email(student_email, subject, body)
                    self.add_case_history(
                        self.selected_case['id'],
                        f"Decision notification sent to {student_email}",
                        'email'
                    )
                    email_sent = True
                except Exception as e:
                    print(f"Failed to send decision email: {e}")

            # Refresh UI
            self.load_cases_from_db()
            self.populate_tree()

            # Update selected case
            for c in self.cases:
                if c['id'] == self.selected_case['id']:
                    self.selected_case = c
                    break

            self.create_overview_fields()
            if hasattr(self, 'history_frame'):
                self.refresh_history_tab()

            # Clear the form
            self.ruling_var.set("")
            if hasattr(self, 'rationale_text'):
                self.rationale_text.delete('1.0', tk.END)

            success_msg = f"Decision '{ruling}' has been recorded for case {self.selected_case['id']}."
            if email_sent:
                success_msg += f"\n\nNotification email sent to {student_email}."
            elif student_email:
                success_msg += "\n\nNote: Email notification could not be sent."
            else:
                success_msg += "\n\nNote: No email address on file for student."

            messagebox.showinfo(_t("misconduct.msg_titles.decision_submitted"), success_msg)

        except Exception as e:
            messagebox.showerror(_t("misconduct.msg_titles.error"), f"Failed to submit decision: {str(e)}")

    def create_student_history_tab(self, parent):
        """Create the student history tab showing all cases for a student."""
        # Content frame with scrolling
        canvas = tk.Canvas(parent, bg=self.colors['white'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        self.student_history_content = tk.Frame(canvas, bg=self.colors['white'])

        self.student_history_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.student_history_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create initial content
        self.refresh_student_history_tab()

    def refresh_student_history_tab(self):
        """Refresh the student history tab content."""
        # Clear existing widgets
        for widget in self.student_history_content.winfo_children():
            widget.destroy()

        padding_frame = tk.Frame(self.student_history_content, bg=self.colors['white'])
        padding_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        if not self.selected_case:
            placeholder = tk.Label(
                padding_frame,
                text=_t("misconduct.student_history.select_case", "Select a case to view student history"),
                font=('Segoe UI', 12),
                fg=self.colors['text_muted'],
                bg=self.colors['white']
            )
            placeholder.pack(expand=True)
            return

        student_id = self.selected_case.get('student_id', '')
        student_name = self.selected_case.get('student', '')

        # Header
        header = tk.Label(
            padding_frame,
            text=f"Academic Misconduct History - {student_name} ({student_id})",
            font=('Segoe UI', 14, 'bold'),
            fg=self.colors['primary'],
            bg=self.colors['white']
        )
        header.pack(anchor='w', pady=(0, 20))

        # Get all cases for this student
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT case_id, date_filed, violation_type, status, severity, ruling
                FROM academic_misconduct_cases
                WHERE student_id = ?
                ORDER BY date_filed DESC
            """, (student_id,))
            student_cases = cursor.fetchall()
            conn.close()

            if not student_cases:
                no_history = tk.Label(
                    padding_frame,
                    text=_t("misconduct.student_history.no_history", "No previous misconduct cases found for this student."),
                    font=('Segoe UI', 11),
                    fg=self.colors['success'],
                    bg=self.colors['white']
                )
                no_history.pack(anchor='w', pady=10)
            else:
                # Summary stats
                stats_frame = tk.Frame(padding_frame, bg=self.colors['light'], relief='solid', bd=1)
                stats_frame.pack(fill=tk.X, pady=(0, 20))

                stats_grid = tk.Frame(stats_frame, bg=self.colors['light'])
                stats_grid.pack(padx=15, pady=15)

                total_cases = len(student_cases)
                resolved_cases = len([c for c in student_cases if c[3] == 'Resolved'])
                pending_cases = total_cases - resolved_cases
                guilty_rulings = len([c for c in student_cases if c[5] and 'guilty' in c[5].lower()])

                stats = [
                    ("Total Cases", str(total_cases), self.colors['info']),
                    ("Resolved", str(resolved_cases), self.colors['success']),
                    ("Active/Pending", str(pending_cases), self.colors['warning']),
                    ("Guilty Rulings", str(guilty_rulings), self.colors['danger'])
                ]

                for i, (label, value, color) in enumerate(stats):
                    stat_frame = tk.Frame(stats_grid, bg=self.colors['white'], padx=15, pady=10)
                    stat_frame.grid(row=0, column=i, padx=5)

                    tk.Label(
                        stat_frame,
                        text=value,
                        font=('Segoe UI', 18, 'bold'),
                        fg=color,
                        bg=self.colors['white']
                    ).pack()

                    tk.Label(
                        stat_frame,
                        text=label,
                        font=('Segoe UI', 9),
                        fg=self.colors['text_muted'],
                        bg=self.colors['white']
                    ).pack()

                # Case list
                tk.Label(
                    padding_frame,
                    text=_t("misconduct.labels.case_history"),
                    font=('Segoe UI', 11, 'bold'),
                    fg=self.colors['text_dark'],
                    bg=self.colors['white']
                ).pack(anchor='w', pady=(10, 5))

                for case in student_cases:
                    case_id, date_filed, violation_type, status, severity, ruling = case

                    case_frame = tk.Frame(padding_frame, bg=self.colors['light'], relief='solid', bd=1)
                    case_frame.pack(fill=tk.X, pady=5)

                    # Highlight current case
                    is_current = (case_id == self.selected_case['id'])
                    if is_current:
                        case_frame.configure(bg=self.colors['secondary'], relief='solid', bd=2)

                    case_info_frame = tk.Frame(case_frame, bg=case_frame['bg'])
                    case_info_frame.pack(fill=tk.X, padx=15, pady=10)

                    # Case ID and date
                    header_row = tk.Frame(case_info_frame, bg=case_frame['bg'])
                    header_row.pack(fill=tk.X)

                    case_id_label = tk.Label(
                        header_row,
                        text=f"{'➤ ' if is_current else ''}Case ID: {case_id}",
                        font=('Segoe UI', 10, 'bold'),
                        fg=self.colors['white'] if is_current else self.colors['primary'],
                        bg=case_frame['bg']
                    )
                    case_id_label.pack(side=tk.LEFT)

                    date_label = tk.Label(
                        header_row,
                        text=f"Filed: {date_filed}",
                        font=('Segoe UI', 9),
                        fg=self.colors['white'] if is_current else self.colors['text_muted'],
                        bg=case_frame['bg']
                    )
                    date_label.pack(side=tk.RIGHT)

                    # Details
                    details = f"Type: {violation_type} | Severity: {severity} | Status: {status}"
                    if ruling:
                        details += f" | Ruling: {ruling}"

                    details_label = tk.Label(
                        case_info_frame,
                        text=details,
                        font=('Segoe UI', 9),
                        fg=self.colors['white'] if is_current else self.colors['text_dark'],
                        bg=case_frame['bg'],
                        wraplength=600,
                        justify='left'
                    )
                    details_label.pack(anchor='w', pady=(5, 0))

        except Exception as e:
            error_label = tk.Label(
                padding_frame,
                text=f"Error loading student history: {str(e)}",
                font=('Segoe UI', 10),
                fg=self.colors['danger'],
                bg=self.colors['white']
            )
            error_label.pack(anchor='w', pady=10)

    def create_analytics_tab(self, parent):
        """Create the analytics dashboard tab."""
        # Content frame with scrolling
        canvas = tk.Canvas(parent, bg=self.colors['white'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        self.analytics_content = tk.Frame(canvas, bg=self.colors['white'])

        self.analytics_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.analytics_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create analytics content
        self.refresh_analytics_tab()

    def refresh_analytics_tab(self):
        """Refresh the analytics dashboard."""
        # Clear existing widgets
        for widget in self.analytics_content.winfo_children():
            widget.destroy()

        padding_frame = tk.Frame(self.analytics_content, bg=self.colors['white'])
        padding_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Header
        header = tk.Label(
            padding_frame,
            text=_t("misconduct.sections.analytics_dashboard"),
            font=('Segoe UI', 16, 'bold'),
            fg=self.colors['primary'],
            bg=self.colors['white']
        )
        header.pack(anchor='w', pady=(0, 20))

        # Get analytics data from database
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Overall statistics
            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases")
            total_cases = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE status = 'Resolved'")
            resolved_cases = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE status != 'Resolved'")
            active_cases = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE status = 'Pending Hearing'")
            pending_hearings = cursor.fetchone()[0]

            # Top statistics panel
            stats_container = tk.Frame(padding_frame, bg=self.colors['white'])
            stats_container.pack(fill=tk.X, pady=(0, 20))

            overview_stats = [
                ("Total Cases", total_cases, self.colors['info'], "📋"),
                ("Active Cases", active_cases, self.colors['warning'], "⚠"),
                ("Resolved Cases", resolved_cases, self.colors['success'], "✓"),
                ("Pending Hearings", pending_hearings, self.colors['danger'], "⚖")
            ]

            for i, (label, value, color, icon) in enumerate(overview_stats):
                stat_card = tk.Frame(stats_container, bg=color, relief='flat', bd=0)
                stat_card.grid(row=0, column=i, padx=5, sticky='ew')
                stats_container.grid_columnconfigure(i, weight=1)

                tk.Label(
                    stat_card,
                    text=icon,
                    font=('Segoe UI', 20),
                    fg=self.colors['white'],
                    bg=color
                ).pack(pady=(10, 0))

                tk.Label(
                    stat_card,
                    text=str(value),
                    font=('Segoe UI', 24, 'bold'),
                    fg=self.colors['white'],
                    bg=color
                ).pack()

                tk.Label(
                    stat_card,
                    text=label,
                    font=('Segoe UI', 9),
                    fg=self.colors['white'],
                    bg=color
                ).pack(pady=(0, 10))

            # Violation types breakdown
            tk.Label(
                padding_frame,
                text=_t("misconduct.sections.violation_breakdown"),
                font=('Segoe UI', 12, 'bold'),
                fg=self.colors['text_dark'],
                bg=self.colors['white']
            ).pack(anchor='w', pady=(20, 10))

            cursor.execute("""
                SELECT violation_type, COUNT(*) as count
                FROM academic_misconduct_cases
                GROUP BY violation_type
                ORDER BY count DESC
            """)
            violation_types = cursor.fetchall()

            if violation_types:
                violations_frame = tk.Frame(padding_frame, bg=self.colors['light'], relief='solid', bd=1)
                violations_frame.pack(fill=tk.X, pady=(0, 20))

                for violation, count in violation_types:
                    row = tk.Frame(violations_frame, bg=self.colors['light'])
                    row.pack(fill=tk.X, padx=15, pady=8)

                    tk.Label(
                        row,
                        text=violation,
                        font=('Segoe UI', 10),
                        fg=self.colors['text_dark'],
                        bg=self.colors['light']
                    ).pack(side=tk.LEFT)

                    tk.Label(
                        row,
                        text=f"{count} cases",
                        font=('Segoe UI', 10, 'bold'),
                        fg=self.colors['secondary'],
                        bg=self.colors['light']
                    ).pack(side=tk.RIGHT)

            # Severity distribution
            tk.Label(
                padding_frame,
                text=_t("misconduct.sections.severity_distribution"),
                font=('Segoe UI', 12, 'bold'),
                fg=self.colors['text_dark'],
                bg=self.colors['white']
            ).pack(anchor='w', pady=(20, 10))

            cursor.execute("""
                SELECT severity, COUNT(*) as count
                FROM academic_misconduct_cases
                GROUP BY severity
                ORDER BY
                    CASE severity
                        WHEN 'Critical' THEN 1
                        WHEN 'High' THEN 2
                        WHEN 'Medium' THEN 3
                        WHEN 'Low' THEN 4
                        ELSE 5
                    END
            """)
            severities = cursor.fetchall()

            if severities:
                severity_frame = tk.Frame(padding_frame, bg=self.colors['light'], relief='solid', bd=1)
                severity_frame.pack(fill=tk.X, pady=(0, 20))

                severity_colors = {
                    'Critical': self.colors['danger'],
                    'High': self.colors['warning'],
                    'Medium': self.colors['info'],
                    'Low': self.colors['success']
                }

                for severity, count in severities:
                    row = tk.Frame(severity_frame, bg=self.colors['light'])
                    row.pack(fill=tk.X, padx=15, pady=8)

                    indicator = tk.Label(
                        row,
                        text="●",
                        font=('Segoe UI', 14),
                        fg=severity_colors.get(severity, self.colors['text_muted']),
                        bg=self.colors['light']
                    )
                    indicator.pack(side=tk.LEFT, padx=(0, 10))

                    tk.Label(
                        row,
                        text=f"{severity} Severity",
                        font=('Segoe UI', 10),
                        fg=self.colors['text_dark'],
                        bg=self.colors['light']
                    ).pack(side=tk.LEFT)

                    tk.Label(
                        row,
                        text=f"{count} cases",
                        font=('Segoe UI', 10, 'bold'),
                        fg=self.colors['secondary'],
                        bg=self.colors['light']
                    ).pack(side=tk.RIGHT)

            # Recent trends
            tk.Label(
                padding_frame,
                text=_t("misconduct.sections.recent_trends"),
                font=('Segoe UI', 12, 'bold'),
                fg=self.colors['text_dark'],
                bg=self.colors['white']
            ).pack(anchor='w', pady=(20, 10))

            cursor.execute("""
                SELECT strftime('%Y-%m', date_filed) as month, COUNT(*) as count
                FROM academic_misconduct_cases
                WHERE date_filed >= date('now', '-6 months')
                GROUP BY month
                ORDER BY month DESC
            """)
            monthly_trends = cursor.fetchall()

            if monthly_trends:
                trends_frame = tk.Frame(padding_frame, bg=self.colors['light'], relief='solid', bd=1)
                trends_frame.pack(fill=tk.X, pady=(0, 20))

                for month, count in monthly_trends:
                    row = tk.Frame(trends_frame, bg=self.colors['light'])
                    row.pack(fill=tk.X, padx=15, pady=8)

                    tk.Label(
                        row,
                        text=month,
                        font=('Segoe UI', 10),
                        fg=self.colors['text_dark'],
                        bg=self.colors['light']
                    ).pack(side=tk.LEFT)

                    # Simple bar representation
                    bar_frame = tk.Frame(row, bg=self.colors['secondary'], height=20, width=count*20)
                    bar_frame.pack(side=tk.LEFT, padx=10)

                    tk.Label(
                        row,
                        text=f"{count} cases",
                        font=('Segoe UI', 10, 'bold'),
                        fg=self.colors['secondary'],
                        bg=self.colors['light']
                    ).pack(side=tk.LEFT)

            # Export buttons
            export_frame = tk.Frame(padding_frame, bg=self.colors['white'])
            export_frame.pack(fill=tk.X, pady=(20, 0))

            tk.Label(
                export_frame,
                text=_t("misconduct.labels.export_options"),
                font=('Segoe UI', 11, 'bold'),
                fg=self.colors['text_dark'],
                bg=self.colors['white']
            ).pack(side=tk.LEFT, padx=(0, 15))

            self.create_button(export_frame, "📄 Export to CSV", self.export_analytics_csv, 'success').pack(side=tk.LEFT, padx=5)
            self.create_button(export_frame, "📊 Generate Report", self.generate_analytics_report, 'primary').pack(side=tk.LEFT, padx=5)

            conn.close()

        except Exception as e:
            error_label = tk.Label(
                padding_frame,
                text=f"Error loading analytics: {str(e)}",
                font=('Segoe UI', 10),
                fg=self.colors['danger'],
                bg=self.colors['white']
            )
            error_label.pack(anchor='w', pady=10)

    def export_analytics_csv(self):
        """Export analytics data to CSV."""
        try:
            from tkinter import filedialog
            import csv
            from datetime import datetime

            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"misconduct_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            if not filename:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT case_id, student_name, student_id, course, violation_type,
                       severity, status, date_filed, ruling
                FROM academic_misconduct_cases
                ORDER BY date_filed DESC
            """)

            cases = cursor.fetchall()
            conn.close()

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Case ID', 'Student Name', 'Student ID', 'Course', 'Violation Type',
                               'Severity', 'Status', 'Date Filed', 'Ruling'])
                writer.writerows(cases)

            messagebox.showinfo(_t("misconduct.msg_titles.export_successful"), f"Analytics data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror(_t("misconduct.msg_titles.export_error"), f"Failed to export data: {str(e)}")

    def generate_analytics_report(self):
        """Generate a comprehensive analytics report."""
        try:
            from datetime import datetime

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            report_lines = []
            report_lines.append("=" * 80)
            report_lines.append("ACADEMIC MISCONDUCT ANALYTICS REPORT")
            report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append("=" * 80)
            report_lines.append("")

            # Overall statistics
            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases")
            total = cursor.fetchone()[0]
            report_lines.append(f"Total Cases: {total}")

            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE status = 'Resolved'")
            resolved = cursor.fetchone()[0]
            report_lines.append(f"Resolved Cases: {resolved}")

            cursor.execute("SELECT COUNT(*) FROM academic_misconduct_cases WHERE status != 'Resolved'")
            active = cursor.fetchone()[0]
            report_lines.append(f"Active Cases: {active}")
            report_lines.append("")

            # Violation types
            report_lines.append("VIOLATION TYPES:")
            report_lines.append("-" * 40)
            cursor.execute("""
                SELECT violation_type, COUNT(*) FROM academic_misconduct_cases
                GROUP BY violation_type ORDER BY COUNT(*) DESC
            """)
            for violation, count in cursor.fetchall():
                report_lines.append(f"  {violation}: {count}")
            report_lines.append("")

            # Severity distribution
            report_lines.append("SEVERITY DISTRIBUTION:")
            report_lines.append("-" * 40)
            cursor.execute("""
                SELECT severity, COUNT(*) FROM academic_misconduct_cases
                GROUP BY severity
            """)
            for severity, count in cursor.fetchall():
                report_lines.append(f"  {severity}: {count}")

            conn.close()

            # Display report
            report_window = tk.Toplevel(self.root)
            report_window.title("Analytics Report")
            report_window.geometry("800x650")
            report_window.configure(bg=self.colors['light'])

            # Main container
            main_frame = tk.Frame(report_window, bg=self.colors['light'])
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            text_widget = scrolledtext.ScrolledText(
                main_frame,
                font=('Courier New', 10),
                bg=self.colors['white'],
                fg=self.colors['text_dark']
            )
            text_widget.pack(fill=tk.BOTH, expand=True)
            report_content = '\n'.join(report_lines)
            text_widget.insert('1.0', report_content)
            text_widget.configure(state='disabled')

            # Button frame
            btn_frame = tk.Frame(main_frame, bg=self.colors['light'])
            btn_frame.pack(fill=tk.X, pady=(10, 0))

            def save_report_as_txt():
                """Save the report to a text file."""
                try:
                    from tkinter import filedialog
                    filename = filedialog.asksaveasfilename(
                        defaultextension=".txt",
                        filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                        initialfile=f"misconduct_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    )
                    if filename:
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(report_content)
                        messagebox.showinfo(_t("misconduct.msg_titles.success"), f"Report saved to:\n{filename}")
                except Exception as e:
                    messagebox.showerror(_t("misconduct.msg_titles.save_error"), f"Failed to save report: {str(e)}")

            def send_report_to_admin():
                """Send the report to admin users via email."""
                try:
                    if not EMAIL_AVAILABLE or queue_email is None:
                        messagebox.showerror(_t("misconduct.msg_titles.email_unavailable"), "Email system is not available.")
                        return

                    # Get admin users from database
                    admin_conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    admin_cursor = admin_conn.cursor()
                    admin_cursor.execute("SELECT username, email FROM users WHERE LOWER(role) = 'admin' AND email IS NOT NULL AND email != ''")
                    admins = admin_cursor.fetchall()
                    admin_conn.close()

                    if not admins:
                        messagebox.showwarning(_t("misconduct.msg_titles.no_admins"), "No admin users with email addresses found in the system.")
                        return

                    # Send to each admin
                    subject = f"Academic Misconduct Analytics Report - {datetime.now().strftime('%Y-%m-%d')}"
                    message = f"""Academic Misconduct Analytics Report

This is an automated report from the Academic Misconduct Panel.

{report_content}

---
This report was generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}
"""

                    sent_count = 0
                    failed_admins = []

                    for admin_username, admin_email in admins:
                        try:
                            success = queue_email(admin_email, subject, message)
                            if success:
                                sent_count += 1
                            else:
                                failed_admins.append(admin_username)
                        except Exception as e:
                            failed_admins.append(f"{admin_username} ({str(e)})")

                    # Show results
                    if sent_count > 0:
                        result_msg = f"Report sent to {sent_count} admin user(s)."
                        if failed_admins:
                            result_msg += f"\n\nFailed to send to: {', '.join(failed_admins)}"
                        messagebox.showinfo(_t("misconduct.msg_titles.email_sent"), result_msg)
                    else:
                        messagebox.showerror(_t("misconduct.msg_titles.send_failed"), f"Failed to send to all admins.\n{', '.join(failed_admins)}")

                except Exception as e:
                    messagebox.showerror(_t("misconduct.msg_titles.send_error"), f"Failed to send report: {str(e)}")

            # Add buttons
            self.create_button(btn_frame, "💾 Save as TXT", save_report_as_txt, 'success').pack(side=tk.LEFT, padx=5)
            self.create_button(btn_frame, "📧 Send to Admin", send_report_to_admin, 'primary').pack(side=tk.LEFT, padx=5)
            self.create_button(btn_frame, "Close", report_window.destroy, 'secondary').pack(side=tk.RIGHT, padx=5)

        except Exception as e:
            messagebox.showerror(_t("misconduct.msg_titles.report_error"), f"Failed to generate report: {str(e)}")

def main():
    """Main entry point."""
    root = tk.Tk()
    app = AcademicMisconductPanel(root)
    root.mainloop()

if __name__ == "__main__":
    main()
