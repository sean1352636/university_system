from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.modules.shared.constants import paths
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from datetime import datetime, timedelta
from university_system.infrastructure.database.db import sqlite3
import csv
import json
import os
import threading
import logging
from cryptography.fernet import Fernet
from typing import Optional, List, Dict, Any

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Try to import the enhanced database initializer from the CLI version. If
# present, this will allow the GUI to create the full health portal schema.
try:
    from university_system.modules.domain.health.services.health_portal import init_enhanced_health_db
except ImportError:
    init_enhanced_health_db = None

class HealthPortalGUI:
    def __init__(self, root, auth_system=None):
        self.root = root
        self.root.title("Enhanced University Health Portal")
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')

        # Initialize authentication - use provided auth system or create new one
        if auth_system:
            self.auth = auth_system
        else:
            self.auth = UserAuth()
        
        # Initialize encryption
        self.encryption_key = self.get_or_create_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)
        
        # Setup logging
        self.setup_logging()
        
        # Initialize database
        self.init_database()
        
        # Configure styles
        self.setup_styles()

        # Setup current user from existing authentication system
        self.setup_current_user()

        # Show appropriate interface based on authentication status
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            self.create_main_interface()
        else:
            self.show_login_screen()

    def setup_current_user(self):
        """Setup current user from existing authentication system"""
        try:
            # Check if auth system has a current authenticated user
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                # The existing auth system is already compatible, just ensure it's properly set
                print(f"✓ Health Portal GUI: Using authenticated user {self.auth.current_user.get('username', 'Unknown')} ({self.auth.current_user.get('role', 'user')})")
            else:
                print("ℹ Health Portal GUI: No authenticated user - will show login screen")
        except Exception as e:
            print(f"✗ Error setting up current user: {e}")

    def get_or_create_encryption_key(self):
        """Get or create a valid Fernet key for sensitive data."""
        key_file = str(paths.DATA_DIR / 'health_encryption.key')

        # 1) Prefer existing file
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                key = f.read().strip()
            try:
                # This validates format (32 url-safe base64-encoded bytes)
                Fernet(key)
                return key
            except Exception:
                pass  # fall through to regenerate

        # 2) Regenerate a good key
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        return key

    def setup_logging(self):
        """Configure logging for audit trail"""
        log_dir = str(paths.LOG_DIR)
        # Directory is automatically created by paths module via _ensure()
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, "health_portal_audit.log")),
                logging.StreamHandler()
            ]
        )
        self.audit_logger = logging.getLogger('health_audit')
    
    def log_audit_event(self, action, resource_type, resource_id, details=None):
        """Log audit events for compliance"""
        if self.auth.current_user:
            self.audit_logger.info(f"USER:{self.auth.current_user['id']} ACTION:{action} RESOURCE:{resource_type}:{resource_id} DETAILS:{details}")
    
    def encrypt_sensitive_data(self, data):
        """Encrypt sensitive health data"""
        if data is None:
            return None
        return self.cipher_suite.encrypt(str(data).encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data):
        """Decrypt sensitive health data"""
        if encrypted_data is None:
            return None
        try:
            return self.cipher_suite.decrypt(encrypted_data.encode()).decode()
        except:
            return encrypted_data
    
    def get_connection(self):
        """Get database connection using the centralized student_records.db path"""
        try:
            # Prefer the central database connection from university_system.infrastructure.database.db
            from university_system.infrastructure.database.db import get_connection as central_get_connection
            return central_get_connection()
        except Exception:
            # Fallback: use centralized path system
            from university_system.modules.shared.constants import paths
            return sqlite3.connect(str(paths.DEFAULT_DB_PATH))
    
    def init_database(self):
        """Initialize the database with all required tables"""
        try:
            # Call the enhanced initializer if available. To ensure the CLI
            # initializer writes to the same database file used by this GUI,
            # temporarily override the refactored.database.db.DEFAULT_DB_PATH.
            if init_enhanced_health_db:
                try:
                    import university_system.infrastructure.database.db as _db_module
                    from pathlib import Path
                    _old_db_path = getattr(_db_module, 'DEFAULT_DB_PATH', None)
                    # Use centralized path configuration
                    _db_module.DEFAULT_DB_PATH = str(paths.DEFAULT_DB_PATH)
                    init_enhanced_health_db()
                    # Restore original path
                    if _old_db_path is not None:
                        _db_module.DEFAULT_DB_PATH = _old_db_path
                except Exception as e:
                    print(f"Warning: failed to initialize enhanced health DB: {e}")

            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Create students table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    first_name TEXT,
                    last_name TEXT,
                    age INTEGER,
                    gender TEXT,
                    email TEXT,
                    phone TEXT
                )
            ''')
            
            # Create health records table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS health_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    record_type TEXT,
                    record_date TEXT,
                    description TEXT,
                    provider TEXT,
                    confidential INTEGER DEFAULT 0,
                    created_at TEXT,
                    encrypted_data TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')
            
            # Create vaccination records table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vaccination_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    vaccine_name TEXT,
                    administered_date TEXT,
                    expiry_date TEXT,
                    lot_number TEXT,
                    manufacturer TEXT,
                    administered_by TEXT,
                    location TEXT,
                    adverse_reaction INTEGER DEFAULT 0,
                    reaction_description TEXT,
                    verified INTEGER DEFAULT 0,
                    verified_by TEXT,
                    verified_date TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')
            
            # Create appointments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS health_appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    appointment_type TEXT,
                    appointment_date TEXT,
                    appointment_time TEXT,
                    provider TEXT,
                    reason TEXT,
                    status TEXT DEFAULT 'scheduled',
                    notes TEXT,
                    scheduled_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')
            
            # Create allergies table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS allergies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    allergen TEXT,
                    severity TEXT,
                    reaction_description TEXT,
                    diagnosed_date TEXT,
                    provider TEXT,
                    verified INTEGER DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')
            
            # Create prescriptions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS prescriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    medication_name TEXT,
                    dosage TEXT,
                    frequency TEXT,
                    prescribed_date TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    prescriber TEXT,
                    pharmacy TEXT,
                    status TEXT DEFAULT 'active',
                    notes TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')
            
            # Create vital signs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vital_signs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    measurement_date TEXT,
                    blood_pressure_systolic INTEGER,
                    blood_pressure_diastolic INTEGER,
                    heart_rate INTEGER,
                    temperature REAL,
                    weight REAL,
                    height REAL,
                    bmi REAL,
                    recorded_by TEXT,
                    notes TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')
            
            # Create audit trail table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_trail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    action TEXT,
                    resource_type TEXT,
                    resource_id TEXT,
                    old_values TEXT,
                    new_values TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    timestamp TEXT,
                    session_id TEXT
                )
            ''')

            # ------------------------------------------------------------------
            # Additional tables for enhanced health portal features
            # These mirror the structures in the CLI version of the health portal
            # and are created here to ensure the GUI functions independently of
            # the CLI. If the CLI initializer runs, these statements are
            # harmless due to the IF NOT EXISTS clauses.

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS medical_conditions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    condition_name TEXT,
                    icd_code TEXT,
                    severity TEXT,
                    diagnosed_date TEXT,
                    status TEXT DEFAULT 'active',
                    provider TEXT,
                    notes TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS care_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    condition_id INTEGER,
                    plan_name TEXT,
                    description TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    provider TEXT,
                    status TEXT DEFAULT 'active',
                    goals TEXT,
                    interventions TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (condition_id) REFERENCES medical_conditions (id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    referring_provider TEXT,
                    specialist_provider TEXT,
                    specialty TEXT,
                    reason TEXT,
                    urgency TEXT,
                    referral_date TEXT,
                    appointment_date TEXT,
                    status TEXT DEFAULT 'pending',
                    notes TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS health_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT,
                    metric_value REAL,
                    measurement_date TEXT,
                    category TEXT,
                    subcategory TEXT,
                    metadata TEXT,
                    calculated_at TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS screening_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    screening_type TEXT,
                    due_date TEXT,
                    completed_date TEXT,
                    status TEXT DEFAULT 'due',
                    provider TEXT,
                    results TEXT,
                    next_due_date TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS risk_assessments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    assessment_type TEXT,
                    risk_score INTEGER,
                    risk_factors TEXT,
                    recommendations TEXT,
                    assessed_date TEXT,
                    assessed_by TEXT,
                    follow_up_date TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS emergency_contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    contact_name TEXT,
                    relationship TEXT,
                    phone_primary TEXT,
                    phone_secondary TEXT,
                    email TEXT,
                    address TEXT,
                    priority_order INTEGER,
                    medical_decision_maker INTEGER DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS provider_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_name TEXT,
                    day_of_week INTEGER,
                    start_time TEXT,
                    end_time TEXT,
                    max_appointments INTEGER DEFAULT 10,
                    specialty TEXT,
                    location TEXT,
                    active INTEGER DEFAULT 1,
                    created_at TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS health_campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_name TEXT,
                    campaign_type TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    target_population TEXT,
                    description TEXT,
                    goals TEXT,
                    status TEXT DEFAULT 'planned',
                    budget REAL,
                    created_by TEXT,
                    created_at TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wellness_participation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    program_name TEXT,
                    enrollment_date TEXT,
                    completion_date TEXT,
                    status TEXT DEFAULT 'enrolled',
                    progress_score INTEGER DEFAULT 0,
                    goals_met INTEGER DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS disease_surveillance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    disease_name TEXT,
                    case_date TEXT,
                    student_id TEXT,
                    symptoms TEXT,
                    severity TEXT,
                    status TEXT DEFAULT 'under_investigation',
                    contact_tracing_needed INTEGER DEFAULT 0,
                    contact_tracing_completed INTEGER DEFAULT 0,
                    contacts_identified INTEGER DEFAULT 0,
                    reported_to_health_dept INTEGER DEFAULT 0,
                    isolation_required INTEGER DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS lab_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    test_name TEXT,
                    test_code TEXT,
                    result_value TEXT,
                    reference_range TEXT,
                    units TEXT,
                    status TEXT,
                    ordered_date TEXT,
                    collected_date TEXT,
                    resulted_date TEXT,
                    ordering_provider TEXT,
                    lab_name TEXT,
                    abnormal_flag TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS quality_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT,
                    metric_category TEXT,
                    target_value REAL,
                    actual_value REAL,
                    measurement_period TEXT,
                    measured_date TEXT,
                    status TEXT,
                    improvement_needed INTEGER DEFAULT 0,
                    created_at TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS data_retention_policies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_type TEXT,
                    retention_period_days INTEGER,
                    auto_archive INTEGER DEFAULT 0,
                    auto_delete INTEGER DEFAULT 0,
                    created_at TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS security_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting_name TEXT UNIQUE,
                    setting_value TEXT,
                    updated_at TEXT,
                    updated_by TEXT
                )
            ''')
            
            # Insert sample data if tables are empty
            cursor.execute("SELECT COUNT(*) FROM students")
            if cursor.fetchone()[0] == 0:
                sample_students = [
                    ('STU001', 'John', 'Doe', 20, 'Male', 'john.doe@university.edu', '555-0101'),
                    ('STU002', 'Jane', 'Smith', 19, 'Female', 'jane.smith@university.edu', '555-0102'),
                    ('STU003', 'Mike', 'Johnson', 21, 'Male', 'mike.johnson@university.edu', '555-0103'),
                ]
                
                for student in sample_students:
                    cursor.execute(
                        'INSERT INTO students (student_id, first_name, last_name, age, gender, email, phone) VALUES (?, ?, ?, ?, ?, ?, ?)',
                        student
                    )
            
            conn.commit()
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error initializing database: {e}")
    
    def setup_styles(self):
        """Configure ttk styles for the application"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure custom styles
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), background='#f0f0f0')
        style.configure('Heading.TLabel', font=('Arial', 12, 'bold'), background='#f0f0f0')
        style.configure('Success.TLabel', foreground='green', font=('Arial', 10, 'bold'))
        style.configure('Error.TLabel', foreground='red', font=('Arial', 10, 'bold'))
        style.configure('Warning.TLabel', foreground='orange', font=('Arial', 10, 'bold'))
    
    def show_login_screen(self):
        """Show login screen"""
        # Clear any existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Create login frame
        login_frame = ttk.Frame(self.root, padding="50")
        login_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Title
        ttk.Label(login_frame, text="Enhanced University Health Portal", 
                 style='Title.TLabel').grid(row=0, column=0, columnspan=2, pady=20)
        
        # Username
        ttk.Label(login_frame, text="Username:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.username_var = tk.StringVar()
        username_entry = ttk.Entry(login_frame, textvariable=self.username_var, width=20)
        username_entry.grid(row=1, column=1, pady=5, padx=(10, 0))
        
        # Password
        ttk.Label(login_frame, text="Password:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.password_var = tk.StringVar()
        password_entry = ttk.Entry(login_frame, textvariable=self.password_var, width=20, show="*")
        password_entry.grid(row=2, column=1, pady=5, padx=(10, 0))
        
        # Login button
        def attempt_login():
            if self.auth.login(self.username_var.get(), self.password_var.get()):
                self.log_audit_event('login', 'session', self.auth.current_user['id'])
                self.create_main_interface()
            else:
                messagebox.showerror("Login Failed", "Invalid username or password")
        
        ttk.Button(login_frame, text="Login", command=attempt_login).grid(row=3, column=0, columnspan=2, pady=20)
        
        # Demo info
        info_text = "Demo Accounts:\nAdmin: admin/admin123\nDoctor: doctor/doctor123\nStudent: student/student123"
        ttk.Label(login_frame, text=info_text, font=('Arial', 8)).grid(row=4, column=0, columnspan=2, pady=10)
        
        # Bind Enter key to login
        password_entry.bind('<Return>', lambda e: attempt_login())
    
    def create_main_interface(self):
        """Create the main interface after successful login"""
        # Clear login screen
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # Create header
        self.create_header(main_frame)
        
        # Create navigation panel
        self.create_navigation(main_frame)
        
        # Create content area
        self.create_content_area(main_frame)
        
        # Create status bar
        self.create_status_bar(main_frame)
    
    def create_header(self, parent):
        """Create the header section"""
        header_frame = ttk.Frame(parent, padding="5")
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        # Title
        title_label = ttk.Label(header_frame, text="Enhanced University Health Portal", 
                               style='Title.TLabel')
        title_label.grid(row=0, column=0, sticky=tk.W)
        
        # User info
        user_info = f"Logged in as: {self.auth.current_user['username']} ({self.auth.current_user['role']})"
        user_label = ttk.Label(header_frame, text=user_info)
        user_label.grid(row=0, column=1, sticky=tk.E)
        
        # Logout button
        logout_btn = ttk.Button(header_frame, text="🏠 Return to Main Menu", command=self.return_to_main_menu)
        logout_btn.grid(row=0, column=2, padx=(10, 0))
        
        header_frame.columnconfigure(1, weight=1)
    
    def create_navigation(self, parent):
        """Create the navigation panel with buttons and scrollbar"""
        nav_frame = ttk.LabelFrame(parent, text="Navigation", padding="5")
        nav_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))

        # Create canvas for scrollable button area
        self.nav_canvas = tk.Canvas(nav_frame, highlightthickness=0, bg='#f0f0f0')
        self.nav_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Navigation scrollbar
        nav_scroll = ttk.Scrollbar(nav_frame, orient=tk.VERTICAL, command=self.nav_canvas.yview)
        nav_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.nav_canvas.configure(yscrollcommand=nav_scroll.set)

        # Create frame inside canvas for buttons
        self.nav_buttons_frame = ttk.Frame(self.nav_canvas)
        self.nav_canvas_window = self.nav_canvas.create_window((0, 0), window=self.nav_buttons_frame, anchor='nw')

        # Configure canvas scrolling
        self.nav_buttons_frame.bind('<Configure>', lambda e: self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox('all')))
        self.nav_canvas.bind('<Configure>', self._on_nav_canvas_configure)

        # Enable mousewheel scrolling
        self.nav_canvas.bind_all('<MouseWheel>', self._on_nav_mousewheel)

        nav_frame.columnconfigure(0, weight=1)
        nav_frame.rowconfigure(0, weight=1)

        # Populate navigation based on user permissions
        self.populate_navigation()

    def _on_nav_canvas_configure(self, event):
        """Handle canvas resize to adjust button frame width"""
        canvas_width = event.width
        self.nav_canvas.itemconfig(self.nav_canvas_window, width=canvas_width)

    def _on_nav_mousewheel(self, event):
        """Handle mousewheel scrolling for navigation"""
        if self.nav_canvas.winfo_containing(event.x_root, event.y_root) == self.nav_canvas:
            self.nav_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def populate_navigation(self):
        """Populate navigation buttons based on user permissions"""
        # Clear existing buttons
        for widget in self.nav_buttons_frame.winfo_children():
            widget.destroy()

        button_row = 0

        # Helper function to create section header
        def create_section_header(text):
            nonlocal button_row
            header = ttk.Label(self.nav_buttons_frame, text=text, font=('Arial', 10, 'bold'),
                             background='#e0e0e0', anchor='w', padding=(5, 5))
            header.grid(row=button_row, column=0, sticky=(tk.W, tk.E), pady=(5, 2), padx=2)
            button_row += 1

        # Helper function to create navigation button
        def create_nav_button(text, function_name):
            nonlocal button_row
            btn = ttk.Button(self.nav_buttons_frame, text=text,
                           command=lambda: self.load_function(function_name), width=30)
            btn.grid(row=button_row, column=0, sticky=(tk.W, tk.E), pady=2, padx=(10, 2))
            button_row += 1

        # Health Records & Clinical Data
        if (self.auth.check_permission('manage_health_records') or
            self.auth.check_permission('view_own_health_record') or
            self.auth.check_permission('view_any_health_record')):

            create_section_header("Health Records & Clinical Data")

            if self.auth.check_permission('manage_health_records'):
                create_nav_button("Manage Health Records", 'manage_health_records')

            create_nav_button("View Health Records", 'view_health_records')
            create_nav_button("View Medical History", 'view_medical_history')
            create_nav_button("Generate Health Reports", 'generate_health_reports')

        # Appointments
        if (self.auth.check_permission('manage_health_appointments') or
            self.auth.check_permission('schedule_health_appointment') or
            self.auth.check_permission('view_own_appointments')):

            create_section_header("Appointments & Scheduling")

            if (self.auth.check_permission('schedule_health_appointment') or
                self.auth.check_permission('manage_health_appointments')):
                create_nav_button("Schedule Appointment", 'schedule_appointment')

            create_nav_button("View Appointments", 'view_appointments')

        # Vaccinations
        if (self.auth.check_permission('manage_vaccinations') or
            self.auth.check_permission('view_own_vaccinations') or
            self.auth.check_permission('verify_vaccinations')):

            create_section_header("Vaccinations")

            if self.auth.check_permission('manage_vaccinations'):
                create_nav_button("Record Vaccination", 'record_vaccination')

            create_nav_button("View Vaccination Records", 'view_vaccination_records')

        # Emergency Contacts
        create_section_header("Emergency Contacts")
        create_nav_button("Manage Emergency Contacts", 'manage_emergency_contacts')

        # Reports and Analytics
        if self.auth.check_permission('view_any_health_record'):
            create_section_header("Reports & Analytics")
            create_nav_button("Health Reports", 'health_reports')

        # Integration Services
        create_section_header("Integration Services")
        create_nav_button("Email Manager", 'email_manager')
        create_nav_button("Send Health Report Email", 'send_health_report_email')
        create_nav_button("Send Health Record Email", 'send_health_record_email')

        # Accessibility & Accommodations
        create_section_header("Accessibility & Accommodations")
        create_nav_button("Open Accessibility Tools", 'open_accessibility_tools')
        create_nav_button("Medical Accommodations", 'medical_accommodations')

        # Administration (Admin only)
        if self.auth.current_user['role'] == 'admin':
            create_section_header("Administration")
            create_nav_button("Security Audit", 'security_audit')
            create_nav_button("Data Management", 'data_management')

        # Configure column weight for button frame
        self.nav_buttons_frame.columnconfigure(0, weight=1)
    
    def create_content_area(self, parent):
        """Create the main content area"""
        self.content_frame = ttk.LabelFrame(parent, text="Content", padding="10")
        self.content_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(0, weight=1)

        # Create content_area as an alias for content_frame for compatibility
        self.content_area = self.content_frame
        
        # Welcome message
        welcome_text = f"Welcome to the Enhanced University Health Portal!\nSelect a function from the navigation panel to begin."
        welcome_label = ttk.Label(self.content_frame, text=welcome_text, justify=tk.CENTER)
        welcome_label.grid(row=0, column=0, pady=50)
    
    def create_status_bar(self, parent):
        """Create the status bar"""
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        
        status_bar = ttk.Label(parent, textvariable=self.status_var, relief=tk.SUNKEN, padding="5")
        status_bar.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E))

    def load_function(self, function_name):
        """Load the selected function in the content area"""
        # Clear current content
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        # Update status
        self.status_var.set(f"Loading {function_name}...")
        
        # Create function interface based on function name
        try:
            if hasattr(self, f'create_{function_name}'):
                getattr(self, f'create_{function_name}')()
            else:
                self.create_placeholder(function_name)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load {function_name}: {str(e)}")
        
        self.status_var.set("Ready")
    
    def create_placeholder(self, function_name):
        """Create a placeholder interface for functions not yet implemented"""
        title = ttk.Label(self.content_frame, text=f"{function_name.replace('_', ' ').title()}",
                         style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        message = ttk.Label(self.content_frame,
                           text=f"This feature ({function_name}) is available in the system.\nGUI interface can be expanded as needed!")
        message.grid(row=1, column=0, pady=20)

    # ==================== INTEGRATION SERVICE INTERFACES ====================

    def create_email_manager(self):
        """Create email manager interface"""
        title = ttk.Label(self.content_frame, text="Health Portal Email Manager",
                         style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        # Launch email manager button
        launch_frame = ttk.Frame(self.content_frame)
        launch_frame.grid(row=1, column=0, pady=20)

        ttk.Button(launch_frame, text="Open Email Manager",
                  command=self.open_email_manager_gui).pack(pady=10)

        # Information text
        info_text = """The Email Manager allows you to:
• Send appointment confirmations and cancellations
• Email health reports to patients
• Send health record notifications
• Manage emergency contact communications

Click the button above to open the full Email Manager interface."""

        info_label = ttk.Label(self.content_frame, text=info_text, justify=tk.LEFT)
        info_label.grid(row=2, column=0, pady=10, padx=20)

    def create_send_health_report_email(self):
        """Create interface for sending health report emails"""
        title = ttk.Label(self.content_frame, text="Send Health Report Email",
                         style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        # Create form for sending health report emails
        form_frame = ttk.LabelFrame(self.content_frame, text="Email Health Report", padding="10")
        form_frame.grid(row=1, column=0, pady=10, padx=20, sticky=(tk.W, tk.E))

        # Patient selection
        ttk.Label(form_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.email_student_id = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.email_student_id, width=20).grid(row=0, column=1, pady=5, padx=10)

        # Report details
        ttk.Label(form_frame, text="Report Title:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.email_report_title = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.email_report_title, width=40).grid(row=1, column=1, pady=5, padx=10)

        ttk.Label(form_frame, text="Report Type:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.email_report_type = tk.StringVar()
        ttk.Combobox(form_frame, textvariable=self.email_report_type,
                    values=["Blood Test Results", "Physical Exam", "Vaccination Record", "Medical Clearance"]).grid(row=2, column=1, pady=5, padx=10)

        ttk.Label(form_frame, text="Report Summary:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.email_report_summary = scrolledtext.ScrolledText(form_frame, height=4, width=50)
        self.email_report_summary.grid(row=3, column=1, pady=5, padx=10)

        # Send button
        def send_health_report_email():
            student_id = self.email_student_id.get().strip()
            if not student_id:
                messagebox.showerror("Error", "Please enter a Student ID")
                return

            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT first_name, last_name, email FROM students WHERE student_id = ?", (student_id,))
                patient_info = cursor.fetchone()
                conn.close()

                if not patient_info:
                    messagebox.showerror("Error", "Student not found")
                    return

                patient_name = f"{patient_info[0]} {patient_info[1]}"
                patient_email = patient_info[2]

                report_details = {
                    'title': self.email_report_title.get(),
                    'type': self.email_report_type.get(),
                    'summary': self.email_report_summary.get('1.0', tk.END).strip(),
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'practitioner': self.auth.current_user.get('username', 'Health Center Staff')
                }

                self.send_health_report_email(patient_email, patient_name, report_details)
                messagebox.showinfo("Success", f"Health report email sent to {patient_name}")

                # Clear form
                self.email_student_id.set("")
                self.email_report_title.set("")
                self.email_report_type.set("")
                self.email_report_summary.delete('1.0', tk.END)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to send email: {str(e)}")

        ttk.Button(form_frame, text="Send Health Report Email",
                  command=send_health_report_email).grid(row=4, column=0, columnspan=2, pady=20)

    def create_send_health_record_email(self):
        """Create interface for sending health record emails"""
        title = ttk.Label(self.content_frame, text="Send Health Record Email",
                         style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        # Create form for sending health record emails
        form_frame = ttk.LabelFrame(self.content_frame, text="Email Health Record", padding="10")
        form_frame.grid(row=1, column=0, pady=10, padx=20, sticky=(tk.W, tk.E))

        # Patient selection
        ttk.Label(form_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.record_email_student_id = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.record_email_student_id, width=20).grid(row=0, column=1, pady=5, padx=10)

        # Record details
        ttk.Label(form_frame, text="Record Type:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.record_email_type = tk.StringVar()
        ttk.Combobox(form_frame, textvariable=self.record_email_type,
                    values=["Complete Medical History", "Vaccination Records", "Visit Summary", "Emergency Information"]).grid(row=1, column=1, pady=5, padx=10)

        ttk.Label(form_frame, text="Date Range:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.record_email_date_range = tk.StringVar(value="All dates")
        ttk.Entry(form_frame, textvariable=self.record_email_date_range, width=30).grid(row=2, column=1, pady=5, padx=10)

        ttk.Label(form_frame, text="Summary:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.record_email_summary = scrolledtext.ScrolledText(form_frame, height=4, width=50)
        self.record_email_summary.grid(row=3, column=1, pady=5, padx=10)

        # Send button
        def send_health_record_email():
            student_id = self.record_email_student_id.get().strip()
            if not student_id:
                messagebox.showerror("Error", "Please enter a Student ID")
                return

            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT first_name, last_name, email FROM students WHERE student_id = ?", (student_id,))
                patient_info = cursor.fetchone()
                conn.close()

                if not patient_info:
                    messagebox.showerror("Error", "Student not found")
                    return

                patient_name = f"{patient_info[0]} {patient_info[1]}"
                patient_email = patient_info[2]

                record_details = {
                    'type': self.record_email_type.get(),
                    'date_range': self.record_email_date_range.get(),
                    'summary': self.record_email_summary.get('1.0', tk.END).strip()
                }

                self.send_health_record_email(patient_email, patient_name, record_details)
                messagebox.showinfo("Success", f"Health record email sent to {patient_name}")

                # Clear form
                self.record_email_student_id.set("")
                self.record_email_type.set("")
                self.record_email_date_range.set("All dates")
                self.record_email_summary.delete('1.0', tk.END)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to send email: {str(e)}")

        ttk.Button(form_frame, text="Send Health Record Email",
                  command=send_health_record_email).grid(row=4, column=0, columnspan=2, pady=20)

    # Health Records Management
    def create_manage_health_records(self):
        """Create health records management interface"""
        title = ttk.Label(self.content_frame, text="Health Records Management", style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Add Record tab
        add_tab = ttk.Frame(notebook)
        notebook.add(add_tab, text="Add Record")
        self.create_add_health_record_form(add_tab)
        
        # View Records tab
        view_tab = ttk.Frame(notebook)
        notebook.add(view_tab, text="View Records")
        self.create_view_health_records_form(view_tab)
        
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)
    
    def create_add_health_record_form(self, parent):
        """Create form for adding health records"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Form fields
        ttk.Label(main_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.hr_student_id = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.hr_student_id, width=20).grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(main_frame, text="Record Type:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.hr_record_type = tk.StringVar()
        record_type_combo = ttk.Combobox(main_frame, textvariable=self.hr_record_type, 
                                        values=['General Medical', 'Annual Physical', 'Illness Treatment', 
                                               'Injury Treatment', 'Mental Health', 'Vaccination', 'Other'])
        record_type_combo.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(main_frame, text="Record Date:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.hr_record_date = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(main_frame, textvariable=self.hr_record_date, width=20).grid(row=2, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(main_frame, text="Provider:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.hr_provider = tk.StringVar(value=f"Dr. {self.auth.current_user['username']}")
        ttk.Entry(main_frame, textvariable=self.hr_provider, width=30).grid(row=3, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(main_frame, text="Description:").grid(row=4, column=0, sticky=(tk.W, tk.N), pady=5)
        self.hr_description = tk.Text(main_frame, width=50, height=6)
        self.hr_description.grid(row=4, column=1, pady=5, padx=(5, 0))
        
        ttk.Label(main_frame, text="Confidential:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.hr_confidential = tk.BooleanVar()
        ttk.Checkbutton(main_frame, variable=self.hr_confidential).grid(row=5, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save Record", command=self.save_health_record).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Form", command=self.clear_health_record_form).pack(side=tk.LEFT, padx=5)
        
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
    
    def save_health_record(self):
        """Save health record to database"""
        try:
            # Validate inputs
            if not self.hr_student_id.get().strip():
                messagebox.showerror("Error", "Student ID is required")
                return
            
            if not self.hr_record_type.get().strip():
                messagebox.showerror("Error", "Record type is required")
                return
            
            if not self.hr_description.get(1.0, tk.END).strip():
                messagebox.showerror("Error", "Description is required")
                return
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Check if student exists
            cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (self.hr_student_id.get().strip(),))
            if cursor.fetchone()[0] == 0:
                messagebox.showerror("Error", "Student ID not found")
                conn.close()
                return
            
            # Insert health record
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO health_records 
                (student_id, record_type, record_date, provider, description, confidential, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.hr_student_id.get().strip(),
                self.hr_record_type.get(),
                self.hr_record_date.get(),
                self.hr_provider.get(),
                self.hr_description.get(1.0, tk.END).strip(),
                1 if self.hr_confidential.get() else 0,
                created_at
            ))
            
            conn.commit()
            record_id = cursor.lastrowid

            # Get patient information for email
            cursor.execute("SELECT first_name, last_name, email FROM students WHERE student_id = ?",
                          (self.hr_student_id.get().strip(),))
            patient_info = cursor.fetchone()

            conn.close()

            # Send health record creation confirmation email
            if patient_info:
                patient_name = f"{patient_info[0]} {patient_info[1]}"
                patient_email = patient_info[2]
                record_type = self.hr_record_type.get()

                self.send_health_record_creation_confirmation(patient_email, patient_name, record_type)

            self.log_audit_event('add_health_record', 'health_record', record_id)
            messagebox.showinfo("Success", "Health record added successfully!\nConfirmation email sent.")
            self.clear_health_record_form()
            
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
    
    def clear_health_record_form(self):
        """Clear the health record form"""
        self.hr_student_id.set("")
        self.hr_record_type.set("")
        self.hr_record_date.set(datetime.now().strftime('%Y-%m-%d'))
        self.hr_provider.set(f"Dr. {self.auth.current_user['username']}")
        self.hr_description.delete(1.0, tk.END)
        self.hr_confidential.set(False)
    
    def create_view_health_records_form(self, parent):
        """Create interface for viewing health records"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Search frame
        search_frame = ttk.LabelFrame(main_frame, text="Search Filters", padding="5")
        search_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Student ID filter
        ttk.Label(search_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.hr_search_student = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.hr_search_student, width=20).grid(row=0, column=1, sticky=tk.W, pady=2, padx=(5, 10))
        
        # Date range filters
        ttk.Label(search_frame, text="Date From:").grid(row=0, column=2, sticky=tk.W, pady=2)
        self.hr_search_date_from = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.hr_search_date_from, width=12).grid(row=0, column=3, sticky=tk.W, pady=2, padx=(5, 10))
        
        ttk.Label(search_frame, text="Date To:").grid(row=0, column=4, sticky=tk.W, pady=2)
        self.hr_search_date_to = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.hr_search_date_to, width=12).grid(row=0, column=5, sticky=tk.W, pady=2, padx=(5, 10))
        
        # Search button
        ttk.Button(search_frame, text="Search", command=self.search_health_records).grid(row=0, column=6, padx=10)
        
        # Results tree
        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        columns = ('ID', 'Student ID', 'Type', 'Date', 'Provider', 'Confidential')
        self.hr_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        # Configure column headings and widths
        for col in columns:
            self.hr_tree.heading(col, text=col)
            if col == 'ID':
                self.hr_tree.column(col, width=50)
            elif col in ['Student ID', 'Type', 'Provider']:
                self.hr_tree.column(col, width=120)
            elif col == 'Date':
                self.hr_tree.column(col, width=100)
            else:
                self.hr_tree.column(col, width=80)
        
        self.hr_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.hr_tree.yview)
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.hr_tree.configure(yscrollcommand=v_scrollbar.set)
        
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.hr_tree.xview)
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.hr_tree.configure(xscrollcommand=h_scrollbar.set)
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=2, column=0, pady=10)
        
        ttk.Button(buttons_frame, text="View Details", command=self.view_health_record_details).pack(side=tk.LEFT, padx=5)
        if self.auth.check_permission('manage_health_records'):
            ttk.Button(buttons_frame, text="Update", command=self.update_health_record).pack(side=tk.LEFT, padx=5)
            ttk.Button(buttons_frame, text="Delete", command=self.delete_health_record).pack(side=tk.LEFT, padx=5)
        
        # Configure grid weights
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # Initial load
        self.search_health_records()
    
    def search_health_records(self):
        """Search and load health records"""
        # Clear existing items
        for item in self.hr_tree.get_children():
            self.hr_tree.delete(item)
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Build query based on permissions and filters
            query = '''
                SELECT hr.id, hr.student_id, hr.record_type, hr.record_date, 
                       hr.provider, hr.confidential
                FROM health_records hr
                JOIN students s ON hr.student_id = s.student_id
                WHERE 1=1
            '''
            
            params = []
            
            # Apply filters
            if self.hr_search_student.get().strip():
                query += " AND hr.student_id LIKE ?"
                params.append(f"%{self.hr_search_student.get().strip()}%")
            
            if self.hr_search_date_from.get().strip():
                query += " AND hr.record_date >= ?"
                params.append(self.hr_search_date_from.get().strip())
            
            if self.hr_search_date_to.get().strip():
                query += " AND hr.record_date <= ?"
                params.append(self.hr_search_date_to.get().strip())
            
            # Apply permission-based filtering
            if not self.auth.check_permission('view_any_health_record'):
                if self.auth.current_user['role'] == 'student':
                    query += " AND hr.student_id = ?"
                    params.append(self.auth.current_user['id'])
                else:
                    query += " AND hr.confidential = 0"
            
            query += " ORDER BY hr.record_date DESC, hr.id DESC LIMIT 100"
            
            cursor.execute(query, params)
            records = cursor.fetchall()
            
            # Insert records into tree
            for record in records:
                confidential = "Yes" if record[5] else "No"
                self.hr_tree.insert('', tk.END, values=(
                    record[0], record[1], record[2], record[3], record[4], confidential
                ))
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load health records: {str(e)}")
    
    def view_health_record_details(self):
        """Show detailed view of selected health record"""
        selection = self.hr_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a record to view.")
            return
        
        record_id = self.hr_tree.item(selection[0])['values'][0]
        
        details_window = tk.Toplevel(self.root)
        details_window.title("Health Record Details")
        details_window.geometry("600x500")
        details_window.transient(self.root)
        details_window.grab_set()
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT hr.id, hr.student_id, s.first_name, s.last_name, hr.record_type,
                       hr.record_date, hr.provider, hr.description, hr.confidential, hr.created_at
                FROM health_records hr
                JOIN students s ON hr.student_id = s.student_id
                WHERE hr.id = ?
            ''', (record_id,))
            
            record = cursor.fetchone()
            conn.close()
            
            if not record:
                messagebox.showerror("Error", "Record not found")
                details_window.destroy()
                return
            
            main_frame = ttk.Frame(details_window, padding="20")
            main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            
            # Record details
            ttk.Label(main_frame, text="Health Record Details", style='Title.TLabel').grid(row=0, column=0, columnspan=2, pady=10)
            
            fields = [
                ("Record ID:", record[0]),
                ("Student ID:", record[1]),
                ("Student Name:", f"{record[2]} {record[3]}"),
                ("Record Type:", record[4]),
                ("Date:", record[5]),
                ("Provider:", record[6]),
                ("Confidential:", "Yes" if record[8] else "No"),
                ("Created:", record[9])
            ]
            
            row = 1
            for label, value in fields:
                ttk.Label(main_frame, text=label, font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky=tk.W, pady=5)
                ttk.Label(main_frame, text=str(value)).grid(row=row, column=1, sticky=tk.W, pady=5, padx=(10, 0))
                row += 1
            
            # Description
            ttk.Label(main_frame, text="Description:", font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky=(tk.W, tk.N), pady=5)
            
            desc_frame = ttk.Frame(main_frame)
            desc_frame.grid(row=row, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5, padx=(10, 0))
            
            desc_text = tk.Text(desc_frame, width=50, height=8, state=tk.DISABLED, wrap=tk.WORD)
            desc_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            
            desc_scroll = ttk.Scrollbar(desc_frame, orient=tk.VERTICAL, command=desc_text.yview)
            desc_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
            desc_text.configure(yscrollcommand=desc_scroll.set)
            
            # Insert description
            desc_text.config(state=tk.NORMAL)
            desc_text.insert(1.0, record[7] or "No description provided")
            desc_text.config(state=tk.DISABLED)
            
            # Close button
            ttk.Button(main_frame, text="Close", command=details_window.destroy).grid(row=row+1, column=0, columnspan=2, pady=20)
            
            details_window.columnconfigure(0, weight=1)
            details_window.rowconfigure(0, weight=1)
            main_frame.columnconfigure(1, weight=1)
            desc_frame.columnconfigure(0, weight=1)
            desc_frame.rowconfigure(0, weight=1)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load record details: {str(e)}")
            details_window.destroy()
    
    def update_health_record(self):
        """Update selected health record"""
        selection = self.hr_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a record to update.")
            return
        
        record_id = self.hr_tree.item(selection[0])['values'][0]

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Get current record details
            cursor.execute('''
                SELECT student_id, record_type, record_date, description, provider, confidential
                FROM health_records
                WHERE id = ?
            ''', (record_id,))
            record = cursor.fetchone()

            if not record:
                messagebox.showerror("Error", "Record not found")
                conn.close()
                return

            # Create update dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Update Health Record")
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Update Health Record", font=('Arial', 12, 'bold')).pack(pady=10)

            form_frame = ttk.Frame(main_frame)
            form_frame.pack(fill='both', expand=True, pady=10)

            # Student ID (read-only)
            ttk.Label(form_frame, text="Student ID:").grid(row=0, column=0, sticky='w', pady=5)
            student_id_label = ttk.Label(form_frame, text=record[0], font=('Arial', 10, 'bold'))
            student_id_label.grid(row=0, column=1, sticky='w', pady=5)

            # Record Type
            ttk.Label(form_frame, text="Record Type:*").grid(row=1, column=0, sticky='w', pady=5)
            record_type_var = tk.StringVar(value=record[1])
            record_type_combo = ttk.Combobox(form_frame, textvariable=record_type_var,
                                            values=['Checkup', 'Vaccination', 'Emergency', 'Prescription',
                                                   'Lab Result', 'Consultation', 'Treatment', 'Other'],
                                            width=30)
            record_type_combo.grid(row=1, column=1, pady=5, padx=10)

            # Record Date
            ttk.Label(form_frame, text="Record Date:*").grid(row=2, column=0, sticky='w', pady=5)
            date_var = tk.StringVar(value=record[2])
            date_entry = ttk.Entry(form_frame, textvariable=date_var, width=32)
            date_entry.grid(row=2, column=1, pady=5, padx=10)

            # Description
            ttk.Label(form_frame, text="Description:").grid(row=3, column=0, sticky='nw', pady=5)
            description_text = tk.Text(form_frame, width=32, height=8)
            description_text.grid(row=3, column=1, pady=5, padx=10)
            if record[3]:
                description_text.insert("1.0", record[3])

            # Provider
            ttk.Label(form_frame, text="Provider:").grid(row=4, column=0, sticky='w', pady=5)
            provider_var = tk.StringVar(value=record[4] or "")
            provider_entry = ttk.Entry(form_frame, textvariable=provider_var, width=32)
            provider_entry.grid(row=4, column=1, pady=5, padx=10)

            # Confidential checkbox
            confidential_var = tk.BooleanVar(value=bool(record[5]))
            ttk.Checkbutton(form_frame, text="Confidential", variable=confidential_var).grid(
                row=5, column=0, columnspan=2, sticky='w', pady=5
            )

            def save_updates():
                try:
                    cursor.execute('''
                        UPDATE health_records
                        SET record_type = ?, record_date = ?, description = ?,
                            provider = ?, confidential = ?
                        WHERE id = ?
                    ''', (
                        record_type_var.get(),
                        date_var.get(),
                        description_text.get("1.0", tk.END).strip(),
                        provider_var.get(),
                        1 if confidential_var.get() else 0,
                        record_id
                    ))

                    conn.commit()
                    messagebox.showinfo("Success", "Health record updated successfully")
                    self.search_health_records()  # Refresh list
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update record: {e}")

            buttons_frame = ttk.Frame(main_frame)
            buttons_frame.pack(pady=10)

            ttk.Button(buttons_frame, text="Save", command=save_updates).pack(side='left', padx=5)
            ttk.Button(buttons_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load record: {e}")
    
    def delete_health_record(self):
        """Delete selected health record"""
        selection = self.hr_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a record to delete.")
            return

        record_id = self.hr_tree.item(selection[0])['values'][0]

        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this health record?"):
            try:
                conn = self.get_connection()
                cursor = conn.cursor()

                # Get record and patient details for email
                cursor.execute('''
                    SELECT hr.record_type, hr.student_id, s.first_name, s.last_name, s.email
                    FROM health_records hr
                    JOIN students s ON hr.student_id = s.student_id
                    WHERE hr.id = ?
                ''', (record_id,))

                record_info = cursor.fetchone()

                cursor.execute('DELETE FROM health_records WHERE id = ?', (record_id,))
                conn.commit()
                conn.close()

                # Send deletion confirmation email
                if record_info:
                    patient_name = f"{record_info[2]} {record_info[3]}"
                    patient_email = record_info[4]
                    record_type = record_info[0]

                    self.send_health_record_deletion_confirmation(patient_email, patient_name, record_type)

                self.log_audit_event('delete_health_record', 'health_record', record_id)
                messagebox.showinfo("Success", "Health record deleted successfully!\nConfirmation email sent.")
                self.search_health_records()  # Refresh the list

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete record: {str(e)}")
    
    # Vaccination Management
    def create_record_vaccination(self):
        """Create vaccination recording interface"""
        title = ttk.Label(self.content_frame, text="Vaccination Management", style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Record Vaccination tab
        record_tab = ttk.Frame(notebook)
        notebook.add(record_tab, text="Record Vaccination")
        self.create_record_vaccination_form(record_tab)
        
        # View Vaccinations tab
        view_tab = ttk.Frame(notebook)
        notebook.add(view_tab, text="View Vaccinations")
        self.create_view_vaccinations_form(view_tab)
        
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)
    
    def create_record_vaccination_form(self, parent):
        """Create form for recording vaccinations"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Form fields
        ttk.Label(main_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.vax_student_id = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.vax_student_id, width=20).grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(main_frame, text="Vaccine:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.vax_name = tk.StringVar()
        vaccine_combo = ttk.Combobox(main_frame, textvariable=self.vax_name, 
                                    values=['COVID-19', 'Influenza (Flu)', 'Hepatitis A', 'Hepatitis B',
                                           'Measles, Mumps, Rubella (MMR)', 'Meningococcal', 
                                           'Tetanus, Diphtheria, Pertussis (Tdap)',
                                           'Varicella (Chickenpox)', 'HPV', 'Other'])
        vaccine_combo.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(main_frame, text="Administered Date:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.vax_date = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(main_frame, textvariable=self.vax_date, width=20).grid(row=2, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(main_frame, text="Lot Number:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.vax_lot = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.vax_lot, width=20).grid(row=3, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(main_frame, text="Manufacturer:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.vax_manufacturer = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.vax_manufacturer, width=30).grid(row=4, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(main_frame, text="Administered By:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.vax_admin_by = tk.StringVar(value=f"Dr. {self.auth.current_user['username']}")
        ttk.Entry(main_frame, textvariable=self.vax_admin_by, width=30).grid(row=5, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(main_frame, text="Location:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.vax_location = tk.StringVar(value="Left arm")
        ttk.Entry(main_frame, textvariable=self.vax_location, width=20).grid(row=6, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        # Adverse reaction checkbox
        self.vax_adverse = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Adverse Reaction Reported", 
                       variable=self.vax_adverse, command=self.toggle_adverse_reaction).grid(row=7, column=1, sticky=tk.W, pady=5)
        
        # Reaction description (initially disabled)
        ttk.Label(main_frame, text="Reaction Description:").grid(row=8, column=0, sticky=(tk.W, tk.N), pady=5)
        self.vax_reaction = tk.Text(main_frame, width=40, height=3, state=tk.DISABLED)
        self.vax_reaction.grid(row=8, column=1, pady=5, padx=(5, 0))
        
        # Save button
        ttk.Button(main_frame, text="Record Vaccination", command=self.save_vaccination).grid(row=9, column=0, columnspan=2, pady=20)
        
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
    
    def toggle_adverse_reaction(self):
        """Toggle adverse reaction text area"""
        if self.vax_adverse.get():
            self.vax_reaction.config(state=tk.NORMAL)
        else:
            self.vax_reaction.config(state=tk.DISABLED)
            self.vax_reaction.delete(1.0, tk.END)
    
    def save_vaccination(self):
        """Save vaccination record to database"""
        try:
            # Validate inputs
            if not all([self.vax_student_id.get().strip(), self.vax_name.get().strip(),
                       self.vax_date.get().strip(), self.vax_lot.get().strip(),
                       self.vax_manufacturer.get().strip(), self.vax_admin_by.get().strip()]):
                messagebox.showerror("Error", "Please fill in all required fields")
                return
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Check if student exists
            cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (self.vax_student_id.get().strip(),))
            if cursor.fetchone()[0] == 0:
                messagebox.showerror("Error", "Student ID not found")
                conn.close()
                return
            
            # Insert vaccination record
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            adverse_reaction = 1 if self.vax_adverse.get() else 0
            reaction_desc = self.vax_reaction.get(1.0, tk.END).strip() if adverse_reaction else ""
            
            cursor.execute('''
                INSERT INTO vaccination_records 
                (student_id, vaccine_name, administered_date, lot_number, manufacturer, 
                 administered_by, location, adverse_reaction, reaction_description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.vax_student_id.get().strip(),
                self.vax_name.get(),
                self.vax_date.get(),
                self.vax_lot.get().strip(),
                self.vax_manufacturer.get().strip(),
                self.vax_admin_by.get().strip(),
                self.vax_location.get().strip(),
                adverse_reaction,
                reaction_desc,
                created_at
            ))
            
            conn.commit()
            vax_id = cursor.lastrowid
            conn.close()
            
            self.log_audit_event('record_vaccination', 'vaccination', vax_id)
            
            if adverse_reaction:
                messagebox.showwarning("Vaccination Recorded", 
                                     "Vaccination recorded successfully!\nADVERSE REACTION REPORTED - Monitor patient closely")
            else:
                messagebox.showinfo("Success", "Vaccination recorded successfully!")
            
            self.clear_vaccination_form()
            
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
    
    def clear_vaccination_form(self):
        """Clear the vaccination form"""
        self.vax_student_id.set("")
        self.vax_name.set("")
        self.vax_date.set(datetime.now().strftime('%Y-%m-%d'))
        self.vax_lot.set("")
        self.vax_manufacturer.set("")
        self.vax_admin_by.set(f"Dr. {self.auth.current_user['username']}")
        self.vax_location.set("Left arm")
        self.vax_adverse.set(False)
        self.vax_reaction.delete(1.0, tk.END)
        self.vax_reaction.config(state=tk.DISABLED)
    
    def create_view_vaccinations_form(self, parent):
        """Create interface for viewing vaccination records"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Search frame
        search_frame = ttk.LabelFrame(main_frame, text="Search", padding="5")
        search_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(search_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.vax_search_student = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.vax_search_student, width=20).grid(row=0, column=1, sticky=tk.W, pady=2, padx=(5, 10))
        
        ttk.Button(search_frame, text="Search", command=self.search_vaccinations).grid(row=0, column=2, padx=5)
        ttk.Button(search_frame, text="Show All", command=self.load_all_vaccinations).grid(row=0, column=3, padx=5)
        
        # Results tree
        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        columns = ('ID', 'Student', 'Vaccine', 'Date', 'Administered By', 'Adverse Reaction')
        self.vax_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.vax_tree.heading(col, text=col)
            if col == 'ID':
                self.vax_tree.column(col, width=50)
            else:
                self.vax_tree.column(col, width=120)
        
        self.vax_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar
        vax_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.vax_tree.yview)
        vax_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.vax_tree.configure(yscrollcommand=vax_scroll.set)
        
        # Buttons
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=2, column=0, pady=10)
        
        ttk.Button(buttons_frame, text="View Details", command=self.view_vaccination_details).pack(side=tk.LEFT, padx=5)
        if self.auth.check_permission('verify_vaccinations'):
            ttk.Button(buttons_frame, text="Verify Record", command=self.verify_vaccination).pack(side=tk.LEFT, padx=5)
        
        # Configure grid weights
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # Initial load
        self.load_all_vaccinations()
    
    def search_vaccinations(self):
        """Search vaccination records"""
        self.load_vaccinations(self.vax_search_student.get().strip())
    
    def load_all_vaccinations(self):
        """Load all vaccination records"""
        self.load_vaccinations()
    
    def load_vaccinations(self, student_filter=""):
        """Load vaccination records with optional student filter"""
        # Clear existing items
        for item in self.vax_tree.get_children():
            self.vax_tree.delete(item)
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = '''
                SELECT vr.id, vr.student_id, vr.vaccine_name, vr.administered_date,
                       vr.administered_by, vr.adverse_reaction
                FROM vaccination_records vr
                WHERE 1=1
            '''
            params = []
            
            if student_filter:
                query += " AND vr.student_id LIKE ?"
                params.append(f"%{student_filter}%")
            
            # Apply permission-based filtering
            if not self.auth.check_permission('view_any_health_record') and self.auth.current_user['role'] == 'student':
                query += " AND vr.student_id = ?"
                params.append(self.auth.current_user['id'])
            
            query += " ORDER BY vr.administered_date DESC LIMIT 100"
            
            cursor.execute(query, params)
            records = cursor.fetchall()
            
            for record in records:
                adverse = "Yes" if record[5] else "No"
                self.vax_tree.insert('', tk.END, values=(
                    record[0], record[1], record[2], record[3], record[4], adverse
                ))
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load vaccination records: {str(e)}")
    
    def view_vaccination_details(self):
        """View details of selected vaccination record"""
        selection = self.vax_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a vaccination record to view.")
            return
        
        record_id = self.vax_tree.item(selection[0])['values'][0]

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Get vaccination details
            cursor.execute('''
                SELECT vr.student_id, s.first_name, s.last_name, vr.vaccine_name,
                       vr.administered_date, vr.expiry_date, vr.lot_number,
                       vr.manufacturer, vr.administered_by, vr.location,
                       vr.adverse_reaction, vr.reaction_description,
                       vr.verified, vr.verified_by, vr.verified_date
                FROM vaccination_records vr
                JOIN students s ON vr.student_id = s.student_id
                WHERE vr.id = ?
            ''', (record_id,))
            record = cursor.fetchone()
            conn.close()

            if not record:
                messagebox.showerror("Error", "Vaccination record not found")
                return

            # Create details dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Vaccination Details")
            dialog.geometry("600x700")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Vaccination Record Details", font=('Arial', 14, 'bold')).pack(pady=10)

            # Details frame
            details_frame = ttk.LabelFrame(main_frame, text="Record Information", padding=15)
            details_frame.pack(fill='both', expand=True, pady=10)

            info_text = tk.Text(details_frame, height=25, width=60, wrap='word', font=('Courier', 10))
            info_text.pack(fill='both', expand=True)

            # Format details
            details = f"""
STUDENT INFORMATION
{'='*50}
Student ID:      {record[0]}
Name:            {record[1]} {record[2]}

VACCINE INFORMATION
{'='*50}
Vaccine Name:    {record[3]}
Administered:    {record[4]}
Expiry Date:     {record[5] or 'N/A'}
Lot Number:      {record[6] or 'N/A'}
Manufacturer:    {record[7] or 'N/A'}

ADMINISTRATION DETAILS
{'='*50}
Administered By: {record[8] or 'N/A'}
Location:        {record[9] or 'N/A'}

ADVERSE REACTIONS
{'='*50}
Adverse Reaction: {'Yes' if record[10] else 'No'}
Description:     {record[11] if record[11] else 'None reported'}

VERIFICATION STATUS
{'='*50}
Verified:        {'Yes' if record[12] else 'No'}
Verified By:     {record[13] if record[13] else 'N/A'}
Verified Date:   {record[14] if record[14] else 'N/A'}
"""

            info_text.insert('1.0', details)
            info_text.config(state='disabled')

            # Close button
            ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load vaccination details: {e}")
    
    def verify_vaccination(self):
        """Verify selected vaccination record"""
        selection = self.vax_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a vaccination record to verify.")
            return
        
        record_id = self.vax_tree.item(selection[0])['values'][0]
        
        if messagebox.askyesno("Verify Vaccination", "Verify this vaccination record?"):
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE vaccination_records 
                    SET verified = 1, verified_by = ?, verified_date = ?
                    WHERE id = ?
                ''', (self.auth.current_user['username'], datetime.now().strftime('%Y-%m-%d'), record_id))
                
                conn.commit()
                conn.close()
                
                self.log_audit_event('verify_vaccination', 'vaccination', record_id)
                messagebox.showinfo("Success", "Vaccination record verified successfully!")
                self.load_vaccinations(self.vax_search_student.get().strip())
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to verify vaccination: {str(e)}")
    
    # Appointment Management
    def create_schedule_appointment(self):
        """Create appointment scheduling interface"""
        title = ttk.Label(self.content_frame, text="Appointment Management", style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Schedule Appointment tab
        schedule_tab = ttk.Frame(notebook)
        notebook.add(schedule_tab, text="Schedule Appointment")
        self.create_schedule_appointment_form(schedule_tab)
        
        # View Appointments tab  
        view_tab = ttk.Frame(notebook)
        notebook.add(view_tab, text="View Appointments")
        self.create_view_appointments_form(view_tab)
        
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)
    
    def create_schedule_appointment_form(self, parent):
        """Create form for scheduling appointments"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Form fields
        ttk.Label(main_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.apt_student_id = tk.StringVar()
        if self.auth.current_user['role'] == 'student':
            self.apt_student_id.set(self.auth.current_user['id'])
        ttk.Entry(main_frame, textvariable=self.apt_student_id, width=20).grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(main_frame, text="Appointment Type:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.apt_type = tk.StringVar()
        apt_type_combo = ttk.Combobox(main_frame, textvariable=self.apt_type, 
                                     values=['General Check-up', 'Follow-up Visit', 'Vaccination', 
                                            'Mental Health Consultation', 'Injury Assessment', 
                                            'Chronic Care Management', 'Preventive Screening', 
                                            'Emergency Consultation'])
        apt_type_combo.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(main_frame, text="Date (YYYY-MM-DD):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.apt_date = tk.StringVar()
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        self.apt_date.set(tomorrow)
        ttk.Entry(main_frame, textvariable=self.apt_date, width=20).grid(row=2, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(main_frame, text="Time (HH:MM):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.apt_time = tk.StringVar(value="09:00")
        ttk.Entry(main_frame, textvariable=self.apt_time, width=20).grid(row=3, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(main_frame, text="Provider:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.apt_provider = tk.StringVar(value="Dr. Health Services")
        ttk.Entry(main_frame, textvariable=self.apt_provider, width=30).grid(row=4, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(main_frame, text="Reason:").grid(row=5, column=0, sticky=(tk.W, tk.N), pady=5)
        self.apt_reason = tk.Text(main_frame, width=40, height=4)
        self.apt_reason.grid(row=5, column=1, pady=5, padx=(5, 0))
        
        # Schedule button
        ttk.Button(main_frame, text="Schedule Appointment", command=self.save_appointment).grid(row=6, column=0, columnspan=2, pady=20)
        
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
    
    def save_appointment(self):
        """Save appointment to database"""
        try:
            # Validate inputs
            if not all([self.apt_student_id.get().strip(), self.apt_type.get().strip(),
                       self.apt_date.get().strip(), self.apt_time.get().strip(),
                       self.apt_provider.get().strip()]):
                messagebox.showerror("Error", "Please fill in all required fields")
                return
            
            # Validate date and time formats
            try:
                datetime.strptime(self.apt_date.get(), '%Y-%m-%d')
                datetime.strptime(self.apt_time.get(), '%H:%M')
            except ValueError:
                messagebox.showerror("Error", "Invalid date or time format")
                return
            
            # Check if date is not in the past
            if datetime.strptime(self.apt_date.get(), '%Y-%m-%d') < datetime.now():
                messagebox.showerror("Error", "Cannot schedule appointments in the past")
                return
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Check if student exists
            cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (self.apt_student_id.get().strip(),))
            if cursor.fetchone()[0] == 0:
                messagebox.showerror("Error", "Student ID not found")
                conn.close()
                return
            
            # Insert appointment
            scheduled_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            reason = self.apt_reason.get(1.0, tk.END).strip()
            
            cursor.execute('''
                INSERT INTO health_appointments 
                (student_id, appointment_type, appointment_date, appointment_time, 
                 provider, reason, status, scheduled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.apt_student_id.get().strip(),
                self.apt_type.get(),
                self.apt_date.get(),
                self.apt_time.get(),
                self.apt_provider.get().strip(),
                reason,
                'scheduled',
                scheduled_at
            ))
            
            conn.commit()
            apt_id = cursor.lastrowid

            # Get patient information for email
            cursor.execute("SELECT first_name, last_name, email FROM students WHERE student_id = ?",
                          (self.apt_student_id.get().strip(),))
            patient_info = cursor.fetchone()

            conn.close()

            # Send appointment confirmation email
            if patient_info:
                patient_name = f"{patient_info[0]} {patient_info[1]}"
                patient_email = patient_info[2]

                appointment_details = {
                    'date': self.apt_date.get(),
                    'time': self.apt_time.get(),
                    'practitioner': self.apt_provider.get().strip(),
                    'department': self.apt_type.get(),
                    'type': self.apt_type.get(),
                    'preparation_notes': f"Reason for visit: {reason}" if reason else "No special preparation required."
                }

                self.send_appointment_confirmation(patient_email, patient_name, appointment_details)

            self.log_audit_event('schedule_appointment', 'appointment', apt_id)
            messagebox.showinfo("Success", f"Appointment scheduled successfully!\nAppointment ID: {apt_id}\nConfirmation email sent.")

            self.clear_appointment_form()
            
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
    
    def clear_appointment_form(self):
        """Clear the appointment form"""
        if self.auth.current_user['role'] != 'student':
            self.apt_student_id.set("")
        self.apt_type.set("")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        self.apt_date.set(tomorrow)
        self.apt_time.set("09:00")
        self.apt_provider.set("Dr. Health Services")
        self.apt_reason.delete(1.0, tk.END)
    
    def create_view_appointments_form(self, parent):
        """Create interface for viewing appointments"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Search frame
        search_frame = ttk.LabelFrame(main_frame, text="Search", padding="5")
        search_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(search_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.apt_search_student = tk.StringVar()
        if self.auth.current_user['role'] == 'student':
            self.apt_search_student.set(self.auth.current_user['id'])
        ttk.Entry(search_frame, textvariable=self.apt_search_student, width=20).grid(row=0, column=1, sticky=tk.W, pady=2, padx=(5, 10))
        
        ttk.Button(search_frame, text="Search", command=self.search_appointments).grid(row=0, column=2, padx=5)
        ttk.Button(search_frame, text="Show All", command=self.load_all_appointments).grid(row=0, column=3, padx=5)
        
        # Results tree
        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        columns = ('ID', 'Student', 'Type', 'Date', 'Time', 'Provider', 'Status')
        self.apt_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.apt_tree.heading(col, text=col)
            if col == 'ID':
                self.apt_tree.column(col, width=50)
            else:
                self.apt_tree.column(col, width=120)
        
        self.apt_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar
        apt_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.apt_tree.yview)
        apt_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.apt_tree.configure(yscrollcommand=apt_scroll.set)
        
        # Buttons
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=2, column=0, pady=10)
        
        ttk.Button(buttons_frame, text="View Details", command=self.view_appointment_details).pack(side=tk.LEFT, padx=5)
        if self.auth.check_permission('manage_health_appointments') or self.auth.check_permission('cancel_own_appointment'):
            ttk.Button(buttons_frame, text="Update Status", command=self.update_appointment_status).pack(side=tk.LEFT, padx=5)
            ttk.Button(buttons_frame, text="Cancel", command=self.cancel_appointment).pack(side=tk.LEFT, padx=5)
        
        # Configure grid weights
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # Initial load
        self.load_all_appointments()
    
    def search_appointments(self):
        """Search appointments"""
        self.load_appointments(self.apt_search_student.get().strip())
    
    def load_all_appointments(self):
        """Load all appointments"""
        self.load_appointments()
    
    def load_appointments(self, student_filter=""):
        """Load appointments with optional student filter"""
        # Clear existing items
        for item in self.apt_tree.get_children():
            self.apt_tree.delete(item)
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = '''
                SELECT ha.id, ha.student_id, ha.appointment_type, ha.appointment_date,
                       ha.appointment_time, ha.provider, ha.status
                FROM health_appointments ha
                WHERE 1=1
            '''
            params = []
            
            if student_filter:
                query += " AND ha.student_id LIKE ?"
                params.append(f"%{student_filter}%")
            
            # Apply permission-based filtering
            if not self.auth.check_permission('manage_health_appointments'):
                if self.auth.current_user['role'] == 'student':
                    query += " AND ha.student_id = ?"
                    params.append(self.auth.current_user['id'])
            
            query += " ORDER BY ha.appointment_date DESC, ha.appointment_time DESC LIMIT 100"
            
            cursor.execute(query, params)
            appointments = cursor.fetchall()
            
            for apt in appointments:
                self.apt_tree.insert('', tk.END, values=apt)
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load appointments: {str(e)}")
    
    def view_appointment_details(self):
        """View details of selected appointment"""
        selection = self.apt_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an appointment to view.")
            return
        
        apt_id = self.apt_tree.item(selection[0])['values'][0]

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Get appointment details
            cursor.execute('''
                SELECT apt.student_id, s.first_name, s.last_name, s.email,
                       apt.appointment_type, apt.appointment_date, apt.appointment_time,
                       apt.provider, apt.reason, apt.status, apt.notes, apt.scheduled_at
                FROM health_appointments apt
                JOIN students ON apt.student_id = s.student_id
                WHERE apt.id = ?
            ''', (apt_id,))
            record = cursor.fetchone()
            conn.close()

            if not record:
                messagebox.showerror("Error", "Appointment not found")
                return

            # Create details dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Appointment Details")
            dialog.geometry("600x600")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Appointment Details", font=('Arial', 14, 'bold')).pack(pady=10)

            # Details frame
            details_frame = ttk.LabelFrame(main_frame, text="Appointment Information", padding=15)
            details_frame.pack(fill='both', expand=True, pady=10)

            info_text = tk.Text(details_frame, height=20, width=60, wrap='word', font=('Courier', 10))
            info_text.pack(fill='both', expand=True)

            # Format details
            status_display = record[9].upper() if record[9] else 'SCHEDULED'
            details = f"""
PATIENT INFORMATION
{'='*50}
Student ID:      {record[0]}
Name:            {record[1]} {record[2]}
Email:           {record[3]}

APPOINTMENT DETAILS
{'='*50}
Type:            {record[4]}
Date:            {record[5]}
Time:            {record[6]}
Provider:        {record[7] or 'Not assigned'}
Status:          {status_display}

REASON FOR VISIT
{'='*50}
{record[8] if record[8] else 'No reason provided'}

NOTES
{'='*50}
{record[10] if record[10] else 'No notes'}

SCHEDULING INFORMATION
{'='*50}
Scheduled At:    {record[11] if record[11] else 'N/A'}
"""

            info_text.insert('1.0', details)
            info_text.config(state='disabled')

            # Close button
            ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load appointment details: {e}")
    
    def update_appointment_status(self):
        """Update appointment status"""
        selection = self.apt_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an appointment to update.")
            return
        
        apt_id = self.apt_tree.item(selection[0])['values'][0]
        current_status = self.apt_tree.item(selection[0])['values'][6]
        
        # Create status selection dialog
        status_dialog = tk.Toplevel(self.root)
        status_dialog.title("Update Appointment Status")
        status_dialog.geometry("300x200")
        status_dialog.transient(self.root)
        status_dialog.grab_set()
        
        ttk.Label(status_dialog, text=f"Current Status: {current_status}").pack(pady=10)
        ttk.Label(status_dialog, text="New Status:").pack()
        
        new_status = tk.StringVar()
        status_combo = ttk.Combobox(status_dialog, textvariable=new_status, 
                                   values=['scheduled', 'completed', 'cancelled', 'no-show', 'rescheduled'])
        status_combo.pack(pady=5)
        
        def update_status():
            if new_status.get():
                try:
                    conn = self.get_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute('UPDATE health_appointments SET status = ? WHERE id = ?', 
                                  (new_status.get(), apt_id))
                    conn.commit()
                    conn.close()
                    
                    self.log_audit_event('update_appointment_status', 'appointment', apt_id,
                                       f"Status changed from {current_status} to {new_status.get()}")
                    
                    messagebox.showinfo("Success", "Appointment status updated successfully!")
                    status_dialog.destroy()
                    self.load_appointments(self.apt_search_student.get().strip())
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update status: {str(e)}")
            else:
                messagebox.showwarning("Warning", "Please select a status")
        
        ttk.Button(status_dialog, text="Update", command=update_status).pack(pady=10)
        ttk.Button(status_dialog, text="Cancel", command=status_dialog.destroy).pack()
    
    def cancel_appointment(self):
        """Cancel selected appointment"""
        selection = self.apt_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an appointment to cancel.")
            return

        apt_id = self.apt_tree.item(selection[0])['values'][0]

        # Ask for cancellation reason
        cancellation_reason = simpledialog.askstring(
            "Cancellation Reason",
            "Please provide a reason for cancelling this appointment:",
            initialvalue="Patient request"
        )

        if not cancellation_reason:
            return

        if messagebox.askyesno("Confirm Cancellation", "Are you sure you want to cancel this appointment?"):
            try:
                conn = self.get_connection()
                cursor = conn.cursor()

                # Get appointment and patient details for email
                cursor.execute('''
                    SELECT ha.student_id, ha.appointment_date, ha.appointment_time,
                           ha.provider, ha.appointment_type, s.first_name, s.last_name, s.email
                    FROM health_appointments ha
                    JOIN students s ON ha.student_id = s.student_id
                    WHERE ha.id = ?
                ''', (apt_id,))

                appointment_info = cursor.fetchone()

                cursor.execute('UPDATE health_appointments SET status = ? WHERE id = ?',
                              ('cancelled', apt_id))
                conn.commit()
                conn.close()

                # Send cancellation confirmation email
                if appointment_info:
                    patient_name = f"{appointment_info[5]} {appointment_info[6]}"
                    patient_email = appointment_info[7]

                    appointment_details = {
                        'date': appointment_info[1],
                        'time': appointment_info[2],
                        'practitioner': appointment_info[3],
                        'department': appointment_info[4]
                    }

                    self.send_appointment_cancellation(patient_email, patient_name, appointment_details, cancellation_reason)

                self.log_audit_event('cancel_appointment', 'appointment', apt_id, f"Reason: {cancellation_reason}")
                messagebox.showinfo("Success", "Appointment cancelled successfully!\nCancellation email sent.")
                self.load_appointments(self.apt_search_student.get().strip())

            except Exception as e:
                messagebox.showerror("Error", f"Failed to cancel appointment: {str(e)}")

    # Reports and Analytics
    def create_health_reports(self):
        """Create health reports interface"""
        title = ttk.Label(self.content_frame, text="Health Reports & Analytics", style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)
        
        # Create notebook for different reports
        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Population Health tab
        population_tab = ttk.Frame(notebook)
        notebook.add(population_tab, text="Population Health")
        self.create_population_health_report(population_tab)
        
        # Vaccination Coverage tab
        vaccination_tab = ttk.Frame(notebook)
        notebook.add(vaccination_tab, text="Vaccination Coverage")
        self.create_vaccination_coverage_report(vaccination_tab)
        
        # Appointment Statistics tab
        appointment_tab = ttk.Frame(notebook)
        notebook.add(appointment_tab, text="Appointment Statistics")
        self.create_appointment_statistics_report(appointment_tab)
        
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)
    
    def create_population_health_report(self, parent):
        """Create population health metrics report"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Report controls
        controls_frame = ttk.LabelFrame(main_frame, text="Report Parameters", padding="5")
        controls_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(controls_frame, text="Date From:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.report_date_from = tk.StringVar(value=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))
        ttk.Entry(controls_frame, textvariable=self.report_date_from, width=15).grid(row=0, column=1, pady=2, padx=(5, 10))
        
        ttk.Label(controls_frame, text="Date To:").grid(row=0, column=2, sticky=tk.W, pady=2)
        self.report_date_to = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(controls_frame, textvariable=self.report_date_to, width=15).grid(row=0, column=3, pady=2, padx=(5, 10))
        
        ttk.Button(controls_frame, text="Generate Report", command=self.generate_population_report).grid(row=0, column=4, padx=10)
        
        # Report display
        report_frame = ttk.Frame(main_frame)
        report_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.population_report_text = scrolledtext.ScrolledText(report_frame, width=80, height=25, font=('Consolas', 10))
        self.population_report_text.pack(fill=tk.BOTH, expand=True)
        
        # Export button
        ttk.Button(main_frame, text="Export Report", command=self.export_population_report).grid(row=2, column=0, pady=10)
        
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Initial report generation
        self.generate_population_report()
    
    def generate_population_report(self):
        """Generate population health report"""
        try:
            self.population_report_text.delete(1.0, tk.END)
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Get date range
            date_from = self.report_date_from.get()
            date_to = self.report_date_to.get()
            
            report = []
            report.append("POPULATION HEALTH REPORT")
            report.append("=" * 50)
            report.append(f"Report Period: {date_from} to {date_to}")
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("")
            
            # Total students
            cursor.execute("SELECT COUNT(*) FROM students")
            total_students = cursor.fetchone()[0]
            report.append(f"Total Registered Students: {total_students}")
            report.append("")
            
            # Health records statistics
            cursor.execute("""
                SELECT COUNT(*) FROM health_records 
                WHERE record_date BETWEEN ? AND ?
            """, (date_from, date_to))
            health_records_count = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT record_type, COUNT(*) 
                FROM health_records 
                WHERE record_date BETWEEN ? AND ?
                GROUP BY record_type 
                ORDER BY COUNT(*) DESC
            """, (date_from, date_to))
            record_types = cursor.fetchall()
            
            report.append("HEALTH RECORDS ANALYSIS")
            report.append("-" * 30)
            report.append(f"Total Health Records: {health_records_count}")
            report.append("")
            report.append("Records by Type:")
            for record_type, count in record_types:
                percentage = (count / health_records_count * 100) if health_records_count > 0 else 0
                report.append(f"  {record_type}: {count} ({percentage:.1f}%)")
            report.append("")
            
            # Vaccination statistics
            cursor.execute("""
                SELECT COUNT(*) FROM vaccination_records 
                WHERE administered_date BETWEEN ? AND ?
            """, (date_from, date_to))
            vaccination_count = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT vaccine_name, COUNT(*) 
                FROM vaccination_records 
                WHERE administered_date BETWEEN ? AND ?
                GROUP BY vaccine_name 
                ORDER BY COUNT(*) DESC
            """, (date_from, date_to))
            vaccine_types = cursor.fetchall()
            
            report.append("VACCINATION ANALYSIS")
            report.append("-" * 30)
            report.append(f"Total Vaccinations Administered: {vaccination_count}")
            report.append("")
            if vaccine_types:
                report.append("Vaccinations by Type:")
                for vaccine, count in vaccine_types:
                    percentage = (count / vaccination_count * 100) if vaccination_count > 0 else 0
                    report.append(f"  {vaccine}: {count} ({percentage:.1f}%)")
            report.append("")
            
            # Appointment statistics
            cursor.execute("""
                SELECT COUNT(*) FROM health_appointments 
                WHERE appointment_date BETWEEN ? AND ?
            """, (date_from, date_to))
            appointment_count = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT status, COUNT(*) 
                FROM health_appointments 
                WHERE appointment_date BETWEEN ? AND ?
                GROUP BY status 
                ORDER BY COUNT(*) DESC
            """, (date_from, date_to))
            appointment_statuses = cursor.fetchall()
            
            report.append("APPOINTMENT ANALYSIS")
            report.append("-" * 30)
            report.append(f"Total Appointments: {appointment_count}")
            report.append("")
            if appointment_statuses:
                report.append("Appointments by Status:")
                for status, count in appointment_statuses:
                    percentage = (count / appointment_count * 100) if appointment_count > 0 else 0
                    report.append(f"  {status.title()}: {count} ({percentage:.1f}%)")
            report.append("")
            
            # Top health concerns
            cursor.execute("""
                SELECT record_type, COUNT(*) as frequency
                FROM health_records 
                WHERE record_date BETWEEN ? AND ?
                  AND record_type NOT IN ('General Medical', 'Annual Physical')
                GROUP BY record_type 
                ORDER BY COUNT(*) DESC
                LIMIT 5
            """, (date_from, date_to))
            top_concerns = cursor.fetchall()
            
            if top_concerns:
                report.append("TOP HEALTH CONCERNS")
                report.append("-" * 30)
                for i, (concern, count) in enumerate(top_concerns, 1):
                    report.append(f"{i}. {concern}: {count} cases")
                report.append("")
            
            # Monthly trends (if date range is more than 30 days)
            date_diff = (datetime.strptime(date_to, '%Y-%m-%d') - datetime.strptime(date_from, '%Y-%m-%d')).days
            if date_diff > 30:
                cursor.execute("""
                    SELECT strftime('%Y-%m', record_date) as month, COUNT(*) 
                    FROM health_records 
                    WHERE record_date BETWEEN ? AND ?
                    GROUP BY strftime('%Y-%m', record_date)
                    ORDER BY month
                """, (date_from, date_to))
                monthly_trends = cursor.fetchall()
                
                if monthly_trends:
                    report.append("MONTHLY HEALTH RECORD TRENDS")
                    report.append("-" * 30)
                    for month, count in monthly_trends:
                        report.append(f"{month}: {count} records")
                    report.append("")
            
            conn.close()
            
            # Display report
            self.population_report_text.insert(tk.END, "\n".join(report))
            
            self.log_audit_event('generate_population_report', 'report', 'population_health')
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")
    
    def export_population_report(self):
        """Export population health report to file"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Save Population Health Report"
            )
            
            if filename:
                report_content = self.population_report_text.get(1.0, tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                
                self.log_audit_event('export_population_report', 'report_export', filename)
                messagebox.showinfo("Success", f"Report exported to: {filename}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export report: {str(e)}")
    
    def create_vaccination_coverage_report(self, parent):
        """Create vaccination coverage report"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Report display
        self.vaccination_report_text = scrolledtext.ScrolledText(main_frame, width=80, height=25, font=('Consolas', 10))
        self.vaccination_report_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Generate button
        ttk.Button(main_frame, text="Generate Vaccination Coverage Report", 
                  command=self.generate_vaccination_report).grid(row=1, column=0, pady=10)
        
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # Initial report generation
        self.generate_vaccination_report()
    
    def generate_vaccination_report(self):
        """Generate vaccination coverage report"""
        try:
            self.vaccination_report_text.delete(1.0, tk.END)
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            report = []
            report.append("VACCINATION COVERAGE REPORT")
            report.append("=" * 50)
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("")
            
            # Total students
            cursor.execute("SELECT COUNT(*) FROM students")
            total_students = cursor.fetchone()[0]
            
            # Vaccination coverage by vaccine type
            cursor.execute("""
                SELECT vaccine_name, 
                       COUNT(DISTINCT student_id) as vaccinated_students,
                       COUNT(*) as total_doses
                FROM vaccination_records 
                GROUP BY vaccine_name 
                ORDER BY vaccinated_students DESC
            """)
            vaccine_coverage = cursor.fetchall()
            
            report.append("VACCINATION COVERAGE BY VACCINE TYPE")
            report.append("-" * 50)
            report.append(f"Total Students: {total_students}")
            report.append("")
            
            for vaccine, vaccinated, doses in vaccine_coverage:
                coverage_percentage = (vaccinated / total_students * 100) if total_students > 0 else 0
                avg_doses = doses / vaccinated if vaccinated > 0 else 0
                report.append(f"{vaccine}:")
                report.append(f"  Students Vaccinated: {vaccinated}/{total_students} ({coverage_percentage:.1f}%)")
                report.append(f"  Total Doses: {doses}")
                report.append(f"  Average Doses per Student: {avg_doses:.1f}")
                report.append("")
            
            # Students with no vaccination records
            cursor.execute("""
                SELECT COUNT(*) FROM students 
                WHERE student_id NOT IN (SELECT DISTINCT student_id FROM vaccination_records)
            """)
            unvaccinated_count = cursor.fetchone()[0]
            
            report.append("VACCINATION STATUS SUMMARY")
            report.append("-" * 30)
            report.append(f"Students with Vaccination Records: {total_students - unvaccinated_count}")
            report.append(f"Students with No Vaccination Records: {unvaccinated_count}")
            if total_students > 0:
                vaccinated_percentage = ((total_students - unvaccinated_count) / total_students * 100)
                report.append(f"Overall Vaccination Coverage: {vaccinated_percentage:.1f}%")
            report.append("")
            
            # Recent vaccinations (last 30 days)
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT vaccine_name, COUNT(*) 
                FROM vaccination_records 
                WHERE administered_date >= ?
                GROUP BY vaccine_name 
                ORDER BY COUNT(*) DESC
            """, (thirty_days_ago,))
            recent_vaccinations = cursor.fetchall()
            
            if recent_vaccinations:
                report.append("RECENT VACCINATIONS (Last 30 Days)")
                report.append("-" * 40)
                for vaccine, count in recent_vaccinations:
                    report.append(f"  {vaccine}: {count} doses")
                report.append("")
            
            # Adverse reactions
            cursor.execute("""
                SELECT vaccine_name, COUNT(*) as adverse_count,
                       (SELECT COUNT(*) FROM vaccination_records vr2 
                        WHERE vr2.vaccine_name = vr1.vaccine_name) as total_doses
                FROM vaccination_records vr1
                WHERE adverse_reaction = 1
                GROUP BY vaccine_name
                ORDER BY adverse_count DESC
            """)
            adverse_reactions = cursor.fetchall()
            
            if adverse_reactions:
                report.append("ADVERSE REACTIONS")
                report.append("-" * 20)
                for vaccine, adverse_count, total_doses in adverse_reactions:
                    adverse_rate = (adverse_count / total_doses * 100) if total_doses > 0 else 0
                    report.append(f"{vaccine}: {adverse_count}/{total_doses} ({adverse_rate:.2f}%)")
                report.append("")
            
            conn.close()
            
            # Display report
            self.vaccination_report_text.insert(tk.END, "\n".join(report))
            
            self.log_audit_event('generate_vaccination_report', 'report', 'vaccination_coverage')
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate vaccination report: {str(e)}")
    
    def create_appointment_statistics_report(self, parent):
        """Create appointment statistics report"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Report display
        self.appointment_report_text = scrolledtext.ScrolledText(main_frame, width=80, height=25, font=('Consolas', 10))
        self.appointment_report_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Generate button
        ttk.Button(main_frame, text="Generate Appointment Statistics Report", 
                  command=self.generate_appointment_report).grid(row=1, column=0, pady=10)
        
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # Initial report generation
        self.generate_appointment_report()
    
    def generate_appointment_report(self):
        """Generate appointment statistics report"""
        try:
            self.appointment_report_text.delete(1.0, tk.END)
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            report = []
            report.append("APPOINTMENT STATISTICS REPORT")
            report.append("=" * 50)
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("")
            
            # Total appointments
            cursor.execute("SELECT COUNT(*) FROM health_appointments")
            total_appointments = cursor.fetchone()[0]
            
            # Appointments by status
            cursor.execute("""
                SELECT status, COUNT(*) 
                FROM health_appointments 
                GROUP BY status 
                ORDER BY COUNT(*) DESC
            """)
            status_breakdown = cursor.fetchall()
            
            report.append("APPOINTMENT STATUS BREAKDOWN")
            report.append("-" * 35)
            report.append(f"Total Appointments: {total_appointments}")
            report.append("")
            
            for status, count in status_breakdown:
                percentage = (count / total_appointments * 100) if total_appointments > 0 else 0
                report.append(f"{status.title()}: {count} ({percentage:.1f}%)")
            report.append("")
            
            # Appointments by type
            cursor.execute("""
                SELECT appointment_type, COUNT(*) 
                FROM health_appointments 
                GROUP BY appointment_type 
                ORDER BY COUNT(*) DESC
            """)
            type_breakdown = cursor.fetchall()
            
            report.append("APPOINTMENT TYPE BREAKDOWN")
            report.append("-" * 30)
            for apt_type, count in type_breakdown:
                percentage = (count / total_appointments * 100) if total_appointments > 0 else 0
                report.append(f"{apt_type}: {count} ({percentage:.1f}%)")
            report.append("")
            
            # Provider workload
            cursor.execute("""
                SELECT provider, COUNT(*) 
                FROM health_appointments 
                GROUP BY provider 
                ORDER BY COUNT(*) DESC
            """)
            provider_workload = cursor.fetchall()
            
            report.append("PROVIDER WORKLOAD")
            report.append("-" * 20)
            for provider, count in provider_workload:
                percentage = (count / total_appointments * 100) if total_appointments > 0 else 0
                report.append(f"{provider}: {count} appointments ({percentage:.1f}%)")
            report.append("")
            
            # Monthly appointment trends
            cursor.execute("""
                SELECT strftime('%Y-%m', appointment_date) as month, COUNT(*) 
                FROM health_appointments 
                WHERE appointment_date >= date('now', '-12 months')
                GROUP BY strftime('%Y-%m', appointment_date)
                ORDER BY month
            """)
            monthly_trends = cursor.fetchall()
            
            if monthly_trends:
                report.append("MONTHLY APPOINTMENT TRENDS (Last 12 Months)")
                report.append("-" * 45)
                for month, count in monthly_trends:
                    report.append(f"{month}: {count} appointments")
                report.append("")
            
            # No-show rate
            cursor.execute("SELECT COUNT(*) FROM health_appointments WHERE status = 'no-show'")
            no_shows = cursor.fetchone()[0]
            no_show_rate = (no_shows / total_appointments * 100) if total_appointments > 0 else 0
            
            # Cancellation rate
            cursor.execute("SELECT COUNT(*) FROM health_appointments WHERE status = 'cancelled'")
            cancellations = cursor.fetchone()[0]
            cancellation_rate = (cancellations / total_appointments * 100) if total_appointments > 0 else 0
            
            report.append("APPOINTMENT RELIABILITY METRICS")
            report.append("-" * 35)
            report.append(f"No-Show Rate: {no_show_rate:.1f}% ({no_shows} appointments)")
            report.append(f"Cancellation Rate: {cancellation_rate:.1f}% ({cancellations} appointments)")
            
            conn.close()
            
            # Display report
            self.appointment_report_text.insert(tk.END, "\n".join(report))
            
            self.log_audit_event('generate_appointment_report', 'report', 'appointment_statistics')
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate appointment report: {str(e)}")
    
    # Security Audit
    def create_security_audit(self):
        """Create security audit interface"""
        title = ttk.Label(self.content_frame, text="Security Audit", style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)
        
        # Create notebook for security features
        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Audit Log tab
        audit_tab = ttk.Frame(notebook)
        notebook.add(audit_tab, text="Audit Log")
        self.create_audit_log_viewer(audit_tab)
        
        # Access Summary tab
        summary_tab = ttk.Frame(notebook)
        notebook.add(summary_tab, text="Access Summary")
        self.create_access_summary(summary_tab)
        
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)
    
    def create_audit_log_viewer(self, parent):
        """Create audit log viewer"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Filters
        filter_frame = ttk.LabelFrame(main_frame, text="Filters", padding="5")
        filter_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(filter_frame, text="User ID:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.audit_user_filter = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.audit_user_filter, width=15).grid(row=0, column=1, pady=2, padx=(5, 10))
        
        ttk.Label(filter_frame, text="Action:").grid(row=0, column=2, sticky=tk.W, pady=2)
        self.audit_action_filter = tk.StringVar()
        action_combo = ttk.Combobox(filter_frame, textvariable=self.audit_action_filter, width=15,
                                   values=['', 'login', 'logout', 'add_health_record', 'view_health_record',
                                          'schedule_appointment', 'record_vaccination'])
        action_combo.grid(row=0, column=3, pady=2, padx=(5, 10))
        
        ttk.Button(filter_frame, text="Filter", command=self.filter_audit_log).grid(row=0, column=4, padx=5)
        ttk.Button(filter_frame, text="Clear", command=self.clear_audit_filters).grid(row=0, column=5, padx=5)
        
        # Audit log display
        self.audit_log_text = scrolledtext.ScrolledText(main_frame, width=100, height=20, font=('Consolas', 9))
        self.audit_log_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Export button
        ttk.Button(main_frame, text="Export Audit Log", command=self.export_audit_log).grid(row=2, column=0, pady=10)
        
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Load initial audit log
        self.load_audit_log()
    
    def load_audit_log(self):
        """Load audit log from file"""
        try:
            log_file = os.path.join("logs", "health_portal_audit.log")
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_content = f.read()
                
                self.audit_log_text.delete(1.0, tk.END)
                self.audit_log_text.insert(tk.END, log_content)
                
                # Scroll to bottom to show most recent entries
                self.audit_log_text.see(tk.END)
            else:
                self.audit_log_text.delete(1.0, tk.END)
                self.audit_log_text.insert(tk.END, "No audit log file found. Audit events will be logged here as they occur.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load audit log: {str(e)}")
    
    def filter_audit_log(self):
        """Filter audit log based on criteria"""
        user_filter = self.audit_user_filter.get().strip()
        action_filter = self.audit_action_filter.get().strip()
        
        if not user_filter and not action_filter:
            self.load_audit_log()
            return
        
        try:
            log_file = os.path.join("logs", "health_portal_audit.log")
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                filtered_lines = []
                for line in lines:
                    include_line = True
                    
                    if user_filter and f"USER:{user_filter}" not in line:
                        include_line = False
                    
                    if action_filter and f"ACTION:{action_filter}" not in line:
                        include_line = False
                    
                    if include_line:
                        filtered_lines.append(line)
                
                self.audit_log_text.delete(1.0, tk.END)
                self.audit_log_text.insert(tk.END, ''.join(filtered_lines))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to filter audit log: {str(e)}")
    
    def clear_audit_filters(self):
        """Clear audit log filters"""
        self.audit_user_filter.set("")
        self.audit_action_filter.set("")
        self.load_audit_log()
    
    def export_audit_log(self):
        """Export audit log to file"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".log",
                filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
                title="Save Audit Log"
            )
            
            if filename:
                log_content = self.audit_log_text.get(1.0, tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                
                self.log_audit_event('export_audit_log', 'audit_export', filename)
                messagebox.showinfo("Success", f"Audit log exported to: {filename}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export audit log: {str(e)}")
    
    def create_access_summary(self, parent):
        """Create access summary report"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Summary display
        self.access_summary_text = scrolledtext.ScrolledText(main_frame, width=80, height=25, font=('Consolas', 10))
        self.access_summary_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Generate button
        ttk.Button(main_frame, text="Generate Access Summary", command=self.generate_access_summary).grid(row=1, column=0, pady=10)
        
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # Initial summary generation
        self.generate_access_summary()
    
    def generate_access_summary(self):
        """Generate access summary report"""
        try:
            self.access_summary_text.delete(1.0, tk.END)
            
            report = []
            report.append("SYSTEM ACCESS SUMMARY")
            report.append("=" * 30)
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("")
            
            # Parse audit log for access patterns
            log_file = os.path.join("logs", "health_portal_audit.log")
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        log_content = f.read()
                    
                    # Count different types of activities
                    login_count = log_content.count("ACTION:login")
                    logout_count = log_content.count("ACTION:logout")
                    health_record_access = log_content.count("ACTION:add_health_record") + log_content.count("ACTION:view_health_record")
                    appointment_access = log_content.count("ACTION:schedule_appointment")
                    vaccination_access = log_content.count("ACTION:record_vaccination")
                    
                    report.append("ACTIVITY SUMMARY")
                    report.append("-" * 20)
                    report.append(f"Login Events: {login_count}")
                    report.append(f"Logout Events: {logout_count}")
                    report.append(f"Health Record Access: {health_record_access}")
                    report.append(f"Appointment Activities: {appointment_access}")
                    report.append(f"Vaccination Activities: {vaccination_access}")
                    report.append("")
                    
                    # Extract user activities
                    users = {}
                    for line in log_content.split('\n'):
                        if 'USER:' in line and 'ACTION:' in line:
                            try:
                                user_part = line.split('USER:')[1].split(' ')[0]
                                action_part = line.split('ACTION:')[1].split(' ')[0]
                                if user_part not in users:
                                    users[user_part] = {}
                                if action_part not in users[user_part]:
                                    users[user_part][action_part] = 0
                                users[user_part][action_part] += 1
                            except:
                                continue
                    
                    if users:
                        report.append("USER ACTIVITY BREAKDOWN")
                        report.append("-" * 25)
                        for user, actions in users.items():
                            report.append(f"{user}:")
                            for action, count in actions.items():
                                report.append(f"  {action}: {count}")
                            report.append("")
                    
                except Exception as e:
                    report.append(f"Error reading audit log: {str(e)}")
                    report.append("")
            else:
                report.append("No audit log file found.")
                report.append("")
            
            # Database access summary
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                # Get table record counts
                tables = ['students', 'health_records', 'vaccination_records', 'health_appointments']
                report.append("DATABASE SUMMARY")
                report.append("-" * 20)
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    report.append(f"{table.replace('_', ' ').title()}: {count} records")
                
                conn.close()
                report.append("")
                
            except Exception as e:
                report.append(f"Error accessing database: {str(e)}")
                report.append("")
            
            # Security recommendations
            report.append("SECURITY RECOMMENDATIONS")
            report.append("-" * 25)
            report.append("• Regularly review audit logs for suspicious activity")
            report.append("• Monitor failed login attempts")
            report.append("• Ensure strong password policies are enforced")
            report.append("• Implement session timeouts")
            report.append("• Regular backup of audit logs")
            report.append("• Review user access permissions periodically")
            
            # Display report
            self.access_summary_text.insert(tk.END, "\n".join(report))
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate access summary: {str(e)}")
    
    # Data Management
    def create_data_management(self):
        """Create data management interface"""
        title = ttk.Label(self.content_frame, text="Data Management", style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)
        
        # Create notebook for data management features
        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Data Export tab
        export_tab = ttk.Frame(notebook)
        notebook.add(export_tab, text="Data Export")
        self.create_data_export_form(export_tab)
        
        # Database Backup tab
        backup_tab = ttk.Frame(notebook)
        notebook.add(backup_tab, text="Database Backup")
        self.create_database_backup_form(backup_tab)
        
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)
    
    def create_data_export_form(self, parent):
        """Create data export form"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Export options
        options_frame = ttk.LabelFrame(main_frame, text="Export Options", padding="10")
        options_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(options_frame, text="Data Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.export_data_type = tk.StringVar(value="health_records")
        data_type_combo = ttk.Combobox(options_frame, textvariable=self.export_data_type, 
                                      values=['health_records', 'vaccination_records', 'health_appointments', 
                                             'students', 'all_data'], state='readonly')
        data_type_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(options_frame, text="Format:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.export_format = tk.StringVar(value="CSV")
        format_combo = ttk.Combobox(options_frame, textvariable=self.export_format, 
                                   values=['CSV', 'JSON'], state='readonly')
        format_combo.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        # Date range (optional)
        ttk.Label(options_frame, text="Date From (optional):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.export_date_from = tk.StringVar()
        ttk.Entry(options_frame, textvariable=self.export_date_from, width=15).grid(row=2, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        ttk.Label(options_frame, text="Date To (optional):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.export_date_to = tk.StringVar()
        ttk.Entry(options_frame, textvariable=self.export_date_to, width=15).grid(row=3, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        # Export button
        ttk.Button(options_frame, text="Export Data", command=self.export_data).grid(row=4, column=0, columnspan=2, pady=15)
        
        # Export log
        log_frame = ttk.LabelFrame(main_frame, text="Export Log", padding="10")
        log_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.export_log_text = scrolledtext.ScrolledText(log_frame, width=70, height=15)
        self.export_log_text.pack(fill=tk.BOTH, expand=True)
        
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
    
    def export_data(self):
        """Export data based on selected options"""
        try:
            data_type = self.export_data_type.get()
            export_format = self.export_format.get()
            date_from = self.export_date_from.get().strip()
            date_to = self.export_date_to.get().strip()
            
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            extension = '.csv' if export_format == 'CSV' else '.json'
            default_filename = f"{data_type}_export_{timestamp}{extension}"
            
            filename = filedialog.asksaveasfilename(
                initialfilename=default_filename,
                defaultextension=extension,
                filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json"), ("All files", "*.*")],
                title="Save Export File"
            )
            
            if not filename:
                return
            
            self.export_log_text.insert(tk.END, f"Starting export of {data_type} to {filename}...\n")
            self.export_log_text.see(tk.END)
            self.root.update()
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Build query based on data type
            if data_type == 'health_records':
                query = '''
                    SELECT hr.id, hr.student_id, s.first_name, s.last_name, hr.record_type,
                           hr.record_date, hr.provider, hr.description, hr.confidential, hr.created_at
                    FROM health_records hr
                    JOIN students s ON hr.student_id = s.student_id
                '''
                headers = ['ID', 'Student ID', 'First Name', 'Last Name', 'Record Type', 
                          'Record Date', 'Provider', 'Description', 'Confidential', 'Created At']
                date_column = 'hr.record_date'
                
            elif data_type == 'vaccination_records':
                query = '''
                    SELECT vr.id, vr.student_id, s.first_name, s.last_name, vr.vaccine_name,
                           vr.administered_date, vr.lot_number, vr.manufacturer, vr.administered_by,
                           vr.adverse_reaction, vr.verified, vr.created_at
                    FROM vaccination_records vr
                    JOIN students s ON vr.student_id = s.student_id
                '''
                headers = ['ID', 'Student ID', 'First Name', 'Last Name', 'Vaccine Name',
                          'Administered Date', 'Lot Number', 'Manufacturer', 'Administered By',
                          'Adverse Reaction', 'Verified', 'Created At']
                date_column = 'vr.administered_date'
                
            elif data_type == 'health_appointments':
                query = '''
                    SELECT ha.id, ha.student_id, s.first_name, s.last_name, ha.appointment_type,
                           ha.appointment_date, ha.appointment_time, ha.provider, ha.reason,
                           ha.status, ha.scheduled_at
                    FROM health_appointments ha
                    JOIN students s ON ha.student_id = s.student_id
                '''
                headers = ['ID', 'Student ID', 'First Name', 'Last Name', 'Appointment Type',
                          'Appointment Date', 'Appointment Time', 'Provider', 'Reason',
                          'Status', 'Scheduled At']
                date_column = 'ha.appointment_date'
                
            elif data_type == 'students':
                query = '''
                    SELECT student_id, first_name, last_name, age, gender, email, phone
                    FROM students
                '''
                headers = ['Student ID', 'First Name', 'Last Name', 'Age', 'Gender', 'Email', 'Phone']
                date_column = None
                
            # Add date filters if specified
            params = []
            if date_column and (date_from or date_to):
                if date_from and date_to:
                    query += f" WHERE {date_column} BETWEEN ? AND ?"
                    params = [date_from, date_to]
                elif date_from:
                    query += f" WHERE {date_column} >= ?"
                    params = [date_from]
                elif date_to:
                    query += f" WHERE {date_column} <= ?"
                    params = [date_to]
            
            query += " ORDER BY " + (date_column or headers[0])
            
            cursor.execute(query, params)
            data = cursor.fetchall()
            
            self.export_log_text.insert(tk.END, f"Retrieved {len(data)} records...\n")
            self.export_log_text.see(tk.END)
            self.root.update()
            
            # Export based on format
            if export_format == 'CSV':
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(headers)
                    writer.writerows(data)
                    
            elif export_format == 'JSON':
                json_data = []
                for row in data:
                    record = dict(zip(headers, row))
                    json_data.append(record)
                
                with open(filename, 'w', encoding='utf-8') as jsonfile:
                    json.dump(json_data, jsonfile, indent=2, default=str)
            
            conn.close()
            
            self.export_log_text.insert(tk.END, f"Export completed successfully!\n")
            self.export_log_text.insert(tk.END, f"File saved: {filename}\n")
            self.export_log_text.insert(tk.END, f"Records exported: {len(data)}\n\n")
            self.export_log_text.see(tk.END)
            
            self.log_audit_event('export_data', 'data_export', filename, f"Type: {data_type}, Format: {export_format}")
            messagebox.showinfo("Success", f"Data exported successfully to {filename}")
            
        except Exception as e:
            error_msg = f"Export failed: {str(e)}\n\n"
            self.export_log_text.insert(tk.END, error_msg)
            self.export_log_text.see(tk.END)
            messagebox.showerror("Error", f"Failed to export data: {str(e)}")
    
    def create_database_backup_form(self, parent):
        """Create database backup form"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Backup options
        options_frame = ttk.LabelFrame(main_frame, text="Backup Options", padding="10")
        options_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(options_frame, text="Backup Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.backup_type = tk.StringVar(value="Full Backup")
        backup_type_combo = ttk.Combobox(options_frame, textvariable=self.backup_type, 
                                        values=['Full Backup', 'Data Only', 'Schema Only'], state='readonly')
        backup_type_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        # Backup location
        ttk.Label(options_frame, text="Backup Location:").grid(row=1, column=0, sticky=tk.W, pady=5)
        from university_system.modules.shared.constants import paths
        self.backup_location = tk.StringVar(value=str(paths.BACKUP_DIR / ""))
        
        location_frame = ttk.Frame(options_frame)
        location_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        ttk.Entry(location_frame, textvariable=self.backup_location, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(location_frame, text="Browse", command=self.browse_backup_location).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Create backup button
        ttk.Button(options_frame, text="Create Backup", command=self.create_backup).grid(row=2, column=0, columnspan=2, pady=15)
        
        # Backup log
        log_frame = ttk.LabelFrame(main_frame, text="Backup Log", padding="10")
        log_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.backup_log_text = scrolledtext.ScrolledText(log_frame, width=70, height=15)
        self.backup_log_text.pack(fill=tk.BOTH, expand=True)
        
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        options_frame.columnconfigure(1, weight=1)
        location_frame.columnconfigure(0, weight=1)
        
        # Initial log message
        self.backup_log_text.insert(tk.END, "Ready to create database backup...\n")
    
    def browse_backup_location(self):
        """Browse for backup location"""
        location = filedialog.askdirectory(initialdir=self.backup_location.get())
        if location:
            self.backup_location.set(location + "/")
    
    def create_backup(self):
        """Create database backup"""
        try:
            backup_dir = self.backup_location.get()
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"health_portal_backup_{timestamp}.sql"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            self.backup_log_text.insert(tk.END, f"Starting backup to {backup_path}...\n")
            self.backup_log_text.see(tk.END)
            self.root.update()
            
            # Simple SQLite backup approach - copy database file
            source_db = str(DEFAULT_DB_PATH)
            if os.path.exists(source_db):
                import shutil
                backup_db_path = os.path.join(backup_dir, f"student_records_backup_{timestamp}.db")
                shutil.copy2(source_db, backup_db_path)
                
                # Also create a SQL dump for portability
                conn = self.get_connection()
                with open(backup_path, 'w', encoding='utf-8') as f:
                    for line in conn.iterdump():
                        f.write('%s\n' % line)
                conn.close()
                
                file_size = os.path.getsize(backup_path) / 1024  # KB
                
                self.backup_log_text.insert(tk.END, f"Backup completed successfully!\n")
                self.backup_log_text.insert(tk.END, f"SQL dump: {backup_path}\n")
                self.backup_log_text.insert(tk.END, f"Database copy: {backup_db_path}\n")
                self.backup_log_text.insert(tk.END, f"Size: {file_size:.1f} KB\n\n")
                self.backup_log_text.see(tk.END)
                
                self.log_audit_event('create_backup', 'database_backup', backup_path)
                messagebox.showinfo("Success", f"Database backup created successfully!\n\n"
                                  f"SQL dump: {backup_path}\n"
                                  f"Database copy: {backup_db_path}")
                
            else:
                raise Exception("Database file not found")
                
        except Exception as e:
            error_msg = f"Backup failed: {str(e)}\n\n"
            self.backup_log_text.insert(tk.END, error_msg)
            self.backup_log_text.see(tk.END)
            messagebox.showerror("Error", f"Failed to create backup: {str(e)}")

    def create_generate_health_reports(self):
        """Generate various health reports for the user"""
        content_frame = ttk.Frame(self.content_area)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(content_frame, text="Health Reports Generator",
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))

        # Report type selection
        report_frame = ttk.LabelFrame(content_frame, text="Select Report Type", padding=15)
        report_frame.pack(fill=tk.X, pady=(0, 20))

        self.report_type = tk.StringVar(value="immunization")

        ttk.Radiobutton(report_frame, text="Immunization Status Report",
                       variable=self.report_type, value="immunization").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(report_frame, text="Health Summary Report",
                       variable=self.report_type, value="health_summary").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(report_frame, text="Appointment History Report",
                       variable=self.report_type, value="appointment_history").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(report_frame, text="Medical History Report",
                       variable=self.report_type, value="medical_history").pack(anchor=tk.W, pady=2)

        # Generate button
        button_frame = ttk.Frame(content_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Generate Report",
                  command=self.generate_selected_report).pack(side=tk.LEFT, padx=(0, 10))

        # Report display area
        report_display_frame = ttk.LabelFrame(content_frame, text="Generated Report", padding=15)
        report_display_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

        self.report_text = scrolledtext.ScrolledText(report_display_frame, wrap=tk.WORD, height=15)
        self.report_text.pack(fill=tk.BOTH, expand=True)

    def generate_selected_report(self):
        """Generate the selected type of health report"""
        if not self.auth.check_permission('view_health_records'):
            messagebox.showerror("Access Denied", "You don't have permission to generate health reports.")
            return

        report_type = self.report_type.get()

        try:
            self.report_text.delete(1.0, tk.END)

            if report_type == "immunization":
                self.generate_immunization_report()
            elif report_type == "health_summary":
                self.generate_health_summary_report()
            elif report_type == "appointment_history":
                self.generate_appointment_history_report()
            elif report_type == "medical_history":
                self.generate_medical_history_report()

            self.log_audit_event('generate_report', 'health_report', report_type)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

    def generate_immunization_report(self):
        """Generate immunization status report"""
        user_id = self.auth.current_user['id']

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT vaccine_name, vaccination_date, dose_number, next_due_date, provider
                FROM vaccinations
                WHERE user_id = ?
                ORDER BY vaccination_date DESC
                """, [user_id])

                vaccinations = cursor.fetchall()

                report = f"IMMUNIZATION STATUS REPORT\n"
                report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                report += f"Patient: {user_id}\n"
                report += "=" * 60 + "\n\n"

                if vaccinations:
                    for vac in vaccinations:
                        report += f"Vaccine: {vac[0]}\n"
                        report += f"Date: {vac[1]}\n"
                        report += f"Dose: {vac[2] or 'N/A'}\n"
                        report += f"Next Due: {vac[3] or 'N/A'}\n"
                        report += f"Provider: {vac[4] or 'Not specified'}\n"
                        report += "-" * 40 + "\n"
                else:
                    report += "No vaccination records found.\n"

                self.report_text.insert(tk.END, report)
        except Exception as e:
            self.report_text.insert(tk.END, f"Error generating immunization report: {str(e)}")

    def generate_health_summary_report(self):
        """Generate comprehensive health summary report"""
        user_id = self.auth.current_user['id']

        report = f"HEALTH SUMMARY REPORT\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"Patient: {user_id}\n"
        report += "=" * 60 + "\n\n"

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Health records summary
                cursor.execute("""
                SELECT record_type, COUNT(*) as count, MAX(created_date) as latest
                FROM health_records
                WHERE user_id = ?
                GROUP BY record_type ORDER BY latest DESC
                """, [user_id])

                records = cursor.fetchall()

                report += "HEALTH RECORDS SUMMARY:\n"
                if records:
                    for record in records:
                        report += f"- {record[0]}: {record[1]} records (Latest: {record[2]})\n"
                else:
                    report += "No health records found.\n"

                # Vaccination summary
                cursor.execute("""
                SELECT COUNT(*) as total_vaccines, MAX(vaccination_date) as latest_vaccine
                FROM vaccinations WHERE user_id = ?
                """, [user_id])

                vac_summary = cursor.fetchone()
                report += f"\nVACCINATION SUMMARY:\n"
                report += f"Total Vaccinations: {vac_summary[0] if vac_summary else 0}\n"
                report += f"Latest Vaccination: {vac_summary[1] if vac_summary and vac_summary[1] else 'None'}\n\n"

                self.report_text.insert(tk.END, report)
        except Exception as e:
            self.report_text.insert(tk.END, f"Error generating health summary: {str(e)}")

    def generate_appointment_history_report(self):
        """Generate appointment history report"""
        user_id = self.auth.current_user['id']

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT appointment_date, appointment_time, appointment_type, provider, status, notes
                FROM appointments
                WHERE user_id = ?
                ORDER BY appointment_date DESC, appointment_time DESC
                """, [user_id])

                appointments = cursor.fetchall()

                report = f"APPOINTMENT HISTORY REPORT\n"
                report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                report += f"Patient: {user_id}\n"
                report += "=" * 60 + "\n\n"

                if appointments:
                    for apt in appointments:
                        report += f"Date: {apt[0]} at {apt[1]}\n"
                        report += f"Type: {apt[2]}\n"
                        report += f"Provider: {apt[3] or 'Not specified'}\n"
                        report += f"Status: {apt[4]}\n"
                        if apt[5]:
                            report += f"Notes: {apt[5]}\n"
                        report += "-" * 40 + "\n"
                else:
                    report += "No appointment history found.\n"

                self.report_text.insert(tk.END, report)
        except Exception as e:
            self.report_text.insert(tk.END, f"Error generating appointment history: {str(e)}")

    def generate_medical_history_report(self):
        """Generate medical history report"""
        user_id = self.auth.current_user['id']

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT record_type, condition_name, diagnosis_date, treatment, provider, notes
                FROM health_records
                WHERE user_id = ? AND record_type IN ('medical_history', 'diagnosis', 'treatment')
                ORDER BY diagnosis_date DESC
                """, [user_id])

                records = cursor.fetchall()

                report = f"MEDICAL HISTORY REPORT\n"
                report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                report += f"Patient: {user_id}\n"
                report += "=" * 60 + "\n\n"

                if records:
                    for record in records:
                        report += f"Type: {record[0]}\n"
                        report += f"Condition: {record[1] or 'Not specified'}\n"
                        report += f"Date: {record[2] or 'Not specified'}\n"
                        report += f"Treatment: {record[3] or 'Not specified'}\n"
                        report += f"Provider: {record[4] or 'Not specified'}\n"
                        if record[5]:
                            report += f"Notes: {record[5]}\n"
                        report += "-" * 40 + "\n"
                else:
                    report += "No medical history found.\n"

                self.report_text.insert(tk.END, report)
        except Exception as e:
            self.report_text.insert(tk.END, f"Error generating medical history: {str(e)}")

    def create_manage_emergency_contacts(self):
        """Manage emergency contacts interface"""
        content_frame = ttk.Frame(self.content_area)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(content_frame, text="Emergency Contacts Management",
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))

        # Contact form
        form_frame = ttk.LabelFrame(content_frame, text="Add Emergency Contact", padding=15)
        form_frame.pack(fill=tk.X, pady=(0, 20))

        # Form fields in a grid
        ttk.Label(form_frame, text="Full Name:*").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.contact_name = ttk.Entry(form_frame, width=25)
        self.contact_name.grid(row=0, column=1, sticky=tk.W, padx=(10, 20), pady=5)

        ttk.Label(form_frame, text="Relationship:*").grid(row=0, column=2, sticky=tk.W, pady=5)
        self.contact_relationship = ttk.Combobox(form_frame, width=22, values=[
            "Parent", "Guardian", "Spouse", "Sibling", "Relative", "Friend", "Other"
        ])
        self.contact_relationship.grid(row=0, column=3, sticky=tk.W, padx=(10, 0), pady=5)

        ttk.Label(form_frame, text="Phone Number:*").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.contact_phone = ttk.Entry(form_frame, width=25)
        self.contact_phone.grid(row=1, column=1, sticky=tk.W, padx=(10, 20), pady=5)

        ttk.Label(form_frame, text="Email:").grid(row=1, column=2, sticky=tk.W, pady=5)
        self.contact_email = ttk.Entry(form_frame, width=22)
        self.contact_email.grid(row=1, column=3, sticky=tk.W, padx=(10, 0), pady=5)

        # Buttons
        button_frame = ttk.Frame(content_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Add Contact",
                  command=self.save_emergency_contact).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Clear Form",
                  command=self.clear_contact_form).pack(side=tk.LEFT)

        # Display area for current contacts
        display_frame = ttk.LabelFrame(content_frame, text="Current Emergency Contacts", padding=15)
        display_frame.pack(fill=tk.BOTH, expand=True)

        self.contacts_text = scrolledtext.ScrolledText(display_frame, wrap=tk.WORD, height=10)
        self.contacts_text.pack(fill=tk.BOTH, expand=True)

        # Load existing contacts
        self.load_emergency_contacts_display()

    def save_emergency_contact(self):
        """Save new emergency contact"""
        if not self.validate_contact_form():
            return

        try:
            contact_info = f"Name: {self.contact_name.get()}\n"
            contact_info += f"Relationship: {self.contact_relationship.get()}\n"
            contact_info += f"Phone: {self.contact_phone.get()}\n"
            contact_info += f"Email: {self.contact_email.get()}\n"
            contact_info += f"Added: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            contact_info += "-" * 40 + "\n"

            self.contacts_text.insert(tk.END, contact_info)
            self.clear_contact_form()
            messagebox.showinfo("Success", "Emergency contact added successfully!")
            self.log_audit_event('add_emergency_contact', 'emergency_contact', self.contact_name.get())

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save emergency contact: {str(e)}")

    def validate_contact_form(self):
        """Validate emergency contact form"""
        if not self.contact_name.get().strip():
            messagebox.showerror("Validation Error", "Contact name is required.")
            return False

        if not self.contact_relationship.get():
            messagebox.showerror("Validation Error", "Relationship is required.")
            return False

        if not self.contact_phone.get().strip():
            messagebox.showerror("Validation Error", "Phone number is required.")
            return False

        return True

    def clear_contact_form(self):
        """Clear the emergency contact form"""
        self.contact_name.delete(0, tk.END)
        self.contact_relationship.set('')
        self.contact_phone.delete(0, tk.END)
        self.contact_email.delete(0, tk.END)

    def load_emergency_contacts_display(self):
        """Load and display emergency contacts"""
        try:
            # This would typically load from database, for now show placeholder
            placeholder_text = "Emergency contacts will be displayed here.\n"
            placeholder_text += "Use the form above to add new emergency contacts.\n"
            self.contacts_text.insert(tk.END, placeholder_text)
        except Exception as e:
            self.contacts_text.insert(tk.END, f"Error loading contacts: {str(e)}")

    def create_view_vaccination_records(self):
        """View and manage vaccination records"""
        content_frame = ttk.Frame(self.content_area)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(content_frame, text="Vaccination Records",
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))

        # Quick add vaccination form
        add_frame = ttk.LabelFrame(content_frame, text="Add Vaccination Record", padding=15)
        add_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(add_frame, text="Vaccine Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.vaccine_name = ttk.Combobox(add_frame, width=25, values=[
            "COVID-19", "Influenza (Flu)", "Hepatitis B", "MMR", "Tdap", "Meningococcal", "HPV", "Other"
        ])
        self.vaccine_name.grid(row=0, column=1, sticky=tk.W, padx=(10, 20), pady=5)

        ttk.Label(add_frame, text="Date:").grid(row=0, column=2, sticky=tk.W, pady=5)
        self.vaccine_date = ttk.Entry(add_frame, width=15)
        self.vaccine_date.grid(row=0, column=3, sticky=tk.W, padx=(10, 0), pady=5)
        self.vaccine_date.insert(0, datetime.now().strftime('%Y-%m-%d'))

        ttk.Button(add_frame, text="Add Vaccination",
                  command=self.add_vaccination_record).grid(row=0, column=4, padx=(20, 0))

        # Vaccination status display
        status_frame = ttk.LabelFrame(content_frame, text="Current Vaccination Status", padding=15)
        status_frame.pack(fill=tk.BOTH, expand=True)

        self.vaccination_text = scrolledtext.ScrolledText(status_frame, wrap=tk.WORD, height=15)
        self.vaccination_text.pack(fill=tk.BOTH, expand=True)

        # Load vaccination records
        self.load_vaccination_display()

    def add_vaccination_record(self):
        """Add a new vaccination record"""
        if not self.vaccine_name.get().strip():
            messagebox.showerror("Validation Error", "Vaccine name is required.")
            return

        if not self.vaccine_date.get().strip():
            messagebox.showerror("Validation Error", "Vaccination date is required.")
            return

        try:
            vac_info = f"Vaccine: {self.vaccine_name.get()}\n"
            vac_info += f"Date: {self.vaccine_date.get()}\n"
            vac_info += f"Status: Current\n"
            vac_info += f"Recorded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            vac_info += "-" * 40 + "\n"

            self.vaccination_text.insert(tk.END, vac_info)

            # Clear form
            self.vaccine_name.set('')
            self.vaccine_date.delete(0, tk.END)
            self.vaccine_date.insert(0, datetime.now().strftime('%Y-%m-%d'))

            messagebox.showinfo("Success", "Vaccination record added successfully!")
            self.log_audit_event('add_vaccination', 'vaccination', self.vaccine_name.get())

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add vaccination record: {str(e)}")

    def load_vaccination_display(self):
        """Load and display vaccination records"""
        try:
            # Load real vaccination data from database
            import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Get user ID (assuming self.current_user contains user info)
                user_id = getattr(self, 'current_user_id', None)
                if not user_id and hasattr(self, 'current_user'):
                    user_id = self.current_user.get('id') if isinstance(self.current_user, dict) else None

                display_data = f"VACCINATION RECORDS\n"
                display_data += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                display_data += "=" * 50 + "\n\n"

                if user_id:
                    # Try to get vaccination records
                    cursor.execute("""
                        SELECT vaccine_name, vaccination_date, status, next_due_date, notes
                        FROM health_records
                        WHERE student_id = ? AND record_type = 'vaccination'
                        ORDER BY vaccination_date DESC
                    """, (user_id,))
                    vaccination_records = cursor.fetchall()

                    # If no health_records table, try vaccinations table
                    if not vaccination_records:
                        cursor.execute("""
                            SELECT vaccine_name, vaccination_date, status, next_due_date, notes
                            FROM vaccinations
                            WHERE student_id = ?
                            ORDER BY vaccination_date DESC
                        """, (user_id,))
                        vaccination_records = cursor.fetchall()

                    if vaccination_records:
                        display_data += "Your vaccination records:\n\n"
                        for record in vaccination_records:
                            vaccine_name, vac_date, status, next_due, notes = record
                            display_data += f"{vaccine_name}: {status or 'Recorded'}"
                            if vac_date:
                                display_data += f" (Date: {vac_date})"
                            display_data += "\n"
                            if next_due:
                                display_data += f"  Next due: {next_due}\n"
                            if notes:
                                display_data += f"  Notes: {notes}\n"
                            display_data += "\n"
                    else:
                        # Check if user exists in system
                        cursor.execute("SELECT id FROM students WHERE student_id = ? OR id = ?", (user_id, user_id))
                        if cursor.fetchone():
                            display_data += "No vaccination records found.\n"
                            display_data += "Use the form above to add your vaccination information.\n\n"
                        else:
                            display_data += "User not found in health system.\n"
                else:
                    display_data += "Please log in to view your vaccination records.\n\n"

                display_data += "\nFor official records and updates, contact the health center.\n"
                display_data += "Use the form above to add new vaccination records.\n"

                self.vaccination_text.insert(tk.END, display_data)

        except Exception as e:
            error_msg = f"VACCINATION RECORDS\n"
            error_msg += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            error_msg += "=" * 50 + "\n\n"
            error_msg += f"Error loading vaccination records: {str(e)}\n\n"
            error_msg += "Please contact the health center for assistance.\n"
            self.vaccination_text.insert(tk.END, error_msg)

    def create_view_medical_history(self):
        """View and manage medical history"""
        content_frame = ttk.Frame(self.content_area)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(content_frame, text="Medical History",
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))

        # Quick add medical record form
        add_frame = ttk.LabelFrame(content_frame, text="Add Medical History Record", padding=15)
        add_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(add_frame, text="Condition:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.condition_name = ttk.Entry(add_frame, width=30)
        self.condition_name.grid(row=0, column=1, sticky=tk.W, padx=(10, 20), pady=5)

        ttk.Label(add_frame, text="Date:").grid(row=0, column=2, sticky=tk.W, pady=5)
        self.condition_date = ttk.Entry(add_frame, width=15)
        self.condition_date.grid(row=0, column=3, sticky=tk.W, padx=(10, 20), pady=5)
        self.condition_date.insert(0, datetime.now().strftime('%Y-%m-%d'))

        ttk.Button(add_frame, text="Add Record",
                  command=self.add_medical_history_record).grid(row=0, column=4)

        # Medical history display
        history_frame = ttk.LabelFrame(content_frame, text="Medical History Records", padding=15)
        history_frame.pack(fill=tk.BOTH, expand=True)

        self.medical_history_text = scrolledtext.ScrolledText(history_frame, wrap=tk.WORD, height=15)
        self.medical_history_text.pack(fill=tk.BOTH, expand=True)

        # Load medical history
        self.load_medical_history_display()

    def add_medical_history_record(self):
        """Add a new medical history record"""
        if not self.condition_name.get().strip():
            messagebox.showerror("Validation Error", "Condition name is required.")
            return

        try:
            history_info = f"Condition: {self.condition_name.get()}\n"
            history_info += f"Date: {self.condition_date.get()}\n"
            history_info += f"Recorded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            history_info += f"Status: Active\n"
            history_info += "-" * 40 + "\n"

            self.medical_history_text.insert(tk.END, history_info)

            # Clear form
            self.condition_name.delete(0, tk.END)
            self.condition_date.delete(0, tk.END)
            self.condition_date.insert(0, datetime.now().strftime('%Y-%m-%d'))

            messagebox.showinfo("Success", "Medical history record added successfully!")
            self.log_audit_event('add_medical_history', 'medical_history', self.condition_name.get())

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add medical history record: {str(e)}")

    def load_medical_history_display(self):
        """Load and display medical history"""
        try:
            # Placeholder medical history
            placeholder_text = f"MEDICAL HISTORY\n"
            placeholder_text += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            placeholder_text += "=" * 50 + "\n\n"
            placeholder_text += "This feature displays medical history records.\n"
            placeholder_text += "Use the form above to add new medical records.\n"
            placeholder_text += "For detailed medical history, contact the health center.\n"

            self.medical_history_text.insert(tk.END, placeholder_text)
        except Exception as e:
            self.medical_history_text.insert(tk.END, f"Error loading medical history: {str(e)}")

    # Helper methods and other functions
    def create_view_health_records(self):
        """Alias for view health records (for navigation compatibility)"""
        self.create_manage_health_records()
    
    def create_view_vaccinations(self):
        """Alias for vaccination records (for navigation compatibility)"""
        self.create_record_vaccination()
    
    def create_view_appointments(self):
        """Alias for appointment management (for navigation compatibility)"""
        self.create_schedule_appointment()
    
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

    # ==================== EMAIL INTEGRATION METHODS ====================

    def _send_email_via_gui(self, to_email, subject, message):
        """Send email via email manager GUI"""
        try:
            from university_system.infrastructure.email.gui.email_manager_gui import EmailManagerGUI
            email_gui = EmailManagerGUI(self.root, auth=self.auth)
            if hasattr(email_gui, 'send_email'):
                email_gui.send_email(to_email=to_email, subject=subject, message=message)
                return True
            return False
        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending email via GUI: {e}")
            return False

    def _show_email_fallback_dialog(self, to_email, subject, message):
        """Show email dialog as fallback when email system unavailable"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Health Portal Email Notification")
        dialog.geometry("600x500")
        dialog.configure(bg='white')
        dialog.grab_set()

        tk.Label(dialog, text="🏥 Health Portal Email Notification", font=('Arial', 14, 'bold'),
                bg='white', fg='#2c3e50').pack(pady=10)

        info_frame = tk.Frame(dialog, bg='white')
        info_frame.pack(fill='x', padx=20, pady=10)

        tk.Label(info_frame, text=f"To: {to_email}", font=('Arial', 11),
                bg='white', fg='#34495e').pack(anchor='w')
        tk.Label(info_frame, text=f"Subject: {subject}", font=('Arial', 11),
                bg='white', fg='#34495e').pack(anchor='w')

        tk.Label(dialog, text="Message:", font=('Arial', 11, 'bold'),
                bg='white', fg='#2c3e50').pack(anchor='w', padx=20, pady=(10, 5))

        message_text = tk.Text(dialog, height=15, wrap='word', font=('Arial', 10))
        message_text.pack(fill='both', expand=True, padx=20, pady=(0, 10))
        message_text.insert('1.0', message)
        message_text.config(state='disabled')

        tk.Button(dialog, text="Close", command=dialog.destroy,
                 bg='#6c757d', fg='white', font=('Arial', 10),
                 padx=20, pady=5, relief='flat').pack(pady=10)

    # ==================== APPOINTMENT EMAIL METHODS ====================

    def send_appointment_confirmation(self, patient_email, patient_name, appointment_details):
        """Send confirmation email for appointment booking"""
        from university_system.infrastructure.email.template_utils import render_template

        subject, message = render_template('appointment_confirmation', {
            'patient_name': patient_name,
            'date': appointment_details.get('date', 'N/A'),
            'time': appointment_details.get('time', 'N/A'),
            'practitioner': appointment_details.get('practitioner', 'N/A'),
            'department': appointment_details.get('department', 'N/A'),
            'location': appointment_details.get('location', 'University Health Center'),
            'appointment_type': appointment_details.get('type', 'N/A')
        })

        if not (subject and message):
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    def send_appointment_cancellation(self, patient_email, patient_name, appointment_details, cancellation_reason):
        """Send confirmation email for appointment cancellation"""
        from university_system.infrastructure.email.template_utils import render_template

        subject, message = render_template('appointment_cancellation', {
            'patient_name': patient_name,
            'date': appointment_details.get('date', 'N/A'),
            'time': appointment_details.get('time', 'N/A'),
            'practitioner': appointment_details.get('practitioner', 'N/A'),
            'department': appointment_details.get('department', 'N/A'),
            'cancellation_reason': cancellation_reason
        })

        if not (subject and message):
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    def send_appointment_date_change(self, patient_email, patient_name, old_appointment, new_appointment):
        """Send confirmation email for appointment date/time changes"""
        from university_system.infrastructure.email.template_utils import render_template

        subject, message = render_template('appointment_rescheduled', {
            'patient_name': patient_name,
            'old_date': old_appointment.get('date', 'N/A'),
            'old_time': old_appointment.get('time', 'N/A'),
            'date': new_appointment.get('date', 'N/A'),
            'time': new_appointment.get('time', 'N/A'),
            'practitioner': new_appointment.get('practitioner', 'N/A'),
            'department': new_appointment.get('department', 'N/A'),
            'location': new_appointment.get('location', 'University Health Center')
        })

        if not (subject and message):
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    # ==================== HEALTH REPORT EMAIL METHODS ====================

    def send_health_report_email(self, patient_email, patient_name, report_details):
        """Send health report via email"""
        from university_system.infrastructure.email.template_utils import render_template
        subject, message = render_template("health_report", {
            "patient_name": patient_name,
            "report_title": report_details.get('title', 'Health Report'),
            "report_type": report_details.get('type', 'N/A'),
            "report_date": report_details.get('date', datetime.now().strftime('%Y-%m-%d')),
            "practitioner": report_details.get('practitioner', 'University Health Center'),
            "report_summary": report_details.get('summary', 'Please see the attached detailed report.'),
            "next_steps": report_details.get('next_steps', 'Please follow up with your healthcare provider if you have any questions about this report.')
        })
        if not (subject and message):
            return

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    def send_health_report_creation_confirmation(self, patient_email, patient_name, report_title):
        """Send confirmation email for health report creation"""
        from university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'patient_name': patient_name,
            'report_title': report_title
        }

        subject, message = render_template('health_report_created', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    def send_health_report_update_confirmation(self, patient_email, patient_name, report_title, update_details):
        """Send confirmation email for health report updates"""
        from university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'patient_name': patient_name,
            'report_title': report_title,
            'update_details': update_details
        }

        subject, message = render_template('health_report_updated', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    def send_health_report_deletion_confirmation(self, patient_email, patient_name, report_title):
        """Send confirmation email for health report deletion"""
        from university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'patient_name': patient_name,
            'report_title': report_title
        }

        subject, message = render_template('health_report_deleted', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    # ==================== HEALTH RECORD EMAIL METHODS ====================

    def send_health_record_email(self, patient_email, patient_name, record_details):
        """Send health record via email"""
        subject = f"Health Portal - Your Health Record: {record_details.get('type', 'Health Record')}"
        message = f"""Dear {patient_name},

Your requested health record is ready for review.

RECORD DETAILS
=============
Record Type: {record_details.get('type', 'N/A')}
Date Range: {record_details.get('date_range', 'N/A')}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

RECORD CONTENTS
==============
{record_details.get('summary', 'This record contains your health information as requested.')}

IMPORTANT INFORMATION
====================
- This record contains confidential medical information
- Keep this information secure and private
- Share only with authorized healthcare providers
- Contact us if you notice any discrepancies

USING YOUR HEALTH RECORD
=======================
You can use this record to:
- Share with other healthcare providers
- Apply for medical accommodations
- Track your health history
- Support insurance claims

If you have questions about this record or need additional information, please contact us at (555) 123-4567.

Best regards,
University Health Center
📞 (555) 123-4567
📧 health@university.edu

PRIVACY NOTICE: This health record is protected under HIPAA regulations."""

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    def send_health_record_creation_confirmation(self, patient_email, patient_name, record_type):
        """Send confirmation email for health record creation"""
        from university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'patient_name': patient_name,
            'record_type': record_type
        }

        subject, message = render_template('health_record_created', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    def send_health_record_update_confirmation(self, patient_email, patient_name, record_type, update_details):
        """Send confirmation email for health record updates"""
        from university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'patient_name': patient_name,
            'record_type': record_type,
            'update_details': update_details
        }

        subject, message = render_template('health_record_updated', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    def send_health_record_deletion_confirmation(self, patient_email, patient_name, record_type):
        """Send confirmation email for health record deletion"""
        from university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'patient_name': patient_name,
            'record_type': record_type
        }

        subject, message = render_template('health_record_deleted', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    # ==================== EMERGENCY CONTACT EMAIL METHODS ====================

    def send_emergency_contact_creation_confirmation(self, patient_email, patient_name, contact_name, contact_relationship):
        """Send confirmation email for emergency contact creation"""
        from university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'patient_name': patient_name,
            'contact_name': contact_name,
            'contact_relationship': contact_relationship
        }

        subject, message = render_template('emergency_contact_added', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    def send_emergency_contact_update_confirmation(self, patient_email, patient_name, contact_name, update_details):
        """Send confirmation email for emergency contact updates"""
        from university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'patient_name': patient_name,
            'contact_name': contact_name,
            'update_details': update_details
        }

        subject, message = render_template('emergency_contact_updated', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    def send_emergency_contact_deletion_confirmation(self, patient_email, patient_name, contact_name):
        """Send confirmation email for emergency contact deletion"""
        from university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'patient_name': patient_name,
            'contact_name': contact_name
        }

        subject, message = render_template('emergency_contact_removed', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    def open_email_manager_gui(self):
        """Open email manager GUI for health portal"""
        try:
            from university_system.infrastructure.email.gui.email_manager_gui import EmailManagerGUI
            email_window = tk.Toplevel(self.root)
            email_window.title("Health Portal - Email Manager")
            email_window.geometry("800x600")
            email_gui = EmailManagerGUI(email_window, auth=self.auth)
        except ImportError:
            messagebox.showerror("Error", "Email Manager GUI not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error opening Email Manager: {e}")

    def create_open_accessibility_tools(self):
        """Create interface for opening Accessibility Tools GUI"""
        title = ttk.Label(self.content_frame, text="Accessibility & Accommodation Tools",
                         style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        # Launch accessibility tools button
        launch_frame = ttk.Frame(self.content_frame)
        launch_frame.grid(row=1, column=0, pady=20)

        ttk.Button(launch_frame, text="Open Accessibility Tools",
                  command=self.open_accessibility_tools_gui, style='Accent.TButton').pack(pady=10)

        # Information text
        info_text = """The Accessibility & Accommodation Tools system allows you to:

• Manage accessibility profiles for students
• Submit and review accommodation requests
• Configure exam accommodations (extended time, separate room, etc.)
• Request assistive technology
• Track alternative material formats
• Configure personal accessibility settings

This comprehensive system ensures that all students have equal access
to educational opportunities and resources.

Click the button above to open the Accessibility Tools interface."""

        info_label = ttk.Label(self.content_frame, text=info_text, justify=tk.LEFT, wraplength=800)
        info_label.grid(row=2, column=0, pady=10, padx=20)

    def open_accessibility_tools_gui(self):
        """Open Accessibility Tools GUI"""
        try:
            from university_system.modules.domain.student_affairs.gui.accessibility_tools_gui import (
                launch_accessibility_tools_gui
            )
            launch_accessibility_tools_gui(self.root, self.auth)
        except ImportError as e:
            messagebox.showerror("Error", f"Accessibility Tools GUI not available: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Error opening Accessibility Tools: {e}")

    def create_medical_accommodations(self):
        """Create interface for medical accommodations information"""
        title = ttk.Label(self.content_frame, text="Medical Accommodations",
                         style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        info_frame = ttk.Frame(self.content_frame)
        info_frame.grid(row=1, column=0, pady=20, padx=20, sticky=(tk.W, tk.E))

        info_text = """Medical Accommodations Information:

Medical accommodations are integrated with the Accessibility Tools system.
You can access all accommodation features through the Accessibility Tools
interface, which includes:

• Medical accommodation requests
• Disability documentation management
• Exam accommodations
• Assistive technology requests
• Alternative materials
• Accessibility profiles

For health-specific accommodations, the Health Portal works in conjunction
with the Accessibility Tools system to ensure proper coordination of care
and support services.

To manage medical accommodations, please use the "Open Accessibility Tools"
button in this section."""

        info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT, wraplength=800)
        info_label.pack(pady=10)

        # Quick access button
        ttk.Button(info_frame, text="Open Accessibility Tools",
                  command=self.open_accessibility_tools_gui,
                  style='Accent.TButton').pack(pady=20)

    def run(self):
        """Start the GUI application"""
        try:
            self.root.mainloop()
        except Exception as e:
            messagebox.showerror("Application Error", f"An error occurred: {str(e)}")


def launch_health_portal_gui(auth=None):
    """Launch Health Portal GUI for integration with university system"""
    root = tk.Tk()
    app = HealthPortalGUI(root, auth_system=auth)
    app.run()


# Main execution
if __name__ == "__main__":
    root = tk.Tk()
    app = HealthPortalGUI(root)
    app.run()
