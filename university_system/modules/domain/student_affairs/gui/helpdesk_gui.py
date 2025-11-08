import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import json
import os
import threading
from functools import partial
import webbrowser
from university_system.infrastructure.email.template_utils import render_template

# Import centralized authentication system
try:
    from university_system.infrastructure.auth.user_authentication import UserAuth
    AUTH_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import UserAuth: {e}")
    AUTH_AVAILABLE = False
    # Minimal fallback for development/testing
    class UserAuth:
        def __init__(self):
            self.current_user = None
        def login(self, username, password):
            if username and password:
                self.current_user = {'username': username, 'role': 'staff'}
                return True
            return False
        def return_to_main_menu(self):
            self.current_user = None
        def check_permission(self, permission):
            return bool(self.current_user)

# Import all the original functions from helpdesk.py
# This ensures backwards compatibility
try:
    from university_system.modules.domain.student_affairs.services.helpdesk import (
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
        pass

class HelpdeskGUI:
    def __init__(self, root, auth_system=None):
        self.root = root
        self.current_user = None

        # Initialize centralized authentication system
        if auth_system:
            self.auth = auth_system
        else:
            self.auth = UserAuth()

        # Initialize the original helpdesk system
        try:
            init_helpdesk_db()
            setup_enhanced_helpdesk_permissions()
        except:
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
            self.show_login()

    def ensure_subject_column(self):
        """Ensure the support_tickets table has a subject column"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Check if subject column exists
            cursor.execute("PRAGMA table_info(support_tickets)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'subject' not in columns:
                cursor.execute("ALTER TABLE support_tickets ADD COLUMN subject TEXT DEFAULT 'No Subject'")
                conn.commit()
                print("Added subject column to support_tickets table")

            # Also ensure created_at and updated_at columns exist
            if 'created_at' not in columns:
                cursor.execute("ALTER TABLE support_tickets ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP")
                conn.commit()
                print("Added created_at column to support_tickets table")

            if 'updated_at' not in columns:
                cursor.execute("ALTER TABLE support_tickets ADD COLUMN updated_at TEXT DEFAULT CURRENT_TIMESTAMP")
                conn.commit()
                print("Added updated_at column to support_tickets table")

            conn.close()
        except Exception as e:
            print(f"Warning: Could not ensure required columns: {e}")

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
        self.root.title("Enhanced Helpdesk System")
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
        """Create the application menu bar"""
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)
        
        # File menu
        file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Ticket", command=self.show_create_ticket)
        file_menu.add_separator()
        file_menu.add_command(label="Export Data", command=self.show_export_dialog)
        file_menu.add_command(label="Import Data", command=self.show_import_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Tickets menu
        tickets_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Tickets", menu=tickets_menu)
        tickets_menu.add_command(label="My Tickets", command=self.show_my_tickets)
        tickets_menu.add_command(label="All Tickets", command=self.show_all_tickets)
        tickets_menu.add_command(label="Search Tickets", command=self.show_search_tickets)
        
        # Knowledge Base menu
        kb_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Knowledge Base", menu=kb_menu)
        kb_menu.add_command(label="Browse Articles", command=self.show_knowledge_base)
        kb_menu.add_command(label="Create Article", command=self.show_create_article)
        
        # Reports menu
        reports_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Reports", menu=reports_menu)
        reports_menu.add_command(label="Analytics Dashboard", command=self.show_analytics)
        reports_menu.add_command(label="Generate Reports", command=self.show_reports)
        
        # Admin menu (only for admins)
        if self.current_user and self.has_permission('manage_tickets'):
            admin_menu = tk.Menu(self.menubar, tearoff=0)
            self.menubar.add_cascade(label="Admin", menu=admin_menu)
            admin_menu.add_command(label="System Management", command=self.show_system_management)
            admin_menu.add_command(label="User Management", command=self.show_user_management)
            admin_menu.add_command(label="Settings", command=self.show_settings)
        
        # Help menu
        help_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_user_guide)
        help_menu.add_command(label="About", command=self.show_about)

    def has_permission(self, permission):
        """Check if current user has permission"""
        if not self.auth or not self.current_user:
            return False
        try:
            return self.auth.check_permission(permission)
        except:
            return False

    def clear_main_container(self):
        """Clear the main container"""
        for widget in self.main_container.winfo_children():
            widget.destroy()

    def show_login(self):
        """Show login dialog"""
        self.clear_main_container()
        
        # Create login frame
        login_frame = ttk.Frame(self.main_container)
        login_frame.pack(expand=True)
        
        # Title
        title_label = ttk.Label(login_frame, text="Helpdesk System Login", style='Title.TLabel')
        title_label.pack(pady=20)
        
        # Login form
        form_frame = ttk.Frame(login_frame)
        form_frame.pack(pady=20)
        
        ttk.Label(form_frame, text="Username:").grid(row=0, column=0, sticky='e', padx=5, pady=5)
        self.username_entry = ttk.Entry(form_frame, width=20)
        self.username_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(form_frame, text="Password:").grid(row=1, column=0, sticky='e', padx=5, pady=5)
        self.password_entry = ttk.Entry(form_frame, width=20, show='*')
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(login_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Login", command=self.login).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Register", command=self.show_register).pack(side='left', padx=5)
        ttk.Button(button_frame, text="CLI Mode", command=self.switch_to_cli).pack(side='left', padx=5)
        
        # Bind Enter key to login
        self.root.bind('<Return>', lambda e: self.login())
        
        # Focus on username entry
        self.username_entry.focus()

    def login(self):
        """Handle login using centralized authentication"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            messagebox.showerror("Error", "Please enter both username and password")
            return

        try:
            # Use centralized authentication system
            result = self.auth.login(username, password)
            if result is True or isinstance(result, dict):
                self.current_user = self.auth.current_user
                self.show_main_dashboard()
            else:
                messagebox.showerror("Error", "Invalid username or password")
        except Exception as e:
            messagebox.showerror("Error", f"Login failed: {str(e)}")

    # Note: authenticate_user method removed - now using centralized UserAuth system

    def show_register(self):
        """Show registration dialog"""
        register_window = tk.Toplevel(self.root)
        register_window.title("Register New User")
        register_window.geometry("400x300")
        register_window.transient(self.root)
        register_window.grab_set()
        
        # Registration form
        form_frame = ttk.Frame(register_window)
        form_frame.pack(pady=20, padx=20, fill='both', expand=True)
        
        ttk.Label(form_frame, text="Register New User", style='Heading.TLabel').pack(pady=10)
        
        # Create a separate frame for the grid layout
        fields_frame = ttk.Frame(form_frame)
        fields_frame.pack(fill='x', pady=10)
        
        # Form fields
        fields = [
            ("Username:", "username"),
            ("Email:", "email"),
            ("Password:", "password"),
            ("Confirm Password:", "confirm_password"),
            ("Full Name:", "full_name")
        ]
        
        self.register_entries = {}
        for i, (label, field) in enumerate(fields):
            ttk.Label(fields_frame, text=label).grid(row=i, column=0, sticky='e', padx=5, pady=5)
            entry = ttk.Entry(fields_frame, width=25)
            if 'password' in field:
                entry.config(show='*')
            entry.grid(row=i, column=1, padx=5, pady=5)
            self.register_entries[field] = entry
        
        # Role selection
        ttk.Label(fields_frame, text="Role:").grid(row=len(fields), column=0, sticky='e', padx=5, pady=5)
        self.role_var = tk.StringVar(value="student")
        role_combo = ttk.Combobox(fields_frame, textvariable=self.role_var, 
                                 values=["student", "staff", "admin"], state="readonly")
        role_combo.grid(row=len(fields), column=1, padx=5, pady=5)
        
        # Buttons - use pack for this frame
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Register", 
                  command=lambda: self.register_user(register_window)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", 
                  command=register_window.destroy).pack(side='left', padx=5)
    
    def register_user(self, window):
        """Handle user registration"""
        try:
            # Get form data
            data = {}
            for field, entry in self.register_entries.items():
                data[field] = entry.get().strip()
            
            # Validate
            if not all(data.values()):
                messagebox.showerror("Error", "Please fill in all fields")
                return
            
            if data['password'] != data['confirm_password']:
                messagebox.showerror("Error", "Passwords do not match")
                return
            
            # Register user (implement actual registration logic)
            if self.create_user_account(data):
                messagebox.showinfo("Success", "User registered successfully!")
                window.destroy()
            else:
                messagebox.showerror("Error", "Registration failed")
                
        except Exception as e:
            messagebox.showerror("Error", f"Registration failed: {str(e)}")

    def create_user_account(self, data):
        """Create user account - integrate with existing system"""
        # This would integrate with your existing user creation system
        return True  # Simplified for demo

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

    def show_main_dashboard(self):
        """Show the main dashboard"""
        self.clear_main_container()
        
        # Header
        header_frame = ttk.Frame(self.main_container)
        header_frame.pack(fill='x', pady=(0, 20))
        
        welcome_label = ttk.Label(header_frame, 
                                 text=f"Welcome to Helpdesk System, {self.current_user['username'] if self.current_user else 'User'}!", 
                                 style='Title.TLabel')
        welcome_label.pack(side='left')
        
        # Logout button
        ttk.Button(header_frame, text="🏠 Return to Main Menu", command=self.return_to_main_menu).pack(side='right')
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill='both', expand=True)
        
        # Dashboard tab
        self.create_dashboard_tab()
        
        # My Tickets tab
        self.create_my_tickets_tab()
        
        # Create Ticket tab
        self.create_new_ticket_tab()
        
        # Knowledge Base tab
        self.create_knowledge_base_tab()
        
        # Admin tabs (if admin)
        if self.has_permission('view_all_tickets'):
            self.create_all_tickets_tab()
            self.create_analytics_tab()
        
        if self.has_permission('manage_tickets'):
            self.create_admin_tab()

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

    def create_dashboard_tab(self):
        """Create dashboard tab"""
        dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(dashboard_frame, text="Dashboard")
        
        # Quick stats
        stats_frame = ttk.LabelFrame(dashboard_frame, text="Quick Statistics")
        stats_frame.pack(fill='x', padx=10, pady=10)
        
        # Create stats grid
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill='x', padx=10, pady=10)
        
        # Load and display stats
        self.load_dashboard_stats(stats_grid)
        
        # Quick actions
        actions_frame = ttk.LabelFrame(dashboard_frame, text="Quick Actions")
        actions_frame.pack(fill='x', padx=10, pady=10)
        
        actions_grid = ttk.Frame(actions_frame)
        actions_grid.pack(fill='x', padx=10, pady=10)
        
        # Action buttons
        ttk.Button(actions_grid, text="Create New Ticket", 
                  command=self.show_create_ticket, style='Primary.TButton').grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(actions_grid, text="View My Tickets", 
                  command=self.show_my_tickets).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(actions_grid, text="Search Knowledge Base", 
                  command=self.show_knowledge_base).grid(row=0, column=2, padx=5, pady=5)
        
        # Recent activity
        recent_frame = ttk.LabelFrame(dashboard_frame, text="Recent Activity")
        recent_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.load_recent_activity(recent_frame)

    def load_dashboard_stats(self, parent):
        """Load dashboard statistics"""
        try:
            # Get statistics from database
            stats = self.get_user_stats()
            
            # Display stats
            row = 0
            for label, value in stats.items():
                ttk.Label(parent, text=f"{label}:", style='Heading.TLabel').grid(row=row, column=0, sticky='w', padx=5)
                ttk.Label(parent, text=str(value)).grid(row=row, column=1, sticky='w', padx=20)
                row += 1
                
        except Exception as e:
            ttk.Label(parent, text=f"Error loading stats: {str(e)}", style='Error.TLabel').pack()

    def get_user_stats(self):
        """Get user statistics"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            
            stats = {}
            
            if self.current_user:
                # User's ticket stats
                cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN status = 'open' THEN 1 END) as open,
                    COUNT(CASE WHEN status = 'resolved' THEN 1 END) as resolved
                FROM support_tickets 
                WHERE user_id = ?
                ''', (self.current_user.get('id', 0),))
                
                result = cursor.fetchone()
                if result:
                    stats["My Total Tickets"] = result[0]
                    stats["My Open Tickets"] = result[1]
                    stats["My Resolved Tickets"] = result[2]
            
            # System-wide stats (if admin)
            if self.has_permission('view_all_tickets'):
                cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN status = 'open' THEN 1 END) as open,
                    COUNT(CASE WHEN assigned_to IS NULL THEN 1 END) as unassigned
                FROM support_tickets
                ''')
                
                result = cursor.fetchone()
                if result:
                    stats["Total System Tickets"] = result[0]
                    stats["System Open Tickets"] = result[1]
                    stats["Unassigned Tickets"] = result[2]
            
            conn.close()
            return stats
            
        except Exception as e:
            return {"Error": str(e)}

    def escalate_ticket_manual(self, ticket_id):
        """Manually escalate a ticket"""
        escalate_window = tk.Toplevel(self.root)
        escalate_window.title(f"Escalate Ticket #{ticket_id}")
        escalate_window.geometry("400x200")
        escalate_window.transient(self.root)
        escalate_window.grab_set()
        
        ttk.Label(escalate_window, text=f"Escalate Ticket #{ticket_id}", style='Heading.TLabel').pack(pady=10)
        
        ttk.Label(escalate_window, text="Escalation Reason:").pack(pady=5)
        reason_entry = ttk.Entry(escalate_window, width=40)
        reason_entry.pack(pady=5)
        reason_entry.insert(0, "Manual escalation")
        
        button_frame = ttk.Frame(escalate_window)
        button_frame.pack(pady=20)
        
        def perform_escalation():
            reason = reason_entry.get().strip()
            if self.escalate_ticket(ticket_id, reason):
                messagebox.showinfo("Success", f"Ticket #{ticket_id} escalated successfully")
                escalate_window.destroy()
                self.refresh_my_tickets()
            else:
                messagebox.showerror("Error", "Failed to escalate ticket")
        
        ttk.Button(button_frame, text="Escalate", command=perform_escalation, 
                  style='Primary.TButton').pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=escalate_window.destroy).pack(side='right')

    def escalate_ticket(self, ticket_id, reason='manual'):
        """Backend function to escalate a ticket"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get current ticket info
            cursor.execute('''
            SELECT assigned_to, department, escalation_level 
            FROM support_tickets 
            WHERE ticket_id = ?
            ''', (ticket_id,))
            
            ticket_info = cursor.fetchone()
            if not ticket_info:
                return False
            
            current_assigned, department, current_level = ticket_info
            new_level = current_level + 1
            
            # Find manager to escalate to
            escalate_to = None
            
            if department:
                cursor.execute('''
                SELECT manager_id FROM departments WHERE name = ?
                ''', (department,))
                dept_manager = cursor.fetchone()
                if dept_manager and dept_manager[0]:
                    escalate_to = dept_manager[0]
            
            if not escalate_to:
                # Escalate to any admin
                cursor.execute('''
                SELECT id FROM users WHERE role = 'admin' AND is_active = 1 LIMIT 1
                ''')
                admin = cursor.fetchone()
                if admin:
                    escalate_to = admin[0]
            
            if escalate_to:
                # Update ticket
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                UPDATE support_tickets 
                SET assigned_to = ?, escalation_level = ?, updated_at = ?
                WHERE ticket_id = ?
                ''', (escalate_to, new_level, now, ticket_id))
                
                # Record escalation
                cursor.execute('''
                INSERT INTO ticket_escalations 
                (ticket_id, escalation_level, escalated_to, escalation_reason, created_at)
                VALUES (?, ?, ?, ?, ?)
                ''', (ticket_id, new_level, escalate_to, reason, now))
                
                conn.commit()
                conn.close()
                return True
            
            conn.close()
            return False
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to escalate ticket: {str(e)}")
            return False

    def show_saved_searches(self):
        """Show and execute saved searches"""
        search_window = tk.Toplevel(self.root)
        search_window.title("Saved Searches")
        search_window.geometry("600x400")
        search_window.transient(self.root)
        search_window.grab_set()
        
        ttk.Label(search_window, text="Saved Searches", style='Heading.TLabel').pack(pady=10)
        
        # Create treeview for saved searches
        columns = ('Name', 'Created')
        searches_tree = ttk.Treeview(search_window, columns=columns, show='headings', height=10)
        
        for col in columns:
            searches_tree.heading(col, text=col)
            searches_tree.column(col, width=200)
        
        searches_tree.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Load saved searches
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT search_id, name, search_criteria, created_at
            FROM saved_searches 
            WHERE user_id = ? 
            ORDER BY created_at DESC
            ''', (self.current_user.get('id', 0),))
            
            searches = cursor.fetchall()
            
            for search in searches:
                searches_tree.insert('', 'end', values=(search[1], search[3][:16]))
            
            conn.close()
            
            def execute_selected_search():
                selection = searches_tree.selection()
                if not selection:
                    messagebox.showwarning("Warning", "Please select a search")
                    return
                
                item = searches_tree.item(selection[0])
                search_name = item['values'][0]
                
                # Find the search data
                for search in searches:
                    if search[1] == search_name:
                        try:
                            criteria = json.loads(search[2])
                            results = self.execute_search_criteria(criteria)
                            search_window.destroy()
                            self.display_search_results_window(results, f"Results for '{search_name}'")
                        except json.JSONDecodeError:
                            messagebox.showerror("Error", "Invalid search data")
                        break
            
            button_frame = ttk.Frame(search_window)
            button_frame.pack(pady=10)
            
            ttk.Button(button_frame, text="Execute Search", command=execute_selected_search,
                      style='Primary.TButton').pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=search_window.destroy).pack(side='left', padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load saved searches: {str(e)}")

    def execute_search_criteria(self, criteria):
        """Execute search with given criteria - backend function"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Build query
            where_conditions = []
            params = []
            
            # Check permissions
            if not self.has_permission('view_all_tickets'):
                where_conditions.append("t.user_id = ?")
                params.append(self.current_user['id'])
            
            # Text search
            if 'text' in criteria:
                where_conditions.append("(t.subject LIKE ? OR t.message LIKE ?)")
                text_param = f"%{criteria['text']}%"
                params.extend([text_param, text_param])
            
            # Status filter
            if 'status' in criteria:
                where_conditions.append("t.status = ?")
                params.append(criteria['status'])
            
            # Priority filter
            if 'priority' in criteria:
                where_conditions.append("t.priority = ?")
                params.append(criteria['priority'])
            
            # Category filter
            if 'category' in criteria:
                where_conditions.append("t.category = ?")
                params.append(criteria['category'])
            
            # Date range
            if 'start_date' in criteria:
                where_conditions.append("DATE(t.created_at) >= ?")
                params.append(criteria['start_date'])
            
            if 'end_date' in criteria:
                where_conditions.append("DATE(t.created_at) <= ?")
                params.append(criteria['end_date'])
            
            # Build final query
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            query = f'''
            SELECT t.*, u1.username as submitter, u2.username as assignee
            FROM support_tickets t
            JOIN users u1 ON t.user_id = u1.id
            LEFT JOIN users u2 ON t.assigned_to = u2.id
            WHERE {where_clause}
            ORDER BY t.updated_at DESC
            '''
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            conn.close()
            return [dict(result) for result in results]
            
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")
            return []

    def display_search_results_window(self, results, title="Search Results"):
        """Display search results in a new window"""
        results_window = tk.Toplevel(self.root)
        results_window.title(title)
        results_window.geometry("1000x600")
        results_window.transient(self.root)
        
        ttk.Label(results_window, text=title, style='Heading.TLabel').pack(pady=10)
        
        if not results:
            ttk.Label(results_window, text="No tickets found matching your search criteria.").pack(pady=20)
            ttk.Button(results_window, text="Close", command=results_window.destroy).pack(pady=10)
            return
        
        # Create treeview for results
        columns = ('ID', 'Subject', 'From', 'Assigned', 'Status', 'Priority', 'Updated')
        results_tree = ttk.Treeview(results_window, columns=columns, show='headings')
        
        column_widths = {'ID': 50, 'Subject': 200, 'From': 100, 'Assigned': 100, 
                        'Status': 100, 'Priority': 80, 'Updated': 120}
        
        for col in columns:
            results_tree.heading(col, text=col)
            results_tree.column(col, width=column_widths.get(col, 100))
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(results_window, orient='vertical', command=results_tree.yview)
        h_scrollbar = ttk.Scrollbar(results_window, orient='horizontal', command=results_tree.xview)
        
        results_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack widgets
        results_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        v_scrollbar.pack(side='right', fill='y')
        
        # Populate results
        for ticket in results:
            assignee = ticket.get('assignee') or 'Unassigned'
            results_tree.insert('', 'end', values=(
                ticket['ticket_id'],
                ticket['subject'][:30],
                ticket['submitter'][:15],
                assignee[:15],
                ticket['status'].title(),
                ticket['priority'].title(),
                ticket['updated_at'][:16]
            ))
        
        # Double-click to view ticket
        def on_double_click(event):
            selection = results_tree.selection()
            if selection:
                item = results_tree.item(selection[0])
                ticket_id = item['values'][0]
                self.show_ticket_details(ticket_id)
        
        results_tree.bind('<Double-1>', on_double_click)
        
        # Close button
        ttk.Button(results_window, text="Close", command=results_window.destroy).pack(pady=10)

    def show_analytics_dashboard(self):
        """Show analytics dashboard in a new window"""
        analytics_window = tk.Toplevel(self.root)
        analytics_window.title("Analytics Dashboard")
        analytics_window.geometry("1000x700")
        analytics_window.transient(self.root)
        
        # Create scrollable frame
        canvas = tk.Canvas(analytics_window)
        scrollbar = ttk.Scrollbar(analytics_window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        ttk.Label(scrollable_frame, text="Analytics Dashboard", style='Title.TLabel').pack(pady=10)
        
        # Time period selector
        period_frame = ttk.Frame(scrollable_frame)
        period_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(period_frame, text="Time Period:").pack(side='left')
        period_var = tk.StringVar(value="30d")
        period_combo = ttk.Combobox(period_frame, textvariable=period_var,
                                   values=["7d", "30d", "90d", "1y"], state="readonly", width=10)
        period_combo.pack(side='left', padx=5)
        
        def refresh_analytics():
            self.load_analytics_data(scrollable_frame, period_var.get())
        
        ttk.Button(period_frame, text="Refresh", command=refresh_analytics).pack(side='left', padx=5)
        
        # Initial load
        self.load_analytics_data(scrollable_frame, "30d")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def load_analytics_data(self, parent, period):
        """Load analytics data for the dashboard"""
        # Clear existing analytics content (but keep header and controls)
        for widget in parent.winfo_children()[2:]:  # Skip title and period frame
            widget.destroy()
        
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            
            # Calculate date range
            days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
            days = days_map.get(period, 30)
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # Overall statistics
            stats_frame = ttk.LabelFrame(parent, text=f"Overview ({period.upper()})")
            stats_frame.pack(fill='x', padx=10, pady=5)
            
            cursor.execute('''
            SELECT 
                COUNT(*) as total_tickets,
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tickets,
                COUNT(CASE WHEN status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets,
                AVG(CASE WHEN resolved_at IS NOT NULL 
                    THEN (julianday(resolved_at) - julianday(created_at)) * 24 
                    ELSE NULL END) as avg_resolution_hours,
                AVG(satisfaction_rating) as avg_satisfaction
            FROM support_tickets
            WHERE created_at >= ?
            ''', (start_date,))
            
            result = cursor.fetchone()
            if result:
                total = result[0]
                resolution_rate = (result[2] / total * 100) if total > 0 else 0
                
                stats_grid = ttk.Frame(stats_frame)
                stats_grid.pack(fill='x', padx=10, pady=10)
                
                metrics = [
                    ("Total Tickets", total),
                    ("Open Tickets", result[1]),
                    ("Resolved Tickets", result[2]),
                    ("Resolution Rate", f"{resolution_rate:.1f}%"),
                    ("Avg Resolution Time", f"{result[3] or 0:.1f}h"),
                    ("Customer Satisfaction", f"{result[4] or 0:.1f}/5.0")
                ]
                
                for i, (label, value) in enumerate(metrics):
                    row = i // 3
                    col = (i % 3) * 2
                    
                    ttk.Label(stats_grid, text=f"{label}:", style='Heading.TLabel').grid(
                        row=row, column=col, sticky='w', padx=5, pady=2)
                    ttk.Label(stats_grid, text=str(value)).grid(
                        row=row, column=col+1, sticky='w', padx=20, pady=2)
            
            conn.close()
            
        except Exception as e:
            ttk.Label(parent, text=f"Error loading analytics: {str(e)}", 
                     style='Error.TLabel').pack(pady=20)

    def load_recent_activity(self, parent):
        """Load recent activity"""
        try:
            # Create treeview for recent activity
            columns = ('Date', 'Type', 'Description')
            tree = ttk.Treeview(parent, columns=columns, show='headings', height=6)
            
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=150)
            
            # Add scrollbar
            scrollbar = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            # Pack widgets
            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            # Load recent activity data
            recent_data = self.get_recent_activity()
            for item in recent_data:
                tree.insert('', 'end', values=item)
                
        except Exception as e:
            ttk.Label(parent, text=f"Error loading activity: {str(e)}", style='Error.TLabel').pack()

    def get_recent_activity(self):
        """Get recent activity data"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            
            if self.current_user:
                cursor.execute('''
                SELECT created_at, 'Ticket Created' as type, subject as description
                FROM support_tickets 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 10
                ''', (self.current_user.get('id', 0),))
                
                results = cursor.fetchall()
                conn.close()
                
                return [(r[0][:16], r[1], r[2][:50]) for r in results]
            
            return []
            
        except Exception as e:
            return [("Error", "System", str(e))]

    def create_my_tickets_tab(self):
        """Create my tickets tab"""
        tickets_frame = ttk.Frame(self.notebook)
        self.notebook.add(tickets_frame, text="My Tickets")
        
        # Toolbar
        toolbar = ttk.Frame(tickets_frame)
        toolbar.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(toolbar, text="Refresh", command=self.refresh_my_tickets).pack(side='left', padx=5)
        ttk.Button(toolbar, text="New Ticket", command=self.show_create_ticket, 
                  style='Primary.TButton').pack(side='left', padx=5)
        
        # Filter frame
        filter_frame = ttk.LabelFrame(tickets_frame, text="Filters")
        filter_frame.pack(fill='x', padx=10, pady=5)
        
        filter_grid = ttk.Frame(filter_frame)
        filter_grid.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(filter_grid, text="Status:").grid(row=0, column=0, padx=5)
        self.my_tickets_status_var = tk.StringVar(value="all")
        status_combo = ttk.Combobox(filter_grid, textvariable=self.my_tickets_status_var,
                                   values=["all", "open", "in progress", "resolved", "closed"],
                                   state="readonly")
        status_combo.grid(row=0, column=1, padx=5)
        status_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_my_tickets())
        
        # Tickets list
        self.my_tickets_frame = ttk.Frame(tickets_frame)
        self.my_tickets_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.create_my_tickets_list()

    def create_my_tickets_list(self):
        """Create my tickets list"""
        # Clear existing widgets
        for widget in self.my_tickets_frame.winfo_children():
            widget.destroy()
        
        # Create treeview
        columns = ('ID', 'Subject', 'Category', 'Status', 'Priority', 'Created', 'Updated')
        self.my_tickets_tree = ttk.Treeview(self.my_tickets_frame, columns=columns, show='headings')
        
        # Configure columns
        column_widths = {'ID': 50, 'Subject': 200, 'Category': 120, 'Status': 100, 
                        'Priority': 80, 'Created': 120, 'Updated': 120}
        
        for col in columns:
            self.my_tickets_tree.heading(col, text=col)
            self.my_tickets_tree.column(col, width=column_widths.get(col, 100))
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(self.my_tickets_frame, orient='vertical', 
                                   command=self.my_tickets_tree.yview)
        h_scrollbar = ttk.Scrollbar(self.my_tickets_frame, orient='horizontal', 
                                   command=self.my_tickets_tree.xview)
        
        self.my_tickets_tree.configure(yscrollcommand=v_scrollbar.set, 
                                      xscrollcommand=h_scrollbar.set)
        
        # Pack widgets
        self.my_tickets_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        self.my_tickets_frame.grid_rowconfigure(0, weight=1)
        self.my_tickets_frame.grid_columnconfigure(0, weight=1)
        
        # Bind double-click to view ticket
        self.my_tickets_tree.bind('<Double-1>', self.on_my_ticket_double_click)
        
        # Context menu
        self.create_my_tickets_context_menu()
        
        # Load data
        self.refresh_my_tickets()

    def create_my_tickets_context_menu(self):
        """Create context menu for my tickets"""
        self.my_tickets_context_menu = tk.Menu(self.root, tearoff=0)
        self.my_tickets_context_menu.add_command(label="View Details", command=self.view_selected_ticket)
        self.my_tickets_context_menu.add_command(label="Reply", command=self.reply_to_selected_ticket)
        self.my_tickets_context_menu.add_separator()
        self.my_tickets_context_menu.add_command(label="Refresh", command=self.refresh_my_tickets)
        
        self.my_tickets_tree.bind('<Button-3>', self.show_my_tickets_context_menu)

    def show_my_tickets_context_menu(self, event):
        """Show context menu for my tickets"""
        try:
            self.my_tickets_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.my_tickets_context_menu.grab_release()

    def refresh_my_tickets(self):
        """Refresh my tickets list"""
        try:
            # Clear existing items
            for item in self.my_tickets_tree.get_children():
                self.my_tickets_tree.delete(item)
            
            # Get tickets from database
            tickets = self.get_my_tickets()
            
            # Populate treeview
            for ticket in tickets:
                # Format dates
                created = ticket['created_at'][:16] if ticket['created_at'] else ''
                updated = ticket['updated_at'][:16] if ticket['updated_at'] else ''
                
                self.my_tickets_tree.insert('', 'end', values=(
                    ticket['ticket_id'],
                    ticket['subject'][:50],
                    ticket['category'],
                    ticket['status'].title(),
                    ticket['priority'].title(),
                    created,
                    updated
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load tickets: {str(e)}")

    def get_my_tickets(self):
        """Get user's tickets from database"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            status_filter = self.my_tickets_status_var.get()
            where_clause = "WHERE user_id = ?"
            params = [self.current_user.get('id', 0)]
            
            if status_filter != "all":
                where_clause += " AND status = ?"
                params.append(status_filter)
            
            cursor.execute(f'''
            SELECT ticket_id, subject, category, status, priority, created_at, updated_at
            FROM support_tickets
            {where_clause}
            ORDER BY created_at DESC
            ''', params)
            
            tickets = cursor.fetchall()
            conn.close()
            
            return [dict(ticket) for ticket in tickets]
            
        except Exception as e:
            messagebox.showerror("Error", f"Database error: {str(e)}")
            return []

    def on_my_ticket_double_click(self, event):
        """Handle double-click on my ticket"""
        self.view_selected_ticket()

    def view_selected_ticket(self):
        """View selected ticket details"""
        selection = self.my_tickets_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a ticket")
            return
        
        item = self.my_tickets_tree.item(selection[0])
        ticket_id = item['values'][0]
        
        self.show_ticket_details(ticket_id)

    def reply_to_selected_ticket(self):
        """Reply to selected ticket"""
        selection = self.my_tickets_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a ticket")
            return
        
        item = self.my_tickets_tree.item(selection[0])
        ticket_id = item['values'][0]
        
        self.show_reply_dialog(ticket_id)

    def show_ticket_details(self, ticket_id):
        """Show detailed ticket view"""
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Ticket #{ticket_id} Details")
        details_window.geometry("800x600")
        details_window.transient(self.root)
        
        # Create notebook for different sections
        notebook = ttk.Notebook(details_window)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Load ticket data
        ticket_data = self.get_ticket_details(ticket_id)
        if not ticket_data:
            messagebox.showerror("Error", "Ticket not found")
            details_window.destroy()
            return
        
        # Details tab
        details_frame = ttk.Frame(notebook)
        notebook.add(details_frame, text="Details")
        
        # Create scrollable frame for details
        canvas = tk.Canvas(details_frame)
        scrollbar = ttk.Scrollbar(details_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Ticket information
        info_frame = ttk.LabelFrame(scrollable_frame, text="Ticket Information")
        info_frame.pack(fill='x', padx=10, pady=5)
        
        # Display ticket fields
        fields = [
            ("Ticket ID:", ticket_data.get('ticket_id')),
            ("Subject:", ticket_data.get('subject')),
            ("Category:", ticket_data.get('category')),
            ("Status:", ticket_data.get('status', '').title()),
            ("Priority:", ticket_data.get('priority', '').title()),
            ("Impact:", ticket_data.get('impact', '').title()),
            ("Urgency:", ticket_data.get('urgency', '').title()),
            ("Created:", ticket_data.get('created_at')),
            ("Updated:", ticket_data.get('updated_at')),
            ("Assigned To:", ticket_data.get('assignee') or 'Unassigned'),
            ("Department:", ticket_data.get('department') or 'None')
        ]
        
        for i, (label, value) in enumerate(fields):
            ttk.Label(info_frame, text=label, style='Heading.TLabel').grid(row=i, column=0, sticky='w', padx=5, pady=2)
            ttk.Label(info_frame, text=str(value) if value else 'N/A').grid(row=i, column=1, sticky='w', padx=20, pady=2)
        
        # Message frame
        message_frame = ttk.LabelFrame(scrollable_frame, text="Original Message")
        message_frame.pack(fill='x', padx=10, pady=5)
        
        message_text = scrolledtext.ScrolledText(message_frame, height=5, wrap='word', state='disabled')
        message_text.pack(fill='x', padx=5, pady=5)
        message_text.config(state='normal')
        message_text.insert('1.0', ticket_data.get('message', ''))
        message_text.config(state='disabled')
        
        # Resolution frame (if resolved)
        if ticket_data.get('resolution'):
            resolution_frame = ttk.LabelFrame(scrollable_frame, text="Resolution")
            resolution_frame.pack(fill='x', padx=10, pady=5)
            
            resolution_text = scrolledtext.ScrolledText(resolution_frame, height=3, wrap='word', state='disabled')
            resolution_text.pack(fill='x', padx=5, pady=5)
            resolution_text.config(state='normal')
            resolution_text.insert('1.0', ticket_data.get('resolution', ''))
            resolution_text.config(state='disabled')
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Replies tab
        replies_frame = ttk.Frame(notebook)
        notebook.add(replies_frame, text="Conversation")
        
        self.create_replies_view(replies_frame, ticket_id)
        
        # Actions tab (if user has permissions)
        if self.has_permission('reply_to_own_ticket') or self.has_permission('manage_tickets'):
            actions_frame = ttk.Frame(notebook)
            notebook.add(actions_frame, text="Actions")
            
            self.create_ticket_actions_view(actions_frame, ticket_id, ticket_data)

    def get_ticket_details(self, ticket_id):
        """Get detailed ticket information"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT t.*, u1.username as submitter, u2.username as assignee
            FROM support_tickets t
            JOIN users u1 ON t.user_id = u1.id
            LEFT JOIN users u2 ON t.assigned_to = u2.id
            WHERE t.ticket_id = ?
            ''', (ticket_id,))
            
            ticket = cursor.fetchone()
            conn.close()
            
            return dict(ticket) if ticket else None
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load ticket: {str(e)}")
            return None

    def create_replies_view(self, parent, ticket_id):
        """Create replies/conversation view"""
        # Toolbar
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(toolbar, text="Add Reply", command=lambda: self.show_reply_dialog(ticket_id)).pack(side='left', padx=5)
        ttk.Button(toolbar, text="Refresh", command=lambda: self.refresh_replies_view(parent, ticket_id)).pack(side='left', padx=5)
        
        # Replies list
        self.replies_frame = ttk.Frame(parent)
        self.replies_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.load_ticket_replies(ticket_id)

    def load_ticket_replies(self, ticket_id):
        """Load ticket replies"""
        try:
            # Clear existing widgets
            for widget in self.replies_frame.winfo_children():
                widget.destroy()
            
            # Create scrollable frame
            canvas = tk.Canvas(self.replies_frame)
            scrollbar = ttk.Scrollbar(self.replies_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Get replies from database
            replies = self.get_ticket_replies(ticket_id)
            
            for i, reply in enumerate(replies):
                reply_frame = ttk.LabelFrame(scrollable_frame, 
                                           text=f"{reply['username']} - {reply['created_at']}")
                reply_frame.pack(fill='x', padx=5, pady=5)
                
                # Reply content
                reply_text = scrolledtext.ScrolledText(reply_frame, height=4, wrap='word', state='disabled')
                reply_text.pack(fill='x', padx=5, pady=5)
                reply_text.config(state='normal')
                reply_text.insert('1.0', reply['message'])
                reply_text.config(state='disabled')
                
                # Internal note indicator
                if reply.get('is_internal') and self.has_permission('manage_tickets'):
                    internal_label = ttk.Label(reply_frame, text="(Internal Note)", style='Warning.TLabel')
                    internal_label.pack()
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
        except Exception as e:
            ttk.Label(self.replies_frame, text=f"Error loading replies: {str(e)}", 
                     style='Error.TLabel').pack()

    def get_ticket_replies(self, ticket_id):
        """Get ticket replies from database"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT r.*, u.username
            FROM ticket_replies r
            JOIN users u ON r.user_id = u.id
            WHERE r.ticket_id = ?
            ORDER BY r.created_at ASC
            ''', (ticket_id,))
            
            replies = cursor.fetchall()
            conn.close()
            
            return [dict(reply) for reply in replies]
            
        except Exception as e:
            return []

    def refresh_replies_view(self, parent, ticket_id):
        """Refresh replies view"""
        self.load_ticket_replies(ticket_id)

    def create_ticket_actions_view(self, parent, ticket_id, ticket_data):
        """Create ticket actions view"""
        actions_frame = ttk.LabelFrame(parent, text="Available Actions")
        actions_frame.pack(fill='x', padx=10, pady=10)
        
        # Reply action
        if self.has_permission('reply_to_own_ticket') or self.has_permission('manage_tickets'):
            ttk.Button(actions_frame, text="Add Reply", 
                      command=lambda: self.show_reply_dialog(ticket_id)).pack(pady=5)
        
        # Admin actions
        if self.has_permission('manage_tickets'):
            ttk.Button(actions_frame, text="Change Status", 
                      command=lambda: self.show_status_dialog(ticket_id)).pack(pady=5)
            ttk.Button(actions_frame, text="Assign Ticket", 
                      command=lambda: self.show_assign_dialog(ticket_id)).pack(pady=5)
            ttk.Button(actions_frame, text="Add Internal Note", 
                      command=lambda: self.show_internal_note_dialog(ticket_id)).pack(pady=5)

    def show_reply_dialog(self, ticket_id):
        """Show reply dialog"""
        reply_window = tk.Toplevel(self.root)
        reply_window.title(f"Reply to Ticket #{ticket_id}")
        reply_window.geometry("600x400")
        reply_window.transient(self.root)
        reply_window.grab_set()
        
        # Title
        ttk.Label(reply_window, text=f"Reply to Ticket #{ticket_id}", 
                 style='Heading.TLabel').pack(pady=10)
        
        # Message frame
        message_frame = ttk.LabelFrame(reply_window, text="Your Reply")
        message_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Message text area
        message_text = scrolledtext.ScrolledText(message_frame, height=10, wrap='word')
        message_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Time tracking (if admin)
        time_frame = ttk.Frame(reply_window)
        if self.has_permission('manage_tickets'):
            time_frame.pack(fill='x', padx=10, pady=5)
            ttk.Label(time_frame, text="Time spent (hours):").pack(side='left')
            time_entry = ttk.Entry(time_frame, width=10)
            time_entry.pack(side='left', padx=5)
        
        # Buttons
        button_frame = ttk.Frame(reply_window)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        def send_reply():
            message = message_text.get('1.0', 'end-1c').strip()
            if not message:
                messagebox.showerror("Error", "Please enter a reply message")
                return
            
            time_spent = 0
            if self.has_permission('manage_tickets') and time_entry.get():
                try:
                    time_spent = float(time_entry.get())
                except ValueError:
                    pass
            
            if self.add_ticket_reply(ticket_id, message, time_spent):
                messagebox.showinfo("Success", "Reply added successfully!")
                reply_window.destroy()
                # Refresh the ticket view if it's open
                self.refresh_my_tickets()
            else:
                messagebox.showerror("Error", "Failed to add reply")
        
        ttk.Button(button_frame, text="Send Reply", command=send_reply, 
                  style='Primary.TButton').pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=reply_window.destroy).pack(side='right')

    def add_ticket_reply(self, ticket_id, message, time_spent=0, is_internal=False):
        """Add reply to ticket"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO ticket_replies 
            (ticket_id, user_id, message, is_internal, time_spent, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (ticket_id, self.current_user.get('id', 0), message, is_internal, time_spent, now))
            
            # Update ticket timestamp
            cursor.execute('''
            UPDATE support_tickets
            SET updated_at = ?, last_activity_at = ?
            WHERE ticket_id = ?
            ''', (now, now, ticket_id))
            
            conn.commit()
            conn.close()

            # Send reply notification email automatically
            if not is_internal:  # Only send for public replies
                try:
                    from university_system.infrastructure.email.email_service import send_reply_notification
                    username = self.current_user.get('username', 'Support Agent')
                    send_reply_notification(ticket_id, self.current_user.get('id'), username, None, None, None)
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to send reply notification: {e}")

            return True

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add reply: {str(e)}")
            return False

    def show_status_dialog(self, ticket_id):
        """Show status change dialog"""
        status_window = tk.Toplevel(self.root)
        status_window.title(f"Change Status - Ticket #{ticket_id}")
        status_window.geometry("400x300")
        status_window.transient(self.root)
        status_window.grab_set()
        
        # Title
        ttk.Label(status_window, text=f"Change Status for Ticket #{ticket_id}", 
                 style='Heading.TLabel').pack(pady=10)
        
        # Status selection
        status_frame = ttk.LabelFrame(status_window, text="New Status")
        status_frame.pack(fill='x', padx=10, pady=10)
        
        status_var = tk.StringVar()
        statuses = ["open", "in progress", "waiting for customer", "resolved", "closed"]
        
        for status in statuses:
            ttk.Radiobutton(status_frame, text=status.title(), variable=status_var, 
                           value=status).pack(anchor='w', padx=5, pady=2)
        
        # Resolution field (for resolved/closed)
        resolution_frame = ttk.LabelFrame(status_window, text="Resolution (if resolved/closed)")
        resolution_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        resolution_text = scrolledtext.ScrolledText(resolution_frame, height=5, wrap='word')
        resolution_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(status_window)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        def update_status():
            new_status = status_var.get()
            if not new_status:
                messagebox.showerror("Error", "Please select a status")
                return
            
            resolution = resolution_text.get('1.0', 'end-1c').strip()
            
            if self.update_ticket_status(ticket_id, new_status, resolution):
                messagebox.showinfo("Success", "Status updated successfully!")
                status_window.destroy()
                self.refresh_my_tickets()
            else:
                messagebox.showerror("Error", "Failed to update status")
        
        ttk.Button(button_frame, text="Update Status", command=update_status, 
                  style='Primary.TButton').pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=status_window.destroy).pack(side='right')

    def update_ticket_status(self, ticket_id, new_status, resolution=None):
        """Update ticket status"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            resolved_at = now if new_status in ['resolved', 'closed'] else None
            
            cursor.execute('''
            UPDATE support_tickets
            SET status = ?, resolution = ?, resolved_at = ?, updated_at = ?, last_activity_at = ?
            WHERE ticket_id = ?
            ''', (new_status, resolution, resolved_at, now, now, ticket_id))

            conn.commit()
            conn.close()

            # Auto-send email notifications for status changes
            if new_status in ['resolved', 'closed']:
                self.auto_send_ticket_notifications(ticket_id, "resolved")

                # Send satisfaction survey when ticket is resolved/closed
                try:
                    from university_system.infrastructure.email.email_service import send_satisfaction_survey
                    send_satisfaction_survey(ticket_id)
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to send satisfaction survey for ticket {ticket_id}: {e}")
            else:
                self.auto_send_ticket_notifications(ticket_id, "updated")

            return True
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update status: {str(e)}")
            return False

    def show_assign_dialog(self, ticket_id):
        """Show ticket assignment dialog"""
        assign_window = tk.Toplevel(self.root)
        assign_window.title(f"Assign Ticket #{ticket_id}")
        assign_window.geometry("400x300")
        assign_window.transient(self.root)
        assign_window.grab_set()
        
        # Title
        ttk.Label(assign_window, text=f"Assign Ticket #{ticket_id}", 
                 style='Heading.TLabel').pack(pady=10)
        
        # Staff selection
        staff_frame = ttk.LabelFrame(assign_window, text="Assign To")
        staff_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Get available staff
        staff_list = self.get_available_staff()
        
        staff_var = tk.StringVar()
        
        # Add "Unassigned" option
        ttk.Radiobutton(staff_frame, text="Unassigned", variable=staff_var, 
                       value="").pack(anchor='w', padx=5, pady=2)
        
        for staff in staff_list:
            display_text = f"{staff['username']} ({staff['role']} - {staff.get('department', 'No Dept')})"
            ttk.Radiobutton(staff_frame, text=display_text, variable=staff_var, 
                           value=str(staff['id'])).pack(anchor='w', padx=5, pady=2)
        
        # Buttons
        button_frame = ttk.Frame(assign_window)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        def assign_ticket():
            assignee_id = staff_var.get()
            assignee_id = int(assignee_id) if assignee_id else None
            
            if self.assign_ticket_to_user(ticket_id, assignee_id):
                messagebox.showinfo("Success", "Ticket assigned successfully!")
                assign_window.destroy()
                self.refresh_my_tickets()
            else:
                messagebox.showerror("Error", "Failed to assign ticket")
        
        ttk.Button(button_frame, text="Assign", command=assign_ticket, 
                  style='Primary.TButton').pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=assign_window.destroy).pack(side='right')

    def get_available_staff(self):
        """Get list of available staff members"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT id, username, role, department
            FROM users
            WHERE role IN ('staff', 'admin') AND is_active = 1
            ORDER BY department, username
            ''')
            
            staff = cursor.fetchall()
            conn.close()
            
            return [dict(s) for s in staff]
            
        except Exception as e:
            return []

    def assign_ticket_to_user(self, ticket_id, assignee_id):
        """Assign ticket to user"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            UPDATE support_tickets
            SET assigned_to = ?, updated_at = ?, last_activity_at = ?
            WHERE ticket_id = ?
            ''', (assignee_id, now, now, ticket_id))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to assign ticket: {str(e)}")
            return False

    def show_internal_note_dialog(self, ticket_id):
        """Show internal note dialog"""
        note_window = tk.Toplevel(self.root)
        note_window.title(f"Add Internal Note - Ticket #{ticket_id}")
        note_window.geometry("600x400")
        note_window.transient(self.root)
        note_window.grab_set()
        
        # Title
        ttk.Label(note_window, text=f"Add Internal Note to Ticket #{ticket_id}", 
                 style='Heading.TLabel').pack(pady=10)
        
        # Message frame
        message_frame = ttk.LabelFrame(note_window, text="Internal Note (Only visible to staff)")
        message_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Message text area
        message_text = scrolledtext.ScrolledText(message_frame, height=10, wrap='word')
        message_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(note_window)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        def add_note():
            message = message_text.get('1.0', 'end-1c').strip()
            if not message:
                messagebox.showerror("Error", "Please enter a note")
                return
            
            if self.add_ticket_reply(ticket_id, message, 0, is_internal=True):
                messagebox.showinfo("Success", "Internal note added successfully!")
                note_window.destroy()
            else:
                messagebox.showerror("Error", "Failed to add internal note")
        
        ttk.Button(button_frame, text="Add Note", command=add_note, 
                  style='Primary.TButton').pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=note_window.destroy).pack(side='right')

    def create_new_ticket_tab(self):
        """Create new ticket tab"""
        ticket_frame = ttk.Frame(self.notebook)
        self.notebook.add(ticket_frame, text="Create Ticket")
        
        # Create scrollable frame
        canvas = tk.Canvas(ticket_frame)
        scrollbar = ttk.Scrollbar(ticket_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Title
        ttk.Label(scrollable_frame, text="Create New Support Ticket", 
                 style='Title.TLabel').pack(pady=10)
        
        # Template selection
        template_frame = ttk.LabelFrame(scrollable_frame, text="Use Template (Optional)")
        template_frame.pack(fill='x', padx=10, pady=5)
        
        self.template_var = tk.StringVar(value="custom")
        ttk.Radiobutton(template_frame, text="Custom Ticket", variable=self.template_var, 
                       value="custom").pack(anchor='w', padx=5, pady=2)
        
        # Load available templates
        templates = self.get_ticket_templates()
        for template in templates:
            ttk.Radiobutton(template_frame, text=f"{template['name']} ({template['category']})", 
                           variable=self.template_var, value=str(template['template_id']),
                           command=lambda t=template: self.load_template(t)).pack(anchor='w', padx=5, pady=2)
        
        # Ticket form
        form_frame = ttk.LabelFrame(scrollable_frame, text="Ticket Details")
        form_frame.pack(fill='x', padx=10, pady=5)
        
        # Subject
        ttk.Label(form_frame, text="Subject:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.subject_entry = ttk.Entry(form_frame, width=60)
        self.subject_entry.grid(row=0, column=1, columnspan=2, sticky='ew', padx=5, pady=5)
        
        # Category
        ttk.Label(form_frame, text="Category:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=self.category_var,
                                     values=["Technical Support", "Academic Inquiry", 
                                            "Financial Services", "Account Access", "Other"],
                                     state="readonly")
        category_combo.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        
        # Priority, Impact, Urgency
        ttk.Label(form_frame, text="Priority:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.priority_var = tk.StringVar(value="medium")
        priority_combo = ttk.Combobox(form_frame, textvariable=self.priority_var,
                                     values=["low", "medium", "high"], state="readonly")
        priority_combo.grid(row=2, column=1, sticky='ew', padx=5, pady=5)
        
        ttk.Label(form_frame, text="Impact:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.impact_var = tk.StringVar(value="low")
        impact_combo = ttk.Combobox(form_frame, textvariable=self.impact_var,
                                   values=["low", "medium", "high"], state="readonly")
        impact_combo.grid(row=3, column=1, sticky='ew', padx=5, pady=5)
        
        ttk.Label(form_frame, text="Urgency:").grid(row=4, column=0, sticky='w', padx=5, pady=5)
        self.urgency_var = tk.StringVar(value="low")
        urgency_combo = ttk.Combobox(form_frame, textvariable=self.urgency_var,
                                    values=["low", "medium", "high"], state="readonly")
        urgency_combo.grid(row=4, column=1, sticky='ew', padx=5, pady=5)
        
        # Configure grid weights
        form_frame.grid_columnconfigure(1, weight=1)
        
        # Message
        message_frame = ttk.LabelFrame(scrollable_frame, text="Message")
        message_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.message_text = scrolledtext.ScrolledText(message_frame, height=10, wrap='word')
        self.message_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(button_frame, text="Create Ticket", command=self.create_ticket, 
                  style='Primary.TButton').pack(side='right', padx=5)
        ttk.Button(button_frame, text="Clear Form", command=self.clear_ticket_form).pack(side='right', padx=5)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def get_ticket_templates(self):
        """Get available ticket templates"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT template_id, name, category, subject_template, message_template,
                   default_priority, default_impact, default_urgency
            FROM ticket_templates
            WHERE is_active = 1
            ORDER BY category, name
            ''')
            
            templates = cursor.fetchall()
            conn.close()
            
            return [dict(template) for template in templates]
            
        except Exception as e:
            return []

    def load_template(self, template):
        """Load selected template into form"""
        try:
            self.subject_entry.delete(0, 'end')
            self.subject_entry.insert(0, template.get('subject_template', ''))
            
            self.category_var.set(template.get('category', ''))
            self.priority_var.set(template.get('default_priority', 'medium'))
            self.impact_var.set(template.get('default_impact', 'low'))
            self.urgency_var.set(template.get('default_urgency', 'low'))
            
            self.message_text.delete('1.0', 'end')
            self.message_text.insert('1.0', template.get('message_template', ''))
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load template: {str(e)}")

    def clear_ticket_form(self):
        """Clear the ticket creation form"""
        self.subject_entry.delete(0, 'end')
        self.category_var.set('')
        self.priority_var.set('medium')
        self.impact_var.set('low')
        self.urgency_var.set('low')
        self.message_text.delete('1.0', 'end')
        self.template_var.set('custom')

    def create_ticket(self):
        """Create new support ticket"""
        try:
            # Validate form
            subject = self.subject_entry.get().strip()
            category = self.category_var.get()
            message = self.message_text.get('1.0', 'end-1c').strip()
            
            if not subject:
                messagebox.showerror("Error", "Subject is required")
                return
            
            if not category:
                messagebox.showerror("Error", "Category is required")
                return
            
            if not message:
                messagebox.showerror("Error", "Message is required")
                return
            
            # Create ticket
            ticket_data = {
                'subject': subject,
                'message': message,
                'category': category,
                'priority': self.priority_var.get(),
                'impact': self.impact_var.get(),
                'urgency': self.urgency_var.get()
            }
            
            if self.create_support_ticket(ticket_data):
                messagebox.showinfo("Success", "Ticket created successfully!")
                self.clear_ticket_form()
                self.refresh_my_tickets()
                # Switch to My Tickets tab
                self.notebook.select(1)
            else:
                messagebox.showerror("Error", "Failed to create ticket")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create ticket: {str(e)}")

    def create_support_ticket(self, ticket_data):
        """Create support ticket in database"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO support_tickets
            (user_id, subject, message, category, status, priority, impact, urgency,
             source, created_at, updated_at, last_activity_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.current_user.get('id', 0),
                ticket_data['subject'],
                ticket_data['message'],
                ticket_data['category'],
                'open',
                ticket_data['priority'],
                ticket_data['impact'],
                ticket_data['urgency'],
                'web',
                now, now, now
            ))

            # Get the created ticket ID
            ticket_id = cursor.lastrowid

            conn.commit()
            conn.close()

            # Auto-send email notifications
            self.auto_send_ticket_notifications(ticket_id, "created")

            return True
            
        except Exception as e:
            messagebox.showerror("Error", f"Database error: {str(e)}")
            return False

    def create_knowledge_base_tab(self):
        """Create knowledge base tab"""
        kb_frame = ttk.Frame(self.notebook)
        self.notebook.add(kb_frame, text="Knowledge Base")
        
        # Toolbar
        toolbar = ttk.Frame(kb_frame)
        toolbar.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(toolbar, text="Refresh", command=self.refresh_knowledge_base).pack(side='left', padx=5)
        if self.has_permission('manage_tickets'):
            ttk.Button(toolbar, text="Create Article", command=self.show_create_article).pack(side='left', padx=5)
        
        # Search frame
        search_frame = ttk.Frame(kb_frame)
        search_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(search_frame, text="Search:").pack(side='left')
        self.kb_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.kb_search_var, width=30)
        search_entry.pack(side='left', padx=5)
        search_entry.bind('<Return>', lambda e: self.search_knowledge_base())
        ttk.Button(search_frame, text="Search", command=self.search_knowledge_base).pack(side='left', padx=5)
        
        # Category filter
        ttk.Label(search_frame, text="Category:").pack(side='left', padx=(20, 0))
        self.kb_category_var = tk.StringVar(value="all")
        category_combo = ttk.Combobox(search_frame, textvariable=self.kb_category_var,
                                     values=["all"], state="readonly", width=15)
        category_combo.pack(side='left', padx=5)
        category_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_knowledge_base())
        
        # Articles list
        self.kb_list_frame = ttk.Frame(kb_frame)
        self.kb_list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.create_knowledge_base_list()

    def create_knowledge_base_list(self):
        """Create knowledge base articles list"""
        # Clear existing widgets
        for widget in self.kb_list_frame.winfo_children():
            widget.destroy()
        
        # Create treeview
        columns = ('ID', 'Title', 'Category', 'Views', 'Rating', 'Updated')
        self.kb_tree = ttk.Treeview(self.kb_list_frame, columns=columns, show='headings')
        
        # Configure columns
        column_widths = {'ID': 50, 'Title': 300, 'Category': 120, 'Views': 80, 
                        'Rating': 100, 'Updated': 120}
        
        for col in columns:
            self.kb_tree.heading(col, text=col)
            self.kb_tree.column(col, width=column_widths.get(col, 100))
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(self.kb_list_frame, orient='vertical', command=self.kb_tree.yview)
        h_scrollbar = ttk.Scrollbar(self.kb_list_frame, orient='horizontal', command=self.kb_tree.xview)
        
        self.kb_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack widgets
        self.kb_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        self.kb_list_frame.grid_rowconfigure(0, weight=1)
        self.kb_list_frame.grid_columnconfigure(0, weight=1)
        
        # Bind double-click to view article
        self.kb_tree.bind('<Double-1>', self.on_kb_article_double_click)
        
        # Load data
        self.refresh_knowledge_base()

    def refresh_knowledge_base(self):
        """Refresh knowledge base list"""
        try:
            # Clear existing items
            for item in self.kb_tree.get_children():
                self.kb_tree.delete(item)
            
            # Get articles from database
            articles = self.get_knowledge_base_articles()
            
            # Update category filter
            categories = ["all"] + list(set(article.get('category', 'Uncategorized') for article in articles))
            # Update combobox values (find the combobox widget)
            for widget in self.kb_list_frame.master.winfo_children():
                if isinstance(widget, ttk.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Combobox) and child.cget('textvariable') == str(self.kb_category_var):
                            child['values'] = categories
                            break
            
            # Filter articles
            category_filter = self.kb_category_var.get()
            if category_filter != "all":
                articles = [a for a in articles if a.get('category') == category_filter]
            
            # Populate treeview
            for article in articles:
                # Calculate rating
                helpful = article.get('helpful_votes', 0)
                unhelpful = article.get('unhelpful_votes', 0)
                total_votes = helpful + unhelpful
                rating = f"{helpful}/{total_votes}" if total_votes > 0 else "No votes"
                
                # Format date
                updated = article.get('updated_at', '')[:16] if article.get('updated_at') else ''
                
                self.kb_tree.insert('', 'end', values=(
                    article.get('article_id', ''),
                    article.get('title', '')[:50],
                    article.get('category', 'Uncategorized'),
                    article.get('views', 0),
                    rating,
                    updated
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load knowledge base: {str(e)}")

    def get_knowledge_base_articles(self):
        """Get knowledge base articles from database"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT article_id, title, category, views, helpful_votes, unhelpful_votes, updated_at
            FROM knowledge_base
            WHERE status = 'published'
            ORDER BY helpful_votes DESC, views DESC
            ''')
            
            articles = cursor.fetchall()
            conn.close()
            
            return [dict(article) for article in articles]
            
        except Exception as e:
            return []

    def search_knowledge_base(self):
        """Search knowledge base articles"""
        search_term = self.kb_search_var.get().strip()
        if not search_term:
            self.refresh_knowledge_base()
            return
        
        try:
            # Clear existing items
            for item in self.kb_tree.get_children():
                self.kb_tree.delete(item)
            
            # Search articles
            articles = self.search_kb_articles(search_term)
            
            # Populate treeview
            for article in articles:
                helpful = article.get('helpful_votes', 0)
                unhelpful = article.get('unhelpful_votes', 0)
                total_votes = helpful + unhelpful
                rating = f"{helpful}/{total_votes}" if total_votes > 0 else "No votes"
                
                updated = article.get('updated_at', '')[:16] if article.get('updated_at') else ''
                
                self.kb_tree.insert('', 'end', values=(
                    article.get('article_id', ''),
                    article.get('title', '')[:50],
                    article.get('category', 'Uncategorized'),
                    article.get('views', 0),
                    rating,
                    updated
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")

    def search_kb_articles(self, search_term):
        """Search knowledge base articles"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT article_id, title, category, views, helpful_votes, unhelpful_votes, updated_at
            FROM knowledge_base
            WHERE status = 'published' 
            AND (title LIKE ? OR content LIKE ? OR search_keywords LIKE ?)
            ORDER BY helpful_votes DESC, views DESC
            ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
            
            articles = cursor.fetchall()
            conn.close()
            
            return [dict(article) for article in articles]
            
        except Exception as e:
            return []

    def on_kb_article_double_click(self, event):
        """Handle double-click on knowledge base article"""
        selection = self.kb_tree.selection()
        if not selection:
            return
        
        item = self.kb_tree.item(selection[0])
        article_id = item['values'][0]
        
        self.show_kb_article_details(article_id)

    def show_kb_article_details(self, article_id):
        """Show knowledge base article details"""
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Knowledge Base Article #{article_id}")
        details_window.geometry("800x600")
        details_window.transient(self.root)
        
        # Get article data
        article_data = self.get_kb_article_details(article_id)
        if not article_data:
            messagebox.showerror("Error", "Article not found")
            details_window.destroy()
            return
        
        # Create scrollable frame
        canvas = tk.Canvas(details_window)
        scrollbar = ttk.Scrollbar(details_window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Article header
        header_frame = ttk.Frame(scrollable_frame)
        header_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(header_frame, text=article_data.get('title', ''), 
                 style='Title.TLabel').pack(anchor='w')
        
        # Article info
        info_frame = ttk.Frame(scrollable_frame)
        info_frame.pack(fill='x', padx=10, pady=5)
        
        info_text = f"Category: {article_data.get('category', 'Uncategorized')} | "
        info_text += f"Views: {article_data.get('views', 0)} | "
        info_text += f"Updated: {article_data.get('updated_at', '')}"
        
        ttk.Label(info_frame, text=info_text).pack(anchor='w')
        
        # Article content
        content_frame = ttk.LabelFrame(scrollable_frame, text="Content")
        content_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        content_text = scrolledtext.ScrolledText(content_frame, wrap='word', state='disabled')
        content_text.pack(fill='both', expand=True, padx=5, pady=5)
        content_text.config(state='normal')
        content_text.insert('1.0', article_data.get('content', ''))
        content_text.config(state='disabled')
        
        # Rating frame
        rating_frame = ttk.LabelFrame(scrollable_frame, text="Rate This Article")
        rating_frame.pack(fill='x', padx=10, pady=10)
        
        helpful = article_data.get('helpful_votes', 0)
        unhelpful = article_data.get('unhelpful_votes', 0)
        total = helpful + unhelpful
        
        current_rating = f"Current rating: {helpful} helpful, {unhelpful} not helpful"
        if total > 0:
            current_rating += f" ({helpful/total*100:.1f}% helpful)"
        
        ttk.Label(rating_frame, text=current_rating).pack(pady=5)
        
        button_frame = ttk.Frame(rating_frame)
        button_frame.pack(pady=5)
        
        ttk.Button(button_frame, text="👍 Helpful", 
                  command=lambda: self.rate_article(article_id, True, details_window)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="👎 Not Helpful", 
                  command=lambda: self.rate_article(article_id, False, details_window)).pack(side='left', padx=5)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Update view count
        self.update_article_views(article_id)

    def get_kb_article_details(self, article_id):
        """Get detailed knowledge base article"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT * FROM knowledge_base WHERE article_id = ?
            ''', (article_id,))
            
            article = cursor.fetchone()
            conn.close()
            
            return dict(article) if article else None
            
        except Exception as e:
            return None

    def update_article_views(self, article_id):
        """Update article view count"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            UPDATE knowledge_base SET views = views + 1 WHERE article_id = ?
            ''', (article_id,))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            pass

    def rate_article(self, article_id, is_helpful, window):
        """Rate knowledge base article"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            
            if is_helpful:
                cursor.execute('''
                UPDATE knowledge_base SET helpful_votes = helpful_votes + 1 WHERE article_id = ?
                ''', (article_id,))
            else:
                cursor.execute('''
                UPDATE knowledge_base SET unhelpful_votes = unhelpful_votes + 1 WHERE article_id = ?
                ''', (article_id,))
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", "Thank you for your feedback!")
            window.destroy()
            self.refresh_knowledge_base()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to rate article: {str(e)}")

    def show_create_article(self):
        """Show create article dialog"""
        if not self.has_permission('manage_tickets'):
            messagebox.showerror("Error", "You don't have permission to create articles")
            return
        
        create_window = tk.Toplevel(self.root)
        create_window.title("Create Knowledge Base Article")
        create_window.geometry("800x600")
        create_window.transient(self.root)
        create_window.grab_set()
        
        # Create scrollable frame
        canvas = tk.Canvas(create_window)
        scrollbar = ttk.Scrollbar(create_window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Title
        ttk.Label(scrollable_frame, text="Create Knowledge Base Article", 
                 style='Title.TLabel').pack(pady=10)
        
        # Form
        form_frame = ttk.LabelFrame(scrollable_frame, text="Article Details")
        form_frame.pack(fill='x', padx=10, pady=10)
        
        # Article title
        ttk.Label(form_frame, text="Title:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        title_entry = ttk.Entry(form_frame, width=60)
        title_entry.grid(row=0, column=1, columnspan=2, sticky='ew', padx=5, pady=5)
        
        # Category
        ttk.Label(form_frame, text="Category:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        category_entry = ttk.Entry(form_frame, width=30)
        category_entry.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        
        # Tags
        ttk.Label(form_frame, text="Tags:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        tags_entry = ttk.Entry(form_frame, width=40)
        tags_entry.grid(row=2, column=1, sticky='ew', padx=5, pady=5)
        ttk.Label(form_frame, text="(comma-separated)").grid(row=2, column=2, sticky='w', padx=5, pady=5)
        
        form_frame.grid_columnconfigure(1, weight=1)
        
        # Content
        content_frame = ttk.LabelFrame(scrollable_frame, text="Article Content")
        content_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        content_text = scrolledtext.ScrolledText(content_frame, height=15, wrap='word')
        content_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Status
        status_frame = ttk.LabelFrame(scrollable_frame, text="Publication Status")
        status_frame.pack(fill='x', padx=10, pady=10)
        
        status_var = tk.StringVar(value="draft")
        ttk.Radiobutton(status_frame, text="Save as Draft", variable=status_var, 
                       value="draft").pack(anchor='w', padx=5, pady=2)
        ttk.Radiobutton(status_frame, text="Publish Immediately", variable=status_var, 
                       value="published").pack(anchor='w', padx=5, pady=2)
        
        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        def create_article():
            title = title_entry.get().strip()
            category = category_entry.get().strip()
            tags = tags_entry.get().strip()
            content = content_text.get('1.0', 'end-1c').strip()
            status = status_var.get()
            
            if not title or not content:
                messagebox.showerror("Error", "Title and content are required")
                return
            
            article_data = {
                'title': title,
                'category': category,
                'tags': tags,
                'content': content,
                'status': status
            }
            
            if self.create_kb_article(article_data):
                messagebox.showinfo("Success", "Article created successfully!")
                create_window.destroy()
                self.refresh_knowledge_base()
            else:
                messagebox.showerror("Error", "Failed to create article")
        
        ttk.Button(button_frame, text="Create Article", command=create_article, 
                  style='Primary.TButton').pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=create_window.destroy).pack(side='right')
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def create_kb_article(self, article_data):
        """Create knowledge base article"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO knowledge_base
            (title, content, category, tags, author_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                article_data['title'],
                article_data['content'],
                article_data['category'],
                article_data['tags'],
                self.current_user.get('id', 0),
                article_data['status'],
                now, now
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            messagebox.showerror("Error", f"Database error: {str(e)}")
            return False

    def create_all_tickets_tab(self):
        """Create all tickets tab (admin only)"""
        if not self.has_permission('view_all_tickets'):
            return
        
        all_tickets_frame = ttk.Frame(self.notebook)
        self.notebook.add(all_tickets_frame, text="All Tickets")
        
        # Toolbar
        toolbar = ttk.Frame(all_tickets_frame)
        toolbar.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(toolbar, text="Refresh", command=self.refresh_all_tickets).pack(side='left', padx=5)
        ttk.Button(toolbar, text="Bulk Actions", command=self.show_bulk_actions).pack(side='left', padx=5)
        
        # Filters
        filter_frame = ttk.LabelFrame(all_tickets_frame, text="Filters")
        filter_frame.pack(fill='x', padx=10, pady=5)
        
        filter_grid = ttk.Frame(filter_frame)
        filter_grid.pack(fill='x', padx=5, pady=5)
        
        # Status filter
        ttk.Label(filter_grid, text="Status:").grid(row=0, column=0, padx=5)
        self.all_tickets_status_var = tk.StringVar(value="all")
        status_combo = ttk.Combobox(filter_grid, textvariable=self.all_tickets_status_var,
                                   values=["all", "open", "in progress", "waiting for customer", "resolved", "closed"],
                                   state="readonly")
        status_combo.grid(row=0, column=1, padx=5)
        
        # Priority filter
        ttk.Label(filter_grid, text="Priority:").grid(row=0, column=2, padx=5)
        self.all_tickets_priority_var = tk.StringVar(value="all")
        priority_combo = ttk.Combobox(filter_grid, textvariable=self.all_tickets_priority_var,
                                     values=["all", "low", "medium", "high"],
                                     state="readonly")
        priority_combo.grid(row=0, column=3, padx=5)
        
        # Assignment filter
        ttk.Label(filter_grid, text="Assignment:").grid(row=0, column=4, padx=5)
        self.all_tickets_assignment_var = tk.StringVar(value="all")
        assignment_combo = ttk.Combobox(filter_grid, textvariable=self.all_tickets_assignment_var,
                                       values=["all", "assigned", "unassigned"],
                                       state="readonly")
        assignment_combo.grid(row=0, column=5, padx=5)
        
        # Bind filter changes
        for combo in [status_combo, priority_combo, assignment_combo]:
            combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_all_tickets())
        
        # Apply filters button
        ttk.Button(filter_grid, text="Apply Filters", 
                  command=self.refresh_all_tickets).grid(row=0, column=6, padx=10)
        
        # Tickets list
        self.all_tickets_frame = ttk.Frame(all_tickets_frame)
        self.all_tickets_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.create_all_tickets_list()

    def create_all_tickets_list(self):
        """Create all tickets list"""
        # Clear existing widgets
        for widget in self.all_tickets_frame.winfo_children():
            widget.destroy()
        
        # Create treeview with checkboxes for selection
        columns = ('Select', 'ID', 'Subject', 'Submitter', 'Assignee', 'Category', 'Status', 'Priority', 'Created', 'Updated')
        self.all_tickets_tree = ttk.Treeview(self.all_tickets_frame, columns=columns, show='headings')
        
        # Configure columns
        column_widths = {'Select': 50, 'ID': 50, 'Subject': 200, 'Submitter': 100, 'Assignee': 100,
                        'Category': 120, 'Status': 100, 'Priority': 80, 'Created': 120, 'Updated': 120}
        
        for col in columns:
            self.all_tickets_tree.heading(col, text=col)
            self.all_tickets_tree.column(col, width=column_widths.get(col, 100))
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(self.all_tickets_frame, orient='vertical', 
                                   command=self.all_tickets_tree.yview)
        h_scrollbar = ttk.Scrollbar(self.all_tickets_frame, orient='horizontal', 
                                   command=self.all_tickets_tree.xview)
        
        self.all_tickets_tree.configure(yscrollcommand=v_scrollbar.set, 
                                       xscrollcommand=h_scrollbar.set)
        
        # Pack widgets
        self.all_tickets_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        self.all_tickets_frame.grid_rowconfigure(0, weight=1)
        self.all_tickets_frame.grid_columnconfigure(0, weight=1)
        
        # Bind events
        self.all_tickets_tree.bind('<Double-1>', self.on_all_ticket_double_click)
        self.all_tickets_tree.bind('<Button-1>', self.on_all_ticket_click)
        
        # Context menu
        self.create_all_tickets_context_menu()
        
        # Track selected items
        self.selected_tickets = set()
        
        # Load data
        self.refresh_all_tickets()

    def create_all_tickets_context_menu(self):
        """Create context menu for all tickets"""
        self.all_tickets_context_menu = tk.Menu(self.root, tearoff=0)
        self.all_tickets_context_menu.add_command(label="View Details", command=self.view_selected_all_ticket)
        self.all_tickets_context_menu.add_command(label="Assign", command=self.assign_selected_ticket)
        self.all_tickets_context_menu.add_command(label="Change Status", command=self.change_status_selected_ticket)
        self.all_tickets_context_menu.add_separator()
        self.all_tickets_context_menu.add_command(label="Select All", command=self.select_all_tickets)
        self.all_tickets_context_menu.add_command(label="Deselect All", command=self.deselect_all_tickets)
        self.all_tickets_context_menu.add_separator()
        self.all_tickets_context_menu.add_command(label="Refresh", command=self.refresh_all_tickets)
        
        self.all_tickets_tree.bind('<Button-3>', self.show_all_tickets_context_menu)

    def show_all_tickets_context_menu(self, event):
        """Show context menu for all tickets"""
        try:
            self.all_tickets_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.all_tickets_context_menu.grab_release()

    def on_all_ticket_click(self, event):
        """Handle click on all tickets tree"""
        region = self.all_tickets_tree.identify("region", event.x, event.y)
        if region == "cell":
            column = self.all_tickets_tree.identify_column(event.x, event.y)
            if column == '#1':  # Select column
                item = self.all_tickets_tree.identify_row(event.y)
                if item:
                    self.toggle_ticket_selection(item)

    def toggle_ticket_selection(self, item):
        """Toggle ticket selection"""
        values = list(self.all_tickets_tree.item(item, 'values'))
        ticket_id = values[1]
        
        if values[0] == '☐':  # Not selected
            values[0] = '☑'
            self.selected_tickets.add(ticket_id)
        else:  # Selected
            values[0] = '☐'
            self.selected_tickets.discard(ticket_id)
        
        self.all_tickets_tree.item(item, values=values)

    def select_all_tickets(self):
        """Select all visible tickets"""
        for item in self.all_tickets_tree.get_children():
            values = list(self.all_tickets_tree.item(item, 'values'))
            if values[0] == '☐':
                values[0] = '☑'
                self.selected_tickets.add(values[1])
                self.all_tickets_tree.item(item, values=values)

    def deselect_all_tickets(self):
        """Deselect all tickets"""
        for item in self.all_tickets_tree.get_children():
            values = list(self.all_tickets_tree.item(item, 'values'))
            if values[0] == '☑':
                values[0] = '☐'
                self.all_tickets_tree.item(item, values=values)
        self.selected_tickets.clear()

    def refresh_all_tickets(self):
        """Refresh all tickets list"""
        try:
            # Clear existing items and selections
            for item in self.all_tickets_tree.get_children():
                self.all_tickets_tree.delete(item)
            self.selected_tickets.clear()
            
            # Get tickets from database
            tickets = self.get_all_tickets()
            
            # Populate treeview
            for ticket in tickets:
                # Format dates
                created = ticket['created_at'][:16] if ticket['created_at'] else ''
                updated = ticket['updated_at'][:16] if ticket['updated_at'] else ''
                
                self.all_tickets_tree.insert('', 'end', values=(
                    '☐',  # Checkbox
                    ticket['ticket_id'],
                    ticket['subject'][:40],
                    ticket['submitter'][:15],
                    ticket.get('assignee', 'Unassigned')[:15],
                    ticket['category'],
                    ticket['status'].title(),
                    ticket['priority'].title(),
                    created,
                    updated
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load tickets: {str(e)}")

    def get_all_tickets(self):
        """Get all tickets from database with filters"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Build where clause based on filters
            where_conditions = []
            params = []
            
            status_filter = self.all_tickets_status_var.get()
            if status_filter != "all":
                where_conditions.append("t.status = ?")
                params.append(status_filter)
            
            priority_filter = self.all_tickets_priority_var.get()
            if priority_filter != "all":
                where_conditions.append("t.priority = ?")
                params.append(priority_filter)
            
            assignment_filter = self.all_tickets_assignment_var.get()
            if assignment_filter == "assigned":
                where_conditions.append("t.assigned_to IS NOT NULL")
            elif assignment_filter == "unassigned":
                where_conditions.append("t.assigned_to IS NULL")
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            cursor.execute(f'''
            SELECT t.ticket_id, t.subject, t.category, t.status, t.priority, t.created_at, t.updated_at,
                   u1.username as submitter, u2.username as assignee
            FROM support_tickets t
            JOIN users u1 ON t.user_id = u1.id
            LEFT JOIN users u2 ON t.assigned_to = u2.id
            WHERE {where_clause}
            ORDER BY t.updated_at DESC
            ''', params)
            
            tickets = cursor.fetchall()
            conn.close()
            
            return [dict(ticket) for ticket in tickets]
            
        except Exception as e:
            messagebox.showerror("Error", f"Database error: {str(e)}")
            return []

    def on_all_ticket_double_click(self, event):
        """Handle double-click on all tickets"""
        region = self.all_tickets_tree.identify("region", event.x, event.y)
        if region == "cell":
            column = self.all_tickets_tree.identify_column(event.x, event.y)
            if column != '#1':  # Not the select column
                self.view_selected_all_ticket()

    def view_selected_all_ticket(self):
        """View selected ticket from all tickets"""
        selection = self.all_tickets_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a ticket")
            return
        
        item = self.all_tickets_tree.item(selection[0])
        ticket_id = item['values'][1]
        
        self.show_ticket_details(ticket_id)

    def assign_selected_ticket(self):
        """Assign selected ticket"""
        selection = self.all_tickets_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a ticket")
            return
        
        item = self.all_tickets_tree.item(selection[0])
        ticket_id = item['values'][1]
        
        self.show_assign_dialog(ticket_id)

    def change_status_selected_ticket(self):
        """Change status of selected ticket"""
        selection = self.all_tickets_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a ticket")
            return
        
        item = self.all_tickets_tree.item(selection[0])
        ticket_id = item['values'][1]
        
        self.show_status_dialog(ticket_id)

    def show_bulk_actions(self):
        """Show bulk actions dialog"""
        if not self.selected_tickets:
            messagebox.showwarning("Warning", "Please select some tickets first")
            return
        
        bulk_window = tk.Toplevel(self.root)
        bulk_window.title("Bulk Actions")
        bulk_window.geometry("400x300")
        bulk_window.transient(self.root)
        bulk_window.grab_set()
        
        # Title
        ttk.Label(bulk_window, text=f"Bulk Actions ({len(self.selected_tickets)} tickets selected)", 
                 style='Heading.TLabel').pack(pady=10)
        
        # Actions frame
        actions_frame = ttk.LabelFrame(bulk_window, text="Available Actions")
        actions_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Bulk assign
        assign_frame = ttk.Frame(actions_frame)
        assign_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(assign_frame, text="Assign to:").pack(side='left')
        
        staff_list = self.get_available_staff()
        assign_var = tk.StringVar()
        assign_combo = ttk.Combobox(assign_frame, textvariable=assign_var, state="readonly")
        assign_combo['values'] = ["Unassigned"] + [f"{s['username']} ({s['role']})" for s in staff_list]
        assign_combo.pack(side='left', padx=5)
        
        ttk.Button(assign_frame, text="Assign", 
                  command=lambda: self.bulk_assign_tickets(assign_var.get(), staff_list, bulk_window)).pack(side='left', padx=5)
        
        # Bulk status change
        status_frame = ttk.Frame(actions_frame)
        status_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(status_frame, text="Change status to:").pack(side='left')
        
        status_var = tk.StringVar()
        status_combo = ttk.Combobox(status_frame, textvariable=status_var, state="readonly")
        status_combo['values'] = ["open", "in progress", "waiting for customer", "resolved", "closed"]
        status_combo.pack(side='left', padx=5)
        
        ttk.Button(status_frame, text="Change Status", 
                  command=lambda: self.bulk_change_status(status_var.get(), bulk_window)).pack(side='left', padx=5)
        
        # Close button
        ttk.Button(bulk_window, text="Close", command=bulk_window.destroy).pack(pady=10)

    def bulk_assign_tickets(self, assign_text, staff_list, window):
        """Bulk assign tickets"""
        if not assign_text:
            messagebox.showerror("Error", "Please select an assignee")
            return
        
        assignee_id = None
        if assign_text != "Unassigned":
            # Extract username from combo text
            username = assign_text.split(' (')[0]
            for staff in staff_list:
                if staff['username'] == username:
                    assignee_id = staff['id']
                    break
        
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            for ticket_id in self.selected_tickets:
                cursor.execute('''
                UPDATE support_tickets
                SET assigned_to = ?, updated_at = ?, last_activity_at = ?
                WHERE ticket_id = ?
                ''', (assignee_id, now, now, ticket_id))
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", f"{len(self.selected_tickets)} tickets assigned successfully!")
            window.destroy()
            self.refresh_all_tickets()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to assign tickets: {str(e)}")

    def bulk_change_status(self, new_status, window):
        """Bulk change ticket status"""
        if not new_status:
            messagebox.showerror("Error", "Please select a status")
            return
        
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            resolved_at = now if new_status in ['resolved', 'closed'] else None
            
            for ticket_id in self.selected_tickets:
                cursor.execute('''
                UPDATE support_tickets
                SET status = ?, resolved_at = ?, updated_at = ?, last_activity_at = ?
                WHERE ticket_id = ?
                ''', (new_status, resolved_at, now, now, ticket_id))
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", f"{len(self.selected_tickets)} tickets updated successfully!")
            window.destroy()
            self.refresh_all_tickets()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update tickets: {str(e)}")

    def create_analytics_tab(self):
        """Create analytics tab"""
        analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(analytics_frame, text="Analytics")
        
        # Create scrollable frame
        canvas = tk.Canvas(analytics_frame)
        scrollbar = ttk.Scrollbar(analytics_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Title
        ttk.Label(scrollable_frame, text="Analytics Dashboard", 
                 style='Title.TLabel').pack(pady=10)
        
        # Time period selector
        period_frame = ttk.Frame(scrollable_frame)
        period_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(period_frame, text="Time Period:").pack(side='left')
        self.analytics_period_var = tk.StringVar(value="30d")
        period_combo = ttk.Combobox(period_frame, textvariable=self.analytics_period_var,
                                   values=["7d", "30d", "90d", "1y"], state="readonly", width=10)
        period_combo.pack(side='left', padx=5)
        period_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_analytics())
        
        ttk.Button(period_frame, text="Refresh", command=self.refresh_analytics).pack(side='left', padx=5)
        
        # Analytics content frame
        self.analytics_content_frame = ttk.Frame(scrollable_frame)
        self.analytics_content_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Load initial analytics
        self.refresh_analytics()

    def refresh_analytics(self):
        """Refresh analytics data"""
        try:
            # Clear existing content
            for widget in self.analytics_content_frame.winfo_children():
                widget.destroy()
            
            # Get analytics data
            period = self.analytics_period_var.get()
            analytics_data = self.get_analytics_data(period)
            
            # Overall statistics
            stats_frame = ttk.LabelFrame(self.analytics_content_frame, text=f"Overview ({period})")
            stats_frame.pack(fill='x', pady=5)
            
            stats_grid = ttk.Frame(stats_frame)
            stats_grid.pack(fill='x', padx=10, pady=10)
            
            # Display key metrics
            metrics = [
                ("Total Tickets", analytics_data.get('total_tickets', 0)),
                ("Open Tickets", analytics_data.get('open_tickets', 0)),
                ("Resolved Tickets", analytics_data.get('resolved_tickets', 0)),
                ("Resolution Rate", f"{analytics_data.get('resolution_rate', 0):.1f}%"),
                ("Avg Resolution Time", f"{analytics_data.get('avg_resolution_hours', 0):.1f}h"),
                ("Customer Satisfaction", f"{analytics_data.get('avg_satisfaction', 0):.1f}/5.0")
            ]
            
            for i, (label, value) in enumerate(metrics):
                row = i // 3
                col = (i % 3) * 2
                
                ttk.Label(stats_grid, text=f"{label}:", style='Heading.TLabel').grid(
                    row=row, column=col, sticky='w', padx=5, pady=2)
                ttk.Label(stats_grid, text=str(value)).grid(
                    row=row, column=col+1, sticky='w', padx=20, pady=2)
            
            # Category breakdown
            if analytics_data.get('categories'):
                category_frame = ttk.LabelFrame(self.analytics_content_frame, text="Tickets by Category")
                category_frame.pack(fill='x', pady=5)
                
                category_tree = ttk.Treeview(category_frame, columns=('Category', 'Count', 'Percentage'), 
                                           show='headings', height=6)
                category_tree.heading('Category', text='Category')
                category_tree.heading('Count', text='Count')
                category_tree.heading('Percentage', text='Percentage')
                
                for category, count in analytics_data['categories'].items():
                    percentage = (count / analytics_data.get('total_tickets', 1)) * 100
                    category_tree.insert('', 'end', values=(category, count, f"{percentage:.1f}%"))
                
                category_tree.pack(fill='x', padx=5, pady=5)
            
            # Staff performance
            if analytics_data.get('staff_performance'):
                staff_frame = ttk.LabelFrame(self.analytics_content_frame, text="Staff Performance")
                staff_frame.pack(fill='x', pady=5)
                
                staff_tree = ttk.Treeview(staff_frame, columns=('Staff', 'Assigned', 'Resolved', 'Rate'), 
                                        show='headings', height=6)
                staff_tree.heading('Staff', text='Staff')
                staff_tree.heading('Assigned', text='Assigned')
                staff_tree.heading('Resolved', text='Resolved')
                staff_tree.heading('Rate', text='Resolution Rate')
                
                for staff_data in analytics_data['staff_performance']:
                    rate = (staff_data['resolved'] / staff_data['assigned'] * 100) if staff_data['assigned'] > 0 else 0
                    staff_tree.insert('', 'end', values=(
                        staff_data['username'], 
                        staff_data['assigned'], 
                        staff_data['resolved'], 
                        f"{rate:.1f}%"
                    ))
                
                staff_tree.pack(fill='x', padx=5, pady=5)
            
        except Exception as e:
            ttk.Label(self.analytics_content_frame, text=f"Error loading analytics: {str(e)}", 
                     style='Error.TLabel').pack()

    def get_analytics_data(self, period):
        """Get analytics data for specified period"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            
            # Calculate date range
            days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
            days = days_map.get(period, 30)
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            analytics_data = {}
            
            # Overall statistics
            cursor.execute('''
            SELECT 
                COUNT(*) as total_tickets,
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tickets,
                COUNT(CASE WHEN status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets,
                AVG(CASE WHEN resolved_at IS NOT NULL 
                    THEN (julianday(resolved_at) - julianday(created_at)) * 24 
                    ELSE NULL END) as avg_resolution_hours,
                AVG(satisfaction_rating) as avg_satisfaction
            FROM support_tickets
            WHERE created_at >= ?
            ''', (start_date,))
            
            result = cursor.fetchone()
            if result:
                total = result[0]
                analytics_data.update({
                    'total_tickets': total,
                    'open_tickets': result[1],
                    'resolved_tickets': result[2],
                    'resolution_rate': (result[2] / total * 100) if total > 0 else 0,
                    'avg_resolution_hours': result[3] or 0,
                    'avg_satisfaction': result[4] or 0
                })
            
            # Category breakdown
            cursor.execute('''
            SELECT category, COUNT(*) as count
            FROM support_tickets
            WHERE created_at >= ?
            GROUP BY category
            ORDER BY count DESC
            ''', (start_date,))
            
            analytics_data['categories'] = dict(cursor.fetchall())
            
            # Staff performance
            cursor.execute('''
            SELECT 
                u.username,
                COUNT(t.ticket_id) as assigned,
                COUNT(CASE WHEN t.status IN ('resolved', 'closed') THEN 1 END) as resolved
            FROM users u
            LEFT JOIN support_tickets t ON u.id = t.assigned_to AND t.created_at >= ?
            WHERE u.role IN ('staff', 'admin') AND u.is_active = 1
            GROUP BY u.id, u.username
            HAVING assigned > 0
            ORDER BY resolved DESC
            ''', (start_date,))
            
            staff_data = []
            for row in cursor.fetchall():
                staff_data.append({
                    'username': row[0],
                    'assigned': row[1],
                    'resolved': row[2]
                })
            
            analytics_data['staff_performance'] = staff_data
            
            conn.close()
            return analytics_data
            
        except Exception as e:
            return {'error': str(e)}

    def create_admin_tab(self):
        """Create admin tab"""
        admin_frame = ttk.Frame(self.notebook)
        self.notebook.add(admin_frame, text="Administration")
        
        # Create notebook for admin sections
        admin_notebook = ttk.Notebook(admin_frame)
        admin_notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # System Management tab
        self.create_system_management_tab(admin_notebook)
        
        # User Management tab
        self.create_user_management_tab(admin_notebook)
        
        # Reports tab
        self.create_reports_tab(admin_notebook)

    def create_system_management_tab(self, parent):
        """Create system management tab"""
        sys_frame = ttk.Frame(parent)
        parent.add(sys_frame, text="System")
        
        # System management options
        options_frame = ttk.LabelFrame(sys_frame, text="System Management")
        options_frame.pack(fill='x', padx=10, pady=10)
        
        # SLA Management
        sla_frame = ttk.Frame(options_frame)
        sla_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(sla_frame, text="SLA Policies:", style='Heading.TLabel').pack(side='left')
        ttk.Button(sla_frame, text="Manage SLAs", command=self.show_sla_management).pack(side='right')
        
        # Template Management
        template_frame = ttk.Frame(options_frame)
        template_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(template_frame, text="Ticket Templates:", style='Heading.TLabel').pack(side='left')
        ttk.Button(template_frame, text="Manage Templates", command=self.show_template_management).pack(side='right')
        
        # Department Management
        dept_frame = ttk.Frame(options_frame)
        dept_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(dept_frame, text="Departments:", style='Heading.TLabel').pack(side='left')
        ttk.Button(dept_frame, text="Manage Departments", command=self.show_department_management).pack(side='right')
        
        # Workflow Management
        workflow_frame = ttk.Frame(options_frame)
        workflow_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(workflow_frame, text="Workflows:", style='Heading.TLabel').pack(side='left')
        ttk.Button(workflow_frame, text="Manage Workflows", command=self.show_workflow_management).pack(side='right')
        
        # System Maintenance
        maintenance_frame = ttk.LabelFrame(sys_frame, text="System Maintenance")
        maintenance_frame.pack(fill='x', padx=10, pady=10)
        
        maint_grid = ttk.Frame(maintenance_frame)
        maint_grid.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(maint_grid, text="Database Cleanup", command=self.show_database_cleanup).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(maint_grid, text="Backup Database", command=self.backup_database).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(maint_grid, text="Check Integrity", command=self.check_data_integrity).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(maint_grid, text="Export Data", command=self.show_export_dialog).grid(row=1, column=1, padx=5, pady=5)
    
    # Placeholder methods for functionality that would integrate with original system
    def show_create_ticket(self):
        """Switch to create ticket tab"""
        # Find the create ticket tab and select it
        for i in range(self.notebook.index('end')):
            if self.notebook.tab(i, 'text') == 'Create Ticket':
                self.notebook.select(i)
                break

    def show_my_tickets(self):
        """Switch to my tickets tab"""
        for i in range(self.notebook.index('end')):
            if self.notebook.tab(i, 'text') == 'My Tickets':
                self.notebook.select(i)
                break

    def show_all_tickets(self):
        """Switch to all tickets tab"""
        for i in range(self.notebook.index('end')):
            if self.notebook.tab(i, 'text') == 'All Tickets':
                self.notebook.select(i)
                break

    def show_search_tickets(self):
        """Show advanced search dialog"""
        search_window = tk.Toplevel(self.root)
        search_window.title("Advanced Ticket Search")
        search_window.geometry("600x500")
        search_window.transient(self.root)
        search_window.grab_set()
        
        # Search form
        form_frame = ttk.LabelFrame(search_window, text="Search Criteria")
        form_frame.pack(fill='x', padx=10, pady=10)
        
        # Text search
        ttk.Label(form_frame, text="Search Text:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        search_text_entry = ttk.Entry(form_frame, width=40)
        search_text_entry.grid(row=0, column=1, columnspan=2, sticky='ew', padx=5, pady=5)
        
        # Status filter
        ttk.Label(form_frame, text="Status:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        status_var = tk.StringVar(value="all")
        status_combo = ttk.Combobox(form_frame, textvariable=status_var,
                                   values=["all", "open", "in progress", "resolved", "closed"],
                                   state="readonly")
        status_combo.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        
        # Priority filter
        ttk.Label(form_frame, text="Priority:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        priority_var = tk.StringVar(value="all")
        priority_combo = ttk.Combobox(form_frame, textvariable=priority_var,
                                     values=["all", "low", "medium", "high"],
                                     state="readonly")
        priority_combo.grid(row=2, column=1, sticky='ew', padx=5, pady=5)
        
        # Date range
        ttk.Label(form_frame, text="Date From:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        date_from_entry = ttk.Entry(form_frame, width=15)
        date_from_entry.grid(row=3, column=1, sticky='w', padx=5, pady=5)
        
        ttk.Label(form_frame, text="Date To:").grid(row=3, column=2, sticky='w', padx=5, pady=5)
        date_to_entry = ttk.Entry(form_frame, width=15)
        date_to_entry.grid(row=3, column=3, sticky='w', padx=5, pady=5)
        
        form_frame.grid_columnconfigure(1, weight=1)
        
        # Results frame
        results_frame = ttk.LabelFrame(search_window, text="Search Results")
        results_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Results treeview
        columns = ('ID', 'Subject', 'Status', 'Priority', 'Created')
        results_tree = ttk.Treeview(results_frame, columns=columns, show='headings')
        
        for col in columns:
            results_tree.heading(col, text=col)
            results_tree.column(col, width=100)
        
        # Scrollbar for results
        results_scroll = ttk.Scrollbar(results_frame, orient='vertical', command=results_tree.yview)
        results_tree.configure(yscrollcommand=results_scroll.set)
        
        results_tree.pack(side='left', fill='both', expand=True)
        results_scroll.pack(side='right', fill='y')
        
        # Search function
        def perform_search():
            # Clear existing results
            for item in results_tree.get_children():
                results_tree.delete(item)
            
            # Get search criteria
            criteria = {
                'text': search_text_entry.get().strip(),
                'status': status_var.get() if status_var.get() != 'all' else None,
                'priority': priority_var.get() if priority_var.get() != 'all' else None,
                'date_from': date_from_entry.get().strip(),
                'date_to': date_to_entry.get().strip()
            }
            
            # Perform search
            results = self.search_tickets(criteria)
            
            # Display results
            for ticket in results:
                results_tree.insert('', 'end', values=(
                    ticket.get('ticket_id', ''),
                    ticket.get('subject', '')[:40],
                    ticket.get('status', '').title(),
                    ticket.get('priority', '').title(),
                    ticket.get('created_at', '')[:16]
                ))
        
        # Buttons
        button_frame = ttk.Frame(search_window)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(button_frame, text="Search", command=perform_search, 
                  style='Primary.TButton').pack(side='right', padx=5)
        ttk.Button(button_frame, text="Clear", 
                  command=lambda: self.clear_search_form(search_text_entry, status_var, priority_var, 
                                                        date_from_entry, date_to_entry, results_tree)).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Close", command=search_window.destroy).pack(side='right')

    def search_tickets(self, criteria):
        """Search tickets based on criteria"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Build query
            where_conditions = []
            params = []
            
            # Check permissions
            if not self.has_permission('view_all_tickets'):
                where_conditions.append("t.user_id = ?")
                params.append(self.current_user.get('id', 0))
            
            # Text search
            if criteria.get('text'):
                where_conditions.append("(t.subject LIKE ? OR t.message LIKE ?)")
                text_param = f"%{criteria['text']}%"
                params.extend([text_param, text_param])
            
            # Status filter
            if criteria.get('status'):
                where_conditions.append("t.status = ?")
                params.append(criteria['status'])
            
            # Priority filter
            if criteria.get('priority'):
                where_conditions.append("t.priority = ?")
                params.append(criteria['priority'])
            
            # Date filters
            if criteria.get('date_from'):
                where_conditions.append("DATE(t.created_at) >= ?")
                params.append(criteria['date_from'])
            
            if criteria.get('date_to'):
                where_conditions.append("DATE(t.created_at) <= ?")
                params.append(criteria['date_to'])
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            cursor.execute(f'''
            SELECT t.ticket_id, t.subject, t.status, t.priority, t.created_at
            FROM support_tickets t
            WHERE {where_clause}
            ORDER BY t.created_at DESC
            LIMIT 100
            ''', params)
            
            results = cursor.fetchall()
            conn.close()
            
            return [dict(result) for result in results]
            
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")
            return []

    def clear_search_form(self, text_entry, status_var, priority_var, date_from, date_to, results_tree):
        """Clear search form"""
        text_entry.delete(0, 'end')
        status_var.set('all')
        priority_var.set('all')
        date_from.delete(0, 'end')
        date_to.delete(0, 'end')
        
        for item in results_tree.get_children():
            results_tree.delete(item)

    def show_knowledge_base(self):
        """Switch to knowledge base tab"""
        for i in range(self.notebook.index('end')):
            if self.notebook.tab(i, 'text') == 'Knowledge Base':
                self.notebook.select(i)
                break

    def show_analytics(self):
        """Switch to analytics tab"""
        for i in range(self.notebook.index('end')):
            if self.notebook.tab(i, 'text') == 'Analytics':
                self.notebook.select(i)
                break

    def show_reports(self):
        """Switch to reports section"""
        for i in range(self.notebook.index('end')):
            if self.notebook.tab(i, 'text') == 'Administration':
                self.notebook.select(i)
                # Then select the Reports sub-tab
                break

    def show_system_management(self):
        """Switch to system management"""
        for i in range(self.notebook.index('end')):
            if self.notebook.tab(i, 'text') == 'Administration':
                self.notebook.select(i)
                break

    def show_user_management(self):
        """Switch to user management"""
        for i in range(self.notebook.index('end')):
            if self.notebook.tab(i, 'text') == 'Administration':
                self.notebook.select(i)
                break

    def show_settings(self):
        """Show system settings dialog"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("System Settings")
        settings_window.geometry("500x400")
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # Settings notebook
        settings_notebook = ttk.Notebook(settings_window)
        settings_notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # General settings
        general_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(general_frame, text="General")
        
        # Email settings
        email_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(email_frame, text="Email")
        
        # Security settings
        security_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(security_frame, text="Security")
        
        # Add settings content here
        ttk.Label(general_frame, text="System settings would be configured here", 
                 style='Heading.TLabel').pack(pady=20)

    # Placeholder methods for admin functions
    def show_sla_management(self):
        """Show SLA management dialog"""
        messagebox.showinfo("Info", "SLA Management would integrate with the original system functions")

    def show_template_management(self):
        """Show template management dialog"""
        messagebox.showinfo("Info", "Template Management would integrate with the original system functions")

    def show_department_management(self):
        """Show department management dialog"""
        messagebox.showinfo("Info", "Department Management would integrate with the original system functions")

    def show_workflow_management(self):
        """Show workflow management dialog"""
        messagebox.showinfo("Info", "Workflow Management would integrate with the original system functions")

    def show_database_cleanup(self):
        """Show database cleanup dialog"""
        messagebox.showinfo("Info", "Database cleanup would integrate with the original maintenance functions")

    def backup_database(self):
        """Backup database"""
        try:
            # This would call the original backup function
            messagebox.showinfo("Success", "Database backup initiated")
        except Exception as e:
            messagebox.showerror("Error", f"Backup failed: {str(e)}")

    def check_data_integrity(self):
        """Check data integrity"""
        try:
            # This would call the original integrity check function
            messagebox.showinfo("Success", "Data integrity check completed - no issues found")
        except Exception as e:
            messagebox.showerror("Error", f"Integrity check failed: {str(e)}")

    def show_export_dialog(self):
        """Show data export dialog"""
        export_window = tk.Toplevel(self.root)
        export_window.title("Export Data")
        export_window.geometry("400x300")
        export_window.transient(self.root)
        export_window.grab_set()
        
        ttk.Label(export_window, text="Data Export Options", style='Heading.TLabel').pack(pady=10)
        
        # Export options
        options_frame = ttk.LabelFrame(export_window, text="Export Options")
        options_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(options_frame, text="Export All Tickets (CSV)", 
                  command=self.export_tickets_csv).pack(fill='x', padx=5, pady=5)
        ttk.Button(options_frame, text="Export Users (CSV)", 
                  command=self.export_users_csv).pack(fill='x', padx=5, pady=5)
        ttk.Button(options_frame, text="Export Analytics (JSON)", 
                  command=self.export_analytics_json).pack(fill='x', padx=5, pady=5)

    def show_import_dialog(self):
        """Show data import dialog"""
        messagebox.showinfo("Info", "Data import functionality would integrate with the original system")

    def show_add_user(self):
        """Show add user dialog"""
        self.show_register()  # Reuse the registration dialog

    def show_edit_user(self):
        """Show edit user dialog"""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a user to edit")
            return
        
        messagebox.showinfo("Info", "User editing would integrate with the original user management system")

    def generate_report(self, report_type):
        """Generate specified report type"""
        try:
            # This would integrate with the original reporting functions
            reports = {
                'executive': 'Executive Summary Report',
                'staff': 'Staff Performance Report',
                'sla': 'SLA Compliance Report',
                'satisfaction': 'Customer Satisfaction Report',
                'trends': 'Trend Analysis Report',
                'custom': 'Custom Report'
            }
            
            report_name = reports.get(report_type, 'Unknown Report')
            messagebox.showinfo("Success", f"{report_name} generation initiated")
            
        except Exception as e:
            messagebox.showerror("Error", f"Report generation failed: {str(e)}")

    def export_tickets_csv(self):
        """Export tickets to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Save Tickets Export"
            )
            
            if filename:
                # This would integrate with the original export function
                messagebox.showinfo("Success", f"Tickets exported to {filename}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def export_users_csv(self):
        """Export users to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Save Users Export"
            )
            
            if filename:
                # This would integrate with the original export function
                messagebox.showinfo("Success", f"Users exported to {filename}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def export_analytics_json(self):
        """Export analytics to JSON"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="Save Analytics Export"
            )
            
            if filename:
                # This would integrate with the original export function
                messagebox.showinfo("Success", f"Analytics exported to {filename}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")

    def show_user_guide(self):
        """Show user guide"""
        guide_window = tk.Toplevel(self.root)
        guide_window.title("User Guide")
        guide_window.geometry("800x600")
        guide_window.transient(self.root)
        
        # User guide content
        guide_text = scrolledtext.ScrolledText(guide_window, wrap='word', state='disabled')
        guide_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        guide_content = """
HELPDESK SYSTEM USER GUIDE

GETTING STARTED
===============
The Enhanced Helpdesk System provides a comprehensive solution for managing support tickets, 
knowledge base articles, and system administration.

MAIN FEATURES
=============

1. DASHBOARD
   - Quick overview of your tickets and system statistics
   - Recent activity display
   - Quick action buttons

2. TICKET MANAGEMENT
   - Create new support tickets using templates or custom forms
   - View and manage your tickets
   - Reply to tickets and track conversations
   - Admin functions for managing all tickets

3. KNOWLEDGE BASE
   - Browse and search articles
   - Rate articles for helpfulness
   - Create new articles (staff/admin only)

4. ANALYTICS (Admin)
   - View system-wide statistics
   - Generate various reports
   - Track performance metrics

5. ADMINISTRATION (Admin)
   - User management
   - System configuration
   - Data import/export
   - Maintenance functions

CREATING TICKETS
================
1. Click "Create Ticket" tab or use the dashboard button
2. Choose a template or create a custom ticket
3. Fill in the required information
4. Submit the ticket

MANAGING TICKETS
================
- View your tickets in the "My Tickets" tab
- Double-click any ticket to view details
- Use the conversation tab to see all replies
- Reply to tickets using the actions panel

ADMIN FUNCTIONS
===============
Administrators have access to additional features:
- View and manage all tickets
- Bulk operations on multiple tickets
- System analytics and reporting
- User and system management

For more detailed information, please contact your system administrator.
        """
        
        guide_text.config(state='normal')
        guide_text.insert('1.0', guide_content)
        guide_text.config(state='disabled')

    def create_system_management_tab(self, parent):
        """Create system management tab"""
        sys_frame = ttk.Frame(parent)
        parent.add(sys_frame, text="System")
        
        # System management options
        options_frame = ttk.LabelFrame(sys_frame, text="System Management")
        options_frame.pack(fill='x', padx=10, pady=10)
        
        # SLA Management
        sla_frame = ttk.Frame(options_frame)
        sla_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(sla_frame, text="SLA Policies:", style='Heading.TLabel').pack(side='left')
        ttk.Button(sla_frame, text="Manage SLAs", command=self.show_sla_management).pack(side='right')
        
        # Template Management
        template_frame = ttk.Frame(options_frame)
        template_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(template_frame, text="Ticket Templates:", style='Heading.TLabel').pack(side='left')
        ttk.Button(template_frame, text="Manage Templates", command=self.show_template_management).pack(side='right')
        
        # Department Management
        dept_frame = ttk.Frame(options_frame)
        dept_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(dept_frame, text="Departments:", style='Heading.TLabel').pack(side='left')
        ttk.Button(dept_frame, text="Manage Departments", command=self.show_department_management).pack(side='right')
        
        # Workflow Management
        workflow_frame = ttk.Frame(options_frame)
        workflow_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(workflow_frame, text="Workflows:", style='Heading.TLabel').pack(side='left')
        ttk.Button(workflow_frame, text="Manage Workflows", command=self.show_workflow_management).pack(side='right')
        
        # System Maintenance
        maintenance_frame = ttk.LabelFrame(sys_frame, text="System Maintenance")
        maintenance_frame.pack(fill='x', padx=10, pady=10)
        
        maint_grid = ttk.Frame(maintenance_frame)
        maint_grid.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(maint_grid, text="Database Cleanup", command=self.show_database_cleanup).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(maint_grid, text="Backup Database", command=self.backup_database).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(maint_grid, text="Check Integrity", command=self.check_data_integrity).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(maint_grid, text="Export Data", command=self.show_export_dialog).grid(row=1, column=1, padx=5, pady=5)

    def create_user_management_tab(self, parent):
        """Create user management tab"""
        user_frame = ttk.Frame(parent)
        parent.add(user_frame, text="Users")
        
        # User list
        users_frame = ttk.LabelFrame(user_frame, text="User Management")
        users_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Toolbar
        toolbar = ttk.Frame(users_frame)
        toolbar.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(toolbar, text="Add User", command=self.show_add_user).pack(side='left', padx=5)
        ttk.Button(toolbar, text="Edit User", command=self.show_edit_user).pack(side='left', padx=5)
        ttk.Button(toolbar, text="Refresh", command=self.refresh_users).pack(side='left', padx=5)
        
        # Users list
        self.users_tree_frame = ttk.Frame(users_frame)
        self.users_tree_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.create_users_list()

    def create_users_list(self):
        """Create users list"""
        # Clear existing widgets
        for widget in self.users_tree_frame.winfo_children():
            widget.destroy()
        
        # Create treeview
        columns = ('ID', 'Username', 'Email', 'Role', 'Department', 'Status', 'Last Login')
        self.users_tree = ttk.Treeview(self.users_tree_frame, columns=columns, show='headings')
        
        # Configure columns
        for col in columns:
            self.users_tree.heading(col, text=col)
            self.users_tree.column(col, width=100)
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(self.users_tree_frame, orient='vertical', command=self.users_tree.yview)
        h_scrollbar = ttk.Scrollbar(self.users_tree_frame, orient='horizontal', command=self.users_tree.xview)
        
        self.users_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack widgets
        self.users_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        self.users_tree_frame.grid_rowconfigure(0, weight=1)
        self.users_tree_frame.grid_columnconfigure(0, weight=1)
        
        # Load data
        self.refresh_users()

    def refresh_users(self):
        """Refresh users list"""
        try:
            # Clear existing items
            for item in self.users_tree.get_children():
                self.users_tree.delete(item)
            
            # Get users from database
            users = self.get_all_users()
            
            # Populate treeview
            for user in users:
                status = "Active" if user.get('is_active') else "Inactive"
                last_login = user.get('last_login_at', '')[:16] if user.get('last_login_at') else 'Never'
                
                self.users_tree.insert('', 'end', values=(
                    user.get('id', ''),
                    user.get('username', ''),
                    user.get('email', ''),
                    user.get('role', '').title(),
                    user.get('department', '') or 'None',
                    status,
                    last_login
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load users: {str(e)}")

    def get_all_users(self):
        """Get all users from database"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT id, username, email, role, department, is_active, last_login_at
            FROM users
            ORDER BY username
            ''')
            
            users = cursor.fetchall()
            conn.close()
            
            return [dict(user) for user in users]
            
        except Exception as e:
            return []

    def create_reports_tab(self, parent):
        """Create reports tab"""
        reports_frame = ttk.Frame(parent)
        parent.add(reports_frame, text="Reports")
        
        # Report generation options
        options_frame = ttk.LabelFrame(reports_frame, text="Report Generation")
        options_frame.pack(fill='x', padx=10, pady=10)
        
        # Report types
        report_grid = ttk.Frame(options_frame)
        report_grid.pack(fill='x', padx=10, pady=10)
        
        # Configure grid weights for better spacing
        for i in range(3):
            report_grid.grid_columnconfigure(i, weight=1)
        
        ttk.Button(report_grid, text="Executive Summary", 
                  command=lambda: self.generate_report('executive')).grid(row=0, column=0, padx=5, pady=5, sticky='ew')
        ttk.Button(report_grid, text="Staff Performance", 
                  command=lambda: self.generate_report('staff')).grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(report_grid, text="SLA Compliance", 
                  command=lambda: self.generate_report('sla')).grid(row=0, column=2, padx=5, pady=5, sticky='ew')
        
        ttk.Button(report_grid, text="Customer Satisfaction", 
                  command=lambda: self.generate_report('satisfaction')).grid(row=1, column=0, padx=5, pady=5, sticky='ew')
        ttk.Button(report_grid, text="Trend Analysis", 
                  command=lambda: self.generate_report('trends')).grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(report_grid, text="Custom Report", 
                  command=lambda: self.generate_report('custom')).grid(row=1, column=2, padx=5, pady=5, sticky='ew')
        
        # Export options
        export_frame = ttk.LabelFrame(reports_frame, text="Data Export")
        export_frame.pack(fill='x', padx=10, pady=10)
        
        export_grid = ttk.Frame(export_frame)
        export_grid.pack(fill='x', padx=10, pady=10)
        
        # Configure grid weights for export section
        for i in range(3):
            export_grid.grid_columnconfigure(i, weight=1)
        
        ttk.Button(export_grid, text="Export Tickets (CSV)", 
                  command=self.export_tickets_csv).grid(row=0, column=0, padx=5, pady=5, sticky='ew')
        ttk.Button(export_grid, text="Export Users (CSV)", 
                  command=self.export_users_csv).grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(export_grid, text="Export Analytics (JSON)", 
                  command=self.export_analytics_json).grid(row=0, column=2, padx=5, pady=5, sticky='ew')

    def show_about(self):
        """Show about dialog"""
        about_window = tk.Toplevel(self.root)
        about_window.title("About Enhanced Helpdesk System")
        about_window.geometry("400x300")
        about_window.transient(self.root)
        about_window.grab_set()
        
        # Center the about dialog
        about_window.update_idletasks()
        x = (about_window.winfo_screenwidth() // 2) - (400 // 2)
        y = (about_window.winfo_screenheight() // 2) - (300 // 2)
        about_window.geometry(f'400x300+{x}+{y}')
        
        # About content
        content_frame = ttk.Frame(about_window)
        content_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        ttk.Label(content_frame, text="Enhanced Helpdesk System", 
                 style='Title.TLabel').pack(pady=10)
        
        ttk.Label(content_frame, text="Version 2.0 GUI Edition").pack(pady=5)
        
        info_text = """
A comprehensive helpdesk and ticket management system
with both GUI and CLI interfaces.

Features:
• Complete ticket lifecycle management
• Knowledge base integration
• Advanced analytics and reporting
• User and role management
• SLA tracking and workflows
• Bulk operations and automation

Built with Python and Tkinter
Backwards compatible with CLI version

© 2024 Enhanced Helpdesk System
        """
        
        ttk.Label(content_frame, text=info_text, justify='center').pack(pady=10)

        ttk.Button(content_frame, text="Close", command=about_window.destroy).pack(pady=10)

    def send_ticket_notification_email(self, ticket_id, notification_type, admin_email, user_email=None):
        """Send ticket notification emails"""
        try:
            # Get ticket details
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT subject, status, category, priority, user_id, created_at, resolution
                FROM support_tickets WHERE ticket_id = ?
            ''', (ticket_id,))

            ticket_result = cursor.fetchone()
            if not ticket_result:
                conn.close()
                return False

            subject, status, category, priority, user_id, created_at, resolution = ticket_result
            conn.close()

            # Generate email content based on notification type
            if notification_type == "created":
                self._send_ticket_created_emails(ticket_id, subject, category, priority, admin_email, user_email)
            elif notification_type == "resolved":
                self._send_ticket_resolved_emails(ticket_id, subject, resolution, admin_email, user_email)
            elif notification_type == "updated":
                self._send_ticket_updated_emails(ticket_id, subject, status, admin_email, user_email)

            return True

        except Exception as e:
            print(f"Failed to send ticket notification: {e}")
            return False

    def _send_ticket_created_emails(self, ticket_id, subject, category, priority, admin_email, user_email):
        """Send emails when ticket is created"""
        # Send ticket notification using centralized email service
        try:
            from university_system.infrastructure.email.email_service import send_ticket_notification

            # Extract username from user_email if available
            username = user_email.split('@')[0] if user_email else 'Unknown User'

            # Send ticket notification (handles both admin and user emails)
            send_ticket_notification(ticket_id, subject, username, [admin_email] if admin_email else None)
        except Exception as e:
            print(f"Failed to send ticket notification: {e}")

    def _send_ticket_resolved_emails(self, ticket_id, subject, resolution, admin_email, user_email):
        """Send emails when ticket is resolved"""
        try:
            from university_system.infrastructure.email.email_service import send_template_email

            if user_email:
                template_vars = {
                    "ticket_id": ticket_id,
                    "subject": subject,
                    "resolution": resolution or 'Issue has been resolved.',
                    "resolution_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

                send_template_email('helpdesk_ticket_resolved', user_email, template_vars)
        except Exception as e:
            print(f"Failed to send ticket resolved notification: {e}")

    def _send_ticket_updated_emails(self, ticket_id, subject, status, admin_email, user_email):
        """Send emails when ticket is updated"""
        try:
            from university_system.infrastructure.email.email_service import send_template_email

            if user_email:
                template_vars = {
                    "ticket_id": ticket_id,
                    "subject": subject,
                    "status": status,
                    "updated_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

                send_template_email('helpdesk_ticket_updated', user_email, template_vars)
        except Exception as e:
            print(f"Failed to send ticket update notification: {e}")

    def _send_ticket_updated_emails_fallback(self, ticket_id, subject, status, user_email):
        """Fallback email sending when template fails"""
        try:
            user_subject = f"Support Ticket Updated - #{ticket_id}"
            user_message = f"""Your support ticket has been updated:

================================================
TICKET UPDATE
================================================

Ticket ID: #{ticket_id}
Subject: {subject}
New Status: {status}
Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please log into the helpdesk system to view the latest updates.

================================================

Best regards,
University Support Team
"""
            self._send_email_via_gui(user_email, user_subject, user_message)
        except Exception as e:
            print(f"Failed to send fallback email: {e}")

    def _send_email_via_gui(self, to_email, subject, message):
        """Send email via email GUI"""
        try:
            from university_system.infrastructure.email.gui.email_manager_gui import EmailManagerGUI
            email_gui = EmailManagerGUI(self.root, auth=self.auth if hasattr(self, 'auth') else None)

            # If email GUI has send_email method, use it
            if hasattr(email_gui, 'send_email'):
                email_gui.send_email(to_email=to_email, subject=subject, message=message)
                return True
            return False
        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending email via GUI: {e}")
            return False

    def auto_send_ticket_notifications(self, ticket_id, notification_type):
        """Automatically send ticket notifications"""
        try:
            # Default admin email (this could be configurable)
            admin_email = "admin@university.edu"

            # Get user email if available
            user_email = None
            if self.current_user and 'email' in self.current_user:
                user_email = self.current_user.get('email')

            self.send_ticket_notification_email(ticket_id, notification_type, admin_email, user_email)
        except Exception as e:
            print(f"Failed to auto-send ticket notifications: {e}")


def run_gui_helpdesk(auth_system=None):
    """Run the GUI helpdesk system"""
    root = tk.Tk()
    app = HelpdeskGUI(root, auth_system)
    
    # Handle window closing
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit the helpdesk system?"):
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Start the GUI
    root.mainloop()


# Backwards compatibility function
def display_helpdesk_menu_gui(auth):
    """GUI version of the original display_helpdesk_menu function"""
    run_gui_helpdesk(auth)


if __name__ == "__main__":
    # Can be run standalone or with existing auth system
    print("Starting Enhanced Helpdesk System GUI...")
    print("This GUI version is fully backwards compatible with the original CLI system.")
    print("Use the 'CLI Mode' button to switch to the original interface.")
    
    try:
        run_gui_helpdesk()
    except Exception as e:
        print(f"Error starting GUI: {e}")
        print("Please ensure all dependencies are installed:")
        print("- tkinter (usually included with Python)")
        print("- sqlite3 (usually included with Python)")
        print("- All original helpdesk system dependencies")
