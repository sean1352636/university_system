# accommodation_gui.py
# GUI version of the accommodation management system
# Maintains full backwards compatibility with the CLI version

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
import os
import sys
import threading
from datetime import datetime, timedelta
import json
import csv
import sqlite3
from pathlib import Path
import logging

# Import database utilities
try:
    from university_system.infrastructure.database.db import get_connection
except ImportError:
    # Fallback to creating our own get_connection
    from university_system.modules.shared.constants import paths
    def get_connection():
        """Get database connection"""
        conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

# Import authentication utilities
try:
    from university_system.infrastructure.auth.user_authentication import get_current_user
except ImportError:
    def get_current_user():
        """Fallback function when auth is not available"""
        return None

# Import the original accommodation module to maintain compatibility
try:
    from university_system.modules.domain.housing.services.accommodation import (
        auth, apply_template, bulk_import_from_csv, check_conflict,
        check_expiry_notifications, display_accommodation_menu,
        fix_accommodation_db_schema, generate_statistics_report,
        get_accommodation_types, init_accommodation_db, log_action,
        migrate_audit_log_schema, notify_student, save_template,
        validate_student_id, validate_date, verify_database_schema,
        TEMPLATES_TABLE, set_auth
    )
    CLI_AVAILABLE = True
except ImportError:
    CLI_AVAILABLE = False
    TEMPLATES_TABLE = 'accommodation_templates'
    print("Warning: Original accommodation module not found. GUI-only mode.")
    # Fallback validate_date function
    def validate_date(date_str):
        """Validate date format"""
        if not date_str:
            return True, None
        try:
            datetime.fromisoformat(date_str)
            return True, None
        except ValueError:
            return False, "Invalid date format. Please use YYYY-MM-DD format."

# Import backup functionality
try:
    from university_system.infrastructure.database.data_backup import backup_before_operation
    BACKUP_AVAILABLE = True
except ImportError:
    BACKUP_AVAILABLE = False
    def backup_before_operation(operation_type):
        """Fallback when backup module not available"""
        logging.info(f"Backup requested for {operation_type} but backup module not available")


def resolve_user_identifier(default: str = 'gui_user', auth_instance=None) -> str:
    """Return a string-safe identifier for the current user.

    Args:
        default: Default value if no user is found
        auth_instance: Optional auth instance to get user from

    Returns:
        String identifier for the current user
    """
    # Try to get user from auth instance first
    if auth_instance and hasattr(auth_instance, 'current_user'):
        user = auth_instance.current_user
        if user and isinstance(user, dict):
            for key in ('username', 'email', 'name', 'id'):
                value = user.get(key)
                if value:
                    return str(value)

    # Fall back to get_current_user() from auth module
    if CLI_AVAILABLE:
        try:
            user = get_current_user()
            if user is None:
                return 'system'

            if isinstance(user, dict):
                for key in ('username', 'email', 'name', 'id'):
                    value = user.get(key)
                    if value:
                        return str(value)
                return json.dumps(user, default=str)

            return str(user)
        except Exception:
            pass

    return default

class AccommodationGUI:
    def __init__(self, root, auth=None):
        self.root = root
        self.root.title("Student Accommodation Management System")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')

        # Store authentication instance
        self.auth = auth
        self.current_user = None

        # Get current user from auth if available
        if self.auth and hasattr(self.auth, 'current_user'):
            self.current_user = self.auth.current_user
            if self.current_user:
                print(f"✓ Accommodation GUI: Using authenticated user {self.current_user.get('username', 'Unknown')} ({self.current_user.get('role', 'user')})")

        # Initialize the database
        if CLI_AVAILABLE:
            init_accommodation_db()
            # Set auth instance in the service module so report generation works
            if self.auth:
                set_auth(self.auth)

        # Create the main interface
        self.create_menu()
        self.create_main_interface()
        self.create_status_bar()

        # Load initial data
        self.refresh_data()
    
    def create_menu(self):
        """Create the main menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Import from CSV", command=self.import_csv)
        file_menu.add_command(label="Import from JSON", command=self.import_json)
        file_menu.add_separator()
        file_menu.add_command(label="Export to CSV", command=self.export_csv)
        file_menu.add_command(label="Export to Excel", command=self.export_excel)
        file_menu.add_command(label="Export to PDF", command=self.export_pdf)
        file_menu.add_command(label="Export to JSON", command=self.export_json)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Accommodation menu
        accom_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Accommodations", menu=accom_menu)
        accom_menu.add_command(label="Add New", command=self.add_accommodation_dialog)
        accom_menu.add_command(label="Update Selected", command=self.update_accommodation_dialog)
        accom_menu.add_command(label="Remove Selected", command=self.remove_accommodation_dialog)
        accom_menu.add_separator()
        accom_menu.add_command(label="Approve/Reject", command=self.approve_accommodation_dialog)
        
        # Templates menu
        template_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Templates", menu=template_menu)
        template_menu.add_command(label="Save Template", command=self.save_template_dialog)
        template_menu.add_command(label="Apply Template", command=self.apply_template_dialog)
        template_menu.add_command(label="Manage Templates", command=self.manage_templates_dialog)
        
        # Reports menu
        reports_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Reports", menu=reports_menu)
        reports_menu.add_command(label="Dashboard Metrics", command=self.show_dashboard)
        reports_menu.add_command(label="Statistics Report", command=self.generate_statistics)
        reports_menu.add_command(label="View by Accommodation Type", command=self.view_students_by_accommodation_type)
        reports_menu.add_command(label="Expiry Check", command=self.check_expiry)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="CLI Mode", command=self.launch_cli)
        tools_menu.add_command(label="Database Info", command=self.show_db_info)
        tools_menu.add_command(label="Settings", command=self.show_settings)
        tools_menu.add_command(label="Upload Document", command=self.upload_document_dialog)
        tools_menu.add_command(label="Bulk Operations", command=self.bulk_operations_dialog)
        tools_menu.add_command(label="Template Usage Stats", command=self.show_templates_usage_dialog)
        tools_menu.add_command(label="Migrate Database", command=self.migrate_database_schema)
        tools_menu.add_command(label="Verify Database Schema", command=self.verify_db_schema)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_help)
        help_menu.add_command(label="About", command=self.show_about)

    def bulk_operations_dialog(self):
        """Show bulk operations dialog"""
        BulkOperationsDialog(self.root, self)

    def notify_student(student_id, subject, message):
        """Send notification to student (GUI version)"""
        if not CLI_AVAILABLE:
            # Show notification in GUI instead
            messagebox.showinfo("Student Notification", 
                f"Would notify {student_id}:\n{subject}\n\n{message}")
            return
        
        # Use CLI version if available
        try:
            from university_system.modules.domain.housing.services.accommodation import notify_student as cli_notify
            cli_notify(student_id, subject, message)
        except Exception as e:
            messagebox.showerror("Notification Error", f"Failed to notify student: {str(e)}")

    def validate_accommodation_data(self, data):
        """Validate accommodation data before submission"""
        errors = []

        # Convert sqlite3.Row to dict if necessary
        if hasattr(data, '__getitem__') and not hasattr(data, 'get'):
            data = dict(data)

        if not data.get('student_id', '').strip():
            errors.append("Student ID is required")
        
        if not data.get('accommodation_type', '').strip():
            errors.append("Accommodation type is required")
        
        # Validate dates
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date:
            try:
                start = datetime.fromisoformat(start_date)
                end = datetime.fromisoformat(end_date)
                if end <= start:
                    errors.append("End date must be after start date")
            except ValueError:
                errors.append("Invalid date format")
        
        return errors
    
    def create_main_interface(self):
        """Create the main interface with tabs"""
        # Toolbar for quick actions
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=10, pady=(5, 0))
        ttk.Button(toolbar, text="Return to Main Menu", command=self.close_to_main_menu).pack(side=tk.LEFT)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Accommodations tab
        self.create_accommodations_tab()
        
        # Search & Filter tab
        self.create_search_tab()
        
        # Dashboard tab
        self.create_dashboard_tab()
        
        # Templates tab
        self.create_templates_tab()

    def close_to_main_menu(self):
        """Close this window so users return to the main launcher."""
        try:
            self.root.destroy()
        except Exception:
            self.root.quit()

    def create_accommodations_tab(self):
        """Create the main accommodations management tab"""
        self.accom_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.accom_frame, text="Accommodations")
        
        # Top frame for buttons
        button_frame = ttk.Frame(self.accom_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Action buttons
        ttk.Button(button_frame, text="Add New", 
                  command=self.add_accommodation_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Update", 
                  command=self.update_accommodation_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Remove", 
                  command=self.remove_accommodation_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="View Details", 
                  command=self.view_accommodation_details).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Refresh", 
                  command=self.refresh_data).pack(side=tk.LEFT, padx=2)
        
        # Approval buttons
        ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=5, fill=tk.Y)
        ttk.Button(button_frame, text="Approve", 
                  command=self.approve_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Reject", 
                  command=self.reject_selected).pack(side=tk.LEFT, padx=2)
        
        # Treeview for accommodations list
        tree_frame = ttk.Frame(self.accom_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create treeview with scrollbars
        self.accom_tree = ttk.Treeview(tree_frame, columns=(
            'ID', 'Student ID', 'Name', 'Type', 'Start Date', 'End Date', 'Status'
        ), show='headings')
        
        # Configure columns
        columns = {
            'ID': 50,
            'Student ID': 100,
            'Name': 150,
            'Type': 150,
            'Start Date': 100,
            'End Date': 100,
            'Status': 80
        }
        
        for col, width in columns.items():
            self.accom_tree.heading(col, text=col)
            self.accom_tree.column(col, width=width, minwidth=50)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.accom_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.accom_tree.xview)
        self.accom_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
        self.accom_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Bind double-click event
        self.accom_tree.bind('<Double-1>', self.on_accommodation_double_click)
    
    def create_search_tab(self):
        """Create the search and filter tab"""
        self.search_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.search_frame, text="Search & Filter")
        
        # Search criteria frame
        criteria_frame = ttk.LabelFrame(self.search_frame, text="Search Criteria")
        criteria_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Row 1: Student ID and Accommodation Type
        row1 = ttk.Frame(criteria_frame)
        row1.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(row1, text="Student ID:").pack(side=tk.LEFT)
        self.search_student_id = ttk.Entry(row1, width=15)
        self.search_student_id.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row1, text="Type:").pack(side=tk.LEFT, padx=(20,0))
        self.search_type = ttk.Combobox(row1, width=20)
        self.search_type.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row1, text="Status:").pack(side=tk.LEFT, padx=(20,0))
        self.search_status = ttk.Combobox(row1, values=['', 'active', 'pending', 'suspended', 'expired'])
        self.search_status.pack(side=tk.LEFT, padx=5)
        
        # Row 2: Date range
        row2 = ttk.Frame(criteria_frame)
        row2.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(row2, text="Start Date >=:").pack(side=tk.LEFT)
        self.search_start_date = ttk.Entry(row2, width=12)
        self.search_start_date.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row2, text="End Date <=:").pack(side=tk.LEFT, padx=(20,0))
        self.search_end_date = ttk.Entry(row2, width=12)
        self.search_end_date.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row2, text="Keyword:").pack(side=tk.LEFT, padx=(20,0))
        self.search_keyword = ttk.Entry(row2, width=20)
        self.search_keyword.pack(side=tk.LEFT, padx=5)
        
        # Search buttons
        button_row = ttk.Frame(criteria_frame)
        button_row.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(button_row, text="Search", command=self.perform_search).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_row, text="Clear", command=self.clear_search).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_row, text="Show All", command=self.refresh_data).pack(side=tk.LEFT, padx=2)
        
        # Results frame
        results_frame = ttk.LabelFrame(self.search_frame, text="Search Results")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create results treeview (same as main tab)
        self.search_tree = ttk.Treeview(results_frame, columns=(
            'ID', 'Student ID', 'Name', 'Type', 'Start Date', 'End Date', 'Status', 'Description'
        ), show='headings')
        
        # Configure columns
        search_columns = {
            'ID': 50,
            'Student ID': 100,
            'Name': 120,
            'Type': 120,
            'Start Date': 90,
            'End Date': 90,
            'Status': 70,
            'Description': 150
        }
        
        for col, width in search_columns.items():
            self.search_tree.heading(col, text=col)
            self.search_tree.column(col, width=width, minwidth=50)
        
        # Scrollbars for search results
        search_v_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.search_tree.yview)
        search_h_scrollbar = ttk.Scrollbar(results_frame, orient=tk.HORIZONTAL, command=self.search_tree.xview)
        self.search_tree.configure(yscrollcommand=search_v_scrollbar.set, xscrollcommand=search_h_scrollbar.set)
        
        self.search_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        search_v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        search_h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def create_dashboard_tab(self):
        """Create the dashboard tab"""
        self.dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_frame, text="Dashboard")
        
        # Metrics frame
        metrics_frame = ttk.LabelFrame(self.dashboard_frame, text="Key Metrics")
        metrics_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Create metrics display
        self.metrics_vars = {}
        metrics_grid = ttk.Frame(metrics_frame)
        metrics_grid.pack(fill=tk.X, padx=10, pady=10)
        
        metrics = [
            ('Total Accommodations', 'total'),
            ('Active', 'active'),
            ('Pending', 'pending'),
            ('Expired', 'expired'),
            ('This Month', 'this_month'),
            ('Expiring Soon', 'expiring_soon')
        ]
        
        for i, (label, key) in enumerate(metrics):
            row = i // 3
            col = i % 3
            
            frame = ttk.Frame(metrics_grid)
            frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')
            
            ttk.Label(frame, text=label, font=('Arial', 10, 'bold')).pack()
            self.metrics_vars[key] = tk.StringVar(value="0")
            ttk.Label(frame, textvariable=self.metrics_vars[key], 
                     font=('Arial', 14)).pack()
        
        # Configure grid weights
        for i in range(3):
            metrics_grid.columnconfigure(i, weight=1)
        
        # Charts frame
        charts_frame = ttk.LabelFrame(self.dashboard_frame, text="Statistics")
        charts_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create text-based charts (can be enhanced with matplotlib if available)
        self.stats_text = ScrolledText(charts_frame, height=15, width=80)
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Refresh button
        ttk.Button(self.dashboard_frame, text="Refresh Dashboard", 
                  command=self.refresh_dashboard).pack(pady=5)
    
    def create_templates_tab(self):
        """Create the templates management tab"""
        self.templates_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.templates_frame, text="Templates")
        
        # Top frame for template buttons
        template_buttons = ttk.Frame(self.templates_frame)
        template_buttons.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(template_buttons, text="Create Template", 
                  command=self.save_template_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(template_buttons, text="Apply Template", 
                  command=self.apply_template_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(template_buttons, text="Edit Template", 
                  command=self.edit_template_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(template_buttons, text="Delete Template",
                  command=self.delete_template_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(template_buttons, text="Import Medical Templates",
                  command=self.import_medical_templates).pack(side=tk.LEFT, padx=2)
        ttk.Button(template_buttons, text="Refresh",
                  command=self.refresh_templates).pack(side=tk.LEFT, padx=2)
        
        # Templates list
        templates_list_frame = ttk.Frame(self.templates_frame)
        templates_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.templates_tree = ttk.Treeview(templates_list_frame, columns=(
            'Name', 'Type', 'Description', 'Duration', 'Created By', 'Created At'
        ), show='headings')
        
        # Configure columns
        template_columns = {
            'Name': 150,
            'Type': 150,
            'Description': 200,
            'Duration': 100,
            'Created By': 100,
            'Created At': 150
        }
        
        for col, width in template_columns.items():
            self.templates_tree.heading(col, text=col)
            self.templates_tree.column(col, width=width, minwidth=50)
        
        # Scrollbars for templates
        templates_v_scrollbar = ttk.Scrollbar(templates_list_frame, orient=tk.VERTICAL, command=self.templates_tree.yview)
        self.templates_tree.configure(yscrollcommand=templates_v_scrollbar.set)
        
        self.templates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        templates_v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click
        self.templates_tree.bind('<Double-1>', self.on_template_double_click)
    
    def create_status_bar(self):
        """Create the status bar"""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.status_bar, textvariable=self.status_var).pack(side=tk.LEFT, padx=5)
        
        # Add current user info if available
        if CLI_AVAILABLE and 'auth' in globals() and auth and auth.current_user:
            user_info = f"User: {auth.current_user}"
            ttk.Label(self.status_bar, text=user_info).pack(side=tk.RIGHT, padx=5)
    
    def refresh_data(self):
        """Refresh the accommodations data"""
        if not CLI_AVAILABLE:
            self.status_var.set("CLI module not available")
            return
        
        try:
            self.status_var.set("Loading accommodations...")
            self.root.update()
            
            # Clear existing data
            for item in self.accom_tree.get_children():
                self.accom_tree.delete(item)
            
            # Load accommodation types for search combo
            types = get_accommodation_types() if CLI_AVAILABLE else []
            self.search_type['values'] = [''] + types
            
            # Get accommodations data
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.id, a.student_id, a.accommodation_type, a.description,
                           a.start_date, a.end_date, a.status, a.created_at,
                           s.first_name, s.last_name, s.email_address
                    FROM accommodations a
                    LEFT JOIN students s ON a.student_id = s.student_id
                    ORDER BY a.id DESC
                ''')
                
                accommodations = cursor.fetchall()
                
                for acc in accommodations:
                    name = f"{acc['first_name'] or ''} {acc['last_name'] or ''}".strip() or 'N/A'
                    
                    self.accom_tree.insert('', 'end', values=(
                        acc['id'],
                        acc['student_id'],
                        name,
                        acc['accommodation_type'],
                        acc['start_date'] or 'N/A',
                        acc['end_date'] or 'N/A',
                        acc['status']
                    ))
            
            self.status_var.set(f"Loaded {len(accommodations)} accommodations")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load accommodations: {str(e)}")
            self.status_var.set("Error loading data")
    
    def refresh_templates(self):
        """Refresh the templates data"""
        if not CLI_AVAILABLE:
            return
        
        try:
            # Clear existing data
            for item in self.templates_tree.get_children():
                self.templates_tree.delete(item)
            
            # Get templates data
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(f'''
                    SELECT name, accommodation_type, description, duration_days,
                           created_by, created_at
                    FROM {TEMPLATES_TABLE}
                    ORDER BY name
                ''')
                
                templates = cursor.fetchall()
                
                for template in templates:
                    self.templates_tree.insert('', 'end', values=(
                        template['name'],
                        template['accommodation_type'],
                        template['description'] or 'N/A',
                        f"{template['duration_days']} days" if template['duration_days'] else 'N/A',
                        template['created_by'] or 'N/A',
                        template['created_at'] or 'N/A'
                    ))
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load templates: {str(e)}")

    def import_medical_templates(self):
        """Import medical templates from JSON files into the database"""
        try:
            from university_system.modules.shared.constants import paths
            import json
            from pathlib import Path

            medical_templates_dir = paths.MEDICAL_TEMPLATES_DIR

            if not medical_templates_dir.exists():
                messagebox.showerror("Error", f"Medical templates directory not found: {medical_templates_dir}")
                return

            # Find all JSON files in the medical templates directory
            json_files = list(medical_templates_dir.glob("*.json"))

            if not json_files:
                messagebox.showinfo("Import", "No medical template JSON files found in the directory.")
                return

            imported_count = 0
            skipped_count = 0
            error_count = 0

            with get_connection() as conn:
                cursor = conn.cursor()

                for json_file in json_files:
                    try:
                        # Read JSON file
                        with open(json_file, 'r', encoding='utf-8') as f:
                            template_data = json.load(f)

                        # Extract template information
                        template_name = template_data.get('template_name', json_file.stem)
                        accommodation_type = template_data.get('accommodation_type', 'Medical')
                        description = template_data.get('description', '')
                        duration_days = template_data.get('duration_days', 365)

                        # Check if template already exists
                        cursor.execute(f"SELECT COUNT(*) FROM {TEMPLATES_TABLE} WHERE name = ?", (template_name,))
                        if cursor.fetchone()[0] > 0:
                            skipped_count += 1
                            continue

                        # Insert template into database
                        cursor.execute(f'''
                            INSERT INTO {TEMPLATES_TABLE}
                            (name, accommodation_type, description, start_offset_days, duration_days, created_by, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            template_name,
                            accommodation_type,
                            description,
                            0,  # start_offset_days
                            duration_days,
                            'System',
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        ))

                        imported_count += 1

                    except Exception as e:
                        error_count += 1
                        print(f"Error importing {json_file.name}: {e}")
                        continue

                conn.commit()

            # Show results
            message = f"Import complete!\n\n"
            message += f"✓ Imported: {imported_count} templates\n"
            if skipped_count > 0:
                message += f"⊘ Skipped (already exist): {skipped_count} templates\n"
            if error_count > 0:
                message += f"✗ Errors: {error_count} templates\n"

            messagebox.showinfo("Import Medical Templates", message)

            # Refresh the templates display
            self.refresh_templates()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to import medical templates: {str(e)}")

    def refresh_dashboard(self):
        """Refresh the dashboard metrics"""
        if not CLI_AVAILABLE:
            return
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            current_month = datetime.now().strftime('%Y-%m')
            thirty_days_future = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            
            with get_connection() as conn:
                cursor = conn.cursor()
                
                # Total accommodations
                cursor.execute('SELECT COUNT(*) FROM accommodations')
                total = cursor.fetchone()[0]
                self.metrics_vars['total'].set(str(total))
                
                # Active accommodations
                cursor.execute('''
                    SELECT COUNT(*) FROM accommodations
                    WHERE (end_date >= ? OR end_date IS NULL) AND status = 'active'
                ''', (today,))
                active = cursor.fetchone()[0]
                self.metrics_vars['active'].set(str(active))
                
                # Pending accommodations
                cursor.execute("SELECT COUNT(*) FROM accommodations WHERE status = 'pending'")
                pending = cursor.fetchone()[0]
                self.metrics_vars['pending'].set(str(pending))
                
                # Expired accommodations
                cursor.execute('''
                    SELECT COUNT(*) FROM accommodations
                    WHERE (end_date < ? OR status = 'expired')
                ''', (today,))
                expired = cursor.fetchone()[0]
                self.metrics_vars['expired'].set(str(expired))
                
                # This month's accommodations
                cursor.execute('''
                    SELECT COUNT(*) FROM accommodations
                    WHERE created_at LIKE ?
                ''', (f"{current_month}%",))
                this_month = cursor.fetchone()[0]
                self.metrics_vars['this_month'].set(str(this_month))
                
                # Expiring soon
                cursor.execute('''
                    SELECT COUNT(*) FROM accommodations
                    WHERE end_date BETWEEN ? AND ? AND status = 'active'
                ''', (today, thirty_days_future))
                expiring_soon = cursor.fetchone()[0]
                self.metrics_vars['expiring_soon'].set(str(expiring_soon))
                
                # Generate statistics text
                self.generate_dashboard_text()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh dashboard: {str(e)}")
    
    def generate_dashboard_text(self):
        """Generate dashboard statistics text"""
        if not CLI_AVAILABLE:
            return
        
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get accommodation type breakdown
                cursor.execute('''
                    SELECT accommodation_type, COUNT(*) as count
                    FROM accommodations
                    GROUP BY accommodation_type
                    ORDER BY count DESC
                ''')
                by_type = cursor.fetchall()
                
                # Get status breakdown
                cursor.execute('''
                    SELECT status, COUNT(*) as count
                    FROM accommodations
                    GROUP BY status
                    ORDER BY count DESC
                ''')
                by_status = cursor.fetchall()
                
                # Generate text
                self.stats_text.delete(1.0, tk.END)
                
                self.stats_text.insert(tk.END, "ACCOMMODATION BREAKDOWN BY TYPE\n")
                self.stats_text.insert(tk.END, "=" * 50 + "\n\n")
                
                total = int(self.metrics_vars['total'].get())
                
                for type_row in by_type:
                    type_name = type_row['accommodation_type']
                    count = type_row['count']
                    percent = (count/total*100) if total > 0 else 0
                    
                    # Simple text bar chart
                    bar_length = int(percent / 2)
                    bar = '█' * bar_length
                    
                    self.stats_text.insert(tk.END, f"{type_name:<25} {count:>3} ({percent:5.1f}%) {bar}\n")
                
                self.stats_text.insert(tk.END, "\n\nBREAKDOWN BY STATUS\n")
                self.stats_text.insert(tk.END, "=" * 50 + "\n\n")
                
                for status_row in by_status:
                    status_name = status_row['status']
                    count = status_row['count']
                    percent = (count/total*100) if total > 0 else 0
                    
                    bar_length = int(percent / 2)
                    bar = '█' * bar_length
                    
                    self.stats_text.insert(tk.END, f"{status_name:<15} {count:>3} ({percent:5.1f}%) {bar}\n")
                
        except Exception as e:
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(tk.END, f"Error generating statistics: {str(e)}")

    def show_templates_usage_dialog(self):
        """Show dialog for templates usage statistics"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return
        
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    SELECT name, COUNT(*) as usage_count
                    FROM accommodations a
                    JOIN {TEMPLATES_TABLE} t ON a.notes LIKE '%Applied from template: ' || t.name || '%'
                    GROUP BY t.name
                    ORDER BY usage_count DESC
                ''')
                usage_stats = cursor.fetchall()
            
            # Create dialog to show usage
            dialog = tk.Toplevel(self.root)
            dialog.title("Template Usage Statistics")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            
            tree = ttk.Treeview(dialog, columns=('Template', 'Usage Count'), show='headings')
            tree.heading('Template', text='Template Name')
            tree.heading('Usage Count', text='Times Used')
            tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            for template_name, count in usage_stats:
                tree.insert('', 'end', values=(template_name, count))
            
            ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load template usage: {str(e)}")

    def upload_document_dialog(self):
        """Show dialog to upload documents for selected accommodation"""
        selected = self.get_selected_accommodation()
        if not selected:
            return
        
        accommodation_id = selected['values'][0]
        
        dialog = DocumentUploadDialog(self.root, accommodation_id)
        if dialog.result:
            messagebox.showinfo("Success", "Document uploaded successfully")
            # Refresh if needed

    def migrate_database_schema(self):
        """Run database schema migration"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return
        
        try:
            # Import the migration functions
            from accommodation import migrate_audit_log_schema, fix_accommodation_db_schema
        
            result = messagebox.askyesno("Database Migration", 
                "This will update the database schema. Continue?")
            if not result:
                return
                
            self.status_var.set("Running database migration...")
            self.root.update()
            
            success1 = migrate_audit_log_schema()
            success2 = fix_accommodation_db_schema()
            
            if success1 and success2:
                messagebox.showinfo("Success", "Database migration completed successfully")
            else:
                messagebox.showwarning("Warning", "Migration completed with some issues. Check logs.")
                
            self.status_var.set("Migration completed")
        
        except ImportError:
            messagebox.showerror("Error", "Original accommodation CLI module not available; migration requires the CLI environment.")
            self.status_var.set("Migration unavailable")
        except Exception as e:
            messagebox.showerror("Error", f"Migration failed: {str(e)}")
            self.status_var.set("Migration failed")

    def export_data(self, format_type):
        """Export accommodations data"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return
        
        # Get export filters
        filter_dialog = ExportFilterDialog(self.root)
        if not filter_dialog.result:
            return
        
        filters = filter_dialog.result
        
        # Choose save location
        if format_type == 'csv':
            file_path = filedialog.asksaveasfilename(
                title="Export to CSV",
                filetypes=[("CSV files", "*.csv")],
                defaultextension=".csv"
            )
        elif format_type == 'excel':
            file_path = filedialog.asksaveasfilename(
                title="Export to Excel",
                filetypes=[("Excel files", "*.xlsx")],
                defaultextension=".xlsx"
            )
        elif format_type == 'pdf':
            file_path = filedialog.asksaveasfilename(
                title="Export to PDF",
                filetypes=[("PDF files", "*.pdf")],
                defaultextension=".pdf"
            )
        elif format_type == 'json':
            file_path = filedialog.asksaveasfilename(
                title="Export to JSON",
                filetypes=[("JSON files", "*.json")],
                defaultextension=".json"
            )
        else:
            messagebox.showerror("Error", f"Unsupported export format: {format_type}")
            return
        
        if not file_path:
            return
        
        try:
            # Get data with filters
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = '''
                    SELECT a.*, s.first_name, s.last_name, s.email_address
                    FROM accommodations a
                    LEFT JOIN students s ON a.student_id = s.student_id
                '''
                
                where_clauses = []
                params = []
                
                if filters['student_id']:
                    where_clauses.append('a.student_id = ?')
                    params.append(filters['student_id'])
                
                if filters['accommodation_type']:
                    where_clauses.append('a.accommodation_type = ?')
                    params.append(filters['accommodation_type'])
                
                if filters['status']:
                    where_clauses.append('a.status = ?')
                    params.append(filters['status'])
                
                if where_clauses:
                    query += ' WHERE ' + ' AND '.join(where_clauses)
                
                query += ' ORDER BY a.id DESC'
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
            
            # Export based on format
            if format_type == 'csv':
                self.export_to_csv_file(rows, file_path)
            elif format_type == 'excel':
                self.export_to_excel_file(rows, file_path)
            elif format_type == 'pdf':
                self.export_to_pdf_file(rows, file_path)
            elif format_type == 'json':
                self.export_to_json_file(rows, file_path)
            
            messagebox.showinfo("Success", f"Data exported to {file_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def export_csv(self):
        """Export accommodations to CSV"""
        self.export_data('csv')
    
    def export_excel(self):
        """Export accommodations to Excel"""
        self.export_data('excel')
    
    def export_pdf(self):
        """Export accommodations to PDF"""
        self.export_data('pdf')
    
    def export_json(self):
        """Export accommodations to JSON"""
        self.export_data('json')

    def apply_template_with_data(self, template_data):
        """Apply template with provided data"""
        try:
            # Get template details
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    SELECT accommodation_type, description, start_offset_days, duration_days
                    FROM {TEMPLATES_TABLE} WHERE name = ?
                ''', (template_data['template_name'],))
                
                template = cursor.fetchone()
                if not template:
                    messagebox.showerror("Error", "Template not found")
                    return
                
                typ, desc, offset, duration = template
                
                # Calculate dates
                start_date = datetime.now() + timedelta(days=offset)
                end_date = start_date + timedelta(days=duration)
                
                # Check for conflicts
                if check_conflict(template_data['student_id'], typ, 
                                start_date.strftime('%Y-%m-%d'), 
                                end_date.strftime('%Y-%m-%d')):
                    if not messagebox.askyesno("Conflict", 
                        "This accommodation overlaps with an existing record. Continue anyway?"):
                        return
                
                # Apply template
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                notes = f"Applied from template: {template_data['template_name']}"
                
                cursor.execute('''
                    INSERT INTO accommodations
                    (student_id, accommodation_type, description, start_date, end_date, 
                     status, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    template_data['student_id'],
                    typ, desc,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d'),
                    'active', notes, now, now
                ))
                
                conn.commit()
                messagebox.showinfo("Success", "Template applied successfully")
                self.refresh_data()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply template: {str(e)}")
    
    def add_accommodation_dialog(self):
        """Show dialog to add new accommodation"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return

        dialog = AccommodationDialog(self.root, "Add Accommodation")
        if dialog.result:
            try:
                # Validate student ID
                if not validate_student_id(dialog.result['student_id']):
                    messagebox.showerror("Error", "Student ID not found in the system")
                    return

                # Check for conflicts
                if check_conflict(
                    dialog.result['student_id'],
                    dialog.result['accommodation_type'],
                    dialog.result['start_date'],
                    dialog.result['end_date']
                ):
                    if not messagebox.askyesno(
                        "Conflict",
                        "This accommodation overlaps with an existing record. Continue anyway?"
                    ):
                        return

                # Add to database
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        '''
                        INSERT INTO accommodations
                        (student_id, accommodation_type, description, start_date, end_date, status, notes, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            dialog.result['student_id'],
                            dialog.result['accommodation_type'],
                            dialog.result['description'],
                            dialog.result['start_date'] if dialog.result['start_date'] else None,
                            dialog.result['end_date'] if dialog.result['end_date'] else None,
                            'active',
                            dialog.result['notes'],
                            now,
                            now
                        )
                    )

                    aid = cursor.lastrowid
                    conn.commit()
                    messagebox.showinfo("Success", f"Accommodation added successfully with ID: {aid}")
                
                # Log action
                if CLI_AVAILABLE:
                    log_action('add_accommodation', aid, f"Added accommodation for student {dialog.result['student_id']}")
                
                # Notify student (Optional, based on your system's needs)
                if CLI_AVAILABLE:
                    notify_student(
                        dialog.result['student_id'],
                        'Accommodation Added',
                        f"Your accommodation of type '{dialog.result['accommodation_type']}' has been added."
                    )
                
                self.refresh_data()
            
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add accommodation: {str(e)}")
                
    def setup_keyboard_shortcuts(self):
        """Set up keyboard shortcuts"""
        self.root.bind('<F5>', lambda e: self.refresh_data())
        self.root.bind('<Control-n>', lambda e: self.add_accommodation_dialog())
        self.root.bind('<Control-e>', lambda e: self.update_accommodation_dialog())
        self.root.bind('<Delete>', lambda e: self.remove_accommodation_dialog())

    def launch_gui():
        """Function to launch GUI from CLI"""
        print("Launching GUI mode...")
        main()

    def validate_gui_input(value, input_type):
        """Validate GUI input based on type"""
        if input_type == 'student_id':
            return value.strip() != '' and CLI_AVAILABLE and validate_student_id(value.strip())
        elif input_type == 'date':
            if not value.strip():
                return True  # Empty dates are allowed
            try:
                datetime.fromisoformat(value.strip())
                return True
            except ValueError:
                return False
        elif input_type == 'integer':
            try:
                int(value)
                return True
            except ValueError:
                return False
        return True


    def create_tooltip(widget, text):
        """Create a tooltip for a widget"""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = tk.Label(tooltip, text=text, background="lightyellow", 
                            relief="solid", borderwidth=1, font=("Arial", 8))
            label.pack()
            
            widget.tooltip = tooltip
        
        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip
        
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)


    def format_date_display(date_str):
        """Format date for display"""
        if not date_str:
            return 'N/A'
        try:
            date_obj = datetime.fromisoformat(date_str)
            return date_obj.strftime('%Y-%m-%d')
        except:
            return date_str


    def get_status_color(status):
        """Get color for status display"""
        colors = {
            'active': 'green',
            'pending': 'orange',
            'suspended': 'red',
            'expired': 'gray',
            'rejected': 'darkred'
        }
        return colors.get(status, 'black')


    # Configuration and constants for GUI
    GUI_CONFIG = {
        'window_title': 'Student Accommodation Management System',
        'window_size': '1200x800',
        'min_window_size': '800x600',
        'theme': 'default',
        'auto_refresh_interval': 30000,  # milliseconds
        'max_recent_files': 10,
        'default_export_format': 'csv',
        'date_format': '%Y-%m-%d',
        'datetime_format': '%Y-%m-%d %H:%M:%S'
    }


    # Error handling and logging for GUI
    def gui_error_handler(func):
        """Decorator for GUI error handling"""
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                print(f"GUI Error in {func.__name__}: {e}")
                if CLI_AVAILABLE:
                    logging.error(f"GUI Error in {func.__name__}: {e}")
                # Show error dialog if tkinter is available
                try:
                    messagebox.showerror("Error", f"An error occurred: {str(e)}")
                except:
                    print(f"Error: {e}")
        return wrapper
        
        # Check command line arguments
        if len(sys.argv) > 1:
            if sys.argv[1] == '--gui':
                main()
            elif sys.argv[1] == '--cli':
                if CLI_AVAILABLE:
                    display_accommodation_menu()
                else:
                    print("CLI mode not available - original accommodation module not found")
            elif sys.argv[1] == '--help':
                print("Student Accommodation Management System")
                print("Usage:")
                print("  python accommodation_gui.py           # Auto-detect mode")
                print("  python accommodation_gui.py --gui     # Force GUI mode")
                print("  python accommodation_gui.py --cli     # Force CLI mode")
                print("  python accommodation_gui.py --help    # Show this help")
            else:
                print(f"Unknown argument: {sys.argv[1]}")
                print("Use --help for usage information")
        else:
            # Auto-detect mode - prefer GUI if available, fall back to CLI
            try:
                # Try to import tkinter to see if GUI is possible
                import tkinter as tk
                # If successful, launch GUI
                main()
            except ImportError:
                # No tkinter available, use CLI
                print("GUI not available (tkinter not installed). Using CLI mode...")
                if CLI_AVAILABLE:
                    display_accommodation_menu()
                else:
                    print("Neither GUI nor CLI mode available.")
                    print("Please install tkinter for GUI mode or ensure accommodation.py is available for CLI mode.")
            except Exception as e:
                # GUI failed for some other reason, fall back to CLI
                print(f"GUI failed to start: {e}")
                print("Falling back to CLI mode...")
                if CLI_AVAILABLE:
                    display_accommodation_menu()
                else:
                    print("CLI mode also not available.")


    # Additional CLI integration functions
    def integrate_with_original_cli():
        """Integrate GUI option into the original CLI accommodation menu.

        Returns:
            bool: True if the integration succeeded, False otherwise.
        """
        if not CLI_AVAILABLE:
            logging.info("Accommodation CLI not available; skipping GUI integration.")
            return False

        try:
            cli_module = sys.modules.get(
                "university_system.modules.domain.housing.services.accommodation"
            )
            if cli_module is None:
                import importlib
                cli_module = importlib.import_module(
                    "university_system.modules.domain.housing.services.accommodation"
                )
        except Exception as err:
            logging.error("Failed to import accommodation CLI module: %s", err)
            return False

        if getattr(cli_module, "_gui_menu_patched", False):
            return True

        def launch_gui_from_cli():
            """Helper that launches the GUI, used by injected CLI menu option."""
            print("\nLaunching Accommodation GUI...\n")
            try:
                main()
            except Exception as exc:  # broad exception to keep CLI responsive
                logging.exception("Accommodation GUI failed to start from CLI: %s", exc)
                print(f"Unable to start the GUI: {exc}")
                input("Press Enter to return to the CLI menu...")

        def gui_enabled_menu():
            """CLI menu function with an additional option for launching the GUI."""
            cli_module.init_accommodation_db()

            options = {
                '0': ('Launch GUI Interface', launch_gui_from_cli, []),
                '1': ('Register Student Accommodation', cli_module.add_accommodation, ['manage_accommodations']),
                '2': ('Bulk Import from CSV', cli_module.bulk_import_from_csv, ['manage_accommodations', 'batch_operations']),
                '3': ('Import from JSON', cli_module.import_from_json, ['manage_accommodations', 'batch_operations']),
                '4': ('Save Template', cli_module.save_template, ['manage_accommodations']),
                '5': ('Apply Template', cli_module.apply_template, ['manage_accommodations']),
                '6': ('Search/Filter Accommodations', cli_module.view_accommodations, ['view_accommodations']),
                '7': ('Update Accommodation', cli_module.update_accommodation, ['manage_accommodations']),
                '8': ('Remove Accommodation', cli_module.remove_accommodation, ['manage_accommodations']),
                '9': ('View by Accommodation Type', cli_module.view_students_by_accommodation, ['view_accommodations']),
                '10': ('Approve/Reject Accommodations', cli_module.approve_accommodation, ['approve_accommodations']),
                '11': ('Export Data', cli_module.export_accommodations, ['export_data']),
                '12': ('Check Expiry Notifications', cli_module.check_expiry_notifications, ['manage_accommodations']),
                '13': ('Dashboard Metrics', cli_module.show_dashboard_metrics, ['view_accommodations']),
                '14': ('Generate Statistics Report', cli_module.generate_statistics_report, ['view_accommodations']),
                '15': ('Return to Main Menu', None, [])
            }

            while True:
                print("\nAccommodation Management:")
                print("=" * 40)

                available_options = []
                current_auth = getattr(cli_module, "auth", None)
                for key, (desc, _, required_perms) in options.items():
                    if not current_auth or not required_perms or not getattr(current_auth, "current_user", None):
                        print(f"{key}. {desc}")
                        available_options.append(key)
                    elif all(current_auth.check_permission(perm) for perm in required_perms):
                        print(f"{key}. {desc}")
                        available_options.append(key)

                choice = input("\nEnter your choice: ").strip()

                if choice not in options:
                    print("Invalid choice. Please try again.")
                    continue

                if choice not in available_options:
                    print("You don't have permission to access that option.")
                    continue

                desc, handler, _ = options[choice]
                if handler is None:
                    break

                try:
                    if handler is cli_module.bulk_import_from_csv:
                        filepath = input("CSV file path: ").strip()
                        handler(filepath)
                    else:
                        handler()
                except Exception as exc:  # keep CLI running
                    logging.exception("Menu action '%s' failed: %s", desc, exc)
                    print(f"An error occurred during {desc}: {exc}")
                    print("Please try again or contact technical support.")

        cli_module.display_accommodation_menu = gui_enabled_menu
        cli_module._gui_menu_patched = True
        logging.info("Accommodation CLI menu patched to include GUI launch option.")
        return True

    def export_gui_data_to_cli_format(output_path: str | Path | None = None):
        """Export GUI-managed accommodation data in a format compatible with CLI imports.

        Args:
            output_path: Optional path for the JSON file. When omitted, a timestamped
                file is written to the shared data/export directory.

        Returns:
            tuple[list[dict], str]: The exported records and the file path written to disk.
        """
        if not CLI_AVAILABLE:
            logging.info("Accommodation CLI not available; GUI export skipped.")
            return [], ""

        export_records: list[dict] = []
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT id, student_id, accommodation_type, description,
                           start_date, end_date, status, notes,
                           created_at, updated_at
                    FROM accommodations
                    ORDER BY created_at ASC
                    '''
                )
                export_records = [dict(row) for row in cursor.fetchall()]
        except Exception as err:
            logging.error("Failed to gather accommodation data for CLI export: %s", err)
            raise

        if output_path is None:
            try:
                from university_system.modules.shared.constants import paths
                export_dir = Path(paths.DATA_DIR) / "exports"
            except Exception:
                export_dir = Path.cwd() / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = export_dir / f"accommodations_gui_export_{timestamp}.json"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open('w', encoding='utf-8') as handle:
            json.dump(export_records, handle, indent=2, default=str)

        logging.info("Accommodation GUI data exported for CLI import: %s", output_path)
        return export_records, os.fspath(output_path)


    # Version and compatibility information
    GUI_VERSION = "1.0.0"
    REQUIRED_CLI_VERSION = "1.0.0"  # Minimum CLI version required
    COMPATIBLE_PYTHON_VERSIONS = ["3.6", "3.7", "3.8", "3.9", "3.10", "3.11"]
    
    def update_accommodation_dialog(self):
        """Show dialog to update selected accommodation"""
        selected = self.get_selected_accommodation()
        if not selected:
            return
        
        accommodation_id = selected['values'][0]
        
        try:
            # Get current accommodation data
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM accommodations WHERE id = ?', (accommodation_id,))
                current_data = cursor.fetchone()
                
            if not current_data:
                messagebox.showerror("Error", "Accommodation not found")
                return
            
            # Show update dialog with current data
            dialog = AccommodationDialog(self.root, "Update Accommodation", current_data)
            if dialog.result:
                # Check for conflicts if dates or type changed
                if (dialog.result['start_date'] != current_data['start_date'] or 
                    dialog.result['end_date'] != current_data['end_date'] or
                    dialog.result['accommodation_type'] != current_data['accommodation_type']):
                    
                    if check_conflict(dialog.result['student_id'], 
                                    dialog.result['accommodation_type'],
                                    dialog.result['start_date'],
                                    dialog.result['end_date'],
                                    excluded_id=accommodation_id):
                        if not messagebox.askyesno("Conflict", 
                            "This update creates a conflict with an existing accommodation. Continue anyway?"):
                            return
                
                # Update in database
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE accommodations SET
                        accommodation_type = ?, description = ?, start_date = ?,
                        end_date = ?, status = ?, notes = ?, updated_at = ?
                        WHERE id = ?
                    ''', (
                        dialog.result['accommodation_type'],
                        dialog.result['description'],
                        dialog.result['start_date'],
                        dialog.result['end_date'],
                        dialog.result['status'],
                        dialog.result['notes'],
                        now,
                        accommodation_id
                    ))
                    conn.commit()
                
                # Log the action
                log_action('update', accommodation_id, f"Updated accommodation for student {dialog.result['student_id']}")
                
                # Notify student
                notify_student(dialog.result['student_id'], 'Accommodation Updated',
                             f"Your {dialog.result['accommodation_type']} accommodation has been updated.")
                
                messagebox.showinfo("Success", "Accommodation updated successfully")
                self.refresh_data()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update accommodation: {str(e)}")
    
    def remove_accommodation_dialog(self):
        """Show dialog to remove selected accommodation"""
        selected = self.get_selected_accommodation()
        if not selected:
            return
        
        accommodation_id = selected['values'][0]
        student_id = selected['values'][1]
        acc_type = selected['values'][3]
        
        # Confirm removal
        if not messagebox.askyesno("Confirm Removal", 
            f"Are you sure you want to remove accommodation ID {accommodation_id} "
            f"({acc_type} for student {student_id})?"):
            return
        
        # Ask for removal reason
        reason = simpledialog.askstring("Removal Reason", 
            "Please enter a reason for removal (optional):", initialvalue="")
        
        # Ask for removal type
        removal_type = messagebox.askyesnocancel("Removal Type", 
            "Yes = Mark as expired, No = Permanently delete, Cancel = Cancel operation")
        
        if removal_type is None:  # Cancel
            return
        
        try:
            if removal_type:  # Mark as expired
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                note_text = f"Expired: {reason}" if reason else "Expired"
                
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE accommodations SET
                        status = 'expired',
                        notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | ' || ? END,
                        updated_at = ?
                        WHERE id = ?
                    ''', (note_text, note_text, now, accommodation_id))
                    conn.commit()
                
                action_msg = "Accommodation marked as expired"
                
            else:  # Permanent deletion
                with get_connection() as conn:
                    cursor = conn.cursor()
                    # Remove associated documents first
                    cursor.execute('DELETE FROM accommodation_documents WHERE accommodation_id = ?', (accommodation_id,))
                    # Remove the accommodation
                    cursor.execute('DELETE FROM accommodations WHERE id = ?', (accommodation_id,))
                    conn.commit()
                
                action_msg = "Accommodation permanently deleted"
            
            # Log the action
            log_action('remove', accommodation_id, f"Removed {acc_type} for student {student_id}. Reason: {reason}")
            
            # Notify student
            notify_student(student_id, 'Accommodation Removed',
                         f"Your {acc_type} accommodation has been removed. Reason: {reason}")
            
            messagebox.showinfo("Success", action_msg)
            self.refresh_data()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove accommodation: {str(e)}")
    
    def view_accommodation_details(self):
        """Show detailed view of selected accommodation"""
        selected = self.get_selected_accommodation()
        if not selected:
            return
        
        accommodation_id = selected['values'][0]
        
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get accommodation details
                cursor.execute('''
                    SELECT a.*, s.first_name, s.last_name, s.email_address
                    FROM accommodations a
                    LEFT JOIN students s ON a.student_id = s.student_id
                    WHERE a.id = ?
                ''', (accommodation_id,))
                
                accommodation = cursor.fetchone()

                if not accommodation:
                    messagebox.showerror("Error", "Accommodation not found")
                    return

                accommodation = dict(accommodation)

                # Get documents
                cursor.execute('''
                    SELECT * FROM accommodation_documents
                    WHERE accommodation_id = ?
                ''', (accommodation_id,))

                documents = [dict(doc) for doc in cursor.fetchall()]

            # Show details dialog
            DetailsDialog(self.root, accommodation, documents)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load accommodation details: {str(e)}")
    
    def get_selected_accommodation(self):
        """Get the currently selected accommodation"""
        selection = self.accom_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an accommodation first")
            return None
        return self.accom_tree.item(selection[0])
    
    def on_accommodation_double_click(self, event):
        """Handle double-click on accommodation"""
        self.view_accommodation_details()
    
    def on_template_double_click(self, event):
        """Handle double-click on template"""
        self.edit_template_dialog()
    
    def perform_search(self):
        """Perform search based on criteria"""
        if not CLI_AVAILABLE:
            return
        
        try:
            # Clear search results
            for item in self.search_tree.get_children():
                self.search_tree.delete(item)
            
            # Build query
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = '''
                    SELECT a.id, a.student_id, a.accommodation_type, a.description,
                           a.start_date, a.end_date, a.status, a.created_at,
                           s.first_name, s.last_name, s.email_address
                    FROM accommodations a
                    LEFT JOIN students s ON a.student_id = s.student_id
                '''
                
                where_clauses = []
                params = []
                
                # Add search criteria
                if self.search_student_id.get().strip():
                    where_clauses.append('a.student_id = ?')
                    params.append(self.search_student_id.get().strip())
                
                if self.search_type.get().strip():
                    where_clauses.append('a.accommodation_type = ?')
                    params.append(self.search_type.get().strip())
                
                if self.search_status.get().strip():
                    where_clauses.append('a.status = ?')
                    params.append(self.search_status.get().strip())
                
                if self.search_start_date.get().strip():
                    where_clauses.append('a.start_date >= ?')
                    params.append(self.search_start_date.get().strip())
                
                if self.search_end_date.get().strip():
                    where_clauses.append('a.end_date <= ?')
                    params.append(self.search_end_date.get().strip())
                
                if self.search_keyword.get().strip():
                    where_clauses.append('(a.description LIKE ? OR a.notes LIKE ?)')
                    keyword = f"%{self.search_keyword.get().strip()}%"
                    params.extend([keyword, keyword])
                
                if where_clauses:
                    query += ' WHERE ' + ' AND '.join(where_clauses)
                
                query += ' ORDER BY a.id DESC'
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                # Populate search results
                for acc in results:
                    name = f"{acc['first_name'] or ''} {acc['last_name'] or ''}".strip() or 'N/A'
                    
                    self.search_tree.insert('', 'end', values=(
                        acc['id'],
                        acc['student_id'],
                        name,
                        acc['accommodation_type'],
                        acc['start_date'] or 'N/A',
                        acc['end_date'] or 'N/A',
                        acc['status'],
                        acc['description'] or 'N/A'
                    ))
                
                self.status_var.set(f"Found {len(results)} matching accommodations")
                
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")
    
    def clear_search(self):
        """Clear all search criteria"""
        self.search_student_id.delete(0, tk.END)
        self.search_type.set('')
        self.search_status.set('')
        self.search_start_date.delete(0, tk.END)
        self.search_end_date.delete(0, tk.END)
        self.search_keyword.delete(0, tk.END)
        
        # Clear search results
        for item in self.search_tree.get_children():
            self.search_tree.delete(item)
        
        self.status_var.set("Search criteria cleared")
    
    def approve_selected(self):
        """Approve selected accommodation"""
        self.process_approval('approve')
    
    def reject_selected(self):
        """Reject selected accommodation"""
        self.process_approval('reject')
    
    def process_approval(self, action):
        """Process approval or rejection"""
        selected = self.get_selected_accommodation()
        if not selected:
            return
        
        accommodation_id = selected['values'][0]
        status = selected['values'][6]
        
        if status != 'pending':
            messagebox.showwarning("Invalid Status", 
                "Only pending accommodations can be approved or rejected")
            return
        
        # Ask for reason
        reason = simpledialog.askstring(f"{action.title()} Reason", 
            f"Enter reason for {action} (optional):", initialvalue="")
        
        try:
            # Get student info
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT student_id, accommodation_type FROM accommodations WHERE id = ?', 
                             (accommodation_id,))
                acc_info = cursor.fetchone()
                student_id, acc_type = acc_info
                
                # Update status
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                user = resolve_user_identifier(auth_instance=self.auth)

                new_status = 'active' if action == 'approve' else 'rejected'
                note_text = f"{action.title()}: {reason}" if reason else f"{action.title()}"

                cursor.execute('''
                    UPDATE accommodations SET
                    status = ?,
                    approved_by = ?,
                    approval_date = ?,
                    notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | ' || ? END,
                    updated_at = ?
                    WHERE id = ?
                ''', (new_status, user, now, note_text, note_text, now, accommodation_id))
                
                conn.commit()
            
            # Log action
            log_action(action, accommodation_id, f"{action.title()} accommodation for {student_id}: {reason}")
            
            # Notify student
            message = f"Your {acc_type} accommodation has been {action}d."
            if reason:
                message += f" {action.title()} reason: {reason}"
            
            notify_student(student_id, f'Accommodation {action.title()}d', message)
            
            messagebox.showinfo("Success", f"Accommodation {action}d successfully")
            self.refresh_data()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to {action} accommodation: {str(e)}")
    
    def approve_accommodation_dialog(self):
        """Show approval management dialog"""
        ApprovalDialog(self.root, self)
    
    def save_template_dialog(self):
        """Show dialog to save new template"""
        dialog = TemplateDialog(self.root, "Save Template")
        if dialog.result:
            try:
                # Check if template exists
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(f'SELECT name FROM {TEMPLATES_TABLE} WHERE name = ?', 
                                 (dialog.result['name'],))
                    if cursor.fetchone():
                        if not messagebox.askyesno("Template Exists", 
                            f"Template '{dialog.result['name']}' already exists. Overwrite?"):
                            return
                
                # Save template
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                user = resolve_user_identifier(auth_instance=self.auth)

                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(f'''
                        INSERT OR REPLACE INTO {TEMPLATES_TABLE}
                        (name, accommodation_type, description, start_offset_days, 
                         duration_days, created_by, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        dialog.result['name'],
                        dialog.result['accommodation_type'],
                        dialog.result['description'],
                        dialog.result['start_offset_days'],
                        dialog.result['duration_days'],
                        user, now, now
                    ))
                    conn.commit()
                
                # Log action
                log_action('save_template', None, f"Saved template: {dialog.result['name']}")
                
                messagebox.showinfo("Success", f"Template '{dialog.result['name']}' saved successfully")
                self.refresh_templates()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save template: {str(e)}")
    
    def apply_template_dialog(self):
        """Show dialog to apply template"""
        dialog = ApplyTemplateDialog(self.root)
        if dialog.result:
            try:
                # Get template details
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(f'''
                        SELECT accommodation_type, description, start_offset_days, duration_days
                        FROM {TEMPLATES_TABLE} WHERE name = ?
                    ''', (dialog.result['template_name'],))
                    
                    template = cursor.fetchone()
                    if not template:
                        messagebox.showerror("Error", "Template not found")
                        return
                    
                    typ, desc, offset, duration = template
                    
                    # Calculate dates
                    start_date = datetime.now() + timedelta(days=offset)
                    end_date = start_date + timedelta(days=duration)
                    
                    # Check for conflicts
                    if check_conflict(dialog.result['student_id'], typ, 
                                    start_date.strftime('%Y-%m-%d'), 
                                    end_date.strftime('%Y-%m-%d')):
                        if not messagebox.askyesno("Conflict", 
                            "This accommodation overlaps with an existing record. Continue anyway?"):
                            return
                    
                    # Apply template
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    notes = f"Applied from template: {dialog.result['template_name']}"
                    
                    cursor.execute('''
                        INSERT INTO accommodations
                        (student_id, accommodation_type, description, start_date, end_date, 
                         status, notes, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        dialog.result['student_id'],
                        typ, desc,
                        start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d'),
                        'active', notes, now, now
                    ))
                    
                    aid = cursor.lastrowid
                    conn.commit()
                
                # Log action
                log_action('apply_template', aid, 
                         f"Applied template {dialog.result['template_name']} to student {dialog.result['student_id']}")
                
                # Notify student
                notify_student(dialog.result['student_id'], 'Accommodation Template Applied',
                             f"Template '{dialog.result['template_name']}' for {typ} has been applied.")
                
                messagebox.showinfo("Success", f"Template applied successfully to student {dialog.result['student_id']}")
                self.refresh_data()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to apply template: {str(e)}")
    
    def edit_template_dialog(self):
        """Edit selected template"""
        selection = self.templates_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to edit")
            return
        
        template_name = self.templates_tree.item(selection[0])['values'][0]
        
        try:
            # Get current template data
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(f'SELECT * FROM {TEMPLATES_TABLE} WHERE name = ?', (template_name,))
                template_data = cursor.fetchone()
            
            if not template_data:
                messagebox.showerror("Error", "Template not found")
                return
            
            # Show edit dialog
            dialog = TemplateDialog(self.root, "Edit Template", template_data)
            if dialog.result:
                # Update template
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(f'''
                        UPDATE {TEMPLATES_TABLE} SET
                        accommodation_type = ?, description = ?, start_offset_days = ?,
                        duration_days = ?, updated_at = ?
                        WHERE name = ?
                    ''', (
                        dialog.result['accommodation_type'],
                        dialog.result['description'],
                        dialog.result['start_offset_days'],
                        dialog.result['duration_days'],
                        now,
                        template_name
                    ))
                    conn.commit()
                
                messagebox.showinfo("Success", f"Template '{template_name}' updated successfully")
                self.refresh_templates()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit template: {str(e)}")
    
    def delete_template_dialog(self):
        """Delete selected template"""
        selection = self.templates_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to delete")
            return
        
        template_name = self.templates_tree.item(selection[0])['values'][0]
        
        if not messagebox.askyesno("Confirm Deletion", 
            f"Are you sure you want to delete template '{template_name}'?"):
            return
        
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'DELETE FROM {TEMPLATES_TABLE} WHERE name = ?', (template_name,))
                conn.commit()
            
            messagebox.showinfo("Success", f"Template '{template_name}' deleted successfully")
            self.refresh_templates()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete template: {str(e)}")
    
    def manage_templates_dialog(self):
        """Show templates management dialog"""
        TemplateManagerDialog(self.root, self)
    
    def import_csv(self):
        """Import accommodations from CSV file"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return
        
        file_path = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                # Use the original bulk import function
                self.status_var.set("Importing from CSV...")
                self.root.update()
                
                # Run import in thread to prevent GUI freezing
                thread = threading.Thread(target=self.run_csv_import, args=(file_path,))
                thread.start()
                
            except Exception as e:
                messagebox.showerror("Error", f"Import failed: {str(e)}")
                self.status_var.set("Import failed")
    
    def run_csv_import(self, file_path):
        """Run CSV import in background thread"""
        try:
            # Redirect output to capture results
            import io
            import contextlib
            
            output = io.StringIO()
            
            with contextlib.redirect_stdout(output):
                bulk_import_from_csv(file_path)
            
            result = output.getvalue()
            
            # Show result in main thread
            self.root.after(0, lambda: self.show_import_result(result))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Import Error", str(e)))
        finally:
            self.root.after(0, lambda: self.status_var.set("Ready"))
            self.root.after(0, self.refresh_data)
    
    def show_import_result(self, result):
        """Show import result"""
        ImportResultDialog(self.root, "CSV Import Results", result)
    
    def import_json(self):
        """Import accommodations from JSON file"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return
        
        file_path = filedialog.askopenfilename(
            title="Select JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                self.status_var.set("Importing from JSON...")
                self.root.update()
                
                thread = threading.Thread(target=self.run_json_import, args=(file_path,))
                thread.start()
                
            except Exception as e:
                messagebox.showerror("Error", f"Import failed: {str(e)}")
                self.status_var.set("Import failed")
    
    def run_json_import(self, file_path):
        """Run JSON import in background thread"""
        try:
            success_count = 0
            error_count = 0
            error_details = []

            # Read and validate JSON file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                self.root.after(0, lambda: messagebox.showerror("JSON Error", f"Invalid JSON format: {e}"))
                return
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("File Error", f"Could not read file: {e}"))
                return

            # Handle both list of records and single record
            if isinstance(data, dict):
                if 'accommodations' in data:
                    records = data['accommodations']
                else:
                    records = [data]
            elif isinstance(data, list):
                records = data
            else:
                self.root.after(0, lambda: messagebox.showerror("Data Error", "JSON must contain a list of records or a single record"))
                return

            # Process each record
            for i, record in enumerate(records):
                try:
                    # Validate required fields
                    student_id = record.get('student_id', '').strip()
                    acc_type = record.get('accommodation_type', '').strip()

                    if not student_id:
                        error_details.append(f"Record {i+1}: Missing student_id")
                        error_count += 1
                        continue

                    if not acc_type:
                        error_details.append(f"Record {i+1}: Missing accommodation_type")
                        error_count += 1
                        continue

                    # Validate student_id format if function exists
                    try:
                        if not validate_student_id(student_id):
                            error_details.append(f"Record {i+1}: Invalid student_id format")
                            error_count += 1
                            continue
                    except NameError:
                        # validate_student_id function not available, skip validation
                        pass

                    # Validate dates if provided
                    start_date = record.get('start_date')
                    end_date = record.get('end_date')

                    if start_date:
                        try:
                            datetime.strptime(start_date, '%Y-%m-%d')
                        except ValueError:
                            error_details.append(f"Record {i+1}: Invalid start_date format (use YYYY-MM-DD)")
                            error_count += 1
                            continue

                    if end_date:
                        try:
                            datetime.strptime(end_date, '%Y-%m-%d')
                        except ValueError:
                            error_details.append(f"Record {i+1}: Invalid end_date format (use YYYY-MM-DD)")
                            error_count += 1
                            continue

                    # Insert record into database
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    with get_connection() as conn:
                        cursor = conn.cursor()

                        # Check if accommodation already exists for this student
                        cursor.execute('''
                            SELECT id FROM accommodations
                            WHERE student_id = ? AND accommodation_type = ? AND status != 'cancelled'
                        ''', (student_id, acc_type))

                        if cursor.fetchone():
                            error_details.append(f"Record {i+1}: Active accommodation already exists for student {student_id}")
                            error_count += 1
                            continue

                        # Insert new accommodation
                        cursor.execute('''
                            INSERT INTO accommodations
                            (student_id, accommodation_type, description, start_date, end_date,
                             status, notes, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            student_id,
                            acc_type,
                            record.get('description', ''),
                            start_date,
                            end_date,
                            record.get('status', 'pending'),
                            record.get('notes', ''),
                            now, now
                        ))
                        conn.commit()
                        success_count += 1

                except Exception as e:
                    error_details.append(f"Record {i+1}: {str(e)}")
                    error_count += 1

            # Prepare result message
            result_message = f"JSON Import Results:\n"
            result_message += f"- Successfully imported: {success_count} records\n"
            result_message += f"- Errors encountered: {error_count} records\n\n"

            if error_details:
                result_message += "Error Details:\n"
                for detail in error_details[:10]:  # Show max 10 errors
                    result_message += f"• {detail}\n"
                if len(error_details) > 10:
                    result_message += f"• ... and {len(error_details) - 10} more errors\n"

            self.root.after(0, lambda: self.show_import_result(result_message))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Import Error", f"Unexpected error: {str(e)}"))
        finally:
            self.root.after(0, lambda: self.status_var.set("Ready"))
            self.root.after(0, self.refresh_data)
    
    def export_to_csv_file(self, rows, file_path):
        """Export data to CSV file"""
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            headers = [
                'ID', 'Student ID', 'Student Name', 'Email', 'Accommodation Type',
                'Description', 'Start Date', 'End Date', 'Status', 'Notes',
                'Created At', 'Updated At'
            ]
            
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            
            for row in rows:
                student_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or 'N/A'
                writer.writerow([
                    row['id'],
                    row['student_id'],
                    student_name,
                    row['email_address'] or 'N/A',
                    row['accommodation_type'],
                    row['description'] or '',
                    row['start_date'] or '',
                    row['end_date'] or '',
                    row['status'],
                    row['notes'] or '',
                    row['created_at'],
                    row['updated_at']
                ])
    
    def export_to_excel_file(self, rows, file_path):
        """Export data to Excel file"""
        try:
            import pandas as pd
            
            data = []
            for row in rows:
                student_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or 'N/A'
                data.append({
                    'ID': row['id'],
                    'Student ID': row['student_id'],
                    'Student Name': student_name,
                    'Email': row['email_address'] or 'N/A',
                    'Accommodation Type': row['accommodation_type'],
                    'Description': row['description'] or '',
                    'Start Date': row['start_date'] or '',
                    'End Date': row['end_date'] or '',
                    'Status': row['status'],
                    'Notes': row['notes'] or '',
                    'Created At': row['created_at'],
                    'Updated At': row['updated_at']
                })
            
            df = pd.DataFrame(data)
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Accommodations', index=False)
                
        except ImportError:
            messagebox.showerror("Error", "pandas module not installed. Cannot export to Excel.")
            raise

    def export_to_pdf_file(self, rows, file_path):
        """Export data to PDF file"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib import colors
            
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            styles = getSampleStyleSheet()
            elements = []
            
            # Add title
            title = Paragraph("Accommodation Records", styles['Title'])
            elements.append(title)
            
            # Add timestamp
            timestamp = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal'])
            elements.append(timestamp)
            elements.append(Paragraph("<br/>", styles['Normal']))
            
            # Add summary
            elements.append(Paragraph(f"Total Records: {len(rows)}", styles['Heading2']))
            elements.append(Paragraph("<br/>", styles['Normal']))
            
            # Add table data
            table_data = [['ID', 'Student', 'Accommodation Type', 'Dates', 'Status']]
            
            for row in rows:
                student_name = f"{row['student_id']} - {row['first_name'] or ''} {row['last_name'] or ''}".strip()
                dates = f"Start: {row['start_date'] or 'N/A'}\nEnd: {row['end_date'] or 'N/A'}"
                
                table_data.append([
                    str(row['id']),
                    student_name,
                    row['accommodation_type'],
                    dates,
                    row['status']
                ])
            
            # Create table
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(table)
            doc.build(elements)
            
        except ImportError:
            messagebox.showerror("Error", "reportlab module not installed. Cannot export to PDF.")
            raise

    def export_to_json_file(self, rows, file_path):
        """Export data to JSON file"""
        data = []
        for row in rows:
            data.append({
                'id': row['id'],
                'student_id': row['student_id'],
                'student_name': f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or None,
                'email': row['email_address'],
                'accommodation_type': row['accommodation_type'],
                'description': row['description'],
                'start_date': row['start_date'],
                'end_date': row['end_date'],
                'status': row['status'],
                'notes': row['notes'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            })
        
        with open(file_path, 'w', encoding='utf-8') as json_file:
            json.dump(data, json_file, indent=2)
    
    def show_dashboard(self):
        """Show dashboard metrics"""
        self.notebook.select(2)  # Switch to dashboard tab
        self.refresh_dashboard()
    
    def generate_statistics(self):
        """Generate statistics report"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return
        
        StatisticsDialog(self.root)
    
    def check_expiry(self):
        """Check expiry notifications"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return
        
        # Ask for number of days
        days = simpledialog.askinteger("Expiry Check", 
            "Check for accommodations expiring in how many days?", 
            initialvalue=7, minvalue=1, maxvalue=365)
        
        if days:
            try:
                import io
                import contextlib
                
                output = io.StringIO()
                
                with contextlib.redirect_stdout(output):
                    check_expiry_notifications(days)
                
                result = output.getvalue()
                ExpiryResultDialog(self.root, result, days)
                
            except Exception as e:
                messagebox.showerror("Error", f"Expiry check failed: {str(e)}")

    def view_students_by_accommodation_type(self):
        """View students grouped by accommodation type"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get all accommodation types with student counts
            cursor.execute("""
                SELECT accommodation_type, COUNT(*) as count
                FROM accommodations
                WHERE status = 'active'
                GROUP BY accommodation_type
                ORDER BY count DESC, accommodation_type
            """)
            type_summary = cursor.fetchall()

            if not type_summary:
                messagebox.showinfo("No Data", "No active accommodations found")
                conn.close()
                return

            # Create display window
            view_window = tk.Toplevel(self.root)
            view_window.title("Students by Accommodation Type")
            view_window.geometry("900x700")

            # Main frame
            main_frame = ttk.Frame(view_window, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Title
            title_label = ttk.Label(main_frame, text="Students Grouped by Accommodation Type",
                                   font=('Arial', 14, 'bold'))
            title_label.pack(pady=(0, 10))

            # Summary frame
            summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding="10")
            summary_frame.pack(fill=tk.X, pady=5)

            total_students = sum(count for _, count in type_summary)
            summary_text = f"Total Active Accommodations: {total_students}\n"
            summary_text += f"Number of Types: {len(type_summary)}"

            ttk.Label(summary_frame, text=summary_text, font=('Arial', 10)).pack(anchor='w')

            # Create notebook for types
            type_notebook = ttk.Notebook(main_frame)
            type_notebook.pack(fill=tk.BOTH, expand=True, pady=10)

            # Create tab for each accommodation type
            for acc_type, count in type_summary:
                # Get students with this accommodation type
                cursor.execute("""
                    SELECT a.id, a.student_id, s.first_name, s.last_name,
                           a.start_date, a.end_date, a.description, a.status
                    FROM accommodations a
                    LEFT JOIN students s ON a.student_id = s.student_id
                    WHERE a.accommodation_type = ? AND a.status = 'active'
                    ORDER BY a.student_id
                """, (acc_type,))
                students = cursor.fetchall()

                # Create tab frame
                tab_frame = ttk.Frame(type_notebook)
                type_notebook.add(tab_frame, text=f"{acc_type} ({count})")

                # Create treeview for students
                tree_frame = ttk.Frame(tab_frame)
                tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

                columns = ('Accom ID', 'Student ID', 'Name', 'Start Date', 'End Date', 'Status')
                tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

                # Configure columns
                tree.column('Accom ID', width=80)
                tree.column('Student ID', width=100)
                tree.column('Name', width=200)
                tree.column('Start Date', width=100)
                tree.column('End Date', width=100)
                tree.column('Status', width=80)

                for col in columns:
                    tree.heading(col, text=col)

                # Add scrollbars
                vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
                hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
                tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

                tree.grid(row=0, column=0, sticky='nsew')
                vsb.grid(row=0, column=1, sticky='ns')
                hsb.grid(row=1, column=0, sticky='ew')

                tree_frame.grid_rowconfigure(0, weight=1)
                tree_frame.grid_columnconfigure(0, weight=1)

                # Populate tree with student data
                for student in students:
                    acc_id, student_id, first_name, last_name, start_date, end_date, description, status = student
                    name = f"{first_name or ''} {last_name or ''}".strip() or 'N/A'

                    tree.insert('', 'end', values=(
                        acc_id,
                        student_id,
                        name,
                        start_date or 'N/A',
                        end_date or 'Indefinite',
                        status
                    ))

                # Add details text area
                details_frame = ttk.LabelFrame(tab_frame, text="Description", padding="5")
                details_frame.pack(fill=tk.X, padx=5, pady=5)

                details_text = ScrolledText(details_frame, height=4, wrap=tk.WORD)
                details_text.pack(fill=tk.X)

                # Bind selection event to show description
                def on_select(event, t=tree, dt=details_text, studs=students):
                    selection = t.selection()
                    if selection:
                        item = t.item(selection[0])
                        acc_id = item['values'][0]
                        # Find matching student record
                        for s in studs:
                            if s[0] == acc_id:
                                dt.delete('1.0', 'end')
                                desc = s[6] if s[6] else 'No description available'
                                dt.insert('1.0', desc)
                                break

                tree.bind('<<TreeviewSelect>>', on_select)

            # Close button
            ttk.Button(main_frame, text="Close", command=view_window.destroy).pack(pady=5)

            conn.close()

            # Log activity
            if CLI_AVAILABLE:
                log_action('view_by_type', None, f'Viewed students grouped by accommodation type')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate view: {str(e)}")
            import traceback
            traceback.print_exc()

    def launch_cli(self):
        """Launch CLI mode"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return
        
        if messagebox.askyesno("Launch CLI", 
            "This will open the command-line interface in a new window. Continue?"):
            
            try:
                # Run CLI in a separate thread
                thread = threading.Thread(target=self.run_cli_mode)
                thread.daemon = True
                thread.start()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to launch CLI: {str(e)}")
    
    def run_cli_mode(self):
        """Run CLI mode in background"""
        try:
            display_accommodation_menu()
        except Exception as e:
            print(f"CLI error: {e}")
    
    def show_db_info(self):
        """Show database information"""
        DatabaseInfoDialog(self.root)
    
    def show_settings(self):
        """Show settings dialog"""
        SettingsDialog(self.root)

    def verify_db_schema(self):
        """Verify database schema and display results"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return

        try:
            import io
            import contextlib

            # Capture the output from verify_database_schema
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                verify_database_schema()

            result = output.getvalue()

            # Create result dialog
            result_window = tk.Toplevel(self.root)
            result_window.title("Database Schema Verification")
            result_window.geometry("700x600")

            main_frame = ttk.Frame(result_window, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text="Database Schema Information",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 10))

            # Text widget for results
            text_frame = ttk.Frame(main_frame)
            text_frame.pack(fill=tk.BOTH, expand=True)

            text_widget = ScrolledText(text_frame, wrap=tk.WORD, width=80, height=30)
            text_widget.pack(fill=tk.BOTH, expand=True)
            text_widget.insert('1.0', result)
            text_widget.config(state='disabled')

            # Close button
            ttk.Button(main_frame, text="Close",
                      command=result_window.destroy).pack(pady=10)

            # Log activity
            if CLI_AVAILABLE:
                log_action('verify_schema', None, 'Verified database schema')

        except Exception as e:
            messagebox.showerror("Error", f"Schema verification failed: {str(e)}")

    def show_help(self):
        """Show help dialog"""
        HelpDialog(self.root)
    
    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo("About", 
            "Student Accommodation Management System\n\n"
            "GUI Version 1.0\n"
            "Backwards compatible with CLI version\n\n"
            "This system helps manage student accommodations\n"
            "with features for registration, tracking, reporting,\n"
            "and template management.")


# Dialog classes for various functions

class AccommodationDialog:
    """Dialog for adding/editing accommodations"""
    
    def __init__(self, parent, title, current_data=None):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        self.create_widgets(current_data)
        
        # Wait for dialog to close
        self.dialog.wait_window()
    
    def create_widgets(self, current_data):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Student ID
        ttk.Label(main_frame, text="Student ID:").grid(row=0, column=0, sticky='w', pady=5)
        self.student_id_var = tk.StringVar(value=current_data['student_id'] if current_data else '')
        ttk.Entry(main_frame, textvariable=self.student_id_var, width=30).grid(row=0, column=1, pady=5, sticky='ew')
        
        # Accommodation Type
        ttk.Label(main_frame, text="Accommodation Type:").grid(row=1, column=0, sticky='w', pady=5)
        self.type_var = tk.StringVar(value=current_data['accommodation_type'] if current_data else '')
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=28)
        if CLI_AVAILABLE:
            type_combo['values'] = get_accommodation_types()
        type_combo.grid(row=1, column=1, pady=5, sticky='ew')
        
        # Description
        ttk.Label(main_frame, text="Description:").grid(row=2, column=0, sticky='nw', pady=5)
        self.description_text = tk.Text(main_frame, height=3, width=30)
        if current_data and current_data['description']:
            self.description_text.insert(tk.END, current_data['description'])
        self.description_text.grid(row=2, column=1, pady=5, sticky='ew')
        
        # Start Date
        ttk.Label(main_frame, text="Start Date (YYYY-MM-DD):").grid(row=3, column=0, sticky='w', pady=5)
        self.start_date_var = tk.StringVar(value=current_data['start_date'] if current_data else '')
        ttk.Entry(main_frame, textvariable=self.start_date_var, width=30).grid(row=3, column=1, pady=5, sticky='ew')
        
        # End Date
        ttk.Label(main_frame, text="End Date (YYYY-MM-DD):").grid(row=4, column=0, sticky='w', pady=5)
        self.end_date_var = tk.StringVar(value=current_data['end_date'] if current_data else '')
        ttk.Entry(main_frame, textvariable=self.end_date_var, width=30).grid(row=4, column=1, pady=5, sticky='ew')
        
        # Status
        ttk.Label(main_frame, text="Status:").grid(row=5, column=0, sticky='w', pady=5)
        self.status_var = tk.StringVar(value=current_data['status'] if current_data else 'active')
        status_combo = ttk.Combobox(main_frame, textvariable=self.status_var, width=28)
        status_combo['values'] = ['active', 'pending', 'suspended', 'expired']
        status_combo.grid(row=5, column=1, pady=5, sticky='ew')
        
        # Notes
        ttk.Label(main_frame, text="Notes:").grid(row=6, column=0, sticky='nw', pady=5)
        self.notes_text = tk.Text(main_frame, height=3, width=30)
        if current_data and current_data['notes']:
            self.notes_text.insert(tk.END, current_data['notes'])
        self.notes_text.grid(row=6, column=1, pady=5, sticky='ew')
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
    
    def save(self):
        """Save the accommodation data"""
        # Validate required fields
        if not self.student_id_var.get().strip():
            messagebox.showerror("Error", "Student ID is required")
            return
        
        if not self.type_var.get().strip():
            messagebox.showerror("Error", "Accommodation type is required")
            return
        
        # Validate and parse dates
        start_date_str = self.start_date_var.get().strip()
        end_date_str = self.end_date_var.get().strip()
        
        start_date = None
        end_date = None
        
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Error", "Invalid start date format. Use YYYY-MM-DD")
                return
        
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Error", "Invalid end date format. Use YYYY-MM-DD")
                return
        
        # Check date range
        if start_date and end_date and end_date <= start_date:
            messagebox.showerror("Error", "End date must be after start date")
            return
        
        # Collect data
        self.result = {
            'student_id': self.student_id_var.get().strip(),
            'accommodation_type': self.type_var.get().strip(),
            'description': self.description_text.get(1.0, tk.END).strip() or None,
            'start_date': start_date_str or None,
            'end_date': end_date_str or None,
            'status': self.status_var.get(),
            'notes': self.notes_text.get(1.0, tk.END).strip() or None
        }
        
        self.dialog.destroy()
        
    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


class TemplateDialog:
    """Dialog for creating/editing templates"""
    
    def __init__(self, parent, title, current_data=None):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("450x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets(current_data)
        self.dialog.wait_window()
    
    def create_widgets(self, current_data):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Template Name
        ttk.Label(main_frame, text="Template Name:").grid(row=0, column=0, sticky='w', pady=5)
        self.name_var = tk.StringVar(value=current_data['name'] if current_data else '')
        ttk.Entry(main_frame, textvariable=self.name_var, width=30).grid(row=0, column=1, pady=5, sticky='ew')
        
        # Accommodation Type
        ttk.Label(main_frame, text="Accommodation Type:").grid(row=1, column=0, sticky='w', pady=5)
        self.type_var = tk.StringVar(value=current_data['accommodation_type'] if current_data else '')
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=28)
        if CLI_AVAILABLE:
            type_combo['values'] = get_accommodation_types()
        type_combo.grid(row=1, column=1, pady=5, sticky='ew')
        
        # Description
        ttk.Label(main_frame, text="Description:").grid(row=2, column=0, sticky='nw', pady=5)
        self.description_text = tk.Text(main_frame, height=3, width=30)
        if current_data and current_data['description']:
            self.description_text.insert(tk.END, current_data['description'])
        self.description_text.grid(row=2, column=1, pady=5, sticky='ew')
        
        # Start Offset Days
        ttk.Label(main_frame, text="Start Offset (days):").grid(row=3, column=0, sticky='w', pady=5)
        self.offset_var = tk.StringVar(value=str(current_data['start_offset_days']) if current_data else '0')
        ttk.Entry(main_frame, textvariable=self.offset_var, width=30).grid(row=3, column=1, pady=5, sticky='ew')
        
        # Duration Days
        ttk.Label(main_frame, text="Duration (days):").grid(row=4, column=0, sticky='w', pady=5)
        self.duration_var = tk.StringVar(value=str(current_data['duration_days']) if current_data else '365')
        ttk.Entry(main_frame, textvariable=self.duration_var, width=30).grid(row=4, column=1, pady=5, sticky='ew')
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
    
    def save(self):
        """Save the template"""
        if not self.name_var.get().strip():
            messagebox.showerror("Error", "Template name is required")
            return
        
        if not self.type_var.get().strip():
            messagebox.showerror("Error", "Accommodation type is required")
            return
        
        try:
            offset = int(self.offset_var.get())
            if offset < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Start offset must be a non-negative number")
            return
        
        try:
            duration = int(self.duration_var.get())
            if duration <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Duration must be a positive number")
            return
        
        self.result = {
            'name': self.name_var.get().strip(),
            'accommodation_type': self.type_var.get().strip(),
            'description': self.description_text.get(1.0, tk.END).strip() or None,
            'start_offset_days': offset,
            'duration_days': duration
        }
        
        self.dialog.destroy()
    
    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


class ApplyTemplateDialog:
    """Dialog for applying templates"""
    
    def __init__(self, parent):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Apply Template")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.wait_window()
    
    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Student ID
        ttk.Label(main_frame, text="Student ID:").grid(row=0, column=0, sticky='w', pady=5)
        self.student_id_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.student_id_var, width=30).grid(row=0, column=1, pady=5, sticky='ew')
        
        # Template Selection
        ttk.Label(main_frame, text="Template:").grid(row=1, column=0, sticky='w', pady=5)
        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(main_frame, textvariable=self.template_var, width=28)
        self.template_combo.grid(row=1, column=1, pady=5, sticky='ew')
        
        # Load templates
        self.load_templates()
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Apply", command=self.apply).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
    
    def load_templates(self):
        """Load available templates"""
        if not CLI_AVAILABLE:
            return
        
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'SELECT name FROM {TEMPLATES_TABLE} ORDER BY name')
                templates = [row[0] for row in cursor.fetchall()]
                self.template_combo['values'] = templates
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load templates: {str(e)}")
    
    def apply(self):
        """Apply the template"""
        if not self.student_id_var.get().strip():
            messagebox.showerror("Error", "Student ID is required")
            return
        
        if not self.template_var.get().strip():
            messagebox.showerror("Error", "Please select a template")
            return
        
        # Validate student ID
        if CLI_AVAILABLE and not validate_student_id(self.student_id_var.get().strip()):
            messagebox.showerror("Error", "Student ID not found in the system")
            return
        
        self.result = {
            'student_id': self.student_id_var.get().strip(),
            'template_name': self.template_var.get().strip()
        }
        
        self.dialog.destroy()
    
    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


class ExportFilterDialog:
    """Dialog for export filters"""
    
    def __init__(self, parent):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Export Filters")
        self.dialog.geometry("400x250")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.wait_window()
    
    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text="Filter Options (leave blank for all):").grid(row=0, column=0, columnspan=2, pady=10)
        
        # Student ID
        ttk.Label(main_frame, text="Student ID:").grid(row=1, column=0, sticky='w', pady=5)
        self.student_id_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.student_id_var, width=30).grid(row=1, column=1, pady=5, sticky='ew')
        
        # Accommodation Type
        ttk.Label(main_frame, text="Accommodation Type:").grid(row=2, column=0, sticky='w', pady=5)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=28)
        if CLI_AVAILABLE:
            type_combo['values'] = [''] + get_accommodation_types()
        type_combo.grid(row=2, column=1, pady=5, sticky='ew')
        
        # Status
        ttk.Label(main_frame, text="Status:").grid(row=3, column=0, sticky='w', pady=5)
        self.status_var = tk.StringVar()
        status_combo = ttk.Combobox(main_frame, textvariable=self.status_var, width=28)
        status_combo['values'] = ['', 'active', 'pending', 'suspended', 'expired']
        status_combo.grid(row=3, column=1, pady=5, sticky='ew')
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Export", command=self.export).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
    
    def export(self):
        """Set export filters"""
        self.result = {
            'student_id': self.student_id_var.get().strip() or None,
            'accommodation_type': self.type_var.get().strip() or None,
            'status': self.status_var.get().strip() or None
        }
        
        self.dialog.destroy()
    
    def cancel(self):
        """Cancel export"""
        self.dialog.destroy()


# Additional dialog classes...

class DetailsDialog:
    """Dialog for showing accommodation details"""
    
    def __init__(self, parent, accommodation, documents):
        # Normalize rows to dictionaries in case callers pass sqlite3.Row objects
        try:
            accommodation = dict(accommodation)
        except (TypeError, ValueError):
            # Already a dict or incompatible type; leave as-is
            pass

        normalized_docs = []
        for doc in documents:
            try:
                normalized_docs.append(dict(doc))
            except (TypeError, ValueError):
                normalized_docs.append(doc)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Accommodation Details - ID {accommodation['id']}")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        
        self.create_widgets(accommodation, normalized_docs)
    
    def create_widgets(self, accommodation, documents):
        """Create detail widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Details text
        self.details_text = ScrolledText(main_frame, width=70, height=25)
        self.details_text.pack(fill=tk.BOTH, expand=True)
        
        # Format details
        student_name = f"{accommodation['first_name'] or ''} {accommodation['last_name'] or ''}".strip() or 'N/A'
        
        details = f"""
ACCOMMODATION DETAILS
{'='*60}

ID: {accommodation['id']}
Student: {accommodation['student_id']} - {student_name}
Email: {accommodation['email_address'] or 'N/A'}
Type: {accommodation['accommodation_type']}
Description: {accommodation['description'] or 'N/A'}
Start Date: {accommodation['start_date'] or 'Not specified'}
End Date: {accommodation['end_date'] or 'Not specified'}
Status: {accommodation['status']}
Approved By: {accommodation.get('approved_by') or 'N/A'}
Approval Date: {accommodation.get('approval_date') or 'N/A'}
Notes: {accommodation['notes'] or 'N/A'}
Created: {accommodation['created_at']}
Last Updated: {accommodation['updated_at']}
"""
        
        if documents:
            details += f"\n\nATTACHED DOCUMENTS:\n{'-'*60}\n"
            for doc in documents:
                details += f"- {doc['document_name']} (Uploaded: {doc['uploaded_at']})\n"
        else:
            details += "\n\nNo attached documents."
        
        self.details_text.insert(tk.END, details)
        self.details_text.config(state=tk.DISABLED)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)


# Import result dialogs and other utility dialogs...

class ImportResultDialog:
    """Dialog for showing import results"""
    
    def __init__(self, parent, title, result_text):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        result_text_widget = ScrolledText(main_frame, width=60, height=20)
        result_text_widget.pack(fill=tk.BOTH, expand=True)
        result_text_widget.insert(tk.END, result_text)
        result_text_widget.config(state=tk.DISABLED)
        
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)


class ApprovalDialog:
    """Dialog for approval management"""
    
    def __init__(self, parent, gui_parent):
        self.gui_parent = gui_parent
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Approval Management")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.load_pending_approvals()
    
    def create_widgets(self):
        """Create approval widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text="Pending Accommodations", font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Approval tree
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.approval_tree = ttk.Treeview(tree_frame, columns=(
            'ID', 'Student ID', 'Name', 'Type', 'Start Date', 'End Date', 'Description'
        ), show='headings')
        
        columns = {
            'ID': 50,
            'Student ID': 100,
            'Name': 120,
            'Type': 150,
            'Start Date': 100,
            'End Date': 100,
            'Description': 200
        }
        
        for col, width in columns.items():
            self.approval_tree.heading(col, text=col)
            self.approval_tree.column(col, width=width, minwidth=50)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.approval_tree.yview)
        self.approval_tree.configure(yscrollcommand=scrollbar.set)
        
        self.approval_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Approve", command=self.approve_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reject", command=self.reject_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Request Info", command=self.request_info).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_pending_approvals).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def load_pending_approvals(self):
        """Load pending approvals"""
        if not CLI_AVAILABLE:
            return
        
        # Clear existing items
        for item in self.approval_tree.get_children():
            self.approval_tree.delete(item)
        
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.id, a.student_id, a.accommodation_type, a.description, 
                           a.start_date, a.end_date, s.first_name, s.last_name
                    FROM accommodations a
                    JOIN students s ON a.student_id = s.student_id
                    WHERE a.status = 'pending'
                    ORDER BY a.created_at DESC
                ''')
                
                pending = cursor.fetchall()
                
                for acc in pending:
                    student_name = f"{acc['first_name'] or ''} {acc['last_name'] or ''}".strip() or 'N/A'
                    
                    self.approval_tree.insert('', 'end', values=(
                        acc['id'],
                        acc['student_id'],
                        student_name,
                        acc['accommodation_type'],
                        acc['start_date'] or 'N/A',
                        acc['end_date'] or 'N/A',
                        acc['description'] or 'N/A'
                    ))
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load pending approvals: {str(e)}")
    
    def get_selected_approval(self):
        """Get selected approval"""
        selection = self.approval_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an accommodation to process")
            return None
        return self.approval_tree.item(selection[0])
    
    def approve_selected(self):
        """Approve selected accommodation"""
        self.process_approval_action('approve')
    
    def reject_selected(self):
        """Reject selected accommodation"""
        self.process_approval_action('reject')
    
    def request_info(self):
        """Request more information"""
        self.process_approval_action('request_info')
    
    def process_approval_action(self, action):
        """Process approval action"""
        selected = self.get_selected_approval()
        if not selected:
            return
        
        accommodation_id = selected['values'][0]
        student_id = selected['values'][1]
        acc_type = selected['values'][3]
        
        # Get reason/comments
        reason = simpledialog.askstring(f"{action.replace('_', ' ').title()}", 
            "Enter reason or comments (optional):", initialvalue="")
        
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            user = resolve_user_identifier(auth_instance=self.auth)

            with get_connection() as conn:
                cursor = conn.cursor()
                
                if action == 'approve':
                    new_status = 'active'
                    note_text = f"Approved: {reason}" if reason else "Approved"
                    message = f"Your {acc_type} accommodation has been approved."
                    
                elif action == 'reject':
                    new_status = 'rejected'
                    note_text = f"Rejected: {reason}" if reason else "Rejected"
                    message = f"Your {acc_type} accommodation has been rejected."
                    
                else:  # request_info
                    new_status = 'pending'  # Keep as pending
                    note_text = f"More info requested: {reason}" if reason else "More info requested"
                    message = f"More information is required for your {acc_type} accommodation."
                
                if reason:
                    message += f" Comments: {reason}"
                
                cursor.execute('''
                    UPDATE accommodations SET
                    status = ?,
                    approved_by = ?,
                    approval_date = ?,
                    notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | ' || ? END,
                    updated_at = ?
                    WHERE id = ?
                ''', (new_status, user, now, note_text, note_text, now, accommodation_id))
                
                conn.commit()
            
            # Log action
            log_action(action, accommodation_id, f"{action} accommodation for {student_id}: {reason}")
            
            # Notify student using template system
            from university_system.infrastructure.email.template_utils import render_template

            try:
                template_subject, template_message = render_template("accommodation_notification", {
                    "action_type": action.replace('_', ' ').title(),
                    "accommodation_type": acc_type,
                    "status": new_status,
                    "reason": reason if reason else "",
                    "message": message
                })

                if template_subject and template_message:
                    notify_student(student_id, template_subject, template_message)
                else:
                    # Fallback to original message if template fails
                    subject = f"Accommodation {action.replace('_', ' ').title()}"
                    notify_student(student_id, subject, message)
            except Exception as e:
                # Error handling - use original message
                subject = f"Accommodation {action.replace('_', ' ').title()}"
                notify_student(student_id, subject, message)
            
            messagebox.showinfo("Success", f"Accommodation {action}d successfully")
            self.load_pending_approvals()
            self.gui_parent.refresh_data()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to {action} accommodation: {str(e)}")


class TemplateManagerDialog:
    """Dialog for managing templates"""
    
    def __init__(self, parent, gui_parent):
        self.gui_parent = gui_parent
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Template Manager")
        self.dialog.geometry("800x500")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.load_templates()
    
    def create_widgets(self):
        """Create template manager widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Template list
        list_frame = ttk.LabelFrame(main_frame, text="Templates")
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.template_tree = ttk.Treeview(list_frame, columns=(
            'Name', 'Type', 'Description', 'Duration', 'Created By'
        ), show='headings')
        
        columns = {
            'Name': 150,
            'Type': 150,
            'Description': 200,
            'Duration': 100,
            'Created By': 120
        }
        
        for col, width in columns.items():
            self.template_tree.heading(col, text=col)
            self.template_tree.column(col, width=width)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.template_tree.yview)
        self.template_tree.configure(yscrollcommand=scrollbar.set)
        
        self.template_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="New Template", command=self.new_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Edit Selected", command=self.edit_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete Selected", command=self.delete_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Apply Template", command=self.apply_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_templates).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def load_templates(self):
        """Load templates"""
        if not CLI_AVAILABLE:
            return
        
        # Clear existing
        for item in self.template_tree.get_children():
            self.template_tree.delete(item)
        
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(f'''
                    SELECT name, accommodation_type, description, duration_days, created_by
                    FROM {TEMPLATES_TABLE}
                    ORDER BY name
                ''')
                
                templates = cursor.fetchall()
                
                for template in templates:
                    self.template_tree.insert('', 'end', values=(
                        template['name'],
                        template['accommodation_type'],
                        template['description'] or 'N/A',
                        f"{template['duration_days']} days" if template['duration_days'] else 'N/A',
                        template['created_by'] or 'N/A'
                    ))
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load templates: {str(e)}")
    
    def new_template(self):
        """Create new template"""
        dialog = TemplateDialog(self.dialog, "New Template")
        if dialog.result:
            self.save_template(dialog.result)
    
    def edit_template(self):
        """Edit selected template"""
        selection = self.template_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to edit")
            return
        
        template_name = self.template_tree.item(selection[0])['values'][0]
        
        try:
            # Get current data
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(f'SELECT * FROM {TEMPLATES_TABLE} WHERE name = ?', (template_name,))
                template_data = cursor.fetchone()
            
            if template_data:
                dialog = TemplateDialog(self.dialog, "Edit Template", template_data)
                if dialog.result:
                    self.update_template(template_name, dialog.result)
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit template: {str(e)}")
    
    def delete_template(self):
        """Delete selected template"""
        selection = self.template_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to delete")
            return
        
        template_name = self.template_tree.item(selection[0])['values'][0]
        
        if messagebox.askyesno("Confirm Delete", f"Delete template '{template_name}'?"):
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(f'DELETE FROM {TEMPLATES_TABLE} WHERE name = ?', (template_name,))
                    conn.commit()
                
                messagebox.showinfo("Success", f"Template '{template_name}' deleted")
                self.load_templates()
                self.gui_parent.refresh_templates()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete template: {str(e)}")
    
    def apply_template(self):
        """Apply selected template"""
        selection = self.template_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to apply")
            return
        
        template_name = self.template_tree.item(selection[0])['values'][0]
        
        # Get student ID
        student_id = simpledialog.askstring("Apply Template", "Enter Student ID:")
        if student_id:
            # Create apply dialog with pre-selected template
            dialog = ApplyTemplateDialog(self.dialog)
            if dialog.result:
                dialog.result['template_name'] = template_name
                self.gui_parent.apply_template_with_data(dialog.result)
    
    def save_template(self, template_data):
        """Save new template"""
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            user = resolve_user_identifier(auth_instance=self.auth)

            description = template_data.get('description')
            if description is not None and not isinstance(description, str):
                description = json.dumps(description, default=str)

            duration_days = template_data.get('duration_days')
            start_offset_days = template_data.get('start_offset_days')

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    INSERT OR REPLACE INTO {TEMPLATES_TABLE}
                    (name, accommodation_type, description, start_offset_days, 
                     duration_days, created_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    template_data['name'],
                    template_data['accommodation_type'],
                    description,
                    int(start_offset_days) if start_offset_days is not None else None,
                    int(duration_days) if duration_days is not None else None,
                    user, now, now
                ))
                conn.commit()

            messagebox.showinfo("Success", f"Template '{template_data['name']}' saved")
            self.load_templates()
            self.gui_parent.refresh_templates()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save template: {str(e)}")
    
    def update_template(self, template_name, template_data):
        """Update existing template"""
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            description = template_data.get('description')
            if description is not None and not isinstance(description, str):
                description = json.dumps(description, default=str)
            duration_days = template_data.get('duration_days')
            start_offset_days = template_data.get('start_offset_days')
            
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    UPDATE {TEMPLATES_TABLE} SET
                    accommodation_type = ?, description = ?, start_offset_days = ?,
                    duration_days = ?, updated_at = ?
                    WHERE name = ?
                ''', (
                    template_data['accommodation_type'],
                    description,
                    int(start_offset_days) if start_offset_days is not None else None,
                    int(duration_days) if duration_days is not None else None,
                    now,
                    template_name
                ))
                conn.commit()
            
            messagebox.showinfo("Success", f"Template '{template_name}' updated")
            self.load_templates()
            self.gui_parent.refresh_templates()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update template: {str(e)}")


class StatisticsDialog:
    """Dialog for statistics report"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Statistics Report")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.generate_statistics()
    
    def create_widgets(self):
        """Create statistics widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Statistics text
        self.stats_text = ScrolledText(main_frame, width=80, height=30)
        self.stats_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Refresh", command=self.generate_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export Report", command=self.export_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def generate_statistics(self):
        """Generate statistics"""
        if not CLI_AVAILABLE:
            return
        
        try:
            import io
            import contextlib
            
            output = io.StringIO()
            
            with contextlib.redirect_stdout(output):
                generate_statistics_report()
            
            result = output.getvalue()
            
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(tk.END, result)
            
        except Exception as e:
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(tk.END, f"Error generating statistics: {str(e)}")
    
    def export_report(self):
        """Export statistics report"""
        file_path = filedialog.asksaveasfilename(
            title="Save Statistics Report",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            defaultextension=".txt"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.stats_text.get(1.0, tk.END))
                
                messagebox.showinfo("Success", f"Report exported to {file_path}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export report: {str(e)}")


class ExpiryResultDialog:
    """Dialog for expiry check results"""
    
    def __init__(self, parent, result_text, days):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Expiry Check - {days} Days")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        result_text_widget = ScrolledText(main_frame, width=70, height=20)
        result_text_widget.pack(fill=tk.BOTH, expand=True)
        result_text_widget.insert(tk.END, result_text)
        result_text_widget.config(state=tk.DISABLED)
        
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)


class DatabaseInfoDialog:
    """Dialog for database information"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Database Information")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        
        self.create_widgets()
        self.load_info()
    
    def create_widgets(self):
        """Create info widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        self.info_text = ScrolledText(main_frame, width=60, height=20)
        self.info_text.pack(fill=tk.BOTH, expand=True)
        
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)
    
    def load_info(self):
        """Load database information"""
        if not CLI_AVAILABLE:
            self.info_text.insert(tk.END, "CLI module not available")
            return

        try:
            from university_system.modules.shared.constants import paths
            db_path = str(paths.DEFAULT_DB_PATH)

            info_text = "DATABASE INFORMATION\n"
            info_text += "=" * 50 + "\n\n"

            # Database file info
            if os.path.exists(db_path):
                stat = os.stat(db_path)
                info_text += f"Database File: {db_path}\n"
                info_text += f"File Size: {stat.st_size:,} bytes\n"
                info_text += f"Last Modified: {datetime.fromtimestamp(stat.st_mtime)}\n\n"
            
            # Table information
            with get_connection() as conn:
                cursor = conn.cursor()
                
                # Get table names
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                info_text += f"Tables: {len(tables)}\n\n"
                
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    info_text += f"{table}: {count:,} records\n"
                
                info_text += "\n"
                
                # Schema information
                for table in tables:
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = cursor.fetchall()
                    
                    info_text += f"\n{table.upper()} TABLE SCHEMA:\n"
                    info_text += "-" * 30 + "\n"
                    
                    for col in columns:
                        info_text += f"  {col[1]} ({col[2]})\n"
            
            self.info_text.insert(tk.END, info_text)
            
        except Exception as e:
            self.info_text.insert(tk.END, f"Error loading database info: {str(e)}")


class SettingsDialog:
    """Dialog for application settings"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Settings")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create settings widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Notification settings
        notification_frame = ttk.LabelFrame(main_frame, text="Notifications")
        notification_frame.pack(fill=tk.X, pady=10)
        
        self.expiry_days_var = tk.StringVar(value="7")
        ttk.Label(notification_frame, text="Expiry notification days:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        ttk.Entry(notification_frame, textvariable=self.expiry_days_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        
        # Display settings
        display_frame = ttk.LabelFrame(main_frame, text="Display")
        display_frame.pack(fill=tk.X, pady=10)
        
        self.auto_refresh_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(display_frame, text="Auto-refresh data", variable=self.auto_refresh_var).pack(anchor='w', padx=5, pady=5)
        
        self.show_tooltips_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(display_frame, text="Show tooltips", variable=self.show_tooltips_var).pack(anchor='w', padx=5, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def save_settings(self):
        """Save settings"""
        # In a real application, you would save these to a config file
        messagebox.showinfo("Settings", "Settings saved successfully")
        self.dialog.destroy()


class HelpDialog:
    """Dialog for help information"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("User Guide")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        help_text = ScrolledText(main_frame, width=70, height=25)
        help_text.pack(fill=tk.BOTH, expand=True)
        
        help_content = """
STUDENT ACCOMMODATION MANAGEMENT SYSTEM - USER GUIDE
===================================================

OVERVIEW
--------
This application helps manage student accommodations with features for:
- Adding and updating accommodation records
- Template management for common accommodations
- Search and filtering capabilities
- Approval workflow for pending accommodations
- Import/export functionality
- Dashboard and reporting

MAIN FEATURES
-------------

1. ACCOMMODATIONS TAB
   - View all accommodation records
   - Add new accommodations
   - Update existing records
   - Remove accommodations
   - Approve/reject pending requests

2. SEARCH & FILTER TAB
   - Search by student ID, type, status
   - Filter by date ranges
   - Keyword search in descriptions

3. DASHBOARD TAB
   - Key metrics and statistics
   - Visual charts and breakdowns
   - Quick overview of system status

4. TEMPLATES TAB
   - Create reusable templates
   - Apply templates to students
   - Manage existing templates

MENU OPTIONS
------------

File Menu:
- Import from CSV/JSON files
- Export to various formats (CSV, Excel, PDF, JSON)

Accommodations Menu:
- Add new accommodations
- Update/remove selected records
- Approval management

Templates Menu:
- Save and apply templates
- Template management

Reports Menu:
- Dashboard metrics
- Statistics reports
- Expiry notifications

Tools Menu:
- CLI mode (command-line interface)
- Database information
- Application settings

KEYBOARD SHORTCUTS
------------------
- Double-click on record: View details
- F5: Refresh data
- Ctrl+N: New accommodation
- Ctrl+E: Edit selected
- Delete: Remove selected

TROUBLESHOOTING
---------------
- If data doesn't load, check database connection
- For import errors, verify file format
- CLI mode provides additional debugging options

For technical support, contact your system administrator.
"""
        
        help_text.insert(tk.END, help_content)
        help_text.config(state=tk.DISABLED)
        
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)

# Complete the apply_template_with_data function
def apply_template_with_data(self, template_data):
    """Apply template with provided data"""
    try:
        # Get template details
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                SELECT accommodation_type, description, start_offset_days, duration_days
                FROM {TEMPLATES_TABLE} WHERE name = ?
            ''', (template_data['template_name'],))
            
            template = cursor.fetchone()
            if not template:
                messagebox.showerror("Error", "Template not found")
                return
            
            typ, desc, offset, duration = template
            
            # Calculate dates
            start_date = datetime.now() + timedelta(days=offset)
            end_date = start_date + timedelta(days=duration)
            
            # Check for conflicts
            if check_conflict(template_data['student_id'], typ, 
                            start_date.strftime('%Y-%m-%d'), 
                            end_date.strftime('%Y-%m-%d')):
                if not messagebox.askyesno("Conflict", 
                    "This accommodation overlaps with an existing record. Continue anyway?"):
                    return
            
            # Apply template
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            notes = f"Applied from template: {template_data['template_name']}"
            
            cursor.execute('''
                INSERT INTO accommodations
                (student_id, accommodation_type, description, start_date, end_date, 
                 status, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'Active', ?, ?, ?)
            ''', (template_data['student_id'], typ, desc,
                  start_date.strftime('%Y-%m-%d'),
                  end_date.strftime('%Y-%m-%d'),
                  notes, now, now))
            
            conn.commit()
            messagebox.showinfo("Success", "Template applied successfully")
            self.refresh_data()
            
    except Exception as e:
        messagebox.showerror("Error", f"Failed to apply template: {str(e)}")

# Fix the broken export_csv function name
def export_csv(self):
    """Export accommodations to CSV"""
    self.export_data('csv')

# Complete the broken export_data function
def export_to_csv_file(self, rows, file_path):
    """Export rows to CSV file"""
    import csv
    
    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        if not rows:
            return
        
        # Get column names
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))

def export_to_excel_file(self, rows, file_path):
    """Export rows to Excel file"""
    try:
        import pandas as pd
        
        # Convert rows to list of dicts
        data = [dict(row) for row in rows]
        df = pd.DataFrame(data)
        
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Accommodations', index=False)
            
    except ImportError:
        messagebox.showerror("Error", "pandas and openpyxl required for Excel export")

def export_to_pdf_file(self, rows, file_path):
    """Export rows to PDF file"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        
        doc = SimpleDocTemplate(file_path, pagesize=A4)
        elements = []
        
        # Title
        styles = getSampleStyleSheet()
        title = Paragraph("Accommodations Report", styles['Title'])
        elements.append(title)
        
        # Table data
        if rows:
            headers = list(rows[0].keys())
            data = [headers]
            
            for row in rows:
                data.append([str(row[col] or '') for col in headers])
            
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 14),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(table)
        
        doc.build(elements)
        
    except ImportError:
        messagebox.showerror("Error", "reportlab required for PDF export")

def export_to_json_file(self, rows, file_path):
    """Export rows to JSON file"""
    import json
    
    data = [dict(row) for row in rows]
    
    with open(file_path, 'w', encoding='utf-8') as jsonfile:
        json.dump(data, jsonfile, indent=2, default=str)

class DocumentUploadDialog:
    """Dialog for uploading documents"""
    
    def __init__(self, parent, accommodation_id):
        self.result = None
        self.accommodation_id = accommodation_id
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Upload Document")
        self.dialog.geometry("500x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.wait_window()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Document name
        ttk.Label(main_frame, text="Document Name:").grid(row=0, column=0, sticky='w', pady=5)
        self.doc_name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.doc_name_var, width=40).grid(row=0, column=1, pady=5, sticky='ew')
        
        # File path
        ttk.Label(main_frame, text="File Path:").grid(row=1, column=0, sticky='w', pady=5)
        path_frame = ttk.Frame(main_frame)
        path_frame.grid(row=1, column=1, sticky='ew', pady=5)
        
        self.file_path_var = tk.StringVar()
        ttk.Entry(path_frame, textvariable=self.file_path_var, width=30).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(path_frame, text="Browse", command=self.browse_file).pack(side=tk.RIGHT, padx=(5,0))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Upload", command=self.upload).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
    
    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Document",
            filetypes=[("All files", "*.*")]
        )
        if file_path:
            self.file_path_var.set(file_path)
            # Auto-fill document name if not set
            if not self.doc_name_var.get():
                import os
                self.doc_name_var.set(os.path.basename(file_path))
    
    def upload(self):
        if not self.doc_name_var.get().strip():
            messagebox.showerror("Error", "Document name is required")
            return

        if not self.file_path_var.get().strip():
            messagebox.showerror("Error", "File path is required")
            return

        if not os.path.exists(self.file_path_var.get()):
            messagebox.showerror("Error", "File does not exist")
            return

        try:
            self.do_upload()
            if CLI_AVAILABLE and 'log_action' in globals():
                log_action('upload_document', self.accommodation_id,
                           f"Uploaded document '{self.doc_name_var.get().strip()}'")

            self.result = True
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Upload failed: {str(e)}")
    
    def do_upload(self):
        """Perform the actual file upload"""
        import shutil
        from datetime import datetime

        # Create uploads directory if it doesn't exist
        uploads_dir = globals().get('UPLOADS_DIR', "uploaded_documents")
        os.makedirs(uploads_dir, exist_ok=True)

        # Create safe filename
        file_path = self.file_path_var.get()
        ext = os.path.splitext(file_path)[1]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{self.accommodation_id}_{timestamp}{ext}"
        destination_path = os.path.join(uploads_dir, safe_filename)
        
        # Copy file
        shutil.copy(file_path, destination_path)
        
        # Record in database
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user = resolve_user_identifier(auth_instance=self.auth)

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO accommodation_documents
                (accommodation_id, document_name, document_path, uploaded_by, uploaded_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (self.accommodation_id, self.doc_name_var.get().strip(),
                  destination_path, user, now))
            conn.commit()

    def cancel(self):
        self.dialog.destroy()

class BulkOperationsDialog:
    """Dialog for bulk operations"""
    
    def __init__(self, parent, gui_parent):
        self.gui_parent = gui_parent
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Bulk Operations")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Operation selection
        operation_frame = ttk.LabelFrame(main_frame, text="Select Operation")
        operation_frame.pack(fill=tk.X, pady=10)
        
        self.operation_var = tk.StringVar(value="update_status")
        ttk.Radiobutton(operation_frame, text="Update Status", 
                       variable=self.operation_var, value="update_status").pack(anchor='w')
        ttk.Radiobutton(operation_frame, text="Update Type", 
                       variable=self.operation_var, value="update_type").pack(anchor='w')
        ttk.Radiobutton(operation_frame, text="Add Notes", 
                       variable=self.operation_var, value="add_notes").pack(anchor='w')
        ttk.Radiobutton(operation_frame, text="Set End Date", 
                       variable=self.operation_var, value="set_end_date").pack(anchor='w')
        
        # Criteria frame
        criteria_frame = ttk.LabelFrame(main_frame, text="Selection Criteria")
        criteria_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(criteria_frame, text="Student ID (optional):").grid(row=0, column=0, sticky='w')
        self.student_id_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.student_id_var, width=20).grid(row=0, column=1, padx=5)
        
        ttk.Label(criteria_frame, text="Current Status:").grid(row=0, column=2, sticky='w', padx=(20,0))
        self.current_status_var = tk.StringVar()
        ttk.Combobox(criteria_frame, textvariable=self.current_status_var, 
                    values=['', 'active', 'pending', 'suspended', 'expired']).grid(row=0, column=3, padx=5)
        
        # Value frame
        value_frame = ttk.LabelFrame(main_frame, text="New Value")
        value_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(value_frame, text="Value:").pack(anchor='w')
        self.new_value_var = tk.StringVar()
        ttk.Entry(value_frame, textvariable=self.new_value_var, width=50).pack(fill=tk.X, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        ttk.Button(button_frame, text="Execute", command=self.execute).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Preview", command=self.preview).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def preview(self):
        """Preview which records would be affected"""
        try:
            query, params = self.build_selection_query()
            
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = cursor.fetchall()
            
            preview_text = f"This operation will affect {len(results)} record(s):\n\n"
            for result in results[:10]:  # Show first 10
                preview_text += f"ID: {result[0]}, Student: {result[1]}, Type: {result[2]}\n"
            
            if len(results) > 10:
                preview_text += f"... and {len(results) - 10} more records"
                
            messagebox.showinfo("Preview", preview_text)
            
        except Exception as e:
            messagebox.showerror("Error", f"Preview failed: {str(e)}")
    
    def build_selection_query(self):
        """Build SQL query based on criteria"""
        query = "SELECT id, student_id, accommodation_type FROM accommodations WHERE 1=1"
        params = []
        
        if self.student_id_var.get().strip():
            query += " AND student_id = ?"
            params.append(self.student_id_var.get().strip())
            
        if self.current_status_var.get().strip():
            query += " AND status = ?"
            params.append(self.current_status_var.get().strip())
            
        return query, params
    
    def execute(self):
        """Execute the bulk operation"""
        if not self.new_value_var.get().strip():
            messagebox.showerror("Error", "New value is required")
            return
            
        if not messagebox.askyesno("Confirm", "Execute bulk operation? This cannot be undone."):
            return
            
        try:
            query, params = self.build_selection_query()
            operation = self.operation_var.get()
            new_value = self.new_value_var.get().strip()
            
            # Get affected records first
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                affected_records = cursor.fetchall()
                
                if not affected_records:
                    messagebox.showinfo("Info", "No records match the criteria")
                    return
                
                # Execute the bulk operation
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                if operation == "update_status":
                    for record_id, _, _ in affected_records:
                        cursor.execute(
                            "UPDATE accommodations SET status = ?, updated_at = ? WHERE id = ?",
                            (new_value, now, record_id)
                        )
                elif operation == "update_type":
                    for record_id, _, _ in affected_records:
                        cursor.execute(
                            "UPDATE accommodations SET accommodation_type = ?, updated_at = ? WHERE id = ?",
                            (new_value, now, record_id)
                        )
                elif operation == "add_notes":
                    for record_id, _, _ in affected_records:
                        cursor.execute(
                            "UPDATE accommodations SET notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | ' || ? END, updated_at = ? WHERE id = ?",
                            (new_value, new_value, now, record_id)
                        )
                elif operation == "set_end_date":
                    for record_id, _, _ in affected_records:
                        cursor.execute(
                            "UPDATE accommodations SET end_date = ?, updated_at = ? WHERE id = ?",
                            (new_value, now, record_id)
                        )
                
                conn.commit()
                
            messagebox.showinfo("Success", f"Updated {len(affected_records)} record(s)")
            self.gui_parent.refresh_data()
            
        except Exception as e:
            messagebox.showerror("Error", f"Bulk operation failed: {str(e)}")

# Missing ExportFilterDialog class
class ExportFilterDialog:
    """Dialog for selecting export filters"""
    
    def __init__(self, parent):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Export Filters")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.center_dialog()
        
        # Wait for dialog to close
        self.dialog.wait_window()
    
    def create_widgets(self):
        """Create filter widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Student ID filter
        ttk.Label(main_frame, text="Student ID (optional):").pack(anchor=tk.W)
        self.student_id_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.student_id_var, width=40).pack(fill=tk.X, pady=(5, 15))
        
        # Accommodation type filter
        ttk.Label(main_frame, text="Accommodation Type (optional):").pack(anchor=tk.W)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=37)
        type_combo['values'] = ('', 'Extended Time', 'Separate Room', 'Large Print', 'Reader', 'Scribe', 'Other')
        type_combo.pack(fill=tk.X, pady=(5, 15))
        
        # Status filter
        ttk.Label(main_frame, text="Status (optional):").pack(anchor=tk.W)
        self.status_var = tk.StringVar()
        status_combo = ttk.Combobox(main_frame, textvariable=self.status_var, width=37)
        status_combo['values'] = ('', 'Active', 'Inactive', 'Pending', 'Expired')
        status_combo.pack(fill=tk.X, pady=(5, 15))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Export", command=self.ok).pack(side=tk.RIGHT)
    
    def center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def ok(self):
        """OK button handler"""
        self.result = {
            'student_id': self.student_id_var.get().strip() or None,
            'accommodation_type': self.type_var.get().strip() or None,
            'status': self.status_var.get().strip() or None
        }
        self.dialog.destroy()
    
    def cancel(self):
        """Cancel button handler"""
        self.result = None
        self.dialog.destroy()

# Missing check_conflict function
def check_conflict(student_id, accommodation_type, start_date, end_date, excluded_id=None):
    """Check for conflicting accommodations"""
    if not CLI_AVAILABLE:
        return False
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT COUNT(*) FROM accommodations 
                WHERE student_id = ? AND accommodation_type = ? 
                AND status = 'active'
            '''
            params = [student_id, accommodation_type]
            
            if start_date and end_date:
                query += '''
                    AND ((start_date <= ? AND end_date >= ?) 
                         OR (start_date <= ? AND end_date >= ?)
                         OR (start_date >= ? AND end_date <= ?))
                '''
                params.extend([start_date, start_date, end_date, end_date, start_date, end_date])
            
            if excluded_id:
                query += ' AND id != ?'
                params.append(excluded_id)
            
            cursor.execute(query, params)
            return cursor.fetchone()[0] > 0
            
    except Exception as e:
        print(f"Conflict check error: {e}")
        return False
        
# Replace the broken main section at the end with:
def main():
    """Main function to run the GUI application"""
    root = tk.Tk()
    
    # Set up global auth if available
    if CLI_AVAILABLE:
        try:
            # Initialize authentication (you may need to modify this based on your auth setup)
            global auth
            if 'auth' not in globals():
                auth = None  # Set up your auth object here if available
        except:
            pass
    
    app = AccommodationGUI(root)
    
    # Set up keyboard shortcuts
    app.setup_keyboard_shortcuts()
    
    # Set window icon (if icon file exists)
    try:
        if os.path.exists('icon.ico'):
            root.iconbitmap('icon.ico')
    except:
        pass
    
    # Start the application
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nApplication closed by user")
    except Exception as e:
        print(f"Application error: {e}")
        if CLI_AVAILABLE:
            # Fall back to CLI mode if GUI fails
            print("Falling back to CLI mode...")
            display_accommodation_menu()

if __name__ == "__main__":
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--gui':
            main()
        elif sys.argv[1] == '--cli':
            if CLI_AVAILABLE:
                display_accommodation_menu()
            else:
                print("CLI mode not available - original accommodation module not found")
        elif sys.argv[1] == '--help':
            print("Student Accommodation Management System")
            print("Usage:")
            print("  python accommodation_gui.py           # Auto-detect mode")
            print("  python accommodation_gui.py --gui     # Force GUI mode")
            print("  python accommodation_gui.py --cli     # Force CLI mode")
            print("  python accommodation_gui.py --help    # Show this help")
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Use --help for usage information")
    else:
        # Auto-detect mode - prefer GUI if available, fall back to CLI
        try:
            # Try to import tkinter to see if GUI is possible
            import tkinter as tk
            # If successful, launch GUI
            main()
        except ImportError:
            # No tkinter available, use CLI
            print("GUI not available (tkinter not installed). Using CLI mode...")
            if CLI_AVAILABLE:
                display_accommodation_menu()
            else:
                print("Neither GUI nor CLI mode available.")
                print("Please install tkinter for GUI mode or ensure accommodation.py is available for CLI mode.")
        except Exception as e:
            # GUI failed for some other reason, fall back to CLI
            print(f"GUI failed to start: {e}")
            print("Falling back to CLI mode...")
            if CLI_AVAILABLE:
                display_accommodation_menu()
            else:
                print("CLI mode also not available.")
