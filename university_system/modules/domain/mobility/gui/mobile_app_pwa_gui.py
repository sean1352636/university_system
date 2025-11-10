"""
Mobile App (PWA) Infrastructure GUI

Comprehensive GUI for managing mobile devices, sessions, offline sync,
app installations, and mobile analytics. Includes authentication,
error handling, and email notifications.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
import logging
import traceback
import secrets
import hashlib

# Core infrastructure
from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.constants import paths
from university_system.modules.shared.utils.activity_logger import log_activity

# Email service
try:
    from university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MobileAppPWAGUI:
    """Mobile App (PWA) Infrastructure Management GUI"""

    def __init__(self, root: tk.Tk, auth_system: Optional[UserAuth] = None):
        self.root = root
        self.root.title("Mobile App (PWA) Infrastructure")
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')

        # Initialize authentication
        if auth_system:
            self.auth = auth_system
        else:
            self.auth = UserAuth()

        # Initialize database
        self.init_database()

        # Configure styles
        self.setup_styles()

        # Setup current user
        self.setup_current_user()

        # Check authentication status - require login through main system
        from university_system.infrastructure.shared_context import get_auth
        auth = get_auth()
        if not auth.current_user:
            messagebox.showerror("Authentication Required",
                "Please log in through the main University System GUI.\n\n"
                "Run: python run.py --gui")
            self.root.destroy()
            return

        # Show main interface
        self.create_main_interface()

    def setup_current_user(self):
        """Setup current user from authentication system"""
        try:
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                logger.info(f"Mobile App GUI: Using authenticated user {self.auth.current_user.get('username', 'Unknown')}")
            else:
                logger.info("Mobile App GUI: No authenticated user - will show login screen")
        except Exception as e:
            logger.error(f"Error setting up current user: {e}")

    def init_database(self):
        """Initialize database tables"""
        try:
            # Import and run schema creation
            from university_system.infrastructure.database.remaining_features_schema import MOBILE_APP_SCHEMA

            with transaction() as conn:
                conn.executescript(MOBILE_APP_SCHEMA)

            logger.info("Mobile App database tables initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            messagebox.showerror("Database Error", f"Failed to initialize database: {e}")

    def setup_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')

        # Configure colors
        style.configure('Header.TLabel',
                       font=('Arial', 16, 'bold'),
                       background='#2c3e50',
                       foreground='white',
                       padding=10)

        style.configure('Title.TLabel',
                       font=('Arial', 12, 'bold'),
                       background='#f0f0f0')

        style.configure('Action.TButton',
                       font=('Arial', 10),
                       padding=5)

        style.configure('Treeview',
                       font=('Arial', 9),
                       rowheight=25)

        style.configure('Treeview.Heading',
                       font=('Arial', 10, 'bold'))

    def create_main_interface(self):
        """Create the main GUI interface"""
        # Clear existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()

        # Header
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill='x', padx=10, pady=(10, 5))

        ttk.Label(header_frame, text="Mobile App (PWA) Infrastructure",
                 style='Header.TLabel').pack(side='left')

        # Return to homepage button
        ttk.Button(header_frame, text="← Return to Main Menu",
                  command=self.return_to_main_menu).pack(side='right', padx=5)

        if self.auth.current_user:
            user_info = f"Logged in as: {self.auth.current_user.get('username', 'User')} ({self.auth.current_user.get('role', 'user')})"
            ttk.Label(header_frame, text=user_info,
                     font=('Arial', 10)).pack(side='right', padx=10)

        # Notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Create tabs
        self.create_devices_tab()
        self.create_sessions_tab()
        self.create_sync_queue_tab()
        self.create_installations_tab()
        self.create_analytics_tab()
        self.create_preferences_tab()

        # Refresh data
        self.refresh_all_data()

    def create_devices_tab(self):
        """Create mobile devices management tab"""
        devices_frame = ttk.Frame(self.notebook)
        self.notebook.add(devices_frame, text="📱 Devices")

        # Controls
        controls_frame = ttk.Frame(devices_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="➕ Register Device",
                  command=self.register_device, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="🔄 Refresh",
                  command=self.load_devices, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="🗑️ Deactivate Selected",
                  command=self.deactivate_device, style='Action.TButton').pack(side='left', padx=5)

        # Search
        ttk.Label(controls_frame, text="Search User ID:").pack(side='left', padx=5)
        self.device_search_var = tk.StringVar()
        search_entry = ttk.Entry(controls_frame, textvariable=self.device_search_var, width=15)
        search_entry.pack(side='left', padx=5)
        search_entry.bind('<Return>', lambda e: self.load_devices())

        # Devices tree
        tree_frame = ttk.Frame(devices_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('device_id', 'user_id', 'device_type', 'device_name',
                  'os_version', 'app_version', 'last_active', 'is_active')
        self.devices_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        # Configure columns
        self.devices_tree.heading('device_id', text='Device ID')
        self.devices_tree.heading('user_id', text='User ID')
        self.devices_tree.heading('device_type', text='Type')
        self.devices_tree.heading('device_name', text='Device Name')
        self.devices_tree.heading('os_version', text='OS Version')
        self.devices_tree.heading('app_version', text='App Version')
        self.devices_tree.heading('last_active', text='Last Active')
        self.devices_tree.heading('is_active', text='Status')

        self.devices_tree.column('device_id', width=80)
        self.devices_tree.column('user_id', width=80)
        self.devices_tree.column('device_type', width=80)
        self.devices_tree.column('device_name', width=150)
        self.devices_tree.column('os_version', width=100)
        self.devices_tree.column('app_version', width=100)
        self.devices_tree.column('last_active', width=150)
        self.devices_tree.column('is_active', width=80)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.devices_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.devices_tree.xview)
        self.devices_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.devices_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_sessions_tab(self):
        """Create mobile sessions tab"""
        sessions_frame = ttk.Frame(self.notebook)
        self.notebook.add(sessions_frame, text="🔐 Sessions")

        # Controls
        controls_frame = ttk.Frame(sessions_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="🔄 Refresh",
                  command=self.load_sessions, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="🚪 End Session",
                  command=self.end_session, style='Action.TButton').pack(side='left', padx=5)

        # Sessions tree
        tree_frame = ttk.Frame(sessions_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('session_id', 'device_id', 'user_id', 'login_time',
                  'logout_time', 'ip_address', 'location', 'status')
        self.sessions_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.sessions_tree.heading(col, text=col.replace('_', ' ').title())
            self.sessions_tree.column(col, width=120)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.sessions_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.sessions_tree.xview)
        self.sessions_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.sessions_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_sync_queue_tab(self):
        """Create offline sync queue tab"""
        sync_frame = ttk.Frame(self.notebook)
        self.notebook.add(sync_frame, text="🔄 Sync Queue")

        # Controls
        controls_frame = ttk.Frame(sync_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="🔄 Refresh",
                  command=self.load_sync_queue, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="✅ Process Selected",
                  command=self.process_sync_item, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="❌ Mark Failed",
                  command=self.mark_sync_failed, style='Action.TButton').pack(side='left', padx=5)

        # Filter
        ttk.Label(controls_frame, text="Status:").pack(side='left', padx=5)
        self.sync_filter_var = tk.StringVar(value='pending')
        ttk.Combobox(controls_frame, textvariable=self.sync_filter_var,
                    values=['all', 'pending', 'synced', 'failed'],
                    width=10, state='readonly').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Filter",
                  command=self.load_sync_queue, style='Action.TButton').pack(side='left', padx=5)

        # Sync queue tree
        tree_frame = ttk.Frame(sync_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('queue_id', 'device_id', 'action_type', 'entity_type',
                  'sync_status', 'created_at', 'synced_at')
        self.sync_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.sync_tree.heading(col, text=col.replace('_', ' ').title())
            self.sync_tree.column(col, width=120)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.sync_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.sync_tree.xview)
        self.sync_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.sync_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_installations_tab(self):
        """Create app installations tab"""
        install_frame = ttk.Frame(self.notebook)
        self.notebook.add(install_frame, text="📦 Installations")

        # Controls
        controls_frame = ttk.Frame(install_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="🔄 Refresh",
                  command=self.load_installations, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="📊 Show Stats",
                  command=self.show_installation_stats, style='Action.TButton').pack(side='left', padx=5)

        # Installations tree
        tree_frame = ttk.Frame(install_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('install_id', 'user_id', 'device_id', 'installed_at',
                  'uninstalled_at', 'status')
        self.install_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.install_tree.heading(col, text=col.replace('_', ' ').title())
            self.install_tree.column(col, width=150)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.install_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.install_tree.xview)
        self.install_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.install_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_analytics_tab(self):
        """Create mobile analytics tab"""
        analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(analytics_frame, text="📊 Analytics")

        # Controls
        controls_frame = ttk.Frame(analytics_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="🔄 Refresh",
                  command=self.load_analytics, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="📈 Export Report",
                  command=self.export_analytics, style='Action.TButton').pack(side='left', padx=5)

        # Date filter
        ttk.Label(controls_frame, text="Days:").pack(side='left', padx=5)
        self.analytics_days_var = tk.StringVar(value='7')
        ttk.Spinbox(controls_frame, from_=1, to=365, textvariable=self.analytics_days_var,
                   width=10).pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Filter",
                  command=self.load_analytics, style='Action.TButton').pack(side='left', padx=5)

        # Analytics tree
        tree_frame = ttk.Frame(analytics_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('analytics_id', 'user_id', 'device_id', 'event_type',
                  'timestamp', 'event_data')
        self.analytics_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.analytics_tree.heading(col, text=col.replace('_', ' ').title())
            self.analytics_tree.column(col, width=120)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.analytics_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.analytics_tree.xview)
        self.analytics_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.analytics_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_preferences_tab(self):
        """Create mobile preferences tab"""
        prefs_frame = ttk.Frame(self.notebook)
        self.notebook.add(prefs_frame, text="⚙️ Preferences")

        # Controls
        controls_frame = ttk.Frame(prefs_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="🔄 Refresh",
                  command=self.load_preferences, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="✏️ Edit Selected",
                  command=self.edit_preference, style='Action.TButton').pack(side='left', padx=5)

        # Preferences tree
        tree_frame = ttk.Frame(prefs_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('pref_id', 'user_id', 'theme', 'notifications_enabled',
                  'offline_mode_enabled', 'data_saver_mode', 'auto_sync')
        self.prefs_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.prefs_tree.heading(col, text=col.replace('_', ' ').title())
            self.prefs_tree.column(col, width=120)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.prefs_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.prefs_tree.xview)
        self.prefs_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.prefs_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    # Data loading methods
    def refresh_all_data(self):
        """Refresh all tab data"""
        try:
            self.load_devices()
            self.load_sessions()
            self.load_sync_queue()
            self.load_installations()
            self.load_analytics()
            self.load_preferences()
        except Exception as e:
            logger.error(f"Error refreshing data: {e}")
            messagebox.showerror("Error", f"Failed to refresh data: {e}")

    def load_devices(self):
        """Load mobile devices"""
        try:
            # Clear existing items
            for item in self.devices_tree.get_children():
                self.devices_tree.delete(item)

            # Query devices
            with get_connection() as conn:
                cursor = conn.cursor()

                search_user = self.device_search_var.get().strip()
                if search_user:
                    cursor.execute('''
                        SELECT device_id, user_id, device_type, device_name,
                               os_version, app_version, last_active, is_active
                        FROM mobile_devices
                        WHERE user_id = ?
                        ORDER BY last_active DESC
                    ''', (search_user,))
                else:
                    cursor.execute('''
                        SELECT device_id, user_id, device_type, device_name,
                               os_version, app_version, last_active, is_active
                        FROM mobile_devices
                        ORDER BY last_active DESC
                        LIMIT 100
                    ''')

                devices = cursor.fetchall()

                for device in devices:
                    status = 'Active' if device[7] else 'Inactive'
                    self.devices_tree.insert('', 'end', values=(
                        device[0], device[1], device[2], device[3],
                        device[4], device[5], device[6], status
                    ))

            logger.info(f"Loaded {len(devices)} devices")

        except Exception as e:
            logger.error(f"Error loading devices: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"Failed to load devices: {e}")

    def load_sessions(self):
        """Load mobile sessions"""
        try:
            for item in self.sessions_tree.get_children():
                self.sessions_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT session_id, device_id, user_id, login_time,
                           logout_time, ip_address, location
                    FROM mobile_sessions
                    ORDER BY login_time DESC
                    LIMIT 100
                ''')

                sessions = cursor.fetchall()

                for session in sessions:
                    status = 'Active' if not session[4] else 'Ended'
                    self.sessions_tree.insert('', 'end', values=(
                        session[0], session[1], session[2], session[3],
                        session[4] or 'Active', session[5], session[6], status
                    ))

            logger.info(f"Loaded {len(sessions)} sessions")

        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
            messagebox.showerror("Error", f"Failed to load sessions: {e}")

    def load_sync_queue(self):
        """Load offline sync queue"""
        try:
            for item in self.sync_tree.get_children():
                self.sync_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()

                status_filter = self.sync_filter_var.get()
                if status_filter == 'all':
                    cursor.execute('''
                        SELECT queue_id, device_id, action_type, entity_type,
                               sync_status, created_at, synced_at
                        FROM offline_sync_queue
                        ORDER BY created_at DESC
                        LIMIT 100
                    ''')
                else:
                    cursor.execute('''
                        SELECT queue_id, device_id, action_type, entity_type,
                               sync_status, created_at, synced_at
                        FROM offline_sync_queue
                        WHERE sync_status = ?
                        ORDER BY created_at DESC
                        LIMIT 100
                    ''', (status_filter,))

                items = cursor.fetchall()

                for item in items:
                    self.sync_tree.insert('', 'end', values=item)

            logger.info(f"Loaded {len(items)} sync queue items")

        except Exception as e:
            logger.error(f"Error loading sync queue: {e}")
            messagebox.showerror("Error", f"Failed to load sync queue: {e}")

    def load_installations(self):
        """Load app installations"""
        try:
            for item in self.install_tree.get_children():
                self.install_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT install_id, user_id, device_id, installed_at,
                           uninstalled_at
                    FROM app_installations
                    ORDER BY installed_at DESC
                    LIMIT 100
                ''')

                installations = cursor.fetchall()

                for install in installations:
                    status = 'Installed' if not install[4] else 'Uninstalled'
                    self.install_tree.insert('', 'end', values=(
                        install[0], install[1], install[2], install[3],
                        install[4] or 'N/A', status
                    ))

            logger.info(f"Loaded {len(installations)} installations")

        except Exception as e:
            logger.error(f"Error loading installations: {e}")
            messagebox.showerror("Error", f"Failed to load installations: {e}")

    def load_analytics(self):
        """Load mobile analytics"""
        try:
            for item in self.analytics_tree.get_children():
                self.analytics_tree.delete(item)

            days = int(self.analytics_days_var.get())
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT analytics_id, user_id, device_id, event_type,
                           timestamp, event_data
                    FROM mobile_analytics
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                    LIMIT 100
                ''', (cutoff_date,))

                analytics = cursor.fetchall()

                for item in analytics:
                    self.analytics_tree.insert('', 'end', values=item)

            logger.info(f"Loaded {len(analytics)} analytics events")

        except Exception as e:
            logger.error(f"Error loading analytics: {e}")
            messagebox.showerror("Error", f"Failed to load analytics: {e}")

    def load_preferences(self):
        """Load mobile preferences"""
        try:
            for item in self.prefs_tree.get_children():
                self.prefs_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT pref_id, user_id, theme, notifications_enabled,
                           offline_mode_enabled, data_saver_mode, auto_sync
                    FROM mobile_preferences
                    LIMIT 100
                ''')

                prefs = cursor.fetchall()

                for pref in prefs:
                    self.prefs_tree.insert('', 'end', values=pref)

            logger.info(f"Loaded {len(prefs)} preferences")

        except Exception as e:
            logger.error(f"Error loading preferences: {e}")
            messagebox.showerror("Error", f"Failed to load preferences: {e}")

    # Action methods
    def register_device(self):
        """Register a new mobile device"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Register Device")
            dialog.geometry("400x400")

            # Form fields
            ttk.Label(dialog, text="User ID:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            user_id_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=user_id_var, width=30).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Device Type:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            device_type_var = tk.StringVar(value='android')
            ttk.Combobox(dialog, textvariable=device_type_var,
                        values=['ios', 'android', 'web'],
                        width=28, state='readonly').grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Device Name:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            device_name_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=device_name_var, width=30).grid(row=2, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="OS Version:").grid(row=3, column=0, padx=10, pady=5, sticky='w')
            os_version_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=os_version_var, width=30).grid(row=3, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="App Version:").grid(row=4, column=0, padx=10, pady=5, sticky='w')
            app_version_var = tk.StringVar(value='1.0.0')
            ttk.Entry(dialog, textvariable=app_version_var, width=30).grid(row=4, column=1, padx=10, pady=5)

            def save_device():
                try:
                    user_id = user_id_var.get().strip()
                    device_type = device_type_var.get()
                    device_name = device_name_var.get().strip()
                    os_version = os_version_var.get().strip()
                    app_version = app_version_var.get().strip()

                    if not user_id:
                        messagebox.showerror("Error", "User ID is required")
                        return

                    # Generate push token
                    push_token = hashlib.sha256(secrets.token_bytes(32)).hexdigest()

                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO mobile_devices
                            (user_id, device_type, device_name, push_token,
                             os_version, app_version)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (user_id, device_type, device_name, push_token,
                              os_version, app_version))

                        device_id = cursor.lastrowid

                    # Log activity
                    log_activity('create', 'mobile_device', device_id,
                                details={'user_id': user_id, 'device_type': device_type})

                    # Send notification email
                    if EMAIL_AVAILABLE:
                        try:
                            send_email(
                                recipient_email=f"user{user_id}@university.edu",
                                subject="New Device Registered",
                                body=f"A new {device_type} device has been registered to your account.\n\n"
                                     f"Device: {device_name}\n"
                                     f"OS: {os_version}\n"
                                     f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                     f"If this wasn't you, please contact IT support immediately."
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send notification email: {e}")

                    messagebox.showinfo("Success", f"Device registered successfully!\nDevice ID: {device_id}")
                    dialog.destroy()
                    self.load_devices()

                except Exception as e:
                    logger.error(f"Error registering device: {e}\n{traceback.format_exc()}")
                    messagebox.showerror("Error", f"Failed to register device: {e}")

            ttk.Button(dialog, text="Save", command=save_device).grid(row=5, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error opening register dialog: {e}")
            messagebox.showerror("Error", f"Failed to open dialog: {e}")

    def deactivate_device(self):
        """Deactivate selected device"""
        try:
            selected = self.devices_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a device to deactivate")
                return

            device_id = self.devices_tree.item(selected[0])['values'][0]

            if messagebox.askyesno("Confirm", "Are you sure you want to deactivate this device?"):
                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE mobile_devices
                        SET is_active = 0
                        WHERE device_id = ?
                    ''', (device_id,))

                log_activity('update', 'mobile_device', device_id,
                            details={'action': 'deactivated'})

                messagebox.showinfo("Success", "Device deactivated successfully")
                self.load_devices()

        except Exception as e:
            logger.error(f"Error deactivating device: {e}")
            messagebox.showerror("Error", f"Failed to deactivate device: {e}")

    def end_session(self):
        """End selected mobile session"""
        try:
            selected = self.sessions_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a session to end")
                return

            session_id = self.sessions_tree.item(selected[0])['values'][0]

            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE mobile_sessions
                    SET logout_time = ?
                    WHERE session_id = ? AND logout_time IS NULL
                ''', (datetime.now().isoformat(), session_id))

            log_activity('update', 'mobile_session', session_id,
                        details={'action': 'ended'})

            messagebox.showinfo("Success", "Session ended successfully")
            self.load_sessions()

        except Exception as e:
            logger.error(f"Error ending session: {e}")
            messagebox.showerror("Error", f"Failed to end session: {e}")

    def process_sync_item(self):
        """Process selected sync queue item"""
        try:
            selected = self.sync_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a sync item to process")
                return

            queue_id = self.sync_tree.item(selected[0])['values'][0]

            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE offline_sync_queue
                    SET sync_status = 'synced', synced_at = ?
                    WHERE queue_id = ?
                ''', (datetime.now().isoformat(), queue_id))

            log_activity('update', 'sync_queue', queue_id,
                        details={'action': 'processed'})

            messagebox.showinfo("Success", "Sync item processed successfully")
            self.load_sync_queue()

        except Exception as e:
            logger.error(f"Error processing sync item: {e}")
            messagebox.showerror("Error", f"Failed to process sync item: {e}")

    def mark_sync_failed(self):
        """Mark selected sync item as failed"""
        try:
            selected = self.sync_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a sync item")
                return

            queue_id = self.sync_tree.item(selected[0])['values'][0]

            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE offline_sync_queue
                    SET sync_status = 'failed'
                    WHERE queue_id = ?
                ''', (queue_id,))

            log_activity('update', 'sync_queue', queue_id,
                        details={'action': 'marked_failed'})

            messagebox.showinfo("Success", "Sync item marked as failed")
            self.load_sync_queue()

        except Exception as e:
            logger.error(f"Error marking sync as failed: {e}")
            messagebox.showerror("Error", f"Failed to mark sync as failed: {e}")

    def show_installation_stats(self):
        """Show installation statistics"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Total installations
                cursor.execute('SELECT COUNT(*) FROM app_installations')
                total = cursor.fetchone()[0]

                # Active installations
                cursor.execute('SELECT COUNT(*) FROM app_installations WHERE uninstalled_at IS NULL')
                active = cursor.fetchone()[0]

                # Recent installations (last 7 days)
                week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                cursor.execute('SELECT COUNT(*) FROM app_installations WHERE installed_at >= ?', (week_ago,))
                recent = cursor.fetchone()[0]

            stats_msg = f"Installation Statistics:\n\n"
            stats_msg += f"Total Installations: {total}\n"
            stats_msg += f"Active Installations: {active}\n"
            stats_msg += f"Recent (7 days): {recent}\n"
            stats_msg += f"Uninstalled: {total - active}"

            messagebox.showinfo("Installation Statistics", stats_msg)

        except Exception as e:
            logger.error(f"Error showing stats: {e}")
            messagebox.showerror("Error", f"Failed to load statistics: {e}")

    def export_analytics(self):
        """Export analytics to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not filename:
                return

            days = int(self.analytics_days_var.get())
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT analytics_id, user_id, device_id, event_type,
                           timestamp, event_data
                    FROM mobile_analytics
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                ''', (cutoff_date,))

                analytics = cursor.fetchall()

            import csv
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Analytics ID', 'User ID', 'Device ID', 'Event Type',
                               'Timestamp', 'Event Data'])
                writer.writerows(analytics)

            messagebox.showinfo("Success", f"Analytics exported to {filename}")
            log_activity('export', 'mobile_analytics', None,
                        details={'filename': filename, 'record_count': len(analytics)})

        except Exception as e:
            logger.error(f"Error exporting analytics: {e}")
            messagebox.showerror("Error", f"Failed to export analytics: {e}")

    def edit_preference(self):
        """Edit mobile preferences for selected user"""
        try:
            selected = self.prefs_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a preference to edit")
                return

            values = self.prefs_tree.item(selected[0])['values']
            pref_id, user_id = values[0], values[1]

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Edit Preferences - User {user_id}")
            dialog.geometry("400x350")

            # Form fields
            ttk.Label(dialog, text="Theme:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            theme_var = tk.StringVar(value=values[2])
            ttk.Combobox(dialog, textvariable=theme_var,
                        values=['light', 'dark', 'auto'],
                        width=28, state='readonly').grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Notifications:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            notifications_var = tk.BooleanVar(value=bool(values[3]))
            ttk.Checkbutton(dialog, variable=notifications_var).grid(row=1, column=1, padx=10, pady=5, sticky='w')

            ttk.Label(dialog, text="Offline Mode:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            offline_var = tk.BooleanVar(value=bool(values[4]))
            ttk.Checkbutton(dialog, variable=offline_var).grid(row=2, column=1, padx=10, pady=5, sticky='w')

            ttk.Label(dialog, text="Data Saver:").grid(row=3, column=0, padx=10, pady=5, sticky='w')
            data_saver_var = tk.BooleanVar(value=bool(values[5]))
            ttk.Checkbutton(dialog, variable=data_saver_var).grid(row=3, column=1, padx=10, pady=5, sticky='w')

            ttk.Label(dialog, text="Auto Sync:").grid(row=4, column=0, padx=10, pady=5, sticky='w')
            auto_sync_var = tk.BooleanVar(value=bool(values[6]))
            ttk.Checkbutton(dialog, variable=auto_sync_var).grid(row=4, column=1, padx=10, pady=5, sticky='w')

            def save_preferences():
                try:
                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE mobile_preferences
                            SET theme = ?, notifications_enabled = ?,
                                offline_mode_enabled = ?, data_saver_mode = ?,
                                auto_sync = ?
                            WHERE pref_id = ?
                        ''', (theme_var.get(), int(notifications_var.get()),
                              int(offline_var.get()), int(data_saver_var.get()),
                              int(auto_sync_var.get()), pref_id))

                    log_activity('update', 'mobile_preferences', pref_id,
                                details={'user_id': user_id})

                    messagebox.showinfo("Success", "Preferences updated successfully")
                    dialog.destroy()
                    self.load_preferences()

                except Exception as e:
                    logger.error(f"Error saving preferences: {e}")
                    messagebox.showerror("Error", f"Failed to save preferences: {e}")

            ttk.Button(dialog, text="Save", command=save_preferences).grid(row=5, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error editing preference: {e}")
            messagebox.showerror("Error", f"Failed to edit preference: {e}")

    def return_to_main_menu(self):
        """Return to main menu by closing the mobile app management window"""
        if messagebox.askyesno("Confirm", "Return to main menu?"):
            try:
                # Log the action
                if self.auth and self.auth.current_user:
                    log_activity('Closed Mobile App Management',
                               user=self.auth.current_user.get('username', 'Unknown'))

                # Close the window
                self.root.destroy()
                logger.info("Mobile App GUI closed")
            except Exception as e:
                logger.error(f"Error closing Mobile App GUI: {e}")
                self.root.destroy()


def launch_mobile_app_pwa_gui(auth=None):
    """Launch the Mobile App (PWA) Infrastructure GUI"""
    try:
        root = tk.Tk()
        app = MobileAppPWAGUI(root, auth_system=auth)
        root.mainloop()
    except Exception as e:
        logger.error(f"Error launching Mobile App GUI: {e}\n{traceback.format_exc()}")
        raise


if __name__ == "__main__":
    launch_mobile_app_pwa_gui()
