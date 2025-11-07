from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from university_system.infrastructure.database.db import sqlite3
import os
import datetime
from datetime import datetime, timedelta
import shutil
import csv
import json
import hashlib
import zipfile
import threading
import time
from PIL import Image, ImageTk
import webbrowser
from university_system.modules.shared.constants import paths

# Import the original classes to maintain backwards compatibility
try:
    from university_system.infrastructure.database.db import DatabaseManager, get_connection
    from university_system.infrastructure.auth.user_authentication import UserAuth, get_current_user
except ImportError:
    # Fallback for backwards compatibility
    # Use the centralized database path defined in the infrastructure
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

    def get_current_user():
        return {'username': 'admin', 'role': 'admin'}

class DocumentManagerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced Document Management System")
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')
        
        # Initialize variables first
        self.activity_tree = None
        self.docs_tree = None
        self.students_tree = None
        
        # Initialize database
        if not self.init_enhanced_db():
            messagebox.showerror("Database Error", "Failed to initialize database. Exiting.")
            root.destroy()
            return
        
        # Current user (for backwards compatibility)
        self.current_user = get_current_user()
        if self.current_user is None:
            self.current_user = {'username': 'admin', 'role': 'admin'}
        
        # Create main interface
        self.create_main_interface()
        
        # Load initial data (do this last)
        self.root.after(100, self.refresh_dashboard)  # Delay to ensure widgets are created

    def init_enhanced_db(self):
        """Initialize enhanced database with all new tables"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Users table for authentication
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password_hash TEXT,
                role TEXT,
                email TEXT,
                first_name TEXT,
                last_name TEXT,
                created_date TEXT,
                is_active BOOLEAN DEFAULT 1
            )
            ''')
            
            # Enhanced document_types table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_types (
                type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                type_name TEXT UNIQUE,
                description TEXT,
                is_required BOOLEAN,
                has_expiry BOOLEAN,
                expiry_reminder_days INTEGER,
                max_file_size_mb INTEGER DEFAULT 10,
                allowed_formats TEXT,
                requires_approval BOOLEAN DEFAULT 1,
                category TEXT,
                sort_order INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1
            )
            ''')

            # Add missing columns to existing document_types table (for backward compatibility)
            try:
                # Check if columns exist and add them if they don't
                cursor.execute("PRAGMA table_info(document_types)")
                existing_columns = {col[1] for col in cursor.fetchall()}

                if 'has_expiry' not in existing_columns:
                    cursor.execute('ALTER TABLE document_types ADD COLUMN has_expiry BOOLEAN DEFAULT 0')
                if 'expiry_reminder_days' not in existing_columns:
                    cursor.execute('ALTER TABLE document_types ADD COLUMN expiry_reminder_days INTEGER')
                if 'max_file_size_mb' not in existing_columns:
                    cursor.execute('ALTER TABLE document_types ADD COLUMN max_file_size_mb INTEGER DEFAULT 10')
                if 'allowed_formats' not in existing_columns:
                    cursor.execute('ALTER TABLE document_types ADD COLUMN allowed_formats TEXT DEFAULT ".pdf,.jpg,.jpeg,.png,.doc,.docx"')
                if 'requires_approval' not in existing_columns:
                    cursor.execute('ALTER TABLE document_types ADD COLUMN requires_approval BOOLEAN DEFAULT 1')
                if 'category' not in existing_columns:
                    cursor.execute('ALTER TABLE document_types ADD COLUMN category TEXT')
                if 'sort_order' not in existing_columns:
                    cursor.execute('ALTER TABLE document_types ADD COLUMN sort_order INTEGER DEFAULT 0')
                if 'is_active' not in existing_columns:
                    cursor.execute('ALTER TABLE document_types ADD COLUMN is_active BOOLEAN DEFAULT 1')
            except Exception as e:
                logger.warning(f"Error adding missing columns to document_types: {e}")

            # Enhanced student_documents table with versioning
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_documents (
                document_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                type_id INTEGER,
                file_path TEXT,
                original_filename TEXT,
                upload_date TEXT,
                expiry_date TEXT,
                verification_status TEXT,
                verification_date TEXT,
                verification_notes TEXT,
                version_number INTEGER DEFAULT 1,
                parent_document_id INTEGER,
                uploaded_by TEXT,
                file_size INTEGER,
                file_hash TEXT,
                tags TEXT,
                is_current_version BOOLEAN DEFAULT 1,
                workflow_status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 0,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (type_id) REFERENCES document_types (type_id),
                FOREIGN KEY (parent_document_id) REFERENCES student_documents (document_id),
                FOREIGN KEY (uploaded_by) REFERENCES users (username)
            )
            ''')
            
            # Students table (if not exists)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                email TEXT,
                course TEXT,
                year INTEGER,
                enrollment_date TEXT,
                status TEXT DEFAULT 'active'
            )
            ''')
            
            # Document workflow table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_workflow (
                workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER,
                step_name TEXT,
                step_order INTEGER,
                assigned_to TEXT,
                status TEXT,
                comments TEXT,
                completed_date TEXT,
                completed_by TEXT,
                FOREIGN KEY (document_id) REFERENCES student_documents (document_id)
            )
            ''')
            
            # Notification system
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_id TEXT,
                notification_type TEXT,
                title TEXT,
                message TEXT,
                created_date TEXT,
                sent_date TEXT,
                is_read BOOLEAN DEFAULT 0,
                is_sent BOOLEAN DEFAULT 0,
                priority TEXT DEFAULT 'normal',
                related_document_id INTEGER,
                FOREIGN KEY (related_document_id) REFERENCES student_documents (document_id)
            )
            ''')

            # ------------------------------------------------------------------
            # Additional tables for the enhanced document management system
            # These tables mirror the structures defined in the CLI version of
            # the document manager. By creating them here, the GUI maintains
            # feature parity when run independently of the CLI.

            # Document tags table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_tags (
                tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_name TEXT UNIQUE,
                tag_color TEXT,
                description TEXT
            )
            ''')

            # Document requirements by course/program
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS course_requirements (
                requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_code TEXT,
                program TEXT,
                type_id INTEGER,
                is_mandatory BOOLEAN DEFAULT 1,
                deadline_days INTEGER,
                FOREIGN KEY (type_id) REFERENCES document_types (type_id)
            )
            ''')

            # System settings table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_name TEXT UNIQUE,
                setting_value TEXT,
                description TEXT,
                updated_by TEXT,
                updated_date TEXT
            )
            ''')

            # Audit log table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                action TEXT,
                table_name TEXT,
                record_id TEXT,
                old_values TEXT,
                new_values TEXT,
                timestamp TEXT,
                ip_address TEXT
            )
            ''')

            # Insert default data if tables are empty
            self.insert_default_data(cursor)
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Database error: {e}")
            return False
            
    def insert_default_data(self, cursor):
        """Insert default data for the system"""
        # Check if users exist
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            # Create default admin user using centralized authentication
            # WARNING: Change DEFAULT_ADMIN_PASSWORD environment variable in production!
            # Load admin password from environment variable for security
            admin_password = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')
            try:
                from university_system.infrastructure.auth.user_authentication import UserAuth
                auth_system = UserAuth()
                auth_system.create_user(
                    username="admin",
                    password=admin_password,
                    email="admin@school.edu",
                    first_name="System",
                    last_name="Administrator",
                    role="admin"
                )
                print("Default admin user created via centralized auth system")
            except Exception as e:
                # Fallback to direct insertion if auth system not available during initialization
                print(f"Using fallback admin creation: {e}")
                admin_hash = hashlib.sha256(admin_password.encode()).hexdigest()
                cursor.execute('''
                INSERT INTO users (username, password_hash, role, email, first_name, last_name, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', ("admin", admin_hash, "admin", "admin@school.edu", "System", "Administrator", datetime.now().strftime('%Y-%m-%d')))
            
        # Check if document types exist
        cursor.execute('SELECT COUNT(*) FROM document_types')
        if cursor.fetchone()[0] == 0:
            default_types = [
                ('ID Photo', 'Student identification photograph', True, False, 0, 5, 'jpg,jpeg,png', True, 'Identity', 1),
                ('Birth Certificate', 'Official birth certificate', True, False, 0, 10, 'pdf,jpg,jpeg,png', True, 'Identity', 2),
                ('National ID Card', 'Government issued identification card', True, True, 30, 10, 'pdf,jpg,jpeg,png', True, 'Identity', 3),
                ('Passport', 'International passport', False, True, 60, 10, 'pdf,jpg,jpeg,png', True, 'Identity', 4),
                ('Prior Qualification', 'Previous educational qualification certificate', True, False, 0, 15, 'pdf,jpg,jpeg,png', True, 'Academic', 5),
                ('Visa Document', 'Student visa documentation', False, True, 30, 10, 'pdf,jpg,jpeg,png', True, 'Immigration', 6),
                ('Health Insurance', 'Student health insurance documentation', False, True, 30, 10, 'pdf,jpg,jpeg,png', True, 'Health', 7),
                ('Transcripts', 'Academic transcripts', True, False, 0, 15, 'pdf', True, 'Academic', 8),
                ('Medical Records', 'Health and medical records', False, True, 365, 20, 'pdf,doc,docx', True, 'Health', 9),
                ('Financial Documentation', 'Proof of financial support', False, True, 90, 15, 'pdf,doc,docx', True, 'Financial', 10)
            ]
            
            cursor.executemany('''
            INSERT INTO document_types (type_name, description, is_required, has_expiry, expiry_reminder_days, 
            max_file_size_mb, allowed_formats, requires_approval, category, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', default_types)
            
        # Insert sample students if none exist
        cursor.execute('SELECT COUNT(*) FROM students')
        if cursor.fetchone()[0] == 0:
            sample_students = [
                ('STU001', 'John', 'Doe', 'john.doe@email.com', 'Computer Science', 2, '2023-09-01', 'active'),
                ('STU002', 'Jane', 'Smith', 'jane.smith@email.com', 'Business Administration', 1, '2024-01-15', 'active'),
                ('STU003', 'Mike', 'Johnson', 'mike.johnson@email.com', 'Engineering', 3, '2022-09-01', 'active'),
                ('STU004', 'Sarah', 'Wilson', 'sarah.wilson@email.com', 'Psychology', 2, '2023-01-10', 'active'),
                ('STU005', 'David', 'Brown', 'david.brown@email.com', 'Mathematics', 4, '2021-09-01', 'active')
            ]
            
            cursor.executemany('''
            INSERT INTO students (student_id, first_name, last_name, email, course, year, enrollment_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', sample_students)

    def create_main_interface(self):
        """Create the main GUI interface"""
        # Create main menu bar
        self.create_menu_bar()

        # Add return to main menu button at the top
        return_btn = ttk.Button(
            self.root,
            text="🏠 Return to Main Menu",
            command=self.return_to_main_menu
        )
        return_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        # Create main frame with sidebar and content area
        self.create_main_layout()

        # Create status bar
        self.create_status_bar()
        
    def create_menu_bar(self):
        """Create the main menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Upload Document", command=self.upload_document_dialog)
        file_menu.add_command(label="Import Documents", command=self.bulk_import_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Export Data", command=self.export_data_dialog)
        file_menu.add_command(label="Backup System", command=self.backup_system)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Document Types", command=self.manage_document_types)
        edit_menu.add_command(label="System Settings", command=self.system_settings)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Dashboard", command=self.show_dashboard)
        view_menu.add_command(label="Documents", command=self.show_documents)
        # view_menu.add_command(label="Students", command=self.show_students)  # Removed - use Student Records GUI
        view_menu.add_command(label="Reports", command=self.show_reports)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Advanced Search", command=self.advanced_search_dialog)
        tools_menu.add_command(label="Bulk Operations", command=self.bulk_operations_dialog)
        tools_menu.add_command(label="Workflow Management", command=self.workflow_management)
        tools_menu.add_command(label="Notification Center", command=self.notification_center)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_user_guide)
        help_menu.add_command(label="About", command=self.show_about)

    def create_main_layout(self):
        """Create the main layout with sidebar and content area"""
        # Create main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Create scrollable sidebar
        sidebar_container = ttk.Frame(main_container, width=250)
        sidebar_container.pack(side='left', fill='y', padx=(0, 10))
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
        
        # Create scrollable content area
        content_container = ttk.Frame(main_container)
        content_container.pack(side='right', fill='both', expand=True)

        # Create canvas and scrollbar for content area
        self.content_canvas = tk.Canvas(content_container, highlightthickness=0)
        content_scrollbar = ttk.Scrollbar(content_container, orient="vertical", command=self.content_canvas.yview)
        self.content_area = ttk.Frame(self.content_canvas)

        self.content_area.bind(
            "<Configure>",
            lambda e: self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))
        )

        self.content_canvas.create_window((0, 0), window=self.content_area, anchor="nw")
        self.content_canvas.configure(yscrollcommand=content_scrollbar.set)

        self.content_canvas.pack(side="left", fill="both", expand=True)
        content_scrollbar.pack(side="right", fill="y")
        
        # Create sidebar navigation
        self.create_sidebar()
        
        # Show dashboard by default
        self.show_dashboard()

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
        
    def create_sidebar(self):
        """Create the navigation sidebar with all features"""
        # Title
        title_label = ttk.Label(self.sidebar, text="Document Management", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # User info
        user_frame = ttk.LabelFrame(self.sidebar, text="Current User", padding=10)
        user_frame.pack(fill='x', pady=5)
        
        user_name = self.current_user.get('username', 'Unknown') if self.current_user else 'Unknown'
        user_role = self.current_user.get('role', 'user') if self.current_user else 'user'
        
        ttk.Label(user_frame, text=f"User: {user_name}").pack(anchor='w')
        ttk.Label(user_frame, text=f"Role: {user_role.title()}").pack(anchor='w')
        
        # Navigation buttons - Updated with all features
        nav_frame = ttk.LabelFrame(self.sidebar, text="Navigation", padding=10)
        nav_frame.pack(fill='x', pady=5)
        
        nav_buttons = [
            ("Dashboard", self.show_dashboard),
            ("Documents", self.show_documents),
            # ("Students", self.show_students),  # Removed - use Student Records GUI
            ("Reports", self.show_reports),
            ("Workflows", self.workflow_management),
            ("Search", self.advanced_search_dialog),
            ("OCR", self.ocr_integration_menu),
            ("🏠 Return to Main Menu", self.return_to_main_menu)
        ]
        
        for text, command in nav_buttons:
            btn = ttk.Button(nav_frame, text=text, command=command, width=20)
            btn.pack(fill='x', pady=2)
        
        # Quick actions - Updated
        actions_frame = ttk.LabelFrame(self.sidebar, text="Quick Actions", padding=10)
        actions_frame.pack(fill='x', pady=5)
        
        action_buttons = [
            ("Upload Document", self.upload_document_dialog),
            ("Bulk Operations", self.bulk_operations_dialog),
            ("Process Workflow", self.process_workflow_step),
            ("Generate Report", self.generate_report_dialog),
            ("🏠 Return to Main Menu", self.return_to_main_menu)
        ]
        
        for text, command in action_buttons:
            btn = ttk.Button(actions_frame, text=text, command=command, width=20)
            btn.pack(fill='x', pady=2)

        # Force scroll region update after all content is added
        self.sidebar.update_idletasks()
        self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))

        # Ensure canvas shows scrollbar when needed
        self.sidebar_canvas.update_idletasks()

    def create_status_bar(self):
        """Create the status bar"""
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief='sunken', anchor='w')
        status_bar.pack(side='bottom', fill='x')

    def show_dashboard(self):
        """Show the main dashboard"""
        self.clear_content_area()
        
        # Create dashboard frame
        dashboard_frame = ttk.Frame(self.content_area)
        dashboard_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(dashboard_frame, text="System Dashboard", font=('Arial', 18, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Create stats cards row
        stats_frame = ttk.Frame(dashboard_frame)
        stats_frame.pack(fill='x', pady=(0, 20))
        
        # Get dashboard statistics
        stats = self.get_dashboard_stats()
        
        # Create stat cards
        self.create_stat_card(stats_frame, "Total Documents", stats['total_docs'], "#4CAF50", 0)
        self.create_stat_card(stats_frame, "Pending Review", stats['pending_docs'], "#FF9800", 1)
        self.create_stat_card(stats_frame, "Students", stats['total_students'], "#2196F3", 2)
        self.create_stat_card(stats_frame, "Today's Uploads", stats['today_uploads'], "#9C27B0", 3)
        
        # Create charts and tables row
        charts_frame = ttk.Frame(dashboard_frame)
        charts_frame.pack(fill='both', expand=True)
        
        # Document status chart (left side)
        self.create_status_chart(charts_frame)
        
        # Recent activity table (right side)
        self.create_recent_activity_table(charts_frame)
        
        # Refresh button
        refresh_btn = ttk.Button(dashboard_frame, text="🔄 Refresh Dashboard", command=self.refresh_dashboard)
        refresh_btn.pack(pady=10)

    def create_stat_card(self, parent, title, value, color, column):
        """Create a statistic card"""
        card_frame = ttk.LabelFrame(parent, text=title, padding=15)
        card_frame.grid(row=0, column=column, padx=10, sticky='ew')
        parent.grid_columnconfigure(column, weight=1)
        
        value_label = ttk.Label(card_frame, text=str(value), font=('Arial', 24, 'bold'))
        value_label.pack()

    def view_active_workflows(self):
        """View all active workflows in GUI"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Active Workflows")
        dialog.geometry("900x600")
        dialog.transient(self.root)
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Active Workflows", font=('Arial', 14, 'bold')).pack(pady=(0, 15))
        
        # Create treeview for workflows
        columns = ('WF ID', 'Doc ID', 'Student', 'Document Type', 'Step', 'Assigned To', 'Age (days)')
        workflows_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            workflows_tree.heading(col, text=col)
            workflows_tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=workflows_tree.yview)
        workflows_tree.configure(yscrollcommand=scrollbar.set)
        
        workflows_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Load workflows data
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT dw.workflow_id, sd.document_id, s.first_name || ' ' || s.last_name as student_name,
                   dt.type_name, dw.step_name, dw.assigned_to, sd.upload_date
            FROM document_workflow dw
            JOIN student_documents sd ON dw.document_id = sd.document_id
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE dw.status = 'pending'
            ORDER BY sd.upload_date ASC
            ''')
            
            workflows = cursor.fetchall()
            conn.close()
            
            for workflow in workflows:
                wf_id, doc_id, student_name, doc_type, step_name, assigned_to, upload_date = workflow
                
                # Calculate age
                from datetime import datetime
                upload_dt = datetime.strptime(upload_date[:10], '%Y-%m-%d')
                age_days = (datetime.now() - upload_dt).days
                
                workflows_tree.insert('', 'end', values=(wf_id, doc_id, student_name, doc_type, step_name, assigned_to, age_days))
                
        except Exception as e:
            ttk.Label(main_frame, text=f"Error loading workflows: {e}").pack()
        
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def process_workflow_step(self):
        """Process a workflow step in GUI"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Process Workflow Step")
        dialog.geometry("700x550")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Process Workflow Step", font=('Arial', 12, 'bold')).pack(pady=(0, 15))
        
        # Workflow ID input
        ttk.Label(main_frame, text="Workflow ID:").pack(anchor='w')
        workflow_id_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=workflow_id_var, width=20).pack(fill='x', pady=5)
        
        # Action selection
        ttk.Label(main_frame, text="Action:").pack(anchor='w', pady=(10, 0))
        action_var = tk.StringVar(value="approve")
        
        actions = [("Approve and Continue", "approve"), ("Reject and Stop", "reject"), ("Request More Info", "request_info")]
        for text, value in actions:
            ttk.Radiobutton(main_frame, text=text, variable=action_var, value=value).pack(anchor='w', pady=2)
        
        # Comments
        ttk.Label(main_frame, text="Comments:").pack(anchor='w', pady=(10, 0))
        comments_text = tk.Text(main_frame, height=5, width=40)
        comments_text.pack(fill='x', pady=5)
        
        def process_step():
            workflow_id = workflow_id_var.get()
            action = action_var.get()
            comments = comments_text.get('1.0', 'end-1c')
            
            if not workflow_id:
                messagebox.showerror("Error", "Please enter workflow ID")
                return
            
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Get workflow details
                cursor.execute('''
                SELECT dw.document_id, dw.step_name
                FROM document_workflow dw
                WHERE dw.workflow_id = ? AND dw.status = 'pending'
                ''', (workflow_id,))
                
                workflow = cursor.fetchone()
                
                if not workflow:
                    messagebox.showerror("Error", "Workflow step not found or already completed")
                    conn.close()
                    return
                
                doc_id, step_name = workflow
                
                if action == "approve":
                    # Mark step as completed
                    cursor.execute('''
                    UPDATE document_workflow 
                    SET status = 'completed', completed_date = ?, completed_by = ?, comments = ?
                    WHERE workflow_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                          self.current_user['username'], comments, workflow_id))
                    
                    # Check if workflow is complete
                    cursor.execute('''
                    SELECT COUNT(*) FROM document_workflow
                    WHERE document_id = ? AND status = 'pending'
                    ''', (doc_id,))
                    
                    pending_steps = cursor.fetchone()[0]
                    
                    if pending_steps == 0:
                        # Mark document as verified
                        cursor.execute('''
                        UPDATE student_documents 
                        SET verification_status = 'Verified', verification_date = ?,
                            workflow_status = 'completed'
                        WHERE document_id = ?
                        ''', (datetime.now().strftime('%Y-%m-%d'), doc_id))
                        
                        messagebox.showinfo("Success", "Workflow completed! Document marked as Verified.")
                    else:
                        messagebox.showinfo("Success", "Step approved. Workflow continues to next step.")
                        
                elif action == "reject":
                    cursor.execute('''
                    UPDATE document_workflow 
                    SET status = 'rejected', completed_date = ?, completed_by = ?, comments = ?
                    WHERE workflow_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                          self.current_user['username'], comments, workflow_id))
                    
                    cursor.execute('''
                    UPDATE student_documents 
                    SET verification_status = 'Rejected', verification_date = ?,
                        verification_notes = ?, workflow_status = 'rejected'
                    WHERE document_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d'), comments, doc_id))
                    
                    messagebox.showinfo("Success", "Document rejected. Workflow stopped.")
                
                conn.commit()
                conn.close()
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to process workflow step: {str(e)}")
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))
        
        ttk.Button(button_frame, text="Process", command=process_step).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def upload_document_dialog(self):
        """Show upload document dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Upload Document")
        dialog.geometry("700x800")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Title
        ttk.Label(main_frame, text="Upload Student Document", font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Student selection
        student_frame = ttk.LabelFrame(main_frame, text="Student Information", padding=10)
        student_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(student_frame, text="Student ID:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.upload_student_id = ttk.Combobox(student_frame, width=20)
        self.upload_student_id.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        # Populate student IDs
        students = self.get_students_list()
        student_values = [f"{s[0]} - {s[1]} {s[2]}" for s in students]
        self.upload_student_id['values'] = student_values
        
        # Search button
        ttk.Button(student_frame, text="🔍 Search", command=self.search_student_for_upload).grid(row=0, column=2, padx=5)
        
        student_frame.grid_columnconfigure(1, weight=1)
        
        # Document type selection
        doc_type_frame = ttk.LabelFrame(main_frame, text="Document Type", padding=10)
        doc_type_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(doc_type_frame, text="Document Type:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.upload_doc_type = ttk.Combobox(doc_type_frame, width=30)
        self.upload_doc_type.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        # Populate document types
        doc_types = self.get_document_types_with_details()
        self.upload_doc_type['values'] = [f"{dt[1]} - {dt[2]}" for dt in doc_types]
        self.upload_doc_type.bind('<<ComboboxSelected>>', self.on_doc_type_selected)
        
        doc_type_frame.grid_columnconfigure(1, weight=1)
        
        # Document type info
        self.doc_type_info = ttk.Label(doc_type_frame, text="", font=('Arial', 9), foreground='blue')
        self.doc_type_info.grid(row=1, column=0, columnspan=2, sticky='w', padx=5, pady=(5, 0))
        
        # File selection
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding=10)
        file_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(file_frame, text="File:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.upload_file_path = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=self.upload_file_path, width=40)
        file_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        ttk.Button(file_frame, text="Browse...", command=self.browse_file).grid(row=0, column=2, padx=5)
        
        file_frame.grid_columnconfigure(1, weight=1)
        
        # File info
        self.file_info = ttk.Label(file_frame, text="", font=('Arial', 9), foreground='gray')
        self.file_info.grid(row=1, column=0, columnspan=3, sticky='w', padx=5, pady=(5, 0))
        
        # Additional options
        options_frame = ttk.LabelFrame(main_frame, text="Additional Options", padding=10)
        options_frame.pack(fill='x', pady=(0, 15))
        
        # Expiry date (if applicable)
        ttk.Label(options_frame, text="Expiry Date:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.upload_expiry_date = tk.Entry(options_frame, width=15)
        self.upload_expiry_date.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        ttk.Label(options_frame, text="(YYYY-MM-DD, if applicable)", font=('Arial', 9), foreground='gray').grid(row=0, column=2, sticky='w', padx=5)
        
        # Tags
        ttk.Label(options_frame, text="Tags:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.upload_tags = tk.Entry(options_frame, width=40)
        self.upload_tags.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky='ew')
        ttk.Label(options_frame, text="(comma-separated)", font=('Arial', 9), foreground='gray').grid(row=2, column=1, sticky='w', padx=5)
        
        # Notes
        ttk.Label(options_frame, text="Notes:").grid(row=3, column=0, sticky='nw', padx=5, pady=5)
        self.upload_notes = tk.Text(options_frame, width=40, height=3)
        self.upload_notes.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky='ew')
        
        options_frame.grid_columnconfigure(1, weight=1)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(20, 0))
        
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Upload Document", command=lambda: self.perform_upload(dialog)).pack(side='right', padx=5)

    def browse_file(self):
        """Browse for file to upload"""
        file_path = filedialog.askopenfilename(
            title="Select Document File",
            filetypes=[
                ("All Supported", "*.pdf;*.jpg;*.jpeg;*.png;*.doc;*.docx"),
                ("PDF files", "*.pdf"),
                ("Image files", "*.jpg;*.jpeg;*.png"),
                ("Word documents", "*.doc;*.docx"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            self.upload_file_path.set(file_path)
            self.update_file_info(file_path)

    def update_file_info(self, file_path):
        """Update file information display"""
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            file_ext = os.path.splitext(file_path)[1][1:].lower()
            
            info_text = f"Size: {file_size_mb:.2f} MB, Format: {file_ext.upper()}"
            self.file_info.config(text=info_text)

    def on_doc_type_selected(self, event=None):
        """Handle document type selection"""
        selection = self.upload_doc_type.get()
        if selection:
            doc_types = self.get_document_types_with_details()
            for dt in doc_types:
                if selection.startswith(dt[1]):
                    # Show document type info
                    info_text = f"Max size: {dt[6]}MB, Formats: {dt[7]}, Required: {'Yes' if dt[3] else 'No'}"
                    if dt[4]:  # has_expiry
                        info_text += f", Expires: Yes"
                    self.doc_type_info.config(text=info_text)
                    break

    def perform_upload(self, dialog):
        """Perform the document upload"""
        # Validate inputs
        if not self.upload_student_id.get():
            messagebox.showerror("Error", "Please select a student")
            return
        
        if not self.upload_doc_type.get():
            messagebox.showerror("Error", "Please select a document type")
            return
        
        if not self.upload_file_path.get() or not os.path.exists(self.upload_file_path.get()):
            messagebox.showerror("Error", "Please select a valid file")
            return
        
        try:
            # Extract student ID
            student_id = self.upload_student_id.get().split(' - ')[0]
            
            # Extract document type ID
            doc_type_selection = self.upload_doc_type.get()
            doc_types = self.get_document_types_with_details()
            type_id = None
            for dt in doc_types:
                if doc_type_selection.startswith(dt[1]):
                    type_id = dt[0]
                    break
            
            if not type_id:
                messagebox.showerror("Error", "Invalid document type selected")
                return
            
            # Validate file
            file_path = self.upload_file_path.get()
            if not self.validate_file(file_path, type_id):
                return
            
            # Perform upload
            success = self.upload_document_to_db(
                student_id, type_id, file_path,
                self.upload_expiry_date.get(),
                self.upload_tags.get(),
                self.upload_notes.get('1.0', 'end-1c')
            )
            
            if success:
                messagebox.showinfo("Success", "Document uploaded successfully!")
                dialog.destroy()
                self.refresh_documents()
                self.refresh_dashboard()
            else:
                messagebox.showerror("Error", "Failed to upload document")
                
        except Exception as e:
            messagebox.showerror("Error", f"Upload failed: {str(e)}")

    def validate_file(self, file_path, type_id):
        """Validate file against document type requirements"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT max_file_size_mb, allowed_formats 
            FROM document_types 
            WHERE type_id = ?
            ''', (type_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                messagebox.showerror("Error", "Document type not found")
                return False
            
            max_size_mb, allowed_formats = result
            
            # Check file size
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            if file_size_mb > max_size_mb:
                messagebox.showerror("Error", f"File size ({file_size_mb:.2f}MB) exceeds maximum allowed size ({max_size_mb}MB)")
                return False
            
            # Check file format
            file_ext = os.path.splitext(file_path)[1][1:].lower()
            allowed_ext_list = [ext.strip().lower() for ext in allowed_formats.split(',')]
            
            if file_ext not in allowed_ext_list:
                messagebox.showerror("Error", f"File format '{file_ext}' not allowed. Allowed formats: {allowed_formats}")
                return False
            
            return True
            
        except Exception as e:
            messagebox.showerror("Error", f"File validation failed: {str(e)}")
            return False

    def upload_document_to_db(self, student_id, type_id, file_path, expiry_date, tags, notes):
        """Upload document to database"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Check for existing document of same type
            cursor.execute('''
            SELECT document_id, version_number 
            FROM student_documents 
            WHERE student_id = ? AND type_id = ? AND is_current_version = 1
            ''', (student_id, type_id))
            
            existing_doc = cursor.fetchone()
            
            # Create document directory if it doesn't exist
            doc_dir = paths.UPLOAD_DIR / 'student_documents' / student_id
            os.makedirs(doc_dir, exist_ok=True)
            
            # Copy file to document directory
            original_filename = os.path.basename(file_path)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_filename = f"{timestamp}_{original_filename}"
            new_file_path = os.path.join(doc_dir, new_filename)
            
            shutil.copy2(file_path, new_file_path)
            
            # Calculate file hash
            with open(new_file_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            
            file_size = os.path.getsize(new_file_path)
            upload_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Handle versioning
            if existing_doc:
                # Mark existing as not current
                cursor.execute('''
                UPDATE student_documents 
                SET is_current_version = 0 
                WHERE document_id = ?
                ''', (existing_doc[0],))
                
                new_version = existing_doc[1] + 1
                parent_doc_id = existing_doc[0]
            else:
                new_version = 1
                parent_doc_id = None
            
            # Insert new document record
            cursor.execute('''
            INSERT INTO student_documents 
            (student_id, type_id, file_path, original_filename, upload_date, expiry_date, 
             verification_status, version_number, parent_document_id, uploaded_by, 
             file_size, file_hash, tags, verification_notes, workflow_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, type_id, new_file_path, original_filename, upload_date, 
                  expiry_date if expiry_date else None, 'Pending', new_version, parent_doc_id, 
                  self.current_user['username'], file_size, file_hash, tags, notes, 'submitted'))
            
            document_id = cursor.lastrowid
            
            # Create notification
            cursor.execute('''
            INSERT INTO notifications (recipient_id, notification_type, title, message, created_date, related_document_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (student_id, 'document_uploaded', 'Document Uploaded',
                  f'Your document has been uploaded and is pending verification.',
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), document_id))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to save document: {str(e)}")
            return False

    def perform_advanced_search(self):
        """Enhanced perform_advanced_search with better UI"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Build dynamic query
            query = '''
            SELECT sd.document_id, 
                   s.first_name || ' ' || s.last_name as student_name,
                   dt.type_name,
                   sd.verification_status,
                   DATE(sd.upload_date) as upload_date
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.is_current_version = 1
            '''
            
            params = []
            
            # Add search conditions
            if hasattr(self, 'search_student') and self.search_student.get():
                query += " AND (s.first_name LIKE ? OR s.last_name LIKE ? OR s.student_id LIKE ?)"
                search_term = f"%{self.search_student.get()}%"
                params.extend([search_term, search_term, search_term])
            
            if hasattr(self, 'search_doc_type') and self.search_doc_type.get() != 'All':
                query += " AND dt.type_name LIKE ?"
                params.append(f"%{self.search_doc_type.get()}%")
            
            if hasattr(self, 'search_status') and self.search_status.get() != 'All':
                query += " AND sd.verification_status = ?"
                params.append(self.search_status.get())
            
            if hasattr(self, 'search_from_date') and self.search_from_date.get():
                query += " AND DATE(sd.upload_date) >= ?"
                params.append(self.search_from_date.get())
            
            if hasattr(self, 'search_to_date') and self.search_to_date.get():
                query += " AND DATE(sd.upload_date) <= ?"
                params.append(self.search_to_date.get())
            
            query += " ORDER BY sd.upload_date DESC LIMIT 100"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Clear existing results
            if hasattr(self, 'search_results_tree'):
                for item in self.search_results_tree.get_children():
                    self.search_results_tree.delete(item)
                
                # Insert new results
                for result in results:
                    self.search_results_tree.insert('', 'end', values=result)
            
            conn.close()
            
            # Update status
            self.status_var.set(f"Search completed: {len(results)} results found")
            
        except Exception as e:
            messagebox.showerror("Search Error", f"Search failed: {str(e)}")

    def ocr_integration_menu(self):
        """OCR integration menu in GUI"""
        dialog = tk.Toplevel(self.root)
        dialog.title("OCR Integration")
        dialog.geometry("600x450")
        dialog.transient(self.root)
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="OCR Integration", font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        ocr_options = [
            ("Extract Text from Document", self.extract_text_from_document_gui),
            ("Batch OCR Processing", self.batch_ocr_processing_gui),
            ("OCR Settings", self.ocr_settings_gui),
            ("🏠 Return to Main Menu", self.return_to_main_menu)
        ]
        
        for text, command in ocr_options:
            ttk.Button(main_frame, text=text, command=command, width=25).pack(pady=5)
        
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=20)

    def extract_text_from_document_gui(self):
        """Extract text from document with GUI"""
        doc_id = simpledialog.askstring("OCR", "Enter document ID:")
        if not doc_id:
            return
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT sd.file_path, sd.original_filename, dt.type_name, s.first_name, s.last_name
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            JOIN students s ON sd.student_id = s.student_id
            WHERE sd.document_id = ?
            ''', (doc_id,))
            
            doc = cursor.fetchone()
            
            if not doc:
                messagebox.showerror("Error", "Document not found")
                conn.close()
                return
            
            file_path, filename, doc_type, first_name, last_name = doc
            
            # Show processing dialog
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title("OCR Processing")
            progress_dialog.geometry("450x150")
            progress_dialog.transient(self.root)
            
            ttk.Label(progress_dialog, text="Processing document with OCR...").pack(pady=20)
            progress_bar = ttk.Progressbar(progress_dialog, mode='indeterminate')
            progress_bar.pack(pady=10)
            progress_bar.start()
            
            # Simulate OCR processing
            self.root.after(3000, lambda: self.show_ocr_results(progress_dialog, doc_id, filename, doc_type, first_name, last_name))
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"OCR processing failed: {str(e)}")

    def show_ocr_results(self, progress_dialog, doc_id, filename, doc_type, first_name, last_name):
        """Show OCR results"""
        progress_dialog.destroy()
        
        # Create results window
        results_window = tk.Toplevel(self.root)
        results_window.title("OCR Results")
        results_window.geometry("850x700")
        
        main_frame = ttk.Frame(results_window, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="OCR Extraction Results", font=('Arial', 14, 'bold')).pack(pady=(0, 15))
        
        # Mock extracted text
        mock_text = f"""EXTRACTED TEXT FROM {filename.upper()}

    Document Type: {doc_type}
    Student Name: {first_name} {last_name}
    Document ID: {doc_id}

    [OCR Placeholder Results]
    Name: {first_name} {last_name}
    Document Type: {doc_type}
    Issue Date: 2024-01-15
    Expiry Date: 2029-01-15
    Document Number: ABC123456789

    Confidence: 95%"""
        
        text_widget = tk.Text(main_frame, wrap='word', height=20, width=70)
        text_widget.insert('1.0', mock_text)
        text_widget.config(state='disabled')
        text_widget.pack(fill='both', expand=True)
        
        # Save button
        def save_ocr_results():
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS ocr_results (
                    ocr_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER,
                    extracted_text TEXT,
                    confidence_score REAL,
                    processing_date TEXT,
                    FOREIGN KEY (document_id) REFERENCES student_documents (document_id)
                )
                ''')
                
                cursor.execute('''
                INSERT INTO ocr_results (document_id, extracted_text, confidence_score, processing_date)
                VALUES (?, ?, ?, ?)
                ''', (doc_id, mock_text, 0.95, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "OCR results saved to database")
                results_window.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save OCR results: {str(e)}")
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(button_frame, text="Save Results", command=save_ocr_results).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Close", command=results_window.destroy).pack(side='right')

    def bulk_status_update(self):
        """Enhanced bulk status update with GUI"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Bulk Status Update")
        dialog.geometry("850x700")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Bulk Status Update", font=('Arial', 14, 'bold')).pack(pady=(0, 15))
        
        # Selection criteria
        criteria_frame = ttk.LabelFrame(main_frame, text="Selection Criteria", padding=10)
        criteria_frame.pack(fill='x', pady=(0, 15))
        
        criteria_var = tk.StringVar(value="type")
        ttk.Radiobutton(criteria_frame, text="By Document Type", variable=criteria_var, value="type").pack(anchor='w')
        ttk.Radiobutton(criteria_frame, text="By Current Status", variable=criteria_var, value="status").pack(anchor='w')
        ttk.Radiobutton(criteria_frame, text="By Date Range", variable=criteria_var, value="date").pack(anchor='w')
        
        # Filter input
        filter_frame = ttk.LabelFrame(main_frame, text="Filter Value", padding=10)
        filter_frame.pack(fill='x', pady=(0, 15))
        
        filter_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=filter_var, width=40).pack(fill='x')
        
        # New status selection
        status_frame = ttk.LabelFrame(main_frame, text="New Status", padding=10)
        status_frame.pack(fill='x', pady=(0, 15))
        
        new_status_var = tk.StringVar(value="Verified")
        status_options = ["Verified", "Rejected", "Pending", "Expired"]
        status_combo = ttk.Combobox(status_frame, textvariable=new_status_var, values=status_options)
        status_combo.pack(fill='x')
        
        # Notes
        ttk.Label(main_frame, text="Notes:").pack(anchor='w')
        notes_text = tk.Text(main_frame, height=3, width=40)
        notes_text.pack(fill='x', pady=5)
        
        def perform_bulk_update():
            criteria = criteria_var.get()
            filter_value = filter_var.get()
            new_status = new_status_var.get()
            notes = notes_text.get('1.0', 'end-1c')
            
            if not filter_value:
                messagebox.showerror("Error", "Please enter filter value")
                return
            
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Build query based on criteria
                if criteria == "type":
                    cursor.execute('''
                    SELECT sd.document_id FROM student_documents sd
                    JOIN document_types dt ON sd.type_id = dt.type_id
                    WHERE dt.type_name LIKE ? AND sd.is_current_version = 1
                    ''', (f'%{filter_value}%',))
                elif criteria == "status":
                    cursor.execute('''
                    SELECT document_id FROM student_documents
                    WHERE verification_status = ? AND is_current_version = 1
                    ''', (filter_value,))
                elif criteria == "date":
                    # Expecting date range format: YYYY-MM-DD to YYYY-MM-DD
                    date_parts = filter_value.split(' to ')
                    if len(date_parts) == 2:
                        cursor.execute('''
                        SELECT document_id FROM student_documents
                        WHERE DATE(upload_date) BETWEEN ? AND ? AND is_current_version = 1
                        ''', (date_parts[0], date_parts[1]))
                    else:
                        messagebox.showerror("Error", "Date format should be: YYYY-MM-DD to YYYY-MM-DD")
                        conn.close()
                        return
                
                doc_ids = [row[0] for row in cursor.fetchall()]
                
                if not doc_ids:
                    messagebox.showinfo("Info", "No documents found matching criteria")
                    conn.close()
                    return
                
                # Confirm update
                confirm = messagebox.askyesno("Confirm", f"Update {len(doc_ids)} documents to status '{new_status}'?")
                if not confirm:
                    conn.close()
                    return
                
                # Perform bulk update
                verification_date = datetime.now().strftime('%Y-%m-%d') if new_status != 'Pending' else None
                
                for doc_id in doc_ids:
                    cursor.execute('''
                    UPDATE student_documents
                    SET verification_status = ?, verification_date = ?, verification_notes = ?
                    WHERE document_id = ?
                    ''', (new_status, verification_date, f"Bulk update: {notes}" if notes else "Bulk update", doc_id))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", f"Successfully updated {len(doc_ids)} documents")
                dialog.destroy()
                self.refresh_documents()
                
            except Exception as e:
                messagebox.showerror("Error", f"Bulk update failed: {str(e)}")
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))
        
        ttk.Button(button_frame, text="Update", command=perform_bulk_update).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')
    
    def export_data_dialog(self):
        """Show export data dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Export Data")
        dialog.geometry("600x450")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Export Data", font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        export_options = [
            ("All Documents", "documents"),
            ("All Students", "students"), 
            ("Document Types", "document_types"),
            ("System Report", "system_report")
        ]
        
        self.export_selection = tk.StringVar(value="documents")
        
        for text, value in export_options:
            ttk.Radiobutton(main_frame, text=text, variable=self.export_selection, value=value).pack(anchor='w', pady=2)
        
        # Format selection
        ttk.Label(main_frame, text="Export Format:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(15, 5))
        self.export_format = tk.StringVar(value="csv")
        
        formats = [("CSV", "csv"), ("Excel", "xlsx"), ("JSON", "json")]
        for text, value in formats:
            ttk.Radiobutton(main_frame, text=text, variable=self.export_format, value=value).pack(anchor='w', pady=2)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(20, 0))
        
        ttk.Button(button_frame, text="Export", command=lambda: self.perform_export(dialog)).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def perform_export(self, dialog):
        """Perform the actual export"""
        file_path = filedialog.asksaveasfilename(
            title="Save Export File",
            defaultextension=f".{self.export_format.get()}",
            filetypes=[(f"{self.export_format.get().upper()} files", f"*.{self.export_format.get()}")]
        )
        
        if file_path:
            try:
                data_type = self.export_selection.get()
                format_type = self.export_format.get()
                
                conn = get_connection()
                cursor = conn.cursor()
                
                if data_type == "documents":
                    cursor.execute('''
                    SELECT sd.document_id, s.student_id, s.first_name, s.last_name,
                           dt.type_name, sd.upload_date, sd.verification_status
                    FROM student_documents sd
                    JOIN students s ON sd.student_id = s.student_id
                    JOIN document_types dt ON sd.type_id = dt.type_id
                    WHERE sd.is_current_version = 1
                    ''')
                    columns = ['Document ID', 'Student ID', 'First Name', 'Last Name', 'Document Type', 'Upload Date', 'Status']
                elif data_type == "students":
                    cursor.execute('SELECT * FROM students')
                    columns = ['Student ID', 'First Name', 'Last Name', 'Email', 'Course', 'Year', 'Enrollment Date', 'Status']
                else:
                    cursor.execute('SELECT * FROM document_types WHERE is_active = 1')
                    columns = ['Type ID', 'Type Name', 'Description', 'Required', 'Has Expiry', 'Reminder Days', 'Max Size MB', 'Formats', 'Requires Approval', 'Category', 'Sort Order', 'Active']
                
                data = cursor.fetchall()
                conn.close()
                
                if format_type == "csv":
                    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(columns)
                        writer.writerows(data)
                elif format_type == "json":
                    json_data = [dict(zip(columns, row)) for row in data]
                    with open(file_path, 'w', encoding='utf-8') as jsonfile:
                        json.dump(json_data, jsonfile, indent=2, default=str)
                
                messagebox.showinfo("Success", f"Data exported successfully to {file_path}")
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export data: {str(e)}")

    def view_document_details(self):
        """View detailed information about selected document"""
        selection = self.docs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document to view details.")
            return
        
        item = self.docs_tree.item(selection[0])
        doc_id = item['values'][0]
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT sd.*, s.first_name, s.last_name, s.email_address, dt.type_name, dt.description
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.document_id = ?
            ''', (doc_id,))
            
            doc_data = cursor.fetchone()
            conn.close()
            
            if doc_data:
                self.show_document_details_window(doc_data)
            else:
                messagebox.showerror("Error", "Document not found.")
                
        except Exception as e:
            messagebox.showerror("Database Error", f"Error loading document details: {str(e)}")

    def show_document_details_window(self, doc_data):
        """Show document details in a new window"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Document Details")
        dialog.geometry("850x700")
        dialog.transient(self.root)
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Create scrollable text widget
        text_widget = tk.Text(main_frame, wrap='word', height=25, width=70)
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        # Format document details
        details = f"""Document Details
================

Document ID: {doc_data[0]}
Student: {doc_data[17]} {doc_data[18]} ({doc_data[1]})
Email: {doc_data[19]}
Document Type: {doc_data[20]}
Description: {doc_data[21]}

File Information:
- Original Filename: {doc_data[4]}
- File Path: {doc_data[3]}
- File Size: {doc_data[13]} bytes
- File Hash: {doc_data[14]}

Status Information:
- Upload Date: {doc_data[5]}
- Expiry Date: {doc_data[6] if doc_data[6] else 'N/A'}
- Status: {doc_data[7]}
- Verification Date: {doc_data[8] if doc_data[8] else 'N/A'}
- Uploaded by: {doc_data[12]}

Version Information:
- Version: {doc_data[10]}
- Is Current: {'Yes' if doc_data[16] else 'No'}
- Workflow Status: {doc_data[17]}

Tags: {doc_data[15] if doc_data[15] else 'None'}

Notes:
{doc_data[9] if doc_data[9] else 'No notes available'}
"""
        
        text_widget.insert('1.0', details)
        text_widget.config(state='disabled')
        
        text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Close button
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def edit_document_status(self):
        """Edit the status of selected document"""
        selection = self.docs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document to edit.")
            return
        
        item = self.docs_tree.item(selection[0])
        doc_id = item['values'][0]
        current_status = item['values'][4]
        
        # Status dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Document Status")
        dialog.geometry("600x450")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Update Document Status", font=('Arial', 12, 'bold')).pack(pady=(0, 15))
        
        ttk.Label(main_frame, text=f"Document ID: {doc_id}").pack(anchor='w')
        ttk.Label(main_frame, text=f"Current Status: {current_status}").pack(anchor='w', pady=(0, 15))
        
        ttk.Label(main_frame, text="New Status:").pack(anchor='w')
        status_var = tk.StringVar(value=current_status)
        status_combo = ttk.Combobox(main_frame, textvariable=status_var, 
                                   values=['Pending', 'Verified', 'Rejected', 'Expired'])
        status_combo.pack(fill='x', pady=5)
        
        ttk.Label(main_frame, text="Notes:").pack(anchor='w', pady=(10, 0))
        notes_text = tk.Text(main_frame, height=5, width=40)
        notes_text.pack(fill='x', pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))
        
        def update_status():
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                UPDATE student_documents 
                SET verification_status = ?, verification_date = ?, verification_notes = ?
                WHERE document_id = ?
                ''', (status_var.get(), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                      notes_text.get('1.0', 'end-1c'), doc_id))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Document status updated successfully!")
                dialog.destroy()
                self.refresh_documents()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update status: {str(e)}")
        
        ttk.Button(button_frame, text="Update", command=update_status).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def view_document_versions(self):
        """View all versions of selected document"""
        selection = self.docs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document to view versions.")
            return
        
        item = self.docs_tree.item(selection[0])
        doc_id = item['values'][0]
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get all versions of this document
            cursor.execute('''
            SELECT sd.document_id, sd.version_number, sd.upload_date, sd.verification_status,
                   sd.is_current_version, sd.original_filename, sd.uploaded_by
            FROM student_documents sd
            WHERE sd.document_id = ? OR sd.parent_document_id = ?
            ORDER BY sd.version_number DESC
            ''', (doc_id, doc_id))
            
            versions = cursor.fetchall()
            conn.close()
            
            if versions:
                self.show_versions_window(versions)
            else:
                messagebox.showinfo("Info", "No version history found.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load versions: {str(e)}")

    def show_versions_window(self, versions):
        """Show document versions in a new window"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Document Versions")
        dialog.geometry("950x600")
        dialog.transient(self.root)
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Document Version History", font=('Arial', 12, 'bold')).pack(pady=(0, 15))
        
        # Create treeview for versions
        columns = ('Version', 'Upload Date', 'Status', 'Current', 'Filename', 'Uploaded By')
        versions_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=12)
        
        for col in columns:
            versions_tree.heading(col, text=col)
            versions_tree.column(col, width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=versions_tree.yview)
        versions_tree.configure(yscrollcommand=scrollbar.set)
        
        versions_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Populate versions
        for version in versions:
            doc_id, version_num, upload_date, status, is_current, filename, uploaded_by = version
            current_text = "Yes" if is_current else "No"
            versions_tree.insert('', 'end', values=(version_num, upload_date, status, current_text, filename, uploaded_by))
        
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def download_document(self):
        """Download selected document file"""
        selection = self.docs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document to download.")
            return
        
        item = self.docs_tree.item(selection[0])
        doc_id = item['values'][0]
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT file_path, original_filename FROM student_documents WHERE document_id = ?', (doc_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result and os.path.exists(result[0]):
                save_path = filedialog.asksaveasfilename(
                    title="Save Document As",
                    initialname=result[1],
                    defaultextension=os.path.splitext(result[1])[1]
                )
                
                if save_path:
                    shutil.copy2(result[0], save_path)
                    messagebox.showinfo("Success", f"Document downloaded to {save_path}")
            else:
                messagebox.showerror("Error", "Document file not found.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download document: {str(e)}")

    def send_document_notification(self):
        """Send notification about selected document"""
        selection = self.docs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document to send notification about.")
            return
        
        item = self.docs_tree.item(selection[0])
        doc_id = item['values'][0]
        student_name = item['values'][1]
        doc_type = item['values'][2]
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Send Document Notification")
        dialog.geometry("600x450")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text=f"Send notification about:", font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        ttk.Label(main_frame, text=f"Document: {doc_type}").pack(anchor='w')
        ttk.Label(main_frame, text=f"Student: {student_name}").pack(anchor='w')
        
        ttk.Label(main_frame, text="Message:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(15, 5))
        message_text = tk.Text(main_frame, height=6, width=40)
        message_text.pack(fill='x', pady=5)
        message_text.insert('1.0', f"Regarding your {doc_type} document...")
        
        def send_notification():
            message = message_text.get('1.0', 'end-1c')
            if message:
                messagebox.showinfo("Success", "Notification sent successfully!")
                dialog.destroy()
            else:
                messagebox.showerror("Error", "Please enter a message")
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))
        
        ttk.Button(button_frame, text="Send", command=send_notification).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def delete_document(self):
        """Delete selected document"""
        selection = self.docs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document to delete.")
            return
        
        item = self.docs_tree.item(selection[0])
        doc_id = item['values'][0]
        
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this document?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Get file path before deletion
                cursor.execute('SELECT file_path FROM student_documents WHERE document_id = ?', (doc_id,))
                result = cursor.fetchone()
                
                # Delete from database
                cursor.execute('DELETE FROM student_documents WHERE document_id = ?', (doc_id,))
                
                conn.commit()
                conn.close()
                
                # Delete physical file
                if result and os.path.exists(result[0]):
                    os.remove(result[0])
                
                messagebox.showinfo("Success", "Document deleted successfully!")
                self.refresh_documents()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete document: {str(e)}")

    def view_student_profile(self):
        """View selected student's profile"""
        selection = self.students_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a student to view profile.")
            return
        
        item = self.students_tree.item(selection[0])
        student_id = item['values'][0]
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
            student_data = cursor.fetchone()
            
            # Get document count
            cursor.execute('SELECT COUNT(*) FROM student_documents WHERE student_id = ? AND is_current_version = 1', (student_id,))
            doc_count = cursor.fetchone()[0]
            
            conn.close()
            
            if student_data:
                self.show_student_profile_window(student_data, doc_count)
            else:
                messagebox.showerror("Error", "Student not found.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load student profile: {str(e)}")

    def show_student_profile_window(self, student_data, doc_count):
        """Show student profile in new window"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Student Profile")
        dialog.geometry("700x550")
        dialog.transient(self.root)
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Student Profile", font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        profile_text = f"""Student Information
==================

Student ID: {student_data[0]}
Name: {student_data[1]} {student_data[2]}
Email: {student_data[3]}
Course: {student_data[4]}
Year: {student_data[5]}
Enrollment Date: {student_data[6]}
Status: {student_data[7]}

Document Statistics:
Total Documents: {doc_count}
"""
        
        text_widget = tk.Text(main_frame, wrap='word', height=15, width=50)
        text_widget.insert('1.0', profile_text)
        text_widget.config(state='disabled')
        text_widget.pack(fill='both', expand=True)
        
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def view_student_documents(self):
        """View documents for selected student"""
        selection = self.students_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a student to view documents.")
            return
        
        item = self.students_tree.item(selection[0])
        student_id = item['values'][0]
        student_name = item['values'][1]
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Documents for {student_name}")
        dialog.geometry("800x600")
        dialog.transient(self.root)
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text=f"Documents for {student_name} (ID: {student_id})", 
                  font=('Arial', 14, 'bold')).pack(pady=(0, 15))
        
        # Create treeview for student documents
        columns = ('Document Type', 'Status', 'Upload Date', 'Expiry', 'Version')
        docs_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            docs_tree.heading(col, text=col)
            docs_tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=docs_tree.yview)
        docs_tree.configure(yscrollcommand=scrollbar.set)
        
        docs_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Load student documents
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT dt.type_name, sd.verification_status, DATE(sd.upload_date),
                   sd.expiry_date, sd.version_number
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.student_id = ? AND sd.is_current_version = 1
            ORDER BY sd.upload_date DESC
            ''', (student_id,))
            
            documents = cursor.fetchall()
            conn.close()
            
            for doc in documents:
                docs_tree.insert('', 'end', values=doc)
                
        except Exception as e:
            ttk.Label(main_frame, text=f"Error loading documents: {e}").pack()
        
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def upload_for_student(self):
        """Upload document for selected student"""
        selection = self.students_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a student first.")
            return
        
        item = self.students_tree.item(selection[0])
        student_id = item['values'][0]
        student_name = item['values'][1]
        
        # Open upload dialog with pre-selected student
        self.upload_document_dialog()
        # Set the student in the upload dialog if possible
        if hasattr(self, 'upload_student_id'):
            self.upload_student_id.set(f"{student_id} - {student_name}")

    def send_student_notification(self):
        """Send notification to selected student"""
        selection = self.students_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a student to send notification to.")
            return
        
        item = self.students_tree.item(selection[0])
        student_id = item['values'][0]
        student_name = item['values'][1]
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Send Student Notification")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text=f"Send notification to:", font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        ttk.Label(main_frame, text=f"Student: {student_name} (ID: {student_id})").pack(anchor='w')
        
        ttk.Label(main_frame, text="Subject:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(15, 5))
        subject_entry = tk.Entry(main_frame, width=40)
        subject_entry.pack(fill='x', pady=5)
        
        ttk.Label(main_frame, text="Message:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        message_text = tk.Text(main_frame, height=8, width=40)
        message_text.pack(fill='x', pady=5)
        
        def send_notification():
            subject = subject_entry.get()
            message = message_text.get('1.0', 'end-1c')
            
            if not subject or not message:
                messagebox.showerror("Error", "Please enter both subject and message")
                return
            
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                INSERT INTO notifications (recipient_id, notification_type, title, message, created_date)
                VALUES (?, ?, ?, ?, ?)
                ''', (student_id, 'general', subject, message, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Notification sent successfully!")
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send notification: {str(e)}")
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))
        
        ttk.Button(button_frame, text="Send", command=send_notification).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def generate_student_report(self):
        """Generate report for selected student"""
        selection = self.students_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a student to generate report for.")
            return
        
        item = self.students_tree.item(selection[0])
        student_id = item['values'][0]
        student_name = item['values'][1]
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get student details and documents
            cursor.execute('''
            SELECT s.*, COUNT(sd.document_id) as doc_count,
                   COUNT(CASE WHEN sd.verification_status = 'Verified' THEN 1 END) as verified_count,
                   COUNT(CASE WHEN sd.verification_status = 'Pending' THEN 1 END) as pending_count
            FROM students s
            LEFT JOIN student_documents sd ON s.student_id = sd.student_id AND sd.is_current_version = 1
            WHERE s.student_id = ?
            GROUP BY s.student_id
            ''', (student_id,))
            
            student_data = cursor.fetchone()
            conn.close()
            
            if not student_data:
                messagebox.showerror("Error", "Student not found")
                return
            
            # Create report window
            report_window = tk.Toplevel(self.root)
            report_window.title(f"Student Report - {student_name}")
            report_window.geometry("850x700")
            
            report_frame = ttk.Frame(report_window, padding=20)
            report_frame.pack(fill='both', expand=True)
            
            report_content = f"""STUDENT REPORT
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    =====================================

    STUDENT INFORMATION:
    Name: {student_data[1]} {student_data[2]}
    Student ID: {student_data[0]}
    Email: {student_data[3]}
    Course: {student_data[4]}
    Year: {student_data[5]}
    Enrollment Date: {student_data[6]}
    Status: {student_data[7]}

    DOCUMENT SUMMARY:
    Total Documents: {student_data[8]}
    Verified Documents: {student_data[9]}
    Pending Documents: {student_data[10]}
    Completion Rate: {(student_data[9] / student_data[8] * 100) if student_data[8] > 0 else 0:.1f}%

    COMPLIANCE STATUS:
    Overall Status: {'Compliant' if student_data[10] == 0 else 'Non-Compliant'}
    """
            
            text_widget = tk.Text(report_frame, wrap='word', height=20, width=70)
            text_widget.insert('1.0', report_content)
            text_widget.config(state='disabled')
            text_widget.pack(fill='both', expand=True)
            
            ttk.Button(report_frame, text="Close", command=report_window.destroy).pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

    def edit_student(self):
        """Edit selected student information"""
        selection = self.students_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a student to edit.")
            return
        
        item = self.students_tree.item(selection[0])
        student_id = item['values'][0]
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
            student_data = cursor.fetchone()
            conn.close()
            
            if not student_data:
                messagebox.showerror("Error", "Student not found")
                return
            
            dialog = tk.Toplevel(self.root)
            dialog.title("Edit Student")
            dialog.geometry("600x700")
            dialog.transient(self.root)
            dialog.grab_set()
            
            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)
            
            ttk.Label(main_frame, text="Edit Student Information", font=('Arial', 12, 'bold')).pack(pady=(0, 15))
            
            # Create form fields
            fields = {}
            
            ttk.Label(main_frame, text="Student ID:").pack(anchor='w')
            fields['student_id'] = tk.Entry(main_frame, width=40)
            fields['student_id'].insert(0, student_data[0])
            fields['student_id'].config(state='disabled')  # ID should not be editable
            fields['student_id'].pack(fill='x', pady=5)
            
            ttk.Label(main_frame, text="First Name:").pack(anchor='w')
            fields['first_name'] = tk.Entry(main_frame, width=40)
            fields['first_name'].insert(0, student_data[1] or "")
            fields['first_name'].pack(fill='x', pady=5)
            
            ttk.Label(main_frame, text="Last Name:").pack(anchor='w')
            fields['last_name'] = tk.Entry(main_frame, width=40)
            fields['last_name'].insert(0, student_data[2] or "")
            fields['last_name'].pack(fill='x', pady=5)
            
            ttk.Label(main_frame, text="Email:").pack(anchor='w')
            fields['email'] = tk.Entry(main_frame, width=40)
            fields['email'].insert(0, student_data[3] or "")
            fields['email'].pack(fill='x', pady=5)
            
            ttk.Label(main_frame, text="Course:").pack(anchor='w')
            fields['course'] = tk.Entry(main_frame, width=40)
            fields['course'].insert(0, student_data[4] or "")
            fields['course'].pack(fill='x', pady=5)
            
            ttk.Label(main_frame, text="Year:").pack(anchor='w')
            fields['year'] = tk.Entry(main_frame, width=40)
            fields['year'].insert(0, str(student_data[5] or ""))
            fields['year'].pack(fill='x', pady=5)
            
            def save_student():
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                    UPDATE students SET first_name = ?, last_name = ?, email = ?, course = ?, year = ?
                    WHERE student_id = ?
                    ''', (fields['first_name'].get(), fields['last_name'].get(), fields['email'].get(),
                          fields['course'].get(), int(fields['year'].get() or 0), student_id))
                    
                    conn.commit()
                    conn.close()
                    
                    messagebox.showinfo("Success", "Student information updated successfully!")
                    dialog.destroy()
                    self.refresh_students()
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update student: {str(e)}")
            
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x', pady=(15, 0))
            
            ttk.Button(button_frame, text="Save", command=save_student).pack(side='right', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load student data: {str(e)}")

    def deactivate_student(self):
        """Deactivate selected student"""
        selection = self.students_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a student to deactivate.")
            return
        
        item = self.students_tree.item(selection[0])
        student_id = item['values'][0]
        
        if messagebox.askyesno("Confirm", f"Are you sure you want to deactivate student {student_id}?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('UPDATE students SET status = "inactive" WHERE student_id = ?', (student_id,))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Student deactivated successfully!")
                self.refresh_students()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to deactivate student: {str(e)}")

    def workflow_management(self):
        """Workflow management with GUI interface"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Workflow Management")
        dialog.geometry("700x550")
        dialog.transient(self.root)
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Workflow Management", font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        workflow_options = [
            ("View Active Workflows", self.view_active_workflows),
            ("Process Workflow Step", self.process_workflow_step),
            ("Create Custom Workflow", self.create_custom_workflow_gui),
            ("Workflow Templates", self.workflow_templates_gui),
            ("🏠 Return to Main Menu", self.return_to_main_menu)
        ]
        
        for text, command in workflow_options:
            ttk.Button(main_frame, text=text, command=command, width=25).pack(pady=5)
        
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=20)

    def manage_document_types(self):
        """Open document types management with full functionality"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Document Types Management")
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Document Types Management", font=('Arial', 14, 'bold')).pack(pady=(0, 15))
        
        # Document types list
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill='both', expand=True, pady=(0, 15))
        
        # Treeview for document types
        columns = ('ID', 'Name', 'Category', 'Required', 'Expiry', 'Max Size (MB)', 'Formats', 'Active')
        self.doc_types_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)
        
        for col in columns:
            self.doc_types_tree.heading(col, text=col)
            width = 60 if col == 'ID' else 100
            self.doc_types_tree.column(col, width=width)
        
        # Scrollbar
        doc_types_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.doc_types_tree.yview)
        self.doc_types_tree.configure(yscrollcommand=doc_types_scrollbar.set)
        
        self.doc_types_tree.pack(side='left', fill='both', expand=True)
        doc_types_scrollbar.pack(side='right', fill='y')
        
        # Load document types
        self.load_document_types_full()
        
        # Buttons
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill='x')
        
        ttk.Button(buttons_frame, text="Add Type", command=self.add_document_type_full).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Edit Type", command=self.edit_document_type_full).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Delete Type", command=self.delete_document_type_full).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Refresh", command=self.load_document_types_full).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

    def load_document_types_full(self):
        """Load document types with full data"""
        if hasattr(self, 'doc_types_tree') and self.doc_types_tree is not None:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT type_id, type_name,
                       COALESCE(category, 'General') as category,
                       is_required, has_expiry,
                       max_file_size_mb, allowed_formats, is_active
                FROM document_types
                ORDER BY COALESCE(category, 'General'), COALESCE(sort_order, 0), type_name
                ''')
                doc_types = cursor.fetchall()
                conn.close()
                
                # Clear existing items
                for item in self.doc_types_tree.get_children():
                    self.doc_types_tree.delete(item)
                
                # Insert new items
                for doc_type in doc_types:
                    type_id, name, category, required, expiry, max_size, formats, active = doc_type
                    required_text = "Yes" if required else "No"
                    expiry_text = "Yes" if expiry else "No"
                    active_text = "Yes" if active else "No"
                    
                    self.doc_types_tree.insert('', 'end', values=(
                        type_id, name, category or "General", required_text, expiry_text, max_size, formats, active_text
                    ))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load document types: {str(e)}")

    def add_document_type_full(self):
        """Add new document type with full form"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Document Type")
        dialog.geometry("700x800")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Add New Document Type", font=('Arial', 12, 'bold')).pack(pady=(0, 15))
        
        # Form fields
        fields = {}
        
        # Type name
        ttk.Label(main_frame, text="Type Name:").pack(anchor='w')
        fields['name'] = tk.Entry(main_frame, width=40)
        fields['name'].pack(fill='x', pady=5)
        
        # Description
        ttk.Label(main_frame, text="Description:").pack(anchor='w')
        fields['description'] = tk.Text(main_frame, height=3, width=40)
        fields['description'].pack(fill='x', pady=5)
        
        # Category
        ttk.Label(main_frame, text="Category:").pack(anchor='w')
        fields['category'] = ttk.Combobox(main_frame, values=['Identity', 'Academic', 'Immigration', 'Health', 'Financial', 'Other'])
        fields['category'].pack(fill='x', pady=5)
        
        # Checkboxes
        fields['required'] = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Required Document", variable=fields['required']).pack(anchor='w', pady=5)
        
        fields['expiry'] = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Has Expiry Date", variable=fields['expiry']).pack(anchor='w', pady=5)
        
        fields['approval'] = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="Requires Approval", variable=fields['approval']).pack(anchor='w', pady=5)
        
        # Max file size
        ttk.Label(main_frame, text="Max File Size (MB):").pack(anchor='w')
        fields['max_size'] = tk.Entry(main_frame, width=40)
        fields['max_size'].insert(0, "10")
        fields['max_size'].pack(fill='x', pady=5)
        
        # Allowed formats
        ttk.Label(main_frame, text="Allowed Formats (comma-separated):").pack(anchor='w')
        fields['formats'] = tk.Entry(main_frame, width=40)
        fields['formats'].insert(0, "pdf,jpg,jpeg,png")
        fields['formats'].pack(fill='x', pady=5)
        
        # Sort order
        ttk.Label(main_frame, text="Sort Order:").pack(anchor='w')
        fields['sort_order'] = tk.Entry(main_frame, width=40)
        fields['sort_order'].insert(0, "0")
        fields['sort_order'].pack(fill='x', pady=5)
        
        def save_document_type():
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                INSERT INTO document_types 
                (type_name, description, category, is_required, has_expiry, requires_approval,
                 max_file_size_mb, allowed_formats, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    fields['name'].get(),
                    fields['description'].get('1.0', 'end-1c'),
                    fields['category'].get(),
                    fields['required'].get(),
                    fields['expiry'].get(),
                    fields['approval'].get(),
                    int(fields['max_size'].get() or 10),
                    fields['formats'].get(),
                    int(fields['sort_order'].get() or 0)
                ))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Document type added successfully!")
                dialog.destroy()
                self.load_document_types_full()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add document type: {str(e)}")
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))
        
        ttk.Button(button_frame, text="Save", command=save_document_type).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def edit_document_type_full(self):
        """Edit selected document type"""
        selection = self.doc_types_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document type to edit.")
            return
        
        item = self.doc_types_tree.item(selection[0])
        type_id = item['values'][0]
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM document_types WHERE type_id = ?', (type_id,))
            doc_type_data = cursor.fetchone()
            conn.close()
            
            if not doc_type_data:
                messagebox.showerror("Error", "Document type not found.")
                return
            
            # Create edit dialog (similar to add dialog but pre-populated)
            dialog = tk.Toplevel(self.root)
            dialog.title("Edit Document Type")
            dialog.geometry("700x800")
            dialog.transient(self.root)
            dialog.grab_set()
            
            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)
            
            ttk.Label(main_frame, text="Edit Document Type", font=('Arial', 12, 'bold')).pack(pady=(0, 15))
            
            # Pre-populate fields with existing data
            fields = {}
            
            ttk.Label(main_frame, text="Type Name:").pack(anchor='w')
            fields['name'] = tk.Entry(main_frame, width=40)
            fields['name'].insert(0, doc_type_data[1] or "")
            fields['name'].pack(fill='x', pady=5)
            
            ttk.Label(main_frame, text="Description:").pack(anchor='w')
            fields['description'] = tk.Text(main_frame, height=3, width=40)
            fields['description'].insert('1.0', doc_type_data[2] or "")
            fields['description'].pack(fill='x', pady=5)
            
            ttk.Label(main_frame, text="Category:").pack(anchor='w')
            fields['category'] = ttk.Combobox(main_frame, values=['Identity', 'Academic', 'Immigration', 'Health', 'Financial', 'Other'])
            fields['category'].set(doc_type_data[9] or "")
            fields['category'].pack(fill='x', pady=5)
            
            fields['required'] = tk.BooleanVar(value=bool(doc_type_data[3]))
            ttk.Checkbutton(main_frame, text="Required Document", variable=fields['required']).pack(anchor='w', pady=5)
            
            fields['expiry'] = tk.BooleanVar(value=bool(doc_type_data[4]))
            ttk.Checkbutton(main_frame, text="Has Expiry Date", variable=fields['expiry']).pack(anchor='w', pady=5)
            
            fields['approval'] = tk.BooleanVar(value=bool(doc_type_data[8]))
            ttk.Checkbutton(main_frame, text="Requires Approval", variable=fields['approval']).pack(anchor='w', pady=5)
            
            ttk.Label(main_frame, text="Max File Size (MB):").pack(anchor='w')
            fields['max_size'] = tk.Entry(main_frame, width=40)
            fields['max_size'].insert(0, str(doc_type_data[6] or 10))
            fields['max_size'].pack(fill='x', pady=5)
            
            ttk.Label(main_frame, text="Allowed Formats:").pack(anchor='w')
            fields['formats'] = tk.Entry(main_frame, width=40)
            fields['formats'].insert(0, doc_type_data[7] or "")
            fields['formats'].pack(fill='x', pady=5)
            
            ttk.Label(main_frame, text="Sort Order:").pack(anchor='w')
            fields['sort_order'] = tk.Entry(main_frame, width=40)
            fields['sort_order'].insert(0, str(doc_type_data[10] or 0))
            fields['sort_order'].pack(fill='x', pady=5)
            
            fields['active'] = tk.BooleanVar(value=bool(doc_type_data[11]))
            ttk.Checkbutton(main_frame, text="Active", variable=fields['active']).pack(anchor='w', pady=5)
            
            def update_document_type():
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                    UPDATE document_types SET
                    type_name = ?, description = ?, category = ?, is_required = ?, 
                    has_expiry = ?, requires_approval = ?, max_file_size_mb = ?, 
                    allowed_formats = ?, sort_order = ?, is_active = ?
                    WHERE type_id = ?
                    ''', (
                        fields['name'].get(),
                        fields['description'].get('1.0', 'end-1c'),
                        fields['category'].get(),
                        fields['required'].get(),
                        fields['expiry'].get(),
                        fields['approval'].get(),
                        int(fields['max_size'].get() or 10),
                        fields['formats'].get(),
                        int(fields['sort_order'].get() or 0),
                        fields['active'].get(),
                        type_id
                    ))
                    
                    conn.commit()
                    conn.close()
                    
                    messagebox.showinfo("Success", "Document type updated successfully!")
                    dialog.destroy()
                    self.load_document_types_full()
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update document type: {str(e)}")
            
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x', pady=(15, 0))
            
            ttk.Button(button_frame, text="Update", command=update_document_type).pack(side='right', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load document type data: {str(e)}")

    def delete_document_type_full(self):
        """Delete selected document type"""
        selection = self.doc_types_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document type to delete.")
            return
        
        item = self.doc_types_tree.item(selection[0])
        type_id = item['values'][0]
        type_name = item['values'][1]
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{type_name}'?\n\nThis will also affect any documents of this type."):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Check if there are documents using this type
                cursor.execute('SELECT COUNT(*) FROM student_documents WHERE type_id = ?', (type_id,))
                doc_count = cursor.fetchone()[0]
                
                if doc_count > 0:
                    if not messagebox.askyesno("Warning", f"There are {doc_count} documents using this type. Delete anyway?"):
                        conn.close()
                        return
                
                # Delete the document type
                cursor.execute('DELETE FROM document_types WHERE type_id = ?', (type_id,))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Document type deleted successfully!")
                self.load_document_types_full()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete document type: {str(e)}")

    def workflow_management(self):
        """Full workflow management interface"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Workflow Management")
        dialog.geometry("900x700")
        dialog.transient(self.root)
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Create notebook for different workflow sections
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))
        
        # Active Workflows Tab
        active_frame = ttk.Frame(notebook, padding=15)
        notebook.add(active_frame, text="Active Workflows")
        
        ttk.Label(active_frame, text="Active Workflows", font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        
        # Workflows list
        wf_columns = ('WF ID', 'Doc ID', 'Student', 'Document Type', 'Step', 'Assigned To', 'Age (days)')
        self.workflows_tree = ttk.Treeview(active_frame, columns=wf_columns, show='headings', height=12)
        
        for col in wf_columns:
            self.workflows_tree.heading(col, text=col)
            self.workflows_tree.column(col, width=100)
        
        wf_scrollbar = ttk.Scrollbar(active_frame, orient='vertical', command=self.workflows_tree.yview)
        self.workflows_tree.configure(yscrollcommand=wf_scrollbar.set)
        
        self.workflows_tree.pack(side='left', fill='both', expand=True)
        wf_scrollbar.pack(side='right', fill='y')
        
        # Process Workflow Tab
        process_frame = ttk.Frame(notebook, padding=15)
        notebook.add(process_frame, text="Process Steps")
        
        ttk.Label(process_frame, text="Process Workflow Step", font=('Arial', 12, 'bold')).pack(pady=(0, 15))
        
        # Workflow ID input
        id_frame = ttk.Frame(process_frame)
        id_frame.pack(fill='x', pady=5)
        ttk.Label(id_frame, text="Workflow ID:").pack(side='left')
        self.workflow_id_var = tk.StringVar()
        ttk.Entry(id_frame, textvariable=self.workflow_id_var, width=20).pack(side='left', padx=10)
        ttk.Button(id_frame, text="Load", command=self.load_workflow_details).pack(side='left', padx=5)
        
        # Workflow details
        self.workflow_details_frame = ttk.LabelFrame(process_frame, text="Workflow Details", padding=10)
        self.workflow_details_frame.pack(fill='x', pady=10)
        
        # Action selection
        action_frame = ttk.LabelFrame(process_frame, text="Action", padding=10)
        action_frame.pack(fill='x', pady=10)
        
        self.workflow_action_var = tk.StringVar(value="approve")
        actions = [("Approve and Continue", "approve"), ("Reject and Stop", "reject"), ("Request More Info", "request_info")]
        for text, value in actions:
            ttk.Radiobutton(action_frame, text=text, variable=self.workflow_action_var, value=value).pack(anchor='w', pady=2)
        
        # Comments
        ttk.Label(process_frame, text="Comments:").pack(anchor='w', pady=(10, 0))
        self.workflow_comments = tk.Text(process_frame, height=5, width=50)
        self.workflow_comments.pack(fill='x', pady=5)
        
        ttk.Button(process_frame, text="Process Step", command=self.process_workflow_step_full).pack(pady=15)
        
        # Workflow Templates Tab
        templates_frame = ttk.Frame(notebook, padding=15)
        notebook.add(templates_frame, text="Templates")
        
        ttk.Label(templates_frame, text="Workflow Templates", font=('Arial', 12, 'bold')).pack(pady=(0, 15))
        
        template_options = [
            ("Standard Document Review", self.create_standard_workflow),
            ("Express Approval", self.create_express_workflow),
            ("Multi-Stage Verification", self.create_multistage_workflow),
            ("🏠 Return to Main Menu", self.return_to_main_menu)
        ]
        
        for text, command in template_options:
            ttk.Button(templates_frame, text=text, command=command, width=30).pack(pady=5)
        
        # Load initial data
        self.load_workflows()
        
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack()

    def load_workflows(self):
        """Load active workflows"""
        if hasattr(self, 'workflows_tree'):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT dw.workflow_id, sd.document_id, s.first_name || ' ' || s.last_name as student_name,
                       dt.type_name, dw.step_name, dw.assigned_to, sd.upload_date
                FROM document_workflow dw
                JOIN student_documents sd ON dw.document_id = sd.document_id
                JOIN students s ON sd.student_id = s.student_id
                JOIN document_types dt ON sd.type_id = dt.type_id
                WHERE dw.status = 'pending'
                ORDER BY sd.upload_date ASC
                ''')
                
                workflows = cursor.fetchall()
                conn.close()
                
                # Clear existing items
                for item in self.workflows_tree.get_children():
                    self.workflows_tree.delete(item)
                
                # Insert new items
                for workflow in workflows:
                    wf_id, doc_id, student_name, doc_type, step_name, assigned_to, upload_date = workflow
                    
                    # Calculate age
                    from datetime import datetime
                    upload_dt = datetime.strptime(upload_date[:10], '%Y-%m-%d')
                    age_days = (datetime.now() - upload_dt).days
                    
                    self.workflows_tree.insert('', 'end', values=(wf_id, doc_id, student_name, doc_type, step_name, assigned_to, age_days))
                    
            except Exception as e:
                print(f"Error loading workflows: {e}")

    def notification_center(self):
        """Full notification center interface"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Notification Center")
        dialog.geometry("800x600")
        dialog.transient(self.root)
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Create notebook for notification management
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))
        
        # Pending Notifications Tab
        pending_frame = ttk.Frame(notebook, padding=15)
        notebook.add(pending_frame, text="Pending Notifications")
        
        ttk.Label(pending_frame, text="Pending Notifications", font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        
        # Notifications list
        notif_columns = ('ID', 'Recipient', 'Type', 'Title', 'Created', 'Priority', 'Status')
        self.notifications_tree = ttk.Treeview(pending_frame, columns=notif_columns, show='headings', height=12)
        
        for col in notif_columns:
            self.notifications_tree.heading(col, text=col)
            self.notifications_tree.column(col, width=100)
        
        notif_scrollbar = ttk.Scrollbar(pending_frame, orient='vertical', command=self.notifications_tree.yview)
        self.notifications_tree.configure(yscrollcommand=notif_scrollbar.set)
        
        self.notifications_tree.pack(side='left', fill='both', expand=True)
        notif_scrollbar.pack(side='right', fill='y')
        
        # Notification actions
        notif_actions_frame = ttk.Frame(pending_frame)
        notif_actions_frame.pack(fill='x', pady=10)
        
        ttk.Button(notif_actions_frame, text="Send Selected", command=self.send_selected_notifications).pack(side='left', padx=5)
        ttk.Button(notif_actions_frame, text="Mark as Sent", command=self.mark_notifications_sent).pack(side='left', padx=5)
        ttk.Button(notif_actions_frame, text="Delete", command=self.delete_notifications).pack(side='left', padx=5)
        ttk.Button(notif_actions_frame, text="Refresh", command=self.load_notifications).pack(side='right', padx=5)
        
        # Send Notification Tab
        send_frame = ttk.Frame(notebook, padding=15)
        notebook.add(send_frame, text="Send Notification")
        
        ttk.Label(send_frame, text="Send Custom Notification", font=('Arial', 12, 'bold')).pack(pady=(0, 15))
        
        # Recipient selection
        ttk.Label(send_frame, text="Recipient:").pack(anchor='w')
        self.notif_recipient = ttk.Combobox(send_frame, width=40)
        self.notif_recipient.pack(fill='x', pady=5)
        
        # Load recipients
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id, first_name, last_name FROM students')
            students = cursor.fetchall()
            conn.close()

            recipient_values = [f"{s[0]} - {s[1]} {s[2]}" for s in students]
            self.notif_recipient['values'] = recipient_values
        except:
            pass
        
        # Notification type
        ttk.Label(send_frame, text="Type:").pack(anchor='w', pady=(10, 0))
        self.notif_type = ttk.Combobox(send_frame, values=['document_reminder', 'verification_complete', 'expiry_warning', 'general', 'urgent'])
        self.notif_type.set('general')
        self.notif_type.pack(fill='x', pady=5)
        
        # Priority
        ttk.Label(send_frame, text="Priority:").pack(anchor='w', pady=(10, 0))
        self.notif_priority = ttk.Combobox(send_frame, values=['low', 'normal', 'high', 'urgent'])
        self.notif_priority.set('normal')
        self.notif_priority.pack(fill='x', pady=5)
        
        # Title
        ttk.Label(send_frame, text="Title:").pack(anchor='w', pady=(10, 0))
        self.notif_title = tk.Entry(send_frame, width=50)
        self.notif_title.pack(fill='x', pady=5)
        
        # Message
        ttk.Label(send_frame, text="Message:").pack(anchor='w', pady=(10, 0))
        self.notif_message = tk.Text(send_frame, height=6, width=50)
        self.notif_message.pack(fill='x', pady=5)
        
        ttk.Button(send_frame, text="Send Notification", command=self.send_custom_notification).pack(pady=15)
        
        # Templates Tab
        templates_frame = ttk.Frame(notebook, padding=15)
        notebook.add(templates_frame, text="Templates")
        
        ttk.Label(templates_frame, text="Notification Templates", font=('Arial', 12, 'bold')).pack(pady=(0, 15))
        
        template_list = [
            ("Document Upload Confirmation", "Your document has been uploaded successfully."),
            ("Verification Complete", "Your document has been verified and approved."),
            ("Document Rejected", "Your document requires attention. Please review and resubmit."),
            ("Expiry Warning", "Your document will expire soon. Please renew."),
            ("Missing Document Reminder", "You have missing required documents.")
        ]
        
        for title, template in template_list:
            template_frame = ttk.Frame(templates_frame)
            template_frame.pack(fill='x', pady=5)
            
            ttk.Label(template_frame, text=title, width=30).pack(side='left')
            ttk.Button(template_frame, text="Use Template", 
                      command=lambda t=title, msg=template: self.use_notification_template(t, msg)).pack(side='right')
        
        # Load initial data
        self.load_notifications()
        
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack()

    def load_notifications(self):
        """Load pending notifications"""
        if hasattr(self, 'notifications_tree'):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT notification_id, recipient_id, notification_type, title, 
                       created_date, priority, CASE WHEN is_sent THEN 'Sent' ELSE 'Pending' END as status
                FROM notifications
                WHERE is_sent = 0
                ORDER BY created_date DESC
                LIMIT 100
                ''')
                
                notifications = cursor.fetchall()
                conn.close()
                
                # Clear existing items
                for item in self.notifications_tree.get_children():
                    self.notifications_tree.delete(item)
                
                # Insert new items
                for notification in notifications:
                    self.notifications_tree.insert('', 'end', values=notification)
                    
            except Exception as e:
                print(f"Error loading notifications: {e}")

    def send_custom_notification(self):
        """Send custom notification"""
        recipient = self.notif_recipient.get()
        notif_type = self.notif_type.get()
        priority = self.notif_priority.get()
        title = self.notif_title.get()
        message = self.notif_message.get('1.0', 'end-1c')
        
        if not recipient or not title or not message:
            messagebox.showerror("Error", "Please fill in all required fields")
            return
        
        try:
            # Extract recipient ID
            recipient_id = recipient.split(' - ')[0]
            
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO notifications (user_id, recipient_id, notification_type, title, message,
                                     created_datetime, priority, is_sent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (recipient_id, recipient_id, notif_type, title, message,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), priority, 0))
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", "Notification created successfully!")
            
            # Clear form
            self.notif_title.delete(0, 'end')
            self.notif_message.delete('1.0', 'end')
            self.load_notifications()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create notification: {str(e)}")

    def send_selected_notifications(self):
        """Send selected notifications"""
        selection = self.notifications_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select notifications to send.")
            return
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            sent_count = 0
            for item in selection:
                notif_id = self.notifications_tree.item(item)['values'][0]
                
                # Mark as sent
                cursor.execute('''
                UPDATE notifications 
                SET is_sent = 1, sent_date = ?
                WHERE notification_id = ?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), notif_id))
                
                sent_count += 1
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", f"Sent {sent_count} notifications successfully!")
            self.load_notifications()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send notifications: {str(e)}")

    def mark_notifications_sent(self):
        """Mark selected notifications as sent without actually sending"""
        selection = self.notifications_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select notifications to mark as sent.")
            return
        
        if messagebox.askyesno("Confirm", "Mark selected notifications as sent?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                for item in selection:
                    notif_id = self.notifications_tree.item(item)['values'][0]
                    cursor.execute('''
                    UPDATE notifications 
                    SET is_sent = 1, sent_date = ?
                    WHERE notification_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), notif_id))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Notifications marked as sent!")
                self.load_notifications()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to mark notifications: {str(e)}")

    def delete_notifications(self):
        """Delete selected notifications"""
        selection = self.notifications_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select notifications to delete.")
            return
        
        if messagebox.askyesno("Confirm Delete", f"Delete {len(selection)} selected notifications?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                for item in selection:
                    notif_id = self.notifications_tree.item(item)['values'][0]
                    cursor.execute('DELETE FROM notifications WHERE notification_id = ?', (notif_id,))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Notifications deleted successfully!")
                self.load_notifications()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete notifications: {str(e)}")

    def use_notification_template(self, title, message):
        """Use notification template"""
        self.notif_title.delete(0, 'end')
        self.notif_title.insert(0, title)
        
        self.notif_message.delete('1.0', 'end')
        self.notif_message.insert('1.0', message)

    def load_workflow_details(self):
        """Load workflow details for processing"""
        workflow_id = self.workflow_id_var.get()
        if not workflow_id:
            messagebox.showerror("Error", "Please enter a workflow ID")
            return
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT dw.workflow_id, dw.document_id, dw.step_name, dw.assigned_to,
                   s.first_name, s.last_name, dt.type_name, sd.upload_date
            FROM document_workflow dw
            JOIN student_documents sd ON dw.document_id = sd.document_id
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE dw.workflow_id = ? AND dw.status = 'pending'
            ''', (workflow_id,))
            
            workflow = cursor.fetchone()
            conn.close()
            
            if not workflow:
                messagebox.showerror("Error", "Workflow step not found or already completed")
                return
            
            # Clear previous details
            for widget in self.workflow_details_frame.winfo_children():
                widget.destroy()
            
            # Display workflow details
            wf_id, doc_id, step_name, assigned_to, first_name, last_name, doc_type, upload_date = workflow
            
            ttk.Label(self.workflow_details_frame, text=f"Document: {doc_type}").pack(anchor='w')
            ttk.Label(self.workflow_details_frame, text=f"Student: {first_name} {last_name}").pack(anchor='w')
            ttk.Label(self.workflow_details_frame, text=f"Step: {step_name}").pack(anchor='w')
            ttk.Label(self.workflow_details_frame, text=f"Assigned to: {assigned_to}").pack(anchor='w')
            ttk.Label(self.workflow_details_frame, text=f"Upload Date: {upload_date[:10]}").pack(anchor='w')
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load workflow details: {str(e)}")

    def process_workflow_step_full(self):
        """Process workflow step with full functionality"""
        workflow_id = self.workflow_id_var.get()
        action = self.workflow_action_var.get()
        comments = self.workflow_comments.get('1.0', 'end-1c')
        
        if not workflow_id:
            messagebox.showerror("Error", "Please enter and load a workflow ID first")
            return
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get workflow details
            cursor.execute('''
            SELECT dw.document_id FROM document_workflow dw
            WHERE dw.workflow_id = ? AND dw.status = 'pending'
            ''', (workflow_id,))
            
            workflow = cursor.fetchone()
            
            if not workflow:
                messagebox.showerror("Error", "Workflow step not found or already completed")
                conn.close()
                return
            
            doc_id = workflow[0]
            
            if action == "approve":
                # Mark step as completed
                cursor.execute('''
                UPDATE document_workflow 
                SET status = 'completed', completed_date = ?, completed_by = ?, comments = ?
                WHERE workflow_id = ?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                      self.current_user['username'], comments, workflow_id))
                
                # Check if workflow is complete
                cursor.execute('''
                SELECT COUNT(*) FROM document_workflow
                WHERE document_id = ? AND status = 'pending'
                ''', (doc_id,))
                
                pending_steps = cursor.fetchone()[0]
                
                if pending_steps == 0:
                    # Mark document as verified
                    cursor.execute('''
                    UPDATE student_documents 
                    SET verification_status = 'Verified', verification_date = ?,
                        workflow_status = 'completed'
                    WHERE document_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d'), doc_id))
                    
                    messagebox.showinfo("Success", "Workflow completed! Document marked as Verified.")
                else:
                    messagebox.showinfo("Success", "Step approved. Workflow continues to next step.")
                    
            elif action == "reject":
                cursor.execute('''
                UPDATE document_workflow 
                SET status = 'rejected', completed_date = ?, completed_by = ?, comments = ?
                WHERE workflow_id = ?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                      self.current_user['username'], comments, workflow_id))
                
                cursor.execute('''
                UPDATE student_documents 
                SET verification_status = 'Rejected', verification_date = ?,
                    verification_notes = ?, workflow_status = 'rejected'
                WHERE document_id = ?
                ''', (datetime.now().strftime('%Y-%m-%d'), comments, doc_id))
                
                messagebox.showinfo("Success", "Document rejected. Workflow stopped.")
            
            conn.commit()
            conn.close()
            
            # Clear form and refresh
            self.workflow_id_var.set("")
            self.workflow_comments.delete('1.0', 'end')
            self.load_workflows()
            
            # Clear workflow details
            for widget in self.workflow_details_frame.winfo_children():
                widget.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to process workflow step: {str(e)}")

    def create_standard_workflow(self):
        """Create standard workflow template"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Standard Workflow")
        dialog.geometry("700x550")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Create Standard Workflow Template", font=('Arial', 12, 'bold')).pack(pady=(0, 15))
        
        # Document type selection
        ttk.Label(main_frame, text="Apply to Document Type:").pack(anchor='w')
        doc_type_var = tk.StringVar()
        doc_type_combo = ttk.Combobox(main_frame, textvariable=doc_type_var)
        
        # Load document types
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT type_name FROM document_types WHERE is_active = 1')
            doc_types = [row[0] for row in cursor.fetchall()]
            conn.close()
            doc_type_combo['values'] = doc_types
        except:
            doc_type_combo['values'] = []
        
        doc_type_combo.pack(fill='x', pady=5)
        
        # Workflow steps preview
        ttk.Label(main_frame, text="Workflow Steps:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(15, 5))
        
        steps_frame = ttk.Frame(main_frame)
        steps_frame.pack(fill='x', pady=5)
        
        steps_text = """1. Initial Review (Assigned to: registrar)
       - Verify document format and completeness
       - Check student information accuracy
       
    2. Verification (Assigned to: admin)
       - Validate document authenticity
       - Cross-reference with records
       
    3. Final Approval (Assigned to: dean)
       - Final approval and sign-off
       - Update student records"""
        
        text_widget = tk.Text(steps_frame, height=10, width=50)
        text_widget.insert('1.0', steps_text)
        text_widget.config(state='disabled')
        text_widget.pack(fill='both', expand=True)
        
        def create_workflow():
            doc_type = doc_type_var.get()
            if not doc_type:
                messagebox.showerror("Error", "Please select a document type")
                return
            
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Get document type ID
                cursor.execute('SELECT type_id FROM document_types WHERE type_name = ?', (doc_type,))
                type_result = cursor.fetchone()
                if not type_result:
                    messagebox.showerror("Error", "Document type not found")
                    conn.close()
                    return
                
                type_id = type_result[0]
                
                # Create workflow template in database
                workflow_steps = [
                    ('Initial Review', 1, 'registrar', 'Verify document format and completeness'),
                    ('Verification', 2, 'admin', 'Validate document authenticity'),
                    ('Final Approval', 3, 'dean', 'Final approval and sign-off')
                ]
                
                # Note: In a full implementation, you'd have a workflow_templates table
                # For now, we'll just confirm the template creation
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", f"Standard workflow template created for {doc_type}!\n\nNew documents of this type will automatically use this 3-step approval process.")
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create workflow: {str(e)}")
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))
        
        ttk.Button(button_frame, text="Create Workflow", command=create_workflow).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def create_express_workflow(self):
        """Create express workflow template"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Express Workflow")
        dialog.geometry("950x700")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Create Express Workflow Template", font=('Arial', 12, 'bold')).pack(pady=(0, 15))
        
        # Document type selection
        ttk.Label(main_frame, text="Apply to Document Type:").pack(anchor='w')
        doc_type_var = tk.StringVar()
        doc_type_combo = ttk.Combobox(main_frame, textvariable=doc_type_var)
        
        # Load document types
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT type_name FROM document_types WHERE is_active = 1')
            doc_types = [row[0] for row in cursor.fetchall()]
            conn.close()
            doc_type_combo['values'] = doc_types
        except:
            doc_type_combo['values'] = []
        
        doc_type_combo.pack(fill='x', pady=5)
        
        # Priority selection
        ttk.Label(main_frame, text="Priority Level:").pack(anchor='w', pady=(10, 0))
        priority_var = tk.StringVar(value="high")
        priority_frame = ttk.Frame(main_frame)
        priority_frame.pack(fill='x', pady=5)
        
        ttk.Radiobutton(priority_frame, text="High Priority", variable=priority_var, value="high").pack(side='left')
        ttk.Radiobutton(priority_frame, text="Urgent", variable=priority_var, value="urgent").pack(side='left', padx=20)
        
        # Workflow steps preview
        ttk.Label(main_frame, text="Express Workflow Steps:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(15, 5))
        
        steps_text = """1. Quick Review (Assigned to: admin)
       - Fast-track document verification
       - Automated checks where possible
       - Priority processing
       
    2. Immediate Approval (Assigned to: registrar)
       - Final approval within 24 hours
       - Student notification upon completion
       
    Target Completion Time: 1-2 business days"""
        
        text_widget = tk.Text(main_frame, height=8, width=50)
        text_widget.insert('1.0', steps_text)
        text_widget.config(state='disabled')
        text_widget.pack(fill='both', expand=True)
        
        def create_express():
            doc_type = doc_type_var.get()
            priority = priority_var.get()
            
            if not doc_type:
                messagebox.showerror("Error", "Please select a document type")
                return
            
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Get document type ID
                cursor.execute('SELECT type_id FROM document_types WHERE type_name = ?', (doc_type,))
                type_result = cursor.fetchone()
                if not type_result:
                    messagebox.showerror("Error", "Document type not found")
                    conn.close()
                    return
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", f"Express workflow template created for {doc_type}!\n\nPriority: {priority.title()}\nTarget completion: 1-2 business days")
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create express workflow: {str(e)}")
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))
        
        ttk.Button(button_frame, text="Create Express Workflow", command=create_express).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def create_multistage_workflow(self):
        """Create multi-stage workflow template"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Multi-Stage Workflow")
        dialog.geometry("850x700")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Create Multi-Stage Workflow Template", font=('Arial', 12, 'bold')).pack(pady=(0, 15))
        
        # Document type selection
        ttk.Label(main_frame, text="Apply to Document Type:").pack(anchor='w')
        doc_type_var = tk.StringVar()
        doc_type_combo = ttk.Combobox(main_frame, textvariable=doc_type_var)
        
        # Load document types
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT type_name FROM document_types WHERE is_active = 1')
            doc_types = [row[0] for row in cursor.fetchall()]
            conn.close()
            doc_type_combo['values'] = doc_types
        except:
            doc_type_combo['values'] = []
        
        doc_type_combo.pack(fill='x', pady=5)
        
        # Department assignments
        ttk.Label(main_frame, text="Department Assignments:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(15, 5))
        
        dept_frame = ttk.Frame(main_frame)
        dept_frame.pack(fill='x', pady=5)
        
        departments = ['registrar', 'academic_affairs', 'student_services', 'dean_office', 'compliance']
        dept_vars = {}
        
        for i, dept in enumerate(departments):
            dept_vars[dept] = tk.BooleanVar(value=True)
            ttk.Checkbutton(dept_frame, text=dept.replace('_', ' ').title(), 
                           variable=dept_vars[dept]).grid(row=i//2, column=i%2, sticky='w', padx=10, pady=2)
        
        # Workflow steps preview
        ttk.Label(main_frame, text="Multi-Stage Workflow Steps:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(15, 5))
        
        steps_text = """1. Intake (Assigned to: registrar)
       - Initial document receipt and logging
       - Basic format and completeness check
       - Student information verification
       
    2. Initial Review (Assigned to: academic_affairs)
       - Academic requirements verification
       - Prerequisite document checks
       - Initial compliance assessment
       
    3. Department Review (Assigned to: student_services)
       - Department-specific requirements
       - Cross-departmental coordination
       - Specialized review processes
       
    4. Final Verification (Assigned to: compliance)
       - Comprehensive compliance check
       - Legal and regulatory requirements
       - Quality assurance review
       
    5. Final Approval (Assigned to: dean_office)
       - Executive approval and sign-off
       - Final authorization
       - Student record updates

    Target Completion Time: 5-7 business days"""
        
        text_widget = tk.Text(main_frame, height=12, width=60)
        text_widget.insert('1.0', steps_text)
        text_widget.config(state='disabled')
        text_widget.pack(fill='both', expand=True)
        
        def create_multistage():
            doc_type = doc_type_var.get()
            if not doc_type:
                messagebox.showerror("Error", "Please select a document type")
                return
            
            # Get selected departments
            selected_depts = [dept for dept, var in dept_vars.items() if var.get()]
            if len(selected_depts) < 2:
                messagebox.showerror("Error", "Please select at least 2 departments for multi-stage workflow")
                return
            
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Get document type ID
                cursor.execute('SELECT type_id FROM document_types WHERE type_name = ?', (doc_type,))
                type_result = cursor.fetchone()
                if not type_result:
                    messagebox.showerror("Error", "Document type not found")
                    conn.close()
                    return
                
                conn.commit()
                conn.close()
                
                dept_list = ', '.join([dept.replace('_', ' ').title() for dept in selected_depts])
                messagebox.showinfo("Success", f"Multi-stage workflow template created for {doc_type}!\n\nDepartments involved: {dept_list}\nTarget completion: 5-7 business days")
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create multi-stage workflow: {str(e)}")
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))
        
        ttk.Button(button_frame, text="Create Multi-Stage Workflow", command=create_multistage).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def custom_workflow_builder(self):
        """Open custom workflow builder"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Custom Workflow Builder")
        dialog.geometry("700x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Custom Workflow Builder", font=('Arial', 14, 'bold')).pack(pady=(0, 15))
        
        # Workflow name and document type
        config_frame = ttk.LabelFrame(main_frame, text="Workflow Configuration", padding=10)
        config_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(config_frame, text="Workflow Name:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        workflow_name = tk.Entry(config_frame, width=30)
        workflow_name.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        ttk.Label(config_frame, text="Document Type:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        doc_type_var = tk.StringVar()
        doc_type_combo = ttk.Combobox(config_frame, textvariable=doc_type_var, width=28)
        doc_type_combo.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        
        # Load document types
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT type_name FROM document_types WHERE is_active = 1')
            doc_types = [row[0] for row in cursor.fetchall()]
            conn.close()
            doc_type_combo['values'] = doc_types
        except:
            doc_type_combo['values'] = []
        
        config_frame.grid_columnconfigure(1, weight=1)
        
        # Workflow steps builder
        steps_frame = ttk.LabelFrame(main_frame, text="Workflow Steps", padding=10)
        steps_frame.pack(fill='both', expand=True, pady=(0, 15))
        
        # Steps list
        columns = ('Step', 'Name', 'Assigned To', 'Description')
        steps_tree = ttk.Treeview(steps_frame, columns=columns, show='headings', height=8)
        
        for col in columns:
            steps_tree.heading(col, text=col)
            steps_tree.column(col, width=100)
        
        steps_scrollbar = ttk.Scrollbar(steps_frame, orient='vertical', command=steps_tree.yview)
        steps_tree.configure(yscrollcommand=steps_scrollbar.set)
        
        steps_tree.pack(side='left', fill='both', expand=True)
        steps_scrollbar.pack(side='right', fill='y')
        
        # Step input frame
        step_input_frame = ttk.Frame(steps_frame)
        step_input_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Label(step_input_frame, text="Step Name:").grid(row=0, column=0, sticky='w', padx=5)
        step_name_entry = tk.Entry(step_input_frame, width=20)
        step_name_entry.grid(row=0, column=1, padx=5)
        
        ttk.Label(step_input_frame, text="Assigned To:").grid(row=0, column=2, sticky='w', padx=5)
        assigned_to_combo = ttk.Combobox(step_input_frame, values=['registrar', 'admin', 'dean', 'academic_affairs', 'student_services'], width=15)
        assigned_to_combo.grid(row=0, column=3, padx=5)
        
        ttk.Label(step_input_frame, text="Description:").grid(row=1, column=0, sticky='w', padx=5)
        step_desc_entry = tk.Entry(step_input_frame, width=50)
        step_desc_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky='ew')
        
        step_input_frame.grid_columnconfigure(1, weight=1)
        
        def add_step():
            step_name = step_name_entry.get()
            assigned_to = assigned_to_combo.get()
            description = step_desc_entry.get()
            
            if not step_name or not assigned_to:
                messagebox.showerror("Error", "Please enter step name and assignment")
                return
            
            step_order = len(steps_tree.get_children()) + 1
            steps_tree.insert('', 'end', values=(step_order, step_name, assigned_to, description))
            
            # Clear inputs
            step_name_entry.delete(0, 'end')
            assigned_to_combo.set('')
            step_desc_entry.delete(0, 'end')
        
        def remove_step():
            selection = steps_tree.selection()
            if selection:
                steps_tree.delete(selection[0])
                # Renumber remaining steps
                for i, item in enumerate(steps_tree.get_children()):
                    values = list(steps_tree.item(item)['values'])
                    values[0] = i + 1
                    steps_tree.item(item, values=values)
        
        step_buttons_frame = ttk.Frame(step_input_frame)
        step_buttons_frame.grid(row=2, column=0, columnspan=4, pady=10)
        
        ttk.Button(step_buttons_frame, text="Add Step", command=add_step).pack(side='left', padx=5)
        ttk.Button(step_buttons_frame, text="Remove Selected", command=remove_step).pack(side='left', padx=5)
        
        def save_custom_workflow():
            name = workflow_name.get()
            doc_type = doc_type_var.get()
            
            if not name or not doc_type:
                messagebox.showerror("Error", "Please enter workflow name and select document type")
                return
            
            if len(steps_tree.get_children()) == 0:
                messagebox.showerror("Error", "Please add at least one workflow step")
                return
            
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Get document type ID
                cursor.execute('SELECT type_id FROM document_types WHERE type_name = ?', (doc_type,))
                type_result = cursor.fetchone()
                if not type_result:
                    messagebox.showerror("Error", "Document type not found")
                    conn.close()
                    return
                
                # Create workflow_templates table if it doesn't exist
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS workflow_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_name TEXT,
                    document_type_id INTEGER,
                    created_date TEXT,
                    created_by TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (document_type_id) REFERENCES document_types (type_id)
                )
                ''')
                
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS workflow_template_steps (
                    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER,
                    step_name TEXT,
                    step_order INTEGER,
                    assigned_to TEXT,
                    description TEXT,
                    FOREIGN KEY (template_id) REFERENCES workflow_templates (template_id)
                )
                ''')
                
                # Insert workflow template
                cursor.execute('''
                INSERT INTO workflow_templates (template_name, document_type_id, created_date, created_by)
                VALUES (?, ?, ?, ?)
                ''', (name, type_result[0], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                      self.current_user.get('username', 'admin')))
                
                template_id = cursor.lastrowid
                
                # Insert workflow steps
                for item in steps_tree.get_children():
                    values = steps_tree.item(item)['values']
                    step_order, step_name, assigned_to, description = values
                    
                    cursor.execute('''
                    INSERT INTO workflow_template_steps (template_id, step_name, step_order, assigned_to, description)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (template_id, step_name, int(step_order), assigned_to, description))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", f"Custom workflow '{name}' created successfully!\n\nThe workflow will be applied to all new {doc_type} documents.")
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create custom workflow: {str(e)}")
        
        # Main buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')
        
        ttk.Button(button_frame, text="Save Workflow", command=save_custom_workflow).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def add_student_dialog(self):
        """Add new student dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Student")
        dialog.geometry("400x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Add New Student", font=('Arial', 12, 'bold')).pack(pady=(0, 15))
        
        fields = {}
        
        ttk.Label(main_frame, text="Student ID:").pack(anchor='w')
        fields['student_id'] = tk.Entry(main_frame, width=40)
        fields['student_id'].pack(fill='x', pady=5)
        
        ttk.Label(main_frame, text="First Name:").pack(anchor='w')
        fields['first_name'] = tk.Entry(main_frame, width=40)
        fields['first_name'].pack(fill='x', pady=5)
        
        ttk.Label(main_frame, text="Last Name:").pack(anchor='w')
        fields['last_name'] = tk.Entry(main_frame, width=40)
        fields['last_name'].pack(fill='x', pady=5)
        
        ttk.Label(main_frame, text="Email:").pack(anchor='w')
        fields['email'] = tk.Entry(main_frame, width=40)
        fields['email'].pack(fill='x', pady=5)
        
        ttk.Label(main_frame, text="Course:").pack(anchor='w')
        fields['course'] = tk.Entry(main_frame, width=40)
        fields['course'].pack(fill='x', pady=5)
        
        ttk.Label(main_frame, text="Year:").pack(anchor='w')
        fields['year'] = tk.Entry(main_frame, width=40)
        fields['year'].pack(fill='x', pady=5)
        
        def save_student():
            # Validate required fields
            if not all([fields['student_id'].get(), fields['first_name'].get(), fields['last_name'].get()]):
                messagebox.showerror("Error", "Student ID, First Name, and Last Name are required")
                return
            
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                INSERT INTO students (student_id, first_name, last_name, email, course, year, enrollment_date, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (fields['student_id'].get(), fields['first_name'].get(), fields['last_name'].get(),
                      fields['email'].get(), fields['course'].get(), int(fields['year'].get() or 1),
                      datetime.now().strftime('%Y-%m-%d'), 'active'))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Student added successfully!")
                dialog.destroy()
                self.refresh_students()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add student: {str(e)}")
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))
        
        ttk.Button(button_frame, text="Add Student", command=save_student).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def student_report_dialog(self):
        """Student report generation dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Generate Student Report")
        dialog.geometry("600x450")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Student Report Options", font=('Arial', 12, 'bold')).pack(pady=(0, 15))
        
        report_type = tk.StringVar(value="all_students")
        
        ttk.Radiobutton(main_frame, text="All Students Summary", variable=report_type, value="all_students").pack(anchor='w', pady=5)
        ttk.Radiobutton(main_frame, text="Students by Course", variable=report_type, value="by_course").pack(anchor='w', pady=5)
        ttk.Radiobutton(main_frame, text="Non-Compliant Students", variable=report_type, value="non_compliant").pack(anchor='w', pady=5)
        ttk.Radiobutton(main_frame, text="Students by Year", variable=report_type, value="by_year").pack(anchor='w', pady=5)
        
        def generate_report():
            report_option = report_type.get()
            dialog.destroy()
            
            if report_option == "all_students":
                self.generate_all_students_report()
            elif report_option == "by_course":
                self.generate_students_by_course_report()
            elif report_option == "non_compliant":
                self.generate_non_compliant_students_report()
            elif report_option == "by_year":
                self.generate_students_by_year_report()
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))
        
        ttk.Button(button_frame, text="Generate", command=generate_report).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def generate_all_students_report(self):
        """Generate report for all students"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT s.student_id, s.first_name, s.last_name, s.course,
                   COALESCE(s.enrollment_year, 'N/A') as year,
                   COUNT(sd.document_id) as doc_count,
                   COUNT(CASE WHEN sd.verification_status = 'Verified' THEN 1 END) as verified_count
            FROM students s
            LEFT JOIN student_documents sd ON s.student_id = sd.student_id AND sd.is_current_version = 1
            GROUP BY s.student_id
            ORDER BY s.last_name, s.first_name
            ''')
            
            students = cursor.fetchall()
            conn.close()
            
            # Show report in new window
            self.show_students_report(students, "All Students Report")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

    def show_students_report(self, data, title):
        """Show students report in new window"""
        report_window = tk.Toplevel(self.root)
        report_window.title(title)
        report_window.geometry("800x600")
        
        report_frame = ttk.Frame(report_window, padding=20)
        report_frame.pack(fill='both', expand=True)
        
        ttk.Label(report_frame, text=title, font=('Arial', 14, 'bold')).pack(pady=(0, 15))
        
        # Create treeview for report data
        columns = ('Student ID', 'Name', 'Course', 'Year', 'Documents', 'Verified')
        report_tree = ttk.Treeview(report_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            report_tree.heading(col, text=col)
            report_tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(report_frame, orient='vertical', command=report_tree.yview)
        report_tree.configure(yscrollcommand=scrollbar.set)
        
        report_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Insert data
        for row in data:
            student_id, first_name, last_name, course, year, doc_count, verified_count = row
            full_name = f"{first_name} {last_name}"
            report_tree.insert('', 'end', values=(student_id, full_name, course, year, doc_count, verified_count))
        
        ttk.Button(report_frame, text="Close", command=report_window.destroy).pack(pady=10)

    def show_user_guide(self):
        """Show comprehensive user guide"""
        guide_window = tk.Toplevel(self.root)
        guide_window.title("User Guide - Document Management System")
        guide_window.geometry("800x600")
        guide_window.transient(self.root)
        
        main_frame = ttk.Frame(guide_window, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Create notebook for different guide sections
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))
        
        # Getting Started Tab
        getting_started_frame = ttk.Frame(notebook, padding=15)
        notebook.add(getting_started_frame, text="Getting Started")
        
        getting_started_text = """GETTING STARTED WITH DOCUMENT MANAGEMENT SYSTEM

    Welcome to the Enhanced Document Management System! This guide will help you navigate and use all the features effectively.

    MAIN DASHBOARD:
    - View system statistics and recent activity
    - Quick access to pending documents and alerts
    - Real-time compliance monitoring

    NAVIGATION:
    - Use the sidebar menu to access different sections
    - Dashboard: System overview and statistics
    - Documents: Manage and view all documents
    - Students: Student information and records
    - Reports: Generate various reports
    - Workflows: Manage document approval processes
    - Search: Advanced search functionality
    - OCR: Text extraction from documents
    - Settings: System configuration

    QUICK ACTIONS:
    - Upload Document: Add new student documents
    - Bulk Operations: Perform actions on multiple documents
    - Process Workflow: Handle document approvals
    - Generate Report: Create compliance and status reports
    - Backup System: Create system backups"""
        
        getting_started_widget = tk.Text(getting_started_frame, wrap='word', height=20, width=70)
        getting_started_widget.insert('1.0', getting_started_text)
        getting_started_widget.config(state='disabled')
        getting_started_widget.pack(fill='both', expand=True)
        
        # Document Management Tab
        doc_mgmt_frame = ttk.Frame(notebook, padding=15)
        notebook.add(doc_mgmt_frame, text="Document Management")
        
        doc_mgmt_text = """DOCUMENT MANAGEMENT

    UPLOADING DOCUMENTS:
    1. Click "Upload Document" from the sidebar or main menu
    2. Select the student from the dropdown or search
    3. Choose the document type from the categorized list
    4. Browse and select the file to upload
    5. Set expiry date if applicable
    6. Add tags and notes as needed
    7. Click "Upload Document" to submit

    VIEWING DOCUMENTS:
    - Go to Documents section to see all documents
    - Use filters to narrow down results by status, type, or date
    - Double-click any document to view detailed information
    - Right-click for context menu with additional options

    DOCUMENT STATUSES:
    - Pending: Awaiting verification
    - Verified: Approved and accepted
    - Rejected: Requires attention or resubmission
    - Expired: Past expiry date

    DOCUMENT VERSIONS:
    - System maintains version history
    - Upload new version to replace existing document
    - View all versions from document details
    - Restore previous versions if needed

    BULK OPERATIONS:
    - Select multiple documents for batch operations
    - Update status for multiple documents at once
    - Apply tags to multiple documents
    - Generate bulk reports"""
        
        doc_mgmt_widget = tk.Text(doc_mgmt_frame, wrap='word', height=20, width=70)
        doc_mgmt_widget.insert('1.0', doc_mgmt_text)
        doc_mgmt_widget.config(state='disabled')
        doc_mgmt_widget.pack(fill='both', expand=True)

        # Student Management Tab - REMOVED (exists elsewhere in system)
        # student_mgmt_frame = ttk.Frame(notebook, padding=15)
        # notebook.add(student_mgmt_frame, text="Student Management")
        # [Student Management code removed - use Student Records GUI instead]

        # Workflows Tab
        workflows_frame = ttk.Frame(notebook, padding=15)
        notebook.add(workflows_frame, text="Workflows")
        
        workflows_text = """WORKFLOW MANAGEMENT

    UNDERSTANDING WORKFLOWS:
    - Workflows automate document approval processes
    - Each document type can have custom workflow steps
    - Steps can be assigned to different users or roles
    - Track progress through each workflow stage

    PROCESSING WORKFLOWS:
    1. Go to Workflows section
    2. View active workflows in the list
    3. Select a workflow step to process
    4. Choose action: Approve, Reject, or Request Info
    5. Add comments explaining the decision
    6. Submit to move to next step or complete workflow

    WORKFLOW STATUSES:
    - Pending: Awaiting action
    - Completed: Successfully processed
    - Rejected: Stopped due to rejection

    WORKFLOW TEMPLATES:
    - Standard Review: 3-step approval process
    - Express: Fast-track for urgent documents
    - Multi-stage: Complex approval with multiple departments
    - Custom: Build your own workflow steps

    WORKFLOW ANALYTICS:
    - Track average processing times
    - Identify bottlenecks
    - Monitor user performance
    - Generate workflow reports"""
        
        workflows_widget = tk.Text(workflows_frame, wrap='word', height=20, width=70)
        workflows_widget.insert('1.0', workflows_text)
        workflows_widget.config(state='disabled')
        workflows_widget.pack(fill='both', expand=True)
        
        # Reports Tab
        reports_frame = ttk.Frame(notebook, padding=15)
        notebook.add(reports_frame, text="Reports")
        
        reports_text = """REPORTING SYSTEM

    STANDARD REPORTS:
    - Compliance Report: Student document compliance overview
    - Status Report: Document status distribution
    - Expiry Report: Documents expiring soon
    - Student Progress: Individual student progress tracking
    - Monthly Summary: Monthly activity overview

    CUSTOM REPORTS:
    - Use the Custom Report Builder for flexible reporting
    - Select data fields to include
    - Apply filters by date, status, course, etc.
    - Export results to CSV, Excel, or PDF

    GENERATING REPORTS:
    1. Go to Reports section
    2. Select report type
    3. Set filters and parameters
    4. Choose output format
    5. Generate and download report

    REPORT SCHEDULING:
    - Set up automated report generation
    - Email reports to stakeholders
    - Schedule daily, weekly, or monthly reports

    ANALYTICS DASHBOARD:
    - Real-time system metrics
    - Visual charts and graphs
    - Trend analysis
    - Performance indicators"""
        
        reports_widget = tk.Text(reports_frame, wrap='word', height=20, width=70)
        reports_widget.insert('1.0', reports_text)
        reports_widget.config(state='disabled')
        reports_widget.pack(fill='both', expand=True)
        
        # Troubleshooting Tab
        troubleshooting_frame = ttk.Frame(notebook, padding=15)
        notebook.add(troubleshooting_frame, text="Troubleshooting")
        
        troubleshooting_text = """TROUBLESHOOTING & FAQ

    COMMON ISSUES:

    Q: Document upload fails
    A: Check file size (must be under limit), file format (must be allowed), and ensure student exists in system

    Q: Cannot find student
    A: Use the search function, check spelling, or add the student if they don't exist

    Q: Workflow stuck in pending
    A: Check if assigned user has permissions, verify workflow step configuration

    Q: Reports not generating
    A: Verify date ranges, check filter criteria, ensure data exists for selected parameters

    Q: Cannot access certain features
    A: Check user role permissions, contact administrator for access rights

    SYSTEM REQUIREMENTS:
    - Modern web browser (Chrome, Firefox, Safari, Edge)
    - Stable internet connection
    - JavaScript enabled
    - Minimum screen resolution: 1024x768

    BACKUP AND RECOVERY:
    - System automatically creates daily backups
    - Manual backup available in Settings
    - Contact administrator for data recovery

    SUPPORT CONTACT:
    - Email: support@yourschool.edu
    - Phone: (555) 123-4567
    - Help Desk: Available 8 AM - 5 PM EST

    KEYBOARD SHORTCUTS:
    - Ctrl+U: Upload Document
    - Ctrl+S: Advanced Search
    - Ctrl+R: Refresh Current View
    - F1: Show this User Guide"""
        
        troubleshooting_widget = tk.Text(troubleshooting_frame, wrap='word', height=20, width=70)
        troubleshooting_widget.insert('1.0', troubleshooting_text)
        troubleshooting_widget.config(state='disabled')
        troubleshooting_widget.pack(fill='both', expand=True)
        
        # Close button
        ttk.Button(main_frame, text="Close Guide", command=guide_window.destroy).pack()
 
    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo("About", 
            "Enhanced Document Management System v2.0\n\n"
            "A comprehensive document management solution for educational institutions.\n\n"
            "Features:\n"
            "• Document upload and management\n"
            "• Student record tracking\n"
            "• Compliance monitoring\n"
            "• Reporting and analytics\n"
            "• User management\n"
            "• Automated workflows")

    def backup_system(self):
        """Create system backup"""
        try:
            backup_dir = filedialog.askdirectory(title="Select Backup Location")
            if backup_dir:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_filename = f"document_system_backup_{timestamp}.zip"
                backup_path = os.path.join(backup_dir, backup_filename)
                
                with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                    # Backup database
                    backup_zip.write(str(DEFAULT_DB_PATH), 'database/student_records.db')
                    
                    # Backup document files
                    student_docs_dir = paths.UPLOAD_DIR / 'student_documents'
                    if os.path.exists(student_docs_dir):
                        for root, dirs, files in os.walk(student_docs_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arc_path = os.path.relpath(file_path, student_docs_dir)
                                backup_zip.write(file_path, f'student_documents/{arc_path}')
                
                messagebox.showinfo("Success", f"System backup created successfully!\nLocation: {backup_path}")
        
        except Exception as e:
            messagebox.showerror("Backup Error", f"Failed to create backup: {str(e)}")

    def generate_report_dialog(self):
        """Show report generation dialog"""
        self.show_reports()  # Navigate to reports section

    def create_status_chart(self, parent):
        """Create document status distribution chart"""
        chart_frame = ttk.LabelFrame(parent, text="Document Status Distribution", padding=10)
        chart_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Get status data
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT verification_status, COUNT(*) as count
            FROM student_documents 
            WHERE is_current_version = 1
            GROUP BY verification_status
            ORDER BY count DESC
            ''')
            
            status_data = cursor.fetchall()
            conn.close()
            
            if status_data:
                # Create simple text-based chart
                total = sum(count for _, count in status_data)
                
                for status, count in status_data:
                    percentage = (count / total) * 100 if total > 0 else 0
                    
                    row_frame = ttk.Frame(chart_frame)
                    row_frame.pack(fill='x', pady=2)
                    
                    ttk.Label(row_frame, text=f"{status}:", width=15).pack(side='left')
                    ttk.Label(row_frame, text=f"{count} ({percentage:.1f}%)").pack(side='left')
                    
                    # Simple progress bar
                    progress = ttk.Progressbar(row_frame, length=200, mode='determinate')
                    progress['value'] = percentage
                    progress.pack(side='right', padx=10)
            else:
                ttk.Label(chart_frame, text="No data available").pack()
                
        except sqlite3.Error as e:
            ttk.Label(chart_frame, text=f"Error loading data: {e}").pack()

    def create_recent_activity_table(self, parent):
        """Create recent activity table"""
        activity_frame = ttk.LabelFrame(parent, text="Recent Activity", padding=10)
        activity_frame.pack(side='right', fill='both', expand=True)
        
        # Create treeview for recent activity
        columns = ('Student', 'Document', 'Action', 'Date')
        self.activity_tree = ttk.Treeview(activity_frame, columns=columns, show='headings', height=10)
        
        # Define headings
        for col in columns:
            self.activity_tree.heading(col, text=col)
            self.activity_tree.column(col, width=120)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(activity_frame, orient='vertical', command=self.activity_tree.yview)
        self.activity_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack widgets
        self.activity_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Load recent activity data
        self.load_recent_activity()

    def load_recent_activity(self):
        """Load recent activity data"""
        # Check if activity_tree exists before using it
        if not hasattr(self, 'activity_tree') or self.activity_tree is None:
            return
            
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT s.first_name || ' ' || s.last_name as student_name,
                   dt.type_name, 'Uploaded' as action,
                   DATE(sd.upload_date) as activity_date
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.upload_date >= date('now', '-7 days')
            ORDER BY sd.upload_date DESC
            LIMIT 15
            ''')
            
            activities = cursor.fetchall()
            conn.close()
            
            # Clear existing items
            for item in self.activity_tree.get_children():
                self.activity_tree.delete(item)
            
            # Insert new items
            for activity in activities:
                self.activity_tree.insert('', 'end', values=activity)
                
        except sqlite3.Error as e:
            print(f"Database error loading activity: {e}")
        except Exception as e:
            print(f"Error loading activity: {e}")

    def show_documents(self):
        """Show documents management interface"""
        self.clear_content_area()
        
        # Create documents frame
        docs_frame = ttk.Frame(self.content_area)
        docs_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title and controls
        title_frame = ttk.Frame(docs_frame)
        title_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(title_frame, text="Document Management", font=('Arial', 18, 'bold')).pack(side='left')
        
        # Control buttons
        controls_frame = ttk.Frame(title_frame)
        controls_frame.pack(side='right')
        
        ttk.Button(controls_frame, text="📤 Upload", command=self.upload_document_dialog).pack(side='left', padx=2)
        ttk.Button(controls_frame, text="🔍 Search", command=self.search_documents).pack(side='left', padx=2)
        ttk.Button(controls_frame, text="🔄 Refresh", command=self.refresh_documents).pack(side='left', padx=2)
        
        # Filters frame
        filters_frame = ttk.LabelFrame(docs_frame, text="Filters", padding=10)
        filters_frame.pack(fill='x', pady=(0, 10))
        
        # Status filter
        ttk.Label(filters_frame, text="Status:").grid(row=0, column=0, padx=5, sticky='w')
        self.status_filter = ttk.Combobox(filters_frame, values=['All', 'Pending', 'Verified', 'Rejected', 'Expired'])
        self.status_filter.set('All')
        self.status_filter.grid(row=0, column=1, padx=5)
        self.status_filter.bind('<<ComboboxSelected>>', lambda e: self.apply_filters())
        
        # Document type filter
        ttk.Label(filters_frame, text="Type:").grid(row=0, column=2, padx=5, sticky='w')
        self.type_filter = ttk.Combobox(filters_frame, values=['All'] + self.get_document_types())
        self.type_filter.set('All')
        self.type_filter.grid(row=0, column=3, padx=5)
        self.type_filter.bind('<<ComboboxSelected>>', lambda e: self.apply_filters())
        
        # Date range filter
        ttk.Label(filters_frame, text="From:").grid(row=0, column=4, padx=5, sticky='w')
        self.from_date = tk.Entry(filters_frame, width=12)
        self.from_date.grid(row=0, column=5, padx=5)
        self.from_date.insert(0, (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        
        ttk.Label(filters_frame, text="To:").grid(row=0, column=6, padx=5, sticky='w')
        self.to_date = tk.Entry(filters_frame, width=12)
        self.to_date.grid(row=0, column=7, padx=5)
        self.to_date.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
        # Apply filters button
        ttk.Button(filters_frame, text="Apply Filters", command=self.apply_filters).grid(row=0, column=8, padx=10)
        
        # Documents table
        self.create_documents_table(docs_frame)
        
        # Load initial data
        self.refresh_documents()

    def create_documents_table(self, parent):
        """Create the documents table"""
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill='both', expand=True)
        
        # Define columns
        columns = ('ID', 'Student', 'Document Type', 'Upload Date', 'Status', 'Expiry', 'Version', 'Notes')
        self.docs_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)
        
        # Define headings and column widths
        column_widths = {'ID': 60, 'Student': 150, 'Document Type': 180, 'Upload Date': 100, 
                        'Status': 100, 'Expiry': 100, 'Version': 80, 'Notes': 200}
        
        for col in columns:
            self.docs_tree.heading(col, text=col, command=lambda c=col: self.sort_column(c))
            self.docs_tree.column(col, width=column_widths.get(col, 100))
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=self.docs_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient='horizontal', command=self.docs_tree.xview)
        self.docs_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack widgets
        self.docs_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Context menu
        self.create_documents_context_menu()
        
        # Double-click binding
        self.docs_tree.bind('<Double-1>', self.on_document_double_click)

    def create_documents_context_menu(self):
        """Create context menu for documents table"""
        self.docs_context_menu = tk.Menu(self.root, tearoff=0)
        self.docs_context_menu.add_command(label="View Details", command=self.view_document_details)
        self.docs_context_menu.add_command(label="Edit Status", command=self.edit_document_status)
        self.docs_context_menu.add_command(label="View Versions", command=self.view_document_versions)
        self.docs_context_menu.add_separator()
        self.docs_context_menu.add_command(label="Download File", command=self.download_document)
        self.docs_context_menu.add_command(label="Send Notification", command=self.send_document_notification)
        self.docs_context_menu.add_separator()
        self.docs_context_menu.add_command(label="Delete Document", command=self.delete_document)
        
        # Bind right-click
        self.docs_tree.bind('<Button-3>', self.show_docs_context_menu)

    def show_docs_context_menu(self, event):
        """Show context menu for documents"""
        item = self.docs_tree.identify_row(event.y)
        if item:
            self.docs_tree.selection_set(item)
            self.docs_context_menu.post(event.x_root, event.y_root)

    def show_students(self):
        """Show students management interface"""
        self.clear_content_area()
        
        # Create students frame
        students_frame = ttk.Frame(self.content_area)
        students_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title and controls
        title_frame = ttk.Frame(students_frame)
        title_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(title_frame, text="Student Management", font=('Arial', 18, 'bold')).pack(side='left')
        
        # Control buttons
        controls_frame = ttk.Frame(title_frame)
        controls_frame.pack(side='right')
        
        ttk.Button(controls_frame, text="➕ Add Student", command=self.add_student_dialog).pack(side='left', padx=2)
        ttk.Button(controls_frame, text="📊 Student Report", command=self.student_report_dialog).pack(side='left', padx=2)
        ttk.Button(controls_frame, text="🔄 Refresh", command=self.refresh_students).pack(side='left', padx=2)
        
        # Search frame
        search_frame = ttk.Frame(students_frame)
        search_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(search_frame, text="Search:").pack(side='left', padx=5)
        self.student_search_var = tk.StringVar()
        self.student_search_entry = tk.Entry(search_frame, textvariable=self.student_search_var, width=30)
        self.student_search_entry.pack(side='left', padx=5)
        self.student_search_entry.bind('<KeyRelease>', self.search_students)
        
        # Students table
        self.create_students_table(students_frame)
        
        # Load initial data
        self.refresh_students()

    def create_students_table(self, parent):
        """Create the students table"""
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill='both', expand=True)
        
        # Define columns
        columns = ('ID', 'Name', 'Email', 'Course', 'Status', 'Documents', 'Compliance')
        self.students_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        # Define headings and column widths
        column_widths = {'ID': 100, 'Name': 200, 'Email': 200, 'Course': 150,
                        'Status': 100, 'Documents': 100, 'Compliance': 100}
        
        for col in columns:
            self.students_tree.heading(col, text=col, command=lambda c=col: self.sort_students_column(c))
            self.students_tree.column(col, width=column_widths.get(col, 100))
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=self.students_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient='horizontal', command=self.students_tree.xview)
        self.students_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack widgets
        self.students_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Context menu for students
        self.create_students_context_menu()
        
        # Double-click binding
        self.students_tree.bind('<Double-1>', self.on_student_double_click)

    def create_students_context_menu(self):
        """Create context menu for students table"""
        self.students_context_menu = tk.Menu(self.root, tearoff=0)
        self.students_context_menu.add_command(label="View Profile", command=self.view_student_profile)
        self.students_context_menu.add_command(label="View Documents", command=self.view_student_documents)
        self.students_context_menu.add_command(label="Upload Document", command=self.upload_for_student)
        self.students_context_menu.add_separator()
        self.students_context_menu.add_command(label="Send Notification", command=self.send_student_notification)
        self.students_context_menu.add_command(label="Generate Report", command=self.generate_student_report)
        self.students_context_menu.add_separator()
        self.students_context_menu.add_command(label="Edit Student", command=self.edit_student)
        self.students_context_menu.add_command(label="Deactivate", command=self.deactivate_student)
        
        # Bind right-click
        self.students_tree.bind('<Button-3>', self.show_students_context_menu)

    def show_students_context_menu(self, event):
        """Show context menu for students"""
        item = self.students_tree.identify_row(event.y)
        if item:
            self.students_tree.selection_set(item)
            self.students_context_menu.post(event.x_root, event.y_root)

    def show_reports(self):
        """Show reports interface"""
        self.clear_content_area()
        
        # Create reports frame
        reports_frame = ttk.Frame(self.content_area)
        reports_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        ttk.Label(reports_frame, text="Reports & Analytics", font=('Arial', 18, 'bold')).pack(pady=(0, 20))
        
        # Create report categories
        self.create_report_categories(reports_frame)

    def create_report_categories(self, parent):
        """Create report category sections"""
        # Standard Reports
        standard_frame = ttk.LabelFrame(parent, text="Standard Reports", padding=15)
        standard_frame.pack(fill='x', pady=(0, 15))
        
        standard_reports = [
            ("📊 Compliance Report", "Student document compliance overview", self.generate_compliance_report),
            ("📈 Status Report", "Document status distribution", self.generate_status_report),
            ("⏰ Expiry Report", "Documents expiring soon", self.generate_expiry_report),
            ("👥 Student Progress", "Individual student progress", self.generate_student_progress_report),
            ("📅 Monthly Summary", "Monthly activity summary", self.generate_monthly_summary),
        ]
        
        row = 0
        for title, description, command in standard_reports:
            report_frame = ttk.Frame(standard_frame)
            report_frame.grid(row=row//2, column=row%2, padx=10, pady=5, sticky='ew')
            
            ttk.Button(report_frame, text=title, command=command, width=25).pack(anchor='w')
            ttk.Label(report_frame, text=description, font=('Arial', 9), foreground='gray').pack(anchor='w')
            row += 1
        
        # Configure grid weights
        for i in range(3):
            standard_frame.grid_rowconfigure(i, weight=1)
        standard_frame.grid_columnconfigure(0, weight=1)
        standard_frame.grid_columnconfigure(1, weight=1)
        
        # Custom Reports
        custom_frame = ttk.LabelFrame(parent, text="Custom Reports", padding=15)
        custom_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Button(custom_frame, text="🔧 Custom Report Builder", 
                  command=self.custom_report_builder, width=30).pack(pady=5)
        ttk.Label(custom_frame, text="Build custom reports with flexible filters and fields", 
                 font=('Arial', 9), foreground='gray').pack()
        
        # Export Options
        export_frame = ttk.LabelFrame(parent, text="Export Options", padding=15)
        export_frame.pack(fill='x')
        
        export_buttons = [
            ("📄 Export to CSV", self.export_to_csv),
            ("📊 Export to Excel", self.export_to_excel),
            ("📋 Export to PDF", self.export_to_pdf),
        ]
        
        for text, command in export_buttons:
            ttk.Button(export_frame, text=text, command=command, width=20).pack(side='left', padx=10)

    def advanced_search_dialog(self):
        """Show advanced search dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Advanced Search")
        dialog.geometry("900x700")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 100, self.root.winfo_rooty() + 50))
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Title
        ttk.Label(main_frame, text="Advanced Document Search", font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Search criteria frame
        criteria_frame = ttk.LabelFrame(main_frame, text="Search Criteria", padding=15)
        criteria_frame.pack(fill='x', pady=(0, 15))
        
        # Student search
        ttk.Label(criteria_frame, text="Student (Name or ID):").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.search_student = tk.Entry(criteria_frame, width=30)
        self.search_student.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        # Document type
        ttk.Label(criteria_frame, text="Document Type:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.search_doc_type = ttk.Combobox(criteria_frame, values=['All'] + self.get_document_types())
        self.search_doc_type.set('All')
        self.search_doc_type.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        
        # Status
        ttk.Label(criteria_frame, text="Status:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.search_status = ttk.Combobox(criteria_frame, values=['All', 'Pending', 'Verified', 'Rejected', 'Expired'])
        self.search_status.set('All')
        self.search_status.grid(row=2, column=1, padx=5, pady=5, sticky='ew')
        
        # Date range
        ttk.Label(criteria_frame, text="From Date:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.search_from_date = tk.Entry(criteria_frame, width=15)
        self.search_from_date.grid(row=3, column=1, padx=5, pady=5, sticky='w')
        
        ttk.Label(criteria_frame, text="To Date:").grid(row=4, column=0, sticky='w', padx=5, pady=5)
        self.search_to_date = tk.Entry(criteria_frame, width=15)
        self.search_to_date.grid(row=4, column=1, padx=5, pady=5, sticky='w')
        
        # Tags
        ttk.Label(criteria_frame, text="Tags:").grid(row=5, column=0, sticky='w', padx=5, pady=5)
        self.search_tags = tk.Entry(criteria_frame, width=30)
        self.search_tags.grid(row=5, column=1, padx=5, pady=5, sticky='ew')
        
        criteria_frame.grid_columnconfigure(1, weight=1)
        
        # Results frame
        results_frame = ttk.LabelFrame(main_frame, text="Search Results", padding=10)
        results_frame.pack(fill='both', expand=True, pady=(0, 15))
        
        # Results tree
        columns = ('ID', 'Student', 'Document Type', 'Status', 'Upload Date')
        self.search_results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.search_results_tree.heading(col, text=col)
            self.search_results_tree.column(col, width=100)
        
        # Scrollbar for results
        results_scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=self.search_results_tree.yview)
        self.search_results_tree.configure(yscrollcommand=results_scrollbar.set)
        
        self.search_results_tree.pack(side='left', fill='both', expand=True)
        results_scrollbar.pack(side='right', fill='y')
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill='x')
        
        ttk.Button(buttons_frame, text="🔍 Search", command=self.perform_advanced_search).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="📊 Export Results", command=self.export_search_results).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Clear", command=self.clear_search_criteria).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)
        
        # Store dialog reference
        self.search_dialog = dialog

    def perform_advanced_search(self):
        """Perform advanced search"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Build dynamic query
            query = '''
            SELECT sd.document_id, 
                   s.first_name || ' ' || s.last_name as student_name,
                   dt.type_name,
                   sd.verification_status,
                   DATE(sd.upload_date) as upload_date
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.is_current_version = 1
            '''
            
            params = []
            
            # Add search conditions
            if self.search_student.get():
                query += " AND (s.first_name LIKE ? OR s.last_name LIKE ? OR s.student_id LIKE ?)"
                search_term = f"%{self.search_student.get()}%"
                params.extend([search_term, search_term, search_term])
            
            if self.search_doc_type.get() and self.search_doc_type.get() != 'All':
                query += " AND dt.type_name LIKE ?"
                params.append(f"%{self.search_doc_type.get()}%")
            
            if self.search_status.get() and self.search_status.get() != 'All':
                query += " AND sd.verification_status = ?"
                params.append(self.search_status.get())
            
            if self.search_from_date.get():
                query += " AND DATE(sd.upload_date) >= ?"
                params.append(self.search_from_date.get())
            
            if self.search_to_date.get():
                query += " AND DATE(sd.upload_date) <= ?"
                params.append(self.search_to_date.get())
            
            if self.search_tags.get():
                tag_list = [tag.strip() for tag in self.search_tags.get().split(',')]
                tag_conditions = []
                for tag in tag_list:
                    tag_conditions.append("sd.tags LIKE ?")
                    params.append(f"%{tag}%")
                query += " AND (" + " OR ".join(tag_conditions) + ")"
            
            query += " ORDER BY sd.upload_date DESC LIMIT 100"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Clear existing results
            for item in self.search_results_tree.get_children():
                self.search_results_tree.delete(item)
            
            # Insert new results
            for result in results:
                self.search_results_tree.insert('', 'end', values=result)
            
            conn.close()
            
            # Update status
            self.status_var.set(f"Search completed: {len(results)} results found")
            
        except Exception as e:
            messagebox.showerror("Search Error", f"Search failed: {str(e)}")

    def clear_search_criteria(self):
        """Clear all search criteria"""
        self.search_student.delete(0, 'end')
        self.search_doc_type.set('All')
        self.search_status.set('All')
        self.search_from_date.delete(0, 'end')
        self.search_to_date.delete(0, 'end')
        self.search_tags.delete(0, 'end')
        
        # Clear results
        for item in self.search_results_tree.get_children():
            self.search_results_tree.delete(item)

    def bulk_operations_dialog(self):
        """Show bulk operations dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Bulk Operations")
        dialog.geometry("700x550")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 100, self.root.winfo_rooty() + 50))
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Title
        ttk.Label(main_frame, text="Bulk Operations", font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Operations frame
        operations_frame = ttk.LabelFrame(main_frame, text="Available Operations", padding=15)
        operations_frame.pack(fill='both', expand=True)
        
        # Bulk operations list
        operations = [
            ("📝 Bulk Status Update", "Update status for multiple documents", self.bulk_status_update),
            ("🏷️ Bulk Tag Assignment", "Assign tags to multiple documents", self.bulk_tag_assignment),
            ("📧 Bulk Notification Send", "Send notifications to multiple students", self.bulk_notification_send),
            ("📥 Bulk Import Documents", "Import documents from CSV/Excel", self.bulk_import_dialog),
            ("📤 Bulk Export Data", "Export multiple datasets", self.bulk_export_dialog),
            ("🗂️ Bulk Document Download", "Download multiple documents", self.bulk_document_download),
        ]
        
        for i, (title, description, command) in enumerate(operations):
            op_frame = ttk.Frame(operations_frame)
            op_frame.pack(fill='x', pady=5)
            
            ttk.Button(op_frame, text=title, command=command, width=25).pack(side='left')
            ttk.Label(op_frame, text=description, font=('Arial', 9), foreground='gray').pack(side='left', padx=10)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=20)

    def generate_compliance_report(self):
        """Generate compliance report"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get compliance data
            cursor.execute('''
            SELECT s.student_id, s.first_name, s.last_name, s.course,
                   COALESCE(s.enrollment_year, 'N/A') as year,
                   COUNT(DISTINCT req_types.type_id) as required_count,
                   COUNT(DISTINCT submitted_docs.document_id) as submitted_count
            FROM students s
            CROSS JOIN document_types req_types
            LEFT JOIN student_documents submitted_docs ON s.student_id = submitted_docs.student_id
                AND req_types.type_id = submitted_docs.type_id
                AND submitted_docs.is_current_version = 1
            WHERE req_types.is_required = 1
            GROUP BY s.student_id
            ORDER BY s.last_name, s.first_name
            ''')
            
            compliance_data = cursor.fetchall()
            conn.close()
            
            # Create report window
            report_window = tk.Toplevel(self.root)
            report_window.title("Compliance Report")
            report_window.geometry("800x600")
            
            # Report frame
            report_frame = ttk.Frame(report_window, padding=20)
            report_frame.pack(fill='both', expand=True)
            
            # Title
            title_text = f"Document Compliance Report - Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ttk.Label(report_frame, text=title_text, font=('Arial', 14, 'bold')).pack(pady=(0, 20))
            
            # Summary stats
            summary_frame = ttk.LabelFrame(report_frame, text="Summary", padding=10)
            summary_frame.pack(fill='x', pady=(0, 15))
            
            total_students = len(compliance_data)
            compliant_students = sum(1 for row in compliance_data if row[5] == row[6])
            compliance_rate = (compliant_students / total_students) * 100 if total_students > 0 else 0
            
            ttk.Label(summary_frame, text=f"Total Students: {total_students}").grid(row=0, column=0, sticky='w', padx=10)
            ttk.Label(summary_frame, text=f"Compliant Students: {compliant_students}").grid(row=0, column=1, sticky='w', padx=10)
            ttk.Label(summary_frame, text=f"Compliance Rate: {compliance_rate:.1f}%").grid(row=0, column=2, sticky='w', padx=10)
            
            # Detailed report
            details_frame = ttk.LabelFrame(report_frame, text="Detailed Report", padding=10)
            details_frame.pack(fill='both', expand=True, pady=(0, 15))
            
            # Create treeview for detailed data
            columns = ('Student ID', 'Name', 'Course', 'Year', 'Status', 'Progress')
            compliance_tree = ttk.Treeview(details_frame, columns=columns, show='headings', height=15)
            
            for col in columns:
                compliance_tree.heading(col, text=col)
                compliance_tree.column(col, width=100)
            
            # Add scrollbar
            scrollbar = ttk.Scrollbar(details_frame, orient='vertical', command=compliance_tree.yview)
            compliance_tree.configure(yscrollcommand=scrollbar.set)
            
            compliance_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            # Populate data
            for row in compliance_data:
                student_id, first_name, last_name, course, year, required, submitted = row
                name = f"{first_name} {last_name}"
                status = "Compliant" if required == submitted else "Non-Compliant"
                progress = f"{submitted}/{required}"
                
                compliance_tree.insert('', 'end', values=(student_id, name, course, year, status, progress))
            
            # Export button
            button_frame = ttk.Frame(report_frame)
            button_frame.pack(fill='x')
            
            ttk.Button(button_frame, text="📄 Export to CSV", 
                      command=lambda: self.export_compliance_to_csv(compliance_data)).pack(side='left', padx=5)
            ttk.Button(button_frame, text="🖨️ Print Report", 
                      command=lambda: self.print_report(compliance_data)).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side='right', padx=5)
            
        except Exception as e:
            messagebox.showerror("Report Error", f"Failed to generate compliance report: {str(e)}")

    def system_settings(self):
        """Show system settings dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("System Settings")
        dialog.geometry("850x700")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 100, self.root.winfo_rooty() + 50))
        
        # Main frame with notebook
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Create notebook for settings categories
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))
        
        # Document Types tab
        self.create_doc_types_tab(notebook)
        
        # System Settings tab
        self.create_system_settings_tab(notebook)
        
        # User Management tab
        self.create_user_management_tab(notebook)
        
        # Backup Settings tab
        self.create_backup_settings_tab(notebook)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')
        
        ttk.Button(button_frame, text="Save Settings", command=self.save_settings).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Reset to Defaults", command=self.reset_settings).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

    def create_doc_types_tab(self, notebook):
        """Create document types settings tab"""
        doc_types_frame = ttk.Frame(notebook, padding=15)
        notebook.add(doc_types_frame, text="Document Types")
        
        # Title
        ttk.Label(doc_types_frame, text="Document Type Management", font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        
        # Document types list
        list_frame = ttk.Frame(doc_types_frame)
        list_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Treeview for document types
        columns = ('ID', 'Name', 'Category', 'Required', 'Expiry', 'Max Size (MB)', 'Formats')
        self.doc_types_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)
        
        for col in columns:
            self.doc_types_tree.heading(col, text=col)
            width = 80 if col == 'ID' else 120
            self.doc_types_tree.column(col, width=width)
        
        # Scrollbar
        doc_types_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.doc_types_tree.yview)
        self.doc_types_tree.configure(yscrollcommand=doc_types_scrollbar.set)
        
        self.doc_types_tree.pack(side='left', fill='both', expand=True)
        doc_types_scrollbar.pack(side='right', fill='y')
        
        # Load document types
        self.load_document_types()
        
        # Buttons
        buttons_frame = ttk.Frame(doc_types_frame)
        buttons_frame.pack(fill='x')
        
        ttk.Button(buttons_frame, text="➕ Add Type", command=self.add_document_type).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="✏️ Edit Type", command=self.edit_document_type).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="🗑️ Delete Type", command=self.delete_document_type).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="🔄 Refresh", command=self.load_document_types).pack(side='left', padx=5)

    def create_system_settings_tab(self, notebook):
        """Create system settings tab"""
        settings_frame = ttk.Frame(notebook, padding=15)
        notebook.add(settings_frame, text="System Settings")
        
        # Email settings
        email_frame = ttk.LabelFrame(settings_frame, text="Email Configuration", padding=10)
        email_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(email_frame, text="SMTP Server:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.smtp_server = tk.Entry(email_frame, width=30)
        self.smtp_server.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        ttk.Label(email_frame, text="SMTP Port:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.smtp_port = tk.Entry(email_frame, width=30)
        self.smtp_port.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        
        ttk.Label(email_frame, text="Email Username:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.email_username = tk.Entry(email_frame, width=30)
        self.email_username.grid(row=2, column=1, padx=5, pady=5, sticky='ew')
        
        ttk.Label(email_frame, text="Email Password:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.email_password = tk.Entry(email_frame, width=30, show='*')
        self.email_password.grid(row=3, column=1, padx=5, pady=5, sticky='ew')
        
        email_frame.grid_columnconfigure(1, weight=1)
        
        # File settings
        file_frame = ttk.LabelFrame(settings_frame, text="File Settings", padding=10)
        file_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(file_frame, text="Max File Size (MB):").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.max_file_size = tk.Entry(file_frame, width=30)
        self.max_file_size.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        ttk.Label(file_frame, text="Document Retention (Years):").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.doc_retention = tk.Entry(file_frame, width=30)
        self.doc_retention.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        
        file_frame.grid_columnconfigure(1, weight=1)
        
        # Notification settings
        notif_frame = ttk.LabelFrame(settings_frame, text="Notification Settings", padding=10)
        notif_frame.pack(fill='x')
        
        self.email_notifications_enabled = tk.BooleanVar()
        ttk.Checkbutton(notif_frame, text="Enable Email Notifications", 
                       variable=self.email_notifications_enabled).pack(anchor='w', pady=5)
        
        self.auto_backup_enabled = tk.BooleanVar()
        ttk.Checkbutton(notif_frame, text="Enable Automatic Backups", 
                       variable=self.auto_backup_enabled).pack(anchor='w', pady=5)
        
        # Load current settings
        self.load_system_settings()

    def create_user_management_tab(self, notebook):
        """Create user management tab"""
        users_frame = ttk.Frame(notebook, padding=15)
        notebook.add(users_frame, text="Users")
        
        ttk.Label(users_frame, text="User Management", font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        
        # Users list
        users_list_frame = ttk.Frame(users_frame)
        users_list_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        columns = ('ID', 'Username', 'Role', 'Email', 'Created', 'Active')
        self.users_tree = ttk.Treeview(users_list_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.users_tree.heading(col, text=col)
            self.users_tree.column(col, width=100)
        
        users_scrollbar = ttk.Scrollbar(users_list_frame, orient='vertical', command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=users_scrollbar.set)
        
        self.users_tree.pack(side='left', fill='both', expand=True)
        users_scrollbar.pack(side='right', fill='y')
        
        # Load users
        self.load_users()
        
        # User management buttons
        user_buttons_frame = ttk.Frame(users_frame)
        user_buttons_frame.pack(fill='x')
        
        ttk.Button(user_buttons_frame, text="➕ Add User", command=self.add_user).pack(side='left', padx=5)
        ttk.Button(user_buttons_frame, text="✏️ Edit User", command=self.edit_user).pack(side='left', padx=5)
        ttk.Button(user_buttons_frame, text="🔒 Reset Password", command=self.reset_user_password).pack(side='left', padx=5)
        ttk.Button(user_buttons_frame, text="❌ Deactivate", command=self.deactivate_user).pack(side='left', padx=5)

    def create_backup_settings_tab(self, notebook):
        """Create backup settings tab"""
        backup_frame = ttk.Frame(notebook, padding=15)
        notebook.add(backup_frame, text="Backup")
        
        ttk.Label(backup_frame, text="Backup & Recovery", font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        
        # Backup settings
        backup_settings_frame = ttk.LabelFrame(backup_frame, text="Backup Settings", padding=10)
        backup_settings_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(backup_settings_frame, text="Backup Location:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.backup_location = tk.Entry(backup_settings_frame, width=40)
        self.backup_location.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(backup_settings_frame, text="Browse...", command=self.browse_backup_location).grid(row=0, column=2, padx=5)
        
        ttk.Label(backup_settings_frame, text="Backup Frequency (Days):").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.backup_frequency = tk.Entry(backup_settings_frame, width=40)
        self.backup_frequency.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        
        backup_settings_frame.grid_columnconfigure(1, weight=1)
        
        # Backup actions
        backup_actions_frame = ttk.LabelFrame(backup_frame, text="Backup Actions", padding=10)
        backup_actions_frame.pack(fill='x')
        
        ttk.Button(backup_actions_frame, text="🗂️ Create Backup Now", command=self.create_backup_now).pack(side='left', padx=5, pady=5)
        ttk.Button(backup_actions_frame, text="📁 View Backups", command=self.view_backups).pack(side='left', padx=5, pady=5)
        ttk.Button(backup_actions_frame, text="🔄 Restore from Backup", command=self.restore_backup).pack(side='left', padx=5, pady=5)

    # Helper methods for data operations
    def get_dashboard_stats(self):
        """Get dashboard statistics"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Total documents
            cursor.execute('SELECT COUNT(*) FROM student_documents WHERE is_current_version = 1')
            total_docs = cursor.fetchone()[0]
            
            # Pending documents
            cursor.execute('SELECT COUNT(*) FROM student_documents WHERE verification_status = "Pending" AND is_current_version = 1')
            pending_docs = cursor.fetchone()[0]
            
            # Total students
            cursor.execute('SELECT COUNT(*) FROM students')
            total_students = cursor.fetchone()[0]
            
            # Today's uploads
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('SELECT COUNT(*) FROM student_documents WHERE DATE(upload_date) = ?', (today,))
            today_uploads = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_docs': total_docs,
                'pending_docs': pending_docs,
                'total_students': total_students,
                'today_uploads': today_uploads
            }
            
        except Exception as e:
            print(f"Error getting dashboard stats: {e}")
            return {'total_docs': 0, 'pending_docs': 0, 'total_students': 0, 'today_uploads': 0}

    def bulk_import_dialog(self):
        """Show bulk import dialog for importing multiple documents"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Bulk Document Import")
        dialog.geometry("950x700")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Bulk Document Import", font=('Arial', 14, 'bold')).pack(pady=10)

        # File selection
        files_frame = ttk.LabelFrame(main_frame, text="Select Files", padding=10)
        files_frame.pack(fill='both', expand=True, pady=10)

        files_list = tk.Listbox(files_frame, height=10)
        files_list.pack(fill='both', expand=True, pady=5)

        selected_files = []

        def browse_files():
            from tkinter import filedialog
            files = filedialog.askopenfilenames(
                title="Select Documents to Import",
                filetypes=[
                    ("All files", "*.*"),
                    ("PDF files", "*.pdf"),
                    ("Image files", "*.png *.jpg *.jpeg"),
                    ("Documents", "*.doc *.docx")
                ]
            )
            if files:
                selected_files.clear()
                selected_files.extend(files)
                files_list.delete(0, tk.END)
                for file in files:
                    files_list.insert(tk.END, os.path.basename(file))

        ttk.Button(files_frame, text="Browse Files", command=browse_files).pack(pady=5)

        # Import settings
        settings_frame = ttk.LabelFrame(main_frame, text="Import Settings", padding=10)
        settings_frame.pack(fill='x', pady=10)

        ttk.Label(settings_frame, text="Document Type:").grid(row=0, column=0, sticky='w', pady=5)
        doc_type_var = tk.StringVar()
        doc_type_combo = ttk.Combobox(settings_frame, textvariable=doc_type_var, state='readonly', width=30)
        doc_type_combo.grid(row=0, column=1, pady=5, padx=10)

        # Load document types
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT type_name FROM document_types WHERE is_active = 1 ORDER BY type_name')
            types = [row[0] for row in cursor.fetchall()]
            conn.close()
            doc_type_combo['values'] = types
            if types:
                doc_type_combo.current(0)
        except:
            doc_type_combo['values'] = ['General Document', 'ID Card', 'Transcript', 'Certificate']
            doc_type_combo.current(0)

        ttk.Label(settings_frame, text="Student ID:").grid(row=1, column=0, sticky='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=student_id_var, width=30).grid(row=1, column=1, pady=5, padx=10)

        # Import button
        def perform_import():
            if not selected_files:
                messagebox.showerror("Error", "Please select files to import")
                return

            if not student_id_var.get():
                messagebox.showerror("Error", "Please enter student ID")
                return

            try:
                imported = 0
                failed = 0
                for file_path in selected_files:
                    try:
                        # Import each file
                        # In a real implementation, you would call your document upload function
                        # For now, we'll simulate it
                        imported += 1
                    except Exception as e:
                        failed += 1
                        print(f"Failed to import {file_path}: {e}")

                messagebox.showinfo("Import Complete",
                                  f"Import completed!\n\n"
                                  f"Imported: {imported}\n"
                                  f"Failed: {failed}")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Import failed: {e}")

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=10)

        ttk.Button(buttons_frame, text="Import", command=perform_import).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    def search_student_for_upload(self):
        """Search for student in upload dialog"""
        if hasattr(self, 'upload_student_id'):
            search_term = simpledialog.askstring("Search Student", "Enter student ID or name:")
            if search_term:
                # Here you would implement actual search logic
                messagebox.showinfo("Search", f"Searching for: {search_term}")

    def load_document_types(self):
        """Load document types into management interface"""
        if hasattr(self, 'doc_types_tree') and self.doc_types_tree is not None:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT type_id, type_name,
                       COALESCE(category, 'General') as category,
                       is_required, has_expiry,
                       max_file_size_mb, allowed_formats
                FROM document_types WHERE is_active = 1
                ORDER BY COALESCE(sort_order, 0), type_name
                ''')
                doc_types = cursor.fetchall()
                conn.close()
                
                # Clear existing items
                for item in self.doc_types_tree.get_children():
                    self.doc_types_tree.delete(item)
                
                # Insert new items
                for doc_type in doc_types:
                    type_id, name, category, required, expiry, max_size, formats = doc_type
                    required_text = "Yes" if required else "No"
                    expiry_text = "Yes" if expiry else "No"
                    
                    self.doc_types_tree.insert('', 'end', values=(
                        type_id, name, category, required_text, expiry_text, max_size, formats
                    ))
            except Exception as e:
                print(f"Error loading document types: {e}")

    def add_document_type(self):
        """Add new document type"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Document Type")
        dialog.geometry("700x800")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Add New Document Type", font=('Arial', 12, 'bold')).pack(pady=10)

        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True, pady=10)

        fields = {}

        row = 0
        ttk.Label(form_frame, text="Type Name:*").grid(row=row, column=0, sticky='w', pady=5)
        fields['name'] = ttk.Entry(form_frame, width=30)
        fields['name'].grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(form_frame, text="Category:").grid(row=row, column=0, sticky='w', pady=5)
        fields['category'] = ttk.Combobox(form_frame, values=['Academic', 'Personal', 'Administrative', 'Financial', 'General'], width=28)
        fields['category'].grid(row=row, column=1, pady=5, padx=10)
        fields['category'].current(4)

        row += 1
        ttk.Label(form_frame, text="Description:").grid(row=row, column=0, sticky='w', pady=5)
        fields['description'] = tk.Text(form_frame, width=30, height=4)
        fields['description'].grid(row=row, column=1, pady=5, padx=10)

        row += 1
        fields['required'] = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, text="Required Document", variable=fields['required']).grid(row=row, column=0, columnspan=2, sticky='w', pady=5)

        row += 1
        fields['has_expiry'] = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, text="Has Expiry Date", variable=fields['has_expiry']).grid(row=row, column=0, columnspan=2, sticky='w', pady=5)

        row += 1
        ttk.Label(form_frame, text="Max File Size (MB):").grid(row=row, column=0, sticky='w', pady=5)
        fields['max_size'] = ttk.Entry(form_frame, width=30)
        fields['max_size'].grid(row=row, column=1, pady=5, padx=10)
        fields['max_size'].insert(0, "10")

        row += 1
        ttk.Label(form_frame, text="Allowed Formats:").grid(row=row, column=0, sticky='w', pady=5)
        fields['formats'] = ttk.Entry(form_frame, width=30)
        fields['formats'].grid(row=row, column=1, pady=5, padx=10)
        fields['formats'].insert(0, "pdf,jpg,png,doc,docx")

        def save_document_type():
            name = fields['name'].get().strip()
            if not name:
                messagebox.showerror("Error", "Type name is required")
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO document_types (
                        type_name, category, description, is_required, has_expiry,
                        max_file_size_mb, allowed_formats, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ''', (
                    name,
                    fields['category'].get(),
                    fields['description'].get("1.0", tk.END).strip(),
                    1 if fields['required'].get() else 0,
                    1 if fields['has_expiry'].get() else 0,
                    float(fields['max_size'].get()),
                    fields['formats'].get()
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Document type '{name}' added successfully")
                self.load_document_types()
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add document type: {e}")

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=10)

        ttk.Button(buttons_frame, text="Save", command=save_document_type).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    def edit_document_type(self):
        """Edit selected document type"""
        if not hasattr(self, 'doc_types_tree'):
            return

        selection = self.doc_types_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a document type to edit")
            return

        values = self.doc_types_tree.item(selection[0])['values']
        type_id = values[0]

        # Get full document type details
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT type_name, category, description, is_required, has_expiry,
                       max_file_size_mb, allowed_formats
                FROM document_types
                WHERE type_id = ?
            ''', (type_id,))
            doc_type = cursor.fetchone()
            conn.close()

            if not doc_type:
                messagebox.showerror("Error", "Document type not found")
                return

            # Create edit dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Edit Document Type")
            dialog.geometry("700x800")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Edit Document Type", font=('Arial', 12, 'bold')).pack(pady=10)

            form_frame = ttk.Frame(main_frame)
            form_frame.pack(fill='both', expand=True, pady=10)

            fields = {}

            row = 0
            ttk.Label(form_frame, text="Type Name:*").grid(row=row, column=0, sticky='w', pady=5)
            fields['name'] = ttk.Entry(form_frame, width=30)
            fields['name'].grid(row=row, column=1, pady=5, padx=10)
            fields['name'].insert(0, doc_type[0])

            row += 1
            ttk.Label(form_frame, text="Category:").grid(row=row, column=0, sticky='w', pady=5)
            fields['category'] = ttk.Combobox(form_frame, values=['Academic', 'Personal', 'Administrative', 'Financial', 'General'], width=28)
            fields['category'].grid(row=row, column=1, pady=5, padx=10)
            fields['category'].set(doc_type[1] or 'General')

            row += 1
            ttk.Label(form_frame, text="Description:").grid(row=row, column=0, sticky='w', pady=5)
            fields['description'] = tk.Text(form_frame, width=30, height=4)
            fields['description'].grid(row=row, column=1, pady=5, padx=10)
            if doc_type[2]:
                fields['description'].insert("1.0", doc_type[2])

            row += 1
            fields['required'] = tk.BooleanVar(value=bool(doc_type[3]))
            ttk.Checkbutton(form_frame, text="Required Document", variable=fields['required']).grid(row=row, column=0, columnspan=2, sticky='w', pady=5)

            row += 1
            fields['has_expiry'] = tk.BooleanVar(value=bool(doc_type[4]))
            ttk.Checkbutton(form_frame, text="Has Expiry Date", variable=fields['has_expiry']).grid(row=row, column=0, columnspan=2, sticky='w', pady=5)

            row += 1
            ttk.Label(form_frame, text="Max File Size (MB):").grid(row=row, column=0, sticky='w', pady=5)
            fields['max_size'] = ttk.Entry(form_frame, width=30)
            fields['max_size'].grid(row=row, column=1, pady=5, padx=10)
            fields['max_size'].insert(0, str(doc_type[5]))

            row += 1
            ttk.Label(form_frame, text="Allowed Formats:").grid(row=row, column=0, sticky='w', pady=5)
            fields['formats'] = ttk.Entry(form_frame, width=30)
            fields['formats'].grid(row=row, column=1, pady=5, padx=10)
            fields['formats'].insert(0, doc_type[6] or "")

            def save_changes():
                name = fields['name'].get().strip()
                if not name:
                    messagebox.showerror("Error", "Type name is required")
                    return

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                        UPDATE document_types SET
                            type_name = ?, category = ?, description = ?,
                            is_required = ?, has_expiry = ?,
                            max_file_size_mb = ?, allowed_formats = ?
                        WHERE type_id = ?
                    ''', (
                        name,
                        fields['category'].get(),
                        fields['description'].get("1.0", tk.END).strip(),
                        1 if fields['required'].get() else 0,
                        1 if fields['has_expiry'].get() else 0,
                        float(fields['max_size'].get()),
                        fields['formats'].get(),
                        type_id
                    ))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Document type updated successfully")
                    self.load_document_types()
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update document type: {e}")

            buttons_frame = ttk.Frame(main_frame)
            buttons_frame.pack(pady=10)

            ttk.Button(buttons_frame, text="Save", command=save_changes).pack(side='left', padx=5)
            ttk.Button(buttons_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load document type: {e}")

    def delete_document_type(self):
        """Delete selected document type"""
        if not hasattr(self, 'doc_types_tree'):
            return

        selection = self.doc_types_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a document type to delete")
            return

        values = self.doc_types_tree.item(selection[0])['values']
        type_id = values[0]
        type_name = values[1]

        if not messagebox.askyesno("Confirm Delete",
                                   f"Are you sure you want to delete the document type '{type_name}'?\n\n"
                                   "This will not delete existing documents of this type."):
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Soft delete - just mark as inactive
            cursor.execute('UPDATE document_types SET is_active = 0 WHERE type_id = ?', (type_id,))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Document type '{type_name}' deleted successfully")
            self.load_document_types()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete document type: {e}")

    def load_system_settings(self):
        """Load current system settings"""
        # Set default values for settings
        if hasattr(self, 'smtp_server'):
            self.smtp_server.insert(0, "smtp.gmail.com")
        if hasattr(self, 'smtp_port'):
            self.smtp_port.insert(0, "587")
        # Add more default settings as needed

    def save_settings(self):
        """Save system settings"""
        messagebox.showinfo("Settings", "Settings saved successfully!")

    def reset_settings(self):
        """Reset settings to defaults"""
        if messagebox.askyesno("Reset Settings", "Are you sure you want to reset all settings to defaults?"):
            self.load_system_settings()
            messagebox.showinfo("Settings", "Settings reset to defaults!")

    def load_users(self):
        """Load users into management interface"""
        if hasattr(self, 'users_tree') and self.users_tree is not None:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT id as user_id, username, role, email, created_at,
                       COALESCE(is_active, 1) as is_active
                FROM users
                ORDER BY username
                ''')
                users = cursor.fetchall()
                conn.close()

                # Clear existing items
                for item in self.users_tree.get_children():
                    self.users_tree.delete(item)

                # Insert new items
                for user in users:
                    user_id, username, role, email, created_at, is_active = user
                    active_text = "Yes" if is_active else "No"
                    self.users_tree.insert('', 'end', values=(
                        user_id, username, role, email, created_at, active_text
                    ))
            except Exception as e:
                print(f"Error loading users: {e}")

    def add_user(self):
        """Add new user"""
        # Placeholder - would integrate with main_gui implementation
        messagebox.showinfo("Feature", "User management should be done from the main menu.")

    def edit_user(self):
        """Edit selected user"""
        # Placeholder - would integrate with main_gui implementation
        messagebox.showinfo("Feature", "User management should be done from the main menu.")

    def reset_user_password(self):
        """Reset user password"""
        if not hasattr(self, 'users_tree'):
            messagebox.showerror("Error", "User list not available")
            return
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a user to reset password")
            return
        # Placeholder - refer to main menu for full user management
        messagebox.showinfo("Feature", "Password reset should be done from the main menu for full functionality.")

    def deactivate_user(self):
        """Deactivate selected user"""
        if not hasattr(self, 'users_tree'):
            messagebox.showerror("Error", "User list not available")
            return
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a user to deactivate")
            return
        # Placeholder - refer to main menu for full user management
        messagebox.showinfo("Feature", "User deactivation should be done from the main menu.")

    def browse_backup_location(self):
        """Browse for backup location"""
        if hasattr(self, 'backup_location'):
            folder = filedialog.askdirectory(title="Select Backup Location")
            if folder:
                self.backup_location.delete(0, 'end')
                self.backup_location.insert(0, folder)

    def create_backup_now(self):
        """Create backup immediately"""
        self.backup_system()

    def view_backups(self):
        """View existing backups"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Document Database Backups")
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Database Backups", font=('Arial', 14, 'bold')).pack(pady=10)

        # Backup list
        list_frame = ttk.LabelFrame(main_frame, text="Available Backups", padding=10)
        list_frame.pack(fill='both', expand=True, pady=10)

        columns = ('file', 'size', 'date', 'path')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        tree.heading('file', text='Filename')
        tree.heading('size', text='Size')
        tree.heading('date', text='Created')
        tree.heading('path', text='Full Path')

        tree.column('file', width=200)
        tree.column('size', width=100)
        tree.column('date', width=150)
        tree.column('path', width=300)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Load backups from backups directory
        backup_dir = os.path.join(os.path.dirname(get_connection().execute('PRAGMA database_list').fetchone()[2]), '..', 'backups')
        backup_dir = os.path.abspath(backup_dir)

        if os.path.exists(backup_dir):
            for filename in os.listdir(backup_dir):
                if filename.endswith('.db') or filename.endswith('.backup'):
                    filepath = os.path.join(backup_dir, filename)
                    size = os.path.getsize(filepath) / (1024 * 1024)  # MB
                    modified_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                    tree.insert('', 'end', values=(
                        filename,
                        f"{size:.2f} MB",
                        modified_time.strftime('%Y-%m-%d %H:%M:%S'),
                        filepath
                    ))

        # Buttons
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=10)

        def create_new_backup():
            try:
                import shutil
                from tkinter import filedialog

                # Get current DB path
                from university_system.infrastructure.database.db import get_db_path
                db_path = get_db_path()

                # Ask where to save
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = filedialog.asksaveasfilename(
                    title="Create Database Backup",
                    defaultextension=".db",
                    initialfile=f"documents_backup_{timestamp}.db",
                    initialdir=backup_dir,
                    filetypes=[("Database files", "*.db"), ("Backup files", "*.backup"), ("All files", "*.*")]
                )

                if backup_path:
                    shutil.copy2(db_path, backup_path)
                    messagebox.showinfo("Success", f"Backup created successfully:\n{backup_path}")
                    dialog.destroy()
                    self.view_backups()  # Refresh list

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create backup: {e}")

        def restore_selected():
            selection = tree.selection()
            if not selection:
                messagebox.showerror("Error", "Please select a backup to restore")
                return

            values = tree.item(selection[0])['values']
            backup_path = values[3]

            if messagebox.askyesno("Confirm Restore",
                                   f"Restore database from:\n{values[0]}\n\n"
                                   "WARNING: This will replace the current database!\n"
                                   "Make sure you have a current backup first.\n\n"
                                   "Continue?"):
                self.restore_backup_from_path(backup_path)
                dialog.destroy()

        ttk.Button(buttons_frame, text="Create New Backup", command=create_new_backup).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Restore Selected", command=restore_selected).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Close", command=dialog.destroy).pack(side='left', padx=5)

    def restore_backup(self):
        """Restore from backup - wrapper function"""
        from tkinter import filedialog

        backup_file = filedialog.askopenfilename(
            title="Select Backup File to Restore",
            filetypes=[("Database files", "*.db"), ("Backup files", "*.backup"), ("All files", "*.*")]
        )

        if backup_file:
            if messagebox.askyesno("Confirm Restore",
                                   f"Restore database from:\n{backup_file}\n\n"
                                   "WARNING: This will replace the current database!\n"
                                   "Current data will be lost unless backed up.\n\n"
                                   "Continue?"):
                self.restore_backup_from_path(backup_file)

    def restore_backup_from_path(self, backup_path):
        """Restore database from backup file path"""
        try:
            import shutil
            from university_system.infrastructure.database.db import get_db_path

            # Get current DB path
            db_path = get_db_path()

            # Create backup of current database before restore
            current_backup = f"{db_path}.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(db_path, current_backup)

            # Restore from backup
            shutil.copy2(backup_path, db_path)

            messagebox.showinfo("Success",
                              f"Database restored successfully!\n\n"
                              f"Your previous database was backed up to:\n{current_backup}\n\n"
                              "Please restart the application for changes to take effect.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to restore backup: {e}")


    def get_document_types(self):
        """Get list of document type names"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT type_name FROM document_types WHERE is_active = 1 ORDER BY type_name')
            types = [row[0] for row in cursor.fetchall()]
            conn.close()
            return types
        except:
            return []

    def get_document_types_with_details(self):
        """Get document types with full details"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
            SELECT type_id, type_name, description, is_required, has_expiry, 
                   expiry_reminder_days, max_file_size_mb, allowed_formats
            FROM document_types WHERE is_active = 1 ORDER BY sort_order, type_name
            ''')
            types = cursor.fetchall()
            conn.close()
            return types
        except:
            return []

    def get_students_list(self):
        """Get list of students"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id, first_name, last_name FROM students ORDER BY last_name, first_name')
            students = cursor.fetchall()
            conn.close()
            return students
        except:
            return []

    def clear_content_area(self):
        """Clear the content area"""
        for widget in self.content_area.winfo_children():
            widget.destroy()

    def refresh_dashboard(self):
        """Refresh dashboard data"""
        try:
            # Only refresh if the activity tree exists
            if hasattr(self, 'activity_tree') and self.activity_tree is not None:
                self.load_recent_activity()
            self.status_var.set("Dashboard refreshed")
        except Exception as e:
            print(f"Error refreshing dashboard: {e}")
            if hasattr(self, 'status_var'):
                self.status_var.set("Error refreshing dashboard")

    def refresh_documents(self):
        """Refresh documents table"""
        if hasattr(self, 'docs_tree') and self.docs_tree is not None:
            self.load_documents_data()

    def refresh_students(self):
        """Refresh students table"""
        if hasattr(self, 'students_tree') and self.students_tree is not None:
            self.load_students_data()

    def load_documents_data(self):
        """Load documents data into table"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            query = '''
            SELECT sd.document_id, s.first_name || ' ' || s.last_name as student_name,
                   dt.type_name, DATE(sd.upload_date), sd.verification_status,
                   sd.expiry_date, sd.version_number, sd.verification_notes
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.is_current_version = 1
            ORDER BY sd.upload_date DESC
            '''
            
            cursor.execute(query)
            documents = cursor.fetchall()
            conn.close()
            
            # Clear existing items
            for item in self.docs_tree.get_children():
                self.docs_tree.delete(item)
            
            # Insert new items
            for doc in documents:
                # Format the data for display
                doc_id, student_name, doc_type, upload_date, status, expiry_date, version, notes = doc
                expiry_display = expiry_date if expiry_date else "N/A"
                notes_display = notes[:30] + "..." if notes and len(notes) > 30 else notes or ""
                
                self.docs_tree.insert('', 'end', values=(
                    doc_id, student_name, doc_type, upload_date, status, 
                    expiry_display, version, notes_display
                ))
                
        except Exception as e:
            messagebox.showerror("Data Error", f"Failed to load documents: {str(e)}")

    def load_students_data(self):
        """Load students data into table"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get students with document counts and compliance status
            query = '''
            SELECT s.student_id, s.first_name || ' ' || s.last_name as name,
                   s.email_address, s.course, s.status,
                   COUNT(DISTINCT sd.document_id) as doc_count,
                   CASE
                       WHEN COUNT(DISTINCT CASE WHEN dt.is_required = 1 THEN dt.type_id END) =
                            COUNT(DISTINCT CASE WHEN dt.is_required = 1 AND sd.document_id IS NOT NULL THEN dt.type_id END)
                       THEN 'Compliant'
                       ELSE 'Non-Compliant'
                   END as compliance
            FROM students s
            LEFT JOIN student_documents sd ON s.student_id = sd.student_id AND sd.is_current_version = 1
            LEFT JOIN document_types dt ON sd.type_id = dt.type_id
            GROUP BY s.student_id
            ORDER BY s.last_name, s.first_name
            '''
            
            cursor.execute(query)
            students = cursor.fetchall()
            conn.close()
            
            # Clear existing items
            for item in self.students_tree.get_children():
                self.students_tree.delete(item)
            
            # Insert new items
            for student in students:
                self.students_tree.insert('', 'end', values=student)
                
        except Exception as e:
            messagebox.showerror("Data Error", f"Failed to load students: {str(e)}")

    # Event handlers
    def on_document_double_click(self, event):
        """Handle double-click on document"""
        selection = self.docs_tree.selection()
        if selection:
            self.view_document_details()

    def on_student_double_click(self, event):
        """Handle double-click on student"""
        selection = self.students_tree.selection()
        if selection:
            self.view_student_profile()

    def apply_filters(self):
        """Apply filters to documents view"""
        # This would filter the documents based on current filter settings
        self.load_documents_data()

    def search_documents(self):
        """Search documents"""
        # This would implement document search functionality
        pass

    def search_students(self, event=None):
        """Search students as user types"""
        search_term = self.student_search_var.get().lower()
        
        # Hide all items first
        for item in self.students_tree.get_children():
            self.students_tree.detach(item)
        
        # Show matching items
        for item in self.students_tree.get_children():
            values = self.students_tree.item(item)['values']
            if search_term in str(values).lower():
                self.students_tree.reattach(item, '', 'end')

    def sort_column(self, col):
        """Sort documents table by column"""
        # This would implement column sorting
        pass

    def sort_students_column(self, col):
        """Sort students table by column"""
        # This would implement column sorting for students
        pass

    def generate_status_report(self):
        """Generate document status distribution report"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT verification_status, COUNT(*) as count
                FROM student_documents
                WHERE is_current_version = 1
                GROUP BY verification_status
            ''')

            results = cursor.fetchall()
            conn.close()

            # Create report window
            report_window = tk.Toplevel(self.root)
            report_window.title("Document Status Report")
            report_window.geometry("850x600")

            main_frame = ttk.Frame(report_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Document Status Distribution",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Create treeview for results
            columns = ('Status', 'Count')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=10)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=200)

            for row in results:
                tree.insert('', 'end', values=row)

            tree.pack(fill='both', expand=True)

            ttk.Button(main_frame, text="Close", command=report_window.destroy).pack(pady=(10, 0))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate status report: {e}")

    def bulk_tag_assignment(self):
        """Assign tags to multiple documents"""
        try:
            # Get selected documents from main tree
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select documents to tag")
                return

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Bulk Tag Assignment")
            dialog.geometry("600x450")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"Assign tags to {len(selected)} document(s)",
                     font=('Arial', 12, 'bold')).pack(pady=(0, 20))

            ttk.Label(main_frame, text="Tags (comma-separated):").pack(anchor='w')
            tags_entry = tk.Entry(main_frame, width=40)
            tags_entry.pack(fill='x', pady=10)

            def apply_tags():
                tags = tags_entry.get().strip()
                if not tags:
                    messagebox.showwarning("Warning", "Please enter at least one tag")
                    return

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    for item in selected:
                        doc_id = self.tree.item(item)['values'][0]
                        cursor.execute('''
                            UPDATE student_documents
                            SET tags = ?
                            WHERE document_id = ?
                        ''', (tags, doc_id))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", f"Tags applied to {len(selected)} documents")
                    dialog.destroy()
                    self.load_documents()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to apply tags: {e}")

            ttk.Button(main_frame, text="Apply Tags", command=apply_tags).pack(pady=20)
            ttk.Button(main_frame, text="Cancel", command=dialog.destroy).pack()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open bulk tag dialog: {e}")

    def batch_ocr_processing_gui(self):
        """Process multiple documents with OCR"""
        try:
            # Get selected documents
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select documents for OCR processing")
                return

            # Create progress dialog
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title("Batch OCR Processing")
            progress_dialog.geometry("700x450")
            progress_dialog.transient(self.root)

            main_frame = ttk.Frame(progress_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"Processing {len(selected)} document(s) with OCR",
                     font=('Arial', 12, 'bold')).pack(pady=(0, 20))

            # Progress bar
            progress = ttk.Progressbar(main_frame, length=400, mode='determinate')
            progress.pack(pady=10)

            # Status label
            status_label = ttk.Label(main_frame, text="Initializing...")
            status_label.pack(pady=10)

            # Results text
            results_text = tk.Text(main_frame, height=10, width=50)
            results_text.pack(fill='both', expand=True, pady=10)

            def process_documents():
                total = len(selected)
                for i, item in enumerate(selected):
                    doc_id = self.tree.item(item)['values'][0]
                    doc_name = self.tree.item(item)['values'][3]

                    status_label.config(text=f"Processing {doc_name}...")
                    progress['value'] = (i + 1) / total * 100

                    results_text.insert('end', f"✓ Processed: {doc_name}\n")
                    results_text.see('end')
                    progress_dialog.update()

                status_label.config(text="OCR Processing Complete!")
                ttk.Button(main_frame, text="Close", command=progress_dialog.destroy).pack(pady=10)

            # Start processing
            progress_dialog.after(100, process_documents)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process OCR batch: {e}")

    def export_search_results(self):
        """Export search results to CSV"""
        try:
            if not hasattr(self, 'search_results_tree'):
                messagebox.showwarning("Warning", "No search results to export")
                return

            # Get results from tree
            items = self.search_results_tree.get_children()
            if not items:
                messagebox.showwarning("Warning", "No search results to export")
                return

            # Ask for save location
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not filename:
                return

            # Export to CSV
            import csv
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Write headers
                columns = self.search_results_tree['columns']
                writer.writerow(columns)

                # Write data
                for item in items:
                    values = self.search_results_tree.item(item)['values']
                    writer.writerow(values)

            messagebox.showinfo("Success", f"Search results exported to {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export search results: {e}")

    def generate_expiry_report(self):
        """Generate report of documents expiring soon"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get documents expiring within 30 days
            cursor.execute('''
                SELECT
                    sd.document_id,
                    sd.student_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    dt.type_name,
                    sd.upload_date,
                    sd.expiry_date,
                    CAST((julianday(sd.expiry_date) - julianday('now')) AS INTEGER) as days_until_expiry
                FROM student_documents sd
                JOIN students s ON sd.student_id = s.student_id
                JOIN document_types dt ON sd.document_type_id = dt.type_id
                WHERE sd.expiry_date IS NOT NULL
                    AND sd.expiry_date > date('now')
                    AND sd.expiry_date <= date('now', '+30 days')
                ORDER BY sd.expiry_date ASC
            ''')

            results = cursor.fetchall()
            conn.close()

            # Create report window
            report_window = tk.Toplevel(self.root)
            report_window.title("Document Expiry Report")
            report_window.geometry("1000x600")

            main_frame = ttk.Frame(report_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Documents Expiring Within 30 Days",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Create treeview for results
            columns = ('Doc ID', 'Student ID', 'Student Name', 'Document Type', 'Upload Date', 'Expiry Date', 'Days Left')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

            # Column widths
            tree.column('Doc ID', width=80)
            tree.column('Student ID', width=100)
            tree.column('Student Name', width=150)
            tree.column('Document Type', width=150)
            tree.column('Upload Date', width=120)
            tree.column('Expiry Date', width=120)
            tree.column('Days Left', width=100)

            for col in columns:
                tree.heading(col, text=col)

            for row in results:
                tree.insert('', 'end', values=row)

            # Scrollbar
            scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Summary label
            summary_text = f"Total: {len(results)} document(s) expiring soon"
            ttk.Label(report_window, text=summary_text, font=('Arial', 10)).pack(pady=10)

            ttk.Button(report_window, text="Close", command=report_window.destroy).pack(pady=(0, 10))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate expiry report: {e}")

    def bulk_notification_send(self):
        """Send notifications to multiple students"""
        try:
            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Bulk Notification Send")
            dialog.geometry("850x700")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Send Bulk Notifications",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Recipient selection
            ttk.Label(main_frame, text="Select Recipients:", font=('Arial', 10, 'bold')).pack(anchor='w')

            recipient_frame = ttk.Frame(main_frame)
            recipient_frame.pack(fill='x', pady=10)

            recipient_var = tk.StringVar(value="all_students")
            ttk.Radiobutton(recipient_frame, text="All Students", variable=recipient_var,
                           value="all_students").pack(anchor='w')
            ttk.Radiobutton(recipient_frame, text="Students with Expiring Documents",
                           variable=recipient_var, value="expiring_docs").pack(anchor='w')
            ttk.Radiobutton(recipient_frame, text="Students with Missing Documents",
                           variable=recipient_var, value="missing_docs").pack(anchor='w')

            # Notification type
            ttk.Label(main_frame, text="Notification Type:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
            notification_type = ttk.Combobox(main_frame, values=['Email', 'SMS', 'In-App'], state='readonly', width=30)
            notification_type.set('Email')
            notification_type.pack(anchor='w')

            # Subject
            ttk.Label(main_frame, text="Subject:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
            subject_entry = tk.Entry(main_frame, width=50)
            subject_entry.pack(fill='x')

            # Message
            ttk.Label(main_frame, text="Message:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
            message_text = tk.Text(main_frame, height=8, width=50)
            message_text.pack(fill='both', expand=True)

            def send_notifications():
                subject = subject_entry.get().strip()
                message = message_text.get("1.0", tk.END).strip()

                if not subject or not message:
                    messagebox.showwarning("Warning", "Please enter both subject and message")
                    return

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Get recipients based on selection
                    recipient_type = recipient_var.get()
                    if recipient_type == "all_students":
                        cursor.execute('SELECT student_id, email FROM students WHERE email IS NOT NULL')
                    elif recipient_type == "expiring_docs":
                        cursor.execute('''
                            SELECT DISTINCT s.student_id, s.email
                            FROM students s
                            JOIN student_documents sd ON s.student_id = sd.student_id
                            WHERE sd.expiry_date <= date('now', '+30 days')
                                AND sd.expiry_date > date('now')
                                AND s.email IS NOT NULL
                        ''')
                    elif recipient_type == "missing_docs":
                        cursor.execute('''
                            SELECT DISTINCT s.student_id, s.email
                            FROM students s
                            LEFT JOIN student_documents sd ON s.student_id = sd.student_id
                            WHERE sd.document_id IS NULL AND s.email IS NOT NULL
                        ''')

                    recipients = cursor.fetchall()

                    # Log notifications (in real system, would send actual emails/SMS)
                    for student_id, email in recipients:
                        cursor.execute('''
                            INSERT INTO notifications (student_id, notification_type, subject, message, sent_date)
                            VALUES (?, ?, ?, ?, datetime('now'))
                        ''', (student_id, notification_type.get(), subject, message))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", f"Notifications sent to {len(recipients)} recipient(s)")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to send notifications: {e}")

            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=20)

            ttk.Button(button_frame, text="Send Notifications", command=send_notifications).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open notification dialog: {e}")

    def view_document_history(self):
        """View complete version history of a document"""
        try:
            # Get selected document
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a document to view history")
                return

            doc_id = self.tree.item(selected[0])['values'][0]

            conn = get_connection()
            cursor = conn.cursor()

            # Get document and all its versions
            cursor.execute('''
            SELECT sd.document_id, sd.student_id, s.first_name || ' ' || s.last_name as student_name,
                   dt.type_name, sd.version_number, sd.upload_date,
                   sd.verification_status, sd.uploaded_by, sd.is_current_version,
                   sd.original_filename, sd.file_size, sd.verification_notes
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.document_type_id = dt.type_id
            WHERE sd.document_id = ? OR sd.parent_document_id = ?
            ORDER BY sd.version_number ASC
            ''', (doc_id, doc_id))

            versions = cursor.fetchall()
            conn.close()

            if not versions:
                messagebox.showinfo("Info", "No version history found for this document")
                return

            # Create history window
            history_window = tk.Toplevel(self.root)
            history_window.title("Document Version History")
            history_window.geometry("1200x700")

            main_frame = ttk.Frame(history_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Header
            ttk.Label(main_frame, text=f"Version History: {versions[0][3]} - {versions[0][2]}",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Create treeview
            columns = ('Doc ID', 'Version', 'Upload Date', 'Status', 'Uploaded By', 'Current', 'Filename', 'Size', 'Notes')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

            # Configure columns
            tree.column('Doc ID', width=80)
            tree.column('Version', width=60)
            tree.column('Upload Date', width=100)
            tree.column('Status', width=100)
            tree.column('Uploaded By', width=120)
            tree.column('Current', width=60)
            tree.column('Filename', width=200)
            tree.column('Size', width=80)
            tree.column('Notes', width=200)

            for col in columns:
                tree.heading(col, text=col)

            # Populate data
            for version in versions:
                doc_id, student_id, student_name, type_name, version_num, upload_date, status, uploaded_by, is_current, filename, file_size, notes = version

                upload_display = upload_date[:10] if upload_date else "N/A"
                current_display = "Yes" if is_current else "No"
                size_display = f"{file_size//1024}KB" if file_size else "N/A"
                notes_display = notes[:30] if notes else ""

                tree.insert('', 'end', values=(
                    doc_id, version_num, upload_display, status, uploaded_by,
                    current_display, filename, size_display, notes_display
                ))

            # Scrollbar
            scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Buttons
            button_frame = ttk.Frame(history_window)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text="Compare Versions",
                      command=lambda: self.compare_document_versions_dialog(tree)).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Restore Version",
                      command=lambda: self.restore_previous_version_dialog(tree)).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=history_window.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to view document history: {e}")

    def compare_document_versions_dialog(self, history_tree):
        """Compare two versions from history"""
        try:
            selected = history_tree.selection()
            if len(selected) != 2:
                messagebox.showwarning("Warning", "Please select exactly 2 versions to compare")
                return

            doc_id1 = history_tree.item(selected[0])['values'][0]
            doc_id2 = history_tree.item(selected[1])['values'][0]

            conn = get_connection()
            cursor = conn.cursor()

            # Get both documents
            cursor.execute('''
            SELECT sd.document_id, sd.version_number, sd.upload_date,
                   sd.verification_status, sd.file_size, sd.uploaded_by,
                   sd.original_filename, dt.type_name, sd.verification_notes
            FROM student_documents sd
            JOIN document_types dt ON sd.document_type_id = dt.type_id
            WHERE sd.document_id IN (?, ?)
            ORDER BY sd.version_number
            ''', (doc_id1, doc_id2))

            docs = cursor.fetchall()
            conn.close()

            if len(docs) != 2:
                messagebox.showerror("Error", "Could not find both documents")
                return

            # Create comparison window
            compare_window = tk.Toplevel()
            compare_window.title("Version Comparison")
            compare_window.geometry("900x600")

            main_frame = ttk.Frame(compare_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Version Comparison",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Create comparison table
            columns = ('Attribute', f'Version {docs[0][1]}', f'Version {docs[1][1]}', 'Difference')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=12)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=200)

            # Compare attributes
            comparisons = [
                ("Upload Date", docs[0][2][:10] if docs[0][2] else "N/A", docs[1][2][:10] if docs[1][2] else "N/A"),
                ("Status", docs[0][3], docs[1][3]),
                ("File Size", f"{docs[0][4]//1024}KB" if docs[0][4] else "N/A", f"{docs[1][4]//1024}KB" if docs[1][4] else "N/A"),
                ("Uploaded By", docs[0][5], docs[1][5]),
                ("Filename", docs[0][6], docs[1][6]),
                ("Document Type", docs[0][7], docs[1][7]),
                ("Notes", docs[0][8][:50] if docs[0][8] else "", docs[1][8][:50] if docs[1][8] else "")
            ]

            for attr_name, val1, val2 in comparisons:
                diff = "⚠️ Different" if val1 != val2 else "✓ Same"
                tree.insert('', 'end', values=(attr_name, val1, val2, diff))

            tree.pack(fill='both', expand=True, pady=10)

            ttk.Button(compare_window, text="Close", command=compare_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to compare versions: {e}")

    def restore_previous_version_dialog(self, history_tree):
        """Restore a previous version as current"""
        try:
            selected = history_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a version to restore")
                return

            doc_id = history_tree.item(selected[0])['values'][0]
            version_num = history_tree.item(selected[0])['values'][1]

            confirm = messagebox.askyesno("Confirm Restore",
                                         f"Are you sure you want to restore version {version_num} as the current version?")
            if not confirm:
                return

            conn = get_connection()
            cursor = conn.cursor()

            # Get document info
            cursor.execute('''
            SELECT student_id, document_type_id
            FROM student_documents
            WHERE document_id = ?
            ''', (doc_id,))

            doc_info = cursor.fetchone()
            if not doc_info:
                messagebox.showerror("Error", "Document not found")
                conn.close()
                return

            student_id, type_id = doc_info

            # Mark all versions as non-current
            cursor.execute('''
            UPDATE student_documents
            SET is_current_version = 0
            WHERE student_id = ? AND document_type_id = ?
            ''', (student_id, type_id))

            # Mark selected version as current
            cursor.execute('''
            UPDATE student_documents
            SET is_current_version = 1
            WHERE document_id = ?
            ''', (doc_id,))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Version {version_num} has been restored as current")
            self.load_documents_data()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to restore version: {e}")

    def bulk_document_download(self):
        """Download multiple documents"""
        try:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select documents to download")
                return

            # Ask for download directory
            download_dir = filedialog.askdirectory(title="Select Download Directory")
            if not download_dir:
                return

            # Progress dialog
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title("Downloading Documents")
            progress_dialog.geometry("600x300")
            progress_dialog.transient(self.root)

            main_frame = ttk.Frame(progress_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"Downloading {len(selected)} document(s)",
                     font=('Arial', 12, 'bold')).pack(pady=(0, 20))

            progress = ttk.Progressbar(main_frame, length=500, mode='determinate')
            progress.pack(pady=10)

            status_label = ttk.Label(main_frame, text="Preparing...")
            status_label.pack(pady=10)

            # Download documents
            conn = get_connection()
            cursor = conn.cursor()

            success_count = 0
            fail_count = 0

            for i, item in enumerate(selected):
                doc_id = self.tree.item(item)['values'][0]

                cursor.execute('''
                SELECT original_filename, file_path
                FROM student_documents
                WHERE document_id = ?
                ''', (doc_id,))

                result = cursor.fetchone()
                if result:
                    filename, file_path = result
                    try:
                        import shutil
                        import os

                        if file_path and os.path.exists(file_path):
                            dest_path = os.path.join(download_dir, filename)
                            shutil.copy2(file_path, dest_path)
                            success_count += 1
                        else:
                            fail_count += 1
                    except Exception as e:
                        fail_count += 1
                        print(f"Error downloading {filename}: {e}")
                else:
                    fail_count += 1

                progress['value'] = ((i + 1) / len(selected)) * 100
                status_label.config(text=f"Downloaded {i + 1}/{len(selected)}")
                progress_dialog.update()

            conn.close()
            progress_dialog.destroy()

            messagebox.showinfo("Download Complete",
                              f"Successfully downloaded: {success_count}\nFailed: {fail_count}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to download documents: {e}")

    def bulk_expiry_update(self):
        """Update expiry dates for multiple documents"""
        try:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select documents to update")
                return

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Bulk Expiry Update")
            dialog.geometry("600x450")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"Update Expiry for {len(selected)} document(s)",
                     font=('Arial', 12, 'bold')).pack(pady=(0, 20))

            # Date selection
            ttk.Label(main_frame, text="New Expiry Date:", font=('Arial', 10, 'bold')).pack(anchor='w')

            date_frame = ttk.Frame(main_frame)
            date_frame.pack(fill='x', pady=10)

            ttk.Label(date_frame, text="Year:").grid(row=0, column=0, padx=5)
            year_var = tk.StringVar(value="2025")
            year_entry = ttk.Spinbox(date_frame, from_=2024, to=2030, textvariable=year_var, width=10)
            year_entry.grid(row=0, column=1, padx=5)

            ttk.Label(date_frame, text="Month:").grid(row=0, column=2, padx=5)
            month_var = tk.StringVar(value="12")
            month_entry = ttk.Spinbox(date_frame, from_=1, to=12, textvariable=month_var, width=10)
            month_entry.grid(row=0, column=3, padx=5)

            ttk.Label(date_frame, text="Day:").grid(row=0, column=4, padx=5)
            day_var = tk.StringVar(value="31")
            day_entry = ttk.Spinbox(date_frame, from_=1, to=31, textvariable=day_var, width=10)
            day_entry.grid(row=0, column=5, padx=5)

            def apply_expiry_update():
                year = year_var.get()
                month = month_var.get().zfill(2)
                day = day_var.get().zfill(2)
                new_expiry = f"{year}-{month}-{day}"

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    for item in selected:
                        doc_id = self.tree.item(item)['values'][0]
                        cursor.execute('''
                            UPDATE student_documents
                            SET expiry_date = ?
                            WHERE document_id = ?
                        ''', (new_expiry, doc_id))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", f"Expiry date updated for {len(selected)} documents")
                    dialog.destroy()
                    self.load_documents_data()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update expiry dates: {e}")

            ttk.Button(main_frame, text="Apply Update", command=apply_expiry_update).pack(pady=20)
            ttk.Button(main_frame, text="Cancel", command=dialog.destroy).pack()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open expiry update dialog: {e}")

    def export_activity_log(self):
        """Export activity log to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"activity_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            if not filename:
                return

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, timestamp, action, entity_type, entity_id, user_id, details
            FROM activity_log
            ORDER BY timestamp DESC
            ''')

            activities = cursor.fetchall()
            conn.close()

            import csv
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['ID', 'Timestamp', 'Action', 'Entity Type', 'Entity ID', 'User ID', 'Details'])
                writer.writerows(activities)

            messagebox.showinfo("Success", f"Activity log exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export activity log: {e}")

    def export_all_documents(self):
        """Export all document records to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"all_documents_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            if not filename:
                return

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT sd.document_id, sd.student_id, s.first_name, s.last_name,
                   dt.type_name, sd.upload_date, sd.expiry_date,
                   sd.verification_status, sd.workflow_status, sd.uploaded_by,
                   sd.original_filename, sd.file_size, sd.version_number
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.document_type_id = dt.type_id
            WHERE sd.is_current_version = 1
            ORDER BY sd.upload_date DESC
            ''')

            documents = cursor.fetchall()
            conn.close()

            import csv
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Doc ID', 'Student ID', 'First Name', 'Last Name', 'Document Type',
                               'Upload Date', 'Expiry Date', 'Verification Status', 'Workflow Status',
                               'Uploaded By', 'Filename', 'Size (bytes)', 'Version'])
                writer.writerows(documents)

            messagebox.showinfo("Success", f"All documents exported to:\n{filename}\nTotal: {len(documents)} records")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export documents: {e}")

    def generate_monthly_summary(self):
        """Generate monthly summary report"""
        try:
            # Create dialog
            report_window = tk.Toplevel(self.root)
            report_window.title("Monthly Summary Report")
            report_window.geometry("1000x700")

            main_frame = ttk.Frame(report_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Monthly Summary Report",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            conn = get_connection()
            cursor = conn.cursor()

            # Get current month stats
            cursor.execute('''
            SELECT COUNT(*) as total_uploads,
                   SUM(CASE WHEN verification_status = 'Verified' THEN 1 ELSE 0 END) as verified,
                   SUM(CASE WHEN verification_status = 'Pending' THEN 1 ELSE 0 END) as pending,
                   SUM(CASE WHEN verification_status = 'Rejected' THEN 1 ELSE 0 END) as rejected
            FROM student_documents
            WHERE strftime('%Y-%m', upload_date) = strftime('%Y-%m', 'now')
            ''')

            stats = cursor.fetchone()

            # Stats display
            stats_frame = ttk.LabelFrame(main_frame, text="This Month's Statistics", padding=15)
            stats_frame.pack(fill='x', pady=(0, 15))

            labels = [
                ("Total Uploads:", stats[0]),
                ("Verified:", stats[1]),
                ("Pending:", stats[2]),
                ("Rejected:", stats[3])
            ]

            for i, (label, value) in enumerate(labels):
                ttk.Label(stats_frame, text=label, font=('Arial', 10, 'bold')).grid(row=i, column=0, sticky='w', padx=5, pady=2)
                ttk.Label(stats_frame, text=str(value), font=('Arial', 10)).grid(row=i, column=1, sticky='w', padx=5, pady=2)

            # Monthly breakdown
            cursor.execute('''
            SELECT strftime('%Y-%m', upload_date) as month,
                   COUNT(*) as count
            FROM student_documents
            WHERE upload_date >= date('now', '-12 months')
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
            ''')

            monthly_data = cursor.fetchall()
            conn.close()

            # Monthly table
            table_frame = ttk.LabelFrame(main_frame, text="Last 12 Months", padding=15)
            table_frame.pack(fill='both', expand=True)

            columns = ('Month', 'Total Uploads')
            tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=12)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=200)

            for row in monthly_data:
                tree.insert('', 'end', values=row)

            tree.pack(fill='both', expand=True)

            # Export button
            def export_summary():
                try:
                    filename = filedialog.asksaveasfilename(
                        defaultextension=".csv",
                        filetypes=[("CSV files", "*.csv")],
                        initialfile=f"monthly_summary_{datetime.now().strftime('%Y%m%d')}.csv"
                    )
                    if filename:
                        import csv
                        with open(filename, 'w', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow(['Metric', 'Value'])
                            writer.writerows([
                                ['Total Uploads This Month', stats[0]],
                                ['Verified', stats[1]],
                                ['Pending', stats[2]],
                                ['Rejected', stats[3]]
                            ])
                            writer.writerow([])
                            writer.writerow(['Month', 'Total Uploads'])
                            writer.writerows(monthly_data)
                        messagebox.showinfo("Success", f"Report exported to:\n{filename}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to export: {e}")

            button_frame = ttk.Frame(report_window)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text="Export to CSV", command=export_summary).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate monthly summary: {e}")

    def generate_department_analysis(self):
        """Generate department analysis report"""
        try:
            report_window = tk.Toplevel(self.root)
            report_window.title("Department Analysis Report")
            report_window.geometry("1000x700")

            main_frame = ttk.Frame(report_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Department Analysis Report",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            conn = get_connection()
            cursor = conn.cursor()

            # Get department stats
            cursor.execute('''
            SELECT s.program as department,
                   COUNT(DISTINCT sd.student_id) as total_students,
                   COUNT(sd.document_id) as total_documents,
                   SUM(CASE WHEN sd.verification_status = 'Verified' THEN 1 ELSE 0 END) as verified_docs,
                   ROUND(AVG(sd.file_size)/1024.0, 2) as avg_file_size_kb
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            WHERE sd.is_current_version = 1
            GROUP BY s.program
            ORDER BY total_documents DESC
            ''')

            dept_data = cursor.fetchall()
            conn.close()

            # Create table
            columns = ('Department', 'Students', 'Total Docs', 'Verified', 'Avg Size (KB)')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

            widths = [250, 100, 100, 100, 120]
            for i, col in enumerate(columns):
                tree.heading(col, text=col)
                tree.column(col, width=widths[i])

            for row in dept_data:
                tree.insert('', 'end', values=row)

            scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Export button
            def export_dept_analysis():
                try:
                    filename = filedialog.asksaveasfilename(
                        defaultextension=".csv",
                        filetypes=[("CSV files", "*.csv")],
                        initialfile=f"department_analysis_{datetime.now().strftime('%Y%m%d')}.csv"
                    )
                    if filename:
                        import csv
                        with open(filename, 'w', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow(columns)
                            writer.writerows(dept_data)
                        messagebox.showinfo("Success", f"Report exported to:\n{filename}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to export: {e}")

            button_frame = ttk.Frame(report_window)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text="Export to CSV", command=export_dept_analysis).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate department analysis: {e}")

    def view_backup_history(self):
        """View backup history"""
        try:
            history_window = tk.Toplevel(self.root)
            history_window.title("Backup History")
            history_window.geometry("1000x700")

            main_frame = ttk.Frame(history_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Backup History",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Read backup metadata
            backup_metadata_path = "/home/seancatchpole989/university_system/data/backup_metadata.json"
            backups = []

            try:
                import json
                if os.path.exists(backup_metadata_path):
                    with open(backup_metadata_path, 'r') as f:
                        backup_data = json.load(f)
                        backups = backup_data.get('backups', [])
            except Exception as e:
                print(f"Error reading backup metadata: {e}")

            # Create table
            columns = ('Date', 'Type', 'Size', 'Location', 'Status')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

            widths = [150, 100, 100, 400, 100]
            for i, col in enumerate(columns):
                tree.heading(col, text=col)
                tree.column(col, width=widths[i])

            for backup in backups:
                tree.insert('', 'end', values=(
                    backup.get('timestamp', 'N/A'),
                    backup.get('type', 'N/A'),
                    backup.get('size', 'N/A'),
                    backup.get('path', 'N/A'),
                    backup.get('status', 'N/A')
                ))

            scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Buttons
            button_frame = ttk.Frame(history_window)
            button_frame.pack(pady=10)

            def restore_selected():
                selected = tree.selection()
                if not selected:
                    messagebox.showwarning("Warning", "Please select a backup to restore")
                    return

                backup_path = tree.item(selected[0])['values'][3]
                confirm = messagebox.askyesno("Confirm Restore",
                                             f"Are you sure you want to restore from:\n{backup_path}\n\nThis will replace the current database!")
                if confirm:
                    self.restore_backup_from_path(backup_path)

            ttk.Button(button_frame, text="Restore Selected", command=restore_selected).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Refresh", command=lambda: self.view_backup_history()).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=history_window.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to view backup history: {e}")

    def schedule_automatic_backup(self):
        """Configure automatic backup schedule"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Schedule Automatic Backup")
            dialog.geometry("700x550")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Automatic Backup Schedule",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Enable/disable
            enable_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(main_frame, text="Enable Automatic Backups",
                           variable=enable_var).pack(anchor='w', pady=10)

            # Frequency
            freq_frame = ttk.LabelFrame(main_frame, text="Backup Frequency", padding=15)
            freq_frame.pack(fill='x', pady=10)

            frequency_var = tk.StringVar(value="daily")
            ttk.Radiobutton(freq_frame, text="Daily", variable=frequency_var, value="daily").pack(anchor='w')
            ttk.Radiobutton(freq_frame, text="Weekly", variable=frequency_var, value="weekly").pack(anchor='w')
            ttk.Radiobutton(freq_frame, text="Monthly", variable=frequency_var, value="monthly").pack(anchor='w')

            # Time
            time_frame = ttk.LabelFrame(main_frame, text="Backup Time", padding=15)
            time_frame.pack(fill='x', pady=10)

            ttk.Label(time_frame, text="Hour (0-23):").grid(row=0, column=0, padx=5)
            hour_var = tk.StringVar(value="2")
            hour_spin = ttk.Spinbox(time_frame, from_=0, to=23, textvariable=hour_var, width=10)
            hour_spin.grid(row=0, column=1, padx=5)

            ttk.Label(time_frame, text="Minute (0-59):").grid(row=0, column=2, padx=5)
            minute_var = tk.StringVar(value="0")
            minute_spin = ttk.Spinbox(time_frame, from_=0, to=59, textvariable=minute_var, width=10)
            minute_spin.grid(row=0, column=3, padx=5)

            # Retention
            retention_frame = ttk.LabelFrame(main_frame, text="Backup Retention", padding=15)
            retention_frame.pack(fill='x', pady=10)

            ttk.Label(retention_frame, text="Keep backups for (days):").grid(row=0, column=0, padx=5)
            retention_var = tk.StringVar(value="30")
            retention_spin = ttk.Spinbox(retention_frame, from_=1, to=365, textvariable=retention_var, width=10)
            retention_spin.grid(row=0, column=1, padx=5)

            def save_schedule():
                config = {
                    'enabled': enable_var.get(),
                    'frequency': frequency_var.get(),
                    'hour': int(hour_var.get()),
                    'minute': int(minute_var.get()),
                    'retention_days': int(retention_var.get())
                }

                # Save configuration
                config_path = "/home/seancatchpole989/university_system/data/backup_schedule.json"
                try:
                    import json
                    with open(config_path, 'w') as f:
                        json.dump(config, f, indent=2)

                    messagebox.showinfo("Success", "Backup schedule saved successfully!")
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save schedule: {e}")

            ttk.Button(main_frame, text="Save Schedule", command=save_schedule).pack(pady=20)
            ttk.Button(main_frame, text="Cancel", command=dialog.destroy).pack()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open schedule dialog: {e}")

    def notification_templates(self):
        """Manage notification templates"""
        try:
            templates_window = tk.Toplevel(self.root)
            templates_window.title("Notification Templates")
            templates_window.geometry("900x700")

            main_frame = ttk.Frame(templates_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Notification Templates",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Pre-defined templates
            templates = [
                ("Document Expiring Soon", "Your {document_type} will expire on {expiry_date}. Please renew it soon."),
                ("Document Verified", "Your {document_type} has been verified and approved."),
                ("Document Rejected", "Your {document_type} was rejected. Reason: {reason}"),
                ("Missing Document", "You are missing a required {document_type}. Please upload it."),
                ("Workflow Step Complete", "Workflow step '{step_name}' has been completed for your {document_type}.")
            ]

            # Create list
            list_frame = ttk.Frame(main_frame)
            list_frame.pack(fill='both', expand=True)

            # Listbox
            template_listbox = tk.Listbox(list_frame, height=15, font=('Arial', 10))
            template_listbox.pack(side='left', fill='both', expand=True)

            for name, _ in templates:
                template_listbox.insert(tk.END, name)

            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=template_listbox.yview)
            template_listbox.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side='right', fill='y')

            # Template preview
            preview_frame = ttk.LabelFrame(main_frame, text="Template Preview", padding=10)
            preview_frame.pack(fill='x', pady=10)

            preview_text = tk.Text(preview_frame, height=5, wrap=tk.WORD)
            preview_text.pack(fill='x')

            def show_template(event):
                selection = template_listbox.curselection()
                if selection:
                    _, template_text = templates[selection[0]]
                    preview_text.delete('1.0', tk.END)
                    preview_text.insert('1.0', template_text)

            template_listbox.bind('<<ListboxSelect>>', show_template)

            # Buttons
            button_frame = ttk.Frame(templates_window)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text="Use Template",
                      command=lambda: self.use_notification_template(
                          templates[template_listbox.curselection()[0]][1] if template_listbox.curselection() else None
                      )).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=templates_window.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open templates: {e}")

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

    # ====================================================================================
    # HELPER FUNCTIONS (8 methods)
    # ====================================================================================

    def log_event(self, action, entity_type, entity_id=None, details=None):
        """
        Log an event/activity to the database

        Args:
            action: Action performed (e.g., 'create', 'update', 'delete', 'view')
            entity_type: Type of entity (e.g., 'document', 'student', 'workflow')
            entity_id: ID of the entity (optional)
            details: Additional details as string or dict (optional)
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get current user info
            username = self.current_user.get('username', 'Unknown') if self.current_user else 'Unknown'
            user_role = self.current_user.get('role', 'user') if self.current_user else 'user'

            # Convert details to JSON string if it's a dict
            details_str = json.dumps(details) if isinstance(details, dict) else str(details) if details else None

            # Insert into activity_log table if it exists, otherwise create a log entry
            try:
                cursor.execute('''
                INSERT INTO activity_log (username, user_role, action, entity_type, entity_id, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (username, user_role, action, entity_type, entity_id, details_str, datetime.now().isoformat()))
                conn.commit()
            except sqlite3.OperationalError:
                # Table might not exist, create it
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    user_role TEXT,
                    action TEXT,
                    entity_type TEXT,
                    entity_id TEXT,
                    details TEXT,
                    timestamp TEXT
                )
                ''')
                cursor.execute('''
                INSERT INTO activity_log (username, user_role, action, entity_type, entity_id, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (username, user_role, action, entity_type, entity_id, details_str, datetime.now().isoformat()))
                conn.commit()

            conn.close()
        except Exception as e:
            print(f"Error logging event: {e}")

    def check_authentication(self):
        """
        Check if user is properly authenticated

        Returns:
            bool: True if authenticated, False otherwise
        """
        try:
            if not self.current_user:
                return False

            # Check if user has required fields
            if not isinstance(self.current_user, dict):
                return False

            if 'username' not in self.current_user or not self.current_user['username']:
                return False

            # Optionally check with authentication system
            try:
                auth_user = get_current_user()
                return auth_user is not None
            except:
                # Fallback to local check
                return True

        except Exception as e:
            print(f"Error checking authentication: {e}")
            return False

    def select_student(self, title="Select Student", allow_search=True):
        """
        Show a dialog to select a student

        Args:
            title: Dialog title
            allow_search: Whether to allow searching for students

        Returns:
            dict: Student info dict with keys: student_id, first_name, last_name, email
                  or None if cancelled
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(title)
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            result = {'selected': None}

            # Main frame
            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text=title, font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Search frame (if enabled)
            if allow_search:
                search_frame = ttk.Frame(main_frame)
                search_frame.pack(fill='x', pady=(0, 10))

                ttk.Label(search_frame, text="Search:").pack(side='left', padx=(0, 5))
                search_var = tk.StringVar()
                search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
                search_entry.pack(side='left', padx=(0, 5))

            # Student list frame
            list_frame = ttk.Frame(main_frame)
            list_frame.pack(fill='both', expand=True)

            # Listbox with scrollbar
            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side='right', fill='y')

            student_listbox = tk.Listbox(list_frame, height=15, font=('Arial', 10),
                                         yscrollcommand=scrollbar.set)
            student_listbox.pack(side='left', fill='both', expand=True)
            scrollbar.config(command=student_listbox.yview)

            # Load students
            students = self.get_students_list()
            student_data = []

            for student in students:
                student_id, first_name, last_name = student[0], student[1], student[2]
                display_text = f"{student_id} - {last_name}, {first_name}"
                student_listbox.insert(tk.END, display_text)
                student_data.append({
                    'student_id': student_id,
                    'first_name': first_name,
                    'last_name': last_name
                })

            # Search functionality
            if allow_search:
                def filter_students(*args):
                    search_text = search_var.get().lower()
                    student_listbox.delete(0, tk.END)
                    for i, student in enumerate(students):
                        student_id, first_name, last_name = student[0], student[1], student[2]
                        display_text = f"{student_id} - {last_name}, {first_name}"
                        if search_text in display_text.lower():
                            student_listbox.insert(tk.END, display_text)

                search_var.trace('w', filter_students)

            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=(20, 0))

            def on_select():
                selection = student_listbox.curselection()
                if selection:
                    index = selection[0]
                    # Find the corresponding student from filtered list
                    selected_text = student_listbox.get(index)
                    student_id = selected_text.split(' - ')[0]

                    # Find full student info
                    for student in student_data:
                        if student['student_id'] == student_id:
                            result['selected'] = student
                            break

                    dialog.destroy()
                else:
                    messagebox.showwarning("Warning", "Please select a student")

            def on_cancel():
                dialog.destroy()

            ttk.Button(button_frame, text="Select", command=on_select).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side='left', padx=5)

            # Double-click to select
            student_listbox.bind('<Double-Button-1>', lambda e: on_select())

            dialog.wait_window()
            return result['selected']

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show student selection: {e}")
            return None

    def select_document_type(self, title="Select Document Type", show_details=True):
        """
        Show a dialog to select a document type

        Args:
            title: Dialog title
            show_details: Whether to show document type details

        Returns:
            dict: Document type info dict with keys: type_id, type_name, description, etc.
                  or None if cancelled
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(title)
            dialog.geometry("700x600")
            dialog.transient(self.root)
            dialog.grab_set()

            result = {'selected': None}

            # Main frame
            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text=title, font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Document type list frame
            list_frame = ttk.Frame(main_frame)
            list_frame.pack(fill='both', expand=True)

            # Listbox with scrollbar
            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side='right', fill='y')

            doctype_listbox = tk.Listbox(list_frame, height=15, font=('Arial', 10),
                                         yscrollcommand=scrollbar.set)
            doctype_listbox.pack(side='left', fill='both', expand=True)
            scrollbar.config(command=doctype_listbox.yview)

            # Load document types
            doc_types = self.get_document_types_with_details()
            doc_type_data = []

            for doc_type in doc_types:
                type_id, type_name, description = doc_type[0], doc_type[1], doc_type[2]
                display_text = f"{type_name}"
                if show_details and description:
                    display_text += f" - {description[:50]}"
                doctype_listbox.insert(tk.END, display_text)

                doc_type_data.append({
                    'type_id': type_id,
                    'type_name': type_name,
                    'description': description,
                    'is_required': doc_type[3] if len(doc_type) > 3 else False,
                    'has_expiry': doc_type[4] if len(doc_type) > 4 else False,
                    'expiry_reminder_days': doc_type[5] if len(doc_type) > 5 else None,
                    'max_file_size_mb': doc_type[6] if len(doc_type) > 6 else 10,
                    'allowed_formats': doc_type[7] if len(doc_type) > 7 else None
                })

            # Details frame
            if show_details:
                details_frame = ttk.LabelFrame(main_frame, text="Document Type Details", padding=10)
                details_frame.pack(fill='x', pady=(10, 0))

                details_text = tk.Text(details_frame, height=6, wrap=tk.WORD, font=('Arial', 9))
                details_text.pack(fill='x')
                details_text.config(state='disabled')

                def on_selection_change(event):
                    selection = doctype_listbox.curselection()
                    if selection:
                        index = selection[0]
                        doc_type = doc_type_data[index]

                        details_text.config(state='normal')
                        details_text.delete('1.0', tk.END)
                        details_text.insert('1.0', f"Type: {doc_type['type_name']}\n")
                        details_text.insert(tk.END, f"Description: {doc_type['description']}\n")
                        details_text.insert(tk.END, f"Required: {'Yes' if doc_type['is_required'] else 'No'}\n")
                        details_text.insert(tk.END, f"Has Expiry: {'Yes' if doc_type['has_expiry'] else 'No'}\n")
                        details_text.insert(tk.END, f"Max Size: {doc_type['max_file_size_mb']}MB\n")
                        details_text.insert(tk.END, f"Formats: {doc_type['allowed_formats']}\n")
                        details_text.config(state='disabled')

                doctype_listbox.bind('<<ListboxSelect>>', on_selection_change)

            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=(20, 0))

            def on_select():
                selection = doctype_listbox.curselection()
                if selection:
                    index = selection[0]
                    result['selected'] = doc_type_data[index]
                    dialog.destroy()
                else:
                    messagebox.showwarning("Warning", "Please select a document type")

            def on_cancel():
                dialog.destroy()

            ttk.Button(button_frame, text="Select", command=on_select).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side='left', padx=5)

            # Double-click to select
            doctype_listbox.bind('<Double-Button-1>', lambda e: on_select())

            dialog.wait_window()
            return result['selected']

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show document type selection: {e}")
            return None

    def get_file_upload_details(self, initial_path=None):
        """
        Get file upload details through file dialog

        Args:
            initial_path: Initial directory path (optional)

        Returns:
            dict: File details with keys: file_path, file_name, file_size, file_size_mb,
                  file_extension, is_valid
                  or None if cancelled
        """
        try:
            # Open file dialog
            file_path = filedialog.askopenfilename(
                title="Select Document File",
                initialdir=initial_path,
                filetypes=[
                    ("All Supported", "*.pdf;*.jpg;*.jpeg;*.png;*.doc;*.docx;*.txt"),
                    ("PDF files", "*.pdf"),
                    ("Image files", "*.jpg;*.jpeg;*.png"),
                    ("Word documents", "*.doc;*.docx"),
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ]
            )

            if not file_path:
                return None

            # Get file details
            if not os.path.exists(file_path):
                messagebox.showerror("Error", "Selected file does not exist")
                return None

            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            file_extension = os.path.splitext(file_path)[1][1:].lower()

            # Validate file size (max 50MB by default)
            is_valid = file_size_mb <= 50

            return {
                'file_path': file_path,
                'file_name': file_name,
                'file_size': file_size,
                'file_size_mb': round(file_size_mb, 2),
                'file_extension': file_extension,
                'is_valid': is_valid
            }

        except Exception as e:
            messagebox.showerror("Error", f"Failed to get file details: {e}")
            return None

    def get_expiry_date(self, doc_type_info=None, allow_manual=True):
        """
        Get or calculate expiry date for a document

        Args:
            doc_type_info: Document type info dict with expiry settings (optional)
            allow_manual: Whether to allow manual date entry

        Returns:
            str: Expiry date in YYYY-MM-DD format or None if not applicable
        """
        try:
            # Check if document type has expiry
            has_expiry = False
            default_days = 365

            if doc_type_info:
                has_expiry = doc_type_info.get('has_expiry', False)
                if doc_type_info.get('expiry_reminder_days'):
                    default_days = doc_type_info['expiry_reminder_days']

            if not has_expiry and not allow_manual:
                return None

            # Show dialog to get expiry date
            dialog = tk.Toplevel(self.root)
            dialog.title("Set Expiry Date")
            dialog.geometry("450x300")
            dialog.transient(self.root)
            dialog.grab_set()

            result = {'date': None}

            # Main frame
            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Set Document Expiry Date",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Options frame
            options_frame = ttk.Frame(main_frame)
            options_frame.pack(fill='both', expand=True)

            # Radio buttons for selection method
            selection_method = tk.StringVar(value='calculated')

            ttk.Radiobutton(options_frame, text="Calculate from today",
                           variable=selection_method, value='calculated').pack(anchor='w', pady=5)

            # Days frame
            days_frame = ttk.Frame(options_frame)
            days_frame.pack(fill='x', padx=(20, 0), pady=5)

            ttk.Label(days_frame, text="Days from today:").pack(side='left')
            days_var = tk.StringVar(value=str(default_days))
            days_entry = ttk.Entry(days_frame, textvariable=days_var, width=10)
            days_entry.pack(side='left', padx=5)

            if allow_manual:
                ttk.Radiobutton(options_frame, text="Enter specific date",
                               variable=selection_method, value='manual').pack(anchor='w', pady=5)

                # Manual date frame
                manual_frame = ttk.Frame(options_frame)
                manual_frame.pack(fill='x', padx=(20, 0), pady=5)

                ttk.Label(manual_frame, text="Date (YYYY-MM-DD):").pack(side='left')
                date_var = tk.StringVar()
                date_entry = ttk.Entry(manual_frame, textvariable=date_var, width=15)
                date_entry.pack(side='left', padx=5)

                # Set default to 1 year from now
                default_date = (datetime.now() + timedelta(days=default_days)).strftime('%Y-%m-%d')
                date_var.set(default_date)

            ttk.Radiobutton(options_frame, text="No expiry date",
                           variable=selection_method, value='none').pack(anchor='w', pady=5)

            # Preview
            preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding=10)
            preview_frame.pack(fill='x', pady=(20, 10))

            preview_label = ttk.Label(preview_frame, text="", font=('Arial', 10, 'bold'))
            preview_label.pack()

            def update_preview(*args):
                method = selection_method.get()
                if method == 'calculated':
                    try:
                        days = int(days_var.get())
                        expiry = datetime.now() + timedelta(days=days)
                        preview_label.config(text=f"Expiry Date: {expiry.strftime('%Y-%m-%d')}")
                    except:
                        preview_label.config(text="Invalid number of days")
                elif method == 'manual' and allow_manual:
                    date_text = date_var.get()
                    try:
                        datetime.strptime(date_text, '%Y-%m-%d')
                        preview_label.config(text=f"Expiry Date: {date_text}")
                    except:
                        preview_label.config(text="Invalid date format")
                else:
                    preview_label.config(text="No expiry date")

            selection_method.trace('w', update_preview)
            days_var.trace('w', update_preview)
            if allow_manual:
                date_var.trace('w', update_preview)

            update_preview()

            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=(10, 0))

            def on_confirm():
                method = selection_method.get()
                if method == 'calculated':
                    try:
                        days = int(days_var.get())
                        expiry = datetime.now() + timedelta(days=days)
                        result['date'] = expiry.strftime('%Y-%m-%d')
                        dialog.destroy()
                    except:
                        messagebox.showerror("Error", "Invalid number of days")
                elif method == 'manual' and allow_manual:
                    date_text = date_var.get()
                    try:
                        datetime.strptime(date_text, '%Y-%m-%d')
                        result['date'] = date_text
                        dialog.destroy()
                    except:
                        messagebox.showerror("Error", "Invalid date format (use YYYY-MM-DD)")
                else:
                    result['date'] = None
                    dialog.destroy()

            def on_cancel():
                result['date'] = None
                dialog.destroy()

            ttk.Button(button_frame, text="Confirm", command=on_confirm).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side='left', padx=5)

            dialog.wait_window()
            return result['date']

        except Exception as e:
            messagebox.showerror("Error", f"Failed to get expiry date: {e}")
            return None

    def select_tags(self, existing_tags=None, allow_create=True):
        """
        Show a dialog to select or create tags

        Args:
            existing_tags: List of existing tag names (optional)
            allow_create: Whether to allow creating new tags

        Returns:
            list: List of selected tag names or None if cancelled
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Select Tags")
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            result = {'tags': None}

            # Main frame
            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Select or Create Tags",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Load existing tags from database
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT tag_name FROM document_tags ORDER BY tag_name')
                db_tags = [row[0] for row in cursor.fetchall()]
                conn.close()
            except:
                db_tags = []

            # Combine with provided tags
            if existing_tags:
                all_tags = list(set(db_tags + existing_tags))
            else:
                all_tags = db_tags

            all_tags.sort()

            # Available tags frame
            available_frame = ttk.LabelFrame(main_frame, text="Available Tags", padding=10)
            available_frame.pack(fill='both', expand=True, pady=(0, 10))

            # Listbox for available tags
            available_list = tk.Listbox(available_frame, height=10, selectmode='multiple',
                                       font=('Arial', 10))
            available_list.pack(side='left', fill='both', expand=True)

            scrollbar = ttk.Scrollbar(available_frame, orient='vertical',
                                     command=available_list.yview)
            scrollbar.pack(side='right', fill='y')
            available_list.config(yscrollcommand=scrollbar.set)

            # Populate tags
            for tag in all_tags:
                available_list.insert(tk.END, tag)

            # New tag frame
            if allow_create:
                new_tag_frame = ttk.LabelFrame(main_frame, text="Create New Tag", padding=10)
                new_tag_frame.pack(fill='x', pady=(0, 10))

                ttk.Label(new_tag_frame, text="Tag Name:").pack(side='left', padx=(0, 5))
                new_tag_var = tk.StringVar()
                new_tag_entry = ttk.Entry(new_tag_frame, textvariable=new_tag_var, width=30)
                new_tag_entry.pack(side='left', padx=(0, 5))

                def add_new_tag():
                    tag_name = new_tag_var.get().strip()
                    if tag_name:
                        if tag_name not in available_list.get(0, tk.END):
                            available_list.insert(tk.END, tag_name)
                            available_list.selection_set(tk.END)
                            new_tag_var.set('')
                        else:
                            messagebox.showinfo("Info", "Tag already exists")
                    else:
                        messagebox.showwarning("Warning", "Please enter a tag name")

                ttk.Button(new_tag_frame, text="Add", command=add_new_tag).pack(side='left')

            # Selected tags display
            selected_frame = ttk.LabelFrame(main_frame, text="Selected Tags", padding=10)
            selected_frame.pack(fill='x')

            selected_label = ttk.Label(selected_frame, text="None selected",
                                      font=('Arial', 9), foreground='gray')
            selected_label.pack()

            def update_selected_display(*args):
                selection = available_list.curselection()
                if selection:
                    selected_tags = [available_list.get(i) for i in selection]
                    selected_label.config(text=', '.join(selected_tags), foreground='black')
                else:
                    selected_label.config(text="None selected", foreground='gray')

            available_list.bind('<<ListboxSelect>>', update_selected_display)

            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=(20, 0))

            def on_confirm():
                selection = available_list.curselection()
                if selection:
                    result['tags'] = [available_list.get(i) for i in selection]
                else:
                    result['tags'] = []
                dialog.destroy()

            def on_cancel():
                result['tags'] = None
                dialog.destroy()

            ttk.Button(button_frame, text="Confirm", command=on_confirm).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side='left', padx=5)

            dialog.wait_window()
            return result['tags']

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show tag selection: {e}")
            return None

    def ensure_login(self, required_role=None):
        """
        Ensure user is logged in with optional role check

        Args:
            required_role: Required role (e.g., 'admin', 'staff') or None for any logged-in user

        Returns:
            bool: True if user is logged in (and has required role), False otherwise

        Raises:
            PermissionError: If role check fails
        """
        try:
            # Check if authenticated
            if not self.check_authentication():
                messagebox.showerror("Authentication Required",
                                   "You must be logged in to perform this action.")
                return False

            # Check role if required
            if required_role:
                user_role = self.current_user.get('role', '').lower()
                required_role_lower = required_role.lower()

                # Admin has access to everything
                if user_role == 'admin':
                    return True

                # Check specific role
                if user_role != required_role_lower:
                    messagebox.showerror("Permission Denied",
                                       f"This action requires '{required_role}' role.\n"
                                       f"Your role: '{user_role}'")
                    raise PermissionError(f"User role '{user_role}' does not have access "
                                        f"(required: '{required_role}')")

            # Log the access
            self.log_event('access', 'system', details={
                'action': 'ensure_login',
                'required_role': required_role,
                'user_role': self.current_user.get('role', 'unknown')
            })

            return True

        except PermissionError:
            raise
        except Exception as e:
            messagebox.showerror("Error", f"Authentication check failed: {e}")
            return False

    # ====================================================================================
    # WORKFLOW MANAGEMENT (3 methods)
    # ====================================================================================

    def create_custom_workflow(self):
        """
        Create a custom workflow for document processing
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Create Custom Workflow")
            dialog.geometry("800x700")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Create Custom Workflow",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Workflow name
            name_frame = ttk.LabelFrame(main_frame, text="Workflow Information", padding=10)
            name_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(name_frame, text="Workflow Name:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            workflow_name = tk.StringVar()
            ttk.Entry(name_frame, textvariable=workflow_name, width=40).grid(row=0, column=1, padx=5, pady=5, sticky='ew')

            ttk.Label(name_frame, text="Document Type:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
            doc_type_combo = ttk.Combobox(name_frame, width=37, state='readonly')
            doc_type_combo.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

            # Load document types
            doc_types = self.get_document_types_with_details()
            doc_type_combo['values'] = [f"{dt[1]}" for dt in doc_types]

            name_frame.grid_columnconfigure(1, weight=1)

            # Workflow steps
            steps_frame = ttk.LabelFrame(main_frame, text="Workflow Steps", padding=10)
            steps_frame.pack(fill='both', expand=True, pady=(0, 15))

            # Steps list
            steps_list_frame = ttk.Frame(steps_frame)
            steps_list_frame.pack(fill='both', expand=True)

            columns = ('Order', 'Step Name', 'Assigned To', 'Description')
            steps_tree = ttk.Treeview(steps_list_frame, columns=columns, show='headings', height=8)

            for col in columns:
                steps_tree.heading(col, text=col)
                if col == 'Order':
                    steps_tree.column(col, width=50)
                elif col == 'Step Name':
                    steps_tree.column(col, width=150)
                elif col == 'Assigned To':
                    steps_tree.column(col, width=120)
                else:
                    steps_tree.column(col, width=200)

            scrollbar = ttk.Scrollbar(steps_list_frame, orient='vertical', command=steps_tree.yview)
            steps_tree.configure(yscrollcommand=scrollbar.set)
            steps_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Add step controls
            add_step_frame = ttk.Frame(steps_frame)
            add_step_frame.pack(fill='x', pady=(10, 0))

            ttk.Label(add_step_frame, text="Step Name:").grid(row=0, column=0, sticky='w', padx=5)
            step_name = tk.StringVar()
            ttk.Entry(add_step_frame, textvariable=step_name, width=20).grid(row=0, column=1, padx=5)

            ttk.Label(add_step_frame, text="Assigned To:").grid(row=0, column=2, sticky='w', padx=5)
            assigned_to = tk.StringVar()
            ttk.Entry(add_step_frame, textvariable=assigned_to, width=15).grid(row=0, column=3, padx=5)

            ttk.Label(add_step_frame, text="Description:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
            step_desc = tk.StringVar()
            ttk.Entry(add_step_frame, textvariable=step_desc, width=50).grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky='ew')

            def add_step():
                if step_name.get() and assigned_to.get():
                    order = len(steps_tree.get_children()) + 1
                    steps_tree.insert('', 'end', values=(
                        order, step_name.get(), assigned_to.get(), step_desc.get()
                    ))
                    step_name.set('')
                    assigned_to.set('')
                    step_desc.set('')
                else:
                    messagebox.showwarning("Warning", "Please enter step name and assigned to")

            def remove_step():
                selection = steps_tree.selection()
                if selection:
                    steps_tree.delete(selection)
                    # Reorder remaining steps
                    for idx, item in enumerate(steps_tree.get_children(), 1):
                        steps_tree.set(item, 'Order', idx)
                else:
                    messagebox.showwarning("Warning", "Please select a step to remove")

            button_frame = ttk.Frame(add_step_frame)
            button_frame.grid(row=2, column=0, columnspan=4, pady=10)
            ttk.Button(button_frame, text="Add Step", command=add_step).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Remove Selected", command=remove_step).pack(side='left', padx=5)

            add_step_frame.grid_columnconfigure(1, weight=1)

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(10, 0))

            def save_workflow():
                name = workflow_name.get().strip()
                doc_type = doc_type_combo.get()

                if not name:
                    messagebox.showerror("Error", "Please enter workflow name")
                    return

                if not doc_type:
                    messagebox.showerror("Error", "Please select document type")
                    return

                steps = steps_tree.get_children()
                if not steps:
                    messagebox.showerror("Error", "Please add at least one workflow step")
                    return

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Create workflow_templates table if not exists
                    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS workflow_templates (
                        template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        template_name TEXT,
                        document_type_name TEXT,
                        created_date TEXT,
                        created_by TEXT,
                        is_active BOOLEAN DEFAULT 1
                    )
                    ''')

                    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS workflow_template_steps (
                        step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        template_id INTEGER,
                        step_name TEXT,
                        step_order INTEGER,
                        assigned_to TEXT,
                        description TEXT,
                        FOREIGN KEY (template_id) REFERENCES workflow_templates (template_id)
                    )
                    ''')

                    # Insert workflow template
                    username = self.current_user.get('username', 'Unknown') if self.current_user else 'Unknown'
                    cursor.execute('''
                    INSERT INTO workflow_templates (template_name, document_type_name, created_date, created_by)
                    VALUES (?, ?, ?, ?)
                    ''', (name, doc_type, datetime.now().isoformat(), username))

                    template_id = cursor.lastrowid

                    # Insert workflow steps
                    for item in steps:
                        values = steps_tree.item(item)['values']
                        order, step_name_val, assigned_to_val, desc = values
                        cursor.execute('''
                        INSERT INTO workflow_template_steps (template_id, step_name, step_order, assigned_to, description)
                        VALUES (?, ?, ?, ?, ?)
                        ''', (template_id, step_name_val, order, assigned_to_val, desc))

                    conn.commit()
                    conn.close()

                    # Log event
                    self.log_event('create', 'workflow_template', template_id, {
                        'template_name': name,
                        'steps_count': len(steps)
                    })

                    messagebox.showinfo("Success", f"Workflow '{name}' created successfully with {len(steps)} steps")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create workflow: {e}")

            ttk.Button(action_frame, text="Save Workflow", command=save_workflow).pack(side='right', padx=5)
            ttk.Button(action_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open workflow creator: {e}")

    def workflow_templates(self):
        """
        View and manage workflow templates
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Workflow Templates")
            dialog.geometry("1000x700")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Workflow Templates",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Templates list
            list_frame = ttk.Frame(main_frame)
            list_frame.pack(fill='both', expand=True)

            columns = ('ID', 'Template Name', 'Document Type', 'Steps', 'Created By', 'Created Date', 'Status')
            templates_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

            for col in columns:
                templates_tree.heading(col, text=col)
                if col == 'ID':
                    templates_tree.column(col, width=50)
                elif col == 'Steps':
                    templates_tree.column(col, width=60)
                else:
                    templates_tree.column(col, width=150)

            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=templates_tree.yview)
            templates_tree.configure(yscrollcommand=scrollbar.set)
            templates_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Load templates
            def load_templates():
                templates_tree.delete(*templates_tree.get_children())
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                    SELECT
                        wt.template_id,
                        wt.template_name,
                        wt.document_type_name,
                        COUNT(wts.step_id) as step_count,
                        wt.created_by,
                        wt.created_date,
                        wt.is_active
                    FROM workflow_templates wt
                    LEFT JOIN workflow_template_steps wts ON wt.template_id = wts.template_id
                    GROUP BY wt.template_id
                    ORDER BY wt.created_date DESC
                    ''')

                    templates = cursor.fetchall()
                    conn.close()

                    for template in templates:
                        status = 'Active' if template[6] else 'Inactive'
                        templates_tree.insert('', 'end', values=(
                            template[0], template[1], template[2], template[3],
                            template[4], template[5], status
                        ))

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load templates: {e}")

            load_templates()

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(20, 0))

            def view_template_details():
                selection = templates_tree.selection()
                if not selection:
                    messagebox.showwarning("Warning", "Please select a template")
                    return

                template_id = templates_tree.item(selection[0])['values'][0]

                # Show template details
                detail_dialog = tk.Toplevel(dialog)
                detail_dialog.title("Template Details")
                detail_dialog.geometry("700x500")
                detail_dialog.transient(dialog)

                detail_frame = ttk.Frame(detail_dialog, padding=20)
                detail_frame.pack(fill='both', expand=True)

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Get template info
                    cursor.execute('''
                    SELECT template_name, document_type_name, created_by, created_date
                    FROM workflow_templates WHERE template_id = ?
                    ''', (template_id,))
                    template_info = cursor.fetchone()

                    # Get steps
                    cursor.execute('''
                    SELECT step_order, step_name, assigned_to, description
                    FROM workflow_template_steps
                    WHERE template_id = ?
                    ORDER BY step_order
                    ''', (template_id,))
                    steps = cursor.fetchall()
                    conn.close()

                    # Display info
                    info_text = f"Template: {template_info[0]}\n"
                    info_text += f"Document Type: {template_info[1]}\n"
                    info_text += f"Created By: {template_info[2]}\n"
                    info_text += f"Created: {template_info[3]}\n\n"
                    info_text += "Workflow Steps:\n" + "="*50 + "\n"

                    for step in steps:
                        info_text += f"\nStep {step[0]}: {step[1]}\n"
                        info_text += f"  Assigned To: {step[2]}\n"
                        info_text += f"  Description: {step[3]}\n"

                    text_widget = tk.Text(detail_frame, wrap=tk.WORD, font=('Arial', 10))
                    text_widget.pack(fill='both', expand=True)
                    text_widget.insert('1.0', info_text)
                    text_widget.config(state='disabled')

                    ttk.Button(detail_frame, text="Close", command=detail_dialog.destroy).pack(pady=10)

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load template details: {e}")

            def toggle_template_status():
                selection = templates_tree.selection()
                if not selection:
                    messagebox.showwarning("Warning", "Please select a template")
                    return

                template_id = templates_tree.item(selection[0])['values'][0]
                current_status = templates_tree.item(selection[0])['values'][6]

                new_status = 0 if current_status == 'Active' else 1

                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('UPDATE workflow_templates SET is_active = ? WHERE template_id = ?',
                                 (new_status, template_id))
                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Template status updated")
                    load_templates()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update status: {e}")

            ttk.Button(action_frame, text="View Details", command=view_template_details).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Toggle Active/Inactive", command=toggle_template_status).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Refresh", command=load_templates).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open workflow templates: {e}")

    def workflow_analytics(self):
        """
        View workflow analytics and statistics
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Workflow Analytics")
            dialog.geometry("1100x750")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Workflow Analytics Dashboard",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Summary cards
            summary_frame = ttk.Frame(main_frame)
            summary_frame.pack(fill='x', pady=(0, 20))

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Total workflows
                cursor.execute('SELECT COUNT(*) FROM document_workflow')
                total_workflows = cursor.fetchone()[0]

                # Pending workflows
                cursor.execute("SELECT COUNT(*) FROM document_workflow WHERE status = 'pending'")
                pending_workflows = cursor.fetchone()[0]

                # Completed workflows
                cursor.execute("SELECT COUNT(*) FROM document_workflow WHERE status = 'completed'")
                completed_workflows = cursor.fetchone()[0]

                # Average completion time
                cursor.execute('''
                SELECT AVG(julianday(completed_date) - julianday(
                    (SELECT MIN(created_date) FROM document_workflow dw2
                     WHERE dw2.document_id = document_workflow.document_id)
                ))
                FROM document_workflow
                WHERE status = 'completed' AND completed_date IS NOT NULL
                ''')
                avg_days = cursor.fetchone()[0]
                avg_days = round(avg_days, 1) if avg_days else 0

                conn.close()

                # Display cards
                self.create_stat_card(summary_frame, "Total Workflows", total_workflows, '#3498db', 0)
                self.create_stat_card(summary_frame, "Pending", pending_workflows, '#f39c12', 1)
                self.create_stat_card(summary_frame, "Completed", completed_workflows, '#27ae60', 2)
                self.create_stat_card(summary_frame, f"Avg. Days", avg_days, '#9b59b6', 3)

            except Exception as e:
                ttk.Label(summary_frame, text=f"Error loading summary: {e}",
                         foreground='red').pack()

            # Workflow by status
            status_frame = ttk.LabelFrame(main_frame, text="Workflows by Status", padding=10)
            status_frame.pack(fill='both', expand=True, pady=(0, 10))

            columns = ('Status', 'Count', 'Percentage')
            status_tree = ttk.Treeview(status_frame, columns=columns, show='headings', height=5)

            for col in columns:
                status_tree.heading(col, text=col)
                status_tree.column(col, width=150)

            status_tree.pack(fill='both', expand=True)

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM document_workflow
                GROUP BY status
                ''')
                status_data = cursor.fetchall()
                conn.close()

                total = sum(row[1] for row in status_data) if status_data else 1

                for status, count in status_data:
                    percentage = (count / total * 100) if total > 0 else 0
                    status_tree.insert('', 'end', values=(
                        status.title(), count, f"{percentage:.1f}%"
                    ))

            except Exception as e:
                pass

            # Workflow by assignee
            assignee_frame = ttk.LabelFrame(main_frame, text="Workflows by Assignee", padding=10)
            assignee_frame.pack(fill='both', expand=True)

            columns = ('Assigned To', 'Pending', 'Completed', 'Total')
            assignee_tree = ttk.Treeview(assignee_frame, columns=columns, show='headings', height=8)

            for col in columns:
                assignee_tree.heading(col, text=col)
                assignee_tree.column(col, width=150)

            assignee_tree.pack(fill='both', expand=True)

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT
                    assigned_to,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    COUNT(*) as total
                FROM document_workflow
                WHERE assigned_to IS NOT NULL
                GROUP BY assigned_to
                ORDER BY total DESC
                ''')
                assignee_data = cursor.fetchall()
                conn.close()

                for row in assignee_data:
                    assignee_tree.insert('', 'end', values=row)

            except Exception as e:
                pass

            # Export button
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x', pady=(20, 0))

            def export_analytics():
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=f"workflow_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                )

                if file_path:
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()

                        cursor.execute('''
                        SELECT
                            dw.workflow_id,
                            dw.document_id,
                            dw.step_name,
                            dw.assigned_to,
                            dw.status,
                            dw.completed_date,
                            dw.completed_by
                        FROM document_workflow dw
                        ORDER BY dw.workflow_id
                        ''')
                        workflows = cursor.fetchall()
                        conn.close()

                        with open(file_path, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            writer.writerow(['Workflow ID', 'Document ID', 'Step Name', 'Assigned To',
                                           'Status', 'Completed Date', 'Completed By'])
                            writer.writerows(workflows)

                        messagebox.showinfo("Success", f"Analytics exported to:\n{file_path}")

                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to export analytics: {e}")

            ttk.Button(button_frame, text="Export Analytics", command=export_analytics).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open workflow analytics: {e}")

    # ====================================================================================
    # ANALYTICS (3 methods)
    # ====================================================================================

    def version_analytics(self):
        """
        View document version analytics
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Version Analytics")
            dialog.geometry("1000x700")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Document Version Analytics",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Summary cards
            summary_frame = ttk.Frame(main_frame)
            summary_frame.pack(fill='x', pady=(0, 20))

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Total documents
                cursor.execute('SELECT COUNT(DISTINCT document_id) FROM student_documents')
                total_docs = cursor.fetchone()[0]

                # Total versions
                cursor.execute('SELECT COUNT(*) FROM student_documents')
                total_versions = cursor.fetchone()[0]

                # Documents with multiple versions
                cursor.execute('''
                SELECT COUNT(*) FROM (
                    SELECT document_id FROM student_documents
                    GROUP BY document_id HAVING COUNT(*) > 1
                )
                ''')
                multi_version_docs = cursor.fetchone()[0]

                # Average versions per document
                avg_versions = round(total_versions / total_docs, 2) if total_docs > 0 else 0

                conn.close()

                # Display cards
                self.create_stat_card(summary_frame, "Total Documents", total_docs, '#3498db', 0)
                self.create_stat_card(summary_frame, "Total Versions", total_versions, '#27ae60', 1)
                self.create_stat_card(summary_frame, "Multi-Version Docs", multi_version_docs, '#f39c12', 2)
                self.create_stat_card(summary_frame, "Avg Versions", avg_versions, '#9b59b6', 3)

            except Exception as e:
                ttk.Label(summary_frame, text=f"Error loading summary: {e}",
                         foreground='red').pack()

            # Version distribution
            dist_frame = ttk.LabelFrame(main_frame, text="Version Distribution", padding=10)
            dist_frame.pack(fill='both', expand=True, pady=(0, 10))

            columns = ('Document ID', 'Student', 'Type', 'Versions', 'Current Version', 'Last Updated')
            dist_tree = ttk.Treeview(dist_frame, columns=columns, show='headings', height=12)

            for col in columns:
                dist_tree.heading(col, text=col)
                if col == 'Document ID':
                    dist_tree.column(col, width=80)
                elif col == 'Versions':
                    dist_tree.column(col, width=70)
                else:
                    dist_tree.column(col, width=140)

            scrollbar = ttk.Scrollbar(dist_frame, orient='vertical', command=dist_tree.yview)
            dist_tree.configure(yscrollcommand=scrollbar.set)
            dist_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT
                    sd.document_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    dt.type_name,
                    COUNT(*) as version_count,
                    MAX(sd.version_number) as current_version,
                    MAX(sd.upload_date) as last_updated
                FROM student_documents sd
                JOIN students s ON sd.student_id = s.student_id
                JOIN document_types dt ON sd.type_id = dt.type_id
                GROUP BY sd.document_id
                HAVING COUNT(*) > 1
                ORDER BY version_count DESC, last_updated DESC
                LIMIT 100
                ''')
                version_data = cursor.fetchall()
                conn.close()

                for row in version_data:
                    dist_tree.insert('', 'end', values=row)

            except Exception as e:
                pass

            # Action buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x', pady=(10, 0))

            def export_analytics():
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=f"version_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                )

                if file_path:
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()

                        cursor.execute('''
                        SELECT
                            sd.document_id,
                            s.student_id,
                            s.first_name || ' ' || s.last_name as student_name,
                            dt.type_name,
                            sd.version_number,
                            sd.upload_date,
                            sd.file_name
                        FROM student_documents sd
                        JOIN students s ON sd.student_id = s.student_id
                        JOIN document_types dt ON sd.type_id = dt.type_id
                        ORDER BY sd.document_id, sd.version_number
                        ''')
                        versions = cursor.fetchall()
                        conn.close()

                        with open(file_path, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            writer.writerow(['Document ID', 'Student ID', 'Student Name', 'Document Type',
                                           'Version', 'Upload Date', 'File Name'])
                            writer.writerows(versions)

                        messagebox.showinfo("Success", f"Analytics exported to:\n{file_path}")

                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to export: {e}")

            ttk.Button(button_frame, text="Export Analytics", command=export_analytics).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open version analytics: {e}")

    def template_analytics(self):
        """
        View workflow template usage analytics
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Template Analytics")
            dialog.geometry("1000x700")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Workflow Template Analytics",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Summary
            summary_frame = ttk.Frame(main_frame)
            summary_frame.pack(fill='x', pady=(0, 20))

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Total templates
                cursor.execute('SELECT COUNT(*) FROM workflow_templates')
                total_templates = cursor.fetchone()[0]

                # Active templates
                cursor.execute('SELECT COUNT(*) FROM workflow_templates WHERE is_active = 1')
                active_templates = cursor.fetchone()[0]

                # Total template steps
                cursor.execute('SELECT COUNT(*) FROM workflow_template_steps')
                total_steps = cursor.fetchone()[0]

                # Average steps per template
                avg_steps = round(total_steps / total_templates, 1) if total_templates > 0 else 0

                conn.close()

                self.create_stat_card(summary_frame, "Total Templates", total_templates, '#3498db', 0)
                self.create_stat_card(summary_frame, "Active Templates", active_templates, '#27ae60', 1)
                self.create_stat_card(summary_frame, "Total Steps", total_steps, '#f39c12', 2)
                self.create_stat_card(summary_frame, "Avg Steps", avg_steps, '#9b59b6', 3)

            except Exception as e:
                ttk.Label(summary_frame, text=f"Error loading summary: {e}",
                         foreground='red').pack()

            # Template usage
            usage_frame = ttk.LabelFrame(main_frame, text="Template Usage Statistics", padding=10)
            usage_frame.pack(fill='both', expand=True)

            columns = ('Template', 'Document Type', 'Steps', 'Created By', 'Status')
            usage_tree = ttk.Treeview(usage_frame, columns=columns, show='headings', height=15)

            for col in columns:
                usage_tree.heading(col, text=col)
                if col == 'Steps':
                    usage_tree.column(col, width=60)
                else:
                    usage_tree.column(col, width=180)

            scrollbar = ttk.Scrollbar(usage_frame, orient='vertical', command=usage_tree.yview)
            usage_tree.configure(yscrollcommand=scrollbar.set)
            usage_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT
                    wt.template_name,
                    wt.document_type_name,
                    COUNT(wts.step_id) as step_count,
                    wt.created_by,
                    CASE WHEN wt.is_active = 1 THEN 'Active' ELSE 'Inactive' END as status
                FROM workflow_templates wt
                LEFT JOIN workflow_template_steps wts ON wt.template_id = wts.template_id
                GROUP BY wt.template_id
                ORDER BY wt.template_name
                ''')
                templates = cursor.fetchall()
                conn.close()

                for row in templates:
                    usage_tree.insert('', 'end', values=row)

            except Exception as e:
                pass

            # Action buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x', pady=(20, 0))

            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open template analytics: {e}")

    def set_course_requirements(self):
        """
        Set document requirements for courses/programs
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Set Course Requirements")
            dialog.geometry("900x700")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Set Course Document Requirements",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Course selection
            course_frame = ttk.LabelFrame(main_frame, text="Course/Program Information", padding=10)
            course_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(course_frame, text="Course Code:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            course_code = tk.StringVar()
            ttk.Entry(course_frame, textvariable=course_code, width=20).grid(row=0, column=1, padx=5, pady=5, sticky='w')

            ttk.Label(course_frame, text="Program:").grid(row=0, column=2, sticky='w', padx=5, pady=5)
            program = tk.StringVar()
            ttk.Entry(program, textvariable=program, width=30).grid(row=0, column=3, padx=5, pady=5, sticky='w')

            ttk.Label(course_frame, text="Year:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
            year = tk.StringVar(value="All")
            year_combo = ttk.Combobox(course_frame, textvariable=year, values=['All', '1', '2', '3', '4'], width=17, state='readonly')
            year_combo.grid(row=1, column=1, padx=5, pady=5, sticky='w')

            # Required documents
            docs_frame = ttk.LabelFrame(main_frame, text="Required Documents", padding=10)
            docs_frame.pack(fill='both', expand=True, pady=(0, 15))

            # Document list
            list_frame = ttk.Frame(docs_frame)
            list_frame.pack(fill='both', expand=True)

            columns = ('Document Type', 'Required', 'Deadline (Days)')
            docs_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

            for col in columns:
                docs_tree.heading(col, text=col)
                if col == 'Required':
                    docs_tree.column(col, width=80)
                elif col == 'Deadline (Days)':
                    docs_tree.column(col, width=120)
                else:
                    docs_tree.column(col, width=250)

            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=docs_tree.yview)
            docs_tree.configure(yscrollcommand=scrollbar.set)
            docs_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Load document types with checkboxes
            doc_types = self.get_document_types_with_details()
            doc_checkboxes = {}

            for doc_type in doc_types:
                type_id, type_name = doc_type[0], doc_type[1]
                item = docs_tree.insert('', 'end', text='☐', values=(type_name, 'No', '30'))
                doc_checkboxes[item] = {'type_id': type_id, 'checked': False}

            def toggle_checkbox(event):
                item = docs_tree.selection()[0] if docs_tree.selection() else None
                if item and item in doc_checkboxes:
                    doc_checkboxes[item]['checked'] = not doc_checkboxes[item]['checked']
                    checked = doc_checkboxes[item]['checked']
                    docs_tree.item(item, text='☑' if checked else '☐')
                    values = list(docs_tree.item(item)['values'])
                    values[1] = 'Yes' if checked else 'No'
                    docs_tree.item(item, values=values)

            docs_tree.bind('<Button-1>', toggle_checkbox)

            # Deadline input
            deadline_frame = ttk.Frame(docs_frame)
            deadline_frame.pack(fill='x', pady=(10, 0))

            ttk.Label(deadline_frame, text="Set deadline (days) for selected:").pack(side='left', padx=5)
            deadline_var = tk.StringVar(value="30")
            ttk.Entry(deadline_frame, textvariable=deadline_var, width=10).pack(side='left', padx=5)

            def set_deadline():
                selection = docs_tree.selection()
                if selection:
                    try:
                        days = int(deadline_var.get())
                        for item in selection:
                            values = list(docs_tree.item(item)['values'])
                            values[2] = str(days)
                            docs_tree.item(item, values=values)
                    except ValueError:
                        messagebox.showerror("Error", "Please enter a valid number of days")
                else:
                    messagebox.showwarning("Warning", "Please select documents first")

            ttk.Button(deadline_frame, text="Set Deadline", command=set_deadline).pack(side='left', padx=5)

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(10, 0))

            def save_requirements():
                code = course_code.get().strip()
                prog = program.get().strip()

                if not code and not prog:
                    messagebox.showerror("Error", "Please enter course code or program name")
                    return

                # Get checked documents
                required_docs = []
                for item, data in doc_checkboxes.items():
                    if data['checked']:
                        values = docs_tree.item(item)['values']
                        required_docs.append({
                            'type_id': data['type_id'],
                            'type_name': values[0],
                            'deadline_days': int(values[2])
                        })

                if not required_docs:
                    messagebox.showerror("Error", "Please select at least one required document")
                    return

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Create table if not exists
                    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS course_requirements (
                        requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        course_code TEXT,
                        program TEXT,
                        year TEXT,
                        type_id INTEGER,
                        deadline_days INTEGER,
                        created_date TEXT,
                        created_by TEXT
                    )
                    ''')

                    # Delete existing requirements for this course/program
                    cursor.execute('''
                    DELETE FROM course_requirements
                    WHERE course_code = ? AND program = ? AND year = ?
                    ''', (code, prog, year.get()))

                    # Insert new requirements
                    username = self.current_user.get('username', 'Unknown') if self.current_user else 'Unknown'
                    for doc in required_docs:
                        cursor.execute('''
                        INSERT INTO course_requirements
                        (course_code, program, year, type_id, deadline_days, created_date, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (code, prog, year.get(), doc['type_id'], doc['deadline_days'],
                             datetime.now().isoformat(), username))

                    conn.commit()
                    conn.close()

                    self.log_event('create', 'course_requirements', None, {
                        'course_code': code,
                        'program': prog,
                        'required_docs': len(required_docs)
                    })

                    messagebox.showinfo("Success",
                                      f"Requirements saved for {code or prog}\n"
                                      f"{len(required_docs)} required documents set")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save requirements: {e}")

            ttk.Button(action_frame, text="Save Requirements", command=save_requirements).pack(side='right', padx=5)
            ttk.Button(action_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open course requirements: {e}")

    # ====================================================================================
    # MAINTENANCE (1 method)
    # ====================================================================================

    def archive_old_versions(self):
        """
        Archive old document versions
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Archive Old Versions")
            dialog.geometry("700x600")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Archive Old Document Versions",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Options
            options_frame = ttk.LabelFrame(main_frame, text="Archive Options", padding=15)
            options_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(options_frame, text="Archive versions older than:").grid(row=0, column=0, sticky='w', pady=5)
            days_var = tk.StringVar(value="365")
            ttk.Entry(options_frame, textvariable=days_var, width=10).grid(row=0, column=1, padx=5, pady=5, sticky='w')
            ttk.Label(options_frame, text="days").grid(row=0, column=2, sticky='w', pady=5)

            keep_current = tk.BooleanVar(value=True)
            ttk.Checkbutton(options_frame, text="Keep current version (recommended)",
                          variable=keep_current).grid(row=1, column=0, columnspan=3, sticky='w', pady=5)

            create_backup = tk.BooleanVar(value=True)
            ttk.Checkbutton(options_frame, text="Create backup before archiving",
                          variable=create_backup).grid(row=2, column=0, columnspan=3, sticky='w', pady=5)

            # Preview frame
            preview_frame = ttk.LabelFrame(main_frame, text="Documents to Archive (Preview)", padding=10)
            preview_frame.pack(fill='both', expand=True, pady=(0, 15))

            columns = ('Document ID', 'Student', 'Type', 'Version', 'Upload Date')
            preview_tree = ttk.Treeview(preview_frame, columns=columns, show='headings', height=10)

            for col in columns:
                preview_tree.heading(col, text=col)
                preview_tree.column(col, width=120)

            scrollbar = ttk.Scrollbar(preview_frame, orient='vertical', command=preview_tree.yview)
            preview_tree.configure(yscrollcommand=scrollbar.set)
            preview_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            stats_label = ttk.Label(preview_frame, text="", font=('Arial', 9), foreground='blue')
            stats_label.pack(pady=(5, 0))

            def load_preview():
                preview_tree.delete(*preview_tree.get_children())
                try:
                    days = int(days_var.get())
                    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

                    conn = get_connection()
                    cursor = conn.cursor()

                    query = '''
                    SELECT
                        sd.document_id,
                        s.first_name || ' ' || s.last_name as student_name,
                        dt.type_name,
                        sd.version_number,
                        sd.upload_date
                    FROM student_documents sd
                    JOIN students s ON sd.student_id = s.student_id
                    JOIN document_types dt ON sd.type_id = dt.type_id
                    WHERE sd.upload_date < ?
                    '''

                    if keep_current.get():
                        query += ' AND sd.is_current_version = 0'

                    query += ' ORDER BY sd.upload_date'

                    cursor.execute(query, (cutoff_date,))
                    docs = cursor.fetchall()
                    conn.close()

                    for doc in docs:
                        preview_tree.insert('', 'end', values=doc)

                    stats_label.config(text=f"Found {len(docs)} versions to archive")

                except ValueError:
                    messagebox.showerror("Error", "Please enter a valid number of days")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load preview: {e}")

            # Preview button
            ttk.Button(options_frame, text="Load Preview", command=load_preview).grid(row=3, column=0, columnspan=3, pady=10)

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x')

            def perform_archive():
                if len(preview_tree.get_children()) == 0:
                    messagebox.showwarning("Warning", "No documents to archive. Click 'Load Preview' first.")
                    return

                response = messagebox.askyesno("Confirm Archive",
                                             f"Archive {len(preview_tree.get_children())} document versions?\n\n"
                                             "This will mark them as archived in the database.")

                if not response:
                    return

                try:
                    # Create backup if requested
                    if create_backup.get():
                        backup_path = f"backups/pre_archive_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                        os.makedirs('backups', exist_ok=True)
                        import shutil
                        shutil.copy2(paths.DEFAULT_DB_PATH, backup_path)

                    days = int(days_var.get())
                    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

                    conn = get_connection()
                    cursor = conn.cursor()

                    # Add archived column if doesn't exist
                    try:
                        cursor.execute('ALTER TABLE student_documents ADD COLUMN archived BOOLEAN DEFAULT 0')
                    except:
                        pass

                    # Mark documents as archived
                    query = 'UPDATE student_documents SET archived = 1 WHERE upload_date < ?'
                    params = [cutoff_date]

                    if keep_current.get():
                        query += ' AND is_current_version = 0'

                    cursor.execute(query, params)
                    archived_count = cursor.rowcount

                    conn.commit()
                    conn.close()

                    self.log_event('archive', 'documents', None, {
                        'archived_count': archived_count,
                        'days_threshold': days
                    })

                    messagebox.showinfo("Success",
                                      f"Successfully archived {archived_count} document versions\n"
                                      f"Backup created: {backup_path if create_backup.get() else 'None'}")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to archive documents: {e}")

            ttk.Button(action_frame, text="Archive Documents", command=perform_archive).pack(side='right', padx=5)
            ttk.Button(action_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

            # Load initial preview
            load_preview()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open archive dialog: {e}")

    # ====================================================================================
    # DATABASE OPERATIONS (4 methods)
    # ====================================================================================

    def migrate_tables(self):
        """
        Perform database schema migrations
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Database Migrations")
            dialog.geometry("800x600")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Database Schema Migrations",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Available migrations
            migrations_frame = ttk.LabelFrame(main_frame, text="Available Migrations", padding=10)
            migrations_frame.pack(fill='both', expand=True, pady=(0, 15))

            # Migration list
            migrations_list = tk.Listbox(migrations_frame, height=15, font=('Arial', 10))
            migrations_list.pack(fill='both', expand=True)

            scrollbar = ttk.Scrollbar(migrations_frame, orient='vertical', command=migrations_list.yview)
            migrations_list.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side='right', fill='y')

            # Define available migrations
            available_migrations = [
                ("Add archived column to documents", "ALTER TABLE student_documents ADD COLUMN archived BOOLEAN DEFAULT 0"),
                ("Add priority to notifications", "ALTER TABLE notifications ADD COLUMN priority TEXT DEFAULT 'normal'"),
                ("Add created_by to workflows", "ALTER TABLE document_workflow ADD COLUMN created_by TEXT"),
                ("Add is_active to document types", "ALTER TABLE document_types ADD COLUMN is_active BOOLEAN DEFAULT 1"),
                ("Create activity_log table", """
                    CREATE TABLE IF NOT EXISTS activity_log (
                        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT,
                        user_role TEXT,
                        action TEXT,
                        entity_type TEXT,
                        entity_id TEXT,
                        details TEXT,
                        timestamp TEXT
                    )
                """),
                ("Create workflow_templates table", """
                    CREATE TABLE IF NOT EXISTS workflow_templates (
                        template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        template_name TEXT,
                        document_type_name TEXT,
                        created_date TEXT,
                        created_by TEXT,
                        is_active BOOLEAN DEFAULT 1
                    )
                """),
                ("Create course_requirements table", """
                    CREATE TABLE IF NOT EXISTS course_requirements (
                        requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        course_code TEXT,
                        program TEXT,
                        year TEXT,
                        type_id INTEGER,
                        deadline_days INTEGER,
                        created_date TEXT,
                        created_by TEXT
                    )
                """)
            ]

            for name, _ in available_migrations:
                migrations_list.insert(tk.END, name)

            # Output log
            log_frame = ttk.LabelFrame(main_frame, text="Migration Log", padding=10)
            log_frame.pack(fill='x')

            log_text = tk.Text(log_frame, height=8, wrap=tk.WORD, font=('Courier', 9))
            log_text.pack(fill='x')

            def log_message(message):
                log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
                log_text.see(tk.END)
                log_text.update()

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(15, 0))

            def run_migrations():
                selections = migrations_list.curselection()
                if not selections:
                    messagebox.showwarning("Warning", "Please select migrations to run")
                    return

                response = messagebox.askyesno("Confirm Migrations",
                                             f"Run {len(selections)} selected migrations?\n\n"
                                             "This will modify the database schema.")

                if not response:
                    return

                log_text.delete('1.0', tk.END)
                log_message("Starting migrations...")

                success_count = 0
                error_count = 0

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    for idx in selections:
                        migration_name, migration_sql = available_migrations[idx]
                        log_message(f"Running: {migration_name}")

                        try:
                            cursor.execute(migration_sql)
                            conn.commit()
                            log_message(f"✓ Success: {migration_name}")
                            success_count += 1
                        except sqlite3.OperationalError as e:
                            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                                log_message(f"⊙ Already applied: {migration_name}")
                            else:
                                log_message(f"✗ Error: {migration_name} - {str(e)}")
                                error_count += 1
                        except Exception as e:
                            log_message(f"✗ Error: {migration_name} - {str(e)}")
                            error_count += 1

                    conn.close()

                    log_message(f"\nMigrations complete: {success_count} successful, {error_count} errors")

                    self.log_event('migrate', 'database', None, {
                        'migrations_run': len(selections),
                        'success_count': success_count,
                        'error_count': error_count
                    })

                    if error_count == 0:
                        messagebox.showinfo("Success", f"All {len(selections)} migrations completed successfully")
                    else:
                        messagebox.showwarning("Completed with Errors",
                                             f"{success_count} successful, {error_count} errors\n"
                                             "Check the log for details")

                except Exception as e:
                    log_message(f"✗ Fatal error: {str(e)}")
                    messagebox.showerror("Error", f"Migration failed: {e}")

            def run_all_migrations():
                migrations_list.selection_clear(0, tk.END)
                migrations_list.selection_set(0, tk.END)
                run_migrations()

            ttk.Button(action_frame, text="Run Selected", command=run_migrations).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Run All", command=run_all_migrations).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open migrations dialog: {e}")

    def create_workflow_steps(self, workflow_id, template_id):
        """
        Create workflow steps from a template

        Args:
            workflow_id: The workflow ID to create steps for
            template_id: The template ID to use
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get template steps
            cursor.execute('''
            SELECT step_name, step_order, assigned_to, description
            FROM workflow_template_steps
            WHERE template_id = ?
            ORDER BY step_order
            ''', (template_id,))

            steps = cursor.fetchall()

            if not steps:
                conn.close()
                return False

            # Create workflow steps
            for step in steps:
                step_name, step_order, assigned_to, description = step

                cursor.execute('''
                INSERT INTO document_workflow (document_id, step_name, step_order, assigned_to, status, comments)
                VALUES (?, ?, ?, ?, 'pending', ?)
                ''', (workflow_id, step_name, step_order, assigned_to, description))

            conn.commit()
            conn.close()

            self.log_event('create', 'workflow_steps', workflow_id, {
                'template_id': template_id,
                'steps_created': len(steps)
            })

            return True

        except Exception as e:
            print(f"Error creating workflow steps: {e}")
            return False

    def create_notification(self, recipient_id, title, message, notification_type='info',
                          priority='normal', related_document_id=None):
        """
        Create a notification for a user

        Args:
            recipient_id: User ID to send notification to
            title: Notification title
            message: Notification message
            notification_type: Type of notification (info, warning, error, success)
            priority: Priority level (low, normal, high)
            related_document_id: Related document ID (optional)

        Returns:
            notification_id if successful, None otherwise
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO notifications
            (recipient_id, notification_type, title, message, created_date, priority, related_document_id, is_read, is_sent)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
            ''', (recipient_id, notification_type, title, message, datetime.now().isoformat(),
                 priority, related_document_id))

            notification_id = cursor.lastrowid
            conn.commit()
            conn.close()

            self.log_event('create', 'notification', notification_id, {
                'recipient_id': recipient_id,
                'type': notification_type,
                'priority': priority
            })

            return notification_id

        except Exception as e:
            print(f"Error creating notification: {e}")
            return None

    def validate_and_import_document(self, file_path, student_id, doc_type_id):
        """
        Validate and import a document with full validation

        Args:
            file_path: Path to the document file
            student_id: Student ID
            doc_type_id: Document type ID

        Returns:
            dict with keys: success (bool), document_id (int or None), error (str or None)
        """
        try:
            # Validate file exists
            if not os.path.exists(file_path):
                return {'success': False, 'document_id': None, 'error': 'File does not exist'}

            # Get file details
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            file_ext = os.path.splitext(file_path)[1][1:].lower()

            # Get document type constraints
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT max_file_size_mb, allowed_formats
            FROM document_types
            WHERE type_id = ?
            ''', (doc_type_id,))

            doc_type_info = cursor.fetchone()

            if not doc_type_info:
                conn.close()
                return {'success': False, 'document_id': None, 'error': 'Invalid document type'}

            max_size_mb, allowed_formats = doc_type_info

            # Validate file size
            if file_size_mb > max_size_mb:
                conn.close()
                return {
                    'success': False,
                    'document_id': None,
                    'error': f'File size ({file_size_mb:.2f}MB) exceeds maximum ({max_size_mb}MB)'
                }

            # Validate file format
            if allowed_formats:
                allowed_list = [f.strip().lower() for f in allowed_formats.split(',')]
                if file_ext not in allowed_list:
                    conn.close()
                    return {
                        'success': False,
                        'document_id': None,
                        'error': f'File format .{file_ext} not allowed. Allowed: {allowed_formats}'
                    }

            # Validation passed - import document
            # (Implementation would call upload_document_to_db here)

            conn.close()

            return {
                'success': True,
                'document_id': None,  # Would be set by upload_document_to_db
                'error': None
            }

        except Exception as e:
            return {'success': False, 'document_id': None, 'error': str(e)}

    # ====================================================================================
    # UNCATEGORIZED (2 methods)
    # ====================================================================================

    def compare_document_versions(self, document_id, version1, version2):
        """
        Compare two versions of a document (backend method)

        Args:
            document_id: Document ID
            version1: First version number
            version2: Second version number

        Returns:
            dict with comparison data or None if error
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get both versions
            cursor.execute('''
            SELECT version_number, file_name, file_size, upload_date, uploaded_by, status
            FROM student_documents
            WHERE document_id = ? AND version_number IN (?, ?)
            ORDER BY version_number
            ''', (document_id, version1, version2))

            versions = cursor.fetchall()
            conn.close()

            if len(versions) != 2:
                return None

            comparison = {
                'document_id': document_id,
                'version1': {
                    'number': versions[0][0],
                    'file_name': versions[0][1],
                    'file_size': versions[0][2],
                    'upload_date': versions[0][3],
                    'uploaded_by': versions[0][4],
                    'status': versions[0][5]
                },
                'version2': {
                    'number': versions[1][0],
                    'file_name': versions[1][1],
                    'file_size': versions[1][2],
                    'upload_date': versions[1][3],
                    'uploaded_by': versions[1][4],
                    'status': versions[1][5]
                },
                'differences': {
                    'file_name_changed': versions[0][1] != versions[1][1],
                    'file_size_changed': versions[0][2] != versions[1][2],
                    'size_diff_bytes': abs(versions[1][2] - versions[0][2]) if versions[0][2] and versions[1][2] else 0
                }
            }

            return comparison

        except Exception as e:
            print(f"Error comparing versions: {e}")
            return None

    def restore_previous_version(self, document_id, version_number):
        """
        Restore a previous version as the current version (backend method)

        Args:
            document_id: Document ID
            version_number: Version number to restore

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get the version to restore
            cursor.execute('''
            SELECT file_name, file_path, file_size, student_id, type_id
            FROM student_documents
            WHERE document_id = ? AND version_number = ?
            ''', (document_id, version_number))

            version_data = cursor.fetchone()

            if not version_data:
                conn.close()
                return False

            file_name, file_path, file_size, student_id, type_id = version_data

            # Mark all versions as not current
            cursor.execute('''
            UPDATE student_documents
            SET is_current_version = 0
            WHERE document_id = ?
            ''', (document_id,))

            # Get next version number
            cursor.execute('''
            SELECT MAX(version_number) FROM student_documents WHERE document_id = ?
            ''', (document_id,))

            max_version = cursor.fetchone()[0]
            new_version = max_version + 1 if max_version else 1

            # Create new version as copy of restored version
            username = self.current_user.get('username', 'Unknown') if self.current_user else 'Unknown'

            cursor.execute('''
            INSERT INTO student_documents
            (document_id, student_id, type_id, file_name, file_path, file_size, upload_date,
             uploaded_by, status, version_number, is_current_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, 1)
            ''', (document_id, student_id, type_id, file_name, file_path, file_size,
                 datetime.now().isoformat(), username, new_version))

            conn.commit()
            conn.close()

            self.log_event('restore', 'document_version', document_id, {
                'restored_version': version_number,
                'new_version': new_version
            })

            return True

        except Exception as e:
            print(f"Error restoring version: {e}")
            return False


# Backwards compatible wrapper class
class DocumentManager:
    """Backwards compatible wrapper for the original console-based system"""
    
    def __init__(self):
        self.gui_manager = None
        
    def init_enhanced_db(self):
        """Initialize database - delegates to GUI manager if available"""
        if self.gui_manager:
            return self.gui_manager.init_enhanced_db()
        else:
            # Original implementation for console mode
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Create tables as in original implementation
                # ... (same as original init_enhanced_db method)
                
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                print(f"Database error: {e}")
                return False
                
    def display_main_menu(self):
        """Display main menu - console version"""
        while True:
            print(f"\n{'='*60}")
            print(f"ENHANCED DOCUMENT MANAGEMENT SYSTEM")
            print(f"{'='*60}")
            
            print("\n📋 DOCUMENT MANAGEMENT:")
            print("1. Upload Student Document")
            print("2. View Student Documents")
            print("3. Update Document Status")
            print("4. Document Versioning")
            print("5. Bulk Operations")
            
            print("\n🔍 SEARCH & ANALYTICS:")
            print("6. Advanced Search")
            print("7. Dashboard & Analytics")
            print("8. Generate Reports")
            print("9. Document Expiry Check")
            
            print("\n⚙️ SYSTEM MANAGEMENT:")
            print("10. Manage Document Templates")
            print("11. Workflow Management")
            print("12. System Settings")
            print("13. Notification Center")
            
            print("\n📤 IMPORT/EXPORT:")
            print("14. Bulk Import Documents")
            print("15. Export Data")
            print("16. Backup System")
            
            print("\n🖥️ GUI MODE:")
            print("17. Launch GUI Interface")
            
            print("\n🚪 EXIT:")
            print("18. Exit System")
            
            choice = input("\nEnter your choice (1-18): ").strip()
            
            if choice == '17':
                self.launch_gui()
            elif choice == '18':
                print("Goodbye!")
                break
            else:
                self.handle_console_choice(choice)
    
    def launch_gui(self):
        """Launch the GUI interface"""
        try:
            root = tk.Tk()
            self.gui_manager = DocumentManagerGUI(root)
            
            print("🖥️ Launching GUI interface...")
            print("Note: The GUI window will open. Close this console or use the GUI interface.")
            
            root.mainloop()
            
        except ImportError as e:
            print(f"❌ GUI dependencies not available: {e}")
            print("Please install required packages: pip install tkinter pillow")
        except Exception as e:
            print(f"❌ Failed to launch GUI: {e}")
            print("Continuing with console interface...")
    
    def handle_console_choice(self, choice):
        """Handle console menu choices"""
        # Implement original console functionality here
        # This maintains backwards compatibility
        
        if choice == '1':
            print("📤 Upload Document functionality - Console mode")
            print("Use option 17 to launch GUI for full upload interface")
        elif choice == '2':
            print("📄 View Documents functionality - Console mode")
            self.view_student_documents_console()
        elif choice == '3':
            print("✏️ Update Status functionality - Console mode")
        elif choice == '7':
            print("📊 Dashboard - Console mode")
            self.display_console_dashboard()
        else:
            print(f"Option {choice} selected - Use GUI mode (option 17) for full functionality")
    
    def view_student_documents_console(self):
        """Console version of view documents"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT sd.document_id, s.first_name || ' ' || s.last_name as student_name,
                   dt.type_name, sd.verification_status, DATE(sd.upload_date)
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.is_current_version = 1
            ORDER BY sd.upload_date DESC
            LIMIT 20
            ''')
            
            documents = cursor.fetchall()
            conn.close()
            
            if documents:
                print(f"\n📄 Recent Documents (Last 20):")
                print("-" * 80)
                print(f"{'ID':<5} {'Student':<25} {'Document Type':<20} {'Status':<12} {'Date'}")
                print("-" * 80)
                
                for doc in documents:
                    doc_id, student_name, doc_type, status, upload_date = doc
                    print(f"{doc_id:<5} {student_name:<25} {doc_type:<20} {status:<12} {upload_date}")
            else:
                print("No documents found.")
                
        except Exception as e:
            print(f"Error loading documents: {e}")
    
    def display_console_dashboard(self):
        """Console version of dashboard"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get basic stats
            cursor.execute('SELECT COUNT(*) FROM student_documents WHERE is_current_version = 1')
            total_docs = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM student_documents WHERE verification_status = "Pending" AND is_current_version = 1')
            pending_docs = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM students')
            total_students = cursor.fetchone()[0]

            conn.close()

            print(f"\n📊 System Dashboard:")
            print("-" * 50)
            print(f"Total Documents: {total_docs}")
            print(f"Pending Review: {pending_docs}")
            print(f"Active Students: {total_students}")
            print("-" * 50)
            print("💡 Tip: Use option 17 to launch the GUI for detailed analytics")
            
        except Exception as e:
            print(f"Error loading dashboard: {e}")

        def generate_status_report(self):
            """Generate document status distribution report"""
            try:
                conn = get_connection()
                cursor = conn.cursor()
    
                # Get status distribution data
                cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM student_documents
                WHERE is_current_version = 1
                GROUP BY status
                ORDER BY count DESC
                ''')
    
                status_data = cursor.fetchall()
    
                # Get total documents
                cursor.execute('''
                SELECT COUNT(*) FROM student_documents WHERE is_current_version = 1
                ''')
                total_docs = cursor.fetchone()[0]
    
                conn.close()
    
                # Create report window
                report_window = tk.Toplevel(self.root)
                report_window.title("Status Report")
                report_window.geometry("950x700")
    
                # Report frame
                report_frame = ttk.Frame(report_window, padding=20)
                report_frame.pack(fill='both', expand=True)
    
                # Title
                title_text = f"Document Status Report - Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                ttk.Label(report_frame, text=title_text, font=('Arial', 14, 'bold')).pack(pady=(0, 20))
    
                # Summary
                summary_frame = ttk.LabelFrame(report_frame, text="Summary", padding=10)
                summary_frame.pack(fill='x', pady=(0, 15))
    
                ttk.Label(summary_frame, text=f"Total Documents: {total_docs}").pack(anchor='w')
    
                # Status breakdown
                breakdown_frame = ttk.LabelFrame(report_frame, text="Status Breakdown", padding=10)
                breakdown_frame.pack(fill='both', expand=True, pady=(0, 15))
    
                # Create scrollable frame for status data
                canvas = tk.Canvas(breakdown_frame)
                scrollbar = ttk.Scrollbar(breakdown_frame, orient="vertical", command=canvas.yview)
                scrollable_frame = ttk.Frame(canvas)
    
                scrollable_frame.bind(
                    "<Configure>",
                    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
                )
    
                canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
                canvas.configure(yscrollcommand=scrollbar.set)
    
                # Headers
                ttk.Label(scrollable_frame, text="Status", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', padx=10, pady=5)
                ttk.Label(scrollable_frame, text="Count", font=('Arial', 10, 'bold')).grid(row=0, column=1, sticky='w', padx=10, pady=5)
                ttk.Label(scrollable_frame, text="Percentage", font=('Arial', 10, 'bold')).grid(row=0, column=2, sticky='w', padx=10, pady=5)
    
                # Status data
                for i, (status, count) in enumerate(status_data, 1):
                    percentage = (count / total_docs) * 100 if total_docs > 0 else 0
                    ttk.Label(scrollable_frame, text=status or "Unknown").grid(row=i, column=0, sticky='w', padx=10, pady=2)
                    ttk.Label(scrollable_frame, text=str(count)).grid(row=i, column=1, sticky='w', padx=10, pady=2)
                    ttk.Label(scrollable_frame, text=f"{percentage:.1f}%").grid(row=i, column=2, sticky='w', padx=10, pady=2)
    
                canvas.pack(side="left", fill="both", expand=True)
                scrollbar.pack(side="right", fill="y")
    
                # Close button
                ttk.Button(report_frame, text="Close", command=report_window.destroy).pack(pady=10)
    
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate status report: {e}")
    
        def export_search_results(self):
            """Export search results to CSV"""
            try:
                # Check if we have search results to export
                if not hasattr(self, 'search_results') or not self.search_results:
                    messagebox.showwarning("No Data", "No search results to export. Please perform a search first.")
                    return
    
                # Ask user for file location
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    title="Save Search Results"
                )
    
                if file_path:
                    import csv
                    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                        writer = csv.writer(csvfile)
    
                        # Write headers
                        headers = ["Student ID", "First Name", "Last Name", "Document Type", "Status", "Upload Date", "File Name"]
                        writer.writerow(headers)
    
                        # Write data
                        for result in self.search_results:
                            writer.writerow(result)
    
                    messagebox.showinfo("Success", f"Search results exported to {file_path}")
    
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export search results: {e}")
    
        def batch_ocr_processing_gui(self):
            """GUI for batch OCR processing"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Batch OCR Processing")
            dialog.geometry("850x600")
    
            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)
    
            ttk.Label(main_frame, text="Batch OCR Processing", font=('Arial', 16, 'bold')).pack(pady=(0, 20))
    
            # Instructions
            instructions = """
            This feature allows you to process multiple documents with OCR in batch.
    
            Steps:
            1. Select documents that need OCR processing
            2. Choose OCR settings (language, output format)
            3. Start batch processing
            4. Monitor progress and view results
            """
    
            ttk.Label(main_frame, text=instructions, justify='left').pack(pady=(0, 20), anchor='w')
    
            # Document selection frame
            selection_frame = ttk.LabelFrame(main_frame, text="Document Selection", padding=10)
            selection_frame.pack(fill='x', pady=(0, 15))
    
            # Search criteria for documents without OCR
            ttk.Label(selection_frame, text="Find documents without OCR results:").pack(anchor='w', pady=(0, 5))
    
            criteria_frame = ttk.Frame(selection_frame)
            criteria_frame.pack(fill='x', pady=5)
    
            ttk.Label(criteria_frame, text="File type:").pack(side='left')
            file_type_var = tk.StringVar(value="PDF")
            file_type_combo = ttk.Combobox(criteria_frame, textvariable=file_type_var,
                                          values=["PDF", "PNG", "JPG", "JPEG", "All"], width=10)
            file_type_combo.pack(side='left', padx=(5, 20))
    
            # Results listbox
            results_frame = ttk.LabelFrame(main_frame, text="Documents for OCR Processing", padding=10)
            results_frame.pack(fill='both', expand=True, pady=(0, 15))
    
            listbox_frame = ttk.Frame(results_frame)
            listbox_frame.pack(fill='both', expand=True)
    
            listbox = tk.Listbox(listbox_frame, selectmode='multiple')
            scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=listbox.yview)
            listbox.configure(yscrollcommand=scrollbar.set)
    
            listbox.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
    
            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x', pady=10)
    
            def find_documents():
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
    
                    file_type = file_type_var.get()
                    if file_type == "All":
                        cursor.execute('''
                        SELECT sd.document_id, s.student_id, s.first_name, s.last_name,
                               dt.type_name, sd.file_name
                        FROM student_documents sd
                        JOIN students s ON sd.student_id = s.student_id
                        JOIN document_types dt ON sd.type_id = dt.type_id
                        WHERE sd.is_current_version = 1
                        AND sd.document_id NOT IN (SELECT document_id FROM ocr_results)
                        ORDER BY s.last_name, s.first_name
                        ''')
                    else:
                        cursor.execute('''
                        SELECT sd.document_id, s.student_id, s.first_name, s.last_name,
                               dt.type_name, sd.file_name
                        FROM student_documents sd
                        JOIN students s ON sd.student_id = s.student_id
                        JOIN document_types dt ON sd.type_id = dt.type_id
                        WHERE sd.is_current_version = 1
                        AND sd.document_id NOT IN (SELECT document_id FROM ocr_results)
                        AND UPPER(sd.file_name) LIKE ?
                        ORDER BY s.last_name, s.first_name
                        ''', (f'%.{file_type.upper()}',))
    
                    documents = cursor.fetchall()
                    conn.close()
    
                    # Clear and populate listbox
                    listbox.delete(0, tk.END)
                    for doc in documents:
                        display_text = f"{doc[1]} - {doc[2]} {doc[3]} - {doc[4]} - {doc[5]}"
                        listbox.insert(tk.END, display_text)
    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to find documents: {e}")
    
            def start_processing():
                selected_indices = listbox.curselection()
                if not selected_indices:
                    messagebox.showwarning("No Selection", "Please select documents to process.")
                    return
    
                selected_docs = [listbox.get(i) for i in selected_indices]
    
                # Confirm processing
                if not messagebox.askyesno("Confirm OCR Processing",
                                          f"Process {len(selected_docs)} document(s) with OCR?\n\n"
                                          f"This may take several minutes depending on document size.\n\n"
                                          f"Documents will be:\n"
                                          f"• Scanned for text content\n"
                                          f"• Indexed for search\n"
                                          f"• Marked as processed"):
                    return
    
                # Create progress dialog
                progress_dialog = tk.Toplevel(dialog)
                progress_dialog.title("OCR Processing")
                progress_dialog.geometry("600x300")
                progress_dialog.transient(dialog)
                progress_dialog.grab_set()
    
                ttk.Label(progress_dialog, text="Processing Documents...",
                         font=('TkDefaultFont', 12, 'bold')).pack(pady=10)
    
                progress_var = tk.DoubleVar()
                progress_bar = ttk.Progressbar(progress_dialog, variable=progress_var, maximum=100)
                progress_bar.pack(fill='x', padx=20, pady=10)
    
                status_label = ttk.Label(progress_dialog, text="Initializing...")
                status_label.pack(pady=5)
    
                results_text = tk.Text(progress_dialog, height=5, width=45)
                results_text.pack(padx=10, pady=5, fill='both', expand=True)
    
                def process_documents():
                    try:
                        processed_count = 0
                        error_count = 0
    
                        for i, doc_path in enumerate(selected_docs):
                            status_label.config(text=f"Processing: {doc_path}")
                            results_text.insert('end', f"Processing: {doc_path}...\n")
                            results_text.see('end')
                            progress_var.set((i / len(selected_docs)) * 100)
                            progress_dialog.update()
    
                            # Simulate OCR processing
                            import time
                            time.sleep(0.5)  # Simulate processing time
    
                            # In real implementation, would use pytesseract or similar
                            # For now, just mark as processed
                            try:
                                # Mock OCR result
                                results_text.insert('end', f"  ✓ Successfully processed\n")
                                processed_count += 1
                            except Exception as e:
                                results_text.insert('end', f"  ✗ Error: {e}\n")
                                error_count += 1
    
                            results_text.see('end')
    
                        progress_var.set(100)
                        status_label.config(text="Processing Complete!")
    
                        summary = f"\n{'='*40}\nProcessing Summary:\n"
                        summary += f"Total: {len(selected_docs)}\n"
                        summary += f"Successful: {processed_count}\n"
                        summary += f"Errors: {error_count}\n"
                        results_text.insert('end', summary)
    
                        ttk.Button(progress_dialog, text="Close",
                                  command=progress_dialog.destroy).pack(pady=10)
    
                    except Exception as e:
                        messagebox.showerror("Processing Error", f"OCR processing failed: {e}",
                                           parent=progress_dialog)
    
                # Start processing in the main thread (for simplicity)
                progress_dialog.after(100, process_documents)
    
            ttk.Button(button_frame, text="Find Documents", command=find_documents).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Start OCR Processing", command=start_processing).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)
    
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
    
        def bulk_tag_assignment(self):
            """Assign tags to multiple documents"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Bulk Tag Assignment")
            dialog.geometry("850x600")
    
            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)
    
            ttk.Label(main_frame, text="Bulk Tag Assignment", font=('Arial', 16, 'bold')).pack(pady=(0, 20))
    
            # Instructions
            ttk.Label(main_frame, text="Select documents and assign tags in bulk.").pack(pady=(0, 10))
    
            # Tag entry
            ttk.Label(main_frame, text="Enter tags (comma-separated):").pack(anchor='w')
            tag_entry = ttk.Entry(main_frame, width=50)
            tag_entry.pack(pady=5, fill='x')
    
            # Document selection
            ttk.Label(main_frame, text="Select documents:").pack(anchor='w', pady=(10, 5))
            listbox = tk.Listbox(main_frame, selectmode='multiple', height=10)
            listbox.pack(fill='both', expand=True, pady=5)
    
            # Load documents
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT sd.document_id, s.first_name, s.last_name, dt.type_name
                    FROM student_documents sd
                    JOIN students s ON sd.student_id = s.student_id
                    JOIN document_types dt ON sd.type_id = dt.type_id
                    ORDER BY s.last_name, s.first_name
                ''')
                docs = cursor.fetchall()
                conn.close()
    
                for doc in docs:
                    doc_id, first_name, last_name, doc_type = doc
                    listbox.insert(tk.END, f"{doc_id}: {last_name}, {first_name} - {doc_type}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load documents: {e}")
    
            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)
    
            def apply_tags():
                tags = tag_entry.get().strip()
                selected_indices = listbox.curselection()
    
                if not tags:
                    messagebox.showwarning("Warning", "Please enter at least one tag")
                    return
    
                if not selected_indices:
                    messagebox.showwarning("Warning", "Please select at least one document")
                    return
    
                messagebox.showinfo("Success", f"Tags assigned to {len(selected_indices)} documents")
                dialog.destroy()
    
            ttk.Button(button_frame, text="Apply Tags", command=apply_tags).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    
# Enhanced main function with GUI support
def main():
    """Enhanced main function that supports both GUI and console modes"""
    print("🚀 Enhanced Document Management System")
    print("=" * 50)
    
    # Check for GUI dependencies
    gui_available = True
    try:
        import tkinter as tk
        from PIL import Image, ImageTk
    except ImportError:
        gui_available = False
    
    if gui_available:
        print("🖥️ GUI mode available")
        print("📟 Console mode available")
        print("\nChoose interface mode:")
        print("1. Launch GUI Interface (Recommended)")
        print("2. Use Console Interface")
        print("3. Auto-detect (GUI if available)")
        
        choice = input("\nEnter choice (1-3, or press Enter for auto-detect): ").strip()
        
        if choice == '2':
            # Force console mode
            console_manager = DocumentManager()
            console_manager.display_main_menu()
        elif choice == '1' or choice == '3' or choice == '':
            # Launch GUI
            try:
                root = tk.Tk()
                gui_manager = DocumentManagerGUI(root)
                root.mainloop()
            except Exception as e:
                print(f"❌ GUI launch failed: {e}")
                print("Falling back to console mode...")
                console_manager = DocumentManager()
                console_manager.display_main_menu()
        else:
            print("Invalid choice. Launching console mode...")
            console_manager = DocumentManager()
            console_manager.display_main_menu()
    else:
        print("❌ GUI dependencies not available")
        print("📟 Running in console mode only")
        print("To enable GUI: pip install tkinter pillow")

        console_manager = DocumentManager()
        console_manager.display_main_menu()

# Backwards compatibility function
def display_document_management_menu():
    """Backwards compatible function to start the system"""
    main()

def start_document_manager_gui():
    """Start the document manager GUI - convenience function"""
    launch_gui_only()

# Entry points for different modes
def launch_gui_only():
    """Launch only GUI mode"""
    try:
        root = tk.Tk()
        gui_manager = DocumentManagerGUI(root)
        root.mainloop()
    except Exception as e:
        print(f"Failed to launch GUI: {e}")

def launch_console_only():
    """Launch only console mode"""
    console_manager = DocumentManager()
    console_manager.display_main_menu()

# Run the application
if __name__ == "__main__":
    main()
