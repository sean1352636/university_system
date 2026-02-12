import tkinter as tk
from tkinter import ttk, messagebox
from university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
import os
import hashlib
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

try:
    from university_system.infrastructure.database.db import DatabaseManager as InfraDBManager, get_connection
    from university_system.infrastructure.auth import UserAuth, get_current_user
except ImportError:
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))
    def get_current_user():
        return {'username': 'admin', 'role': 'admin'}

try:
    from university_system.modules.shared.utils.i18n import get_text as _t, get_current_language
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"


class DocumentDatabaseManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

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
            from university_system.core.defaults import DEFAULT_ADMIN_PASSWORD
            admin_password = DEFAULT_ADMIN_PASSWORD
            try:
                from university_system.infrastructure.auth import UserAuth
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
                            log_message(f"\u2713 Success: {migration_name}")
                            success_count += 1
                        except sqlite3.OperationalError as e:
                            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                                log_message(f"\u2299 Already applied: {migration_name}")
                            else:
                                log_message(f"\u2717 Error: {migration_name} - {str(e)}")
                                error_count += 1
                        except Exception as e:
                            log_message(f"\u2717 Error: {migration_name} - {str(e)}")
                            error_count += 1

                    conn.close()

                    log_message(f"\nMigrations complete: {success_count} successful, {error_count} errors")

                    self.gui.log_event('migrate', 'database', None, {
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
                    log_message(f"\u2717 Fatal error: {str(e)}")
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
