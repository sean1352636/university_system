# Standard library imports
import os
import csv
import json
import time
import shutil
import hashlib
import zipfile
import threading
from datetime import datetime, timedelta

# Internationalization
from university_system.modules.shared.utils.i18n import get_text as _t

# Local imports - Database
from university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection

# Local imports - Paths
from university_system.modules.shared.constants import paths

# SQL safety
from university_system.core.sql_safety import validate_identifier

# Local imports - Authentication
from university_system.infrastructure.auth import UserAuth, get_current_user, set_auth_instance
from university_system.infrastructure.shared_context import get_auth

# Import activity logger for audit trail
try:
    from university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Optional imports - Email system
try:
    from university_system.infrastructure.email import (
        send_email,
        send_template_email,
        queue_email,
        initialize_communication_system,
        set_auth
    )
    from university_system.modules.shared.utils.logs import log_event
    from university_system.infrastructure.email.template_utils import render_template
    EMAIL_SYSTEM_AVAILABLE = True
except ImportError:
    EMAIL_SYSTEM_AVAILABLE = False
    print(_t("shared.utils.document_manager.warning_email_unavailable", default="Warning: Email system not available"))
    # Provide a fallback log_event function
    def log_event(level, message):
        print(f"[{level.upper()}] {message}")


def set_auth_context(self, auth):
    """Set authentication context for email system integration"""
    self.auth = auth
    if EMAIL_SYSTEM_AVAILABLE:
        try:
            set_auth(auth)
            log_event('info', f"Authentication context set for document management email system")
        except Exception as e:
            log_event('error', f"Failed to set auth context for email system: {e}")

class DocumentManager:
    def __init__(self, auth=None):
        # Accept an optional auth instance from the caller (main.py)
        self.auth = auth

        # If caller passed an authenticated auth, publish it globally so get_current_user() works
        if self.auth and getattr(self.auth, "current_user", None):
            try:
                set_auth_instance(self.auth)
            except Exception:
                pass

        self.init_enhanced_db()

        # Initialize email system
        if EMAIL_SYSTEM_AVAILABLE:
            initialize_communication_system()
            # Set auth context if available
            if hasattr(self, 'auth') and self.auth:
                try:
                    set_auth(self.auth)
                except Exception:
                    pass
        
    def display_main_menu(self):
        """Display the main document management menu"""
        while True:
            # Check authentication
            if not self.check_authentication():
                return False
                
            current_user = get_current_user()
            
            print(f"\n{'='*60}")
            print(_t("shared.utils.document_manager.system_title", default="ENHANCED DOCUMENT MANAGEMENT SYSTEM"))
            print(_t("shared.utils.document_manager.logged_in_as", default="Logged in as: {username} ({role})", username=current_user['username'], role=current_user['role']))
            print(f"{'='*60}")
            
            # Show different menus based on user role
            if current_user['role'] == 'student':
                self.display_student_menu()
            else:
                self.display_admin_menu()
                
    def display_admin_menu(self):
        """Display admin/staff menu"""
        print(_t("shared.utils.document_manager.menu_document_management", default="\n📋 DOCUMENT MANAGEMENT:"))
        print(f"{_t('shared.utils.document_manager.menu_upload_document', default='1.  Upload Document'):<25} {_t('shared.utils.document_manager.menu_view_documents', default='2.  View Documents'):<25} {_t('shared.utils.document_manager.menu_update_status', default='3.  Update Status'):<25} {_t('shared.utils.document_manager.menu_versioning', default='4.  Versioning'):<25}")
        print(f"{_t('shared.utils.document_manager.menu_bulk_operations', default='5.  Bulk Operations'):<25}")

        print(_t("shared.utils.document_manager.menu_search_analytics", default="\n🔍 SEARCH & ANALYTICS:"))
        print(f"{_t('shared.utils.document_manager.menu_advanced_search', default='6.  Advanced Search'):<25} {_t('shared.utils.document_manager.menu_dashboard', default='7.  Dashboard'):<25} {_t('shared.utils.document_manager.menu_generate_reports', default='8.  Generate Reports'):<25} {_t('shared.utils.document_manager.menu_expiry_check', default='9.  Expiry Check'):<25}")

        print(_t("shared.utils.document_manager.menu_system_management", default="\n⚙️ SYSTEM MANAGEMENT:"))
        print(f"{_t('shared.utils.document_manager.menu_doc_templates', default='10. Doc Templates'):<25} {_t('shared.utils.document_manager.menu_workflow_mgmt', default='11. Workflow Mgmt'):<25} {_t('shared.utils.document_manager.menu_system_settings', default='13. System Settings'):<25} {_t('shared.utils.document_manager.menu_notifications', default='14. Notifications'):<25}")

        print(_t("shared.utils.document_manager.menu_import_export", default="\n📤 IMPORT/EXPORT:"))
        print(f"{_t('shared.utils.document_manager.menu_bulk_import', default='15. Bulk Import'):<25} {_t('shared.utils.document_manager.menu_export_data', default='16. Export Data'):<25} {_t('shared.utils.document_manager.menu_backup_system', default='17. Backup System'):<25}")

        print(_t("shared.utils.document_manager.menu_advanced_features", default="\n🤖 ADVANCED FEATURES:"))
        print(f"{_t('shared.utils.document_manager.menu_ocr_integration', default='18. OCR Integration'):<25} {_t('shared.utils.document_manager.menu_api_server', default='19. API Server'):<25} {_t('shared.utils.document_manager.menu_web_interface', default='20. Web Interface'):<25}")

        print(_t("shared.utils.document_manager.menu_exit", default="\n🚪 EXIT:"))
        print(f"{_t('shared.utils.document_manager.menu_switch_user', default='21. Switch User'):<25} {_t('shared.utils.document_manager.menu_exit_system', default='22. Exit System'):<25}")

        choice = input(_t("shared.utils.document_manager.prompt_choice_1_22", default="\nEnter your choice (1-22): ")).strip()
        self.handle_admin_choice(choice)
        
    def display_student_menu(self):
        """Display student self-service menu"""
        print(_t("shared.utils.document_manager.menu_my_documents", default="\n📋 MY DOCUMENTS:"))
        print(f"{_t('shared.utils.document_manager.menu_view_my_documents', default='1.  View My Documents'):<25} {_t('shared.utils.document_manager.menu_upload_document', default='2.  Upload Document'):<25} {_t('shared.utils.document_manager.menu_check_requirements', default='3.  Check Requirements'):<25} {_t('shared.utils.document_manager.menu_document_status', default='4.  Document Status'):<25}")

        print(_t("shared.utils.document_manager.menu_my_dashboard", default="\n📊 MY DASHBOARD:"))
        print(f"{_t('shared.utils.document_manager.menu_my_dashboard_item', default='5.  My Dashboard'):<25} {_t('shared.utils.document_manager.menu_notification_history', default='6.  Notification History'):<25}")

        print(_t("shared.utils.document_manager.menu_exit", default="\n🚪 EXIT:"))
        print(f"{_t('shared.utils.document_manager.menu_logout', default='7.  Logout'):<25} {_t('shared.utils.document_manager.menu_exit_system', default='8.  Exit System'):<25}")

        choice = input(_t("shared.utils.document_manager.prompt_choice_1_8", default="\nEnter your choice (1-8): ")).strip()
        self.handle_student_choice(choice)
        
    def handle_admin_choice(self, choice):
        """Handle admin menu choices"""
        if choice == '1':
            self.upload_student_document()
        elif choice == '2':
            self.view_student_documents()
        elif choice == '3':
            self.update_document_status()
        elif choice == '4':
            self.document_versioning_menu()
        elif choice == '5':
            self.bulk_operations_menu()
        elif choice == '6':
            self.advanced_search()
        elif choice == '7':
            self.display_dashboard()
        elif choice == '8':
            self.generate_reports_menu()
        elif choice == '9':
            self.check_document_expiry()
        elif choice == '10':
            self.manage_document_templates()
        elif choice == '11':
            self.workflow_management()
        elif choice == '13':
            self.system_settings()
        elif choice == '14':
            self.notification_center()
        elif choice == '15':
            self.bulk_import_documents()
        elif choice == '16':
            self.export_data_menu()
        elif choice == '17':
            self.backup_system()
        elif choice == '18':
            self.ocr_integration_menu()
        elif choice == '19':
            self.api_server_menu()
        elif choice == '20':
            self.web_interface_menu()
        elif choice == '21':
            self.current_user = None
        elif choice == '22':
            print(_t("shared.utils.document_manager.goodbye", default="Goodbye!"))
            exit()
        else:
            print(_t("shared.utils.document_manager.invalid_choice", default="Invalid choice. Please try again."))
            
    def handle_student_choice(self, choice):
        """Handle student menu choices"""
        if choice == '1':
            self.view_my_documents()
        elif choice == '2':
            self.student_upload_document()
        elif choice == '3':
            self.check_my_requirements()
        elif choice == '4':
            self.my_document_status()
        elif choice == '5':
            self.student_dashboard()
        elif choice == '6':
            self.my_notifications()
        elif choice == '7':
            self.current_user = None
        elif choice == '8':
            print(_t("shared.utils.document_manager.goodbye", default="Goodbye!"))
            exit()
        else:
            print(_t("shared.utils.document_manager.invalid_choice", default="Invalid choice. Please try again."))

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

            # Students table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                email_address TEXT,
                course TEXT,
                year INTEGER,
                program TEXT,
                enrollment_date TEXT,
                status TEXT DEFAULT 'active',
                phone TEXT,
                address TEXT,
                emergency_contact TEXT,
                created_date TEXT DEFAULT (datetime('now')),
                is_active BOOLEAN DEFAULT 1,
                grade_level TEXT
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
            
            # System settings
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
            
            # Audit trail
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

            # Migrate existing tables if needed
            self.migrate_tables(cursor)

            # Insert default data if tables are empty
            self.insert_default_data(cursor)

            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(_t("shared.utils.document_manager.database_error", default="Database error: {error}", error=str(e)))
            return False

    def migrate_tables(self, cursor):
        """Migrate existing tables to add missing columns"""
        try:
            # Check if has_expiry column exists in document_types
            cursor.execute("PRAGMA table_info(document_types)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'has_expiry' not in columns:
                print("Migrating document_types table: adding has_expiry column")
                cursor.execute("ALTER TABLE document_types ADD COLUMN has_expiry BOOLEAN DEFAULT 0")

            if 'expiry_reminder_days' not in columns:
                print("Migrating document_types table: adding expiry_reminder_days column")
                cursor.execute("ALTER TABLE document_types ADD COLUMN expiry_reminder_days INTEGER DEFAULT 0")

            if 'category' not in columns:
                print("Migrating document_types table: adding category column")
                cursor.execute("ALTER TABLE document_types ADD COLUMN category TEXT DEFAULT 'General'")

            if 'sort_order' not in columns:
                print("Migrating document_types table: adding sort_order column")
                cursor.execute("ALTER TABLE document_types ADD COLUMN sort_order INTEGER DEFAULT 0")

            if 'is_active' not in columns:
                print("Migrating document_types table: adding is_active column")
                cursor.execute("ALTER TABLE document_types ADD COLUMN is_active BOOLEAN DEFAULT 1")

            # Check if students table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
            if not cursor.fetchone():
                print("Creating missing students table")
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    first_name TEXT,
                    last_name TEXT,
                    email_address TEXT,
                    course TEXT,
                    year INTEGER,
                    program TEXT,
                    enrollment_date TEXT,
                    status TEXT DEFAULT 'active',
                    phone TEXT,
                    address TEXT,
                    emergency_contact TEXT,
                    created_date TEXT DEFAULT (datetime('now')),
                    is_active BOOLEAN DEFAULT 1,
                    grade_level TEXT
                )
                ''')

        except sqlite3.Error as e:
            print(f"Migration warning: {e}")
            
    def insert_default_data(self, cursor):
        """Insert default data for the system"""
        # Check if users exist
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            # Create default admin user using centralized authentication
            from university_system.core.defaults import DEFAULT_ADMIN_PASSWORD
            admin_password = DEFAULT_ADMIN_PASSWORD
            admin_created = False
            user_id = None

            try:
                from university_system.infrastructure.auth import UserAuth
                auth_system = UserAuth()
                user_id = auth_system.create_user(
                    username="admin",
                    password=admin_password,
                    email="admin@school.edu",
                    first_name="System",
                    last_name="Administrator",
                    role="admin"
                )
                if user_id:
                    print("Default admin user created via centralized auth system")
                    admin_created = True
                    # Log activity
                    if ACTIVITY_LOGGER_AVAILABLE:
                        log_activity('create', 'user', user_id=user_id, details={
                            'username': 'admin',
                            'role': 'admin',
                            'source': 'bootstrap',
                            'method': 'central_auth'
                        })
                else:
                    raise Exception("Auth system returned no user_id")
            except Exception as e:
                # Fallback to direct insertion if auth system not available during initialization
                # This is ONLY for bootstrap scenarios where the auth system may not be fully initialized
                print(f"WARNING: Using fallback admin creation (auth system unavailable): {e}")
                print("NOTE: This fallback uses weaker password hashing and should only occur during initial setup.")

                # Use PBKDF2 for better security instead of SHA256
                import secrets
                salt = secrets.token_hex(16)
                # Simple PBKDF2 implementation
                password_hash = hashlib.pbkdf2_hmac('sha256', admin_password.encode(), salt.encode(), 100000).hex()

                cursor.execute('''
                INSERT INTO users (username, password_hash, password_salt, role, email, first_name, last_name, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', ("admin", password_hash, salt, "admin", "admin@school.edu", "System", "Administrator", datetime.now().strftime('%Y-%m-%d')))
                user_id = cursor.lastrowid
                admin_created = True

                # Log activity even in fallback mode
                if ACTIVITY_LOGGER_AVAILABLE:
                    log_activity('create', 'user', user_id=user_id, details={
                        'username': 'admin',
                        'role': 'admin',
                        'source': 'bootstrap',
                        'method': 'fallback'
                    })

            if not admin_created:
                print("ERROR: Failed to create default admin user")
            
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
            
        # Insert default system settings (SMTP settings removed - handled by email_manager)
        cursor.execute('SELECT COUNT(*) FROM system_settings')
        if cursor.fetchone()[0] == 0:
            default_settings = [
                ('notification_enabled', 'true', 'Enable email notifications'),
                ('auto_backup_enabled', 'false', 'Enable automatic backups'),
                ('backup_frequency_days', '7', 'Backup frequency in days'),
                ('max_file_size_mb', '50', 'Maximum file size for uploads'),
                ('document_retention_years', '7', 'Document retention period in years'),
                ('workflow_enabled', 'true', 'Enable document workflow approval process'),
                ('auto_expiry_check', 'true', 'Automatically check for expiring documents'),
                ('expiry_check_frequency_days', '1', 'How often to check for expiring documents'),
                ('bulk_upload_enabled', 'true', 'Enable bulk document upload functionality'),
                ('versioning_enabled', 'true', 'Enable document versioning')
            ]
            
            cursor.executemany('''
            INSERT INTO system_settings (setting_name, setting_value, description, updated_date)
            VALUES (?, ?, ?, ?)
            ''', [(s[0], s[1], s[2], datetime.now().strftime('%Y-%m-%d')) for s in default_settings])
            
        # Insert default tags
        cursor.execute('SELECT COUNT(*) FROM document_tags')
        if cursor.fetchone()[0] == 0:
            default_tags = [
                ('urgent', '#ff0000', 'Urgent documents requiring immediate attention'),
                ('verified', '#00ff00', 'Documents that have been verified'),
                ('pending', '#ffff00', 'Documents pending review'),
                ('archived', '#808080', 'Archived documents'),
                ('international', '#0000ff', 'Documents for international students'),
                ('renewal', '#ff8800', 'Documents requiring renewal')
            ]
            
            cursor.executemany('''
            INSERT INTO document_tags (tag_name, tag_color, description)
            VALUES (?, ?, ?)
            ''', default_tags)
        
    def check_authentication(self):
        """Check if user is authenticated via the central auth system (set once in main.py)"""
        # If the global is already set, we’re good
        cu = get_current_user()
        if cu:
            # Cache username for operations that use self.current_user
            self.current_user = cu.get('username')
            return True

        # If caller injected an auth that’s logged in, publish it globally and proceed
        if hasattr(self, "auth") and getattr(self.auth, "current_user", None):
            try:
                set_auth_instance(self.auth)
            except Exception:
                pass
            return True

        # Otherwise, not logged in
        print(_t("shared.utils.document_manager.error_not_logged_in", default="You must be logged in to access the Document Management System."))
        print(_t("shared.utils.document_manager.error_run_auth_first", default="Please run the main authentication menu first."))
        return False

    def upload_student_document(self):
        """Enhanced document upload with versioning support and integrated email notifications"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get student ID
            student_id = self.select_student(cursor)
            if not student_id:
                conn.close()
                return
            
            # Get document type
            type_info = self.select_document_type(cursor)
            if not type_info:
                conn.close()
                return
                
            type_id, type_name, has_expiry, max_size, allowed_formats = type_info
            
            # Check for existing documents of this type
            cursor.execute('''
            SELECT document_id, version_number, original_filename 
            FROM student_documents 
            WHERE student_id = ? AND type_id = ? AND is_current_version = 1
            ''', (student_id, type_id))
            
            existing_doc = cursor.fetchone()
            
            if existing_doc:
                print(_t("shared.utils.document_manager.existing_doc_found", default="\nExisting document found: {filename} (Version {version})", filename=existing_doc[2], version=existing_doc[1]))
                print(_t("shared.utils.document_manager.option_upload_new_version", default="1. Upload new version (replace existing)"))
                print(_t("shared.utils.document_manager.option_upload_additional", default="2. Upload additional document"))
                print(_t("shared.utils.document_manager.option_cancel", default="3. Cancel"))
                
                choice = input("Choose option (1-3): ").strip()
                if choice == '3':
                    conn.close()
                    return
                elif choice == '1':
                    # Create new version
                    new_version = existing_doc[1] + 1
                    parent_doc_id = existing_doc[0]
                    
                    # Mark existing as not current
                    cursor.execute('''
                    UPDATE student_documents 
                    SET is_current_version = 0 
                    WHERE document_id = ?
                    ''', (existing_doc[0],))
                else:
                    new_version = 1
                    parent_doc_id = None
            else:
                new_version = 1
                parent_doc_id = None
            
            # Get file details
            file_info = self.get_file_upload_details(allowed_formats, max_size)
            if not file_info:
                conn.close()
                return
                
            file_path, original_filename, file_size, file_hash = file_info
            
            # Get expiry date if needed
            expiry_date = None
            if has_expiry:
                expiry_date = self.get_expiry_date()
                
            # Get tags
            tags = self.select_tags(cursor)
            
            # Insert document record
            upload_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO student_documents 
            (student_id, type_id, file_path, original_filename, upload_date, expiry_date, 
             verification_status, version_number, parent_document_id, uploaded_by, 
             file_size, file_hash, tags, workflow_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, type_id, file_path, original_filename, upload_date, expiry_date,
                  'Pending', new_version, parent_doc_id, self.current_user, file_size, file_hash, tags, 'submitted'))
            
            document_id = cursor.lastrowid
            
            # Create workflow steps
            self.create_workflow_steps(cursor, document_id, type_id)
            
            # Create notification in database
            self.create_notification(cursor, student_id, 'document_uploaded', 
                                   f'Document Uploaded: {type_name}',
                                   f'Your {type_name} has been uploaded successfully and is pending verification.',
                                   document_id)
            
            conn.commit()
            conn.close()
            
            print(_t("shared.utils.document_manager.document_uploaded_success", default="\nDocument uploaded successfully!"))
            print(_t("shared.utils.document_manager.document_id", default="Document ID: {doc_id}", doc_id=document_id))
            print(_t("shared.utils.document_manager.version", default="Version: {version}", version=new_version))
            print(_t("shared.utils.document_manager.status_pending_verification", default="Status: Pending Verification"))
            
            # Send email notification using integrated email system
            if EMAIL_SYSTEM_AVAILABLE:
                try:
                    # Get student details for email
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                    SELECT email_address, first_name, last_name 
                    FROM students WHERE student_id = ?
                    ''', (student_id,))
                    student_data = cursor.fetchone()
                    conn.close()
                    
                    if student_data:
                        email_address, first_name, last_name = student_data
                        
                        # Use template email for better formatting
                        template_vars = {
                            'student_name': f"{first_name} {last_name}".strip() or "Student",
                            'document_type': type_name,
                            'document_id': document_id,
                            'version': new_version,
                            'upload_date': upload_date
                        }

                        subject, body = render_template('document_upload_confirmation', template_vars)

                        if send_email(email_address, subject, body):
                            log_event('info', f"Document upload confirmation email sent to {email_address}")
                            print(_t("shared.utils.document_manager.email_sent", default="Confirmation email sent to {email}", email=email_address))
                        else:
                            log_event('warning', f"Failed to send confirmation email to {email_address}")
                            print(_t("shared.utils.document_manager.email_failed", default="Document uploaded but email notification failed"))
                    else:
                        log_event('warning', f"Could not find email address for student {student_id}")
                        
                except Exception as e:
                    log_event('error', f"Error sending document upload notification: {e}")
                    print(_t("shared.utils.document_manager.email_failed", default="Document uploaded but email notification failed"))
            else:
                print(_t("shared.utils.document_manager.email_system_unavailable", default="Document uploaded (email system not available)"))

        except sqlite3.Error as e:
            print(_t("shared.utils.document_manager.database_error", default="Database error: {error}", error=str(e)))
            log_event('error', f"Database error in upload_student_document: {e}")

    def check_document_expiry(self):
        """Check for expiring documents and send notifications"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get expiry settings
            try:
                days_ahead = int(input("Check for documents expiring within how many days? (default: 30): ") or "30")
            except ValueError:
                days_ahead = 30
            
            future_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Find expiring documents
            cursor.execute('''
            SELECT sd.document_id, sd.student_id, s.first_name, s.last_name, s.email_address,
                   dt.type_name, sd.expiry_date, sd.original_filename,
                   julianday(sd.expiry_date) - julianday('now') as days_until_expiry
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.expiry_date BETWEEN ? AND ?
            AND sd.verification_status = 'Verified'
            AND sd.is_current_version = 1
            ORDER BY sd.expiry_date ASC
            ''', (today, future_date))
            
            expiring_docs = cursor.fetchall()
            
            # Find already expired documents
            cursor.execute('''
            SELECT sd.document_id, sd.student_id, s.first_name, s.last_name, s.email_address,
                   dt.type_name, sd.expiry_date, sd.original_filename
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.expiry_date < ?
            AND sd.verification_status != 'Expired'
            AND sd.is_current_version = 1
            ORDER BY sd.expiry_date ASC
            ''', (today,))
            
            expired_docs = cursor.fetchall()
            
            print(_t("shared.utils.document_manager.expiry_check_results", default="\nDocument Expiry Check Results:"))
            print(_t("shared.utils.document_manager.docs_expiring_within", default="Documents expiring within {days} days: {count}", days=days_ahead, count=len(expiring_docs)))
            print(_t("shared.utils.document_manager.docs_already_expired", default="Documents already expired: {count}", count=len(expired_docs)))
            
            if expiring_docs:
                print(_t("shared.utils.document_manager.docs_expiring_soon_header", default="\nDocuments Expiring Soon:"))
                print("-" * 80)
                for doc in expiring_docs:
                    doc_id, student_id, first_name, last_name, email, doc_type, expiry_date, filename, days_left = doc
                    student_name = f"{first_name} {last_name}".strip()
                    print(_t("shared.utils.document_manager.expiry_doc_line", default="ID: {doc_id} | {student_name} | {doc_type} | Expires: {expiry_date} ({days} days)", doc_id=doc_id, student_name=student_name, doc_type=doc_type, expiry_date=expiry_date, days=int(days_left)))

            if expired_docs:
                print(_t("shared.utils.document_manager.expired_docs_header", default="\nExpired Documents:"))
                print("-" * 80)
                for doc in expired_docs:
                    doc_id, student_id, first_name, last_name, email, doc_type, expiry_date, filename = doc
                    student_name = f"{first_name} {last_name}".strip()
                    print(_t("shared.utils.document_manager.expired_doc_line", default="ID: {doc_id} | {student_name} | {doc_type} | Expired: {expiry_date}", doc_id=doc_id, student_name=student_name, doc_type=doc_type, expiry_date=expiry_date))
            
            # Send notifications
            if expiring_docs or expired_docs:
                send_notifications = input("\nSend email notifications? (y/n): ").strip().lower()
                
                if send_notifications == 'y':
                    notification_count = 0
                    
                    # Process expiring documents
                    for doc in expiring_docs:
                        doc_id, student_id, first_name, last_name, email_address, doc_type, expiry_date, filename, days_left = doc
                        
                        if email_address and EMAIL_SYSTEM_AVAILABLE:
                            student_name = f"{first_name} {last_name}".strip()
                            days_left_int = int(days_left)

                            template_vars = {
                                'student_name': student_name,
                                'document_type': doc_type,
                                'document_id': doc_id,
                                'filename': filename,
                                'expiry_date': expiry_date,
                                'days_left': days_left_int
                            }

                            subject, body = render_template('document_expiry_warning', template_vars)

                            if send_email(email_address, subject, body):
                                notification_count += 1
                                log_event('info', f"Expiry warning sent to {email_address} for document {doc_id}")
                    
                    # Process expired documents
                    for doc in expired_docs:
                        doc_id, student_id, first_name, last_name, email_address, doc_type, expiry_date, filename = doc
                        
                        # Mark as expired in database
                        cursor.execute('''
                        UPDATE student_documents 
                        SET verification_status = 'Expired'
                        WHERE document_id = ?
                        ''', (doc_id,))
                        
                        if email_address and EMAIL_SYSTEM_AVAILABLE:
                            student_name = f"{first_name} {last_name}".strip()

                            template_vars = {
                                'student_name': student_name,
                                'document_type': doc_type,
                                'document_id': doc_id,
                                'filename': filename,
                                'expiry_date': expiry_date
                            }

                            subject, body = render_template('document_expired', template_vars)

                            if send_email(email_address, subject, body):
                                notification_count += 1
                                log_event('info', f"Expiry notification sent to {email_address} for expired document {doc_id}")
                    
                    conn.commit()
                    print(_t("shared.utils.document_manager.processed_notifications", default="\nProcessed {count} email notifications", count=notification_count))

                else:
                    print(_t("shared.utils.document_manager.notifications_skipped", default="Notifications skipped"))
            else:
                print(_t("shared.utils.document_manager.no_expiry_notifications", default="No documents require expiry notifications"))

            conn.close()

        except sqlite3.Error as e:
            print(_t("shared.utils.document_manager.database_error", default="Database error: {error}", error=str(e)))
            log_event('error', f"Database error in check_document_expiry: {e}")

    def update_document_status(self):
        """Update document status with email notifications"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get document to update
            document_id = input(_t("shared.utils.document_manager.prompt_document_id", default="Enter document ID to update: ")).strip()
            if not document_id.isdigit():
                print(_t("shared.utils.document_manager.invalid_document_id", default="Invalid document ID."))
                conn.close()
                return

            # Get document details
            cursor.execute('''
            SELECT sd.document_id, sd.student_id, s.first_name, s.last_name, s.email_address,
                   dt.type_name, sd.verification_status, sd.original_filename
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.document_id = ? AND sd.is_current_version = 1
            ''', (document_id,))

            doc_info = cursor.fetchone()

            if not doc_info:
                print(_t("shared.utils.document_manager.document_not_found", default="Document not found."))
                conn.close()
                return

            doc_id, student_id, first_name, last_name, email_address, doc_type, current_status, filename = doc_info
            student_name = f"{first_name} {last_name}".strip()

            print(_t("shared.utils.document_manager.document_info", default="\nDocument: {doc_type} for {student_name}", doc_type=doc_type, student_name=student_name))
            print(_t("shared.utils.document_manager.current_status", default="Current Status: {status}", status=current_status))
            print(_t("shared.utils.document_manager.file_info", default="File: {filename}", filename=filename))

            print(_t("shared.utils.document_manager.new_status_options", default="\nNew Status Options:"))
            print(_t("shared.utils.document_manager.status_option_verified", default="1. Verified"))
            print(_t("shared.utils.document_manager.status_option_rejected", default="2. Rejected"))
            print(_t("shared.utils.document_manager.status_option_pending", default="3. Pending"))
            print(_t("shared.utils.document_manager.status_option_expired", default="4. Expired"))
            print(_t("shared.utils.document_manager.status_option_under_review", default="5. Under Review"))

            choice = input(_t("shared.utils.document_manager.prompt_choose_status", default="Choose new status (1-5): ")).strip()

            status_map = {
                '1': 'Verified',
                '2': 'Rejected',
                '3': 'Pending',
                '4': 'Expired',
                '5': 'Under Review'
            }

            if choice not in status_map:
                print(_t("shared.utils.document_manager.invalid_choice", default="Invalid choice. Please try again."))
                conn.close()
                return

            new_status = status_map[choice]
            notes = input(_t("shared.utils.document_manager.prompt_verification_notes", default="Verification notes (optional): ")).strip()

            # Update document status
            verification_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if new_status != 'Pending' else None

            cursor.execute('''
            UPDATE student_documents
            SET verification_status = ?, verification_date = ?, verification_notes = ?
            WHERE document_id = ?
            ''', (new_status, verification_date, notes, doc_id))

            # Create notification
            if new_status == 'Verified':
                notification_title = f"Document Verified: {doc_type}"
                notification_message = f"Your {doc_type} has been verified and approved."
            elif new_status == 'Rejected':
                notification_title = f"Document Rejected: {doc_type}"
                notification_message = f"Your {doc_type} has been rejected. {notes if notes else 'Please contact the registrar for details.'}"
            else:
                notification_title = f"Document Status Updated: {doc_type}"
                notification_message = f"Your {doc_type} status has been updated to {new_status}."

            self.create_notification(cursor, student_id, 'status_update',
                                   notification_title, notification_message, doc_id)

            conn.commit()
            conn.close()

            print(_t("shared.utils.document_manager.status_updated", default="\nDocument status updated to: {status}", status=new_status))
            
            # Send detailed email notification
            if EMAIL_SYSTEM_AVAILABLE and email_address:
                try:
                    template_vars = {
                        'student_name': student_name,
                        'document_type': doc_type,
                        'document_id': doc_id,
                        'filename': filename,
                        'verification_date': verification_date,
                        'notes': notes or ''
                    }

                    if new_status == 'Verified':
                        subject, body = render_template('document_verified', template_vars)
                    elif new_status == 'Rejected':
                        subject, body = render_template('document_rejected', template_vars)
                    else:
                        template_vars['status'] = new_status
                        template_vars['updated_date'] = verification_date or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        subject, body = render_template('document_notification', template_vars)

                    if send_email(email_address, subject, body):
                        log_event('info', f"Status update email sent to {email_address}")
                        print(_t("shared.utils.document_manager.status_email_sent", default="Status update email sent to {email}", email=email_address))
                    else:
                        log_event('warning', f"Failed to send status update email to {email_address}")

                except Exception as e:
                    log_event('error', f"Error sending status update email: {e}")
                    print(_t("shared.utils.document_manager.status_updated_email_failed", default="Status updated but email notification failed"))

        except sqlite3.Error as e:
            print(_t("shared.utils.document_manager.database_error", default="Database error: {error}", error=str(e)))
            log_event('error', f"Database error in update_document_status: {e}")

    def update_document_status(self):
        """Update document status with email notifications"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get document to update
            document_id = input(_t("shared.utils.document_manager.prompt_document_id", default="Enter document ID to update: ")).strip()
            if not document_id.isdigit():
                print(_t("shared.utils.document_manager.invalid_document_id", default="Invalid document ID."))
                conn.close()
                return

            # Get document details
            cursor.execute('''
            SELECT sd.document_id, sd.student_id, s.first_name, s.last_name, s.email_address,
                   dt.type_name, sd.verification_status, sd.original_filename
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.document_id = ? AND sd.is_current_version = 1
            ''', (document_id,))

            doc_info = cursor.fetchone()

            if not doc_info:
                print(_t("shared.utils.document_manager.document_not_found", default="Document not found."))
                conn.close()
                return

            doc_id, student_id, first_name, last_name, email_address, doc_type, current_status, filename = doc_info
            student_name = f"{first_name} {last_name}".strip()

            print(_t("shared.utils.document_manager.document_info", default="\nDocument: {doc_type} for {student_name}", doc_type=doc_type, student_name=student_name))
            print(_t("shared.utils.document_manager.current_status", default="Current Status: {status}", status=current_status))
            print(_t("shared.utils.document_manager.file_info", default="File: {filename}", filename=filename))

            print(_t("shared.utils.document_manager.new_status_options", default="\nNew Status Options:"))
            print(_t("shared.utils.document_manager.status_option_verified", default="1. Verified"))
            print(_t("shared.utils.document_manager.status_option_rejected", default="2. Rejected"))
            print(_t("shared.utils.document_manager.status_option_pending", default="3. Pending"))
            print(_t("shared.utils.document_manager.status_option_expired", default="4. Expired"))
            print(_t("shared.utils.document_manager.status_option_under_review", default="5. Under Review"))

            choice = input(_t("shared.utils.document_manager.prompt_choose_status", default="Choose new status (1-5): ")).strip()

            status_map = {
                '1': 'Verified',
                '2': 'Rejected',
                '3': 'Pending',
                '4': 'Expired',
                '5': 'Under Review'
            }

            if choice not in status_map:
                print(_t("shared.utils.document_manager.invalid_choice", default="Invalid choice. Please try again."))
                conn.close()
                return

            new_status = status_map[choice]
            notes = input(_t("shared.utils.document_manager.prompt_verification_notes", default="Verification notes (optional): ")).strip()

            # Update document status
            verification_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if new_status != 'Pending' else None

            cursor.execute('''
            UPDATE student_documents
            SET verification_status = ?, verification_date = ?, verification_notes = ?
            WHERE document_id = ?
            ''', (new_status, verification_date, notes, doc_id))

            # Create notification
            if new_status == 'Verified':
                notification_title = f"Document Verified: {doc_type}"
                notification_message = f"Your {doc_type} has been verified and approved."
            elif new_status == 'Rejected':
                notification_title = f"Document Rejected: {doc_type}"
                notification_message = f"Your {doc_type} has been rejected. {notes if notes else 'Please contact the registrar for details.'}"
            else:
                notification_title = f"Document Status Updated: {doc_type}"
                notification_message = f"Your {doc_type} status has been updated to {new_status}."

            self.create_notification(cursor, student_id, 'status_update',
                                   notification_title, notification_message, doc_id)

            conn.commit()
            conn.close()

            print(_t("shared.utils.document_manager.status_updated", default="\nDocument status updated to: {status}", status=new_status))
            
            # Send detailed email notification
            if EMAIL_SYSTEM_AVAILABLE and email_address:
                try:
                    template_vars = {
                        'student_name': student_name,
                        'document_type': doc_type,
                        'document_id': doc_id,
                        'filename': filename,
                        'verification_date': verification_date,
                        'notes': notes or ''
                    }

                    if new_status == 'Verified':
                        subject, body = render_template('document_verified', template_vars)
                    elif new_status == 'Rejected':
                        subject, body = render_template('document_rejected', template_vars)
                    else:
                        template_vars['status'] = new_status
                        template_vars['updated_date'] = verification_date or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        subject, body = render_template('document_notification', template_vars)

                    if send_email(email_address, subject, body):
                        log_event('info', f"Status update email sent to {email_address}")
                        print(_t("shared.utils.document_manager.status_email_sent", default="Status update email sent to {email}", email=email_address))
                    else:
                        log_event('warning', f"Failed to send status update email to {email_address}")

                except Exception as e:
                    log_event('error', f"Error sending status update email: {e}")
                    print(_t("shared.utils.document_manager.status_updated_email_failed", default="Status updated but email notification failed"))

        except sqlite3.Error as e:
            print(_t("shared.utils.document_manager.database_error", default="Database error: {error}", error=str(e)))
            log_event('error', f"Database error in update_document_status: {e}")

    def select_student(self, cursor):
        """Enhanced student selection with search"""
        student_id = input("Enter student ID (leave blank to search): ").strip()
        
        if student_id:
            cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
            student = cursor.fetchone()
            if student:
                print(f"Selected: {student[0]} {student[1]} (ID: {student_id})")
                return student_id
            else:
                print(_t("shared.utils.document_manager.student_not_found", default="Student not found."))
                return None
        
        # Search functionality
        search_term = input("Enter search term (name or partial ID): ").strip()
        if not search_term:
            return None
            
        cursor.execute('''
        SELECT student_id, first_name, last_name, course, year
        FROM students
        WHERE first_name LIKE ? OR last_name LIKE ? OR student_id LIKE ?
        ORDER BY last_name, first_name
        LIMIT 20
        ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        
        students = cursor.fetchall()
        
        if not students:
            print("No students found.")
            return None
            
        print("\nSearch Results:")
        for i, (id, first_name, last_name, course, year) in enumerate(students):
            print(f"{i+1}. {last_name}, {first_name} (ID: {id}) - {course} Year {year}")
            
        try:
            choice = int(input("\nSelect student number: ")) - 1
            if 0 <= choice < len(students):
                return students[choice][0]
            else:
                print(_t("shared.utils.document_manager.invalid_selection", default="Invalid selection."))
                return None
        except ValueError:
            print(_t("shared.utils.document_manager.invalid_input", default="Invalid input."))
            return None

    def select_document_type(self, cursor):
        """Enhanced document type selection with categories"""
        cursor.execute('''
        SELECT type_id, type_name, description, has_expiry, max_file_size_mb, 
               allowed_formats, category, is_required
        FROM document_types 
        WHERE is_active = 1 
        ORDER BY category, sort_order, type_name
        ''')
        
        doc_types = cursor.fetchall()
        
        if not doc_types:
            print("No document types available.")
            return None
            
        print("\nAvailable Document Types:")
        current_category = None
        
        for i, (type_id, type_name, desc, has_expiry, max_size, formats, category, required) in enumerate(doc_types):
            if category != current_category:
                print(f"\n📁 {category.upper()}:")
                current_category = category
                
            required_text = " (Required)" if required else ""
            expiry_text = " (Expires)" if has_expiry else ""
            size_text = f" (Max: {max_size}MB)"
            
            print(f"  {i+1}. {type_name}{required_text}{expiry_text}{size_text}")
            print(f"      {desc}")
            print(f"      Formats: {formats}")
        
        try:
            choice = int(input("\nSelect document type: ")) - 1
            if 0 <= choice < len(doc_types):
                selected = doc_types[choice]
                return (selected[0], selected[1], selected[3], selected[4], selected[5])
            else:
                print(_t("shared.utils.document_manager.invalid_selection", default="Invalid selection."))
                return None
        except ValueError:
            print(_t("shared.utils.document_manager.invalid_input", default="Invalid input."))
            return None

    def get_file_upload_details(self, allowed_formats, max_size_mb):
        """Get file upload details with validation"""
        print(f"\nFile Requirements:")
        print(f"Allowed formats: {allowed_formats}")
        print(f"Maximum size: {max_size_mb}MB")
        
        file_path = input("Enter file path: ").strip()
        
        if not file_path or not os.path.exists(file_path):
            print(_t("shared.utils.document_manager.file_not_found", default="File not found."))
            return None
            
        # Validate file format
        file_ext = os.path.splitext(file_path)[1][1:].lower()
        if file_ext not in allowed_formats.lower().split(','):
            print(f"Invalid file format. Allowed: {allowed_formats}")
            return None
            
        # Validate file size
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        
        if file_size_mb > max_size_mb:
            print(f"File too large. Maximum size: {max_size_mb}MB")
            return None
            
        # Generate file hash for duplicate detection
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
            
        original_filename = os.path.basename(file_path)
        
        return file_path, original_filename, file_size, file_hash

    def get_expiry_date(self):
        """Get expiry date with validation"""
        while True:
            expiry_input = input("Enter expiry date (YYYY-MM-DD): ").strip()
            
            try:
                expiry_date = datetime.strptime(expiry_input, '%Y-%m-%d')
                
                if expiry_date <= datetime.now():
                    print("Expiry date must be in the future.")
                    continue
                    
                return expiry_input
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

    def select_tags(self, cursor):
        """Select tags for document"""
        cursor.execute('SELECT tag_name, description FROM document_tags ORDER BY tag_name')
        tags = cursor.fetchall()
        
        if not tags:
            return ""
            
        print("\nAvailable Tags (select multiple with commas):")
        for i, (tag_name, desc) in enumerate(tags):
            print(f"{i+1}. {tag_name} - {desc}")
            
        selection = input("Select tag numbers (e.g., 1,3,5) or press Enter to skip: ").strip()
        
        if not selection:
            return ""
            
        try:
            selected_indices = [int(x.strip()) - 1 for x in selection.split(',')]
            selected_tags = [tags[i][0] for i in selected_indices if 0 <= i < len(tags)]
            return ','.join(selected_tags)
        except ValueError:
            print("Invalid selection. No tags added.")
            return ""

    def create_workflow_steps(self, cursor, document_id, type_id):
        """Create workflow steps for document approval"""
        # Get document type requirements
        cursor.execute('SELECT requires_approval FROM document_types WHERE type_id = ?', (type_id,))
        requires_approval = cursor.fetchone()[0]
        
        if not requires_approval:
            return
            
        # Default workflow steps
        workflow_steps = [
            ('Initial Review', 1, 'registrar'),
            ('Verification', 2, 'admin'),
            ('Final Approval', 3, 'dean')
        ]
        
        for step_name, step_order, assigned_to in workflow_steps:
            cursor.execute('''
            INSERT INTO document_workflow (document_id, step_name, step_order, assigned_to, status)
            VALUES (?, ?, ?, ?, ?)
            ''', (document_id, step_name, step_order, assigned_to, 'pending'))

    def create_notification(self, cursor, recipient_id, notification_type, title, message, document_id=None):
        """Create a notification with integrated email system support"""
        # Insert notification into database
        cursor.execute('''
        INSERT INTO notifications (recipient_id, notification_type, title, message, created_date, related_document_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (recipient_id, notification_type, title, message, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), document_id))
        
        # Send email notification if email system is available
        if EMAIL_SYSTEM_AVAILABLE:
            try:
                # Get recipient email address
                cursor.execute('''
                SELECT email_address, first_name, last_name 
                FROM students WHERE student_id = ?
                ''', (recipient_id,))
                
                recipient_data = cursor.fetchone()
                if recipient_data:
                    email_address, first_name, last_name = recipient_data
                    recipient_name = f"{first_name} {last_name}".strip() or "Student"
                    
                    # Format email content
                    template_vars = {
                        'student_name': recipient_name,
                        'title': title,
                        'message': message
                    }

                    subject, body = render_template('document_notification', template_vars)

                    # Send email
                    if send_email(email_address, subject, body):
                        log_event('info', f"Notification email sent to {email_address} for {notification_type}")
                    else:
                        log_event('warning', f"Failed to send notification email to {email_address}")
                else:
                    log_event('warning', f"Could not find email address for recipient {recipient_id}")
                    
            except Exception as e:
                log_event('error', f"Error sending notification email: {e}")
                
    # Advanced Search System
    def advanced_search(self):
        """Advanced search with multiple filters"""
        print("\n🔍 ADVANCED SEARCH")
        
        # Build search criteria
        criteria = {}
        
        print("\nSearch Filters (press Enter to skip):")
        
        student_search = input("Student name or ID: ").strip()
        if student_search:
            criteria['student'] = student_search
            
        doc_type = input("Document type: ").strip()
        if doc_type:
            criteria['doc_type'] = doc_type
            
        status = input("Status (Pending/Verified/Rejected/Expired): ").strip()
        if status:
            criteria['status'] = status
            
        from_date = input("From date (YYYY-MM-DD): ").strip()
        if from_date:
            criteria['from_date'] = from_date
            
        to_date = input("To date (YYYY-MM-DD): ").strip()
        if to_date:
            criteria['to_date'] = to_date
            
        tags = input("Tags (comma-separated): ").strip()
        if tags:
            criteria['tags'] = tags
            
        # Execute search
        results = self.execute_advanced_search(criteria)
        
        if not results:
            print("No documents found matching your criteria.")
            return
            
        print(f"\n📊 Search Results ({len(results)} documents found):")
        print("-" * 120)
        print(f"{'ID':<5} {'Student':<20} {'Document Type':<25} {'Status':<12} {'Upload Date':<12} {'Version':<8} {'Tags'}")
        print("-" * 120)
        
        for result in results:
            doc_id, student_name, doc_type, status, upload_date, version, tags = result
            tags_display = tags[:20] + "..." if tags and len(tags) > 20 else tags or ""
            print(f"{doc_id:<5} {student_name:<20} {doc_type:<25} {status:<12} {upload_date:<12} {version:<8} {tags_display}")
            
        # Options for search results
        print("\nSearch Result Options:")
        print("1. View document details")
        print("2. Export results")
        print("3. Bulk update status")
        print("4. Return to menu")
        
        choice = input("Choose option (1-4): ").strip()
        
        if choice == '1':
            doc_id = input("Enter document ID to view: ").strip()
            if doc_id.isdigit():
                self.view_document_details(int(doc_id))
        elif choice == '2':
            self.export_search_results(results)
        elif choice == '3':
            self.bulk_update_from_search(results)

    def execute_advanced_search(self, criteria):
        """Execute the advanced search query"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Build dynamic query
            query = '''
            SELECT sd.document_id, 
                   s.first_name || ' ' || s.last_name as student_name,
                   dt.type_name,
                   sd.verification_status,
                   DATE(sd.upload_date) as upload_date,
                   sd.version_number,
                   sd.tags
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.is_current_version = 1
            '''
            
            params = []
            
            # Add search conditions
            if 'student' in criteria:
                query += " AND (s.first_name LIKE ? OR s.last_name LIKE ? OR s.student_id LIKE ?)"
                search_term = f"%{criteria['student']}%"
                params.extend([search_term, search_term, search_term])
                
            if 'doc_type' in criteria:
                query += " AND dt.type_name LIKE ?"
                params.append(f"%{criteria['doc_type']}%")
                
            if 'status' in criteria:
                query += " AND sd.verification_status = ?"
                params.append(criteria['status'])
                
            if 'from_date' in criteria:
                query += " AND DATE(sd.upload_date) >= ?"
                params.append(criteria['from_date'])
                
            if 'to_date' in criteria:
                query += " AND DATE(sd.upload_date) <= ?"
                params.append(criteria['to_date'])
                
            if 'tags' in criteria:
                tag_list = [tag.strip() for tag in criteria['tags'].split(',')]
                tag_conditions = []
                for tag in tag_list:
                    tag_conditions.append("sd.tags LIKE ?")
                    params.append(f"%{tag}%")
                query += " AND (" + " OR ".join(tag_conditions) + ")"
            
            query += " ORDER BY sd.upload_date DESC LIMIT 100"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            conn.close()
            return results
            
        except sqlite3.Error as e:
            print(f"Search error: {e}")
            return []

    # Dashboard and Analytics
    def display_dashboard(self):
        """Display comprehensive dashboard"""
        print("\n📊 SYSTEM DASHBOARD")
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Quick stats
            self.display_quick_stats(cursor)
            
            # Document status overview
            self.display_status_overview(cursor)
            
            # Recent activity
            self.display_recent_activity(cursor)
            
            # Expiry alerts
            self.display_expiry_alerts(cursor)
            
            # Performance metrics
            self.display_performance_metrics(cursor)
            
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Dashboard error: {e}")

    def display_quick_stats(self, cursor):
        """Display quick statistics"""
        print("\n📈 Quick Statistics:")
        print("-" * 50)
        
        # Total documents
        cursor.execute('SELECT COUNT(*) FROM student_documents WHERE is_current_version = 1')
        total_docs = cursor.fetchone()[0]
        
        # Total students with documents
        cursor.execute('SELECT COUNT(DISTINCT student_id) FROM student_documents')
        students_with_docs = cursor.fetchone()[0]
        
        # Pending documents
        cursor.execute('SELECT COUNT(*) FROM student_documents WHERE verification_status = "Pending" AND is_current_version = 1')
        pending_docs = cursor.fetchone()[0]
        
        # Documents uploaded today
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('SELECT COUNT(*) FROM student_documents WHERE DATE(upload_date) = ?', (today,))
        today_uploads = cursor.fetchone()[0]
        
        print(f"Total Documents: {total_docs}")
        print(f"Students with Documents: {students_with_docs}")
        print(f"Pending Review: {pending_docs}")
        print(f"Uploaded Today: {today_uploads}")

    def display_status_overview(self, cursor):
        """Display document status overview"""
        print("\n📋 Document Status Overview:")
        print("-" * 50)
        
        cursor.execute('''
        SELECT verification_status, COUNT(*) as count
        FROM student_documents 
        WHERE is_current_version = 1
        GROUP BY verification_status
        ORDER BY count DESC
        ''')
        
        status_data = cursor.fetchall()
        
        if status_data:
            total = sum(count for _, count in status_data)
            for status, count in status_data:
                percentage = (count / total) * 100 if total > 0 else 0
                print(f"{status:<15}: {count:>5} ({percentage:>5.1f}%)")

    def display_recent_activity(self, cursor):
        """Display recent activity"""
        print("\n🕒 Recent Activity (Last 7 days):")
        print("-" * 80)
        
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        cursor.execute('''
        SELECT DATE(sd.upload_date) as upload_day, 
               COUNT(*) as daily_count
        FROM student_documents sd
        WHERE DATE(sd.upload_date) >= ?
        GROUP BY DATE(sd.upload_date)
        ORDER BY upload_day DESC
        ''', (week_ago,))
        
        activity_data = cursor.fetchall()
        
        if activity_data:
            print(f"{'Date':<12} {'Documents Uploaded':<20}")
            print("-" * 35)
            for date, count in activity_data:
                print(f"{date:<12} {count:<20}")
        else:
            print("No recent activity found.")

    def display_expiry_alerts(self, cursor):
        """Display expiry alerts"""
        print("\n⚠️ Expiry Alerts:")
        print("-" * 80)
        
        # Documents expiring in next 30 days
        future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
        SELECT COUNT(*) 
        FROM student_documents sd
        WHERE sd.expiry_date BETWEEN ? AND ?
        AND sd.verification_status != 'Expired'
        AND sd.is_current_version = 1
        ''', (today, future_date))
        
        expiring_soon = cursor.fetchone()[0]
        
        # Already expired documents
        cursor.execute('''
        SELECT COUNT(*) 
        FROM student_documents sd
        WHERE sd.expiry_date < ?
        AND sd.verification_status != 'Expired'
        AND sd.is_current_version = 1
        ''', (today,))
        
        already_expired = cursor.fetchone()[0]
        
        print(f"Expiring within 30 days: {expiring_soon}")
        print(f"Already expired: {already_expired}")
        
        if expiring_soon > 0 or already_expired > 0:
            print("\n💡 Tip: Use 'Check Document Expiry' to view details and take action.")

    def display_performance_metrics(self, cursor):
        """Display performance metrics"""
        print("\n⚡ Performance Metrics:")
        print("-" * 50)
        
        # Average processing time (mock calculation)
        cursor.execute('''
        SELECT AVG(
            CASE 
                WHEN verification_date IS NOT NULL 
                THEN julianday(verification_date) - julianday(upload_date)
                ELSE NULL
            END
        ) as avg_processing_days
        FROM student_documents
        WHERE verification_date IS NOT NULL
        ''')
        
        avg_processing = cursor.fetchone()[0]
        
        if avg_processing:
            print(f"Average Processing Time: {avg_processing:.1f} days")
        else:
            print("Average Processing Time: No data available")
        
        # Compliance rate
        cursor.execute('''
        SELECT 
            COUNT(DISTINCT s.student_id) as total_students,
            COUNT(DISTINCT CASE WHEN req_count.missing_count = 0 THEN s.student_id END) as compliant_students
        FROM students s
        LEFT JOIN (
            SELECT s.student_id,
                   COUNT(dt.type_id) - COUNT(sd.document_id) as missing_count
            FROM students s
            CROSS JOIN document_types dt
            LEFT JOIN student_documents sd ON s.student_id = sd.student_id 
                AND dt.type_id = sd.type_id 
                AND sd.is_current_version = 1
            WHERE dt.is_required = 1
            GROUP BY s.student_id
        ) req_count ON s.student_id = req_count.student_id
        ''')
        
        total_students, compliant_students = cursor.fetchone()
        
        if total_students > 0:
            compliance_rate = (compliant_students / total_students) * 100
            print(f"Compliance Rate: {compliance_rate:.1f}% ({compliant_students}/{total_students})")

    # Bulk Operations
    def bulk_operations_menu(self):
        """Bulk operations menu"""
        print(_t("shared.utils.document_manager.bulk_operations_header", default="\n📦 BULK OPERATIONS"))
        print(_t("shared.utils.document_manager.menu_bulk_status_update", default="1. Bulk Status Update"))
        print(_t("shared.utils.document_manager.menu_bulk_doc_download", default="2. Bulk Document Download"))
        print(_t("shared.utils.document_manager.menu_bulk_notification_send", default="3. Bulk Notification Send"))
        print(_t("shared.utils.document_manager.menu_bulk_tag_assignment", default="4. Bulk Tag Assignment"))
        print(_t("shared.utils.document_manager.menu_bulk_expiry_update", default="5. Bulk Document Expiry Update"))
        print(_t("shared.utils.document_manager.menu_return_main", default="6. Return to Main Menu"))

        choice = input(_t("shared.utils.document_manager.prompt_choose_option_1_6", default="Choose option (1-6): ")).strip()
        
        if choice == '1':
            self.bulk_status_update()
        elif choice == '2':
            self.bulk_document_download()
        elif choice == '3':
            self.bulk_notification_send()
        elif choice == '4':
            self.bulk_tag_assignment()
        elif choice == '5':
            self.bulk_expiry_update()

    def bulk_status_update(self):
        """Bulk update document status"""
        print(_t("shared.utils.document_manager.bulk_status_update_header", default="\n📝 BULK STATUS UPDATE"))
        
        # Get selection criteria
        print(_t("shared.utils.document_manager.select_docs_to_update", default="Select documents to update:"))
        print(_t("shared.utils.document_manager.option_by_doc_type", default="1. By document type"))
        print("2. By current status")
        print("3. By date range")
        print("4. By student course")
        
        criteria_choice = input("Choose criteria (1-4): ").strip()
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Build query based on criteria
            if criteria_choice == '1':
                # By document type
                doc_type = input("Enter document type name: ").strip()
                cursor.execute('''
                SELECT sd.document_id, s.first_name || ' ' || s.last_name as student_name,
                       dt.type_name, sd.verification_status
                FROM student_documents sd
                JOIN students s ON sd.student_id = s.student_id
                JOIN document_types dt ON sd.type_id = dt.type_id
                WHERE dt.type_name LIKE ? AND sd.is_current_version = 1
                ''', (f'%{doc_type}%',))
                
            elif criteria_choice == '2':
                # By current status
                current_status = input("Enter current status: ").strip()
                cursor.execute('''
                SELECT sd.document_id, s.first_name || ' ' || s.last_name as student_name,
                       dt.type_name, sd.verification_status
                FROM student_documents sd
                JOIN students s ON sd.student_id = s.student_id
                JOIN document_types dt ON sd.type_id = dt.type_id
                WHERE sd.verification_status = ? AND sd.is_current_version = 1
                ''', (current_status,))
                
            elif criteria_choice == '3':
                # By date range
                from_date = input("From date (YYYY-MM-DD): ").strip()
                to_date = input("To date (YYYY-MM-DD): ").strip()
                cursor.execute('''
                SELECT sd.document_id, s.first_name || ' ' || s.last_name as student_name,
                       dt.type_name, sd.verification_status
                FROM student_documents sd
                JOIN students s ON sd.student_id = s.student_id
                JOIN document_types dt ON sd.type_id = dt.type_id
                WHERE DATE(sd.upload_date) BETWEEN ? AND ? AND sd.is_current_version = 1
                ''', (from_date, to_date))
                
            elif criteria_choice == '4':
                # By student course
                course = input("Enter course code: ").strip()
                cursor.execute('''
                SELECT sd.document_id, s.first_name || ' ' || s.last_name as student_name,
                       dt.type_name, sd.verification_status
                FROM student_documents sd
                JOIN students s ON sd.student_id = s.student_id
                JOIN document_types dt ON sd.type_id = dt.type_id
                WHERE s.course LIKE ? AND sd.is_current_version = 1
                ''', (f'%{course}%',))
                
            documents = cursor.fetchall()
            
            if not documents:
                print("No documents found matching criteria.")
                conn.close()
                return
                
            print(f"\nFound {len(documents)} documents:")
            print("-" * 80)
            print(f"{'ID':<5} {'Student':<25} {'Document Type':<25} {'Current Status'}")
            print("-" * 80)
            
            for doc in documents[:10]:  # Show first 10
                print(f"{doc[0]:<5} {doc[1]:<25} {doc[2]:<25} {doc[3]}")
                
            if len(documents) > 10:
                print(f"... and {len(documents) - 10} more documents")
                
            # Confirm bulk update
            confirm = input(f"\nUpdate status for all {len(documents)} documents? (y/n): ").strip().lower()
            
            if confirm != 'y':
                print("Bulk update cancelled.")
                conn.close()
                return
                
            # Get new status
            print("\nNew status options:")
            print("1. Verified")
            print("2. Rejected")
            print("3. Pending")
            print("4. Expired")
            
            status_choice = input("Choose new status (1-4): ").strip()
            status_map = {'1': 'Verified', '2': 'Rejected', '3': 'Pending', '4': 'Expired'}
            
            if status_choice not in status_map:
                print("Invalid status choice.")
                conn.close()
                return
                
            new_status = status_map[status_choice]
            notes = input("Bulk update notes (optional): ").strip()
            
            # Perform bulk update
            doc_ids = [doc[0] for doc in documents]
            verification_date = datetime.now().strftime('%Y-%m-%d') if new_status != 'Pending' else None
            
            # Update all documents
            for doc_id in doc_ids:
                cursor.execute('''
                UPDATE student_documents
                SET verification_status = ?, verification_date = ?, verification_notes = ?
                WHERE document_id = ?
                ''', (new_status, verification_date, f"Bulk update: {notes}" if notes else "Bulk update", doc_id))
            
            conn.commit()
            conn.close()
            
            print(f"\n✅ Successfully updated {len(doc_ids)} documents to status: {new_status}")
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    # Enhanced reporting system
    def generate_reports_menu(self):
        """Enhanced reporting menu"""
        print("\n📊 GENERATE REPORTS")
        print("1. Compliance Report")
        print("2. Document Status Report")
        print("3. Expiry Report")
        print("4. Student Progress Report")
        print("5. Department Analysis")
        print("6. Monthly Summary Report")
        print("7. Custom Report Builder")
        print("8. Return to Main Menu")
        
        choice = input("Choose report (1-8): ").strip()
        
        if choice == '1':
            self.generate_compliance_report()
        elif choice == '2':
            self.generate_status_report()
        elif choice == '3':
            self.generate_expiry_report()
        elif choice == '4':
            self.generate_student_progress_report()
        elif choice == '5':
            self.generate_department_analysis()
        elif choice == '6':
            self.generate_monthly_summary()
        elif choice == '7':
            self.custom_report_builder()

    def generate_compliance_report(self):
        """Generate detailed compliance report"""
        print("\n📋 COMPLIANCE REPORT")
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get report parameters
            print("Report Parameters:")
            course_filter = input("Course filter (leave blank for all): ").strip()
            year_filter = input("Year filter (leave blank for all): ").strip()
            
            # Build query
            base_query = '''
            SELECT s.student_id, s.first_name, s.last_name, s.course, s.year,
                   GROUP_CONCAT(DISTINCT missing_docs.type_name) as missing_documents,
                   COUNT(DISTINCT submitted_docs.document_id) as submitted_count,
                   COUNT(DISTINCT req_types.type_id) as required_count
            FROM students s
            CROSS JOIN document_types req_types
            LEFT JOIN student_documents submitted_docs ON s.student_id = submitted_docs.student_id 
                AND req_types.type_id = submitted_docs.type_id 
                AND submitted_docs.is_current_version = 1
            LEFT JOIN document_types missing_docs ON req_types.type_id = missing_docs.type_id 
                AND submitted_docs.document_id IS NULL
                AND missing_docs.is_required = 1
            WHERE req_types.is_required = 1
            '''
            
            params = []
            
            if course_filter:
                base_query += " AND s.course LIKE ?"
                params.append(f'%{course_filter}%')
                
            if year_filter:
                base_query += " AND s.year = ?"
                params.append(year_filter)
                
            base_query += " GROUP BY s.student_id ORDER BY s.last_name, s.first_name"
            
            cursor.execute(base_query, params)
            results = cursor.fetchall()
            
            if not results:
                print("No students found.")
                conn.close()
                return
                
            # Generate report
            print(f"\n📊 COMPLIANCE REPORT")
            print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 120)
            
            compliant_students = 0
            total_students = len(results)
            
            print(f"{'Student ID':<12} {'Name':<25} {'Course':<8} {'Year':<5} {'Status':<15} {'Missing Documents'}")
            print("-" * 120)
            
            for result in results:
                student_id, first_name, last_name, course, year, missing_docs, submitted, required = result
                
                if missing_docs:
                    status = "Non-Compliant"
                    missing_display = missing_docs[:50] + "..." if len(missing_docs) > 50 else missing_docs
                else:
                    status = "Compliant"
                    missing_display = "None"
                    compliant_students += 1
                    
                full_name = f"{first_name} {last_name}"
                print(f"{student_id:<12} {full_name:<25} {course:<8} {year:<5} {status:<15} {missing_display}")
            
            # Summary
            compliance_rate = (compliant_students / total_students) * 100 if total_students > 0 else 0
            
            print("\n" + "=" * 60)
            print("SUMMARY:")
            print(f"Total Students: {total_students}")
            print(f"Compliant Students: {compliant_students}")
            print(f"Non-Compliant Students: {total_students - compliant_students}")
            print(f"Compliance Rate: {compliance_rate:.1f}%")
            
            # Export option
            export = input("\nExport to CSV? (y/n): ").strip().lower()
            if export == 'y':
                self.export_compliance_report(results, course_filter, year_filter)
                
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Report generation error: {e}")

    def export_compliance_report(self, data, course_filter, year_filter):
        """Export compliance report to CSV"""
        filename = f"compliance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(['Student ID', 'First Name', 'Last Name', 'Course', 'Year', 'Status', 'Missing Documents'])
                
                # Write data
                for result in data:
                    student_id, first_name, last_name, course, year, missing_docs, submitted, required = result
                    status = "Compliant" if not missing_docs else "Non-Compliant"
                    missing_display = missing_docs if missing_docs else "None"
                    
                    writer.writerow([student_id, first_name, last_name, course, year, status, missing_display])
                    
            print(f"✅ Report exported to: {filename}")
            
        except Exception as e:
            print(f"Export error: {e}")

    # Student self-service functions
    def view_my_documents(self):
        """Student view of their own documents"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get student ID from username
            cursor.execute('SELECT student_id FROM students WHERE first_name || " " || last_name = ?', (self.current_user,))
            result = cursor.fetchone()
            
            if not result:
                # Try to find by username pattern
                cursor.execute('''
                SELECT student_id, first_name, last_name 
                FROM students 
                WHERE LOWER(first_name || last_name) LIKE LOWER(?)
                ''', (f'%{self.current_user}%',))
                result = cursor.fetchone()
                
                if not result:
                    print("Could not find your student record. Please contact administration.")
                    conn.close()
                    return
                    
            student_id = result[0]
            
            # Get student info
            cursor.execute('SELECT first_name, last_name, course, year FROM students WHERE student_id = ?', (student_id,))
            student_info = cursor.fetchone()
            
            print(f"\n📄 MY DOCUMENTS")
            print(f"Student: {student_info[0]} {student_info[1]} (ID: {student_id})")
            print(f"Course: {student_info[2]}, Year: {student_info[3]}")
            print("=" * 80)
            
            # Get all documents
            cursor.execute('''
            SELECT sd.document_id, dt.type_name, sd.original_filename, 
                   sd.upload_date, sd.expiry_date, sd.verification_status,
                   sd.version_number, sd.verification_notes
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.student_id = ? AND sd.is_current_version = 1
            ORDER BY dt.sort_order, sd.upload_date DESC
            ''', (student_id,))
            
            documents = cursor.fetchall()
            
            if documents:
                print(f"{'Type':<25} {'Status':<12} {'Upload Date':<12} {'Expiry':<12} {'Version':<8} {'Notes'}")
                print("-" * 80)
                
                for doc in documents:
                    doc_id, type_name, filename, upload_date, expiry_date, status, version, notes = doc
                    
                    expiry_display = expiry_date[:10] if expiry_date else "N/A"
                    upload_display = upload_date[:10] if upload_date else "N/A"
                    notes_display = notes[:20] + "..." if notes and len(notes) > 20 else notes or ""
                    
                    print(f"{type_name:<25} {status:<12} {upload_display:<12} {expiry_display:<12} {version:<8} {notes_display}")
            else:
                print("No documents uploaded yet.")
                
            # Show missing required documents
            cursor.execute('''
            SELECT dt.type_name, dt.description
            FROM document_types dt
            WHERE dt.is_required = 1 AND dt.type_id NOT IN (
                SELECT sd.type_id FROM student_documents sd 
                WHERE sd.student_id = ? AND sd.is_current_version = 1
            )
            ORDER BY dt.sort_order
            ''', (student_id,))
            
            missing_docs = cursor.fetchall()
            
            if missing_docs:
                print(f"\n⚠️ MISSING REQUIRED DOCUMENTS ({len(missing_docs)}):")
                print("-" * 60)
                for type_name, description in missing_docs:
                    print(f"• {type_name} - {description}")
                    
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def student_upload_document(self):
        """Allow student to upload their own documents"""
        print("\n📤 UPLOAD DOCUMENT")
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get student ID (simplified for demo)
            student_id = input("Enter your student ID: ").strip()
            
            # Verify student
            cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
            student = cursor.fetchone()
            
            if not student:
                print("Student ID not found.")
                conn.close()
                return
                
            print(f"Uploading for: {student[0]} {student[1]}")
            
            # Show available document types
            cursor.execute('''
            SELECT type_id, type_name, description, max_file_size_mb, allowed_formats
            FROM document_types 
            WHERE is_active = 1
            ORDER BY is_required DESC, sort_order
            ''')
            
            doc_types = cursor.fetchall()
            
            print("\nAvailable Document Types:")
            for i, (type_id, type_name, desc, max_size, formats) in enumerate(doc_types):
                print(f"{i+1}. {type_name} (Max: {max_size}MB, Formats: {formats})")
                print(f"   {desc}")
                
            try:
                choice = int(input("\nSelect document type: ")) - 1
                if choice < 0 or choice >= len(doc_types):
                    print(_t("shared.utils.document_manager.invalid_selection", default="Invalid selection."))
                    conn.close()
                    return
                    
                selected_type = doc_types[choice]
                type_id, type_name, desc, max_size, allowed_formats = selected_type
                
            except ValueError:
                print(_t("shared.utils.document_manager.invalid_input", default="Invalid input."))
                conn.close()
                return
                
            # Get file upload details
            file_info = self.get_file_upload_details(allowed_formats, max_size)
            if not file_info:
                conn.close()
                return
                
            file_path, original_filename, file_size, file_hash = file_info
            
            # Insert document
            upload_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO student_documents 
            (student_id, type_id, file_path, original_filename, upload_date, 
             verification_status, uploaded_by, file_size, file_hash, workflow_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, type_id, file_path, original_filename, upload_date,
                  'Pending', f'student_{student_id}', file_size, file_hash, 'submitted'))
            
            document_id = cursor.lastrowid
            
            # Create notification for admin
            self.create_notification(cursor, 'admin', 'student_document_uploaded',
                                   f'Student Document Uploaded: {type_name}',
                                   f'Student {student_id} ({student[0]} {student[1]}) has uploaded {type_name}.',
                                   document_id)
            
            conn.commit()
            conn.close()
            
            print(f"\n✅ Document uploaded successfully!")
            print(f"Document ID: {document_id}")
            print(f"Status: Pending Review")
            print("You will be notified once the document is reviewed.")
            
        except sqlite3.Error as e:
            print(f"Upload error: {e}")

    def student_dashboard(self):
        """Student dashboard with progress overview"""
        print("\n📊 MY DASHBOARD")
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get student ID (simplified)
            student_id = input("Enter your student ID: ").strip()
            
            # Get student info
            cursor.execute('SELECT first_name, last_name, course, year FROM students WHERE student_id = ?', (student_id,))
            student = cursor.fetchone()
            
            if not student:
                print(_t("shared.utils.document_manager.student_not_found", default="Student not found."))
                conn.close()
                return
                
            print(f"\nWelcome, {student[0]} {student[1]}!")
            print(f"Course: {student[2]}, Year: {student[3]}")
            print("=" * 60)
            
            # Document completion status
            cursor.execute('''
            SELECT COUNT(DISTINCT dt.type_id) as required_count
            FROM document_types dt
            WHERE dt.is_required = 1
            ''')
            
            total_required = cursor.fetchone()[0]
            
            cursor.execute('''
            SELECT COUNT(DISTINCT sd.type_id) as submitted_count
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.student_id = ? AND dt.is_required = 1 AND sd.is_current_version = 1
            ''', (student_id,))
            
            submitted_required = cursor.fetchone()[0]
            
            completion_rate = (submitted_required / total_required) * 100 if total_required > 0 else 0
            
            print(f"📈 COMPLETION STATUS:")
            print(f"Required Documents: {submitted_required}/{total_required} ({completion_rate:.1f}%)")
            
            # Progress bar
            progress_bar = "█" * int(completion_rate / 10) + "░" * (10 - int(completion_rate / 10))
            print(f"Progress: [{progress_bar}] {completion_rate:.1f}%")
            
            # Recent activity
            print(f"\n🕒 RECENT ACTIVITY:")
            cursor.execute('''
            SELECT dt.type_name, sd.upload_date, sd.verification_status
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.student_id = ? AND sd.is_current_version = 1
            ORDER BY sd.upload_date DESC
            LIMIT 5
            ''', (student_id,))
            
            recent_docs = cursor.fetchall()
            
            if recent_docs:
                for doc_type, upload_date, status in recent_docs:
                    upload_display = upload_date[:10] if upload_date else "Unknown"
                    print(f"• {doc_type} - {status} ({upload_display})")
            else:
                print("No recent activity.")
                
            # Urgent actions needed
            print(f"\n⚠️ ACTION REQUIRED:")
            
            # Missing required documents
            cursor.execute('''
            SELECT dt.type_name
            FROM document_types dt
            WHERE dt.is_required = 1 AND dt.type_id NOT IN (
                SELECT sd.type_id FROM student_documents sd 
                WHERE sd.student_id = ? AND sd.is_current_version = 1
            )
            LIMIT 3
            ''', (student_id,))
            
            missing_docs = cursor.fetchall()
            
            if missing_docs:
                print("Missing Required Documents:")
                for (type_name,) in missing_docs:
                    print(f"• Upload {type_name}")
            else:
                print("✅ All required documents submitted!")
                
            # Expiring documents
            future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            
            cursor.execute('''
            SELECT dt.type_name, sd.expiry_date
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.student_id = ? AND sd.expiry_date <= ? AND sd.expiry_date >= ?
            AND sd.is_current_version = 1
            ''', (student_id, future_date, datetime.now().strftime('%Y-%m-%d')))
            
            expiring_docs = cursor.fetchall()
            
            if expiring_docs:
                print("\nDocuments Expiring Soon:")
                for type_name, expiry_date in expiring_docs:
                    print(f"• {type_name} expires on {expiry_date}")
                    
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Dashboard error: {e}")

    # Notification system
    def notification_center(self):
        """Notification management center"""
        print("\n📢 NOTIFICATION CENTER")
        print("1. View Pending Notifications")
        print("2. Send Custom Notification")
        print("3. Notification Templates")
        print("4. Email Settings")
        print("5. Bulk Notification Campaign")
        print("6. Return to Main Menu")
        
        choice = input("Choose option (1-6): ").strip()
        
        if choice == '1':
            self.view_pending_notifications()
        elif choice == '2':
            self.send_custom_notification()
        elif choice == '3':
            self.notification_templates()
        elif choice == '4':
            self.email_settings()
        elif choice == '5':
            self.bulk_notification_campaign()



    # System settings and configuration
    def system_settings(self):
        """System settings management"""
        print("\n⚙️ SYSTEM SETTINGS")
        print("1. Email Configuration")
        print("2. Document Type Management")
        print("3. Backup Settings")
        print("4. Security Settings")
        print("5. View Current Settings")
        print("6. Return to Main Menu")
        
        choice = input("Choose option (1-6): ").strip()
        
        if choice == '1':
            self.email_configuration()
        elif choice == '2':
            self.document_type_management()
        elif choice == '3':
            self.backup_settings()
        elif choice == '4':
            self.security_settings()
        elif choice == '5':
            self.view_current_settings()

    def view_current_settings(self):
        """View current system settings"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT setting_name, setting_value, description FROM system_settings ORDER BY setting_name')
            settings = cursor.fetchall()
            
            print("\n📋 CURRENT SYSTEM SETTINGS")
            print("=" * 80)
            print(f"{'Setting':<25} {'Value':<20} {'Description'}")
            print("-" * 80)
            
            for setting_name, value, description in settings:
                # Mask sensitive values
                display_value = "*****" if "password" in setting_name.lower() else value
                print(f"{setting_name:<25} {display_value:<20} {description}")
                
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Settings error: {e}")

    # Backup and restore
    def backup_system(self):
        """System backup functionality"""
        print("\n💾 BACKUP SYSTEM")
        print("1. Create Full Backup")
        print("2. Restore from Backup")
        print("3. Schedule Automatic Backup")
        print("4. View Backup History")
        print("5. Return to Main Menu")
        
        choice = input("Choose option (1-5): ").strip()
        
        if choice == '1':
            self.create_full_backup()
        elif choice == '2':
            self.restore_from_backup()
        elif choice == '3':
            self.schedule_automatic_backup()
        elif choice == '4':
            self.view_backup_history()

    def create_full_backup(self):
        """Create a full system backup"""
        try:
            backup_dir = 'backups'
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
                
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"backup_{timestamp}.zip"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            print(f"Creating backup: {backup_filename}")
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                # Backup database
                if os.path.exists(paths.DEFAULT_DB_PATH):
                    backup_zip.write(str(paths.DEFAULT_DB_PATH), 'student_records.db')

                # Backup document files
                if os.path.exists(paths.STUDENT_DOCUMENTS_DIR):
                    for root, dirs, files in os.walk(paths.STUDENT_DOCUMENTS_DIR):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, '.')
                            backup_zip.write(file_path, arcname)
                            
            # Record backup in database
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO audit_log (user_id, action, table_name, record_id, new_values, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (self.current_user, 'BACKUP_CREATED', 'system', backup_filename, 
                  f'Full system backup created: {backup_path}', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Backup created successfully: {backup_path}")
            print(f"Backup size: {os.path.getsize(backup_path) / (1024*1024):.2f} MB")
            
        except Exception as e:
            print(f"Backup error: {e}")

    # Document Versioning Management
    def document_versioning_menu(self):
        """Document versioning management menu"""
        print(_t("shared.utils.document_manager.versioning_header", default="\n📚 DOCUMENT VERSIONING MANAGEMENT"))
        print(_t("shared.utils.document_manager.menu_view_doc_history", default="1. View Document History"))
        print(_t("shared.utils.document_manager.menu_compare_doc_versions", default="2. Compare Document Versions"))
        print(_t("shared.utils.document_manager.menu_restore_previous_version", default="3. Restore Previous Version"))
        print(_t("shared.utils.document_manager.menu_archive_old_versions", default="4. Archive Old Versions"))
        print(_t("shared.utils.document_manager.menu_version_analytics", default="5. Version Analytics"))
        print(_t("shared.utils.document_manager.menu_return_main", default="6. Return to Main Menu"))

        choice = input(_t("shared.utils.document_manager.prompt_choose_option_1_6", default="Choose option (1-6): ")).strip()
        
        if choice == '1':
            self.view_document_history()
        elif choice == '2':
            self.compare_document_versions()
        elif choice == '3':
            self.restore_previous_version()
        elif choice == '4':
            self.archive_old_versions()
        elif choice == '5':
            self.version_analytics()

    def view_document_history(self):
        """View complete version history of a document"""
        doc_id = input(_t("shared.utils.document_manager.prompt_enter_doc_id", default="Enter document ID: ")).strip()
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get document and all its versions
            cursor.execute('''
            SELECT sd.document_id, sd.student_id, s.first_name, s.last_name,
                   dt.type_name, sd.version_number, sd.upload_date, 
                   sd.verification_status, sd.uploaded_by, sd.is_current_version,
                   sd.original_filename, sd.file_size, sd.verification_notes
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.document_id = ? OR sd.parent_document_id = ?
            ORDER BY sd.version_number ASC
            ''', (doc_id, doc_id))
            
            versions = cursor.fetchall()
            
            if not versions:
                print(_t("shared.utils.document_manager.document_not_found", default="Document not found."))
                conn.close()
                return
                
            print(f"\n📜 DOCUMENT VERSION HISTORY")
            print(f"Document: {versions[0][4]} for {versions[0][2]} {versions[0][3]}")
            print("=" * 100)
            
            print(f"{'Ver':<4} {'Upload Date':<12} {'Status':<12} {'Uploaded By':<15} {'Current':<8} {'Size':<10} {'Notes'}")
            print("-" * 100)
            
            for version in versions:
                doc_id, student_id, first_name, last_name, type_name, version_num, upload_date, status, uploaded_by, is_current, filename, file_size, notes = version
                
                upload_display = upload_date[:10] if upload_date else "N/A"
                current_display = "Yes" if is_current else "No"
                size_display = f"{file_size//1024}KB" if file_size else "N/A"
                notes_display = notes[:15] + "..." if notes and len(notes) > 15 else notes or ""
                
                print(f"{version_num:<4} {upload_display:<12} {status:<12} {uploaded_by:<15} {current_display:<8} {size_display:<10} {notes_display}")
                
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def compare_document_versions(self):
        """Compare two versions of a document"""
        print("\n🔍 COMPARE DOCUMENT VERSIONS")
        
        doc_id1 = input("Enter first document ID: ").strip()
        doc_id2 = input("Enter second document ID: ").strip()
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get both documents
            cursor.execute('''
            SELECT sd.document_id, sd.version_number, sd.upload_date, 
                   sd.verification_status, sd.file_size, sd.uploaded_by,
                   sd.original_filename, dt.type_name
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.document_id IN (?, ?)
            ORDER BY sd.version_number
            ''', (doc_id1, doc_id2))
            
            docs = cursor.fetchall()
            
            if len(docs) != 2:
                print("Could not find both documents.")
                conn.close()
                return
                
            print(f"\n📊 VERSION COMPARISON")
            print("=" * 80)
            
            print(f"{'Attribute':<20} {'Version {docs[0][1]}':<25} {'Version {docs[1][1]}':<25}")
            print("-" * 80)
            
            attributes = [
                ("Upload Date", docs[0][2][:10] if docs[0][2] else "N/A", docs[1][2][:10] if docs[1][2] else "N/A"),
                ("Status", docs[0][3], docs[1][3]),
                ("File Size", f"{docs[0][4]//1024}KB" if docs[0][4] else "N/A", f"{docs[1][4]//1024}KB" if docs[1][4] else "N/A"),
                ("Uploaded By", docs[0][5], docs[1][5]),
                ("Filename", docs[0][6], docs[1][6])
            ]
            
            for attr_name, val1, val2 in attributes:
                marker = " ⚠️" if val1 != val2 else ""
                print(f"{attr_name:<20} {val1:<25} {val2:<25}{marker}")
                
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def restore_previous_version(self):
        """Restore a previous version as current"""
        print("\n🔄 RESTORE PREVIOUS VERSION")
        
        doc_id = input("Enter document ID to restore: ").strip()
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get document info
            cursor.execute('''
            SELECT sd.student_id, sd.type_id, s.first_name, s.last_name, dt.type_name
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.document_id = ?
            ''', (doc_id,))
            
            doc_info = cursor.fetchone()
            
            if not doc_info:
                print(_t("shared.utils.document_manager.document_not_found", default="Document not found."))
                conn.close()
                return
                
            student_id, type_id, first_name, last_name, type_name = doc_info
            
            print(f"Restoring {type_name} for {first_name} {last_name}")
            
            confirm = input("Are you sure you want to restore this version? (y/n): ").strip().lower()
            
            if confirm != 'y':
                print("Restore cancelled.")
                conn.close()
                return
                
            # Mark all versions as non-current
            cursor.execute('''
            UPDATE student_documents 
            SET is_current_version = 0 
            WHERE (document_id = ? OR parent_document_id = ?) AND student_id = ? AND type_id = ?
            ''', (doc_id, doc_id, student_id, type_id))
            
            # Mark selected version as current
            cursor.execute('''
            UPDATE student_documents 
            SET is_current_version = 1 
            WHERE document_id = ?
            ''', (doc_id,))
            
            # Log the action
            cursor.execute('''
            INSERT INTO audit_log (user_id, action, table_name, record_id, new_values, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (self.current_user, 'VERSION_RESTORED', 'student_documents', doc_id,
                  f'Restored version for {type_name}', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            conn.commit()
            conn.close()
            
            print("✅ Version restored successfully!")
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    # Workflow Management
    def workflow_management(self):
        """Workflow management system"""
        print("\n🔄 WORKFLOW MANAGEMENT")
        print("1. View Active Workflows")
        print("2. Process Workflow Step")
        print("3. Create Custom Workflow")
        print("4. Workflow Templates")
        print("5. Workflow Analytics")
        print("6. Return to Main Menu")
        
        choice = input("Choose option (1-6): ").strip()
        
        if choice == '1':
            self.view_active_workflows()
        elif choice == '2':
            self.process_workflow_step()
        elif choice == '3':
            self.create_custom_workflow()
        elif choice == '4':
            self.workflow_templates()
        elif choice == '5':
            self.workflow_analytics()

    def view_active_workflows(self):
        """View all active workflows"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT dw.workflow_id, sd.document_id, s.first_name, s.last_name,
                   dt.type_name, dw.step_name, dw.step_order, dw.assigned_to,
                   dw.status, sd.upload_date
            FROM document_workflow dw
            JOIN student_documents sd ON dw.document_id = sd.document_id
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE dw.status = 'pending'
            ORDER BY sd.upload_date ASC, dw.step_order ASC
            ''')
            
            workflows = cursor.fetchall()
            
            if not workflows:
                print("No active workflows found.")
                conn.close()
                return
                
            print(f"\n📋 ACTIVE WORKFLOWS ({len(workflows)} pending steps)")
            print("=" * 120)
            print(f"{'WF ID':<6} {'Doc ID':<7} {'Student':<25} {'Document Type':<20} {'Step':<15} {'Assigned To':<15} {'Age (days)'}")
            print("-" * 120)
            
            for workflow in workflows:
                wf_id, doc_id, first_name, last_name, doc_type, step_name, step_order, assigned_to, status, upload_date = workflow
                
                # Calculate age
                upload_dt = datetime.strptime(upload_date[:10], '%Y-%m-%d')
                age_days = (datetime.now() - upload_dt).days
                
                student_name = f"{first_name} {last_name}"
                print(f"{wf_id:<6} {doc_id:<7} {student_name:<25} {doc_type:<20} {step_name:<15} {assigned_to:<15} {age_days}")
                
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def process_workflow_step(self):
        """Process a workflow step"""
        workflow_id = input("Enter workflow ID to process: ").strip()
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get workflow details
            cursor.execute('''
            SELECT dw.workflow_id, dw.document_id, dw.step_name, dw.assigned_to,
                   s.first_name, s.last_name, dt.type_name
            FROM document_workflow dw
            JOIN student_documents sd ON dw.document_id = sd.document_id
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE dw.workflow_id = ? AND dw.status = 'pending'
            ''', (workflow_id,))
            
            workflow = cursor.fetchone()
            
            if not workflow:
                print("Workflow step not found or already completed.")
                conn.close()
                return
                
            wf_id, doc_id, step_name, assigned_to, first_name, last_name, doc_type = workflow
            
            print(f"\n🔄 PROCESSING WORKFLOW STEP")
            print(f"Document: {doc_type} for {first_name} {last_name}")
            print(f"Step: {step_name}")
            print(f"Assigned to: {assigned_to}")
            
            print("\nStep Actions:")
            print("1. Approve and Continue")
            print("2. Reject and Stop")
            print("3. Request More Information")
            print("4. Reassign to Another User")
            print("5. Cancel")
            
            action = input("Choose action (1-5): ").strip()
            
            if action == '1':
                # Approve and continue
                comments = input("Comments (optional): ").strip()
                
                # Mark current step as completed
                cursor.execute('''
                UPDATE document_workflow 
                SET status = 'completed', completed_date = ?, completed_by = ?, comments = ?
                WHERE workflow_id = ?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), self.current_user, comments, workflow_id))
                
                # Check if there are more steps
                cursor.execute('''
                SELECT workflow_id FROM document_workflow
                WHERE document_id = ? AND step_order > (
                    SELECT step_order FROM document_workflow WHERE workflow_id = ?
                ) AND status = 'pending'
                ORDER BY step_order LIMIT 1
                ''', (doc_id, workflow_id))
                
                next_step = cursor.fetchone()
                
                if not next_step:
                    # No more steps - mark document as verified
                    cursor.execute('''
                    UPDATE student_documents 
                    SET verification_status = 'Verified', verification_date = ?,
                        workflow_status = 'completed'
                    WHERE document_id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d'), doc_id))
                    
                    print("✅ Workflow completed! Document marked as Verified.")
                else:
                    print("✅ Step approved. Workflow continues to next step.")
                    
            elif action == '2':
                # Reject and stop
                reason = input("Rejection reason: ").strip()
                
                cursor.execute('''
                UPDATE document_workflow 
                SET status = 'rejected', completed_date = ?, completed_by = ?, comments = ?
                WHERE workflow_id = ?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), self.current_user, reason, workflow_id))
                
                cursor.execute('''
                UPDATE student_documents 
                SET verification_status = 'Rejected', verification_date = ?,
                    verification_notes = ?, workflow_status = 'rejected'
                WHERE document_id = ?
                ''', (datetime.now().strftime('%Y-%m-%d'), reason, doc_id))
                
                print("❌ Document rejected. Workflow stopped.")
                
            elif action == '5':
                print("Action cancelled.")
                conn.close()
                return
                
            conn.commit()
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    # Custom Report Builder
    def custom_report_builder(self):
        """Custom report builder with flexible criteria"""
        print("\n📊 CUSTOM REPORT BUILDER")
        
        # Step 1: Select data source
        print("Step 1: Select Primary Data Source")
        print("1. Student Documents")
        print("2. Students")
        print("3. Document Types")
        print("4. Workflows")
        print("5. Notifications")
        
        source_choice = input("Choose data source (1-5): ").strip()
        
        if source_choice != '1':
            print("Only Student Documents source is implemented in this demo.")
            return
            
        # Step 2: Select fields
        print("\nStep 2: Select Fields to Include")
        available_fields = {
            '1': ('student_id', 'Student ID'),
            '2': ('student_name', 'Student Name'),
            '3': ('course', 'Course'),
            '4': ('document_type', 'Document Type'),
            '5': ('upload_date', 'Upload Date'),
            '6': ('verification_status', 'Status'),
            '7': ('verification_date', 'Verification Date'),
            '8': ('expiry_date', 'Expiry Date'),
            '9': ('file_size', 'File Size'),
            '10': ('tags', 'Tags'),
            '11': ('version_number', 'Version'),
            '12': ('uploaded_by', 'Uploaded By')
        }
        
        print("Available Fields:")
        for key, (field_name, display_name) in available_fields.items():
            print(f"{key}. {display_name}")
            
        selected_fields = input("\nSelect fields (comma-separated numbers, e.g., 1,2,4,5): ").strip()
        
        try:
            field_indices = [x.strip() for x in selected_fields.split(',')]
            selected_field_names = []
            selected_field_displays = []
            
            for idx in field_indices:
                if idx in available_fields:
                    field_name, display_name = available_fields[idx]
                    selected_field_names.append(field_name)
                    selected_field_displays.append(display_name)
                    
        except ValueError:
            print("Invalid field selection.")
            return
            
        # Step 3: Set filters
        print("\nStep 3: Set Filters (press Enter to skip)")
        filters = {}
        
        date_from = input("From date (YYYY-MM-DD): ").strip()
        if date_from:
            filters['date_from'] = date_from
            
        date_to = input("To date (YYYY-MM-DD): ").strip()
        if date_to:
            filters['date_to'] = date_to
            
        status_filter = input("Status filter: ").strip()
        if status_filter:
            filters['status'] = status_filter
            
        course_filter = input("Course filter: ").strip()
        if course_filter:
            filters['course'] = course_filter
            
        # Step 4: Generate report
        print("\nStep 4: Generating Custom Report...")
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Build dynamic query
            field_map = {
                'student_id': 'sd.student_id',
                'student_name': "s.first_name || ' ' || s.last_name",
                'course': 's.course',
                'document_type': 'dt.type_name',
                'upload_date': 'DATE(sd.upload_date)',
                'verification_status': 'sd.verification_status',
                'verification_date': 'DATE(sd.verification_date)',
                'expiry_date': 'sd.expiry_date',
                'file_size': 'sd.file_size',
                'tags': 'sd.tags',
                'version_number': 'sd.version_number',
                'uploaded_by': 'sd.uploaded_by'
            }
            
            select_fields = [field_map[field] for field in selected_field_names if field in field_map]
            
            query = f'''
            SELECT {', '.join(select_fields)}
            FROM student_documents sd
            JOIN students s ON sd.student_id = s.student_id
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.is_current_version = 1
            '''
            
            params = []
            
            # Add filters
            if 'date_from' in filters:
                query += " AND DATE(sd.upload_date) >= ?"
                params.append(filters['date_from'])
                
            if 'date_to' in filters:
                query += " AND DATE(sd.upload_date) <= ?"
                params.append(filters['date_to'])
                
            if 'status' in filters:
                query += " AND sd.verification_status LIKE ?"
                params.append(f"%{filters['status']}%")
                
            if 'course' in filters:
                query += " AND s.course LIKE ?"
                params.append(f"%{filters['course']}%")
                
            query += " ORDER BY sd.upload_date DESC LIMIT 1000"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            if not results:
                print("No data found matching your criteria.")
                conn.close()
                return
                
            # Display results
            print(f"\n📋 CUSTOM REPORT RESULTS ({len(results)} records)")
            print("=" * 120)
            
            # Print header
            header = " | ".join([display[:15] for display in selected_field_displays])
            print(header)
            print("-" * len(header))
            
            # Print data
            for row in results:
                formatted_row = []
                for i, value in enumerate(row):
                    if value is None:
                        formatted_value = "N/A"
                    elif isinstance(value, int) and selected_field_names[i] == 'file_size':
                        formatted_value = f"{value//1024}KB"
                    else:
                        formatted_value = str(value)
                    formatted_row.append(formatted_value[:15])
                    
                print(" | ".join(formatted_row))
                
            # Export option
            export = input(f"\nExport {len(results)} records to CSV? (y/n): ").strip().lower()
            if export == 'y':
                self.export_custom_report(results, selected_field_displays, filters)
                
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Report generation error: {e}")

    def export_custom_report(self, data, headers, filters):
        """Export custom report to CSV"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"custom_report_{timestamp}.csv"
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write metadata
                writer.writerow(['# Custom Report'])
                writer.writerow([f'# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
                writer.writerow([f'# Total Records: {len(data)}'])
                
                # Write filters
                if filters:
                    writer.writerow(['# Filters Applied:'])
                    for key, value in filters.items():
                        writer.writerow([f'# {key}: {value}'])
                        
                writer.writerow([])  # Empty row
                
                # Write headers
                writer.writerow(headers)
                
                # Write data
                for row in data:
                    writer.writerow(row)
                    
            print(f"✅ Custom report exported to: {filename}")
            
        except Exception as e:
            print(f"Export error: {e}")

    # OCR Integration Placeholder
    def ocr_integration_menu(self):
        """OCR integration for document text extraction"""
        print(_t("shared.utils.document_manager.ocr_header", default="\n🔤 OCR INTEGRATION"))
        print(_t("shared.utils.document_manager.menu_extract_text", default="1. Extract Text from Document"))
        print(_t("shared.utils.document_manager.menu_batch_ocr", default="2. Batch OCR Processing"))
        print(_t("shared.utils.document_manager.menu_ocr_settings", default="3. OCR Settings"))
        print(_t("shared.utils.document_manager.menu_view_ocr_results", default="4. View OCR Results"))
        print(_t("shared.utils.document_manager.menu_return_main", default="5. Return to Main Menu"))

        choice = input(_t("shared.utils.document_manager.prompt_choose_option_1_5", default="Choose option (1-5): ")).strip()
        
        if choice == '1':
            self.extract_text_from_document()
        elif choice == '2':
            self.batch_ocr_processing()
        elif choice == '3':
            self.ocr_settings()
        elif choice == '4':
            self.view_ocr_results()

    def extract_text_from_document(self):
        """Extract text from a document using OCR (placeholder)"""
        print(_t("shared.utils.document_manager.extract_text_header", default="\n🔤 EXTRACT TEXT FROM DOCUMENT"))

        doc_id = input(_t("shared.utils.document_manager.prompt_enter_doc_id", default="Enter document ID: ")).strip()
        
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
                print(_t("shared.utils.document_manager.document_not_found", default="Document not found."))
                conn.close()
                return
                
            file_path, filename, doc_type, first_name, last_name = doc
            
            print(f"Processing: {filename} ({doc_type}) for {first_name} {last_name}")
            
            # Placeholder OCR processing
            print("🔄 Processing document with OCR...")
            time.sleep(2)  # Simulate processing time
            
            # Mock extracted text
            mock_extracted_text = f"""
EXTRACTED TEXT FROM {filename.upper()}

Document Type: {doc_type}
Student Name: {first_name} {last_name}
Document ID: {doc_id}

[This is a placeholder for OCR-extracted text]
[In a real implementation, this would use libraries like:]
[- Tesseract OCR (pytesseract)]
[- Google Cloud Vision API]
[- AWS Textract]
[- Azure Computer Vision]

Sample extracted content:
- Name: {first_name} {last_name}
- Document Type: {doc_type}
- Issue Date: 2024-01-15
- Expiry Date: 2029-01-15
- Document Number: ABC123456789
            """
            
            print(_t("shared.utils.document_manager.ocr_complete", default="OCR Processing Complete!"))
            print("\n📄 EXTRACTED TEXT:")
            print("-" * 60)
            print(mock_extracted_text)
            
            # Option to save extracted text
            save_text = input("\nSave extracted text to database? (y/n): ").strip().lower()
            
            if save_text == 'y':
                # Add OCR results table if it doesn't exist
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
                ''', (doc_id, mock_extracted_text, 0.95, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                
                conn.commit()
                print(_t("shared.utils.document_manager.ocr_results_saved", default="OCR results saved to database."))
                
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    # API Endpoints Placeholder
    def api_server_menu(self):
        """API server management"""
        print(_t("shared.utils.document_manager.api_server_header", default="\n🌐 API SERVER MANAGEMENT"))
        print(_t("shared.utils.document_manager.menu_start_api_server", default="1. Start API Server"))
        print(_t("shared.utils.document_manager.menu_view_api_endpoints", default="2. View API Endpoints"))
        print(_t("shared.utils.document_manager.menu_api_documentation", default="3. API Documentation"))
        print(_t("shared.utils.document_manager.menu_api_keys_mgmt", default="4. API Keys Management"))
        print(_t("shared.utils.document_manager.menu_api_usage_stats", default="5. API Usage Statistics"))
        print(_t("shared.utils.document_manager.menu_return_main", default="6. Return to Main Menu"))

        choice = input(_t("shared.utils.document_manager.prompt_choose_option_1_6", default="Choose option (1-6): ")).strip()
        
        if choice == '1':
            self.start_api_server()
        elif choice == '2':
            self.view_api_endpoints()
        elif choice == '3':
            self.api_documentation()
        elif choice == '4':
            self.api_keys_management()
        elif choice == '5':
            self.api_usage_statistics()

    def start_api_server(self):
        """Start the REST API server (placeholder)"""
        print("\n🚀 STARTING API SERVER")
        
        print("API Server Configuration:")
        print("- Host: localhost")
        print("- Port: 8080")
        print("- Protocol: HTTP")
        print("- Authentication: API Key Required")
        
        print("\n📡 Starting server...")
        time.sleep(2)
        
        print(_t("shared.utils.document_manager.api_server_started", default="API Server Started Successfully!"))
        print("\n🔗 Available Endpoints:")
        
        endpoints = [
            "GET    /api/v1/students",
            "GET    /api/v1/students/{id}/documents",
            "POST   /api/v1/documents/upload",
            "GET    /api/v1/documents/{id}",
            "PUT    /api/v1/documents/{id}/status",
            "GET    /api/v1/reports/compliance",
            "GET    /api/v1/notifications",
            "POST   /api/v1/notifications/send"
        ]
        
        for endpoint in endpoints:
            print(f"  {endpoint}")
            
        print(f"\n📖 API Documentation: http://localhost:8080/docs")
        print(f"🔍 Health Check: http://localhost:8080/health")
        
        print("\n⚠️ Note: This is a placeholder implementation.")
        print("In production, you would use frameworks like:")
        print("- FastAPI (Python)")
        print("- Flask (Python)")
        print("- Express.js (Node.js)")
        print("- Django REST Framework (Python)")

    def view_api_endpoints(self):
        """View all available API endpoints"""
        print("\n📋 API ENDPOINTS REFERENCE")
        print("=" * 80)
        
        api_groups = {
            "Authentication": [
                ("POST", "/api/v1/auth/login", "User authentication"),
                ("POST", "/api/v1/auth/logout", "User logout"),
                ("POST", "/api/v1/auth/refresh", "Refresh access token")
            ],
            "Students": [
                ("GET", "/api/v1/students", "List all students"),
                ("GET", "/api/v1/students/{id}", "Get student by ID"),
                ("POST", "/api/v1/students", "Create new student"),
                ("PUT", "/api/v1/students/{id}", "Update student"),
                ("DELETE", "/api/v1/students/{id}", "Delete student")
            ],
            "Documents": [
                ("GET", "/api/v1/documents", "List documents with filters"),
                ("GET", "/api/v1/documents/{id}", "Get document by ID"),
                ("POST", "/api/v1/documents/upload", "Upload new document"),
                ("PUT", "/api/v1/documents/{id}", "Update document"),
                ("DELETE", "/api/v1/documents/{id}", "Delete document"),
                ("GET", "/api/v1/documents/{id}/versions", "Get document versions"),
                ("POST", "/api/v1/documents/{id}/verify", "Verify document")
            ],
            "Reports": [
                ("GET", "/api/v1/reports/compliance", "Compliance report"),
                ("GET", "/api/v1/reports/status", "Status report"),
                ("GET", "/api/v1/reports/custom", "Custom report with filters"),
                ("POST", "/api/v1/reports/export", "Export report data")
            ],
            "System": [
                ("GET", "/api/v1/health", "System health check"),
                ("GET", "/api/v1/stats", "System statistics"),
                ("POST", "/api/v1/backup", "Create system backup"),
                ("GET", "/api/v1/version", "API version info")
            ]
        }
        
        for group_name, endpoints in api_groups.items():
            print(f"\n📁 {group_name.upper()}:")
            print("-" * 60)
            
            for method, endpoint, description in endpoints:
                print(f"{method:<7} {endpoint:<35} {description}")

    # Mobile-Responsive Web Interface Placeholder
    def web_interface_menu(self):
        """Web interface management"""
        print(_t("shared.utils.document_manager.web_interface_header", default="\n📱 WEB INTERFACE MANAGEMENT"))
        print(_t("shared.utils.document_manager.menu_start_web_server", default="1. Start Web Server"))
        print(_t("shared.utils.document_manager.menu_generate_mobile_interface", default="2. Generate Mobile Interface"))
        print(_t("shared.utils.document_manager.menu_web_settings", default="3. Web Interface Settings"))
        print(_t("shared.utils.document_manager.menu_view_access_logs", default="4. View Access Logs"))
        print(_t("shared.utils.document_manager.menu_mobile_qr_code", default="5. Mobile App QR Code"))
        print(_t("shared.utils.document_manager.menu_return_main", default="6. Return to Main Menu"))

        choice = input(_t("shared.utils.document_manager.prompt_choose_option_1_6", default="Choose option (1-6): ")).strip()
        
        if choice == '1':
            self.start_web_server()
        elif choice == '2':
            self.generate_mobile_interface()
        elif choice == '3':
            self.web_interface_settings()
        elif choice == '4':
            self.view_access_logs()
        elif choice == '5':
            self.mobile_app_qr_code()

    def start_web_server(self):
        """Start the web interface server"""
        print("\n🌐 STARTING WEB INTERFACE")
        
        print("Web Server Configuration:")
        print("- Host: 0.0.0.0")
        print("- Port: 5000")
        print("- SSL: Enabled")
        print("- Responsive Design: Yes")
        print("- PWA Support: Yes")
        
        print("\n🔄 Initializing web server...")
        time.sleep(2)
        
        print(_t("shared.utils.document_manager.web_interface_started", default="Web Interface Started Successfully!"))
        
        print("\n🔗 Access URLs:")
        print("- Desktop: https://localhost:5000")
        print("- Mobile: https://localhost:5000/mobile")
        print("- Admin Panel: https://localhost:5000/admin")
        print("- Student Portal: https://localhost:5000/student")
        
        print("\n📱 Mobile Features:")
        print("- Touch-friendly interface")
        print("- Camera document capture")
        print("- Offline document queue")
        print("- Push notifications")
        print("- Biometric authentication")
        
        print("\n⚠️ Note: This is a placeholder implementation.")
        print("In production, you would use:")
        print("- React/Vue.js for frontend")
        print("- Progressive Web App (PWA)")
        print("- Responsive CSS frameworks")
        print("- Mobile-first design principles")

    def generate_mobile_interface(self):
        """Generate mobile-responsive interface code"""
        print("\n📱 GENERATING MOBILE INTERFACE")
        
        print("Creating mobile-responsive HTML templates...")
        
        # Create basic mobile HTML template
        mobile_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Student Document Portal</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f5f5; }
        .container { max-width: 100%; padding: 20px; margin: 0 auto; }
        .header { background: #2196F3; color: white; padding: 20px; text-align: center; }
        .card { background: white; border-radius: 8px; padding: 20px; margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .button { background: #2196F3; color: white; border: none; padding: 15px 30px; border-radius: 5px; width: 100%; margin: 10px 0; font-size: 16px; }
        .status-pending { color: #ff9800; }
        .status-verified { color: #4caf50; }
        .status-rejected { color: #f44336; }
        @media (max-width: 768px) {
            .container { padding: 10px; }
            .button { padding: 12px 20px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📄 Document Portal</h1>
        <p>Manage your documents on the go</p>
    </div>
    
    <div class="container">
        <div class="card">
            <h2>📊 My Documents</h2>
            <div class="status-verified">✅ ID Photo - Verified</div>
            <div class="status-pending">⏳ Transcript - Pending</div>
            <div class="status-rejected">❌ Birth Certificate - Rejected</div>
        </div>
        
        <div class="card">
            <h2>📤 Quick Actions</h2>
            <button class="button">📷 Capture Document</button>
            <button class="button">📁 Upload from Gallery</button>
            <button class="button">📋 Check Requirements</button>
        </div>
        
        <div class="card">
            <h2>🔔 Notifications</h2>
            <p>Your transcript is pending verification...</p>
        </div>
    </div>
</body>
</html>'''
        
        try:
            with open('mobile_interface.html', 'w', encoding='utf-8') as f:
                f.write(mobile_html)
                
            print(_t("shared.utils.document_manager.mobile_interface_generated", default="Mobile interface generated successfully!"))
            print("📄 File created: mobile_interface.html")
            print("\nFeatures included:")
            print("- Responsive design for all screen sizes")
            print("- Touch-friendly buttons and forms")
            print("- Modern mobile UI components")
            print("- Status indicators with colors")
            print("- Progressive Web App ready")
            
        except Exception as e:
            print(f"Error generating interface: {e}")

    # Additional Missing Functions
    def bulk_import_documents(self):
        """Bulk import documents from CSV/Excel"""
        print(_t("shared.utils.document_manager.bulk_import_header", default="\n📦 BULK IMPORT DOCUMENTS"))
        print(_t("shared.utils.document_manager.menu_import_csv", default="1. Import from CSV"))
        print(_t("shared.utils.document_manager.menu_import_excel", default="2. Import from Excel"))
        print(_t("shared.utils.document_manager.menu_download_template", default="3. Download Import Template"))
        print(_t("shared.utils.document_manager.menu_return_main", default="4. Return to Main Menu"))

        choice = input(_t("shared.utils.document_manager.prompt_choose_option_1_4", default="Choose option (1-4): ")).strip()
        
        if choice == '1':
            self.import_from_csv()
        elif choice == '2':
            self.import_from_excel()
        elif choice == '3':
            self.download_import_template()

    def import_from_csv(self):
        """Import documents from CSV file"""
        print("\n📄 IMPORT FROM CSV")
        
        csv_file = input("Enter CSV file path: ").strip()
        
        if not os.path.exists(csv_file):
            print(_t("shared.utils.document_manager.file_not_found", default="File not found."))
            return
            
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                print("CSV Columns found:", list(reader.fieldnames))
                
                required_columns = ['student_id', 'document_type', 'file_path']
                missing_columns = [col for col in required_columns if col not in reader.fieldnames]
                
                if missing_columns:
                    print(f"Missing required columns: {missing_columns}")
                    return
                    
                print("\n🔄 Processing CSV data...")
                
                success_count = 0
                error_count = 0
                
                for row_num, row in enumerate(reader, 1):
                    try:
                        # Process each row
                        student_id = row['student_id'].strip()
                        document_type = row['document_type'].strip()
                        file_path = row['file_path'].strip()
                        
                        # Validate and import
                        if self.validate_and_import_document(student_id, document_type, file_path):
                            success_count += 1
                        else:
                            error_count += 1
                            print(f"❌ Error in row {row_num}: {student_id}")
                            
                    except Exception as e:
                        error_count += 1
                        print(f"❌ Error processing row {row_num}: {e}")
                        
                print(_t("shared.utils.document_manager.import_completed", default="\nImport completed!"))
                print(f"Success: {success_count} documents")
                print(f"Errors: {error_count} documents")
                
        except Exception as e:
            print(f"CSV import error: {e}")

    def validate_and_import_document(self, student_id, document_type, file_path):
        """Validate and import a single document"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Validate student exists
            cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
            if not cursor.fetchone():
                print(f"Student {student_id} not found")
                conn.close()
                return False
                
            # Validate document type
            cursor.execute('SELECT type_id FROM document_types WHERE type_name = ?', (document_type,))
            type_result = cursor.fetchone()
            if not type_result:
                print(f"Document type '{document_type}' not found")
                conn.close()
                return False
                
            type_id = type_result[0]
            
            # Validate file exists
            if not os.path.exists(file_path):
                print(f"File not found: {file_path}")
                conn.close()
                return False
                
            # Import the document
            original_filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            upload_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO student_documents 
            (student_id, type_id, file_path, original_filename, upload_date, 
             verification_status, uploaded_by, file_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, type_id, file_path, original_filename, upload_date,
                  'Pending', f'bulk_import_{self.current_user}', file_size))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Import error for {student_id}: {e}")
            return False

    def export_data_menu(self):
        """Data export menu"""
        print(_t("shared.utils.document_manager.export_data_header", default="\n📤 EXPORT DATA"))
        print(_t("shared.utils.document_manager.menu_export_students", default="1. Export All Students"))
        print(_t("shared.utils.document_manager.menu_export_documents", default="2. Export All Documents"))
        print(_t("shared.utils.document_manager.menu_export_compliance", default="3. Export Compliance Report"))
        print(_t("shared.utils.document_manager.menu_export_activity_log", default="4. Export User Activity Log"))
        print(_t("shared.utils.document_manager.menu_export_custom", default="5. Export Custom Dataset"))
        print(_t("shared.utils.document_manager.menu_return_main", default="6. Return to Main Menu"))

        choice = input(_t("shared.utils.document_manager.prompt_choose_export_option", default="Choose export option (1-6): ")).strip()
        
        if choice == '1':
            self.export_all_students()
        elif choice == '2':
            self.export_all_documents()
        elif choice == '3':
            self.export_compliance_data()
        elif choice == '4':
            self.export_activity_log()
        elif choice == '5':
            self.export_custom_dataset()

    def export_all_students(self):
        """Export all student data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT student_id, first_name, last_name, email, course, year, 
                   enrollment_date, status
            FROM students
            ORDER BY last_name, first_name
            ''')
            
            students = cursor.fetchall()
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"students_export_{timestamp}.csv"
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(['Student ID', 'First Name', 'Last Name', 'Email', 
                               'Course', 'Year', 'Enrollment Date', 'Status'])
                
                # Write data
                writer.writerows(students)
                
            print(f"✅ Students exported to: {filename}")
            print(f"Total records: {len(students)}")
            
            conn.close()
            
        except Exception as e:
            print(f"Export error: {e}")

    def manage_document_templates(self):
        """Manage document templates and requirements"""
        print(_t("shared.utils.document_manager.template_mgmt_header", default="\n📋 DOCUMENT TEMPLATE MANAGEMENT"))
        print(_t("shared.utils.document_manager.menu_view_doc_types", default="1. View Document Types"))
        print(_t("shared.utils.document_manager.menu_add_doc_type", default="2. Add New Document Type"))
        print(_t("shared.utils.document_manager.menu_modify_doc_type", default="3. Modify Document Type"))
        print(_t("shared.utils.document_manager.menu_set_course_requirements", default="4. Set Course Requirements"))
        print(_t("shared.utils.document_manager.menu_template_analytics", default="5. Template Analytics"))
        print(_t("shared.utils.document_manager.menu_return_main", default="6. Return to Main Menu"))

        choice = input(_t("shared.utils.document_manager.prompt_choose_option_1_6", default="Choose option (1-6): ")).strip()
        
        if choice == '1':
            self.view_document_types()
        elif choice == '2':
            self.add_document_type()
        elif choice == '3':
            self.modify_document_type()
        elif choice == '4':
            self.set_course_requirements()
        elif choice == '5':
            self.template_analytics()

    def view_document_types(self):
        """View all document types"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT type_id, type_name, category, is_required, has_expiry, 
                   max_file_size_mb, allowed_formats, is_active
            FROM document_types
            ORDER BY category, sort_order, type_name
            ''')
            
            doc_types = cursor.fetchall()
            
            print(f"\n📋 DOCUMENT TYPES ({len(doc_types)} total)")
            print("=" * 100)
            print(f"{'ID':<4} {'Name':<25} {'Category':<15} {'Required':<9} {'Expiry':<7} {'Size(MB)':<8} {'Active'}")
            print("-" * 100)
            
            for doc_type in doc_types:
                type_id, name, category, required, expiry, size, formats, active = doc_type
                
                required_text = "Yes" if required else "No"
                expiry_text = "Yes" if expiry else "No"
                active_text = "Yes" if active else "No"
                
                print(f"{type_id:<4} {name:<25} {category:<15} {required_text:<9} {expiry_text:<7} {size:<8} {active_text}")
                
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def check_my_requirements(self):
        """Student check their document requirements"""
        print(_t("shared.utils.document_manager.my_requirements_header", default="\n📋 MY DOCUMENT REQUIREMENTS"))

        student_id = input(_t("shared.utils.document_manager.prompt_enter_student_id", default="Enter your student ID: ")).strip()
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get student info
            cursor.execute('SELECT first_name, last_name, course, year FROM students WHERE student_id = ?', (student_id,))
            student = cursor.fetchone()
            
            if not student:
                print(_t("shared.utils.document_manager.student_not_found", default="Student not found."))
                conn.close()
                return
                
            first_name, last_name, course, year = student
            
            print(f"\nRequirements for: {first_name} {last_name}")
            print(f"Course: {course}, Year: {year}")
            print("=" * 60)
            
            # Get all required documents
            cursor.execute('''
            SELECT dt.type_name, dt.description, dt.has_expiry,
                   CASE WHEN sd.document_id IS NOT NULL THEN 'Submitted' ELSE 'Missing' END as status,
                   sd.verification_status
            FROM document_types dt
            LEFT JOIN student_documents sd ON dt.type_id = sd.type_id 
                AND sd.student_id = ? AND sd.is_current_version = 1
            WHERE dt.is_required = 1
            ORDER BY dt.sort_order
            ''', (student_id,))
            
            requirements = cursor.fetchall()
            
            if requirements:
                print(f"{'Document Type':<25} {'Status':<12} {'Verification':<15} {'Description'}")
                print("-" * 80)
                
                for req in requirements:
                    doc_type, description, has_expiry, status, verification = req
                    
                    if status == 'Missing':
                        status_display = "❌ Missing"
                        verification_display = "N/A"
                    else:
                        status_display = "✅ Submitted"
                        verification_display = verification or "Pending"
                        
                    desc_short = description[:30] + "..." if len(description) > 30 else description
                    
                    print(f"{doc_type:<25} {status_display:<12} {verification_display:<15} {desc_short}")
                    
            # Show submission progress
            submitted_count = sum(1 for req in requirements if req[3] == 'Submitted')
            total_count = len(requirements)
            progress = (submitted_count / total_count) * 100 if total_count > 0 else 0
            
            print(f"\n📊 Progress: {submitted_count}/{total_count} ({progress:.1f}%)")
            
            if submitted_count == total_count:
                print("🎉 Congratulations! All required documents submitted.")
            else:
                missing_count = total_count - submitted_count
                print(f"⚠️  You still need to submit {missing_count} required documents.")
                
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def my_document_status(self):
        """Show detailed status of student's documents"""
        print(_t("shared.utils.document_manager.my_doc_status_header", default="\n📊 MY DOCUMENT STATUS"))

        student_id = input(_t("shared.utils.document_manager.prompt_enter_student_id", default="Enter your student ID: ")).strip()
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get detailed document status
            cursor.execute('''
            SELECT dt.type_name, sd.upload_date, sd.verification_status,
                   sd.verification_date, sd.expiry_date, sd.verification_notes,
                   sd.version_number
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.student_id = ? AND sd.is_current_version = 1
            ORDER BY sd.upload_date DESC
            ''', (student_id,))
            
            documents = cursor.fetchall()
            
            if not documents:
                print("No documents found for this student ID.")
                conn.close()
                return
                
            print(f"\n📄 DOCUMENT STATUS DETAILS")
            print("=" * 100)
            
            for doc in documents:
                doc_type, upload_date, status, verify_date, expiry_date, notes, version = doc
                
                print(f"\n📋 {doc_type} (Version {version})")
                print(f"   Upload Date: {upload_date[:10] if upload_date else 'N/A'}")
                print(f"   Status: {status}")
                
                if verify_date:
                    print(f"   Verified: {verify_date[:10]}")
                    
                if expiry_date:
                    expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d')
                    days_until_expiry = (expiry_dt - datetime.now()).days
                    
                    if days_until_expiry < 0:
                        print(f"   Expiry: {expiry_date} (⚠️ EXPIRED)")
                    elif days_until_expiry < 30:
                        print(f"   Expiry: {expiry_date} (⚠️ Expires in {days_until_expiry} days)")
                    else:
                        print(f"   Expiry: {expiry_date}")
                        
                if notes:
                    print(f"   Notes: {notes}")
                    
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def my_notifications(self):
        """Show student's notifications"""
        print(_t("shared.utils.document_manager.my_notifications_header", default="\n🔔 MY NOTIFICATIONS"))

        student_id = input(_t("shared.utils.document_manager.prompt_enter_student_id", default="Enter your student ID: ")).strip()
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT notification_id, notification_type, title, message, 
                   created_date, is_read, priority
            FROM notifications
            WHERE recipient_id = ?
            ORDER BY created_date DESC
            LIMIT 20
            ''', (student_id,))
            
            notifications = cursor.fetchall()
            
            if not notifications:
                print(_t("shared.utils.document_manager.no_notifications_found", default="No notifications found."))
                conn.close()
                return
                
            print(f"\n📬 YOUR NOTIFICATIONS ({len(notifications)} total)")
            print("=" * 80)
            
            unread_count = 0
            
            for notification in notifications:
                notif_id, notif_type, title, message, created_date, is_read, priority = notification
                
                if not is_read:
                    unread_count += 1
                    
                read_indicator = "📖" if is_read else "📩"
                priority_indicator = "🔴" if priority == 'high' else "🟡" if priority == 'medium' else "⚪"
                
                created_display = created_date[:16] if created_date else "Unknown"
                
                print(f"\n{read_indicator} {priority_indicator} {title}")
                print(f"   {message}")
                print(f"   {created_display}")
                
            print(f"\n📊 Summary: {unread_count} unread, {len(notifications)} total")
            
            # Mark as read option
            if unread_count > 0:
                mark_read = input("\nMark all as read? (y/n): ").strip().lower()
                if mark_read == 'y':
                    cursor.execute('''
                    UPDATE notifications 
                    SET is_read = 1 
                    WHERE recipient_id = ? AND is_read = 0
                    ''', (student_id,))
                    
                    conn.commit()
                    print(_t("shared.utils.document_manager.all_notifications_read", default="All notifications marked as read."))
                    
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    # =============== MISSING METHODS IMPLEMENTATION ===============

    def view_student_documents(self):
        """View all documents for a specific student"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            student_id = self.select_student(cursor)
            if not student_id:
                conn.close()
                return

            cursor.execute('''
            SELECT sd.document_id, dt.type_name, sd.original_filename,
                   sd.upload_date, sd.expiry_date, sd.verification_status,
                   sd.version_number, sd.workflow_status, sd.tags
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.student_id = ? AND sd.is_current_version = 1
            ORDER BY sd.upload_date DESC
            ''', (student_id,))

            documents = cursor.fetchall()

            if not documents:
                print(f"\nNo documents found for student {student_id}.")
                conn.close()
                return

            print(f"\n{'='*80}")
            print(f"DOCUMENTS FOR STUDENT: {student_id}")
            print(f"{'='*80}")

            for doc in documents:
                doc_id, type_name, filename, upload_date, expiry_date, status, version, workflow, tags = doc

                print(f"\nDocument ID: {doc_id}")
                print(f"Type: {type_name}")
                print(f"Filename: {filename}")
                print(f"Uploaded: {upload_date}")
                print(f"Version: {version}")
                print(f"Status: {status} | Workflow: {workflow}")

                if expiry_date:
                    expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d')
                    days_until_expiry = (expiry_dt - datetime.now()).days

                    if days_until_expiry < 0:
                        print(f"Expiry: {expiry_date} (EXPIRED)")
                    elif days_until_expiry < 30:
                        print(f"Expiry: {expiry_date} (Expires in {days_until_expiry} days - WARNING)")
                    else:
                        print(f"Expiry: {expiry_date}")

                if tags:
                    print(f"Tags: {tags}")
                print("-" * 80)

            print(f"\nTotal Documents: {len(documents)}")

            # Offer to view document details
            view_details = input("\nView detailed info for a document? (y/n): ").strip().lower()
            if view_details == 'y':
                self.view_document_details()

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def generate_reports_menu(self):
        """Menu for generating various reports"""
        print(_t("shared.utils.document_manager.reports_header", default="\n📊 REPORT GENERATION"))
        print(_t("shared.utils.document_manager.menu_status_report", default="1. Status Report"))
        print(_t("shared.utils.document_manager.menu_expiry_report", default="2. Expiry Report"))
        print(_t("shared.utils.document_manager.menu_dept_analysis", default="3. Department Analysis"))
        print(_t("shared.utils.document_manager.menu_monthly_summary", default="4. Monthly Summary"))
        print(_t("shared.utils.document_manager.menu_student_progress", default="5. Student Progress Report"))
        print(_t("shared.utils.document_manager.menu_compliance_report", default="6. Compliance Report"))
        print(_t("shared.utils.document_manager.menu_custom_report", default="7. Custom Report Builder"))
        print(_t("shared.utils.document_manager.menu_return_main", default="8. Return to Main Menu"))

        choice = input(_t("shared.utils.document_manager.prompt_choose_report", default="\nChoose report type (1-8): ")).strip()

        if choice == '1':
            self.generate_status_report()
        elif choice == '2':
            self.generate_expiry_report()
        elif choice == '3':
            self.generate_department_analysis()
        elif choice == '4':
            self.generate_monthly_summary()
        elif choice == '5':
            self.generate_student_progress_report()
        elif choice == '6':
            self.generate_compliance_report()
        elif choice == '7':
            self.custom_report_builder()

    def add_document_type(self):
        """Add a new document type to the system"""
        try:
            print(_t("shared.utils.document_manager.add_doc_type_header", default="\n➕ ADD DOCUMENT TYPE"))

            type_name = input(_t("shared.utils.document_manager.prompt_doc_type_name", default="Document type name: ")).strip()
            if not type_name:
                print(_t("shared.utils.document_manager.type_name_required", default="Type name is required."))
                return

            description = input("Description: ").strip()

            is_required = input("Is this document required? (y/n): ").strip().lower() == 'y'

            has_expiry = input("Does this document expire? (y/n): ").strip().lower() == 'y'

            expiry_reminder_days = 0
            if has_expiry:
                try:
                    expiry_reminder_days = int(input("Reminder days before expiry (e.g., 30): ").strip())
                except ValueError:
                    expiry_reminder_days = 30

            try:
                max_file_size = int(input("Maximum file size in MB (default 10): ").strip() or "10")
            except ValueError:
                max_file_size = 10

            allowed_formats = input("Allowed file formats (comma-separated, e.g., pdf,jpg,png): ").strip()
            if not allowed_formats:
                allowed_formats = "pdf,jpg,jpeg,png"

            requires_approval = input("Requires approval? (y/n): ").strip().lower() == 'y'

            category = input("Category (e.g., Identity, Academic, Health): ").strip() or "General"

            try:
                sort_order = int(input("Sort order (default 0): ").strip() or "0")
            except ValueError:
                sort_order = 0

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO document_types (type_name, description, is_required, has_expiry,
                                       expiry_reminder_days, max_file_size_mb, allowed_formats,
                                       requires_approval, category, sort_order, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ''', (type_name, description, is_required, has_expiry, expiry_reminder_days,
                  max_file_size, allowed_formats, requires_approval, category, sort_order))

            conn.commit()
            conn.close()

            print(f"\n✅ Document type '{type_name}' added successfully!")

        except sqlite3.IntegrityError:
            print(f"Error: Document type '{type_name}' already exists.")
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def modify_document_type(self):
        """Modify an existing document type"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Show existing types
            cursor.execute('''
            SELECT type_id, type_name, is_required, has_expiry, category
            FROM document_types
            WHERE is_active = 1
            ORDER BY category, type_name
            ''')

            types = cursor.fetchall()

            if not types:
                print(_t("shared.utils.document_manager.no_document_types_found", default="No document types found."))
                conn.close()
                return

            print("\n📝 DOCUMENT TYPES:")
            for i, (type_id, name, required, has_expiry, category) in enumerate(types):
                print(f"{i+1}. {name} ({category}) - Required: {required}, Expires: {has_expiry}")

            try:
                choice = int(input("\nSelect type to modify: ")) - 1
                if 0 <= choice < len(types):
                    type_id = types[choice][0]
                else:
                    print(_t("shared.utils.document_manager.invalid_selection", default="Invalid selection."))
                    conn.close()
                    return
            except ValueError:
                print(_t("shared.utils.document_manager.invalid_input", default="Invalid input."))
                conn.close()
                return

            # Get current values
            cursor.execute('SELECT * FROM document_types WHERE type_id = ?', (type_id,))
            current = cursor.fetchone()

            print(f"\nModifying: {current[1]}")
            print("Press Enter to keep current value")

            new_name = input(f"Name [{current[1]}]: ").strip() or current[1]
            new_desc = input(f"Description [{current[2]}]: ").strip() or current[2]

            is_req_input = input(f"Required (y/n) [{current[3]}]: ").strip().lower()
            new_is_required = is_req_input == 'y' if is_req_input else current[3]

            has_exp_input = input(f"Has expiry (y/n) [{current[4]}]: ").strip().lower()
            new_has_expiry = has_exp_input == 'y' if has_exp_input else current[4]

            new_reminder_days = input(f"Reminder days [{current[5]}]: ").strip()
            new_reminder_days = int(new_reminder_days) if new_reminder_days else current[5]

            new_max_size = input(f"Max file size MB [{current[6]}]: ").strip()
            new_max_size = int(new_max_size) if new_max_size else current[6]

            new_formats = input(f"Allowed formats [{current[7]}]: ").strip() or current[7]

            new_category = input(f"Category [{current[9]}]: ").strip() or current[9]

            cursor.execute('''
            UPDATE document_types
            SET type_name = ?, description = ?, is_required = ?, has_expiry = ?,
                expiry_reminder_days = ?, max_file_size_mb = ?, allowed_formats = ?,
                category = ?
            WHERE type_id = ?
            ''', (new_name, new_desc, new_is_required, new_has_expiry, new_reminder_days,
                  new_max_size, new_formats, new_category, type_id))

            conn.commit()
            conn.close()

            print(_t("shared.utils.document_manager.doc_type_updated", default="\nDocument type updated successfully!"))

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def document_type_management(self):
        """Manage document types"""
        print("\n📋 DOCUMENT TYPE MANAGEMENT")
        print("1. View Document Types")
        print("2. Add Document Type")
        print("3. Modify Document Type")
        print("4. Deactivate Document Type")
        print("5. Return to Main Menu")

        choice = input("\nChoose option (1-5): ").strip()

        if choice == '1':
            self.view_document_types()
        elif choice == '2':
            self.add_document_type()
        elif choice == '3':
            self.modify_document_type()
        elif choice == '4':
            type_id = input("Enter document type ID to deactivate: ").strip()
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE document_types SET is_active = 0 WHERE type_id = ?', (type_id,))
                conn.commit()
                conn.close()
                print(_t("shared.utils.document_manager.doc_type_deactivated", default="Document type deactivated."))
            except sqlite3.Error as e:
                print(f"Database error: {e}")

    def view_document_details(self):
        """View detailed information about a specific document"""
        doc_id = input("Enter document ID: ").strip()

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT sd.document_id, sd.student_id, s.first_name, s.last_name,
                   dt.type_name, sd.original_filename, sd.file_path, sd.upload_date,
                   sd.expiry_date, sd.verification_status, sd.verification_date,
                   sd.verification_notes, sd.version_number, sd.uploaded_by,
                   sd.file_size, sd.file_hash, sd.tags, sd.workflow_status, sd.priority
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            LEFT JOIN students s ON sd.student_id = s.student_id
            WHERE sd.document_id = ?
            ''', (doc_id,))

            doc = cursor.fetchone()

            if not doc:
                print(_t("shared.utils.document_manager.document_not_found", default="Document not found."))
                conn.close()
                return

            print(f"\n{'='*80}")
            print("DOCUMENT DETAILS")
            print(f"{'='*80}")

            print(f"\nDocument ID: {doc[0]}")
            print(f"Student: {doc[2]} {doc[3]} (ID: {doc[1]})")
            print(f"Document Type: {doc[4]}")
            print(f"Original Filename: {doc[5]}")
            print(f"File Path: {doc[6]}")
            print(f"Upload Date: {doc[7]}")
            print(f"Uploaded By: {doc[13]}")
            print(f"File Size: {doc[14]} bytes")
            print(f"File Hash: {doc[15]}")
            print(f"Version: {doc[12]}")
            print(f"Verification Status: {doc[9]}")
            print(f"Workflow Status: {doc[17]}")
            print(f"Priority: {doc[18]}")

            if doc[8]:
                print(f"Expiry Date: {doc[8]}")

            if doc[10]:
                print(f"Verification Date: {doc[10]}")

            if doc[11]:
                print(f"Verification Notes: {doc[11]}")

            if doc[16]:
                print(f"Tags: {doc[16]}")

            # Show workflow steps
            cursor.execute('''
            SELECT step_name, step_order, assigned_to, status, comments,
                   completed_date, completed_by
            FROM document_workflow
            WHERE document_id = ?
            ORDER BY step_order
            ''', (doc_id,))

            workflow_steps = cursor.fetchall()

            if workflow_steps:
                print(f"\n{'='*80}")
                print("WORKFLOW STEPS:")
                for step in workflow_steps:
                    print(f"\nStep {step[1]}: {step[0]}")
                    print(f"  Assigned to: {step[2]}")
                    print(f"  Status: {step[3]}")
                    if step[4]:
                        print(f"  Comments: {step[4]}")
                    if step[5]:
                        print(f"  Completed: {step[5]} by {step[6]}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def generate_status_report(self):
        """Generate a comprehensive status report for all documents"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📊 DOCUMENT STATUS REPORT")
            print("=" * 80)

            # Overall statistics
            cursor.execute('''
            SELECT verification_status, COUNT(*) as count
            FROM student_documents
            WHERE is_current_version = 1
            GROUP BY verification_status
            ''')

            status_counts = cursor.fetchall()

            print("\nDocument Status Summary:")
            total_docs = 0
            for status, count in status_counts:
                print(f"  {status}: {count}")
                total_docs += count
            print(f"  Total: {total_docs}")

            # Workflow status
            cursor.execute('''
            SELECT workflow_status, COUNT(*) as count
            FROM student_documents
            WHERE is_current_version = 1
            GROUP BY workflow_status
            ''')

            workflow_counts = cursor.fetchall()

            print("\nWorkflow Status Summary:")
            for workflow, count in workflow_counts:
                print(f"  {workflow}: {count}")

            # By document type
            cursor.execute('''
            SELECT dt.type_name, COUNT(*) as count,
                   SUM(CASE WHEN sd.verification_status = 'Verified' THEN 1 ELSE 0 END) as verified
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.is_current_version = 1
            GROUP BY dt.type_name
            ORDER BY count DESC
            ''')

            type_counts = cursor.fetchall()

            print("\nDocuments by Type:")
            for type_name, count, verified in type_counts:
                print(f"  {type_name}: {count} total, {verified} verified")

            # Export option
            export = input("\nExport this report to CSV? (y/n): ").strip().lower()
            if export == 'y':
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"status_report_{timestamp}.csv"

                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Status', 'Count'])
                    writer.writerows(status_counts)
                    writer.writerow([])
                    writer.writerow(['Document Type', 'Total', 'Verified'])
                    writer.writerows(type_counts)

                print(f"✅ Report exported to {filename}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def generate_expiry_report(self):
        """Generate report of documents expiring soon"""
        try:
            days_ahead = input("Check documents expiring within how many days? (default 30): ").strip()
            days_ahead = int(days_ahead) if days_ahead else 30

            conn = get_connection()
            cursor = conn.cursor()

            future_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            current_date = datetime.now().strftime('%Y-%m-%d')

            cursor.execute('''
            SELECT sd.document_id, sd.student_id, s.first_name, s.last_name,
                   dt.type_name, sd.expiry_date, sd.verification_status
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            LEFT JOIN students s ON sd.student_id = s.student_id
            WHERE sd.expiry_date IS NOT NULL
              AND sd.expiry_date <= ?
              AND sd.expiry_date >= ?
              AND sd.is_current_version = 1
            ORDER BY sd.expiry_date ASC
            ''', (future_date, current_date))

            expiring_docs = cursor.fetchall()

            print(f"\n📅 EXPIRY REPORT - Documents expiring within {days_ahead} days")
            print("=" * 80)

            if not expiring_docs:
                print("No documents expiring within the specified period.")
                conn.close()
                return

            for doc in expiring_docs:
                doc_id, student_id, first_name, last_name, type_name, expiry_date, status = doc

                expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d')
                days_left = (expiry_dt - datetime.now()).days

                urgency = "🔴 URGENT" if days_left <= 7 else "🟡 WARNING" if days_left <= 30 else "🟢 OK"

                print(f"\n{urgency} Document ID: {doc_id}")
                print(f"  Student: {first_name} {last_name} ({student_id})")
                print(f"  Type: {type_name}")
                print(f"  Expires: {expiry_date} ({days_left} days)")
                print(f"  Status: {status}")

            print(f"\nTotal expiring documents: {len(expiring_docs)}")

            # Export option
            export = input("\nExport this report to CSV? (y/n): ").strip().lower()
            if export == 'y':
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"expiry_report_{timestamp}.csv"

                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Document ID', 'Student ID', 'Student Name', 'Document Type',
                                   'Expiry Date', 'Days Remaining', 'Status'])

                    for doc in expiring_docs:
                        expiry_dt = datetime.strptime(doc[5], '%Y-%m-%d')
                        days_left = (expiry_dt - datetime.now()).days
                        writer.writerow([doc[0], doc[1], f"{doc[2]} {doc[3]}",
                                       doc[4], doc[5], days_left, doc[6]])

                print(f"✅ Report exported to {filename}")

            conn.close()

        except ValueError:
            print(_t("shared.utils.document_manager.invalid_input", default="Invalid input."))
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def generate_department_analysis(self):
        """Generate analysis report by department/program"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n🏢 DEPARTMENT ANALYSIS REPORT")
            print("=" * 80)

            # Get programs from students
            cursor.execute('''
            SELECT DISTINCT s.program, COUNT(DISTINCT s.student_id) as student_count,
                   COUNT(sd.document_id) as doc_count,
                   SUM(CASE WHEN sd.verification_status = 'Verified' THEN 1 ELSE 0 END) as verified_count
            FROM students s
            LEFT JOIN student_documents sd ON s.student_id = sd.student_id
                AND sd.is_current_version = 1
            WHERE s.program IS NOT NULL
            GROUP BY s.program
            ORDER BY s.program
            ''')

            programs = cursor.fetchall()

            if not programs:
                print(_t("shared.utils.document_manager.no_program_data", default="No program data available."))
                conn.close()
                return

            print("\nDocuments by Program:")
            print(f"{'Program':<30} {'Students':<10} {'Documents':<12} {'Verified':<10}")
            print("-" * 80)

            for program, students, docs, verified in programs:
                completion_rate = (verified / docs * 100) if docs > 0 else 0
                print(f"{program:<30} {students:<10} {docs:<12} {verified:<10} ({completion_rate:.1f}%)")

            # Detailed breakdown by document type for each program
            show_details = input("\nShow detailed breakdown by document type? (y/n): ").strip().lower()

            if show_details == 'y':
                for program, _, _, _ in programs:
                    print(f"\n{program}:")

                    cursor.execute('''
                    SELECT dt.type_name, COUNT(*) as count,
                           SUM(CASE WHEN sd.verification_status = 'Verified' THEN 1 ELSE 0 END) as verified
                    FROM student_documents sd
                    JOIN document_types dt ON sd.type_id = dt.type_id
                    JOIN students s ON sd.student_id = s.student_id
                    WHERE s.program = ? AND sd.is_current_version = 1
                    GROUP BY dt.type_name
                    ''', (program,))

                    type_breakdown = cursor.fetchall()

                    for type_name, count, verified in type_breakdown:
                        print(f"  {type_name}: {count} total, {verified} verified")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def generate_monthly_summary(self):
        """Generate monthly activity summary"""
        try:
            month_input = input("Enter month (YYYY-MM) or press Enter for current month: ").strip()

            if not month_input:
                target_month = datetime.now().strftime('%Y-%m')
            else:
                target_month = month_input

            conn = get_connection()
            cursor = conn.cursor()

            print(f"\n📆 MONTHLY SUMMARY - {target_month}")
            print("=" * 80)

            # Documents uploaded this month
            cursor.execute('''
            SELECT COUNT(*)
            FROM student_documents
            WHERE strftime('%Y-%m', upload_date) = ?
            ''', (target_month,))

            uploaded_count = cursor.fetchone()[0]
            print(f"\nDocuments Uploaded: {uploaded_count}")

            # Documents verified this month
            cursor.execute('''
            SELECT COUNT(*)
            FROM student_documents
            WHERE strftime('%Y-%m', verification_date) = ?
            ''', (target_month,))

            verified_count = cursor.fetchone()[0]
            print(f"Documents Verified: {verified_count}")

            # Most active users
            cursor.execute('''
            SELECT uploaded_by, COUNT(*) as count
            FROM student_documents
            WHERE strftime('%Y-%m', upload_date) = ?
            GROUP BY uploaded_by
            ORDER BY count DESC
            LIMIT 5
            ''', (target_month,))

            active_users = cursor.fetchall()

            if active_users:
                print("\nMost Active Users:")
                for user, count in active_users:
                    print(f"  {user}: {count} uploads")

            # Document types uploaded
            cursor.execute('''
            SELECT dt.type_name, COUNT(*) as count
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE strftime('%Y-%m', sd.upload_date) = ?
            GROUP BY dt.type_name
            ORDER BY count DESC
            ''', (target_month,))

            type_breakdown = cursor.fetchall()

            if type_breakdown:
                print("\nDocument Types Uploaded:")
                for type_name, count in type_breakdown:
                    print(f"  {type_name}: {count}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def generate_student_progress_report(self):
        """Generate comprehensive progress report for a student"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            student_id = self.select_student(cursor)
            if not student_id:
                conn.close()
                return

            # Get student info
            cursor.execute('''
            SELECT first_name, last_name, program, enrollment_year
            FROM students WHERE student_id = ?
            ''', (student_id,))

            student_info = cursor.fetchone()

            if not student_info:
                print(_t("shared.utils.document_manager.student_not_found", default="Student not found."))
                conn.close()
                return

            first_name, last_name, program, enrollment_year = student_info

            print(f"\n📊 STUDENT PROGRESS REPORT")
            print("=" * 80)
            print(f"Student: {first_name} {last_name} ({student_id})")
            print(f"Program: {program}")
            print(f"Enrollment Year: {enrollment_year}")
            print("=" * 80)

            # Get all documents
            cursor.execute('''
            SELECT dt.type_name, dt.is_required, sd.verification_status,
                   sd.upload_date, sd.expiry_date
            FROM document_types dt
            LEFT JOIN student_documents sd ON dt.type_id = sd.type_id
                AND sd.student_id = ? AND sd.is_current_version = 1
            WHERE dt.is_active = 1
            ORDER BY dt.category, dt.sort_order
            ''', (student_id,))

            documents = cursor.fetchall()

            required_count = 0
            required_submitted = 0
            total_verified = 0

            print("\nDocument Completion Status:")
            print(f"{'Document Type':<30} {'Required':<10} {'Status':<15} {'Upload Date':<15}")
            print("-" * 80)

            for doc in documents:
                type_name, is_required, status, upload_date, expiry_date = doc

                if is_required:
                    required_count += 1
                    if status:
                        required_submitted += 1

                if status == 'Verified':
                    total_verified += 1

                req_text = "Yes" if is_required else "No"
                status_text = status if status else "Not Submitted"
                upload_text = upload_date[:10] if upload_date else "-"

                print(f"{type_name:<30} {req_text:<10} {status_text:<15} {upload_text:<15}")

            # Summary
            print("\n" + "=" * 80)
            print(f"Required Documents: {required_submitted}/{required_count}")
            print(f"Total Verified: {total_verified}")

            completion_pct = (required_submitted / required_count * 100) if required_count > 0 else 0
            print(f"Completion Rate: {completion_pct:.1f}%")

            # Check for missing required documents
            cursor.execute('''
            SELECT dt.type_name
            FROM document_types dt
            LEFT JOIN student_documents sd ON dt.type_id = sd.type_id
                AND sd.student_id = ? AND sd.is_current_version = 1
            WHERE dt.is_required = 1 AND dt.is_active = 1 AND sd.document_id IS NULL
            ''', (student_id,))

            missing_docs = cursor.fetchall()

            if missing_docs:
                print("\n⚠️  Missing Required Documents:")
                for doc in missing_docs:
                    print(f"  - {doc[0]}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def bulk_document_download(self):
        """Download multiple documents at once"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📥 BULK DOCUMENT DOWNLOAD")
            print("1. Download all documents for a student")
            print("2. Download documents by type")
            print("3. Download documents by status")
            print("4. Download from search results")

            choice = input("\nChoose option (1-4): ").strip()

            documents = []

            if choice == '1':
                student_id = self.select_student(cursor)
                if student_id:
                    cursor.execute('''
                    SELECT document_id, file_path, original_filename
                    FROM student_documents
                    WHERE student_id = ? AND is_current_version = 1
                    ''', (student_id,))
                    documents = cursor.fetchall()

            elif choice == '2':
                type_info = self.select_document_type(cursor)
                if type_info:
                    cursor.execute('''
                    SELECT document_id, file_path, original_filename
                    FROM student_documents
                    WHERE type_id = ? AND is_current_version = 1
                    ''', (type_info[0],))
                    documents = cursor.fetchall()

            elif choice == '3':
                status = input("Enter status (Pending/Verified/Rejected): ").strip()
                cursor.execute('''
                SELECT document_id, file_path, original_filename
                FROM student_documents
                WHERE verification_status = ? AND is_current_version = 1
                ''', (status,))
                documents = cursor.fetchall()

            if not documents:
                print(_t("shared.utils.document_manager.no_docs_for_download", default="No documents found for download."))
                conn.close()
                return

            print(f"\nFound {len(documents)} documents.")

            # Create download directory
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            download_dir = f"bulk_download_{timestamp}"

            os.makedirs(download_dir, exist_ok=True)

            print(f"Downloading to: {download_dir}/")

            success_count = 0
            for doc_id, file_path, original_filename in documents:
                try:
                    if os.path.exists(file_path):
                        dest_path = os.path.join(download_dir, f"{doc_id}_{original_filename}")
                        shutil.copy2(file_path, dest_path)
                        success_count += 1
                        print(f"  ✓ {original_filename}")
                    else:
                        print(f"  ✗ {original_filename} (file not found)")
                except Exception as e:
                    print(f"  ✗ {original_filename} (error: {e})")

            print(f"\n✅ Downloaded {success_count}/{len(documents)} documents to {download_dir}/")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def bulk_expiry_update(self):
        """Update expiry dates for multiple documents"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📅 BULK EXPIRY UPDATE")

            type_info = self.select_document_type(cursor)
            if not type_info:
                conn.close()
                return

            type_id = type_info[0]

            cursor.execute('''
            SELECT document_id, student_id, original_filename, expiry_date
            FROM student_documents
            WHERE type_id = ? AND is_current_version = 1
            ''', (type_id,))

            documents = cursor.fetchall()

            if not documents:
                print(_t("shared.utils.document_manager.no_docs_for_type", default="No documents found for this type."))
                conn.close()
                return

            print(f"\nFound {len(documents)} documents of this type.")

            new_expiry = self.get_expiry_date()

            confirm = input(f"\nUpdate expiry date to {new_expiry} for all {len(documents)} documents? (y/n): ").strip().lower()

            if confirm == 'y':
                cursor.execute('''
                UPDATE student_documents
                SET expiry_date = ?
                WHERE type_id = ? AND is_current_version = 1
                ''', (new_expiry, type_id))

                conn.commit()
                print(f"✅ Updated expiry date for {len(documents)} documents.")
            else:
                print(_t("shared.utils.document_manager.operation_cancelled", default="Operation cancelled."))

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def bulk_tag_assignment(self):
        """Assign tags to multiple documents"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n🏷️  BULK TAG ASSIGNMENT")

            # Get documents to tag
            print("Select documents to tag:")
            print("1. By student")
            print("2. By document type")
            print("3. By status")

            choice = input("\nChoose option (1-3): ").strip()

            if choice == '1':
                student_id = self.select_student(cursor)
                if not student_id:
                    conn.close()
                    return

                cursor.execute('''
                SELECT document_id, original_filename
                FROM student_documents
                WHERE student_id = ? AND is_current_version = 1
                ''', (student_id,))

            elif choice == '2':
                type_info = self.select_document_type(cursor)
                if not type_info:
                    conn.close()
                    return

                cursor.execute('''
                SELECT document_id, original_filename
                FROM student_documents
                WHERE type_id = ? AND is_current_version = 1
                ''', (type_info[0],))

            elif choice == '3':
                status = input("Enter status: ").strip()
                cursor.execute('''
                SELECT document_id, original_filename
                FROM student_documents
                WHERE verification_status = ? AND is_current_version = 1
                ''', (status,))

            else:
                print(_t("shared.utils.document_manager.invalid_choice", default="Invalid choice. Please try again."))
                conn.close()
                return

            documents = cursor.fetchall()

            if not documents:
                print(_t("shared.utils.document_manager.no_documents_found", default="No documents found."))
                conn.close()
                return

            print(f"\nFound {len(documents)} documents.")

            # Select tags
            tags = self.select_tags(cursor)
            if not tags:
                conn.close()
                return

            confirm = input(f"\nAssign tags '{tags}' to {len(documents)} documents? (y/n): ").strip().lower()

            if confirm == 'y':
                for doc_id, _ in documents:
                    cursor.execute('''
                    UPDATE student_documents
                    SET tags = ?
                    WHERE document_id = ?
                    ''', (tags, doc_id))

                conn.commit()
                print(f"✅ Tags assigned to {len(documents)} documents.")
            else:
                print(_t("shared.utils.document_manager.operation_cancelled", default="Operation cancelled."))

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def bulk_update_from_search(self):
        """Perform bulk updates on search results"""
        print("\n🔍 BULK UPDATE FROM SEARCH")
        print("First, perform a search to find documents...")

        # Reuse advanced search
        results = self.execute_advanced_search({})

        if not results:
            print(_t("shared.utils.document_manager.no_documents_found", default="No documents found."))
            return

        print(f"\nFound {len(results)} documents.")
        print("\nBulk Operations:")
        print("1. Update Status")
        print("2. Assign Tags")
        print("3. Update Expiry Date")
        print("4. Change Priority")

        choice = input("\nChoose operation (1-4): ").strip()

        try:
            conn = get_connection()
            cursor = conn.cursor()

            doc_ids = [r[0] for r in results]

            if choice == '1':
                new_status = input("New status (Pending/Verified/Rejected): ").strip()
                cursor.execute(f'''
                UPDATE student_documents
                SET verification_status = ?
                WHERE document_id IN ({','.join('?' * len(doc_ids))})
                ''', [new_status] + doc_ids)

            elif choice == '2':
                tags = self.select_tags(cursor)
                cursor.execute(f'''
                UPDATE student_documents
                SET tags = ?
                WHERE document_id IN ({','.join('?' * len(doc_ids))})
                ''', [tags] + doc_ids)

            elif choice == '3':
                new_expiry = self.get_expiry_date()
                cursor.execute(f'''
                UPDATE student_documents
                SET expiry_date = ?
                WHERE document_id IN ({','.join('?' * len(doc_ids))})
                ''', [new_expiry] + doc_ids)

            elif choice == '4':
                priority = input("New priority (0-5): ").strip()
                cursor.execute(f'''
                UPDATE student_documents
                SET priority = ?
                WHERE document_id IN ({','.join('?' * len(doc_ids))})
                ''', [priority] + doc_ids)

            conn.commit()
            conn.close()

            print(f"✅ Updated {len(results)} documents.")

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def export_all_documents(self):
        """Export all document records to CSV"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT sd.document_id, sd.student_id, s.first_name, s.last_name,
                   dt.type_name, sd.original_filename, sd.upload_date,
                   sd.expiry_date, sd.verification_status, sd.version_number,
                   sd.tags, sd.workflow_status
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            LEFT JOIN students s ON sd.student_id = s.student_id
            WHERE sd.is_current_version = 1
            ORDER BY sd.upload_date DESC
            ''')

            documents = cursor.fetchall()

            if not documents:
                print(_t("shared.utils.document_manager.no_documents_to_export", default="No documents to export."))
                conn.close()
                return

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"all_documents_{timestamp}.csv"

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Document ID', 'Student ID', 'First Name', 'Last Name',
                               'Document Type', 'Filename', 'Upload Date', 'Expiry Date',
                               'Status', 'Version', 'Tags', 'Workflow Status'])
                writer.writerows(documents)

            print(f"✅ Exported {len(documents)} documents to {filename}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def export_search_results(self):
        """Export search results to CSV"""
        print("\n📤 EXPORT SEARCH RESULTS")
        print("First, perform a search...")

        results = self.execute_advanced_search({})

        if not results:
            print(_t("shared.utils.document_manager.no_results_to_export", default="No results to export."))
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"search_results_{timestamp}.csv"

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Document ID', 'Student ID', 'Student Name', 'Document Type',
                           'Filename', 'Upload Date', 'Status'])
            writer.writerows(results)

        print(f"✅ Exported {len(results)} results to {filename}")

    def export_activity_log(self):
        """Export activity log/audit trail to CSV"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            days = input("Export log for how many days? (default 30): ").strip()
            days = int(days) if days else 30

            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            cursor.execute('''
            SELECT log_id, user_id, action, table_name, record_id,
                   old_values, new_values, timestamp
            FROM audit_log
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            ''', (cutoff_date,))

            logs = cursor.fetchall()

            if not logs:
                print(_t("shared.utils.document_manager.no_activity_logs_found", default="No activity logs found."))
                conn.close()
                return

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"activity_log_{timestamp}.csv"

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Log ID', 'User', 'Action', 'Table', 'Record ID',
                               'Old Values', 'New Values', 'Timestamp'])
                writer.writerows(logs)

            print(f"✅ Exported {len(logs)} log entries to {filename}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def export_compliance_data(self):
        """Export compliance data for auditing"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📋 EXPORT COMPLIANCE DATA")

            cursor.execute('''
            SELECT s.student_id, s.first_name, s.last_name, s.program,
                   dt.type_name, dt.is_required,
                   CASE WHEN sd.document_id IS NOT NULL THEN 'Submitted' ELSE 'Missing' END as status,
                   sd.verification_status, sd.upload_date, sd.expiry_date
            FROM students s
            CROSS JOIN document_types dt
            LEFT JOIN student_documents sd ON s.student_id = sd.student_id
                AND dt.type_id = sd.type_id AND sd.is_current_version = 1
            WHERE dt.is_active = 1
            ORDER BY s.student_id, dt.category, dt.sort_order
            ''')

            compliance_data = cursor.fetchall()

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"compliance_data_{timestamp}.csv"

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Student ID', 'First Name', 'Last Name', 'Program',
                               'Document Type', 'Required', 'Status', 'Verification Status',
                               'Upload Date', 'Expiry Date'])
                writer.writerows(compliance_data)

            print(f"✅ Exported compliance data to {filename}")
            print(f"Total records: {len(compliance_data)}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def export_custom_dataset(self):
        """Export custom dataset with selected fields"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📊 EXPORT CUSTOM DATASET")
            print("Select fields to export:")
            print("1. Student Information")
            print("2. Document Details")
            print("3. Verification Status")
            print("4. Workflow Information")
            print("5. Dates and Expiry")
            print("6. All Fields")

            choice = input("\nChoose option (1-6): ").strip()

            if choice == '6':
                query = '''
                SELECT sd.document_id, sd.student_id, s.first_name, s.last_name,
                       s.program, dt.type_name, sd.original_filename, sd.upload_date,
                       sd.expiry_date, sd.verification_status, sd.verification_date,
                       sd.verification_notes, sd.version_number, sd.uploaded_by,
                       sd.tags, sd.workflow_status, sd.priority
                FROM student_documents sd
                JOIN document_types dt ON sd.type_id = dt.type_id
                LEFT JOIN students s ON sd.student_id = s.student_id
                WHERE sd.is_current_version = 1
                '''
                headers = ['Document ID', 'Student ID', 'First Name', 'Last Name', 'Program',
                          'Document Type', 'Filename', 'Upload Date', 'Expiry Date',
                          'Verification Status', 'Verification Date', 'Verification Notes',
                          'Version', 'Uploaded By', 'Tags', 'Workflow Status', 'Priority']
            else:
                print("Custom field selection not fully implemented. Using default export.")
                query = '''
                SELECT sd.document_id, sd.student_id, dt.type_name, sd.original_filename,
                       sd.upload_date, sd.verification_status
                FROM student_documents sd
                JOIN document_types dt ON sd.type_id = dt.type_id
                WHERE sd.is_current_version = 1
                '''
                headers = ['Document ID', 'Student ID', 'Document Type', 'Filename',
                          'Upload Date', 'Status']

            cursor.execute(query)
            data = cursor.fetchall()

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"custom_export_{timestamp}.csv"

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(data)

            print(f"✅ Exported {len(data)} records to {filename}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def import_from_excel(self):
        """Import documents from Excel spreadsheet"""
        try:
            print("\n📥 IMPORT FROM EXCEL")

            file_path = input("Enter Excel file path: ").strip()

            if not os.path.exists(file_path):
                print(_t("shared.utils.document_manager.file_not_found", default="File not found."))
                return

            print("\nNote: This feature requires openpyxl library.")
            print("For now, please convert your Excel file to CSV and use the CSV import option.")

            # Placeholder for future Excel import implementation
            # Would need: import openpyxl

        except Exception as e:
            print(f"Import error: {e}")

    def download_import_template(self):
        """Download a template file for bulk import"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"import_template_{timestamp}.csv"

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['student_id', 'document_type', 'file_path', 'expiry_date',
                               'tags', 'priority', 'notes'])
                writer.writerow(['STU001', 'Birth Certificate', '/path/to/file.pdf',
                               '2025-12-31', 'verified,urgent', '5', 'Sample entry'])

            print(f"✅ Template downloaded: {filename}")
            print("\nTemplate Instructions:")
            print("- student_id: Student ID from your system")
            print("- document_type: Exact name of document type")
            print("- file_path: Full path to the document file")
            print("- expiry_date: Format YYYY-MM-DD (optional)")
            print("- tags: Comma-separated tags (optional)")
            print("- priority: Number 0-5 (optional)")
            print("- notes: Any additional notes (optional)")

        except Exception as e:
            print(f"Error creating template: {e}")

    def email_settings(self):
        """Configure email settings - delegates to email manager"""
        print("\n📧 EMAIL SETTINGS")

        if not EMAIL_SYSTEM_AVAILABLE:
            print("❌ Email system is not available.")
            print("Please ensure the email infrastructure is properly installed.")
            return

        print("\nEmail settings are managed by the centralized email system.")
        print("To configure email settings:")
        print("1. Navigate to: university_system/infrastructure/email/")
        print("2. Run the email manager configuration")
        print("3. Or use the main system settings menu")

        view_current = input("\nView current email configuration? (y/n): ").strip().lower()

        if view_current == 'y':
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT setting_name, setting_value, description
                FROM system_settings
                WHERE setting_name LIKE '%email%' OR setting_name LIKE '%smtp%'
                   OR setting_name LIKE '%notification%'
                ORDER BY setting_name
                ''')

                settings = cursor.fetchall()

                if settings:
                    print("\nCurrent Email-Related Settings:")
                    for name, value, desc in settings:
                        # Mask password if present
                        display_value = '***' if 'password' in name.lower() else value
                        print(f"  {name}: {display_value}")
                        if desc:
                            print(f"    ({desc})")
                else:
                    print("\nNo email settings found in system_settings table.")

                conn.close()

            except sqlite3.Error as e:
                print(f"Database error: {e}")

    def email_configuration(self):
        """Alias for email_settings"""
        self.email_settings()

    def notification_templates(self):
        """Manage notification email templates"""
        print("\n📧 NOTIFICATION TEMPLATES")

        if not EMAIL_SYSTEM_AVAILABLE:
            print("Email system not available.")
            return

        print("\nAvailable Templates:")
        print("1. Document Upload Confirmation")
        print("2. Document Verification Notification")
        print("3. Document Expiry Warning")
        print("4. Document Rejection Notice")
        print("5. Workflow Step Completion")
        print("6. Custom Template")

        print("\nNote: Templates are managed by the email system.")
        print("Template files location: university_system/infrastructure/email/templates/")

        edit = input("\nWould you like to view template variables? (y/n): ").strip().lower()

        if edit == 'y':
            print("\nCommon Template Variables:")
            print("  {student_name} - Student's full name")
            print("  {student_id} - Student ID")
            print("  {document_type} - Type of document")
            print("  {document_id} - Document ID")
            print("  {upload_date} - Upload date")
            print("  {expiry_date} - Expiry date")
            print("  {status} - Document status")
            print("  {verification_notes} - Verification notes")

    def send_custom_notification(self):
        """Send a custom notification to selected users"""
        try:
            print("\n📧 SEND CUSTOM NOTIFICATION")

            print("\nRecipient Selection:")
            print("1. Specific Student")
            print("2. All Students")
            print("3. Students by Program")
            print("4. Students with Expiring Documents")

            choice = input("\nChoose option (1-4): ").strip()

            recipients = []
            conn = get_connection()
            cursor = conn.cursor()

            if choice == '1':
                student_id = self.select_student(cursor)
                if student_id:
                    recipients = [student_id]

            elif choice == '2':
                cursor.execute('SELECT student_id FROM students')
                recipients = [row[0] for row in cursor.fetchall()]

            elif choice == '3':
                program = input("Enter program name: ").strip()
                cursor.execute('SELECT student_id FROM students WHERE program = ?', (program,))
                recipients = [row[0] for row in cursor.fetchall()]

            elif choice == '4':
                days = input("Documents expiring within how many days? ").strip()
                days = int(days) if days else 30
                future_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

                cursor.execute('''
                SELECT DISTINCT student_id
                FROM student_documents
                WHERE expiry_date <= ? AND expiry_date >= date('now')
                ''', (future_date,))
                recipients = [row[0] for row in cursor.fetchall()]

            if not recipients:
                print("No recipients found.")
                conn.close()
                return

            print(f"\nFound {len(recipients)} recipients.")

            title = input("Notification title: ").strip()
            message = input("Notification message: ").strip()
            priority = input("Priority (normal/high/urgent): ").strip() or 'normal'

            confirm = input(f"\nSend notification to {len(recipients)} recipients? (y/n): ").strip().lower()

            if confirm == 'y':
                for recipient_id in recipients:
                    self.create_notification(cursor, recipient_id, 'custom', title, message)

                conn.commit()
                print(f"✅ Notifications queued for {len(recipients)} recipients.")
            else:
                print(_t("shared.utils.document_manager.operation_cancelled", default="Operation cancelled."))

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def bulk_notification_send(self):
        """Send bulk notifications"""
        # Alias to send_custom_notification
        self.send_custom_notification()

    def bulk_notification_campaign(self):
        """Create and manage notification campaigns"""
        try:
            print("\n📢 NOTIFICATION CAMPAIGN")

            campaign_name = input("Campaign name: ").strip()

            print("\nCampaign Type:")
            print("1. Document Reminder Campaign")
            print("2. Expiry Warning Campaign")
            print("3. Compliance Check Campaign")
            print("4. General Announcement")

            choice = input("\nChoose campaign type (1-4): ").strip()

            conn = get_connection()
            cursor = conn.cursor()

            if choice == '1':
                # Find students with missing required documents
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name
                FROM students s
                CROSS JOIN document_types dt
                LEFT JOIN student_documents sd ON s.student_id = sd.student_id
                    AND dt.type_id = sd.type_id AND sd.is_current_version = 1
                WHERE dt.is_required = 1 AND dt.is_active = 1 AND sd.document_id IS NULL
                ''')

                students = cursor.fetchall()

                for student_id, first_name, last_name in students:
                    title = f"Document Reminder: {campaign_name}"
                    message = f"Dear {first_name}, you have required documents that need to be submitted."
                    self.create_notification(cursor, student_id, 'campaign', title, message)

                conn.commit()
                print(f"✅ Campaign sent to {len(students)} students.")

            elif choice == '2':
                days = int(input("Warn about documents expiring within how many days? ").strip() or "30")
                future_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

                cursor.execute('''
                SELECT DISTINCT sd.student_id, s.first_name, dt.type_name, sd.expiry_date
                FROM student_documents sd
                JOIN document_types dt ON sd.type_id = dt.type_id
                JOIN students s ON sd.student_id = s.student_id
                WHERE sd.expiry_date <= ? AND sd.expiry_date >= date('now')
                  AND sd.is_current_version = 1
                ''', (future_date,))

                expiring = cursor.fetchall()

                for student_id, first_name, doc_type, expiry_date in expiring:
                    title = f"Document Expiry Warning: {doc_type}"
                    message = f"Dear {first_name}, your {doc_type} expires on {expiry_date}. Please renew."
                    self.create_notification(cursor, student_id, 'expiry_warning', title, message)

                conn.commit()
                print(f"✅ Expiry warnings sent to {len(expiring)} students.")

            elif choice == '4':
                # General announcement to all
                cursor.execute('SELECT student_id FROM students')
                all_students = cursor.fetchall()

                title = input("Announcement title: ").strip()
                message = input("Announcement message: ").strip()

                for student_id, in all_students:
                    self.create_notification(cursor, student_id, 'announcement', title, message)

                conn.commit()
                print(f"✅ Announcement sent to {len(all_students)} students.")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def view_pending_notifications(self):
        """View notifications that are pending delivery"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT notification_id, recipient_id, notification_type, title,
                   message, created_date, priority
            FROM notifications
            WHERE is_sent = 0
            ORDER BY priority DESC, created_date ASC
            ''')

            pending = cursor.fetchall()

            print("\n📬 PENDING NOTIFICATIONS")
            print("=" * 80)

            if not pending:
                print("No pending notifications.")
                conn.close()
                return

            for notif in pending:
                notif_id, recipient, notif_type, title, message, created, priority = notif

                print(f"\nNotification ID: {notif_id}")
                print(f"To: {recipient}")
                print(f"Type: {notif_type}")
                print(f"Priority: {priority}")
                print(f"Title: {title}")
                print(f"Message: {message[:100]}...")
                print(f"Created: {created}")
                print("-" * 80)

            print(f"\nTotal Pending: {len(pending)}")

            # Option to mark as sent or delete
            action = input("\nActions: (m)ark as sent, (d)elete, (q)uit: ").strip().lower()

            if action == 'm':
                cursor.execute('UPDATE notifications SET is_sent = 1 WHERE is_sent = 0')
                conn.commit()
                print("✅ All pending notifications marked as sent.")
            elif action == 'd':
                confirm = input("Delete all pending notifications? (y/n): ").strip().lower()
                if confirm == 'y':
                    cursor.execute('DELETE FROM notifications WHERE is_sent = 0')
                    conn.commit()
                    print("✅ Pending notifications deleted.")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def backup_settings(self):
        """Configure backup settings"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n💾 BACKUP SETTINGS")

            # Get current settings
            cursor.execute('''
            SELECT setting_name, setting_value
            FROM system_settings
            WHERE setting_name LIKE '%backup%'
            ''')

            current_settings = dict(cursor.fetchall())

            print("\nCurrent Backup Settings:")
            for key, value in current_settings.items():
                print(f"  {key}: {value}")

            print("\nModify Settings:")

            auto_backup = input(f"Enable automatic backups? (y/n) [{current_settings.get('auto_backup_enabled', 'false')}]: ").strip().lower()
            if auto_backup:
                new_value = 'true' if auto_backup == 'y' else 'false'
                cursor.execute('''
                UPDATE system_settings SET setting_value = ?, updated_date = ?
                WHERE setting_name = 'auto_backup_enabled'
                ''', (new_value, datetime.now().strftime('%Y-%m-%d')))

            frequency = input(f"Backup frequency (days) [{current_settings.get('backup_frequency_days', '7')}]: ").strip()
            if frequency:
                cursor.execute('''
                UPDATE system_settings SET setting_value = ?, updated_date = ?
                WHERE setting_name = 'backup_frequency_days'
                ''', (frequency, datetime.now().strftime('%Y-%m-%d')))

            retention = input("Backup retention period (days, default 30): ").strip()
            if retention:
                cursor.execute('''
                INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
                VALUES ('backup_retention_days', ?, 'Days to keep old backups', ?)
                ''', (retention, datetime.now().strftime('%Y-%m-%d')))

            conn.commit()
            conn.close()

            print("\n✅ Backup settings updated.")

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def schedule_automatic_backup(self):
        """Schedule automatic backups"""
        print("\n⏰ SCHEDULE AUTOMATIC BACKUP")

        print("\nAutomatic backup scheduling requires:")
        print("1. System cron job (Linux/Mac)")
        print("2. Task Scheduler (Windows)")
        print("3. Or a background service")

        print("\nTo enable automatic backups:")
        print("1. Set auto_backup_enabled to 'true' in backup settings")
        print("2. Configure your system's task scheduler")
        print("3. Run this script with '--backup' flag")

        enable = input("\nEnable automatic backup flag in settings? (y/n): ").strip().lower()

        if enable == 'y':
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                UPDATE system_settings
                SET setting_value = 'true', updated_date = ?
                WHERE setting_name = 'auto_backup_enabled'
                ''', (datetime.now().strftime('%Y-%m-%d'),))

                conn.commit()
                conn.close()

                print("✅ Automatic backup enabled in settings.")
                print("\nNext steps:")
                print("- Configure your system scheduler to run regular backups")
                print(f"- Command: python {__file__} --backup")

            except sqlite3.Error as e:
                print(f"Database error: {e}")

    def restore_from_backup(self):
        """Restore system from a backup file"""
        try:
            backup_dir = 'backups'

            if not os.path.exists(backup_dir):
                print("No backup directory found.")
                return

            # List available backups
            backups = [f for f in os.listdir(backup_dir) if f.endswith('.zip')]

            if not backups:
                print("No backup files found.")
                return

            print("\n🔄 RESTORE FROM BACKUP")
            print("\nAvailable Backups:")

            backups.sort(reverse=True)

            for i, backup in enumerate(backups):
                backup_path = os.path.join(backup_dir, backup)
                size = os.path.getsize(backup_path) / (1024 * 1024)
                mtime = datetime.fromtimestamp(os.path.getmtime(backup_path))
                print(f"{i+1}. {backup} ({size:.2f} MB) - {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

            try:
                choice = int(input("\nSelect backup to restore: ")) - 1
                if 0 <= choice < len(backups):
                    selected_backup = os.path.join(backup_dir, backups[choice])
                else:
                    print(_t("shared.utils.document_manager.invalid_selection", default="Invalid selection."))
                    return
            except ValueError:
                print(_t("shared.utils.document_manager.invalid_input", default="Invalid input."))
                return

            print(f"\n⚠️  WARNING: This will replace your current database!")
            confirm = input("Are you sure you want to restore? Type 'YES' to confirm: ").strip()

            if confirm != 'YES':
                print("Restore cancelled.")
                return

            print(f"\nRestoring from {backups[choice]}...")

            with zipfile.ZipFile(selected_backup, 'r') as backup_zip:
                backup_zip.extractall('.')

            print("✅ System restored successfully!")
            print("⚠️  Please restart the application.")

        except Exception as e:
            print(f"Restore error: {e}")

    def view_backup_history(self):
        """View history of backups"""
        try:
            backup_dir = 'backups'

            if not os.path.exists(backup_dir):
                print("No backup directory found.")
                return

            backups = [f for f in os.listdir(backup_dir) if f.endswith('.zip')]

            if not backups:
                print("No backup files found.")
                return

            print("\n💾 BACKUP HISTORY")
            print("=" * 80)

            backups.sort(reverse=True)

            total_size = 0

            for backup in backups:
                backup_path = os.path.join(backup_dir, backup)
                size = os.path.getsize(backup_path) / (1024 * 1024)
                total_size += size
                mtime = datetime.fromtimestamp(os.path.getmtime(backup_path))

                print(f"\nFile: {backup}")
                print(f"Size: {size:.2f} MB")
                print(f"Created: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

            print(f"\n{'='*80}")
            print(f"Total Backups: {len(backups)}")
            print(f"Total Size: {total_size:.2f} MB")

            # Check audit log for backup records
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT record_id, new_values, timestamp
            FROM audit_log
            WHERE action = 'BACKUP_CREATED'
            ORDER BY timestamp DESC
            LIMIT 10
            ''')

            log_entries = cursor.fetchall()

            if log_entries:
                print("\n📋 Recent Backup Log Entries:")
                for filename, details, timestamp in log_entries:
                    print(f"  {timestamp}: {filename}")

            conn.close()

        except Exception as e:
            print(f"Error viewing backup history: {e}")

    def security_settings(self):
        """Configure security settings"""
        print("\n🔒 SECURITY SETTINGS")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\nSecurity Configuration:")
            print("1. Password Policy")
            print("2. Session Timeout")
            print("3. Access Control")
            print("4. Audit Logging")
            print("5. File Upload Restrictions")
            print("6. View Access Logs")
            print("7. Return to Main Menu")

            choice = input("\nChoose option (1-7): ").strip()

            if choice == '1':
                print("\nPassword Policy Settings:")
                min_length = input("Minimum password length (default 8): ").strip() or "8"
                require_special = input("Require special characters? (y/n): ").strip().lower() == 'y'

                cursor.execute('''
                INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
                VALUES ('password_min_length', ?, 'Minimum password length', ?)
                ''', (min_length, datetime.now().strftime('%Y-%m-%d')))

                cursor.execute('''
                INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
                VALUES ('password_require_special', ?, 'Require special characters', ?)
                ''', ('true' if require_special else 'false', datetime.now().strftime('%Y-%m-%d')))

                conn.commit()
                print("✅ Password policy updated.")

            elif choice == '2':
                timeout = input("Session timeout (minutes, default 30): ").strip() or "30"
                cursor.execute('''
                INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
                VALUES ('session_timeout_minutes', ?, 'Session timeout in minutes', ?)
                ''', (timeout, datetime.now().strftime('%Y-%m-%d')))
                conn.commit()
                print("✅ Session timeout updated.")

            elif choice == '4':
                audit_enabled = input("Enable audit logging? (y/n): ").strip().lower() == 'y'
                cursor.execute('''
                INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
                VALUES ('audit_logging_enabled', ?, 'Enable audit trail logging', ?)
                ''', ('true' if audit_enabled else 'false', datetime.now().strftime('%Y-%m-%d')))
                conn.commit()
                print("✅ Audit logging setting updated.")

            elif choice == '5':
                max_size = input("Maximum file upload size (MB, default 50): ").strip() or "50"
                cursor.execute('''
                UPDATE system_settings SET setting_value = ?, updated_date = ?
                WHERE setting_name = 'max_file_size_mb'
                ''', (max_size, datetime.now().strftime('%Y-%m-%d')))
                conn.commit()
                print("✅ File upload restrictions updated.")

            elif choice == '6':
                self.view_access_logs()

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def view_access_logs(self):
        """View system access logs"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            days = input("View logs for how many days? (default 7): ").strip()
            days = int(days) if days else 7

            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            cursor.execute('''
            SELECT user_id, action, table_name, record_id, timestamp, ip_address
            FROM audit_log
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT 100
            ''', (cutoff_date,))

            logs = cursor.fetchall()

            print(f"\n🔍 ACCESS LOGS (Last {days} days)")
            print("=" * 80)

            if not logs:
                print("No logs found.")
                conn.close()
                return

            for log in logs:
                user, action, table, record, timestamp, ip = log
                print(f"\n{timestamp} | User: {user} | Action: {action}")
                print(f"  Table: {table} | Record: {record}")
                if ip:
                    print(f"  IP: {ip}")

            print(f"\n{'='*80}")
            print(f"Total Log Entries: {len(logs)}")

            # Summary by user
            cursor.execute('''
            SELECT user_id, COUNT(*) as action_count
            FROM audit_log
            WHERE timestamp >= ?
            GROUP BY user_id
            ORDER BY action_count DESC
            ''', (cutoff_date,))

            user_summary = cursor.fetchall()

            print("\nActivity by User:")
            for user, count in user_summary:
                print(f"  {user}: {count} actions")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def web_interface_settings(self):
        """Configure web interface settings"""
        print("\n🌐 WEB INTERFACE SETTINGS")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\nWeb Interface Configuration:")

            port = input("Web server port (default 5000): ").strip() or "5000"
            cursor.execute('''
            INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
            VALUES ('web_interface_port', ?, 'Web interface port number', ?)
            ''', (port, datetime.now().strftime('%Y-%m-%d')))

            host = input("Host address (default 127.0.0.1): ").strip() or "127.0.0.1"
            cursor.execute('''
            INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
            VALUES ('web_interface_host', ?, 'Web interface host address', ?)
            ''', (host, datetime.now().strftime('%Y-%m-%d')))

            ssl_enabled = input("Enable SSL/HTTPS? (y/n): ").strip().lower() == 'y'
            cursor.execute('''
            INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
            VALUES ('web_interface_ssl', ?, 'Enable SSL for web interface', ?)
            ''', ('true' if ssl_enabled else 'false', datetime.now().strftime('%Y-%m-%d')))

            conn.commit()
            conn.close()

            print("\n✅ Web interface settings updated.")
            print(f"Access URL: http{'s' if ssl_enabled else ''}://{host}:{port}")

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def mobile_app_qr_code(self):
        """Generate QR code for mobile app access"""
        print("\n📱 MOBILE APP QR CODE")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get web interface settings
            cursor.execute('''
            SELECT setting_name, setting_value
            FROM system_settings
            WHERE setting_name IN ('web_interface_host', 'web_interface_port', 'web_interface_ssl')
            ''')

            settings = dict(cursor.fetchall())

            host = settings.get('web_interface_host', '127.0.0.1')
            port = settings.get('web_interface_port', '5000')
            ssl = settings.get('web_interface_ssl', 'false') == 'true'

            url = f"http{'s' if ssl else ''}://{host}:{port}"

            print(f"\nMobile Access URL: {url}")
            print("\nQR Code generation requires 'qrcode' library.")
            print("Install with: pip install qrcode[pil]")

            try:
                import qrcode

                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(url)
                qr.make(fit=True)

                qr.print_ascii(invert=True)

                save = input("\nSave QR code as image? (y/n): ").strip().lower()
                if save == 'y':
                    img = qr.make_image(fill_color="black", back_color="white")
                    filename = "mobile_access_qr.png"
                    img.save(filename)
                    print(f"✅ QR code saved as {filename}")

            except ImportError:
                print("\n❌ QR code library not installed.")
                print("Install with: pip install qrcode[pil]")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def api_keys_management(self):
        """Manage API keys for external access"""
        print("\n🔑 API KEYS MANAGEMENT")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Create api_keys table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key TEXT UNIQUE,
                key_name TEXT,
                created_by TEXT,
                created_date TEXT,
                expiry_date TEXT,
                is_active BOOLEAN DEFAULT 1,
                permissions TEXT
            )
            ''')

            print("\n1. List API Keys")
            print("2. Generate New API Key")
            print("3. Revoke API Key")
            print("4. Return to Main Menu")

            choice = input("\nChoose option (1-4): ").strip()

            if choice == '1':
                cursor.execute('SELECT key_id, key_name, api_key, created_date, is_active FROM api_keys')
                keys = cursor.fetchall()

                if not keys:
                    print("\nNo API keys found.")
                else:
                    print("\nAPI Keys:")
                    for key_id, name, key, created, active in keys:
                        status = "Active" if active else "Revoked"
                        masked_key = key[:8] + "..." + key[-4:]
                        print(f"  {key_id}. {name}: {masked_key} ({status}) - Created: {created}")

            elif choice == '2':
                key_name = input("API key name/description: ").strip()

                # Generate random API key
                import secrets
                api_key = secrets.token_urlsafe(32)

                expiry_days = input("Valid for how many days? (default 365): ").strip()
                expiry_days = int(expiry_days) if expiry_days else 365
                expiry_date = (datetime.now() + timedelta(days=expiry_days)).strftime('%Y-%m-%d')

                permissions = input("Permissions (read/write/admin): ").strip() or "read"

                cursor.execute('''
                INSERT INTO api_keys (api_key, key_name, created_by, created_date, expiry_date, permissions)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (api_key, key_name, self.current_user, datetime.now().strftime('%Y-%m-%d'),
                      expiry_date, permissions))

                conn.commit()

                print(f"\n✅ API Key Generated:")
                print(f"Name: {key_name}")
                print(f"Key: {api_key}")
                print(f"Expires: {expiry_date}")
                print(f"\n⚠️  Save this key securely - it won't be shown again!")

            elif choice == '3':
                key_id = input("Enter API key ID to revoke: ").strip()
                cursor.execute('UPDATE api_keys SET is_active = 0 WHERE key_id = ?', (key_id,))
                conn.commit()
                print("✅ API key revoked.")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def api_usage_statistics(self):
        """View API usage statistics"""
        print("\n📊 API USAGE STATISTICS")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Check if we have API usage logs
            cursor.execute('''
            SELECT COUNT(*) FROM audit_log WHERE action LIKE 'API%'
            ''')

            api_log_count = cursor.fetchone()[0]

            if api_log_count == 0:
                print("\nNo API usage logs found.")
                print("API usage tracking requires proper logging setup.")
                conn.close()
                return

            days = input("View statistics for how many days? (default 30): ").strip()
            days = int(days) if days else 30

            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            # API calls by date
            cursor.execute('''
            SELECT date(timestamp) as call_date, COUNT(*) as call_count
            FROM audit_log
            WHERE action LIKE 'API%' AND timestamp >= ?
            GROUP BY date(timestamp)
            ORDER BY call_date DESC
            ''', (cutoff_date,))

            daily_stats = cursor.fetchall()

            print(f"\nAPI Calls by Date (Last {days} days):")
            for date, count in daily_stats:
                print(f"  {date}: {count} calls")

            # API calls by endpoint
            cursor.execute('''
            SELECT table_name, COUNT(*) as call_count
            FROM audit_log
            WHERE action LIKE 'API%' AND timestamp >= ?
            GROUP BY table_name
            ORDER BY call_count DESC
            ''', (cutoff_date,))

            endpoint_stats = cursor.fetchall()

            print("\nAPI Calls by Endpoint:")
            for endpoint, count in endpoint_stats:
                print(f"  {endpoint}: {count} calls")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def api_documentation(self):
        """Display API documentation"""
        print("\n📚 API DOCUMENTATION")
        print("=" * 80)

        print("""
API Endpoints:

Authentication:
  POST   /api/auth/login              - Authenticate user
  POST   /api/auth/logout             - Logout user

Documents:
  GET    /api/documents               - List all documents
  GET    /api/documents/{id}          - Get document details
  POST   /api/documents               - Upload new document
  PUT    /api/documents/{id}          - Update document
  DELETE /api/documents/{id}          - Delete document

  GET    /api/documents/{id}/download - Download document file
  GET    /api/documents/{id}/versions - Get version history

Students:
  GET    /api/students                - List all students
  GET    /api/students/{id}           - Get student details
  GET    /api/students/{id}/documents - Get student's documents

Document Types:
  GET    /api/document-types          - List document types
  GET    /api/document-types/{id}     - Get type details

Reports:
  GET    /api/reports/status          - Get status report
  GET    /api/reports/expiry          - Get expiry report
  GET    /api/reports/compliance      - Get compliance report

Workflows:
  GET    /api/workflows               - List active workflows
  GET    /api/workflows/{id}          - Get workflow details
  POST   /api/workflows/{id}/complete - Complete workflow step

Authentication:
  All API requests require an API key in the header:
  Authorization: Bearer YOUR_API_KEY

Response Format:
  All responses are in JSON format
  Success: {"status": "success", "data": {...}}
  Error: {"status": "error", "message": "Error description"}

Rate Limiting:
  - 1000 requests per hour per API key
  - 10000 requests per day per API key

For detailed documentation and examples, visit:
  http://your-server/api/docs
        """)

        save_doc = input("\nSave documentation to file? (y/n): ").strip().lower()
        if save_doc == 'y':
            filename = "api_documentation.txt"
            with open(filename, 'w') as f:
                f.write("API Documentation\n")
                f.write("=" * 80 + "\n\n")
                f.write("Refer to console output for full documentation.\n")
            print(f"✅ Documentation saved to {filename}")

    def ocr_settings(self):
        """Configure OCR settings"""
        print("\n👁️  OCR SETTINGS")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\nOCR (Optical Character Recognition) Configuration:")

            ocr_enabled = input("Enable OCR processing? (y/n): ").strip().lower() == 'y'
            cursor.execute('''
            INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
            VALUES ('ocr_enabled', ?, 'Enable OCR text extraction', ?)
            ''', ('true' if ocr_enabled else 'false', datetime.now().strftime('%Y-%m-%d')))

            if ocr_enabled:
                print("\nOCR Engine Options:")
                print("1. Tesseract OCR (Open Source)")
                print("2. Google Cloud Vision API")
                print("3. AWS Textract")
                print("4. Azure Computer Vision")

                engine_choice = input("Select OCR engine (1-4): ").strip()

                engines = {
                    '1': 'tesseract',
                    '2': 'google_vision',
                    '3': 'aws_textract',
                    '4': 'azure_vision'
                }

                engine = engines.get(engine_choice, 'tesseract')

                cursor.execute('''
                INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
                VALUES ('ocr_engine', ?, 'OCR engine to use', ?)
                ''', (engine, datetime.now().strftime('%Y-%m-%d')))

                auto_ocr = input("Automatically OCR all uploaded documents? (y/n): ").strip().lower() == 'y'
                cursor.execute('''
                INSERT OR REPLACE INTO system_settings (setting_name, setting_value, description, updated_date)
                VALUES ('ocr_auto_process', ?, 'Automatically OCR uploaded documents', ?)
                ''', ('true' if auto_ocr else 'false', datetime.now().strftime('%Y-%m-%d')))

            conn.commit()
            conn.close()

            print("\n✅ OCR settings updated.")

            if ocr_enabled:
                print("\nNote: Ensure the selected OCR engine is properly installed and configured.")

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def batch_ocr_processing(self):
        """Process multiple documents with OCR"""
        print("\n👁️  BATCH OCR PROCESSING")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Check if OCR is enabled
            cursor.execute('''
            SELECT setting_value FROM system_settings WHERE setting_name = 'ocr_enabled'
            ''')

            result = cursor.fetchone()
            if not result or result[0] != 'true':
                print("❌ OCR is not enabled. Please enable it in OCR settings first.")
                conn.close()
                return

            print("\nSelect documents to process:")
            print("1. All pending documents")
            print("2. Documents by type")
            print("3. Specific student's documents")

            choice = input("\nChoose option (1-3): ").strip()

            if choice == '1':
                cursor.execute('''
                SELECT document_id, file_path, original_filename
                FROM student_documents
                WHERE is_current_version = 1
                ''')
            elif choice == '2':
                type_info = self.select_document_type(cursor)
                if not type_info:
                    conn.close()
                    return
                cursor.execute('''
                SELECT document_id, file_path, original_filename
                FROM student_documents
                WHERE type_id = ? AND is_current_version = 1
                ''', (type_info[0],))
            elif choice == '3':
                student_id = self.select_student(cursor)
                if not student_id:
                    conn.close()
                    return
                cursor.execute('''
                SELECT document_id, file_path, original_filename
                FROM student_documents
                WHERE student_id = ? AND is_current_version = 1
                ''', (student_id,))
            else:
                print(_t("shared.utils.document_manager.invalid_choice", default="Invalid choice. Please try again."))
                conn.close()
                return

            documents = cursor.fetchall()

            if not documents:
                print(_t("shared.utils.document_manager.no_documents_found", default="No documents found."))
                conn.close()
                return

            print(f"\nFound {len(documents)} documents to process.")

            confirm = input("Start OCR processing? (y/n): ").strip().lower()

            if confirm == 'y':
                print("\nProcessing documents...")
                print("Note: Actual OCR implementation requires OCR library integration.")

                for doc_id, file_path, filename in documents:
                    print(f"  Processing: {filename}")
                    # Placeholder for actual OCR processing
                    # In real implementation, would call OCR engine here

                print(f"\n✅ Batch processing complete for {len(documents)} documents.")
                print("OCR results would be stored in the database.")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def view_ocr_results(self):
        """View OCR extraction results"""
        print("\n👁️  OCR RESULTS")

        doc_id = input("Enter document ID: ").strip()

        print(f"\nOCR results for document {doc_id}:")
        print("\nNote: OCR results storage requires additional database schema.")
        print("This would display extracted text, confidence scores, and metadata.")
        print("\nFeature requires full OCR integration implementation.")

    def create_custom_workflow(self):
        """Create a custom workflow template"""
        try:
            print("\n⚙️  CREATE CUSTOM WORKFLOW")

            workflow_name = input("Workflow name: ").strip()
            if not workflow_name:
                print("Workflow name is required.")
                return

            description = input("Workflow description: ").strip()

            # Get document types this workflow applies to
            conn = get_connection()
            cursor = conn.cursor()

            type_info = self.select_document_type(cursor)
            if not type_info:
                conn.close()
                return

            type_id = type_info[0]

            print("\nDefine workflow steps:")
            steps = []
            step_order = 1

            while True:
                print(f"\nStep {step_order}:")
                step_name = input("  Step name (or 'done' to finish): ").strip()

                if step_name.lower() == 'done':
                    break

                assigned_to = input("  Assigned to (role/username): ").strip()
                required = input("  Required step? (y/n): ").strip().lower() == 'y'

                steps.append({
                    'name': step_name,
                    'order': step_order,
                    'assigned_to': assigned_to,
                    'required': required
                })

                step_order += 1

            if not steps:
                print("No steps defined. Workflow not created.")
                conn.close()
                return

            # Create workflow template table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflow_templates (
                template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT UNIQUE,
                description TEXT,
                type_id INTEGER,
                is_active BOOLEAN DEFAULT 1,
                created_by TEXT,
                created_date TEXT,
                FOREIGN KEY (type_id) REFERENCES document_types (type_id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflow_template_steps (
                step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER,
                step_name TEXT,
                step_order INTEGER,
                assigned_to TEXT,
                is_required BOOLEAN,
                FOREIGN KEY (template_id) REFERENCES workflow_templates (template_id)
            )
            ''')

            # Insert workflow template
            cursor.execute('''
            INSERT INTO workflow_templates (template_name, description, type_id, created_by, created_date)
            VALUES (?, ?, ?, ?, ?)
            ''', (workflow_name, description, type_id, self.current_user,
                  datetime.now().strftime('%Y-%m-%d')))

            template_id = cursor.lastrowid

            # Insert workflow steps
            for step in steps:
                cursor.execute('''
                INSERT INTO workflow_template_steps (template_id, step_name, step_order, assigned_to, is_required)
                VALUES (?, ?, ?, ?, ?)
                ''', (template_id, step['name'], step['order'], step['assigned_to'], step['required']))

            conn.commit()
            conn.close()

            print(f"\n✅ Workflow '{workflow_name}' created successfully with {len(steps)} steps!")

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def workflow_templates(self):
        """Manage workflow templates"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n⚙️  WORKFLOW TEMPLATES")

            # Check if workflow_templates table exists
            cursor.execute('''
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='workflow_templates'
            ''')

            if not cursor.fetchone():
                print("\nNo workflow templates found.")
                print("Use 'Create Custom Workflow' to create your first template.")
                conn.close()
                return

            cursor.execute('''
            SELECT template_id, template_name, description, is_active
            FROM workflow_templates
            ORDER BY template_name
            ''')

            templates = cursor.fetchall()

            if not templates:
                print("\nNo workflow templates found.")
                conn.close()
                return

            print("\nAvailable Templates:")
            for template_id, name, desc, active in templates:
                status = "Active" if active else "Inactive"
                print(f"\n{template_id}. {name} ({status})")
                if desc:
                    print(f"   {desc}")

                # Show steps
                cursor.execute('''
                SELECT step_name, step_order, assigned_to
                FROM workflow_template_steps
                WHERE template_id = ?
                ORDER BY step_order
                ''', (template_id,))

                steps = cursor.fetchall()
                if steps:
                    print("   Steps:")
                    for step_name, step_order, assigned_to in steps:
                        print(f"     {step_order}. {step_name} (assigned to: {assigned_to})")

            print("\nActions:")
            print("1. Activate/Deactivate template")
            print("2. Delete template")
            print("3. Return to menu")

            action = input("\nChoose action (1-3): ").strip()

            if action == '1':
                template_id = input("Enter template ID: ").strip()
                cursor.execute('''
                UPDATE workflow_templates
                SET is_active = NOT is_active
                WHERE template_id = ?
                ''', (template_id,))
                conn.commit()
                print("✅ Template status updated.")

            elif action == '2':
                template_id = input("Enter template ID to delete: ").strip()
                confirm = input(f"Delete template {template_id}? (y/n): ").strip().lower()
                if confirm == 'y':
                    cursor.execute('DELETE FROM workflow_template_steps WHERE template_id = ?', (template_id,))
                    cursor.execute('DELETE FROM workflow_templates WHERE template_id = ?', (template_id,))
                    conn.commit()
                    print("✅ Template deleted.")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def workflow_analytics(self):
        """View workflow performance analytics"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📊 WORKFLOW ANALYTICS")
            print("=" * 80)

            # Average workflow completion time
            cursor.execute('''
            SELECT AVG(
                julianday(MAX(completed_date)) - julianday(MIN(created_date))
            ) as avg_days
            FROM (
                SELECT dw.document_id,
                       (SELECT upload_date FROM student_documents WHERE document_id = dw.document_id) as created_date,
                       dw.completed_date
                FROM document_workflow dw
                WHERE dw.status = 'completed'
            )
            ''')

            avg_time = cursor.fetchone()[0]

            if avg_time:
                print(f"\nAverage Workflow Completion Time: {avg_time:.1f} days")

            # Workflow completion rate
            cursor.execute('''
            SELECT
                COUNT(DISTINCT CASE WHEN status = 'completed' THEN document_id END) as completed,
                COUNT(DISTINCT document_id) as total
            FROM document_workflow
            ''')

            completed, total = cursor.fetchone()

            if total > 0:
                completion_rate = (completed / total) * 100
                print(f"Workflow Completion Rate: {completion_rate:.1f}% ({completed}/{total})")

            # Bottleneck analysis - steps taking longest
            cursor.execute('''
            SELECT step_name, AVG(
                julianday(completed_date) - julianday(
                    (SELECT MIN(created_date) FROM student_documents WHERE document_id = document_workflow.document_id)
                )
            ) as avg_days
            FROM document_workflow
            WHERE status = 'completed' AND completed_date IS NOT NULL
            GROUP BY step_name
            ORDER BY avg_days DESC
            LIMIT 5
            ''')

            bottlenecks = cursor.fetchall()

            if bottlenecks:
                print("\nSlowest Workflow Steps:")
                for step_name, avg_days in bottlenecks:
                    if avg_days:
                        print(f"  {step_name}: {avg_days:.1f} days average")

            # Workflow status distribution
            cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM document_workflow
            GROUP BY status
            ''')

            status_dist = cursor.fetchall()

            if status_dist:
                print("\nWorkflow Status Distribution:")
                for status, count in status_dist:
                    print(f"  {status}: {count}")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def version_analytics(self):
        """Analyze document versioning patterns"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📊 VERSION ANALYTICS")
            print("=" * 80)

            # Documents with multiple versions
            cursor.execute('''
            SELECT parent_document_id, COUNT(*) as version_count
            FROM student_documents
            WHERE parent_document_id IS NOT NULL
            GROUP BY parent_document_id
            HAVING COUNT(*) > 1
            ORDER BY version_count DESC
            LIMIT 10
            ''')

            multi_version = cursor.fetchall()

            if multi_version:
                print("\nDocuments with Most Versions:")
                for parent_id, count in multi_version:
                    print(f"  Document {parent_id}: {count} versions")

            # Average versions per document type
            cursor.execute('''
            SELECT dt.type_name, AVG(version_count) as avg_versions
            FROM document_types dt
            JOIN (
                SELECT type_id, COUNT(*) as version_count
                FROM student_documents
                GROUP BY student_id, type_id
            ) vc ON dt.type_id = vc.type_id
            GROUP BY dt.type_name
            ORDER BY avg_versions DESC
            ''')

            avg_versions = cursor.fetchall()

            if avg_versions:
                print("\nAverage Versions by Document Type:")
                for type_name, avg_ver in avg_versions:
                    print(f"  {type_name}: {avg_ver:.2f} versions")

            # Total storage used by versions
            cursor.execute('''
            SELECT SUM(file_size) as total_size,
                   COUNT(*) as version_count
            FROM student_documents
            WHERE is_current_version = 0
            ''')

            total_size, old_versions = cursor.fetchone()

            if total_size:
                size_mb = total_size / (1024 * 1024)
                print(f"\nOld Versions Storage:")
                print(f"  Old versions: {old_versions}")
                print(f"  Storage used: {size_mb:.2f} MB")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def template_analytics(self):
        """Analyze document template usage"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📊 TEMPLATE ANALYTICS")
            print("=" * 80)

            # Most used document types
            cursor.execute('''
            SELECT dt.type_name, COUNT(*) as usage_count
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            GROUP BY dt.type_name
            ORDER BY usage_count DESC
            ''')

            usage = cursor.fetchall()

            if usage:
                print("\nDocument Type Usage:")
                for type_name, count in usage:
                    print(f"  {type_name}: {count} documents")

            # Verification success rate by type
            cursor.execute('''
            SELECT dt.type_name,
                   COUNT(*) as total,
                   SUM(CASE WHEN sd.verification_status = 'Verified' THEN 1 ELSE 0 END) as verified
            FROM student_documents sd
            JOIN document_types dt ON sd.type_id = dt.type_id
            WHERE sd.is_current_version = 1
            GROUP BY dt.type_name
            ORDER BY dt.type_name
            ''')

            verification_rates = cursor.fetchall()

            if verification_rates:
                print("\nVerification Success Rate by Type:")
                for type_name, total, verified in verification_rates:
                    rate = (verified / total * 100) if total > 0 else 0
                    print(f"  {type_name}: {rate:.1f}% ({verified}/{total})")

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def set_course_requirements(self):
        """Set document requirements for specific courses/programs"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📚 SET COURSE REQUIREMENTS")

            course_code = input("Course code (e.g., CS101): ").strip()
            if not course_code:
                print("Course code is required.")
                conn.close()
                return

            program = input("Program name: ").strip()

            print("\nSelect required document types:")

            cursor.execute('''
            SELECT type_id, type_name, category
            FROM document_types
            WHERE is_active = 1
            ORDER BY category, type_name
            ''')

            doc_types = cursor.fetchall()

            if not doc_types:
                print("No document types available.")
                conn.close()
                return

            print("\nAvailable Document Types:")
            for i, (type_id, type_name, category) in enumerate(doc_types):
                print(f"{i+1}. {type_name} ({category})")

            selected = input("\nEnter numbers of required documents (comma-separated): ").strip()

            if not selected:
                print("No documents selected.")
                conn.close()
                return

            selected_indices = [int(x.strip()) - 1 for x in selected.split(',')]

            for idx in selected_indices:
                if 0 <= idx < len(doc_types):
                    type_id = doc_types[idx][0]

                    is_mandatory = input(f"Is {doc_types[idx][1]} mandatory? (y/n): ").strip().lower() == 'y'

                    deadline_days = input(f"Deadline (days after enrollment, default 30): ").strip()
                    deadline_days = int(deadline_days) if deadline_days else 30

                    cursor.execute('''
                    INSERT OR REPLACE INTO course_requirements
                    (course_code, program, type_id, is_mandatory, deadline_days)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (course_code, program, type_id, is_mandatory, deadline_days))

            conn.commit()
            conn.close()

            print(f"\n✅ Requirements set for {course_code}")

        except ValueError:
            print(_t("shared.utils.document_manager.invalid_input", default="Invalid input."))
        except sqlite3.Error as e:
            print(f"Database error: {e}")

    def archive_old_versions(self):
        """Archive old document versions to free up space"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            print("\n📦 ARCHIVE OLD VERSIONS")

            # Count old versions
            cursor.execute('''
            SELECT COUNT(*), SUM(file_size)
            FROM student_documents
            WHERE is_current_version = 0
            ''')

            count, total_size = cursor.fetchone()

            if count == 0:
                print("No old versions to archive.")
                conn.close()
                return

            size_mb = (total_size or 0) / (1024 * 1024)

            print(f"\nFound {count} old versions")
            print(f"Total size: {size_mb:.2f} MB")

            print("\nArchive Options:")
            print("1. Move to archive directory")
            print("2. Create compressed archive")
            print("3. Delete old versions (WARNING: Cannot be undone)")
            print("4. Cancel")

            choice = input("\nChoose option (1-4): ").strip()

            if choice == '1' or choice == '2':
                archive_dir = 'document_archive'
                os.makedirs(archive_dir, exist_ok=True)

                cursor.execute('''
                SELECT document_id, file_path, original_filename
                FROM student_documents
                WHERE is_current_version = 0 AND file_path IS NOT NULL
                ''')

                old_docs = cursor.fetchall()

                if choice == '2':
                    # Create zip archive
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    zip_filename = f"archived_versions_{timestamp}.zip"
                    zip_path = os.path.join(archive_dir, zip_filename)

                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as archive_zip:
                        for doc_id, file_path, orig_name in old_docs:
                            if os.path.exists(file_path):
                                arcname = f"{doc_id}_{orig_name}"
                                archive_zip.write(file_path, arcname)

                    print(f"\n✅ Created archive: {zip_path}")
                else:
                    # Move files
                    for doc_id, file_path, orig_name in old_docs:
                        if os.path.exists(file_path):
                            new_path = os.path.join(archive_dir, f"{doc_id}_{orig_name}")
                            shutil.move(file_path, new_path)

                            # Update database
                            cursor.execute('''
                            UPDATE student_documents
                            SET file_path = ?
                            WHERE document_id = ?
                            ''', (new_path, doc_id))

                    conn.commit()
                    print(f"\n✅ Moved {len(old_docs)} files to archive directory")

            elif choice == '3':
                confirm = input("\n⚠️  Delete all old versions? Type 'DELETE' to confirm: ").strip()

                if confirm == 'DELETE':
                    cursor.execute('''
                    SELECT file_path FROM student_documents
                    WHERE is_current_version = 0 AND file_path IS NOT NULL
                    ''')

                    files_to_delete = cursor.fetchall()

                    # Delete files
                    deleted_count = 0
                    for file_path, in files_to_delete:
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                                deleted_count += 1
                            except Exception as e:
                                print(f"Error deleting {file_path}: {e}")

                    # Delete database records
                    cursor.execute('DELETE FROM student_documents WHERE is_current_version = 0')

                    conn.commit()
                    print(f"\n✅ Deleted {deleted_count} old version files and {count} database records")
                else:
                    print(_t("shared.utils.document_manager.operation_cancelled", default="Operation cancelled."))

            conn.close()

        except sqlite3.Error as e:
            print(f"Database error: {e}")

def display_document_management_menu():
    """Standalone function to start the document management system"""
    print("🚀 Starting Enhanced Document Management System...")
    
    # Initialize the system
    doc_manager = DocumentManager()
    
    try:
        # Start the main application loop
        doc_manager.display_main_menu()
    except KeyboardInterrupt:
        print("\n\n👋 System shutdown requested. Goodbye!")
    except Exception as e:
        print(f"\n❌ System error: {e}")
        print("Please contact system administrator.")

def main():
    import sys
    import getpass

    from university_system.infrastructure.auth import (
        UserAuth, set_auth_instance, get_current_user
    )

    def ensure_login() -> "UserAuth | None":
        cu = get_current_user()
        if cu:
            return None  # already logged in

        auth = get_auth()
        if auth is None:
            auth = UserAuth()

        # Try common interactive auth entrypoints your UserAuth might have
        for method in ("run_authentication_menu", "login_console", "login_menu", "run_console_interface", "run"):
            if hasattr(auth, method):
                try:
                    getattr(auth, method)()
                except Exception:
                    pass
                if getattr(auth, "current_user", None):
                    set_auth_instance(auth)
                    return auth

        # Fallback: prompt + direct login()
        if hasattr(auth, "login"):
            username = input("Username: ").strip()
            password = getpass.getpass("Password: ")
            try:
                ok = auth.login(username, password)
            except TypeError:
                ok = auth.login(username, password)

            if ok and getattr(auth, "current_user", None):
                set_auth_instance(auth)
                return auth

        if not get_current_user():
            print("❌ Login failed or not completed. The Document Manager requires an authenticated session.")
            sys.exit(1)

        set_auth_instance(auth)
        return auth

    # 1) Ensure login (populates global current_user used by DocumentManager.check_authentication)
    auth_instance = ensure_login()

    # 2) Start Document Manager
    dm = DocumentManager()

    # 3) Give email subsystem the auth context if available
    try:
        set_auth_context(dm, auth_instance)  # safe if None
    except NameError:
        if auth_instance is not None:
            dm.auth = auth_instance

    # 4) Run
    dm.display_main_menu()


if __name__ == "__main__":
    main()
