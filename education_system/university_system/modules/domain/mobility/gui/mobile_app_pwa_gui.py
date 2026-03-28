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
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth as get_centralized_auth
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.constants import paths
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

# Language/i18n support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    SUPPORTED_LANGUAGES,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
)

# Email service
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Import email template utilities
try:
    from education_system.university_system.infrastructure.email.template_utils import render_template
    TEMPLATE_AVAILABLE = True
except ImportError:
    TEMPLATE_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MobileAppPWAGUI:
    """Mobile App (PWA) Infrastructure Management GUI"""

    def __init__(self, root: tk.Tk, auth_system: Optional[UserAuth] = None):
        self.root = root

        # Initialize i18n system
        init_i18n()

        self.root.title(_t("mobile_app.title"))
        self.root.geometry("1400x900")

        # Initialize authentication
        if auth_system:
            self.auth = auth_system
        else:
            # Use centralized auth system
            self.auth = get_centralized_auth()
            if self.auth is None:
                self.auth = UserAuth()

        # Initialize database
        self.init_database()

        # Configure styles
        self.setup_styles()

        # Setup current user
        self.setup_current_user()

        # Check authentication status - require login through main system
        from education_system.university_system.infrastructure.shared_context import get_auth
        auth = get_auth()
        if not auth.current_user:
            messagebox.showerror(_t("common.auth_required"),
                _t("mobile_app.login_message"))
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
        """Initialize database tables and migrate missing columns."""
        try:
            from education_system.university_system.infrastructure.database.remaining_features_schema import MOBILE_APP_SCHEMA

            with transaction() as conn:
                conn.executescript(MOBILE_APP_SCHEMA)
                # Migrate older databases that are missing columns added after
                # the initial schema was deployed.
                _migrations = [
                    ("mobile_devices", "is_active", "BOOLEAN DEFAULT 1"),
                    ("mobile_sessions", "ip_address", "TEXT"),
                    ("mobile_sessions", "location", "TEXT"),
                    ("mobile_analytics", "device_id", "INTEGER"),
                    ("mobile_preferences", "theme", "TEXT DEFAULT 'light'"),
                    ("mobile_preferences", "offline_mode_enabled", "BOOLEAN DEFAULT 1"),
                    ("mobile_preferences", "data_saver_mode", "BOOLEAN DEFAULT 0"),
                    ("mobile_preferences", "auto_sync", "BOOLEAN DEFAULT 1"),
                    ("app_installations", "installed_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                    ("app_installations", "uninstalled_at", "TIMESTAMP"),
                ]
                for table, col, col_type in _migrations:
                    try:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                    except Exception:
                        pass  # Column already exists

            logger.info("Mobile App database tables initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            messagebox.showerror(_t("common.database_error"), f"{_t('common.failed_init_db')}: {e}")

    def setup_styles(self):
        """Configure ttk styles to match main_gui.py standards"""
        style = ttk.Style()

        # Use clam theme like main_gui.py
        style.theme_use('clam')

        # Header styling (matching main_gui.py)
        style.configure('Header.TLabel',
                       font=('Arial', 18, 'bold'))

        style.configure('Title.TLabel',
                       font=('Arial', 14, 'bold'))

        style.configure('Section.TLabel',
                       font=('Arial', 12, 'bold'))

        style.configure('Info.TLabel',
                       font=('Arial', 11))

        # Button styles matching main_gui.py
        style.configure('TButton',
                       font=('Arial', 10))

        style.configure('Accent.TButton',
                       font=('Arial', 10, 'bold'))

        # Treeview styling
        style.configure('Treeview',
                       font=('Arial', 10),
                       rowheight=25)

        style.configure('Treeview.Heading',
                       font=('Arial', 10, 'bold'))

        # LabelFrame styling
        style.configure('TLabelframe.Label',
                       font=('Arial', 11, 'bold'))

    def create_main_interface(self):
        """Create the main GUI interface"""
        # Clear existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()

        # Update window title
        self.root.title(_t("mobile_app.title"))

        # Main container frame with padding (matching main_gui.py)
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Header frame with LabelFrame style (matching main_gui.py)
        header_frame = ttk.LabelFrame(main_frame, text=_t("mobile_app.title"), padding="10")
        header_frame.pack(fill='x', pady=(0, 10))

        # Control buttons row
        button_frame = ttk.Frame(header_frame)
        button_frame.pack(fill='x', pady=(0, 10))

        # Return to homepage button
        ttk.Button(button_frame, text=f"← {_t('common.return_to_main_menu')}",
                  command=self.return_to_main_menu,
                  style='Accent.TButton').pack(side='left', padx=(0, 10))

        # Refresh all button
        ttk.Button(button_frame, text=_t("common.refresh_all"),
                  command=self.refresh_all_data).pack(side='left', padx=(0, 10))

        # Language selector button
        self.lang_btn = ttk.Button(
            button_frame,
            text=f"🌐 {_t('gui.change_language')} [{get_current_language_name()}]",
            command=self.change_language
        )
        self.lang_btn.pack(side='right', padx=(10, 0))

        # Status row
        status_frame = ttk.Frame(header_frame)
        status_frame.pack(fill='x')

        ttk.Label(status_frame, text=f"{_t('common.status')}:", font=('Arial', 10, 'bold')).pack(side='left')
        ttk.Label(status_frame, text=_t("common.connected"), font=('Arial', 10)).pack(side='left', padx=(10, 20))

        # User info
        if self.auth.current_user:
            ttk.Label(status_frame, text=f"{_t('common.current_user')}:", font=('Arial', 10, 'bold')).pack(side='left')
            user_info = f"{self.auth.current_user.get('username', _t('common.user'))} ({self.auth.current_user.get('role', _t('common.user'))})"
            ttk.Label(status_frame, text=user_info, font=('Arial', 10)).pack(side='left', padx=(10, 0))

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True)

        # Create tabs
        self.create_devices_tab()
        self.create_sessions_tab()
        self.create_sync_queue_tab()
        self.create_installations_tab()
        self.create_analytics_tab()
        self.create_preferences_tab()

        # Refresh data
        self.refresh_all_data()

    def change_language(self):
        """Open language selector and refresh UI if language changes"""
        old_lang = get_current_language()
        show_gui_language_selector(self.root)
        new_lang = get_current_language()
        if old_lang != new_lang:
            # Refresh the entire interface with new language
            self.create_main_interface()

    def create_devices_tab(self):
        """Create mobile devices management tab"""
        devices_frame = ttk.Frame(self.notebook)
        self.notebook.add(devices_frame, text=f"📱 {_t('mobile_app.devices')}")

        # Controls
        controls_frame = ttk.Frame(devices_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text=f"➕ {_t('mobile_app.register_device')}",
                  command=self.register_device).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=f"🔄 {_t('common.refresh')}",
                  command=self.load_devices).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=f"🗑️ {_t('mobile_app.deactivate_selected')}",
                  command=self.deactivate_device).pack(side='left', padx=5)

        # Search
        ttk.Label(controls_frame, text=f"{_t('mobile_app.search_user_id')}:").pack(side='left', padx=5)
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
        self.devices_tree.heading('device_id', text=_t('mobile_app.device_id'))
        self.devices_tree.heading('user_id', text=_t('common.user_id'))
        self.devices_tree.heading('device_type', text=_t('mobile_app.type'))
        self.devices_tree.heading('device_name', text=_t('mobile_app.device_name'))
        self.devices_tree.heading('os_version', text=_t('mobile_app.os_version'))
        self.devices_tree.heading('app_version', text=_t('mobile_app.app_version'))
        self.devices_tree.heading('last_active', text=_t('mobile_app.last_active'))
        self.devices_tree.heading('is_active', text=_t('common.status'))

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
        self.notebook.add(sessions_frame, text=f"🔐 {_t('mobile_app.sessions')}")

        # Controls
        controls_frame = ttk.Frame(sessions_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text=f"🔄 {_t('common.refresh')}",
                  command=self.load_sessions).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=f"🚪 {_t('mobile_app.end_session')}",
                  command=self.end_session).pack(side='left', padx=5)

        # Sessions tree
        tree_frame = ttk.Frame(sessions_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('session_id', 'device_id', 'user_id', 'login_time',
                  'logout_time', 'ip_address', 'location', 'status')
        self.sessions_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        # Configure column headings with translations
        self.sessions_tree.heading('session_id', text=_t('mobile_app.session_id'))
        self.sessions_tree.heading('device_id', text=_t('mobile_app.device_id'))
        self.sessions_tree.heading('user_id', text=_t('common.user_id'))
        self.sessions_tree.heading('login_time', text=_t('mobile_app.login_time'))
        self.sessions_tree.heading('logout_time', text=_t('mobile_app.logout_time'))
        self.sessions_tree.heading('ip_address', text=_t('mobile_app.ip_address'))
        self.sessions_tree.heading('location', text=_t('mobile_app.location'))
        self.sessions_tree.heading('status', text=_t('common.status'))
        for col in columns:
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
        self.notebook.add(sync_frame, text=f"🔄 {_t('mobile_app.sync_queue')}")

        # Controls
        controls_frame = ttk.Frame(sync_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text=f"🔄 {_t('common.refresh')}",
                  command=self.load_sync_queue).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=f"✅ {_t('mobile_app.process_selected')}",
                  command=self.process_sync_item).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=f"❌ {_t('mobile_app.mark_failed')}",
                  command=self.mark_sync_failed).pack(side='left', padx=5)

        # Filter
        ttk.Label(controls_frame, text=f"{_t('common.status')}:").pack(side='left', padx=5)
        self.sync_filter_var = tk.StringVar(value='pending')
        ttk.Combobox(controls_frame, textvariable=self.sync_filter_var,
                    values=['all', 'pending', 'synced', 'failed'],
                    width=10, state='readonly').pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("common.filter"),
                  command=self.load_sync_queue).pack(side='left', padx=5)

        # Sync queue tree
        tree_frame = ttk.Frame(sync_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('queue_id', 'device_id', 'action_type', 'entity_type',
                  'sync_status', 'created_at', 'synced_at')
        self.sync_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        # Configure column headings with translations
        self.sync_tree.heading('queue_id', text=_t('mobile_app.queue_id'))
        self.sync_tree.heading('device_id', text=_t('mobile_app.device_id'))
        self.sync_tree.heading('action_type', text=_t('mobile_app.action_type'))
        self.sync_tree.heading('entity_type', text=_t('mobile_app.entity_type'))
        self.sync_tree.heading('sync_status', text=_t('mobile_app.sync_status'))
        self.sync_tree.heading('created_at', text=_t('common.created_at'))
        self.sync_tree.heading('synced_at', text=_t('mobile_app.synced_at'))
        for col in columns:
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
        self.notebook.add(install_frame, text=f"📦 {_t('mobile_app.installations')}")

        # Controls
        controls_frame = ttk.Frame(install_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text=f"🔄 {_t('common.refresh')}",
                  command=self.load_installations).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=f"📊 {_t('mobile_app.show_stats')}",
                  command=self.show_installation_stats).pack(side='left', padx=5)

        # Installations tree
        tree_frame = ttk.Frame(install_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('install_id', 'user_id', 'device_id', 'installed_at',
                  'uninstalled_at', 'status')
        self.install_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        # Configure column headings with translations
        self.install_tree.heading('install_id', text=_t('mobile_app.install_id'))
        self.install_tree.heading('user_id', text=_t('common.user_id'))
        self.install_tree.heading('device_id', text=_t('mobile_app.device_id'))
        self.install_tree.heading('installed_at', text=_t('mobile_app.installed_at'))
        self.install_tree.heading('uninstalled_at', text=_t('mobile_app.uninstalled_at'))
        self.install_tree.heading('status', text=_t('common.status'))
        for col in columns:
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
        self.notebook.add(analytics_frame, text=f"📊 {_t('mobile_app.analytics')}")

        # Controls
        controls_frame = ttk.Frame(analytics_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text=f"🔄 {_t('common.refresh')}",
                  command=self.load_analytics).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=f"📈 {_t('common.export_report')}",
                  command=self.export_analytics).pack(side='left', padx=5)

        # Date filter
        ttk.Label(controls_frame, text=f"{_t('common.days')}:").pack(side='left', padx=5)
        self.analytics_days_var = tk.StringVar(value='7')
        ttk.Spinbox(controls_frame, from_=1, to=365, textvariable=self.analytics_days_var,
                   width=10).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=_t("common.filter"),
                  command=self.load_analytics).pack(side='left', padx=5)

        # Analytics tree
        tree_frame = ttk.Frame(analytics_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('analytics_id', 'user_id', 'device_id', 'event_type',
                  'timestamp', 'event_data')
        self.analytics_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        # Configure column headings with translations
        self.analytics_tree.heading('analytics_id', text=_t('mobile_app.analytics_id'))
        self.analytics_tree.heading('user_id', text=_t('common.user_id'))
        self.analytics_tree.heading('device_id', text=_t('mobile_app.device_id'))
        self.analytics_tree.heading('event_type', text=_t('mobile_app.event_type'))
        self.analytics_tree.heading('timestamp', text=_t('common.timestamp'))
        self.analytics_tree.heading('event_data', text=_t('mobile_app.event_data'))
        for col in columns:
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
        self.notebook.add(prefs_frame, text=f"⚙️ {_t('mobile_app.preferences')}")

        # Controls
        controls_frame = ttk.Frame(prefs_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text=f"🔄 {_t('common.refresh')}",
                  command=self.load_preferences).pack(side='left', padx=5)
        ttk.Button(controls_frame, text=f"✏️ {_t('common.edit_selected')}",
                  command=self.edit_preference).pack(side='left', padx=5)

        # Preferences tree
        tree_frame = ttk.Frame(prefs_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('pref_id', 'user_id', 'theme', 'notifications_enabled',
                  'offline_mode_enabled', 'data_saver_mode', 'auto_sync')
        self.prefs_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        # Configure column headings with translations
        self.prefs_tree.heading('pref_id', text=_t('mobile_app.pref_id'))
        self.prefs_tree.heading('user_id', text=_t('common.user_id'))
        self.prefs_tree.heading('theme', text=_t('mobile_app.theme'))
        self.prefs_tree.heading('notifications_enabled', text=_t('mobile_app.notifications_enabled'))
        self.prefs_tree.heading('offline_mode_enabled', text=_t('mobile_app.offline_mode_enabled'))
        self.prefs_tree.heading('data_saver_mode', text=_t('mobile_app.data_saver_mode'))
        self.prefs_tree.heading('auto_sync', text=_t('mobile_app.auto_sync'))
        for col in columns:
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
            messagebox.showerror(_t("common.error"), f"{_t('common.failed_refresh')}: {e}")

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
                    status = _t('common.active') if device[7] else _t('common.inactive')
                    self.devices_tree.insert('', 'end', values=(
                        device[0], device[1], device[2], device[3],
                        device[4], device[5], device[6], status
                    ))

            logger.info(f"Loaded {len(devices)} devices")

        except Exception as e:
            logger.error(f"Error loading devices: {e}\n{traceback.format_exc()}")
            messagebox.showerror(_t("common.error"), f"{_t('mobile_app.failed_load_devices')}: {e}")

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
                    status = _t('common.active') if not session[4] else _t('mobile_app.ended')
                    self.sessions_tree.insert('', 'end', values=(
                        session[0], session[1], session[2], session[3],
                        session[4] or _t('common.active'), session[5], session[6], status
                    ))

            logger.info(f"Loaded {len(sessions)} sessions")

        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
            messagebox.showerror(_t("common.error"), f"{_t('mobile_app.failed_load_sessions')}: {e}")

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
            messagebox.showerror(_t("common.error"), f"{_t('mobile_app.failed_load_sync')}: {e}")

    def load_installations(self):
        """Load app installations"""
        try:
            for item in self.install_tree.get_children():
                self.install_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT installation_id, user_id, device_id, installed_at,
                           uninstalled_at
                    FROM app_installations
                    ORDER BY installed_at DESC
                    LIMIT 100
                ''')

                installations = cursor.fetchall()

                for install in installations:
                    status = _t('mobile_app.installed') if not install[4] else _t('mobile_app.uninstalled')
                    self.install_tree.insert('', 'end', values=(
                        install[0], install[1], install[2], install[3],
                        install[4] or _t('common.na'), status
                    ))

            logger.info(f"Loaded {len(installations)} installations")

        except Exception as e:
            logger.error(f"Error loading installations: {e}")
            messagebox.showerror(_t("common.error"), f"{_t('mobile_app.failed_load_installations')}: {e}")

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
            messagebox.showerror(_t("common.error"), f"{_t('mobile_app.failed_load_analytics')}: {e}")

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
            messagebox.showerror(_t("common.error"), f"{_t('mobile_app.failed_load_preferences')}: {e}")

    # Action methods
    def register_device(self):
        """Register a new mobile device"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("mobile_app.register_device"))
            dialog.geometry("400x400")

            # Form fields
            ttk.Label(dialog, text=f"{_t('common.user_id')}:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            user_id_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=user_id_var, width=30).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text=f"{_t('mobile_app.device_type')}:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            device_type_var = tk.StringVar(value='android')
            ttk.Combobox(dialog, textvariable=device_type_var,
                        values=['ios', 'android', 'web'],
                        width=28, state='readonly').grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text=f"{_t('mobile_app.device_name')}:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            device_name_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=device_name_var, width=30).grid(row=2, column=1, padx=10, pady=5)

            ttk.Label(dialog, text=f"{_t('mobile_app.os_version')}:").grid(row=3, column=0, padx=10, pady=5, sticky='w')
            os_version_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=os_version_var, width=30).grid(row=3, column=1, padx=10, pady=5)

            ttk.Label(dialog, text=f"{_t('mobile_app.app_version')}:").grid(row=4, column=0, padx=10, pady=5, sticky='w')
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
                        messagebox.showerror(_t("common.error"), _t("mobile_app.user_id_required"))
                        return

                    if not device_name:
                        messagebox.showerror(_t("common.error"), _t("mobile_app.device_name_required"))
                        return

                    if not os_version:
                        messagebox.showerror(_t("common.error"), _t("mobile_app.os_version_required"))
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
                            # Try to use template first, fall back to i18n-based email
                            try:
                                if TEMPLATE_AVAILABLE:
                                    subject, body = render_template('device_registration_notification', {
                                        'device_type': device_type,
                                        'device_name': device_name,
                                        'os_version': os_version,
                                        'app_version': app_version,
                                        'registration_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    })
                                else:
                                    raise Exception("Template not available")
                            except Exception as template_error:
                                logger.warning(f"Failed to render template: {template_error}. Using i18n-based email.")
                                # Fallback to i18n-based email
                                subject = _t("mobile_app.email_new_device_subject")
                                body = _t("mobile_app.email_new_device_body",
                                         device_type=device_type,
                                         device_name=device_name,
                                         os_version=os_version,
                                         time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

                            send_email(
                                recipient_email=f"user{user_id}@university.edu",
                                subject=subject,
                                body=body
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send notification email: {e}")

                    messagebox.showinfo(_t("common.success"), f"{_t('mobile_app.device_registered')}\n{_t('mobile_app.device_id')}: {device_id}")
                    dialog.destroy()
                    self.load_devices()

                except Exception as e:
                    logger.error(f"Error registering device: {e}\n{traceback.format_exc()}")
                    messagebox.showerror(_t("common.error"), f"{_t('mobile_app.failed_register_device')}: {e}")

            ttk.Button(dialog, text=_t("common.save"), command=save_device).grid(row=5, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error opening register dialog: {e}")
            messagebox.showerror(_t("common.error"), f"{_t('common.failed_open_dialog')}: {e}")

    def deactivate_device(self):
        """Deactivate selected device"""
        try:
            selected = self.devices_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), _t("mobile_app.select_device_deactivate"))
                return

            device_id = self.devices_tree.item(selected[0])['values'][0]

            if messagebox.askyesno(_t("common.confirm"), _t("mobile_app.confirm_deactivate_device")):
                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE mobile_devices
                        SET is_active = 0
                        WHERE device_id = ?
                    ''', (device_id,))

                log_activity('update', 'mobile_device', device_id,
                            details={'action': 'deactivated'})

                messagebox.showinfo(_t("common.success"), _t("mobile_app.device_deactivated"))
                self.load_devices()

        except Exception as e:
            logger.error(f"Error deactivating device: {e}")
            messagebox.showerror(_t("common.error"), f"{_t('mobile_app.failed_deactivate_device')}: {e}")

    def end_session(self):
        """End selected mobile session"""
        try:
            selected = self.sessions_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), _t("mobile_app.select_session_end"))
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

            messagebox.showinfo(_t("common.success"), _t("mobile_app.session_ended"))
            self.load_sessions()

        except Exception as e:
            logger.error(f"Error ending session: {e}")
            messagebox.showerror(_t("common.error"), f"{_t('mobile_app.failed_end_session')}: {e}")

    def process_sync_item(self):
        """Process selected sync queue item"""
        try:
            selected = self.sync_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), _t("mobile_app.select_sync_process"))
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

            messagebox.showinfo(_t("common.success"), _t("mobile_app.sync_processed"))
            self.load_sync_queue()

        except Exception as e:
            logger.error(f"Error processing sync item: {e}")
            messagebox.showerror(_t("common.error"), f"{_t('mobile_app.failed_process_sync')}: {e}")

    def mark_sync_failed(self):
        """Mark selected sync item as failed"""
        try:
            selected = self.sync_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), _t("mobile_app.select_sync_item"))
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

            messagebox.showinfo(_t("common.success"), _t("mobile_app.sync_marked_failed"))
            self.load_sync_queue()

        except Exception as e:
            logger.error(f"Error marking sync as failed: {e}")
            messagebox.showerror(_t("common.error"), f"{_t('mobile_app.failed_mark_sync')}: {e}")

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

            stats_msg = f"{_t('mobile_app.installation_stats')}:\n\n"
            stats_msg += f"{_t('mobile_app.total_installations')}: {total}\n"
            stats_msg += f"{_t('mobile_app.active_installations')}: {active}\n"
            stats_msg += f"{_t('mobile_app.recent_7_days')}: {recent}\n"
            stats_msg += f"{_t('mobile_app.uninstalled')}: {total - active}"

            messagebox.showinfo(_t("mobile_app.installation_stats"), stats_msg)

        except Exception as e:
            logger.error(f"Error showing stats: {e}")
            messagebox.showerror(_t("common.error"), f"{_t('mobile_app.failed_load_stats')}: {e}")

    def export_analytics(self):
        """Export analytics to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[(_t("common.csv_files"), "*.csv"), (_t("common.all_files"), "*.*")]
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
                writer.writerow([_t('mobile_app.analytics_id'), _t('common.user_id'), _t('mobile_app.device_id'),
                               _t('mobile_app.event_type'), _t('common.timestamp'), _t('mobile_app.event_data')])
                writer.writerows(analytics)

            messagebox.showinfo(_t("common.success"), f"{_t('mobile_app.analytics_exported')}: {filename}")
            log_activity('export', 'mobile_analytics', None,
                        details={'filename': filename, 'record_count': len(analytics)})

        except Exception as e:
            logger.error(f"Error exporting analytics: {e}")
            messagebox.showerror(_t("common.error"), f"{_t('mobile_app.failed_export_analytics')}: {e}")

    def edit_preference(self):
        """Edit mobile preferences for selected user"""
        try:
            selected = self.prefs_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), _t("mobile_app.select_preference_edit"))
                return

            values = self.prefs_tree.item(selected[0])['values']
            pref_id, user_id = values[0], values[1]

            dialog = tk.Toplevel(self.root)
            dialog.title(f"{_t('mobile_app.edit_preferences')} - {_t('common.user')} {user_id}")
            dialog.geometry("400x350")

            # Form fields
            ttk.Label(dialog, text=f"{_t('mobile_app.theme')}:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            theme_var = tk.StringVar(value=values[2])
            ttk.Combobox(dialog, textvariable=theme_var,
                        values=['light', 'dark', 'auto'],
                        width=28, state='readonly').grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text=f"{_t('mobile_app.notifications')}:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            notifications_var = tk.BooleanVar(value=bool(values[3]))
            ttk.Checkbutton(dialog, variable=notifications_var).grid(row=1, column=1, padx=10, pady=5, sticky='w')

            ttk.Label(dialog, text=f"{_t('mobile_app.offline_mode')}:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            offline_var = tk.BooleanVar(value=bool(values[4]))
            ttk.Checkbutton(dialog, variable=offline_var).grid(row=2, column=1, padx=10, pady=5, sticky='w')

            ttk.Label(dialog, text=f"{_t('mobile_app.data_saver')}:").grid(row=3, column=0, padx=10, pady=5, sticky='w')
            data_saver_var = tk.BooleanVar(value=bool(values[5]))
            ttk.Checkbutton(dialog, variable=data_saver_var).grid(row=3, column=1, padx=10, pady=5, sticky='w')

            ttk.Label(dialog, text=f"{_t('mobile_app.auto_sync')}:").grid(row=4, column=0, padx=10, pady=5, sticky='w')
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

                    messagebox.showinfo(_t("common.success"), _t("mobile_app.preferences_updated"))
                    dialog.destroy()
                    self.load_preferences()

                except Exception as e:
                    logger.error(f"Error saving preferences: {e}")
                    messagebox.showerror(_t("common.error"), f"{_t('mobile_app.failed_save_preferences')}: {e}")

            ttk.Button(dialog, text=_t("common.save"), command=save_preferences).grid(row=5, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error editing preference: {e}")
            messagebox.showerror(_t("common.error"), f"{_t('mobile_app.failed_edit_preference')}: {e}")

    def return_to_main_menu(self):
        """Return to main menu by closing the mobile app management window"""
        if messagebox.askyesno(_t("common.confirm"), _t("common.return_to_main_menu_confirm")):
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
