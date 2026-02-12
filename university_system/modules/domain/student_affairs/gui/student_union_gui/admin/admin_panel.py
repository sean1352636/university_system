import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from university_system.infrastructure.email.template_utils import render_template
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth
from university_system.core.sql_safety import validate_table_name

# Import i18n for multi-language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from university_system.infrastructure.database.db import get_connection
    from university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False
    

def show_admin_content(self):
    """Display admin panel in main content area"""
    if not (self.is_admin() or self.is_staff()):
        messagebox.showerror("Access Denied", "Admin or staff access required")
        return
    self.clear_content()
    admin_frame = ttk.Frame(self.content_frame)
    admin_frame.pack(fill=tk.BOTH, expand=True)
    # Create and display admin content without notebook
    self._render_admin_tab(admin_frame)


def _render_admin_tab(self, parent_frame):
    """Render admin content in the provided parent frame"""
    ttk.Label(parent_frame, text="System Administration",
             font=('Arial', 14, 'bold')).pack(pady=10)
    # Admin sections
    admin_notebook = ttk.Notebook(parent_frame)
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


def show_admin_tab(self):
    """Legacy method for backwards compatibility - creates tab in notebook if exists"""
    if hasattr(self, 'notebook') and self.notebook:
        admin_frame = ttk.Frame(self.notebook)
        self.notebook.add(admin_frame, text="Administration")
        self._render_admin_tab(admin_frame)
    else:
        # Fall back to content display
        self.show_admin_content()


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
        # Use central authentication system for role changes
        if not self.auth_manager:
            messagebox.showerror("Error", "Authentication system not available")
            return
        try:
            success = self.auth_manager.update_user(user_id, role=new_role)
            if success:
                messagebox.showinfo("Success", f"Role changed to {new_role}")
                self.refresh_users_list()
                # Log activity
                try:
                    from university_system.modules.shared.utils.activity_logger import log_activity
                    log_activity('update', 'user_role', user_id=user_id,
                                details={'username': username, 'old_role': current_role, 'new_role': new_role})
                except (ImportError, sqlite3.Error, OSError) as log_error:
                    print(f"Activity logging failed: {log_error}")
            else:
                messagebox.showerror("Error", "Failed to change role")
        except (tk.TclError, AttributeError) as e:
            messagebox.showerror("Error", f"Failed to change role: {e}")
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
        # Use central authentication system for user deletion
        if not self.auth_manager:
            messagebox.showerror("Error", "Authentication system not available")
            return
        try:
            success = self.auth_manager.delete_user(user_id)
            if success:
                messagebox.showinfo("Success", f"User '{username}' deleted")
                self.refresh_users_list()
                # Log activity
                try:
                    from university_system.modules.shared.utils.activity_logger import log_activity
                    log_activity('delete', 'user', user_id=user_id,
                                details={'username': username})
                except (ImportError, sqlite3.Error, OSError) as log_error:
                    print(f"Activity logging failed: {log_error}")
            else:
                messagebox.showerror("Error", "Failed to delete user")
        except (tk.TclError, AttributeError) as e:
            messagebox.showerror("Error", f"Failed to delete user: {e}")


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
        
    except sqlite3.Error as e:
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
                safe_table = validate_table_name(table, conn=conn)
                cursor.execute('SELECT COUNT(*) FROM [' + safe_table + ']')
                count = cursor.fetchone()[0]
                info += f"{table}: {count} records\n"
            except Exception:
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
        
    except sqlite3.Error as e:
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
        
    except (tk.TclError, AttributeError) as e:
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


