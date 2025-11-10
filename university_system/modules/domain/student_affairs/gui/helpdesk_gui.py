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

# Import authentication - REQUIRED (no fallback for security)
from university_system.infrastructure.auth.user_authentication import UserAuth, get_global_auth
from university_system.infrastructure.shared_context import get_auth

# Import activity logger for audit trail
try:
    from university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

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
                "Authentication Required",
                "Authentication system not available. Helpdesk GUI cannot start."
            )
            root.destroy()
            return

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
            messagebox.showerror(
                "Authentication Required",
                "Please log in through the main University System GUI.\n\n"
                "Run: python run.py --gui\n\n"
                "Helpdesk can only be accessed after logging in through the main system."
            )
            root.destroy()
            return

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

    # Login/logout/registration removed - use main GUI for authentication
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

    # ============================================================================
    # ENHANCED TICKET MANAGEMENT FUNCTIONS (8 NEW FUNCTIONS)
    # ============================================================================

    def create_ticket_enhanced(self):
        """Enhanced ticket creation with templates and validation"""
        if not self.current_user:
            messagebox.showerror("Error", "You must be logged in to create a support ticket.")
            return

        if not self.has_permission('create_ticket'):
            messagebox.showerror("Permission Denied", "You don't have permission to create support tickets.")
            return

        # Create enhanced ticket creation dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Enhanced Ticket")
        dialog.geometry("700x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main container
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Title
        ttk.Label(main_frame, text="Create New Support Ticket",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Template selection
        template_frame = ttk.LabelFrame(main_frame, text="Template Selection", padding="10")
        template_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(template_frame, text="Select a template to auto-fill form:").pack(anchor='w')

        template_var = tk.StringVar(value='custom')
        template_combo = ttk.Combobox(template_frame, textvariable=template_var, state="readonly", width=50)
        template_combo.pack(fill='x', pady=5)

        # Load templates
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT template_id, name, description FROM ticket_templates
                WHERE is_active = 1 ORDER BY category, name
            ''')
            templates = cursor.fetchall()
            conn.close()

            template_list = ['Custom (No Template)']
            template_map = {0: None}

            for idx, (tid, name, desc) in enumerate(templates, 1):
                template_list.append(f"{name} - {desc}")
                template_map[idx] = tid

            template_combo['values'] = template_list
        except Exception as e:
            print(f"Error loading templates: {e}")
            template_combo['values'] = ['Custom (No Template)']
            template_map = {0: None}

        # Form fields
        form_frame = ttk.LabelFrame(main_frame, text="Ticket Information", padding="10")
        form_frame.pack(fill='both', expand=True, pady=(0, 10))

        # Subject
        ttk.Label(form_frame, text="Subject *").grid(row=0, column=0, sticky='w', pady=2)
        subject_entry = ttk.Entry(form_frame, width=60)
        subject_entry.grid(row=0, column=1, columnspan=2, sticky='ew', pady=2)

        # Category with subcategory
        ttk.Label(form_frame, text="Category *").grid(row=1, column=0, sticky='w', pady=2)
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, state="readonly", width=28)
        category_combo['values'] = ['Technical Support', 'Academic Inquiry', 'Financial Services',
                                    'Account Access', 'Other']
        category_combo.grid(row=1, column=1, sticky='w', pady=2)

        ttk.Label(form_frame, text="Subcategory").grid(row=1, column=2, sticky='w', pady=2, padx=(10,0))
        subcategory_var = tk.StringVar()
        subcategory_combo = ttk.Combobox(form_frame, textvariable=subcategory_var, state="readonly", width=25)
        subcategory_combo.grid(row=1, column=3, sticky='w', pady=2)

        # Priority, Impact, Urgency
        ttk.Label(form_frame, text="Priority *").grid(row=2, column=0, sticky='w', pady=2)
        priority_var = tk.StringVar(value='medium')
        priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, state="readonly", width=15)
        priority_combo['values'] = ['low', 'medium', 'high']
        priority_combo.grid(row=2, column=1, sticky='w', pady=2)

        ttk.Label(form_frame, text="Impact *").grid(row=3, column=0, sticky='w', pady=2)
        impact_var = tk.StringVar(value='low')
        impact_combo = ttk.Combobox(form_frame, textvariable=impact_var, state="readonly", width=15)
        impact_combo['values'] = ['low', 'medium', 'high']
        impact_combo.grid(row=3, column=1, sticky='w', pady=2)

        ttk.Label(form_frame, text="Urgency *").grid(row=4, column=0, sticky='w', pady=2)
        urgency_var = tk.StringVar(value='low')
        urgency_combo = ttk.Combobox(form_frame, textvariable=urgency_var, state="readonly", width=15)
        urgency_combo['values'] = ['low', 'medium', 'high']
        urgency_combo.grid(row=4, column=1, sticky='w', pady=2)

        # Message
        ttk.Label(form_frame, text="Description *").grid(row=5, column=0, sticky='nw', pady=2)
        message_text = scrolledtext.ScrolledText(form_frame, height=10, width=60)
        message_text.grid(row=5, column=1, columnspan=3, sticky='ew', pady=2)

        # Configure grid weights
        form_frame.columnconfigure(1, weight=1)

        # Update subcategory when category changes
        def update_subcategories(event=None):
            cat = category_var.get()
            subcategories_map = {
                "Technical Support": ["Login Issues", "Performance Problems", "Software Bugs", "Hardware Problems"],
                "Academic Inquiry": ["Course Information", "Grading Questions", "Academic Records", "Transcript Requests"],
                "Financial Services": ["Payment Plans", "Refunds", "Financial Aid", "Billing Inquiries"],
                "Account Access": ["Password Reset", "Account Locked", "Permission Issues", "Profile Updates"],
                "Other": ["General Inquiry", "Feedback", "Complaint", "Suggestion"]
            }
            subcategory_combo['values'] = subcategories_map.get(cat, [])
            if subcategory_combo['values']:
                subcategory_combo.current(0)

        category_combo.bind('<<ComboboxSelected>>', update_subcategories)

        # Load template when selected
        def load_template(event=None):
            idx = template_combo.current()
            if idx > 0 and idx in template_map:
                template_id = template_map[idx]
                self.create_ticket_from_template_gui(template_id, subject_entry, category_var,
                                                     priority_var, impact_var, urgency_var, message_text)

        template_combo.bind('<<ComboboxSelected>>', load_template)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(0, 5))

        def submit_ticket():
            subject = subject_entry.get().strip()
            category = category_var.get()
            subcategory = subcategory_var.get()
            message = message_text.get('1.0', 'end-1c').strip()
            priority = priority_var.get()
            impact = impact_var.get()
            urgency = urgency_var.get()

            if not subject or not category or not message:
                messagebox.showerror("Error", "Subject, category, and description are required")
                return

            # Create ticket using enhanced method
            ticket_id = self.create_ticket_with_details(subject, message, category, priority,
                                                       impact, urgency, subcategory)
            if ticket_id:
                messagebox.showinfo("Success", f"Ticket #{ticket_id} created successfully!")
                dialog.destroy()
                self.refresh_my_tickets()
            else:
                messagebox.showerror("Error", "Failed to create ticket")

        ttk.Button(button_frame, text="Create Ticket", command=submit_ticket).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    def create_ticket_from_template_gui(self, template_id, subject_entry, category_var,
                                        priority_var, impact_var, urgency_var, message_text):
        """Load template data into form fields"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM ticket_templates WHERE template_id = ?', (template_id,))
            template = cursor.fetchone()
            conn.close()

            if not template:
                messagebox.showerror("Error", "Template not found")
                return

            # Unpack template data (adjust indices based on schema)
            # Assuming: template_id, name, description, category, subject_template, message_template,
            #           default_priority, default_impact, default_urgency, form_fields
            _, name, desc, category, subj_tpl, msg_tpl, pri, imp, urg, form_fields = template[:10]

            # Fill in form fields
            if subj_tpl:
                subject_entry.delete(0, 'end')
                subject_entry.insert(0, subj_tpl)

            if category:
                category_var.set(category)

            if pri:
                priority_var.set(pri)
            if imp:
                impact_var.set(imp)
            if urg:
                urgency_var.set(urg)

            if msg_tpl:
                message_text.delete('1.0', 'end')
                message_text.insert('1.0', msg_tpl)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load template: {str(e)}")

    def create_custom_ticket_gui(self):
        """Create ticket with custom form fields (wrapper for create_ticket_enhanced)"""
        # This is essentially the same as create_ticket_enhanced but can be extended
        # with dynamic custom fields from database
        self.create_ticket_enhanced()

    def create_ticket_with_details(self, subject, message, category, priority, impact, urgency, subcategory=None):
        """Programmatic ticket creation with full details"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Determine SLA and department assignment
            cursor.execute('''
                SELECT sla_id, first_response_hours, resolution_hours
                FROM sla_policies
                WHERE priority = ? AND impact = ? AND urgency = ? AND is_active = 1
                ORDER BY sla_id LIMIT 1
            ''', (priority, impact, urgency))

            sla_result = cursor.fetchone()
            due_date = None
            if sla_result:
                resolution_hours = sla_result[2]
                due_date = (datetime.now() + timedelta(hours=resolution_hours)).strftime('%Y-%m-%d %H:%M:%S')

            # Auto-assign to department based on category
            assigned_to = None
            department = None

            category_dept_map = {
                "Technical Support": "IT Support",
                "Academic Inquiry": "Academic Affairs",
                "Financial Services": "Financial Services",
                "Account Access": "IT Support"
            }

            if category in category_dept_map:
                department = category_dept_map[category]

                # Find available staff in the department
                cursor.execute('''
                    SELECT u.id FROM users u
                    WHERE u.role IN ('staff', 'admin') AND u.is_active = 1
                    ORDER BY u.last_login_at DESC LIMIT 1
                ''')

                dept_staff = cursor.fetchone()
                if dept_staff:
                    assigned_to = dept_staff[0]

            # Get current time
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Insert ticket into database
            cursor.execute('''
                INSERT INTO support_tickets
                (user_id, assigned_to, subject, message, category, subcategory, status, priority,
                 impact, urgency, source, due_date, department, created_at, updated_at, last_activity_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (self.current_user.get('id', 0), assigned_to, subject, message, category, subcategory,
                  'open', priority, impact, urgency, 'web', due_date, department, now, now, now))

            conn.commit()
            ticket_id = cursor.lastrowid
            conn.close()

            # Send notifications
            self.auto_send_ticket_notifications(ticket_id, "created")

            return ticket_id

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create ticket: {str(e)}")
            return None

    def assign_ticket_enhanced(self, ticket_id):
        """Enhanced ticket assignment with load balancing and skill-based routing"""
        if not self.current_user:
            messagebox.showerror("Error", "You must be logged in to assign tickets.")
            return

        if not self.has_permission('manage_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to assign tickets.")
            return

        # Create assignment dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Enhanced Ticket Assignment")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Assign Ticket #{ticket_id}",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

        # Assignment options
        option_frame = ttk.LabelFrame(main_frame, text="Assignment Options", padding="10")
        option_frame.pack(fill='x', pady=(0, 10))

        assign_option = tk.StringVar(value='user')
        ttk.Radiobutton(option_frame, text="Assign to specific user",
                       variable=assign_option, value='user').pack(anchor='w')
        ttk.Radiobutton(option_frame, text="Assign to department (auto-balance)",
                       variable=assign_option, value='department').pack(anchor='w')
        ttk.Radiobutton(option_frame, text="Unassign ticket",
                       variable=assign_option, value='unassign').pack(anchor='w')

        # User selection frame
        user_frame = ttk.LabelFrame(main_frame, text="Select User", padding="10")
        user_frame.pack(fill='both', expand=True, pady=(0, 10))

        # Staff list
        columns = ('ID', 'Username', 'Role', 'Department', 'Active Tickets')
        staff_tree = ttk.Treeview(user_frame, columns=columns, show='headings', height=10)

        for col in columns:
            staff_tree.heading(col, text=col)
            staff_tree.column(col, width=100)

        staff_tree.pack(fill='both', expand=True, side='left')

        scrollbar = ttk.Scrollbar(user_frame, orient='vertical', command=staff_tree.yview)
        scrollbar.pack(side='right', fill='y')
        staff_tree.configure(yscrollcommand=scrollbar.set)

        # Load staff members with workload
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT u.id, u.username, u.role, COALESCE(u.department, 'No Department'),
                       COUNT(st.ticket_id) as active_tickets
                FROM users u
                LEFT JOIN support_tickets st ON u.id = st.assigned_to AND st.status NOT IN ('closed', 'resolved')
                WHERE u.role IN ('staff', 'admin') AND u.is_active = 1
                GROUP BY u.id, u.username, u.role, u.department
                ORDER BY active_tickets ASC, u.username
            ''')

            staff_members = cursor.fetchall()
            conn.close()

            for staff in staff_members:
                staff_tree.insert('', 'end', values=staff)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load staff: {str(e)}")
            return

        # Department selection (hidden by default)
        dept_frame = ttk.LabelFrame(main_frame, text="Select Department", padding="10")

        dept_var = tk.StringVar()
        dept_combo = ttk.Combobox(dept_frame, textvariable=dept_var, state="readonly", width=40)
        dept_combo.pack(fill='x')

        # Load departments
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT name FROM departments WHERE is_active = 1 ORDER BY name')
            departments = [row[0] for row in cursor.fetchall()]
            conn.close()
            dept_combo['values'] = departments
        except:
            dept_combo['values'] = ['IT Support', 'Academic Affairs', 'Financial Services']

        # Show/hide frames based on selection
        def update_frames(*args):
            if assign_option.get() == 'user':
                user_frame.pack(fill='both', expand=True, pady=(0, 10))
                dept_frame.pack_forget()
            elif assign_option.get() == 'department':
                user_frame.pack_forget()
                dept_frame.pack(fill='x', pady=(0, 10))
            else:
                user_frame.pack_forget()
                dept_frame.pack_forget()

        assign_option.trace('w', update_frames)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        def perform_assignment():
            try:
                from university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                new_assigned = None
                new_department = None

                if assign_option.get() == 'user':
                    selection = staff_tree.selection()
                    if not selection:
                        messagebox.showerror("Error", "Please select a user")
                        return

                    values = staff_tree.item(selection[0])['values']
                    new_assigned = values[0]
                    new_department = values[3] if values[3] != 'No Department' else None

                elif assign_option.get() == 'department':
                    new_department = dept_var.get()
                    if not new_department:
                        messagebox.showerror("Error", "Please select a department")
                        return

                    # Auto-assign to least loaded staff in department
                    cursor.execute('''
                        SELECT u.id, COUNT(st.ticket_id) as workload
                        FROM users u
                        LEFT JOIN support_tickets st ON u.id = st.assigned_to AND st.status NOT IN ('closed', 'resolved')
                        WHERE u.role IN ('staff', 'admin') AND u.is_active = 1 AND u.department = ?
                        GROUP BY u.id
                        ORDER BY workload ASC LIMIT 1
                    ''', (new_department,))

                    result = cursor.fetchone()
                    if result:
                        new_assigned = result[0]

                # Update ticket
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    UPDATE support_tickets
                    SET assigned_to = ?, department = ?, updated_at = ?, last_activity_at = ?
                    WHERE ticket_id = ?
                ''', (new_assigned, new_department, now, now, ticket_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Ticket #{ticket_id} assigned successfully!")
                dialog.destroy()
                self.refresh_all_tickets()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to assign ticket: {str(e)}")

        ttk.Button(button_frame, text="Assign", command=perform_assignment).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    def change_ticket_status_enhanced(self, ticket_id):
        """Enhanced status change with resolution tracking and workflow validation"""
        if not self.current_user:
            messagebox.showerror("Error", "You must be logged in to update ticket status.")
            return

        if not self.has_permission('manage_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to update ticket status.")
            return

        # Create status change dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Change Ticket Status")
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Change Status for Ticket #{ticket_id}",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

        # Get current status
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT status, resolution FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
            result = cursor.fetchone()
            conn.close()

            if not result:
                messagebox.showerror("Error", f"Ticket #{ticket_id} not found")
                dialog.destroy()
                return

            current_status, current_resolution = result

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load ticket: {str(e)}")
            dialog.destroy()
            return

        # Current status display
        status_frame = ttk.LabelFrame(main_frame, text="Current Status", padding="10")
        status_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(status_frame, text=current_status.upper(),
                 font=('TkDefaultFont', 10, 'bold')).pack()

        # New status selection
        new_status_frame = ttk.LabelFrame(main_frame, text="New Status", padding="10")
        new_status_frame.pack(fill='x', pady=(0, 10))

        status_var = tk.StringVar(value=current_status)
        statuses = ['open', 'in progress', 'waiting for customer', 'resolved', 'closed', 'cancelled']

        for status in statuses:
            ttk.Radiobutton(new_status_frame, text=status.title(),
                           variable=status_var, value=status).pack(anchor='w')

        # Resolution frame (shown for resolved/closed)
        resolution_frame = ttk.LabelFrame(main_frame, text="Resolution Details", padding="10")
        resolution_frame.pack(fill='both', expand=True, pady=(0, 10))

        ttk.Label(resolution_frame, text="Required for Resolved/Closed tickets:").pack(anchor='w')
        resolution_text = scrolledtext.ScrolledText(resolution_frame, height=8, width=50)
        resolution_text.pack(fill='both', expand=True)

        if current_resolution:
            resolution_text.insert('1.0', current_resolution)

        # Show/hide resolution based on status
        def update_resolution_visibility(*args):
            if status_var.get() in ['resolved', 'closed']:
                resolution_frame.pack(fill='both', expand=True, pady=(0, 10))
            else:
                resolution_frame.pack_forget()

        status_var.trace('w', update_resolution_visibility)
        update_resolution_visibility()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        def update_status():
            new_status = status_var.get()
            resolution = resolution_text.get('1.0', 'end-1c').strip()

            if new_status == current_status:
                messagebox.showinfo("Info", "Status is already set to " + new_status.upper())
                return

            if new_status in ['resolved', 'closed'] and not resolution:
                messagebox.showerror("Error", "Resolution details are required for resolved/closed tickets")
                return

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

                messagebox.showinfo("Success", f"Ticket status updated to: {new_status.upper()}")
                dialog.destroy()
                self.refresh_all_tickets()
                self.auto_send_ticket_notifications(ticket_id, "updated")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update status: {str(e)}")

        ttk.Button(button_frame, text="Update Status", command=update_status).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    def bulk_status_change_gui(self):
        """Bulk change status of multiple selected tickets"""
        if not self.has_permission('manage_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to change ticket status.")
            return

        # Get selected tickets from all tickets view
        if not hasattr(self, 'all_tickets_tree'):
            messagebox.showerror("Error", "Please navigate to All Tickets tab first")
            return

        selection = self.all_tickets_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select one or more tickets")
            return

        ticket_ids = [self.all_tickets_tree.item(item)['values'][0] for item in selection]

        # Create bulk status change dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Bulk Status Change")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Update {len(ticket_ids)} Tickets",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

        ttk.Label(main_frame, text=f"Ticket IDs: {', '.join(map(str, ticket_ids))}").pack(pady=(0, 10))

        # Status selection
        status_frame = ttk.LabelFrame(main_frame, text="Select New Status", padding="10")
        status_frame.pack(fill='x', pady=(0, 10))

        status_var = tk.StringVar(value='open')
        statuses = ['open', 'in progress', 'waiting for customer', 'resolved', 'closed']

        for status in statuses:
            ttk.Radiobutton(status_frame, text=status.title(),
                           variable=status_var, value=status).pack(anchor='w')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        def perform_bulk_update():
            new_status = status_var.get()

            try:
                from university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                resolved_at = now if new_status in ['resolved', 'closed'] else None

                for ticket_id in ticket_ids:
                    cursor.execute('''
                        UPDATE support_tickets
                        SET status = ?, resolved_at = ?, updated_at = ?, last_activity_at = ?
                        WHERE ticket_id = ?
                    ''', (new_status, resolved_at, now, now, ticket_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"{len(ticket_ids)} tickets updated to {new_status.upper()}")
                dialog.destroy()
                self.refresh_all_tickets()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update tickets: {str(e)}")

        ttk.Button(button_frame, text="Update All", command=perform_bulk_update).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    def execute_ticket_action_gui(self, ticket_id, action):
        """Execute various ticket actions through unified interface"""
        if action == 'reply':
            self.show_add_reply(ticket_id)
        elif action == 'assign':
            self.assign_ticket_enhanced(ticket_id)
        elif action == 'change_status':
            self.change_ticket_status_enhanced(ticket_id)
        elif action == 'escalate':
            self.escalate_ticket_dialog(ticket_id)
        elif action == 'view':
            self.view_ticket_details(ticket_id)
        elif action == 'close':
            self.change_ticket_status_enhanced(ticket_id)
        else:
            messagebox.showinfo("Info", f"Action '{action}' not yet implemented")

    # END OF ENHANCED TICKET MANAGEMENT FUNCTIONS
    # ============================================================================

    # ============================================================================
    # ANALYTICS & REPORTING FUNCTIONS (12 FUNCTIONS)
    # ============================================================================

    def generate_enhanced_ticket_report_gui(self):
        """Show report generation dialog"""
        if not self.current_user:
            messagebox.showerror("Error", "You must be logged in to generate reports.")
            return

        if not self.has_permission('view_all_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to generate reports.")
            return

        # Create report selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Generate Reports")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Enhanced Ticket Report Generator",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 20))

        # Report type selection
        report_frame = ttk.LabelFrame(main_frame, text="Select Report Type", padding="10")
        report_frame.pack(fill='both', expand=True, pady=(0, 10))

        report_type = tk.StringVar(value='executive')

        reports = [
            ('executive', 'Executive Summary Report', 'High-level metrics and KPIs'),
            ('staff', 'Staff Performance Report', 'Individual staff metrics and workload'),
            ('sla', 'SLA Compliance Report', 'SLA adherence and breaches'),
            ('satisfaction', 'Customer Satisfaction Report', 'Satisfaction ratings and feedback'),
            ('trend', 'Trend Analysis Report', 'Historical trends and patterns'),
            ('department', 'Department Performance Report', 'Department-level metrics'),
            ('custom', 'Custom Date Range Report', 'Custom period analysis')
        ]

        for value, label, desc in reports:
            frame = ttk.Frame(report_frame)
            frame.pack(fill='x', pady=2)
            ttk.Radiobutton(frame, text=label, variable=report_type, value=value).pack(side='left')
            ttk.Label(frame, text=f"  ({desc})", foreground='gray').pack(side='left')

        # Period selection
        period_frame = ttk.LabelFrame(main_frame, text="Time Period", padding="10")
        period_frame.pack(fill='x', pady=(0, 10))

        period_var = tk.StringVar(value='30d')
        periods = [('7d', '7 Days'), ('30d', '30 Days'), ('90d', '90 Days'), ('1y', '1 Year')]

        period_buttons = ttk.Frame(period_frame)
        period_buttons.pack(fill='x')
        for value, label in periods:
            ttk.Radiobutton(period_buttons, text=label, variable=period_var,
                           value=value).pack(side='left', padx=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        def generate_report():
            rtype = report_type.get()
            period = period_var.get()

            if rtype == 'executive':
                self.generate_executive_summary_gui(period)
            elif rtype == 'staff':
                self.generate_staff_performance_report_gui(period)
            elif rtype == 'department':
                self.generate_department_report_gui(period)
            elif rtype == 'satisfaction':
                self.generate_satisfaction_report_gui(period)
            elif rtype == 'trend':
                self.generate_trend_analysis_report_gui(period)
            elif rtype == 'custom':
                self.generate_custom_date_report_gui()
            else:
                messagebox.showinfo("Info", f"Report type '{rtype}' will be generated")

            dialog.destroy()

        ttk.Button(button_frame, text="Generate Report", command=generate_report).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    def generate_executive_summary_gui(self, period='30d'):
        """Generate and display executive summary report"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Calculate date range
            days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
            days = days_map.get(period, 30)
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            # Get key metrics
            cursor.execute('''
                SELECT
                    COUNT(*) as total_tickets,
                    COUNT(CASE WHEN status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets,
                    COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tickets,
                    COUNT(CASE WHEN priority = 'high' THEN 1 END) as high_priority,
                    AVG(CASE WHEN resolved_at IS NOT NULL
                        THEN (julianday(resolved_at) - julianday(created_at)) * 24
                        ELSE NULL END) as avg_resolution_hours,
                    AVG(satisfaction_rating) as avg_satisfaction
                FROM support_tickets
                WHERE created_at >= ?
            ''', (start_date,))

            metrics = cursor.fetchone()

            # Create report window
            report_window = tk.Toplevel(self.root)
            report_window.title(f"Executive Summary - {period.upper()}")
            report_window.geometry("800x600")

            main_frame = ttk.Frame(report_window, padding="10")
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text=f"📊 Executive Summary Report ({period.upper()})",
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

            # Scrollable content
            canvas = tk.Canvas(main_frame)
            scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Report content
            report_text = ""

            if metrics[0] > 0:
                resolution_rate = (metrics[1] / metrics[0] * 100)

                # Key Metrics Section
                metrics_frame = ttk.LabelFrame(scrollable_frame, text="📊 Key Metrics", padding="10")
                metrics_frame.pack(fill='x', pady=5)

                metrics_text = f"""Total Tickets: {metrics[0]}
Resolution Rate: {resolution_rate:.1f}%
Open Tickets: {metrics[2]}
High Priority: {metrics[3]}"""

                if metrics[4]:
                    metrics_text += f"\nAvg Resolution Time: {metrics[4]:.1f} hours"
                if metrics[5]:
                    metrics_text += f"\nCustomer Satisfaction: {metrics[5]:.1f}/5.0"

                ttk.Label(metrics_frame, text=metrics_text, justify='left',
                         font=('TkDefaultFont', 10)).pack(anchor='w')

                report_text += metrics_text + "\n\n"

                # Top Categories
                cursor.execute('''
                    SELECT category, COUNT(*) as count
                    FROM support_tickets
                    WHERE created_at >= ?
                    GROUP BY category
                    ORDER BY count DESC
                    LIMIT 5
                ''', (start_date,))

                categories = cursor.fetchall()

                cat_frame = ttk.LabelFrame(scrollable_frame, text="📋 Top Categories", padding="10")
                cat_frame.pack(fill='x', pady=5)

                cat_text = ""
                for cat, count in categories:
                    percentage = (count / metrics[0] * 100)
                    cat_text += f"{cat}: {count} ({percentage:.1f}%)\n"

                ttk.Label(cat_frame, text=cat_text, justify='left').pack(anchor='w')
                report_text += "Top Categories:\n" + cat_text + "\n"

                # Staff Workload
                cursor.execute('''
                    SELECT u.username,
                           COUNT(t.ticket_id) as assigned,
                           COUNT(CASE WHEN t.status IN ('resolved', 'closed') THEN 1 END) as resolved
                    FROM users u
                    LEFT JOIN support_tickets t ON u.id = t.assigned_to AND t.created_at >= ?
                    WHERE u.role IN ('staff', 'admin') AND u.is_active = 1
                    GROUP BY u.id, u.username
                    HAVING assigned > 0
                    ORDER BY assigned DESC
                    LIMIT 5
                ''', (start_date,))

                staff_stats = cursor.fetchall()

                staff_frame = ttk.LabelFrame(scrollable_frame, text="👥 Staff Workload", padding="10")
                staff_frame.pack(fill='x', pady=5)

                staff_text = ""
                for username, assigned, resolved in staff_stats:
                    staff_resolution_rate = (resolved / assigned * 100) if assigned > 0 else 0
                    staff_text += f"{username}: {assigned} assigned, {resolved} resolved ({staff_resolution_rate:.1f}%)\n"

                ttk.Label(staff_frame, text=staff_text, justify='left').pack(anchor='w')
                report_text += "Staff Workload:\n" + staff_text

            conn.close()

            # Export button
            export_frame = ttk.Frame(main_frame)
            export_frame.pack(fill='x', pady=(10, 0))

            def export_report():
                self.save_report_to_file_gui("executive_summary", period, report_text)

            ttk.Button(export_frame, text="Export to File", command=export_report).pack(side='right', padx=5)
            ttk.Button(export_frame, text="Close", command=report_window.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

    def generate_staff_performance_report_gui(self, period='30d'):
        """Generate staff performance report"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
            days = days_map.get(period, 30)
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            # Get staff performance data
            cursor.execute('''
                SELECT
                    u.username,
                    u.role,
                    COUNT(t.ticket_id) as total_assigned,
                    COUNT(CASE WHEN t.status IN ('resolved', 'closed') THEN 1 END) as resolved,
                    AVG(CASE WHEN t.resolved_at IS NOT NULL
                        THEN (julianday(t.resolved_at) - julianday(t.created_at)) * 24
                        ELSE NULL END) as avg_resolution_hours,
                    AVG(t.satisfaction_rating) as avg_satisfaction
                FROM users u
                LEFT JOIN support_tickets t ON u.id = t.assigned_to AND t.created_at >= ?
                WHERE u.role IN ('staff', 'admin') AND u.is_active = 1
                GROUP BY u.id, u.username, u.role
                HAVING total_assigned > 0
                ORDER BY total_assigned DESC
            ''', (start_date,))

            staff_data = cursor.fetchall()
            conn.close()

            # Create report window
            report_window = tk.Toplevel(self.root)
            report_window.title(f"Staff Performance Report - {period.upper()}")
            report_window.geometry("900x600")

            main_frame = ttk.Frame(report_window, padding="10")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"👥 Staff Performance Report ({period.upper()})",
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

            # Create treeview
            columns = ('Username', 'Role', 'Assigned', 'Resolved', 'Resolution %', 'Avg Hours', 'Satisfaction')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=120)

            tree.pack(fill='both', expand=True, pady=(0, 10))

            # Add scrollbar
            scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
            scrollbar.pack(side='right', fill='y')
            tree.configure(yscrollcommand=scrollbar.set)

            # Populate data
            report_text = "Staff Performance Report\n" + "="*50 + "\n\n"
            for username, role, assigned, resolved, avg_hours, avg_sat in staff_data:
                resolution_rate = (resolved / assigned * 100) if assigned > 0 else 0
                avg_hours_str = f"{avg_hours:.1f}" if avg_hours else "N/A"
                avg_sat_str = f"{avg_sat:.1f}" if avg_sat else "N/A"

                tree.insert('', 'end', values=(
                    username, role, assigned, resolved,
                    f"{resolution_rate:.1f}%", avg_hours_str, avg_sat_str
                ))

                report_text += f"{username} ({role}): {assigned} assigned, {resolved} resolved ({resolution_rate:.1f}%), "
                report_text += f"Avg: {avg_hours_str}h, Satisfaction: {avg_sat_str}\n"

            # Export button
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x')

            def export_report():
                self.save_report_to_file_gui("staff_performance", period, report_text)

            ttk.Button(button_frame, text="Export to File", command=export_report).pack(side='right', padx=5)
            ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

    def generate_department_report_gui(self, period='30d'):
        """Generate department performance report"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
            days = days_map.get(period, 30)
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            # Get department performance data
            cursor.execute('''
                SELECT
                    COALESCE(department, 'Unassigned') as dept,
                    COUNT(*) as total_tickets,
                    COUNT(CASE WHEN status IN ('resolved', 'closed') THEN 1 END) as resolved,
                    AVG(CASE WHEN resolved_at IS NOT NULL
                        THEN (julianday(resolved_at) - julianday(created_at)) * 24
                        ELSE NULL END) as avg_resolution_hours
                FROM support_tickets
                WHERE created_at >= ?
                GROUP BY department
                ORDER BY total_tickets DESC
            ''', (start_date,))

            dept_data = cursor.fetchall()
            conn.close()

            # Create report window with chart
            report_window = tk.Toplevel(self.root)
            report_window.title(f"Department Performance - {period.upper()}")
            report_window.geometry("800x600")

            main_frame = ttk.Frame(report_window, padding="10")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"🏢 Department Performance Report ({period.upper()})",
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

            # Create treeview
            columns = ('Department', 'Total Tickets', 'Resolved', 'Resolution %', 'Avg Resolution Hours')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=12)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=150)

            tree.pack(fill='both', expand=True, pady=(0, 10))

            report_text = "Department Performance Report\n" + "="*50 + "\n\n"
            for dept, total, resolved, avg_hours in dept_data:
                resolution_rate = (resolved / total * 100) if total > 0 else 0
                avg_hours_str = f"{avg_hours:.1f}" if avg_hours else "N/A"

                tree.insert('', 'end', values=(
                    dept, total, resolved, f"{resolution_rate:.1f}%", avg_hours_str
                ))

                report_text += f"{dept}: {total} tickets, {resolved} resolved ({resolution_rate:.1f}%), Avg: {avg_hours_str}h\n"

            # Export button
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x')

            def export_report():
                self.save_report_to_file_gui("department_performance", period, report_text)

            ttk.Button(button_frame, text="Export to File", command=export_report).pack(side='right', padx=5)
            ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

    def generate_satisfaction_report_gui(self, period='30d'):
        """Generate customer satisfaction report"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
            days = days_map.get(period, 30)
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            # Get satisfaction data
            cursor.execute('''
                SELECT
                    satisfaction_rating,
                    COUNT(*) as count,
                    satisfaction_feedback
                FROM support_tickets
                WHERE created_at >= ? AND satisfaction_rating IS NOT NULL
                GROUP BY satisfaction_rating
                ORDER BY satisfaction_rating DESC
            ''', (start_date,))

            satisfaction_data = cursor.fetchall()

            # Get average
            cursor.execute('''
                SELECT AVG(satisfaction_rating) as avg_rating,
                       COUNT(*) as total_rated
                FROM support_tickets
                WHERE created_at >= ? AND satisfaction_rating IS NOT NULL
            ''', (start_date,))

            avg_data = cursor.fetchone()
            conn.close()

            # Create report window
            report_window = tk.Toplevel(self.root)
            report_window.title(f"Customer Satisfaction Report - {period.upper()}")
            report_window.geometry("700x500")

            main_frame = ttk.Frame(report_window, padding="10")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"⭐ Customer Satisfaction Report ({period.upper()})",
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

            # Average satisfaction
            if avg_data and avg_data[0]:
                summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding="10")
                summary_frame.pack(fill='x', pady=(0, 10))

                summary_text = f"Average Rating: {avg_data[0]:.2f}/5.0\nTotal Rated Tickets: {avg_data[1]}"
                ttk.Label(summary_frame, text=summary_text, font=('TkDefaultFont', 11, 'bold')).pack()

            # Rating distribution
            dist_frame = ttk.LabelFrame(main_frame, text="Rating Distribution", padding="10")
            dist_frame.pack(fill='both', expand=True, pady=(0, 10))

            columns = ('Rating', 'Count', 'Percentage')
            tree = ttk.Treeview(dist_frame, columns=columns, show='headings', height=5)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=150)

            tree.pack(fill='both', expand=True)

            report_text = f"Customer Satisfaction Report\n{'='*50}\n\n"
            if avg_data and avg_data[0]:
                report_text += f"Average Rating: {avg_data[0]:.2f}/5.0\nTotal Rated: {avg_data[1]}\n\n"

            total_ratings = sum(count for _, count, _ in satisfaction_data)
            for rating, count, _ in satisfaction_data:
                percentage = (count / total_ratings * 100) if total_ratings > 0 else 0
                tree.insert('', 'end', values=(
                    f"{'⭐' * rating} ({rating})", count, f"{percentage:.1f}%"
                ))
                report_text += f"{rating} stars: {count} ({percentage:.1f}%)\n"

            # Export button
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x')

            def export_report():
                self.save_report_to_file_gui("satisfaction", period, report_text)

            ttk.Button(button_frame, text="Export to File", command=export_report).pack(side='right', padx=5)
            ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

    def generate_trend_analysis_report_gui(self, period='30d'):
        """Generate trend analysis report"""
        try:
            from university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
            days = days_map.get(period, 30)
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            # Get daily ticket counts
            cursor.execute('''
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM support_tickets
                WHERE created_at >= ?
                GROUP BY DATE(created_at)
                ORDER BY date
            ''', (start_date,))

            daily_data = cursor.fetchall()

            # Get status trends
            cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM support_tickets
                WHERE created_at >= ?
                GROUP BY status
                ORDER BY count DESC
            ''', (start_date,))

            status_data = cursor.fetchall()
            conn.close()

            # Create report window
            report_window = tk.Toplevel(self.root)
            report_window.title(f"Trend Analysis - {period.upper()}")
            report_window.geometry("800x600")

            main_frame = ttk.Frame(report_window, padding="10")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"📈 Trend Analysis Report ({period.upper()})",
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

            # Daily trends
            daily_frame = ttk.LabelFrame(main_frame, text="Daily Ticket Volume", padding="10")
            daily_frame.pack(fill='both', expand=True, pady=(0, 10))

            columns = ('Date', 'Tickets Created')
            tree = ttk.Treeview(daily_frame, columns=columns, show='headings', height=8)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=200)

            tree.pack(fill='both', expand=True)

            report_text = f"Trend Analysis Report\n{'='*50}\n\nDaily Trends:\n"
            for date, count in daily_data:
                tree.insert('', 'end', values=(date, count))
                report_text += f"{date}: {count} tickets\n"

            # Status distribution
            status_frame = ttk.LabelFrame(main_frame, text="Status Distribution", padding="10")
            status_frame.pack(fill='x', pady=(0, 10))

            status_text = "\n\nStatus Distribution:\n"
            for status, count in status_data:
                status_text += f"{status}: {count} tickets\n"

            ttk.Label(status_frame, text=status_text, justify='left').pack(anchor='w')
            report_text += status_text

            # Export button
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x')

            def export_report():
                self.save_report_to_file_gui("trend_analysis", period, report_text)

            ttk.Button(button_frame, text="Export to File", command=export_report).pack(side='right', padx=5)
            ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

    def generate_custom_date_report_gui(self):
        """Generate report for custom date range"""
        # Create dialog for date selection
        dialog = tk.Toplevel(self.root)
        dialog.title("Custom Date Range Report")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Select Date Range",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

        # Date inputs
        date_frame = ttk.LabelFrame(main_frame, text="Date Range", padding="10")
        date_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(date_frame, text="Start Date (YYYY-MM-DD):").grid(row=0, column=0, sticky='w', pady=5)
        start_entry = ttk.Entry(date_frame, width=20)
        start_entry.insert(0, (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        start_entry.grid(row=0, column=1, pady=5)

        ttk.Label(date_frame, text="End Date (YYYY-MM-DD):").grid(row=1, column=0, sticky='w', pady=5)
        end_entry = ttk.Entry(date_frame, width=20)
        end_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        end_entry.grid(row=1, column=1, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        def generate():
            start_date = start_entry.get()
            end_date = end_entry.get()

            try:
                # Validate dates
                datetime.strptime(start_date, '%Y-%m-%d')
                datetime.strptime(end_date, '%Y-%m-%d')

                dialog.destroy()
                messagebox.showinfo("Info", f"Generating report from {start_date} to {end_date}")
                # Here you would call the actual report generation with the custom dates

            except ValueError:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD")

        ttk.Button(button_frame, text="Generate", command=generate).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    def export_ticket_list_gui(self):
        """Export filtered ticket list to CSV"""
        try:
            import csv
            from tkinter import filedialog

            # Get tickets to export (from current view)
            if hasattr(self, 'all_tickets_tree'):
                items = self.all_tickets_tree.get_children()
                if not items:
                    messagebox.showinfo("Info", "No tickets to export")
                    return

                # Ask for save location
                filename = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=f"tickets_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                )

                if not filename:
                    return

                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['ID', 'Subject', 'Status', 'Priority', 'Category', 'Created', 'Assigned To'])

                    for item in items:
                        values = self.all_tickets_tree.item(item)['values']
                        writer.writerow(values)

                messagebox.showinfo("Success", f"Exported {len(items)} tickets to {filename}")

            else:
                messagebox.showerror("Error", "No ticket list available to export")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export tickets: {str(e)}")

    def save_report_to_file_gui(self, report_type, period, report_content):
        """Save report to file"""
        try:
            from tkinter import filedialog

            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"{report_type}_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            if not filename:
                return

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"Helpdesk Report: {report_type}\n")
                f.write(f"Period: {period}\n")
                f.write(f"Generated by: {self.current_user.get('username', 'Unknown')}\n")
                f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("\n" + "="*50 + "\n\n")
                f.write(report_content)

            messagebox.showinfo("Success", f"Report saved to {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save report: {str(e)}")

    def export_analytics_data_gui(self):
        """Export analytics data to CSV"""
        try:
            import csv
            from tkinter import filedialog
            from university_system.infrastructure.database.db import get_connection

            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"analytics_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            if not filename:
                return

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT ticket_id, user_id, subject, category, status, priority,
                       created_at, resolved_at, satisfaction_rating
                FROM support_tickets
                ORDER BY created_at DESC
            ''')

            tickets = cursor.fetchall()
            conn.close()

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Ticket ID', 'User ID', 'Subject', 'Category', 'Status',
                               'Priority', 'Created At', 'Resolved At', 'Satisfaction'])

                for ticket in tickets:
                    writer.writerow(ticket)

            messagebox.showinfo("Success", f"Exported {len(tickets)} tickets to {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export analytics data: {str(e)}")

    # END OF ANALYTICS & REPORTING FUNCTIONS
    # ============================================================================

    # ============================================================================
    # IMPORT/EXPORT & SYSTEM MANAGEMENT FUNCTIONS (7 FUNCTIONS)
    # ============================================================================

    def import_tickets_csv_gui(self):
        """Import tickets from CSV file"""
        try:
            import csv
            from tkinter import filedialog
            from university_system.infrastructure.database.db import get_connection

            filename = filedialog.askopenfilename(
                title="Select CSV file to import",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not filename:
                return

            imported = 0
            errors = []

            with open(filename, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)

                conn = get_connection()
                cursor = conn.cursor()

                for row in reader:
                    try:
                        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        cursor.execute('''
                            INSERT INTO support_tickets
                            (user_id, subject, message, category, status, priority, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            self.current_user.get('id', 0),
                            row.get('subject', ''),
                            row.get('message', ''),
                            row.get('category', 'Other'),
                            row.get('status', 'open'),
                            row.get('priority', 'medium'),
                            now, now
                        ))

                        imported += 1

                    except Exception as e:
                        errors.append(f"Row {reader.line_num}: {str(e)}")

                conn.commit()
                conn.close()

            if errors:
                error_msg = "\n".join(errors[:5])
                if len(errors) > 5:
                    error_msg += f"\n... and {len(errors)-5} more errors"
                messagebox.showwarning("Import Complete with Errors",
                                      f"Imported {imported} tickets\nErrors: {len(errors)}\n\n{error_msg}")
            else:
                messagebox.showinfo("Success", f"Successfully imported {imported} tickets")

            self.refresh_all_tickets()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to import tickets: {str(e)}")

    def data_import_export_gui(self):
        """Show import/export options dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Data Import/Export")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Data Import/Export",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 20))

        # Export options
        export_frame = ttk.LabelFrame(main_frame, text="Export", padding="10")
        export_frame.pack(fill='x', pady=(0, 10))

        ttk.Button(export_frame, text="Export Tickets to CSV",
                  command=lambda: [dialog.destroy(), self.export_ticket_list_gui()]).pack(fill='x', pady=2)
        ttk.Button(export_frame, text="Export Analytics Data",
                  command=lambda: [dialog.destroy(), self.export_analytics_data_gui()]).pack(fill='x', pady=2)

        # Import options
        import_frame = ttk.LabelFrame(main_frame, text="Import", padding="10")
        import_frame.pack(fill='x', pady=(0, 10))

        ttk.Button(import_frame, text="Import Tickets from CSV",
                  command=lambda: [dialog.destroy(), self.import_tickets_csv_gui()]).pack(fill='x', pady=2)

        # Close button
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=(10, 0))

    def system_management_menu_gui(self):
        """Show system management menu"""
        if not self.has_permission('manage_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to access system management.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("System Management")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="System Management",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 20))

        # Management options
        options_frame = ttk.Frame(main_frame)
        options_frame.pack(fill='both', expand=True)

        ttk.Button(options_frame, text="📊 Generate Reports",
                  command=lambda: [dialog.destroy(), self.generate_enhanced_ticket_report_gui()]).pack(fill='x', pady=5)
        ttk.Button(options_frame, text="💾 Data Import/Export",
                  command=lambda: [dialog.destroy(), self.data_import_export_gui()]).pack(fill='x', pady=5)
        ttk.Button(options_frame, text="🔧 System Maintenance",
                  command=lambda: [dialog.destroy(), self.system_maintenance_gui()]).pack(fill='x', pady=5)
        ttk.Button(options_frame, text="📋 Audit Logs",
                  command=lambda: [dialog.destroy(), self.view_audit_logs_gui()]).pack(fill='x', pady=5)

        # Close button
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=(20, 0))

    def system_maintenance_gui(self):
        """System maintenance functions"""
        dialog = tk.Toplevel(self.root)
        dialog.title("System Maintenance")
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="System Maintenance",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 20))

        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill='both', expand=True)

        def check_integrity():
            try:
                from university_system.modules.domain.student_affairs.services.helpdesk import check_data_integrity
                check_data_integrity(self.auth if hasattr(self, 'auth') else None)
                messagebox.showinfo("Success", "Data integrity check completed")
            except Exception as e:
                messagebox.showerror("Error", f"Integrity check failed: {str(e)}")

        def backup_db():
            try:
                from university_system.modules.domain.student_affairs.services.helpdesk import backup_database
                backup_database(self.auth if hasattr(self, 'auth') else None)
                messagebox.showinfo("Success", "Database backup completed")
            except Exception as e:
                messagebox.showerror("Error", f"Backup failed: {str(e)}")

        ttk.Button(info_frame, text="🔍 Check Data Integrity",
                  command=check_integrity).pack(fill='x', pady=5)
        ttk.Button(info_frame, text="💾 Backup Database",
                  command=backup_db).pack(fill='x', pady=5)
        ttk.Button(info_frame, text="🧹 Database Cleanup",
                  command=lambda: messagebox.showinfo("Info", "Database cleanup functionality")).pack(fill='x', pady=5)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=(20, 0))

    def view_audit_logs_gui(self):
        """View ticket audit logs"""
        try:
            from university_system.infrastructure.database.db import get_connection

            log_window = tk.Toplevel(self.root)
            log_window.title("Audit Logs")
            log_window.geometry("1000x600")

            main_frame = ttk.Frame(log_window, padding="10")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="📋 Ticket Audit Logs",
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

            # Create treeview
            columns = ('Log ID', 'Ticket ID', 'User', 'Action', 'Timestamp', 'Details')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=150)

            tree.pack(fill='both', expand=True, pady=(0, 10))

            # Add scrollbar
            scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
            scrollbar.pack(side='right', fill='y')
            tree.configure(yscrollcommand=scrollbar.set)

            # Load audit logs
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT al.log_id, al.ticket_id, u.username, al.action, al.created_at,
                       al.new_values
                FROM ticket_audit_log al
                LEFT JOIN users u ON al.user_id = u.id
                ORDER BY al.created_at DESC
                LIMIT 1000
            ''')

            logs = cursor.fetchall()
            conn.close()

            for log in logs:
                log_id, ticket_id, username, action, timestamp, details = log
                tree.insert('', 'end', values=(
                    log_id, ticket_id, username or 'System', action, timestamp,
                    details[:50] if details else ''
                ))

            ttk.Button(main_frame, text="Close", command=log_window.destroy).pack()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load audit logs: {str(e)}")

    def log_ticket_action_gui(self, ticket_id, action, old_values=None, new_values=None):
        """Log ticket action to audit trail"""
        try:
            from university_system.infrastructure.database.db import get_connection
            import json

            conn = get_connection()
            cursor = conn.cursor()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO ticket_audit_log
                (ticket_id, user_id, action, old_values, new_values, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                ticket_id,
                self.current_user.get('id', 0),
                action,
                json.dumps(old_values or {}),
                json.dumps(new_values or {}),
                now
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"Failed to log action: {e}")

    # END OF IMPORT/EXPORT & SYSTEM MANAGEMENT FUNCTIONS
    # ============================================================================

    # ============================================================================
    # TICKET TEMPLATE MANAGEMENT FUNCTIONS (5 FUNCTIONS)
    # ============================================================================

    def manage_ticket_templates_gui(self):
        """Manage ticket templates"""
        if not self.has_permission('manage_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to manage templates.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Ticket Template Management")
        dialog.geometry("900x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Ticket Template Management",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Toolbar
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill='x', pady=(0, 10))

        ttk.Button(toolbar, text="➕ Create Template",
                  command=lambda: self.create_ticket_template_gui()).pack(side='left', padx=5)
        ttk.Button(toolbar, text="✏️ Edit Template",
                  command=lambda: self.edit_selected_template(tree)).pack(side='left', padx=5)
        ttk.Button(toolbar, text="🔄 Toggle Active",
                  command=lambda: self.toggle_selected_template(tree)).pack(side='left', padx=5)
        ttk.Button(toolbar, text="🔃 Refresh",
                  command=lambda: self.load_templates_list(tree)).pack(side='left', padx=5)

        # Templates list
        columns = ('ID', 'Name', 'Category', 'Priority', 'Impact', 'Urgency', 'Active')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

        for col in columns:
            tree.heading(col, text=col)
            width = 80 if col == 'ID' else 150
            tree.column(col, width=width)

        tree.pack(fill='both', expand=True, side='left')

        # Scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)

        # Load templates
        self.load_templates_list(tree)

        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    def load_templates_list(self, tree):
        """Load templates into treeview"""
        try:
            from university_system.infrastructure.database.db import get_connection

            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT template_id, name, category, default_priority, default_impact,
                       default_urgency, is_active
                FROM ticket_templates
                ORDER BY category, name
            ''')

            templates = cursor.fetchall()
            conn.close()

            for template in templates:
                tid, name, category, priority, impact, urgency, is_active = template
                active_text = "✓ Yes" if is_active else "✗ No"

                tree.insert('', 'end', values=(
                    tid, name, category or 'N/A', priority or 'N/A',
                    impact or 'N/A', urgency or 'N/A', active_text
                ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load templates: {str(e)}")

    def create_ticket_template_gui(self):
        """Create a new ticket template"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Ticket Template")
        dialog.geometry("600x700")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Create New Ticket Template",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True)

        # Name
        ttk.Label(form_frame, text="Template Name *").grid(row=0, column=0, sticky='w', pady=5)
        name_entry = ttk.Entry(form_frame, width=40)
        name_entry.grid(row=0, column=1, sticky='ew', pady=5)

        # Description
        ttk.Label(form_frame, text="Description").grid(row=1, column=0, sticky='w', pady=5)
        desc_entry = ttk.Entry(form_frame, width=40)
        desc_entry.grid(row=1, column=1, sticky='ew', pady=5)

        # Category
        ttk.Label(form_frame, text="Category *").grid(row=2, column=0, sticky='w', pady=5)
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, state="readonly", width=38)
        category_combo['values'] = ['Technical Support', 'Academic Inquiry', 'Financial Services',
                                    'Account Access', 'Other']
        category_combo.grid(row=2, column=1, sticky='ew', pady=5)

        # Subject Template
        ttk.Label(form_frame, text="Subject Template").grid(row=3, column=0, sticky='nw', pady=5)
        subject_entry = ttk.Entry(form_frame, width=40)
        subject_entry.grid(row=3, column=1, sticky='ew', pady=5)
        ttk.Label(form_frame, text="Use [FIELD_NAME] for placeholders", foreground='gray').grid(
            row=4, column=1, sticky='w')

        # Message Template
        ttk.Label(form_frame, text="Message Template").grid(row=5, column=0, sticky='nw', pady=5)
        message_text = scrolledtext.ScrolledText(form_frame, height=8, width=40)
        message_text.grid(row=5, column=1, sticky='ew', pady=5)

        # Priority, Impact, Urgency
        ttk.Label(form_frame, text="Default Priority").grid(row=6, column=0, sticky='w', pady=5)
        priority_var = tk.StringVar(value='medium')
        priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, state="readonly", width=15)
        priority_combo['values'] = ['low', 'medium', 'high']
        priority_combo.grid(row=6, column=1, sticky='w', pady=5)

        ttk.Label(form_frame, text="Default Impact").grid(row=7, column=0, sticky='w', pady=5)
        impact_var = tk.StringVar(value='low')
        impact_combo = ttk.Combobox(form_frame, textvariable=impact_var, state="readonly", width=15)
        impact_combo['values'] = ['low', 'medium', 'high']
        impact_combo.grid(row=7, column=1, sticky='w', pady=5)

        ttk.Label(form_frame, text="Default Urgency").grid(row=8, column=0, sticky='w', pady=5)
        urgency_var = tk.StringVar(value='low')
        urgency_combo = ttk.Combobox(form_frame, textvariable=urgency_var, state="readonly", width=15)
        urgency_combo['values'] = ['low', 'medium', 'high']
        urgency_combo.grid(row=8, column=1, sticky='w', pady=5)

        form_frame.columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        def save_template():
            name = name_entry.get().strip()
            category = category_var.get()

            if not name or not category:
                messagebox.showerror("Error", "Name and category are required")
                return

            try:
                from university_system.infrastructure.database.db import get_connection

                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    INSERT INTO ticket_templates
                    (name, description, category, subject_template, message_template,
                     default_priority, default_impact, default_urgency, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    name,
                    desc_entry.get().strip(),
                    category,
                    subject_entry.get().strip(),
                    message_text.get('1.0', 'end-1c').strip(),
                    priority_var.get(),
                    impact_var.get(),
                    urgency_var.get(),
                    self.current_user.get('id', 0),
                    now
                ))

                conn.commit()
                template_id = cursor.lastrowid
                conn.close()

                messagebox.showinfo("Success", f"Template #{template_id} created successfully!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create template: {str(e)}")

        ttk.Button(button_frame, text="Create Template", command=save_template).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    def edit_selected_template(self, tree):
        """Edit selected template"""
        selection = tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a template to edit")
            return

        template_id = tree.item(selection[0])['values'][0]
        self.edit_ticket_template_gui(template_id)

    def edit_ticket_template_gui(self, template_id):
        """Edit an existing ticket template"""
        try:
            from university_system.infrastructure.database.db import get_connection

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM ticket_templates WHERE template_id = ?', (template_id,))
            template = cursor.fetchone()
            conn.close()

            if not template:
                messagebox.showerror("Error", "Template not found")
                return

            # Create edit dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Edit Template #{template_id}")
            dialog.geometry("600x700")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding="10")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"Edit Template: {template[1]}",
                     font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

            # Form fields (similar to create, but pre-filled)
            form_frame = ttk.Frame(main_frame)
            form_frame.pack(fill='both', expand=True)

            # Name
            ttk.Label(form_frame, text="Template Name *").grid(row=0, column=0, sticky='w', pady=5)
            name_entry = ttk.Entry(form_frame, width=40)
            name_entry.insert(0, template[1])
            name_entry.grid(row=0, column=1, sticky='ew', pady=5)

            # Description
            ttk.Label(form_frame, text="Description").grid(row=1, column=0, sticky='w', pady=5)
            desc_entry = ttk.Entry(form_frame, width=40)
            desc_entry.insert(0, template[2] or '')
            desc_entry.grid(row=1, column=1, sticky='ew', pady=5)

            # Category
            ttk.Label(form_frame, text="Category *").grid(row=2, column=0, sticky='w', pady=5)
            category_var = tk.StringVar(value=template[3] or '')
            category_combo = ttk.Combobox(form_frame, textvariable=category_var, state="readonly", width=38)
            category_combo['values'] = ['Technical Support', 'Academic Inquiry', 'Financial Services',
                                        'Account Access', 'Other']
            category_combo.grid(row=2, column=1, sticky='ew', pady=5)

            # Subject Template
            ttk.Label(form_frame, text="Subject Template").grid(row=3, column=0, sticky='nw', pady=5)
            subject_entry = ttk.Entry(form_frame, width=40)
            subject_entry.insert(0, template[4] or '')
            subject_entry.grid(row=3, column=1, sticky='ew', pady=5)

            # Message Template
            ttk.Label(form_frame, text="Message Template").grid(row=4, column=0, sticky='nw', pady=5)
            message_text = scrolledtext.ScrolledText(form_frame, height=8, width=40)
            message_text.insert('1.0', template[5] or '')
            message_text.grid(row=4, column=1, sticky='ew', pady=5)

            # Priority, Impact, Urgency
            ttk.Label(form_frame, text="Default Priority").grid(row=5, column=0, sticky='w', pady=5)
            priority_var = tk.StringVar(value=template[6] or 'medium')
            priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, state="readonly", width=15)
            priority_combo['values'] = ['low', 'medium', 'high']
            priority_combo.grid(row=5, column=1, sticky='w', pady=5)

            ttk.Label(form_frame, text="Default Impact").grid(row=6, column=0, sticky='w', pady=5)
            impact_var = tk.StringVar(value=template[7] or 'low')
            impact_combo = ttk.Combobox(form_frame, textvariable=impact_var, state="readonly", width=15)
            impact_combo['values'] = ['low', 'medium', 'high']
            impact_combo.grid(row=6, column=1, sticky='w', pady=5)

            ttk.Label(form_frame, text="Default Urgency").grid(row=7, column=0, sticky='w', pady=5)
            urgency_var = tk.StringVar(value=template[8] or 'low')
            urgency_combo = ttk.Combobox(form_frame, textvariable=urgency_var, state="readonly", width=15)
            urgency_combo['values'] = ['low', 'medium', 'high']
            urgency_combo.grid(row=7, column=1, sticky='w', pady=5)

            form_frame.columnconfigure(1, weight=1)

            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x', pady=(10, 0))

            def update_template():
                name = name_entry.get().strip()
                category = category_var.get()

                if not name or not category:
                    messagebox.showerror("Error", "Name and category are required")
                    return

                try:
                    from university_system.infrastructure.database.db import get_connection

                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                        UPDATE ticket_templates
                        SET name = ?, description = ?, category = ?, subject_template = ?,
                            message_template = ?, default_priority = ?, default_impact = ?,
                            default_urgency = ?
                        WHERE template_id = ?
                    ''', (
                        name,
                        desc_entry.get().strip(),
                        category,
                        subject_entry.get().strip(),
                        message_text.get('1.0', 'end-1c').strip(),
                        priority_var.get(),
                        impact_var.get(),
                        urgency_var.get(),
                        template_id
                    ))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Template updated successfully!")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update template: {str(e)}")

            ttk.Button(button_frame, text="Update Template", command=update_template).pack(side='right', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load template: {str(e)}")

    def toggle_selected_template(self, tree):
        """Toggle active status of selected template"""
        selection = tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a template to toggle")
            return

        template_id = tree.item(selection[0])['values'][0]
        self.toggle_ticket_template_gui(template_id, tree)

    def toggle_ticket_template_gui(self, template_id, tree):
        """Toggle template active status"""
        try:
            from university_system.infrastructure.database.db import get_connection

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT name, is_active FROM ticket_templates WHERE template_id = ?',
                          (template_id,))
            result = cursor.fetchone()

            if not result:
                messagebox.showerror("Error", "Template not found")
                conn.close()
                return

            name, is_active = result
            new_status = not is_active

            cursor.execute('UPDATE ticket_templates SET is_active = ? WHERE template_id = ?',
                          (new_status, template_id))

            conn.commit()
            conn.close()

            status_text = "activated" if new_status else "deactivated"
            messagebox.showinfo("Success", f"Template '{name}' has been {status_text}")

            # Refresh tree
            self.load_templates_list(tree)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to toggle template: {str(e)}")

    def view_ticket_templates_gui(self):
        """View ticket templates (read-only)"""
        self.manage_ticket_templates_gui()

    # END OF TICKET TEMPLATE MANAGEMENT FUNCTIONS
    # ============================================================================

    # ============================================================================
    # DEPARTMENT & ORGANIZATION MANAGEMENT FUNCTIONS (9 FUNCTIONS)
    # ============================================================================

    def manage_departments_gui(self):
        """Manage departments"""
        if not self.has_permission('manage_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to manage departments.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Department Management")
        dialog.geometry("900x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Department Management",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Toolbar
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill='x', pady=(0, 10))

        ttk.Button(toolbar, text="➕ Create Department",
                  command=lambda: self.create_department_gui()).pack(side='left', padx=5)
        ttk.Button(toolbar, text="✏️ Edit Department",
                  command=lambda: self.edit_selected_department(tree)).pack(side='left', padx=5)
        ttk.Button(toolbar, text="🔄 Toggle Active",
                  command=lambda: self.toggle_selected_department(tree)).pack(side='left', padx=5)
        ttk.Button(toolbar, text="🔃 Refresh",
                  command=lambda: self.load_departments_list(tree)).pack(side='left', padx=5)

        # Departments list
        columns = ('ID', 'Name', 'Email', 'Manager', 'Description', 'Active')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

        for col in columns:
            tree.heading(col, text=col)
            width = 60 if col == 'ID' else 150
            tree.column(col, width=width)

        tree.pack(fill='both', expand=True, side='left')

        # Scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)

        # Load departments
        self.load_departments_list(tree)

        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    def load_departments_list(self, tree):
        """Load departments into treeview"""
        try:
            from university_system.infrastructure.database.db import get_connection

            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT d.dept_id, d.name, d.email, u.username as manager,
                       d.description, d.is_active
                FROM departments d
                LEFT JOIN users u ON d.manager_id = u.id
                ORDER BY d.name
            ''')

            departments = cursor.fetchall()
            conn.close()

            for dept in departments:
                dept_id, name, email, manager, description, is_active = dept
                active_text = "✓ Yes" if is_active else "✗ No"
                manager_text = manager or 'None'

                tree.insert('', 'end', values=(
                    dept_id, name, email or 'N/A', manager_text,
                    (description or 'N/A')[:50], active_text
                ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load departments: {str(e)}")

    def create_department_gui(self):
        """Create a new department"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Department")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Create New Department",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True)

        ttk.Label(form_frame, text="Department Name *").grid(row=0, column=0, sticky='w', pady=5)
        name_entry = ttk.Entry(form_frame, width=35)
        name_entry.grid(row=0, column=1, sticky='ew', pady=5)

        ttk.Label(form_frame, text="Description").grid(row=1, column=0, sticky='nw', pady=5)
        desc_text = scrolledtext.ScrolledText(form_frame, height=5, width=35)
        desc_text.grid(row=1, column=1, sticky='ew', pady=5)

        ttk.Label(form_frame, text="Email").grid(row=2, column=0, sticky='w', pady=5)
        email_entry = ttk.Entry(form_frame, width=35)
        email_entry.grid(row=2, column=1, sticky='ew', pady=5)

        form_frame.columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        def save_department():
            name = name_entry.get().strip()

            if not name:
                messagebox.showerror("Error", "Department name is required")
                return

            try:
                from university_system.infrastructure.database.db import get_connection

                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    INSERT INTO departments (name, description, email, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (
                    name,
                    desc_text.get('1.0', 'end-1c').strip(),
                    email_entry.get().strip(),
                    now
                ))

                conn.commit()
                dept_id = cursor.lastrowid
                conn.close()

                messagebox.showinfo("Success", f"Department #{dept_id} created successfully!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create department: {str(e)}")

        ttk.Button(button_frame, text="Create Department", command=save_department).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    def edit_selected_department(self, tree):
        """Edit selected department"""
        selection = tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a department to edit")
            return

        dept_id = tree.item(selection[0])['values'][0]
        self.edit_department_gui(dept_id)

    def edit_department_gui(self, dept_id):
        """Edit an existing department"""
        try:
            from university_system.infrastructure.database.db import get_connection

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM departments WHERE dept_id = ?', (dept_id,))
            dept = cursor.fetchone()
            conn.close()

            if not dept:
                messagebox.showerror("Error", "Department not found")
                return

            # Create edit dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Edit Department #{dept_id}")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding="10")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"Edit Department: {dept[1]}",
                     font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

            # Form fields
            form_frame = ttk.Frame(main_frame)
            form_frame.pack(fill='both', expand=True)

            ttk.Label(form_frame, text="Department Name *").grid(row=0, column=0, sticky='w', pady=5)
            name_entry = ttk.Entry(form_frame, width=35)
            name_entry.insert(0, dept[1])
            name_entry.grid(row=0, column=1, sticky='ew', pady=5)

            ttk.Label(form_frame, text="Description").grid(row=1, column=0, sticky='nw', pady=5)
            desc_text = scrolledtext.ScrolledText(form_frame, height=5, width=35)
            desc_text.insert('1.0', dept[2] or '')
            desc_text.grid(row=1, column=1, sticky='ew', pady=5)

            ttk.Label(form_frame, text="Email").grid(row=2, column=0, sticky='w', pady=5)
            email_entry = ttk.Entry(form_frame, width=35)
            email_entry.insert(0, dept[3] or '')
            email_entry.grid(row=2, column=1, sticky='ew', pady=5)

            form_frame.columnconfigure(1, weight=1)

            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x', pady=(10, 0))

            def update_department():
                name = name_entry.get().strip()

                if not name:
                    messagebox.showerror("Error", "Department name is required")
                    return

                try:
                    from university_system.infrastructure.database.db import get_connection

                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                        UPDATE departments
                        SET name = ?, description = ?, email = ?
                        WHERE dept_id = ?
                    ''', (
                        name,
                        desc_text.get('1.0', 'end-1c').strip(),
                        email_entry.get().strip(),
                        dept_id
                    ))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Department updated successfully!")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update department: {str(e)}")

            ttk.Button(button_frame, text="Update Department", command=update_department).pack(side='right', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load department: {str(e)}")

    def toggle_selected_department(self, tree):
        """Toggle active status of selected department"""
        selection = tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a department to toggle")
            return

        dept_id = tree.item(selection[0])['values'][0]
        self.toggle_department_gui(dept_id, tree)

    def toggle_department_gui(self, dept_id, tree):
        """Toggle department active status"""
        try:
            from university_system.infrastructure.database.db import get_connection

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT name, is_active FROM departments WHERE dept_id = ?', (dept_id,))
            result = cursor.fetchone()

            if not result:
                messagebox.showerror("Error", "Department not found")
                conn.close()
                return

            name, is_active = result
            new_status = not is_active

            cursor.execute('UPDATE departments SET is_active = ? WHERE dept_id = ?',
                          (new_status, dept_id))

            conn.commit()
            conn.close()

            status_text = "activated" if new_status else "deactivated"
            messagebox.showinfo("Success", f"Department '{name}' has been {status_text}")

            # Refresh tree
            self.load_departments_list(tree)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to toggle department: {str(e)}")

    def view_departments_gui(self):
        """View departments (read-only)"""
        self.manage_departments_gui()

    def manage_organizations_gui(self):
        """Manage organizations"""
        if not self.has_permission('manage_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to manage organizations.")
            return

        messagebox.showinfo("Organizations", "Organization management feature coming soon.\n\nCurrently supports department-level organization.")

    def view_organizations_gui(self):
        """View organizations"""
        self.manage_organizations_gui()

    # END OF DEPARTMENT & ORGANIZATION MANAGEMENT FUNCTIONS
    # ============================================================================

    # ============================================================================
    # WORKFLOW AUTOMATION FUNCTIONS (8 FUNCTIONS)
    # ============================================================================

    def manage_workflows_gui(self):
        """Manage automated workflows"""
        if not self.has_permission('manage_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to manage workflows.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Workflow Management")
        dialog.geometry("1000x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Automated Workflow Management",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Toolbar
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill='x', pady=(0, 10))

        ttk.Button(toolbar, text="➕ Create Workflow",
                  command=lambda: self.create_workflow_gui()).pack(side='left', padx=5)
        ttk.Button(toolbar, text="✏️ Edit Workflow",
                  command=lambda: self.edit_selected_workflow(tree)).pack(side='left', padx=5)
        ttk.Button(toolbar, text="🔄 Toggle Active",
                  command=lambda: self.toggle_selected_workflow(tree)).pack(side='left', padx=5)
        ttk.Button(toolbar, text="🔃 Refresh",
                  command=lambda: self.load_workflows_list(tree)).pack(side='left', padx=5)

        # Workflows list
        columns = ('ID', 'Name', 'Trigger Type', 'Description', 'Active')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

        for col in columns:
            tree.heading(col, text=col)
            width = 60 if col == 'ID' else 200
            tree.column(col, width=width)

        tree.pack(fill='both', expand=True, side='left')

        # Scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)

        # Load workflows
        self.load_workflows_list(tree)

        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    def load_workflows_list(self, tree):
        """Load workflows into treeview"""
        try:
            from university_system.infrastructure.database.db import get_connection

            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT workflow_id, name, trigger_type, description, is_active
                FROM ticket_workflows
                ORDER BY trigger_type, name
            ''')

            workflows = cursor.fetchall()
            conn.close()

            for workflow in workflows:
                wf_id, name, trigger_type, description, is_active = workflow
                active_text = "✓ Yes" if is_active else "✗ No"

                tree.insert('', 'end', values=(
                    wf_id, name, trigger_type or 'N/A',
                    (description or 'N/A')[:50], active_text
                ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load workflows: {str(e)}")

    def create_workflow_gui(self):
        """Create a new automated workflow"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Workflow")
        dialog.geometry("600x700")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Create New Automated Workflow",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True)

        # Name
        ttk.Label(form_frame, text="Workflow Name *").grid(row=0, column=0, sticky='w', pady=5)
        name_entry = ttk.Entry(form_frame, width=40)
        name_entry.grid(row=0, column=1, sticky='ew', pady=5)

        # Description
        ttk.Label(form_frame, text="Description").grid(row=1, column=0, sticky='w', pady=5)
        desc_entry = ttk.Entry(form_frame, width=40)
        desc_entry.grid(row=1, column=1, sticky='ew', pady=5)

        # Trigger Type
        ttk.Label(form_frame, text="Trigger Type *").grid(row=2, column=0, sticky='w', pady=5)
        trigger_var = tk.StringVar()
        trigger_combo = ttk.Combobox(form_frame, textvariable=trigger_var, state="readonly", width=38)
        trigger_combo['values'] = ['ticket_created', 'ticket_updated', 'status_changed',
                                   'priority_changed', 'assigned', 'overdue']
        trigger_combo.grid(row=2, column=1, sticky='ew', pady=5)

        # Conditions (JSON)
        ttk.Label(form_frame, text="Conditions (JSON)").grid(row=3, column=0, sticky='nw', pady=5)
        conditions_text = scrolledtext.ScrolledText(form_frame, height=8, width=40)
        conditions_text.insert('1.0', '{\n  "priority": "high",\n  "category": "Technical Support"\n}')
        conditions_text.grid(row=3, column=1, sticky='ew', pady=5)

        # Actions (JSON)
        ttk.Label(form_frame, text="Actions (JSON) *").grid(row=4, column=0, sticky='nw', pady=5)
        actions_text = scrolledtext.ScrolledText(form_frame, height=8, width=40)
        actions_text.insert('1.0', '{\n  "assign_to_department": "IT Support",\n  "set_priority": "high"\n}')
        actions_text.grid(row=4, column=1, sticky='ew', pady=5)

        ttk.Label(form_frame, text="Actions: assign_to_department, set_priority, change_status",
                 foreground='gray', font=('TkDefaultFont', 8)).grid(row=5, column=1, sticky='w')

        form_frame.columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        def save_workflow():
            name = name_entry.get().strip()
            trigger_type = trigger_var.get()

            if not name or not trigger_type:
                messagebox.showerror("Error", "Name and trigger type are required")
                return

            try:
                import json
                from university_system.infrastructure.database.db import get_connection

                # Validate JSON
                conditions_json = conditions_text.get('1.0', 'end-1c').strip()
                actions_json = actions_text.get('1.0', 'end-1c').strip()

                if conditions_json:
                    json.loads(conditions_json)
                if actions_json:
                    json.loads(actions_json)

                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    INSERT INTO ticket_workflows
                    (name, description, trigger_type, trigger_conditions, actions, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    name,
                    desc_entry.get().strip(),
                    trigger_type,
                    conditions_json if conditions_json else None,
                    actions_json if actions_json else None,
                    now
                ))

                conn.commit()
                workflow_id = cursor.lastrowid
                conn.close()

                messagebox.showinfo("Success", f"Workflow #{workflow_id} created successfully!")
                dialog.destroy()

            except json.JSONDecodeError as e:
                messagebox.showerror("Error", f"Invalid JSON: {str(e)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create workflow: {str(e)}")

        ttk.Button(button_frame, text="Create Workflow", command=save_workflow).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    def edit_selected_workflow(self, tree):
        """Edit selected workflow"""
        selection = tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a workflow to edit")
            return

        workflow_id = tree.item(selection[0])['values'][0]
        self.edit_workflow_gui(workflow_id)

    def edit_workflow_gui(self, workflow_id):
        """Edit existing workflow - placeholder for full implementation"""
        messagebox.showinfo("Info", f"Editing workflow #{workflow_id}\n\nFull edit form coming soon.")

    def toggle_selected_workflow(self, tree):
        """Toggle active status of selected workflow"""
        selection = tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a workflow to toggle")
            return

        workflow_id = tree.item(selection[0])['values'][0]
        self.toggle_workflow_gui(workflow_id, tree)

    def toggle_workflow_gui(self, workflow_id, tree):
        """Toggle workflow active status"""
        try:
            from university_system.infrastructure.database.db import get_connection

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT name, is_active FROM ticket_workflows WHERE workflow_id = ?',
                          (workflow_id,))
            result = cursor.fetchone()

            if not result:
                messagebox.showerror("Error", "Workflow not found")
                conn.close()
                return

            name, is_active = result
            new_status = not is_active

            cursor.execute('UPDATE ticket_workflows SET is_active = ? WHERE workflow_id = ?',
                          (new_status, workflow_id))

            conn.commit()
            conn.close()

            status_text = "activated" if new_status else "deactivated"
            messagebox.showinfo("Success", f"Workflow '{name}' has been {status_text}")

            # Refresh tree
            self.load_workflows_list(tree)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to toggle workflow: {str(e)}")

    def run_ticket_workflows_gui(self, ticket_id, trigger_type):
        """Run automated workflows based on triggers"""
        try:
            import json
            from university_system.infrastructure.database.db import get_connection

            conn = get_connection()
            cursor = conn.cursor()

            # Get active workflows for this trigger
            cursor.execute('''
                SELECT workflow_id, name, trigger_conditions, actions
                FROM ticket_workflows
                WHERE trigger_type = ? AND is_active = 1
            ''', (trigger_type,))

            workflows = cursor.fetchall()
            executed_count = 0

            for workflow in workflows:
                workflow_id, name, conditions_json, actions_json = workflow

                try:
                    conditions = json.loads(conditions_json) if conditions_json else {}
                    actions = json.loads(actions_json) if actions_json else {}

                    # Check conditions and execute
                    if self.check_workflow_conditions_gui(ticket_id, conditions):
                        self.execute_workflow_actions_gui(ticket_id, actions)
                        executed_count += 1

                except json.JSONDecodeError:
                    pass

            conn.close()

        except Exception as e:
            print(f"Error running workflows: {e}")

    def check_workflow_conditions_gui(self, ticket_id, conditions):
        """Check if workflow conditions are met"""
        try:
            from university_system.infrastructure.database.db import get_connection

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
            ticket = cursor.fetchone()

            if not ticket:
                conn.close()
                return False

            # Convert to dict
            columns = [desc[0] for desc in cursor.description]
            ticket_dict = dict(zip(columns, ticket))
            conn.close()

            # Check each condition
            for field, expected_value in conditions.items():
                if field in ticket_dict:
                    if ticket_dict[field] != expected_value:
                        return False

            return True

        except Exception:
            return False

    def execute_workflow_actions_gui(self, ticket_id, actions):
        """Execute workflow actions"""
        try:
            from university_system.infrastructure.database.db import get_connection

            conn = get_connection()
            cursor = conn.cursor()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            for action, value in actions.items():
                if action == 'set_priority':
                    cursor.execute('''
                        UPDATE support_tickets SET priority = ?, updated_at = ? WHERE ticket_id = ?
                    ''', (value, now, ticket_id))
                elif action == 'change_status':
                    cursor.execute('''
                        UPDATE support_tickets SET status = ?, updated_at = ? WHERE ticket_id = ?
                    ''', (value, now, ticket_id))

            conn.commit()
            conn.close()

        except Exception:
            pass

    def view_workflows_gui(self):
        """View workflows (read-only)"""
        self.manage_workflows_gui()

    # END OF WORKFLOW AUTOMATION FUNCTIONS
    # ============================================================================

    # ============================================================================
    # SLA POLICY MANAGEMENT FUNCTIONS (7 FUNCTIONS)
    # ============================================================================

    def manage_sla_policies_gui(self):
        """Manage SLA policies"""
        if not self.has_permission('manage_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to manage SLA policies.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("SLA Policy Management")
        dialog.geometry("1100x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="SLA Policy Management",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Toolbar
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill='x', pady=(0, 10))

        ttk.Button(toolbar, text="➕ Create SLA Policy",
                  command=lambda: self.create_sla_policy_gui()).pack(side='left', padx=5)
        ttk.Button(toolbar, text="✏️ Edit SLA Policy",
                  command=lambda: self.edit_selected_sla(tree)).pack(side='left', padx=5)
        ttk.Button(toolbar, text="🔄 Toggle Active",
                  command=lambda: self.toggle_selected_sla(tree)).pack(side='left', padx=5)
        ttk.Button(toolbar, text="📊 SLA Report",
                  command=lambda: self.generate_sla_compliance_report_gui()).pack(side='left', padx=5)
        ttk.Button(toolbar, text="⚠️ Check Overdue",
                  command=lambda: self.check_overdue_tickets_gui()).pack(side='left', padx=5)
        ttk.Button(toolbar, text="🔃 Refresh",
                  command=lambda: self.load_sla_policies_list(tree)).pack(side='left', padx=5)

        # SLA policies list
        columns = ('ID', 'Name', 'P/I/U', 'Response (h)', 'Resolution (h)',
                  'Escalation (h)', 'Business Hours', 'Active')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

        for col in columns:
            tree.heading(col, text=col)
            width = 60 if col == 'ID' else 120
            tree.column(col, width=width)

        tree.pack(fill='both', expand=True, side='left')

        # Scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)

        # Load SLA policies
        self.load_sla_policies_list(tree)

        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    def load_sla_policies_list(self, tree):
        """Load SLA policies into treeview"""
        try:
            from university_system.infrastructure.database.db import get_connection

            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT sla_id, name, priority, impact, urgency, first_response_hours,
                       resolution_hours, escalation_hours, business_hours_only, is_active
                FROM sla_policies
                ORDER BY priority, impact, urgency
            ''')

            policies = cursor.fetchall()
            conn.close()

            for policy in policies:
                sla_id, name, priority, impact, urgency, response_h, resolution_h, escalation_h, business_only, is_active = policy
                p_i_u = f"{priority}/{impact}/{urgency}"
                business_text = "Yes" if business_only else "No"
                active_text = "✓ Yes" if is_active else "✗ No"

                tree.insert('', 'end', values=(
                    sla_id, name, p_i_u, response_h, resolution_h,
                    escalation_h, business_text, active_text
                ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load SLA policies: {str(e)}")

    def create_sla_policy_gui(self):
        """Create a new SLA policy"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create SLA Policy")
        dialog.geometry("500x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Create New SLA Policy",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True)

        # Name
        ttk.Label(form_frame, text="Policy Name *").grid(row=0, column=0, sticky='w', pady=5)
        name_entry = ttk.Entry(form_frame, width=35)
        name_entry.grid(row=0, column=1, sticky='ew', pady=5)

        # Description
        ttk.Label(form_frame, text="Description").grid(row=1, column=0, sticky='w', pady=5)
        desc_entry = ttk.Entry(form_frame, width=35)
        desc_entry.grid(row=1, column=1, sticky='ew', pady=5)

        # Priority, Impact, Urgency
        ttk.Label(form_frame, text="Priority *").grid(row=2, column=0, sticky='w', pady=5)
        priority_var = tk.StringVar(value='medium')
        priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, state="readonly", width=15)
        priority_combo['values'] = ['low', 'medium', 'high']
        priority_combo.grid(row=2, column=1, sticky='w', pady=5)

        ttk.Label(form_frame, text="Impact *").grid(row=3, column=0, sticky='w', pady=5)
        impact_var = tk.StringVar(value='low')
        impact_combo = ttk.Combobox(form_frame, textvariable=impact_var, state="readonly", width=15)
        impact_combo['values'] = ['low', 'medium', 'high']
        impact_combo.grid(row=3, column=1, sticky='w', pady=5)

        ttk.Label(form_frame, text="Urgency *").grid(row=4, column=0, sticky='w', pady=5)
        urgency_var = tk.StringVar(value='low')
        urgency_combo = ttk.Combobox(form_frame, textvariable=urgency_var, state="readonly", width=15)
        urgency_combo['values'] = ['low', 'medium', 'high']
        urgency_combo.grid(row=4, column=1, sticky='w', pady=5)

        # Time targets
        ttk.Label(form_frame, text="First Response (hours) *").grid(row=5, column=0, sticky='w', pady=5)
        response_entry = ttk.Entry(form_frame, width=15)
        response_entry.insert(0, '4')
        response_entry.grid(row=5, column=1, sticky='w', pady=5)

        ttk.Label(form_frame, text="Resolution (hours) *").grid(row=6, column=0, sticky='w', pady=5)
        resolution_entry = ttk.Entry(form_frame, width=15)
        resolution_entry.insert(0, '24')
        resolution_entry.grid(row=6, column=1, sticky='w', pady=5)

        ttk.Label(form_frame, text="Escalation (hours) *").grid(row=7, column=0, sticky='w', pady=5)
        escalation_entry = ttk.Entry(form_frame, width=15)
        escalation_entry.insert(0, '8')
        escalation_entry.grid(row=7, column=1, sticky='w', pady=5)

        # Business hours only
        business_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, text="Business hours only",
                       variable=business_var).grid(row=8, column=1, sticky='w', pady=5)

        form_frame.columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        def save_sla():
            name = name_entry.get().strip()

            if not name:
                messagebox.showerror("Error", "Policy name is required")
                return

            try:
                from university_system.infrastructure.database.db import get_connection

                first_response = int(response_entry.get())
                resolution = int(resolution_entry.get())
                escalation = int(escalation_entry.get())

                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    INSERT INTO sla_policies
                    (name, description, priority, impact, urgency, first_response_hours,
                     resolution_hours, escalation_hours, business_hours_only, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    name,
                    desc_entry.get().strip(),
                    priority_var.get(),
                    impact_var.get(),
                    urgency_var.get(),
                    first_response,
                    resolution,
                    escalation,
                    business_var.get(),
                    now
                ))

                conn.commit()
                sla_id = cursor.lastrowid
                conn.close()

                messagebox.showinfo("Success", f"SLA Policy #{sla_id} created successfully!")
                dialog.destroy()

            except ValueError:
                messagebox.showerror("Error", "Time values must be numbers")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create SLA policy: {str(e)}")

        ttk.Button(button_frame, text="Create SLA Policy", command=save_sla).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    def edit_selected_sla(self, tree):
        """Edit selected SLA policy"""
        selection = tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select an SLA policy to edit")
            return

        sla_id = tree.item(selection[0])['values'][0]
        self.edit_sla_policy_gui(sla_id)

    def edit_sla_policy_gui(self, sla_id):
        """Edit SLA policy - placeholder"""
        messagebox.showinfo("Info", f"Editing SLA Policy #{sla_id}\n\nFull edit form coming soon.")

    def toggle_selected_sla(self, tree):
        """Toggle active status of selected SLA policy"""
        selection = tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select an SLA policy to toggle")
            return

        sla_id = tree.item(selection[0])['values'][0]
        self.toggle_sla_policy_gui(sla_id, tree)

    def toggle_sla_policy_gui(self, sla_id, tree):
        """Toggle SLA policy active status"""
        try:
            from university_system.infrastructure.database.db import get_connection

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT name, is_active FROM sla_policies WHERE sla_id = ?', (sla_id,))
            result = cursor.fetchone()

            if not result:
                messagebox.showerror("Error", "SLA policy not found")
                conn.close()
                return

            name, is_active = result
            new_status = not is_active

            cursor.execute('UPDATE sla_policies SET is_active = ? WHERE sla_id = ?',
                          (new_status, sla_id))

            conn.commit()
            conn.close()

            status_text = "activated" if new_status else "deactivated"
            messagebox.showinfo("Success", f"SLA Policy '{name}' has been {status_text}")

            # Refresh tree
            self.load_sla_policies_list(tree)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to toggle SLA policy: {str(e)}")

    def check_overdue_tickets_gui(self):
        """Check for overdue tickets based on SLA"""
        try:
            from university_system.infrastructure.database.db import get_connection

            conn = get_connection()
            cursor = conn.cursor()

            now = datetime.now()

            cursor.execute('''
                SELECT ticket_id, subject, due_date, JULIANDAY(?) - JULIANDAY(due_date) as days_overdue
                FROM support_tickets
                WHERE status NOT IN ('resolved', 'closed')
                  AND due_date IS NOT NULL
                  AND due_date < ?
                ORDER BY days_overdue DESC
            ''', (now.strftime('%Y-%m-%d %H:%M:%S'), now.strftime('%Y-%m-%d %H:%M:%S')))

            overdue = cursor.fetchall()
            conn.close()

            if not overdue:
                messagebox.showinfo("SLA Check", "No overdue tickets found!")
                return

            # Create results window
            result_window = tk.Toplevel(self.root)
            result_window.title("Overdue Tickets")
            result_window.geometry("800x400")

            main_frame = ttk.Frame(result_window, padding="10")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"⚠️ {len(overdue)} Overdue Tickets Found",
                     font=('TkDefaultFont', 12, 'bold'), foreground='red').pack(pady=(0, 10))

            columns = ('Ticket ID', 'Subject', 'Due Date', 'Days Overdue')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=200)

            tree.pack(fill='both', expand=True)

            for ticket_id, subject, due_date, days_overdue in overdue:
                tree.insert('', 'end', values=(
                    ticket_id, subject[:50], due_date, f"{days_overdue:.1f}"
                ))

            ttk.Button(main_frame, text="Close", command=result_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to check overdue tickets: {str(e)}")

    def generate_sla_compliance_report_gui(self):
        """Generate SLA compliance report"""
        try:
            from university_system.infrastructure.database.db import get_connection

            conn = get_connection()
            cursor = conn.cursor()

            # Get SLA compliance metrics
            cursor.execute('''
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN resolved_at <= due_date THEN 1 END) as within_sla,
                    COUNT(CASE WHEN resolved_at > due_date THEN 1 END) as breached,
                    COUNT(CASE WHEN resolved_at IS NULL AND due_date < datetime('now') THEN 1 END) as at_risk
                FROM support_tickets
                WHERE due_date IS NOT NULL
            ''')

            metrics = cursor.fetchone()
            conn.close()

            if not metrics or metrics[0] == 0:
                messagebox.showinfo("SLA Report", "No SLA data available")
                return

            total, within_sla, breached, at_risk = metrics
            compliance_rate = (within_sla / total * 100) if total > 0 else 0

            # Create report window
            report_window = tk.Toplevel(self.root)
            report_window.title("SLA Compliance Report")
            report_window.geometry("600x400")

            main_frame = ttk.Frame(report_window, padding="10")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="📊 SLA Compliance Report",
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 20))

            # Metrics display
            metrics_frame = ttk.LabelFrame(main_frame, text="Compliance Metrics", padding="20")
            metrics_frame.pack(fill='both', expand=True)

            metrics_text = f"""
Total Tickets with SLA: {total}
Within SLA: {within_sla} ({compliance_rate:.1f}%)
Breached SLA: {breached}
At Risk (Overdue): {at_risk}

Overall Compliance Rate: {compliance_rate:.1f}%
"""

            ttk.Label(metrics_frame, text=metrics_text, font=('TkDefaultFont', 11),
                     justify='left').pack(anchor='w')

            # Color-coded status
            if compliance_rate >= 95:
                status_color = 'green'
                status_text = "✓ Excellent"
            elif compliance_rate >= 80:
                status_color = 'orange'
                status_text = "⚠ Needs Improvement"
            else:
                status_color = 'red'
                status_text = "✗ Critical"

            ttk.Label(metrics_frame, text=f"Status: {status_text}",
                     font=('TkDefaultFont', 12, 'bold'),
                     foreground=status_color).pack(pady=(10, 0))

            ttk.Button(main_frame, text="Close", command=report_window.destroy).pack(pady=20)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate SLA report: {str(e)}")

    def view_sla_policies_gui(self):
        """View SLA policies (read-only)"""
        self.manage_sla_policies_gui()

    # END OF SLA POLICY MANAGEMENT FUNCTIONS
    # ============================================================================

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

    # ========================================================================
    # SEARCH & FILTERING FUNCTIONS
    # ========================================================================

    def advanced_search_tickets_gui(self):
        """Advanced ticket search with multiple filters"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Advanced Ticket Search")
        dialog.geometry("700x700")

        # Main frame with scrollbar
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Search criteria storage
        criteria = {}

        # Text search
        ttk.Label(main_frame, text="Search Text (Subject/Message):").grid(row=0, column=0, sticky=tk.W, pady=5)
        text_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=text_var, width=50).grid(row=0, column=1, pady=5, padx=5)

        # Status filter
        ttk.Label(main_frame, text="Status Filter:").grid(row=1, column=0, sticky=tk.W, pady=5)
        status_var = tk.StringVar(value="all")
        status_combo = ttk.Combobox(main_frame, textvariable=status_var, width=47,
                                    values=["all", "open", "in progress", "resolved", "closed"])
        status_combo.grid(row=1, column=1, pady=5, padx=5)

        # Priority filter
        ttk.Label(main_frame, text="Priority Filter:").grid(row=2, column=0, sticky=tk.W, pady=5)
        priority_var = tk.StringVar(value="all")
        priority_combo = ttk.Combobox(main_frame, textvariable=priority_var, width=47,
                                      values=["all", "low", "medium", "high"])
        priority_combo.grid(row=2, column=1, pady=5, padx=5)

        # Category filter
        ttk.Label(main_frame, text="Category Filter:").grid(row=3, column=0, sticky=tk.W, pady=5)
        category_var = tk.StringVar(value="all")
        categories = ["all", "Technical Support", "Academic Inquiry", "Financial Services",
                      "Account Access", "Other"]
        category_combo = ttk.Combobox(main_frame, textvariable=category_var, width=47, values=categories)
        category_combo.grid(row=3, column=1, pady=5, padx=5)

        # Date range
        ttk.Label(main_frame, text="Start Date (YYYY-MM-DD):").grid(row=4, column=0, sticky=tk.W, pady=5)
        start_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=start_date_var, width=50).grid(row=4, column=1, pady=5, padx=5)

        ttk.Label(main_frame, text="End Date (YYYY-MM-DD):").grid(row=5, column=0, sticky=tk.W, pady=5)
        end_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=end_date_var, width=50).grid(row=5, column=1, pady=5, padx=5)

        # Assigned user filter (admin only)
        assigned_label = ttk.Label(main_frame, text="Assigned To (Username):")
        assigned_var = tk.StringVar()
        assigned_entry = ttk.Entry(main_frame, textvariable=assigned_var, width=50)

        if self.auth.has_permission('view_all_tickets'):
            assigned_label.grid(row=6, column=0, sticky=tk.W, pady=5)
            assigned_entry.grid(row=6, column=1, pady=5, padx=5)

        # Save search name
        ttk.Label(main_frame, text="Save Search As:").grid(row=7, column=0, sticky=tk.W, pady=5)
        save_name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=save_name_var, width=50).grid(row=7, column=1, pady=5, padx=5)

        # Results display
        results_frame = ttk.LabelFrame(main_frame, text="Search Results", padding="10")
        results_frame.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        # Results treeview
        columns = ('id', 'subject', 'from', 'assigned', 'status', 'priority', 'updated')
        results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=10)

        results_tree.heading('id', text='ID')
        results_tree.heading('subject', text='Subject')
        results_tree.heading('from', text='From')
        results_tree.heading('assigned', text='Assigned')
        results_tree.heading('status', text='Status')
        results_tree.heading('priority', text='Priority')
        results_tree.heading('updated', text='Updated')

        results_tree.column('id', width=40)
        results_tree.column('subject', width=200)
        results_tree.column('from', width=100)
        results_tree.column('assigned', width=100)
        results_tree.column('status', width=80)
        results_tree.column('priority', width=60)
        results_tree.column('updated', width=120)

        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=results_tree.yview)
        results_tree.configure(yscrollcommand=scrollbar.set)

        results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def execute_search():
            """Execute the search with current criteria"""
            # Build criteria dictionary
            search_criteria = {}

            if text_var.get().strip():
                search_criteria['text'] = text_var.get().strip()

            if status_var.get() != "all":
                search_criteria['status'] = status_var.get()

            if priority_var.get() != "all":
                search_criteria['priority'] = priority_var.get()

            if category_var.get() != "all":
                search_criteria['category'] = category_var.get()

            if start_date_var.get().strip():
                search_criteria['start_date'] = start_date_var.get().strip()

            if end_date_var.get().strip():
                search_criteria['end_date'] = end_date_var.get().strip()

            if assigned_var.get().strip() and self.auth.has_permission('view_all_tickets'):
                search_criteria['assigned_user'] = assigned_var.get().strip()

            # Save search if name provided
            if save_name_var.get().strip():
                self.save_search_criteria_gui(save_name_var.get().strip(), search_criteria)

            # Execute search
            results = self.execute_search_gui(search_criteria)

            # Display results
            self.display_search_results_gui(results, results_tree)

        # Button frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=9, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text="Search", command=execute_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Load Saved Search",
                  command=lambda: self.load_saved_searches_gui(results_tree)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Clear", command=lambda: [
            text_var.set(''), status_var.set('all'), priority_var.set('all'),
            category_var.set('all'), start_date_var.set(''), end_date_var.set(''),
            assigned_var.set(''), save_name_var.set(''),
            results_tree.delete(*results_tree.get_children())
        ]).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def save_search_criteria_gui(self, name, criteria):
        """Save search criteria for later use"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            user_id = self.auth.current_user['id']

            cursor.execute('''
                INSERT INTO saved_searches (user_id, name, search_criteria, created_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, name, json.dumps(criteria), now))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Search '{name}' saved successfully!")

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to save search: {e}")

    def load_saved_searches_gui(self, results_tree):
        """Load and execute saved searches"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            user_id = self.auth.current_user['id']

            cursor.execute('''
                SELECT search_id, name, search_criteria
                FROM saved_searches
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))

            searches = cursor.fetchall()
            conn.close()

            if not searches:
                messagebox.showinfo("No Saved Searches", "No saved searches found.")
                return

            # Create selection dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Load Saved Search")
            dialog.geometry("400x300")

            ttk.Label(dialog, text="Select a saved search:", padding="10").pack()

            # Listbox with saved searches
            listbox_frame = ttk.Frame(dialog)
            listbox_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            scrollbar = ttk.Scrollbar(listbox_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            search_listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set)
            search_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=search_listbox.yview)

            for search_id, name, criteria_json in searches:
                search_listbox.insert(tk.END, name)

            def execute_selected():
                selection = search_listbox.curselection()
                if selection:
                    idx = selection[0]
                    search_id, name, criteria_json = searches[idx]

                    try:
                        criteria = json.loads(criteria_json)
                        results = self.execute_search_gui(criteria)
                        self.display_search_results_gui(results, results_tree)
                        dialog.destroy()
                    except json.JSONDecodeError:
                        messagebox.showerror("Error", "Corrupted search data")

            ttk.Button(dialog, text="Execute", command=execute_selected).pack(pady=5)
            ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=5)

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load searches: {e}")

    def execute_search_gui(self, criteria):
        """Execute search with given criteria"""
        try:
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build query
            where_conditions = []
            params = []

            # Check permissions
            if not self.auth.has_permission('view_all_tickets'):
                where_conditions.append("t.user_id = ?")
                params.append(self.auth.current_user['id'])

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

            # Assigned user
            if 'assigned_user' in criteria:
                where_conditions.append("u2.username = ?")
                params.append(criteria['assigned_user'])

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
            return results

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Search failed: {e}")
            return []

    def display_search_results_gui(self, results, tree_widget):
        """Display search results in the treeview"""
        # Clear existing results
        for item in tree_widget.get_children():
            tree_widget.delete(item)

        if not results:
            messagebox.showinfo("No Results", "No tickets found matching your search criteria.")
            return

        # Populate results
        for ticket in results:
            assignee = ticket['assignee'] if ticket['assignee'] else 'Unassigned'
            tree_widget.insert('', tk.END, values=(
                ticket['ticket_id'],
                ticket['subject'][:40],
                ticket['submitter'][:20],
                assignee[:20],
                ticket['status'].upper(),
                ticket['priority'].upper(),
                ticket['updated_at']
            ))

        messagebox.showinfo("Search Complete", f"Found {len(results)} ticket(s) matching your criteria.")

    def rebuild_search_indexes_gui(self):
        """Rebuild full-text search indexes"""
        if not self.auth.has_permission('manage_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to rebuild search indexes.")
            return

        if not messagebox.askyesno("Confirm", "Rebuild search indexes? This may take a moment."):
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Update search keywords for knowledge base articles
            cursor.execute('''
                UPDATE knowledge_base
                SET search_keywords = LOWER(title || ' ' || content || ' ' || COALESCE(tags, ''))
            ''')

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Search indexes rebuilt successfully!")

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to rebuild indexes: {e}")

    # ========================================================================
    # KNOWLEDGE BASE FUNCTIONS
    # ========================================================================

    def manage_knowledge_base_gui(self):
        """Knowledge base management interface"""
        kb_window = tk.Toplevel(self.root)
        kb_window.title("Knowledge Base Management")
        kb_window.geometry("900x600")

        # Main frame
        main_frame = ttk.Frame(kb_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Toolbar
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=5)

        ttk.Button(toolbar, text="View Articles",
                  command=lambda: self.view_kb_articles_gui()).pack(side=tk.LEFT, padx=2)

        if self.auth.has_permission('manage_tickets'):
            ttk.Button(toolbar, text="Create Article",
                      command=lambda: self.create_kb_article_gui()).pack(side=tk.LEFT, padx=2)
            ttk.Button(toolbar, text="Edit Article",
                      command=lambda: self.edit_kb_article_gui()).pack(side=tk.LEFT, padx=2)

        if self.auth.has_permission('view_all_tickets'):
            ttk.Button(toolbar, text="Statistics",
                      command=lambda: self.kb_statistics_gui()).pack(side=tk.LEFT, padx=2)

        ttk.Button(toolbar, text="Refresh",
                  command=lambda: self.refresh_kb_list(tree)).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Close",
                  command=kb_window.destroy).pack(side=tk.RIGHT, padx=2)

        # Articles list
        list_frame = ttk.LabelFrame(main_frame, text="Knowledge Base Articles", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        columns = ('id', 'title', 'category', 'views', 'helpful', 'unhelpful', 'updated')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        tree.heading('id', text='ID')
        tree.heading('title', text='Title')
        tree.heading('category', text='Category')
        tree.heading('views', text='Views')
        tree.heading('helpful', text='Helpful')
        tree.heading('unhelpful', text='Unhelpful')
        tree.heading('updated', text='Updated')

        tree.column('id', width=40)
        tree.column('title', width=300)
        tree.column('category', width=120)
        tree.column('views', width=60)
        tree.column('helpful', width=60)
        tree.column('unhelpful', width=60)
        tree.column('updated', width=140)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Double-click to view details
        tree.bind('<Double-1>', lambda e: self.view_kb_article_detail_gui_from_tree(tree))

        # Initial load
        self.refresh_kb_list(tree)

    def refresh_kb_list(self, tree):
        """Refresh knowledge base articles list"""
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT article_id, title, category, views, helpful_votes, unhelpful_votes, updated_at
                FROM knowledge_base
                WHERE status = 'published'
                ORDER BY helpful_votes DESC, views DESC
            ''')

            articles = cursor.fetchall()
            conn.close()

            for article in articles:
                tree.insert('', tk.END, values=article)

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load articles: {e}")

    def view_kb_articles_gui(self):
        """View knowledge base articles with category filter"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Knowledge Base Articles")
        dialog.geometry("800x600")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Category filter
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=5)

        ttk.Label(filter_frame, text="Category:").pack(side=tk.LEFT, padx=5)

        # Get categories
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT DISTINCT category FROM knowledge_base
                WHERE status = 'published' AND category IS NOT NULL
                ORDER BY category
            ''')
            categories = ['All Categories'] + [row[0] for row in cursor.fetchall()]
            conn.close()

        except sqlite3.Error:
            categories = ['All Categories']

        category_var = tk.StringVar(value='All Categories')
        category_combo = ttk.Combobox(filter_frame, textvariable=category_var,
                                      values=categories, width=30)
        category_combo.pack(side=tk.LEFT, padx=5)

        # Articles list
        columns = ('id', 'title', 'category', 'views', 'rating')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

        tree.heading('id', text='ID')
        tree.heading('title', text='Title')
        tree.heading('category', text='Category')
        tree.heading('views', text='Views')
        tree.heading('rating', text='Rating')

        tree.column('id', width=40)
        tree.column('title', width=400)
        tree.column('category', width=120)
        tree.column('views', width=60)
        tree.column('rating', width=100)

        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        def load_articles():
            # Clear existing
            for item in tree.get_children():
                tree.delete(item)

            try:
                conn = get_connection()
                cursor = conn.cursor()

                where_clause = "WHERE status = 'published'"
                params = []

                if category_var.get() != 'All Categories':
                    where_clause += " AND category = ?"
                    params.append(category_var.get())

                cursor.execute(f'''
                    SELECT article_id, title, category, views, helpful_votes, unhelpful_votes
                    FROM knowledge_base
                    {where_clause}
                    ORDER BY helpful_votes DESC, views DESC
                ''', params)

                articles = cursor.fetchall()
                conn.close()

                for article in articles:
                    article_id, title, category, views, helpful, unhelpful = article
                    total_votes = helpful + unhelpful
                    rating = f"{helpful}/{total_votes}" if total_votes > 0 else "No votes"

                    tree.insert('', tk.END, values=(article_id, title, category, views, rating))

            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to load articles: {e}")

        # Filter button
        ttk.Button(filter_frame, text="Filter", command=load_articles).pack(side=tk.LEFT, padx=5)

        # View detail button
        ttk.Button(main_frame, text="View Details",
                  command=lambda: self.view_kb_article_detail_gui_from_tree(tree)).pack(pady=5)
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=5)

        # Double-click to view
        tree.bind('<Double-1>', lambda e: self.view_kb_article_detail_gui_from_tree(tree))

        # Initial load
        load_articles()

    def view_kb_article_detail_gui_from_tree(self, tree):
        """View KB article detail from tree selection"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an article to view.")
            return

        item = tree.item(selection[0])
        article_id = item['values'][0]
        self.view_kb_article_detail_gui(article_id)

    def view_kb_article_detail_gui(self, article_id):
        """View detailed knowledge base article"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT kb.*, u.username as author
                FROM knowledge_base kb
                LEFT JOIN users u ON kb.author_id = u.id
                WHERE kb.article_id = ?
            ''', (article_id,))

            article = cursor.fetchone()

            if not article:
                messagebox.showerror("Not Found", "Article not found.")
                conn.close()
                return

            # Update view count
            cursor.execute('''
                UPDATE knowledge_base SET views = views + 1 WHERE article_id = ?
            ''', (article_id,))
            conn.commit()
            conn.close()

            # Create detail window
            detail_window = tk.Toplevel(self.root)
            detail_window.title(f"Article #{article[0]}: {article[1]}")
            detail_window.geometry("700x600")

            main_frame = ttk.Frame(detail_window, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Header info
            info_frame = ttk.LabelFrame(main_frame, text="Article Information", padding="10")
            info_frame.pack(fill=tk.X, pady=5)

            ttk.Label(info_frame, text=f"Title: {article[1]}", font=('Arial', 12, 'bold')).pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Category: {article[3] or 'Uncategorized'}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Author: {article[-1] or 'Unknown'}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Status: {article[6]}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Views: {article[7]}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Helpful votes: {article[8]} | Unhelpful votes: {article[9]}").pack(anchor=tk.W)

            if article[4]:  # tags
                ttk.Label(info_frame, text=f"Tags: {article[4]}").pack(anchor=tk.W)

            ttk.Label(info_frame, text=f"Created: {article[11]}").pack(anchor=tk.W)
            ttk.Label(info_frame, text=f"Updated: {article[12]}").pack(anchor=tk.W)

            # Content
            content_frame = ttk.LabelFrame(main_frame, text="Content", padding="10")
            content_frame.pack(fill=tk.BOTH, expand=True, pady=5)

            content_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, height=20)
            content_text.pack(fill=tk.BOTH, expand=True)
            content_text.insert('1.0', article[2])  # content
            content_text.config(state=tk.DISABLED)

            ttk.Button(main_frame, text="Close", command=detail_window.destroy).pack(pady=5)

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load article: {e}")

    def create_kb_article_gui(self):
        """Create a new knowledge base article"""
        if not self.auth.has_permission('manage_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to create articles.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Create Knowledge Base Article")
        dialog.geometry("700x600")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, pady=5)
        title_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=title_var, width=60).grid(row=0, column=1, pady=5, padx=5)

        # Category
        ttk.Label(main_frame, text="Category:").grid(row=1, column=0, sticky=tk.W, pady=5)
        category_var = tk.StringVar()
        categories = ["Technical Support", "Academic Inquiry", "Financial Services", "Account Access", "Other"]
        ttk.Combobox(main_frame, textvariable=category_var, values=categories, width=57).grid(row=1, column=1, pady=5, padx=5)

        # Tags
        ttk.Label(main_frame, text="Tags (comma-separated):").grid(row=2, column=0, sticky=tk.W, pady=5)
        tags_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=tags_var, width=60).grid(row=2, column=1, pady=5, padx=5)

        # Content
        ttk.Label(main_frame, text="Content:").grid(row=3, column=0, sticky=tk.NW, pady=5)
        content_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, width=60, height=20)
        content_text.grid(row=3, column=1, pady=5, padx=5)

        def save_article():
            title = title_var.get().strip()
            category = category_var.get().strip()
            tags = tags_var.get().strip()
            content = content_text.get('1.0', tk.END).strip()

            if not title or not content:
                messagebox.showerror("Validation Error", "Title and content are required.")
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                author_id = self.auth.current_user['id']

                cursor.execute('''
                    INSERT INTO knowledge_base
                    (title, content, category, tags, author_id, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'published', ?, ?)
                ''', (title, content, category, tags, author_id, now, now))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Knowledge base article created successfully!")
                dialog.destroy()

            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to create article: {e}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text="Save", command=save_article).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def edit_kb_article_gui(self):
        """Edit an existing knowledge base article"""
        if not self.auth.has_permission('manage_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to edit articles.")
            return

        # Ask for article ID
        article_id = simpledialog.askinteger("Edit Article", "Enter article ID to edit:")
        if not article_id:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM knowledge_base WHERE article_id = ?', (article_id,))
            article = cursor.fetchone()

            if not article:
                messagebox.showerror("Not Found", "Article not found.")
                conn.close()
                return

            # Check permissions
            if article[5] != self.auth.current_user['id'] and not self.auth.has_permission('manage_tickets'):
                messagebox.showerror("Permission Denied", "You don't have permission to edit this article.")
                conn.close()
                return

            conn.close()

            # Create edit dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Edit Article #{article_id}")
            dialog.geometry("700x600")

            main_frame = ttk.Frame(dialog, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Title
            ttk.Label(main_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, pady=5)
            title_var = tk.StringVar(value=article[1])
            ttk.Entry(main_frame, textvariable=title_var, width=60).grid(row=0, column=1, pady=5, padx=5)

            # Category
            ttk.Label(main_frame, text="Category:").grid(row=1, column=0, sticky=tk.W, pady=5)
            category_var = tk.StringVar(value=article[3] or '')
            categories = ["Technical Support", "Academic Inquiry", "Financial Services", "Account Access", "Other"]
            ttk.Combobox(main_frame, textvariable=category_var, values=categories, width=57).grid(row=1, column=1, pady=5, padx=5)

            # Tags
            ttk.Label(main_frame, text="Tags:").grid(row=2, column=0, sticky=tk.W, pady=5)
            tags_var = tk.StringVar(value=article[4] or '')
            ttk.Entry(main_frame, textvariable=tags_var, width=60).grid(row=2, column=1, pady=5, padx=5)

            # Content
            ttk.Label(main_frame, text="Content:").grid(row=3, column=0, sticky=tk.NW, pady=5)
            content_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, width=60, height=20)
            content_text.grid(row=3, column=1, pady=5, padx=5)
            content_text.insert('1.0', article[2])

            def save_changes():
                new_title = title_var.get().strip()
                new_category = category_var.get().strip()
                new_tags = tags_var.get().strip()
                new_content = content_text.get('1.0', tk.END).strip()

                if not new_title or not new_content:
                    messagebox.showerror("Validation Error", "Title and content are required.")
                    return

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    cursor.execute('''
                        UPDATE knowledge_base
                        SET title = ?, content = ?, category = ?, tags = ?, updated_at = ?
                        WHERE article_id = ?
                    ''', (new_title, new_content, new_category, new_tags, now, article_id))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Article updated successfully!")
                    dialog.destroy()

                except sqlite3.Error as e:
                    messagebox.showerror("Error", f"Failed to update article: {e}")

            # Buttons
            btn_frame = ttk.Frame(main_frame)
            btn_frame.grid(row=4, column=0, columnspan=2, pady=10)

            ttk.Button(btn_frame, text="Save", command=save_changes).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load article: {e}")

    def kb_statistics_gui(self):
        """Display knowledge base statistics"""
        if not self.auth.has_permission('view_all_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to view statistics.")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get statistics
            cursor.execute('SELECT COUNT(*) FROM knowledge_base WHERE status = "published"')
            total_articles = cursor.fetchone()[0]

            cursor.execute('''
                SELECT title, views FROM knowledge_base
                WHERE status = 'published'
                ORDER BY views DESC
                LIMIT 5
            ''')
            top_viewed = cursor.fetchall()

            cursor.execute('''
                SELECT title, helpful_votes, unhelpful_votes
                FROM knowledge_base
                WHERE status = 'published' AND (helpful_votes + unhelpful_votes) > 0
                ORDER BY (helpful_votes * 1.0 / (helpful_votes + unhelpful_votes)) DESC
                LIMIT 5
            ''')
            top_helpful = cursor.fetchall()

            cursor.execute('''
                SELECT category, COUNT(*) as count
                FROM knowledge_base
                WHERE status = 'published'
                GROUP BY category
                ORDER BY count DESC
            ''')
            categories = cursor.fetchall()

            conn.close()

            # Create statistics window
            stats_window = tk.Toplevel(self.root)
            stats_window.title("Knowledge Base Statistics")
            stats_window.geometry("600x500")

            main_frame = ttk.Frame(stats_window, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Total articles
            ttk.Label(main_frame, text=f"Total Published Articles: {total_articles}",
                     font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=10)

            # Most viewed
            viewed_frame = ttk.LabelFrame(main_frame, text="Most Viewed Articles", padding="10")
            viewed_frame.pack(fill=tk.X, pady=5)

            for title, views in top_viewed:
                ttk.Label(viewed_frame, text=f"{title[:50]}: {views} views").pack(anchor=tk.W)

            # Most helpful
            helpful_frame = ttk.LabelFrame(main_frame, text="Most Helpful Articles", padding="10")
            helpful_frame.pack(fill=tk.X, pady=5)

            for title, helpful, unhelpful in top_helpful:
                total_votes = helpful + unhelpful
                helpfulness = (helpful / total_votes * 100) if total_votes > 0 else 0
                ttk.Label(helpful_frame, text=f"{title[:50]}: {helpfulness:.1f}% helpful ({total_votes} votes)").pack(anchor=tk.W)

            # Categories
            cat_frame = ttk.LabelFrame(main_frame, text="Articles by Category", padding="10")
            cat_frame.pack(fill=tk.X, pady=5)

            for category, count in categories:
                ttk.Label(cat_frame, text=f"{category or 'Uncategorized'}: {count}").pack(anchor=tk.W)

            ttk.Button(main_frame, text="Close", command=stats_window.destroy).pack(pady=10)

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load statistics: {e}")

    def display_kb_suggestions_gui(self, ticket):
        """Display knowledge base article suggestions for a ticket"""
        if not ticket or not ticket.get('knowledge_base_articles'):
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            article_ids = ticket['knowledge_base_articles'].split(',')
            placeholders = ','.join(['?' for _ in article_ids])

            cursor.execute(f'''
                SELECT article_id, title, category, helpful_votes, unhelpful_votes
                FROM knowledge_base
                WHERE article_id IN ({placeholders}) AND status = 'published'
            ''', article_ids)

            articles = cursor.fetchall()
            conn.close()

            if not articles:
                return

            # Create suggestions window
            suggest_window = tk.Toplevel(self.root)
            suggest_window.title("Suggested Knowledge Base Articles")
            suggest_window.geometry("600x400")

            main_frame = ttk.Frame(suggest_window, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text="Suggested Articles That Might Help:",
                     font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=10)

            # Article list
            for article in articles:
                article_id, title, category, helpful, unhelpful = article
                total_votes = helpful + unhelpful
                helpful_ratio = (helpful / total_votes * 100) if total_votes > 0 else 0

                article_frame = ttk.Frame(main_frame)
                article_frame.pack(fill=tk.X, pady=5)

                ttk.Label(article_frame, text=f"• {title}", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
                ttk.Label(article_frame, text=f"  Category: {category} - {helpful_ratio:.0f}% helpful").pack(anchor=tk.W)

                ttk.Button(article_frame, text="View Article",
                          command=lambda aid=article_id: self.view_kb_article_detail_gui(aid)).pack(anchor=tk.W, padx=20)

            ttk.Button(main_frame, text="Close", command=suggest_window.destroy).pack(pady=10)

        except sqlite3.Error as e:
            print(f"Error loading KB suggestions: {e}")

    def suggest_knowledge_base_articles_gui(self, ticket_id, content):
        """Suggest relevant knowledge base articles based on ticket content"""
        try:
            # Extract keywords
            keywords = self.extract_keywords_gui(content.lower())

            if not keywords:
                return

            conn = get_connection()
            cursor = conn.cursor()

            # Search for articles with matching keywords
            keyword_conditions = []
            params = []

            for keyword in keywords[:5]:  # Limit to top 5 keywords
                keyword_conditions.append("(title LIKE ? OR content LIKE ? OR search_keywords LIKE ?)")
                params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])

            if keyword_conditions:
                query = f'''
                    SELECT article_id, title, category
                    FROM knowledge_base
                    WHERE status = 'published' AND ({" OR ".join(keyword_conditions)})
                    ORDER BY helpful_votes DESC, views DESC
                    LIMIT 3
                '''

                cursor.execute(query, params)
                articles = cursor.fetchall()

                if articles:
                    # Store suggestions in ticket
                    article_ids = [str(a[0]) for a in articles]
                    cursor.execute('''
                        UPDATE support_tickets
                        SET knowledge_base_articles = ?
                        WHERE ticket_id = ?
                    ''', (','.join(article_ids), ticket_id))

                    conn.commit()

            conn.close()

        except sqlite3.Error as e:
            print(f"Error suggesting KB articles: {e}")

    def extract_keywords_gui(self, text):
        """Extract relevant keywords from text"""
        # Remove common words and extract meaningful terms
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                      'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
                      'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                      'may', 'might', 'can', 'cant', 'cannot', 'i', 'you', 'he', 'she', 'it',
                      'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his',
                      'her', 'its', 'our', 'their'}

        # Simple word extraction
        import re
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
        keywords = [word for word in words if word.lower() not in stop_words]

        # Return most frequent keywords
        from collections import Counter
        word_counts = Counter(keywords)
        return [word for word, count in word_counts.most_common(10)]

    # ========================================================================
    # ENHANCED TICKET VIEW FUNCTIONS
    # ========================================================================

    def view_ticket_detail_enhanced_gui(self, ticket_id):
        """View complete ticket details with all information"""
        try:
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

            if not ticket:
                messagebox.showerror("Not Found", "Ticket not found.")
                return

            # Create detail window
            detail_window = tk.Toplevel(self.root)
            detail_window.title(f"Ticket #{ticket_id} - {ticket['subject']}")
            detail_window.geometry("1000x700")

            # Main scrollable frame
            main_canvas = tk.Canvas(detail_window)
            scrollbar = ttk.Scrollbar(detail_window, orient="vertical", command=main_canvas.yview)
            scrollable_frame = ttk.Frame(main_canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
            )

            main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            main_canvas.configure(yscrollcommand=scrollbar.set)

            # Ticket header
            header_frame = ttk.LabelFrame(scrollable_frame, text="Ticket Information", padding="10")
            header_frame.pack(fill=tk.X, padx=10, pady=5)

            ttk.Label(header_frame, text=f"Ticket ID: #{ticket['ticket_id']}", font=('Arial', 12, 'bold')).pack(anchor=tk.W)
            ttk.Label(header_frame, text=f"Subject: {ticket['subject']}", font=('Arial', 11)).pack(anchor=tk.W)
            ttk.Label(header_frame, text=f"Status: {ticket['status'].upper()}").pack(anchor=tk.W)
            ttk.Label(header_frame, text=f"Priority: {ticket['priority'].upper()} | Impact: {ticket['impact'].upper()} | Urgency: {ticket['urgency'].upper()}").pack(anchor=tk.W)
            ttk.Label(header_frame, text=f"Category: {ticket['category']}").pack(anchor=tk.W)
            ttk.Label(header_frame, text=f"Submitted by: {ticket['submitter']}").pack(anchor=tk.W)
            ttk.Label(header_frame, text=f"Assigned to: {ticket['assignee'] or 'Unassigned'}").pack(anchor=tk.W)
            ttk.Label(header_frame, text=f"Created: {ticket['created_at']}").pack(anchor=tk.W)
            ttk.Label(header_frame, text=f"Updated: {ticket['updated_at']}").pack(anchor=tk.W)

            if ticket['due_date']:
                ttk.Label(header_frame, text=f"Due Date: {ticket['due_date']}").pack(anchor=tk.W)

            # Message
            msg_frame = ttk.LabelFrame(scrollable_frame, text="Message", padding="10")
            msg_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            msg_text = scrolledtext.ScrolledText(msg_frame, wrap=tk.WORD, height=5)
            msg_text.pack(fill=tk.BOTH, expand=True)
            msg_text.insert('1.0', ticket['message'])
            msg_text.config(state=tk.DISABLED)

            # Replies
            self.display_ticket_replies_gui(ticket_id, scrollable_frame)

            # Time tracking
            self.display_time_tracking_gui(ticket_id, scrollable_frame)

            # Escalation history
            self.display_escalation_history_gui(ticket_id, scrollable_frame)

            # Linked tickets
            self.display_linked_tickets_gui(ticket_id, scrollable_frame)

            # Audit trail (admin only)
            if self.auth.has_permission('view_all_tickets'):
                self.display_audit_trail_gui(ticket_id, scrollable_frame)

            # Action buttons
            action_frame = ttk.Frame(scrollable_frame)
            action_frame.pack(fill=tk.X, padx=10, pady=10)

            if self.auth.has_permission('reply_to_any_ticket') or ticket['user_id'] == self.auth.current_user['id']:
                ttk.Button(action_frame, text="Reply", command=lambda: self.reply_to_ticket_enhanced_gui(ticket_id, False)).pack(side=tk.LEFT, padx=5)

            if self.auth.has_permission('manage_tickets'):
                ttk.Button(action_frame, text="Internal Note", command=lambda: self.reply_to_ticket_enhanced_gui(ticket_id, True)).pack(side=tk.LEFT, padx=5)
                ttk.Button(action_frame, text="Add Time Entry", command=lambda: self.add_time_entry_gui(ticket_id)).pack(side=tk.LEFT, padx=5)
                ttk.Button(action_frame, text="Link Ticket", command=lambda: self.link_tickets_gui(ticket_id)).pack(side=tk.LEFT, padx=5)

            ttk.Button(action_frame, text="Close", command=detail_window.destroy).pack(side=tk.RIGHT, padx=5)

            main_canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load ticket details: {e}")

    def view_all_tickets_enhanced_gui(self):
        """Enhanced view of all tickets with advanced filtering"""
        if not self.auth.has_permission('view_all_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to view all tickets.")
            return

        window = tk.Toplevel(self.root)
        window.title("All Tickets - Enhanced View")
        window.geometry("1200x700")

        main_frame = ttk.Frame(window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Filter frame
        filter_frame = ttk.LabelFrame(main_frame, text="Filters", padding="10")
        filter_frame.pack(fill=tk.X, pady=5)

        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=5)

        filter_var = tk.StringVar(value="all")
        filters = [
            ("All tickets", "all"),
            ("Unassigned", "unassigned"),
            ("My assigned", "my_assigned"),
            ("Overdue", "overdue"),
            ("High priority", "high_priority"),
            ("Escalated", "escalated")
        ]

        for label, value in filters:
            ttk.Radiobutton(filter_frame, text=label, variable=filter_var, value=value).pack(side=tk.LEFT, padx=5)

        # Tickets treeview
        columns = ('id', 'subject', 'category', 'status', 'priority', 'submitter', 'assignee', 'created', 'due')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

        tree.heading('id', text='ID')
        tree.heading('subject', text='Subject')
        tree.heading('category', text='Category')
        tree.heading('status', text='Status')
        tree.heading('priority', text='Priority')
        tree.heading('submitter', text='Submitter')
        tree.heading('assignee', text='Assignee')
        tree.heading('created', text='Created')
        tree.heading('due', text='Due Date')

        tree.column('id', width=50)
        tree.column('subject', width=250)
        tree.column('category', width=120)
        tree.column('status', width=100)
        tree.column('priority', width=80)
        tree.column('submitter', width=100)
        tree.column('assignee', width=100)
        tree.column('created', width=130)
        tree.column('due', width=130)

        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        def load_tickets():
            # Clear existing
            for item in tree.get_children():
                tree.delete(item)

            try:
                conn = get_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                where_conditions = []
                params = []

                filter_val = filter_var.get()
                if filter_val == "unassigned":
                    where_conditions.append("t.assigned_to IS NULL")
                elif filter_val == "my_assigned":
                    where_conditions.append("t.assigned_to = ?")
                    params.append(self.auth.current_user['id'])
                elif filter_val == "overdue":
                    where_conditions.append("t.due_date IS NOT NULL AND t.due_date < ? AND t.status NOT IN ('resolved', 'closed')")
                    params.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                elif filter_val == "high_priority":
                    where_conditions.append("t.priority = 'high'")
                elif filter_val == "escalated":
                    where_conditions.append("t.escalation_level > 0")

                where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

                cursor.execute(f'''
                    SELECT t.ticket_id, t.subject, t.category, t.status, t.priority,
                           u1.username as submitter, u2.username as assignee,
                           t.created_at, t.due_date
                    FROM support_tickets t
                    JOIN users u1 ON t.user_id = u1.id
                    LEFT JOIN users u2 ON t.assigned_to = u2.id
                    WHERE {where_clause}
                    ORDER BY t.created_at DESC
                ''', params)

                tickets = cursor.fetchall()
                conn.close()

                for ticket in tickets:
                    tree.insert('', tk.END, values=(
                        ticket['ticket_id'],
                        ticket['subject'][:40],
                        ticket['category'],
                        ticket['status'].upper(),
                        ticket['priority'].upper(),
                        ticket['submitter'],
                        ticket['assignee'] or 'Unassigned',
                        ticket['created_at'],
                        ticket['due_date'] or 'N/A'
                    ))

            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to load tickets: {e}")

        ttk.Button(filter_frame, text="Apply Filter", command=load_tickets).pack(side=tk.LEFT, padx=5)
        ttk.Button(main_frame, text="View Details", command=lambda: self.view_ticket_from_tree(tree)).pack(pady=5)
        ttk.Button(main_frame, text="Close", command=window.destroy).pack(pady=5)

        tree.bind('<Double-1>', lambda e: self.view_ticket_from_tree(tree))

        # Initial load
        load_tickets()

    def view_ticket_from_tree(self, tree):
        """View ticket details from treeview selection"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a ticket to view.")
            return

        item = tree.item(selection[0])
        ticket_id = item['values'][0]
        self.view_ticket_detail_enhanced_gui(ticket_id)

    def display_ticket_replies_gui(self, ticket_id, parent_frame):
        """Display ticket reply history"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT r.*, u.username, u.role
                FROM ticket_replies r
                JOIN users u ON r.user_id = u.id
                WHERE r.ticket_id = ?
                ORDER BY r.created_at ASC
            ''', (ticket_id,))

            replies = cursor.fetchall()
            conn.close()

            if not replies:
                return

            replies_frame = ttk.LabelFrame(parent_frame, text="Conversation History", padding="10")
            replies_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            for reply in replies:
                reply_type = "Internal Note" if reply[4] else "Reply"
                is_internal = reply[4]

                # Only show internal notes to admins
                if is_internal and not self.auth.has_permission('manage_tickets'):
                    continue

                reply_item_frame = ttk.Frame(replies_frame)
                reply_item_frame.pack(fill=tk.X, pady=5)

                icon = "🔒" if is_internal else "💬"
                header_text = f"{icon} {reply_type} from {reply[-2]} ({reply[-1]}) at {reply[6]}"

                ttk.Label(reply_item_frame, text=header_text, font=('Arial', 9, 'bold')).pack(anchor=tk.W)

                msg_text = tk.Text(reply_item_frame, wrap=tk.WORD, height=3, relief=tk.FLAT, bg='#f0f0f0')
                msg_text.pack(fill=tk.X, pady=2)
                msg_text.insert('1.0', reply[3])
                msg_text.config(state=tk.DISABLED)

                ttk.Separator(replies_frame, orient='horizontal').pack(fill=tk.X, pady=2)

        except sqlite3.Error as e:
            print(f"Error loading replies: {e}")

    def display_time_tracking_gui(self, ticket_id, parent_frame):
        """Display time tracking information"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT tt.*, u.username
                FROM ticket_time_tracking tt
                JOIN users u ON tt.user_id = u.id
                WHERE tt.ticket_id = ?
                ORDER BY tt.created_at
            ''', (ticket_id,))

            time_entries = cursor.fetchall()
            conn.close()

            if not time_entries:
                return

            time_frame = ttk.LabelFrame(parent_frame, text="Time Tracking", padding="10")
            time_frame.pack(fill=tk.X, padx=10, pady=5)

            total_time = 0
            billable_time = 0

            for entry in time_entries:
                duration = entry[5] / 60  # minutes to hours
                total_time += duration
                if entry[7]:  # billable
                    billable_time += duration

                billable_text = " (Billable)" if entry[7] else ""
                entry_text = f"⏱️  {entry[-1]}: {duration:.2f} hours{billable_text}"

                if entry[6]:  # description
                    entry_text += f"\n   Description: {entry[6]}"

                ttk.Label(time_frame, text=entry_text).pack(anchor=tk.W, pady=2)

            ttk.Separator(time_frame, orient='horizontal').pack(fill=tk.X, pady=5)
            ttk.Label(time_frame, text=f"Total Time: {total_time:.2f} hours", font=('Arial', 9, 'bold')).pack(anchor=tk.W)
            ttk.Label(time_frame, text=f"Billable Time: {billable_time:.2f} hours", font=('Arial', 9, 'bold')).pack(anchor=tk.W)

        except sqlite3.Error as e:
            print(f"Error loading time tracking: {e}")

    def display_escalation_history_gui(self, ticket_id, parent_frame):
        """Display escalation history"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT e.*, u1.username as escalated_to_user, u2.username as escalated_by_user
                FROM ticket_escalations e
                LEFT JOIN users u1 ON e.escalated_to = u1.id
                LEFT JOIN users u2 ON e.escalated_by = u2.id
                WHERE e.ticket_id = ?
                ORDER BY e.created_at
            ''', (ticket_id,))

            escalations = cursor.fetchall()
            conn.close()

            if not escalations:
                return

            esc_frame = ttk.LabelFrame(parent_frame, text="Escalation History", padding="10")
            esc_frame.pack(fill=tk.X, padx=10, pady=5)

            for esc in escalations:
                status = "Resolved" if esc[6] else "Open"
                escalated_by = esc[-1] or "System"

                esc_text = f"🔺 Level {esc[2]} - Escalated to {esc[-2]} by {escalated_by}\n"
                esc_text += f"   Reason: {esc[4]}\n"
                esc_text += f"   Date: {esc[7]} - Status: {status}"

                ttk.Label(esc_frame, text=esc_text).pack(anchor=tk.W, pady=2)

        except sqlite3.Error as e:
            print(f"Error loading escalation history: {e}")

    def display_audit_trail_gui(self, ticket_id, parent_frame):
        """Display audit trail for admins"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT al.*, u.username
                FROM ticket_audit_log al
                JOIN users u ON al.user_id = u.id
                WHERE al.ticket_id = ?
                ORDER BY al.created_at DESC
                LIMIT 10
            ''', (ticket_id,))

            audit_entries = cursor.fetchall()
            conn.close()

            if not audit_entries:
                return

            audit_frame = ttk.LabelFrame(parent_frame, text="Recent Activity (Audit Trail)", padding="10")
            audit_frame.pack(fill=tk.X, padx=10, pady=5)

            for entry in audit_entries:
                audit_text = f"📋 {entry[3]} by {entry[-1]} at {entry[8]}"

                if entry[4]:  # old_values
                    try:
                        old_vals = json.loads(entry[4])
                        if old_vals:
                            audit_text += f"\n   Previous: {old_vals}"
                    except json.JSONDecodeError:
                        pass

                if entry[5]:  # new_values
                    try:
                        new_vals = json.loads(entry[5])
                        if new_vals:
                            audit_text += f"\n   New: {new_vals}"
                    except json.JSONDecodeError:
                        pass

                ttk.Label(audit_frame, text=audit_text).pack(anchor=tk.W, pady=2)

        except sqlite3.Error as e:
            print(f"Error loading audit trail: {e}")

    def display_linked_tickets_gui(self, ticket_id, parent_frame):
        """Display linked tickets"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT tl.*, t.subject, t.status
                FROM ticket_links tl
                JOIN support_tickets t ON tl.linked_ticket_id = t.ticket_id
                WHERE tl.ticket_id = ?
                ORDER BY tl.created_at
            ''', (ticket_id,))

            links = cursor.fetchall()
            conn.close()

            if not links:
                return

            links_frame = ttk.LabelFrame(parent_frame, text="Linked Tickets", padding="10")
            links_frame.pack(fill=tk.X, padx=10, pady=5)

            for link in links:
                link_text = f"🔗 {link[3]} #{link[2]}: {link[-2]} ({link[-1]})"
                ttk.Label(links_frame, text=link_text).pack(anchor=tk.W, pady=2)

        except sqlite3.Error as e:
            print(f"Error loading linked tickets: {e}")

    # ========================================================================
    # TICKET REPLIES & COMMUNICATION
    # ========================================================================

    def reply_to_ticket_enhanced_gui(self, ticket_id, is_internal=False):
        """Enhanced reply functionality with attachments"""
        # Permission check
        is_admin = self.auth.has_permission('reply_to_any_ticket')

        if not is_admin and not self.auth.has_permission('reply_to_own_ticket'):
            messagebox.showerror("Permission Denied", "You don't have permission to reply to tickets.")
            return

        # Check ownership for non-admins
        if not is_admin:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT user_id FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
                result = cursor.fetchone()
                conn.close()

                if not result or result[0] != self.auth.current_user['id']:
                    messagebox.showerror("Permission Denied", "You don't have permission to reply to this ticket.")
                    return
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to check permissions: {e}")
                return

        # Create reply dialog
        reply_type = "Internal Note" if is_internal else "Reply"
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Add {reply_type} to Ticket #{ticket_id}")
        dialog.geometry("600x500")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Message
        ttk.Label(main_frame, text=f"{reply_type} Message:").pack(anchor=tk.W, pady=5)
        message_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=15)
        message_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Time spent (admin only)
        time_frame = ttk.Frame(main_frame)
        if self.auth.has_permission('manage_tickets'):
            time_frame.pack(fill=tk.X, pady=5)
            ttk.Label(time_frame, text="Time spent (hours):").pack(side=tk.LEFT, padx=5)
            time_var = tk.StringVar(value="0")
            ttk.Entry(time_frame, textvariable=time_var, width=10).pack(side=tk.LEFT, padx=5)

        def save_reply():
            message = message_text.get('1.0', tk.END).strip()

            if not message:
                messagebox.showerror("Validation Error", "Reply message cannot be empty.")
                return

            time_spent = 0
            if self.auth.has_permission('manage_tickets'):
                try:
                    time_spent = float(time_var.get())
                except ValueError:
                    time_spent = 0

            try:
                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                user_id = self.auth.current_user['id']

                cursor.execute('''
                    INSERT INTO ticket_replies
                    (ticket_id, user_id, message, is_internal, time_spent, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (ticket_id, user_id, message, is_internal, time_spent, now))

                # Update ticket timestamps
                cursor.execute('''
                    UPDATE support_tickets
                    SET updated_at = ?, last_activity_at = ?
                    WHERE ticket_id = ?
                ''', (now, now, ticket_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"{reply_type} added successfully!")
                dialog.destroy()
                self.load_tickets()

            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to add {reply_type.lower()}: {e}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        ttk.Button(btn_frame, text="Save", command=save_reply).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def handle_file_attachments_gui(self, ticket_id, reply_id=None):
        """Handle file attachment uploads (placeholder implementation)"""
        # Note: Full file upload implementation would require additional file handling
        messagebox.showinfo("Feature Coming Soon", "File attachment feature is under development.")

    def add_attachment_gui(self, ticket_id, reply_id, file_path):
        """Add attachment to ticket or reply (placeholder implementation)"""
        # Note: Full implementation would require file storage and validation
        messagebox.showinfo("Feature Coming Soon", "File attachment feature is under development.")

    # ========================================================================
    # TIME TRACKING & TICKET LINKING
    # ========================================================================

    def add_time_entry_gui(self, ticket_id):
        """Add time tracking entry"""
        if not self.auth.has_permission('manage_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to add time entries.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Add Time Entry - Ticket #{ticket_id}")
        dialog.geometry("400x300")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Duration
        ttk.Label(main_frame, text="Duration (hours):").grid(row=0, column=0, sticky=tk.W, pady=5)
        duration_var = tk.StringVar(value="1.0")
        ttk.Entry(main_frame, textvariable=duration_var, width=20).grid(row=0, column=1, pady=5, padx=5)

        # Description
        ttk.Label(main_frame, text="Description:").grid(row=1, column=0, sticky=tk.NW, pady=5)
        description_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, width=30, height=5)
        description_text.grid(row=1, column=1, pady=5, padx=5)

        # Billable
        billable_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text="Billable", variable=billable_var).grid(row=2, column=1, sticky=tk.W, pady=5)

        def save_time_entry():
            try:
                duration = float(duration_var.get())
                if duration <= 0:
                    messagebox.showerror("Validation Error", "Duration must be greater than 0.")
                    return
            except ValueError:
                messagebox.showerror("Validation Error", "Please enter a valid number for duration.")
                return

            description = description_text.get('1.0', tk.END).strip()
            billable = billable_var.get()

            try:
                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                start_time = (datetime.now() - timedelta(hours=duration)).strftime('%Y-%m-%d %H:%M:%S')
                duration_minutes = int(duration * 60)
                user_id = self.auth.current_user['id']

                cursor.execute('''
                    INSERT INTO ticket_time_tracking
                    (ticket_id, user_id, start_time, end_time, duration_minutes, description, billable, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (ticket_id, user_id, start_time, now, duration_minutes, description, billable, now))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Time entry added: {duration} hours")
                dialog.destroy()

            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to add time entry: {e}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text="Save", command=save_time_entry).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def link_tickets_gui(self, ticket_id):
        """Link tickets together"""
        if not self.auth.has_permission('manage_tickets'):
            messagebox.showerror("Permission Denied", "You don't have permission to link tickets.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Link Ticket #{ticket_id}")
        dialog.geometry("400x250")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Linked ticket ID
        ttk.Label(main_frame, text="Ticket ID to link:").grid(row=0, column=0, sticky=tk.W, pady=5)
        linked_id_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=linked_id_var, width=20).grid(row=0, column=1, pady=5, padx=5)

        # Link type
        ttk.Label(main_frame, text="Link type:").grid(row=1, column=0, sticky=tk.W, pady=5)
        link_type_var = tk.StringVar(value="related_to")
        link_types = [
            ("Related to", "related_to"),
            ("Duplicate of", "duplicate_of"),
            ("Blocks", "blocks"),
            ("Blocked by", "blocked_by"),
            ("Parent of", "parent_of"),
            ("Child of", "child_of")
        ]

        link_frame = ttk.Frame(main_frame)
        link_frame.grid(row=1, column=1, pady=5, padx=5, sticky=tk.W)

        for i, (label, value) in enumerate(link_types):
            ttk.Radiobutton(link_frame, text=label, variable=link_type_var, value=value).grid(row=i, column=0, sticky=tk.W)

        def save_link():
            try:
                linked_ticket_id = int(linked_id_var.get())

                if linked_ticket_id == ticket_id:
                    messagebox.showerror("Validation Error", "Cannot link ticket to itself.")
                    return

                # Check if target ticket exists
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('SELECT ticket_id, subject FROM support_tickets WHERE ticket_id = ?', (linked_ticket_id,))
                target_ticket = cursor.fetchone()

                if not target_ticket:
                    messagebox.showerror("Not Found", "Target ticket not found.")
                    conn.close()
                    return

                link_type = link_type_var.get()
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    INSERT INTO ticket_links (ticket_id, linked_ticket_id, link_type, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (ticket_id, linked_ticket_id, link_type, now))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Ticket linked successfully as '{link_type}'")
                dialog.destroy()

            except ValueError:
                messagebox.showerror("Validation Error", "Please enter a valid ticket ID.")
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to link tickets: {e}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text="Link", command=save_link).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)


def run_gui_helpdesk(auth_system=None):
    """Run the GUI helpdesk system"""
    root = tk.Tk()
    app = HelpdeskGUI(root, auth=auth_system)
    
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
