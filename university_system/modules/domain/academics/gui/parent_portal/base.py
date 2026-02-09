from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from university_system.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import csv
from typing import Optional, List, Dict, Any
import sys
import os
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import email service for sending actual emails
try:
    from university_system.infrastructure.email.email_service import send_email, send_email_as_user
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available - emails will be stored locally only")

# Import the original parent portal functionality
try:
    from university_system.modules.domain.academics.services.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility


class ParentPortalGUI:
    """Modern GUI for the Guardian Portal system.
    Allows parents/guardians to monitor their university student's academic progress,
    attendance, financial information, and communicate with instructors.
    Maintains full backwards compatibility with the original CLI version."""
    def __init__(self, auth=None):
        # Initialize i18n for language support
        init_i18n()

        self.auth = auth
        self.parent_portal = None
        self.root = None
        self.current_user = None
        self.parent_id = None
        self.children = []
        
        # GUI Components
        self.main_frame = None
        self.sidebar_frame = None
        self.content_frame = None
        self.status_bar = None
        
        # Initialize the portal
        if auth:
            self.parent_portal = ParentPortal(auth)
            # Get current user dynamically from auth - don't store a stale snapshot
            if auth.current_user and auth.current_user.get('role') == 'parent':
                self.parent_id = self.parent_portal.get_parent_id_from_user(auth.current_user['id'])
    def create_main_window(self):
        """Create and configure the main application window"""
        self.root = tk.Tk()
        self.root.title(_t("parent_portal.title"))
        self.root.geometry("1200x700")
        self.root.minsize(900, 600)

        # Configure style - use 'default' theme for lower resource usage
        style = ttk.Style()
        # Use 'default' theme to minimize X pixmap allocation (prevents BadAlloc errors)
        style.theme_use('default')
        
        # Configure fonts only - avoid background colors to reduce X pixmap allocation
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
        style.configure('Heading.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Info.TLabel', font=('Arial', 10))
        
        self.setup_layout()
        self.load_user_data()
        self.show_dashboard()
        
        return self.root
    def setup_layout(self):
        """Setup the main layout with sidebar and content area"""
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Sidebar container with fixed width
        sidebar_container = ttk.Frame(main_container, width=300)
        sidebar_container.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        sidebar_container.pack_propagate(False)

        # Create canvas and scrollbar for sidebar - use default bg to reduce pixmap usage
        self.sidebar_canvas = tk.Canvas(sidebar_container, highlightthickness=0, width=280)
        sidebar_scrollbar = ttk.Scrollbar(sidebar_container, orient="vertical", command=self.sidebar_canvas.yview)
        self.sidebar_frame = ttk.Frame(self.sidebar_canvas)

        # Create window in canvas for sidebar frame
        self.sidebar_window = self.sidebar_canvas.create_window((0, 0), window=self.sidebar_frame, anchor="nw")

        # Configure scrolling
        self.sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)
        self.sidebar_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sidebar_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Update scroll region when sidebar content changes
        self.sidebar_frame.bind(
            "<Configure>",
            lambda e: self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))
        )

        # Keep sidebar width in sync with canvas width
        def _on_sidebar_canvas_configure(event):
            self.sidebar_canvas.itemconfig(self.sidebar_window, width=event.width)
        self.sidebar_canvas.bind("<Configure>", _on_sidebar_canvas_configure)

        # Bind mouse wheel scrolling
        def _on_mousewheel(event):
            self.sidebar_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        def _on_mousewheel_linux(event):
            if event.num == 4:
                self.sidebar_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.sidebar_canvas.yview_scroll(1, "units")

        self.sidebar_canvas.bind("<MouseWheel>", _on_mousewheel)  # Windows
        self.sidebar_canvas.bind("<Button-4>", _on_mousewheel_linux)  # Linux scroll up
        self.sidebar_canvas.bind("<Button-5>", _on_mousewheel_linux)  # Linux scroll down

        # Content area
        content_container = ttk.Frame(main_container)
        content_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.content_frame = ttk.Frame(content_container)
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        # Status bar
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.setup_sidebar()
    def setup_sidebar(self):
        """Setup the navigation sidebar"""
        # Title
        title_label = ttk.Label(self.sidebar_frame, text=_t("parent_portal.sidebar_title"), style='Title.TLabel')
        title_label.pack(pady=20)
        
        # User info - get current user dynamically
        current_user = self.get_current_user()
        if current_user:
            # Get full name
            first_name = current_user.get('first_name', '')
            last_name = current_user.get('last_name', '')
            full_name = f"{first_name} {last_name}".strip() or current_user.get('username', 'User')

            user_info = ttk.Label(
                self.sidebar_frame,
                text=f"Welcome, {full_name}",
                style='Title.TLabel',
                font=('Arial', 11)
            )
            user_info.pack(pady=10)
        
        # Navigation menu
        self.create_nav_menu()
    def create_nav_menu(self):
        """Create the navigation menu with role-based filtering"""
        # Check if user is admin using standard method
        is_admin = self.is_admin()

        # Menu sections
        menus = [
            (_t("parent_portal.nav.dashboard"), self.show_dashboard),
            (_t("parent_portal.nav.quick_actions"), self.show_quick_actions),
        ]

        # Add Admin menu ONLY for admin users (matching CLI behavior)
        if is_admin:
            menus.append((_t("parent_portal.nav.admin_panel"), self.show_admin_menu))

        # Continue with rest of menu
        menus.extend([
            (_t("parent_portal.nav.my_students"), self.show_children),
            (_t("parent_portal.nav.academic_records"), self.show_academic_menu),
            (_t("parent_portal.nav.attendance_conduct"), self.show_attendance_menu),
            (_t("parent_portal.nav.health_safety"), self.show_health_menu),
            (_t("parent_portal.nav.communication"), self.show_communication_menu),
            (_t("parent_portal.nav.financial"), self.show_financial_menu),
            (_t("parent_portal.nav.academic_support"), self.show_academic_support_menu),
            (_t("parent_portal.nav.settings_tools"), self.show_settings_menu),
            (_t("parent_portal.nav.notifications"), self.mark_notifications_read),
            (_t("common.return_to_main_menu"), self.return_to_main_menu),
        ])
        self.nav_buttons = []
        for text, command in menus:
            # Use ttk.Button to reduce X pixmap allocation
            btn = ttk.Button(
                self.sidebar_frame,
                text=text,
                command=command,
                width=30
            )
            btn.pack(fill=tk.X, pady=2, padx=10)
            self.nav_buttons.append(btn)
    def clear_content(self):
        """Clear the content frame"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    def get_current_user(self):
        """Get current user from auth system dynamically"""
        if self.auth:
            return self.auth.current_user
        return None
    def get_user_role(self):
        """Get the current user's role from authentication system"""
        try:
            current_user = self.get_current_user()
            if current_user:
                return current_user.get('role', '').lower()
            return None
        except Exception as e:
            print(f"Error getting user role: {e}")
            return None
    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'
    def is_staff(self):
        """Check if current user is staff"""
        role = self.get_user_role()
        return role == 'staff'
    def is_parent(self):
        """Check if current user is parent"""
        role = self.get_user_role()
        return role == 'parent'
    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'
    def load_user_data(self):
        """Load user data in background"""
        current_user = self.get_current_user()

        # Admin users get access to all students
        if self.is_admin():
            try:
                all_students = self._load_all_students_for_admin()
                self.children = all_students
                self.update_status(f"Admin access: Loaded {len(self.children)} students from database")
            except Exception as e:
                self.update_status(f"Error loading admin data: {str(e)}")
            return

        if current_user and current_user.get('role') == 'parent':
            # Get parent ID dynamically
            if self.parent_portal:
                self.parent_id = self.parent_portal.get_parent_id_from_user(current_user['id'])

        # Load children data
        if self.parent_portal and self.parent_id:
            try:
                self.children = self.parent_portal.view_children()
                self.update_status(f"Loaded data for {len(self.children)} children")
            except Exception as e:
                self.update_status(f"Error loading data: {str(e)}")
    def _load_all_students_for_admin(self):
        """Load all students from database for admin users with format matching children tuple"""
        students = []
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT student_id, first_name, middle_name, last_name, course, 'Admin Access'
                FROM students
                ORDER BY last_name, first_name
                LIMIT 1000
            ''')
            students = cursor.fetchall()
            conn.close()
        except Exception as e:
            print(f"Error loading students for admin: {e}")
        return students
    def update_status(self, message: str):
        """Update status bar with message and current user"""
        current_user = self.get_current_user()
        if current_user:
            username = current_user.get('username', 'Unknown')
            full_message = f"{message} | Logged in as: {username}"
        else:
            full_message = message

        if self.status_bar:
            self.status_bar.config(text=full_message)
    def show_placeholder(self, title):
        """Show a placeholder interface"""
        self.clear_content()
        self.update_status(title)
        
        title_label = ttk.Label(self.content_frame, text=title, style='Title.TLabel', font=('Arial', 20, 'bold'))
        title_label.pack(pady=20)
        
        ttk.Label(self.content_frame, text=f"{title} interface coming soon!").pack(pady=50)
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
                from university_system.modules.shared.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()
