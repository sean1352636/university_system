import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import json
import os
import threading
from functools import partial
import webbrowser
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.core.sql_safety import validate_identifier

# Import authentication - REQUIRED (no fallback for security)
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Import activity logger for audit trail
try:
    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import all the original functions from helpdesk.py
# This ensures backwards compatibility
try:
    from education_system.university_system.modules.domain.student_affairs.services.helpdesk import (
        backup_database, bulk_assign_tickets, check_data_integrity,
        create_kb_article, display_helpdesk_menu, escalate_ticket,
        escalate_ticket_manual, export_tickets_csv, export_users_csv,
        init_default_data, init_helpdesk_db, search_kb_articles,
        setup_enhanced_helpdesk_permissions
    )
except ImportError:
    # If helpdesk.py is not available, we'll define minimal stubs
    print("Warning: helpdesk.py not found. Running in standalone mode.")
    
    def init_helpdesk_db():
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Create support_tickets table with enhanced fields
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS support_tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                assigned_to INTEGER,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT,
                status TEXT DEFAULT 'open',
                priority TEXT DEFAULT 'medium',
                impact TEXT DEFAULT 'low',
                urgency TEXT DEFAULT 'low',
                source TEXT DEFAULT 'web',
                resolution TEXT,
                satisfaction_rating INTEGER,
                satisfaction_feedback TEXT,
                estimated_hours REAL,
                actual_hours REAL,
                due_date TEXT,
                resolved_at TEXT,
                first_response_at TEXT,
                last_activity_at TEXT,
                escalation_level INTEGER DEFAULT 0,
                tags TEXT,
                department TEXT,
                organization_id INTEGER,
                parent_ticket_id INTEGER,
                knowledge_base_articles TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (assigned_to) REFERENCES users (id),
                FOREIGN KEY (parent_ticket_id) REFERENCES support_tickets (ticket_id)
            )
            ''')

            # Add subject column if it doesn't exist (migration)
            try:
                # Check if subject column exists using PRAGMA
                cursor.execute("PRAGMA table_info(support_tickets)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'subject' not in columns:
                    cursor.execute("ALTER TABLE support_tickets ADD COLUMN subject TEXT DEFAULT 'No Subject'")
                    conn.commit()
            except Exception as e:
                print(f"Warning: Could not add subject column: {e}")

            # Create ticket_replies table with enhanced fields
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_replies (
                reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                user_id INTEGER,
                message TEXT NOT NULL,
                is_internal BOOLEAN DEFAULT 0,
                reply_type TEXT DEFAULT 'comment',
                time_spent REAL DEFAULT 0,
                created_at TEXT,
                edited_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')
            
            # Create ticket_attachments table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_attachments (
                attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                reply_id INTEGER,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_size INTEGER,
                mime_type TEXT,
                file_hash TEXT,
                uploaded_by INTEGER,
                upload_path TEXT,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (reply_id) REFERENCES ticket_replies (reply_id),
                FOREIGN KEY (uploaded_by) REFERENCES users (id)
            )
            ''')
            
            # Create ticket_assignments table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_assignments (
                assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                assigned_from INTEGER,
                assigned_to INTEGER,
                assignment_reason TEXT,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (assigned_from) REFERENCES users (id),
                FOREIGN KEY (assigned_to) REFERENCES users (id)
            )
            ''')
            
            # Create ticket_templates table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_templates (
                template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                subject_template TEXT,
                message_template TEXT,
                default_priority TEXT,
                default_impact TEXT,
                default_urgency TEXT,
                form_fields TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_by INTEGER,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
            ''')
            
            # Create sla_policies table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sla_policies (
                sla_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                priority TEXT,
                impact TEXT,
                urgency TEXT,
                first_response_hours INTEGER,
                resolution_hours INTEGER,
                escalation_hours INTEGER,
                business_hours_only BOOLEAN DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
            ''')
            
            # Create ticket_workflows table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_workflows (
                workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                trigger_type TEXT NOT NULL,
                trigger_conditions TEXT,
                actions TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_by INTEGER,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
            ''')
            
            # Create ticket_time_tracking table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_time_tracking (
                time_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                user_id INTEGER,
                start_time TEXT,
                end_time TEXT,
                duration_minutes INTEGER,
                description TEXT,
                billable BOOLEAN DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')
            
            # Create ticket_escalations table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_escalations (
                escalation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                escalation_level INTEGER,
                escalated_to INTEGER,
                escalated_by INTEGER,
                escalation_reason TEXT,
                resolved BOOLEAN DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (escalated_to) REFERENCES users (id),
                FOREIGN KEY (escalated_by) REFERENCES users (id)
            )
            ''')
            
            # Create ticket_links table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_links (
                link_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                linked_ticket_id INTEGER,
                link_type TEXT,
                created_by INTEGER,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (linked_ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
            ''')
            
            # Create ticket_audit_log table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_audit_log (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                user_id INTEGER,
                action TEXT NOT NULL,
                old_values TEXT,
                new_values TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')
            
            # Create knowledge_base table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_base (
                article_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT,
                tags TEXT,
                author_id INTEGER,
                status TEXT DEFAULT 'draft',
                views INTEGER DEFAULT 0,
                helpful_votes INTEGER DEFAULT 0,
                unhelpful_votes INTEGER DEFAULT 0,
                search_keywords TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (author_id) REFERENCES users (id)
            )
            ''')
            
            # Create departments table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                manager_id INTEGER,
                email TEXT,
                sla_policy_id INTEGER,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (manager_id) REFERENCES users (id),
                FOREIGN KEY (sla_policy_id) REFERENCES sla_policies (sla_id)
            )
            ''')
            
            # Create organizations table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS organizations (
                org_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                domain TEXT,
                contact_email TEXT,
                phone TEXT,
                address TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
            ''')
            
            # Create saved_searches table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_searches (
                search_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                search_criteria TEXT,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            conn.commit()
            conn.close()
            print("Enhanced helpdesk database initialized successfully!")
            
            # Initialize default data
            init_default_data()
            
        except sqlite3.Error as e:
            print(f"An error occurred while initializing the helpdesk database: {e}")
        
    def setup_enhanced_helpdesk_permissions():
        """
        Setup enhanced helpdesk permissions

        Creates and configures helpdesk-specific permissions in the
        authentication system. This includes permissions for:
        - Creating and managing tickets
        - Knowledge base management
        - SLA and workflow configuration
        - Analytics and reporting
        - Department and organization management

        Permissions are automatically assigned to appropriate roles
        (Student, Staff, Admin) based on typical helpdesk workflows.

        Note: This is a wrapper that calls the actual implementation
        from the services layer. It's provided here for backwards
        compatibility and convenience.
        """
        try:
            # Try to import and call the actual implementation
            from education_system.university_system.modules.domain.student_affairs.services.helpdesk import (
                setup_enhanced_helpdesk_permissions as service_setup_permissions
            )
            service_setup_permissions()
        except ImportError:
            # If service layer is not available, do basic setup
            print("Warning: Helpdesk service layer not available. Setting up basic permissions...")
            try:
                from education_system.university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                # Check if permissions table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='permissions'")
                if not cursor.fetchone():
                    print("Permissions table not found. Authentication system must be initialized first.")
                    conn.close()
                    return

                # Add basic helpdesk permissions
                basic_permissions = [
                    ('create_ticket', 'Can create support tickets'),
                    ('view_own_tickets', 'Can view own support tickets'),
                    ('view_all_tickets', 'Can view all support tickets'),
                    ('manage_tickets', 'Can manage ticket status and priority')
                ]

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for perm_name, perm_desc in basic_permissions:
                    cursor.execute(
                        "SELECT COUNT(*) FROM permissions WHERE permission_name = ?",
                        (perm_name,)
                    )
                    if cursor.fetchone()[0] == 0:
                        cursor.execute(
                            "INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)",
                            (perm_name, perm_desc, timestamp)
                        )

                conn.commit()
                conn.close()
                print("Basic helpdesk permissions setup completed")

            except Exception as e:
                print(f"Error setting up basic helpdesk permissions: {e}")
        except Exception as e:
            print(f"Error setting up enhanced helpdesk permissions: {e}")



class HelpdeskGUI:
    def __init__(self, root, auth=None):
        """
        Initialize Helpdesk GUI.

        Args:
            root: Tkinter root window
            auth: Authentication instance (if None, will use get_auth())

        Raises:
            RuntimeError: If authentication system is not available
        """
        self.root = root
        self.current_user = None

        # Get authentication instance - REQUIRED for security
        self.auth = auth if auth is not None else get_auth()
        if self.auth is None:
            # Try global auth as fallback
            self.auth = get_global_auth()

        if self.auth is None:
            messagebox.showerror(
                _t("helpdesk.auth.required_title", default="Authentication Required"),
                _t("helpdesk.auth.not_available", default="Authentication system not available. Helpdesk GUI cannot start.")
            )
            root.destroy()
            return

        # Initialize the original helpdesk system
        try:
            init_helpdesk_db()
            setup_enhanced_helpdesk_permissions()
        except Exception:
            pass

        # Run schema migration to ensure subject column exists
        self.ensure_subject_column()

        # Set up current user from existing authentication system
        self.setup_current_user()

        self.setup_styles()
        self.setup_main_window()
        self.create_menu_bar()

        # Show appropriate interface based on authentication status
        if self.current_user:
            self.show_main_dashboard()
        else:
            messagebox.showerror(
                _t("helpdesk.auth.required_title", default="Authentication Required"),
                _t("helpdesk.auth.login_required", default="Please log in through the main University System GUI.\n\nRun: python run.py --gui\n\nHelpdesk can only be accessed after logging in through the main system.")
            )
            root.destroy()
            return

    def ensure_subject_column(self):
        """Ensure the support_tickets table has all required columns"""
        conn = None
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout
            cursor = conn.cursor()

            # Check existing columns
            cursor.execute("PRAGMA table_info(support_tickets)")
            columns = [row[1] for row in cursor.fetchall()]

            # Define all required columns with their defaults
            # Note: SQLite ALTER TABLE doesn't allow non-constant defaults like CURRENT_TIMESTAMP
            required_columns = [
                ('subject', "TEXT DEFAULT 'No Subject'"),
                ('message', "TEXT DEFAULT ''"),
                ('created_at', "TEXT"),
                ('updated_at', "TEXT"),
                ('impact', "TEXT DEFAULT 'low'"),
                ('urgency', "TEXT DEFAULT 'low'"),
                ('source', "TEXT DEFAULT 'web'"),
                ('last_activity_at', "TEXT"),
                ('user_id', "INTEGER DEFAULT 0"),
                ('assigned_to', "INTEGER"),
                ('resolution', "TEXT"),
                ('satisfaction_feedback', "TEXT"),
                ('first_response_at', "TEXT"),
                ('escalation_level', "INTEGER DEFAULT 0"),
                ('department', "TEXT"),
            ]

            # Add missing columns
            for col_name, col_def in required_columns:
                if col_name not in columns:
                    try:
                        safe_col = validate_identifier(col_name, "column")
                        cursor.execute('ALTER TABLE support_tickets ADD COLUMN ' + safe_col + ' ' + col_def)
                        conn.commit()
                        print(f"Added {col_name} column to support_tickets table")
                    except Exception as col_err:
                        print(f"Warning: Could not add {col_name} column: {col_err}")

        except Exception as e:
            print(f"Warning: Could not ensure required columns: {e}")
        finally:
            if conn:
                conn.close()

    def setup_current_user(self):
        """Setup current user from existing authentication system"""
        try:
            # Check if auth system has a current authenticated user
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                auth_user = self.auth.current_user

                # auth_user is already a dictionary from UserAuth system
                if isinstance(auth_user, dict):
                    self.current_user = {
                        "id": auth_user.get('id', 0),
                        "username": auth_user.get('username', 'Unknown'),
                        "role": auth_user.get('role', 'user'),
                        "permissions": auth_user.get('permissions', [])
                    }
                else:
                    # Handle case where it might be an object
                    self.current_user = {
                        "id": getattr(auth_user, 'id', 0),
                        "username": getattr(auth_user, 'username', 'Unknown'),
                        "role": getattr(auth_user, 'role', 'user'),
                        "permissions": getattr(auth_user, 'permissions', [])
                    }

                print(f"✓ Helpdesk GUI: Using authenticated user {self.current_user['username']} ({self.current_user['role']})")
            else:
                self.current_user = None
                print("ℹ Helpdesk GUI: No authenticated user - will show login screen")
        except Exception as e:
            print(f"✗ Error setting up current user: {e}")
            self.current_user = None

    def setup_styles(self):
        """Setup custom styles for the GUI"""
        self.style = ttk.Style()

        # Configure custom styles
        self.style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
        self.style.configure('Heading.TLabel', font=('Arial', 12, 'bold'))
        self.style.configure('Success.TLabel', foreground='green')
        self.style.configure('Error.TLabel', foreground='red')
        self.style.configure('Warning.TLabel', foreground='orange')

        # Custom button styles
        self.style.configure('Primary.TButton', font=('Arial', 10, 'bold'))
        self.style.configure('Success.TButton', foreground='white')
        self.style.configure('Danger.TButton', foreground='white')

    def setup_main_window(self):
        """Setup the main window"""
        self.root.title(_t("helpdesk.window_title", default="Enhanced Helpdesk System"))
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)

        # Center the window
        self.center_window()

        # Create main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill='both', expand=True, padx=10, pady=10)

    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def create_menu_bar(self):
        """Create the application menu bar with role-based filtering"""
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)

        # Get user role for filtering
        is_admin = self.is_admin()
        is_staff = self.is_staff()
        is_student = self.is_student()

        # File menu
        file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=_t("helpdesk.menu.file", default="File"), menu=file_menu)
        file_menu.add_command(label=_t("helpdesk.menu.new_ticket", default="New Ticket"), command=self.show_create_ticket)

        # Admin/Staff can export/import data
        if is_admin or is_staff:
            file_menu.add_separator()
            file_menu.add_command(label=_t("helpdesk.menu.export_data", default="Export Data"), command=self.show_export_dialog)
            file_menu.add_command(label=_t("helpdesk.menu.import_data", default="Import Data"), command=self.show_import_dialog)

        file_menu.add_separator()
        file_menu.add_command(label=_t("common.exit", default="Exit"), command=self.root.quit)

        # Tickets menu
        tickets_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=_t("helpdesk.menu.tickets", default="Tickets"), menu=tickets_menu)
        tickets_menu.add_command(label=_t("helpdesk.menu.my_tickets", default="My Tickets"), command=self.show_my_tickets)

        # Admin/Staff can view all tickets
        if is_admin or is_staff:
            tickets_menu.add_command(label=_t("helpdesk.menu.all_tickets", default="All Tickets"), command=self.show_all_tickets)

        tickets_menu.add_command(label=_t("helpdesk.menu.search_tickets", default="Search Tickets"), command=self.show_search_tickets)

        # Knowledge Base menu
        kb_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=_t("helpdesk.menu.knowledge_base", default="Knowledge Base"), menu=kb_menu)
        kb_menu.add_command(label=_t("helpdesk.menu.browse_articles", default="Browse Articles"), command=self.show_knowledge_base)

        # Admin/Staff can create articles
        if is_admin or is_staff:
            kb_menu.add_command(label=_t("helpdesk.menu.create_article", default="Create Article"), command=self.show_create_article)

        # Reports menu (Admin/Staff only)
        if is_admin or is_staff:
            reports_menu = tk.Menu(self.menubar, tearoff=0)
            self.menubar.add_cascade(label=_t("helpdesk.menu.reports", default="Reports"), menu=reports_menu)
            reports_menu.add_command(label=_t("helpdesk.menu.analytics_dashboard", default="Analytics Dashboard"), command=self.show_analytics)
            reports_menu.add_command(label=_t("helpdesk.menu.generate_reports", default="Generate Reports"), command=self.show_reports)

        # Admin menu (Admin only)
        if is_admin and self.current_user and self.has_permission('manage_tickets'):
            admin_menu = tk.Menu(self.menubar, tearoff=0)
            self.menubar.add_cascade(label=_t("helpdesk.menu.admin", default="Admin"), menu=admin_menu)
            admin_menu.add_command(label=_t("helpdesk.menu.system_management", default="System Management"), command=self.show_system_management)
            admin_menu.add_command(label=_t("helpdesk.menu.user_management", default="User Management"), command=self.show_user_management)
            admin_menu.add_command(label=_t("helpdesk.menu.settings", default="Settings"), command=self.show_settings)

        # Help menu
        help_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label=_t("helpdesk.menu.help", default="Help"), menu=help_menu)
        help_menu.add_command(label=_t("helpdesk.menu.user_guide", default="User Guide"), command=self.show_user_guide)
        help_menu.add_command(label=_t("helpdesk.menu.about", default="About"), command=self.show_about)

    def has_permission(self, permission):
        """Check if current user has permission"""
        if not self.auth or not self.current_user:
            return False
        try:
            return self.auth.check_permission(permission)
        except Exception:
            return False

    def get_user_role(self):
        """Get the current user's role"""
        try:
            if self.current_user and isinstance(self.current_user, dict):
                return self.current_user.get('role', '').lower()
            return None
        except Exception as e:
            print(f"Error getting user role: {e}")
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff or helpdesk staff"""
        role = self.get_user_role()
        return role in ['staff', 'helpdesk_staff', 'support_staff']

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'

    def clear_main_container(self):
        """Clear the main container"""
        for widget in self.main_container.winfo_children():
            widget.destroy()

    def switch_to_cli(self):
        """Switch to CLI mode"""
        self.root.withdraw()  # Hide GUI
        try:
            # Import and run the original CLI system
            if self.auth:
                display_helpdesk_menu(self.auth)
            else:
                # Run without auth for demo
                print("Switching to CLI mode...")
                print("This would run the original CLI helpdesk system")
        except Exception as e:
            print(f"Error switching to CLI: {e}")
        finally:
            self.root.deiconify()  # Show GUI again

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
                from education_system.university_system.modules.shared.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def open_student_support_gui(self):
        """Open the Student Support Portal GUI in a new window"""
        try:
            from education_system.university_system.modules.domain.student_affairs.gui.student_support import StudentSupportGUI

            # Create a new Toplevel window for Student Support
            support_window = tk.Toplevel(self.root)
            support_window.title(_t("student_support.window_title", default="Student Support Portal"))
            support_window.geometry("1850x1100")
            support_window.transient(self.root)

            # Initialize the Student Support GUI in the new window
            StudentSupportGUI(support_window, self.auth)

        except ImportError as e:
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("helpdesk.errors.load_failed", default="Could not load Student Support GUI: {error}").format(error=e))
        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("helpdesk.errors.load_failed", default="Could not open Student Support Portal: {error}").format(error=e))
            import traceback
            traceback.print_exc()

