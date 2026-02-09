from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import json
from datetime import datetime, timedelta
import os
import logging
from pathlib import Path
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.constants.paths import PROJECT_ROOT, LOG_DIR

# Initialize logger
logger = logging.getLogger(__name__)

# Import i18n for internationalization
try:
    from university_system.modules.shared.utils.i18n import (
        get_text as _t,
        init_i18n,
        get_current_language,
        get_current_language_name
    )
    from university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    def _t(key, **kwargs):
        """Fallback translation function"""
        # Extract last part of key and convert to readable text
        text = key.split('.')[-1].replace('_', ' ').title()
        # Handle variable substitution
        for k, v in kwargs.items():
            text = text.replace('{' + k + '}', str(v))
        return text

    def init_i18n(lang=None):
        """Fallback init function"""
        pass

    def get_current_language():
        """Fallback language getter"""
        return 'en'

    def get_current_language_name():
        """Fallback language name getter"""
        return 'English'

    def show_gui_language_selector(parent):
        """Fallback language selector"""
        messagebox.showinfo("Info", "Language selection not available")
# Availability flags
STUDENT_SYSTEM_AVAILABLE = False  # define up front

# Fallback implementations
class FallbackConfig:
    """Fallback config manager"""
    def __init__(self):
        self.config = {
            'api_enabled': False,
            'retention_days': 90,
            'auto_archive_days': 30,
            'max_log_size_mb': 100,
            'enable_real_time': False,
            'enable_alerts': True,
            'enable_analytics': True,
            'enable_encryption': False,
            'smtp_username': '',
            'smtp_password': '',
            'smtp_server': '',
            'smtp_port': 587,
            'webhook_secret': '',
            'alert_email': '',
            'api_secret_key': '',
            'weekly_report_email': '',
            'weekly_report_day': 1,
            'weekly_report_time': '09:00',
            'daily_report_time': '08:00',
            'security_alert_email': '',
            'failed_login_threshold': 5,
            'rapid_actions_threshold': 20,
            'alert_failed_logins': True,
            'alert_unusual_hours': True,
            'alert_rapid_actions': True,
            'alert_admin_actions': True,
            'weekly_include_summary': True,
            'weekly_include_charts': True,
            'weekly_include_alerts': True
        }
        # For compatibility with code that accesses .default_config
        self.default_config = self.config.copy()

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value

    def save_config(self):
        """Save fallback configuration - stores config in memory only"""
        logger.debug("FallbackConfig: save_config called (no-op, config stored in memory only)")

class FallbackAnalytics:
    """
    Fallback analytics manager

    Provides mock analytics functionality when the full analytics
    module is unavailable. Returns empty/default data to prevent
    application failures while maintaining API compatibility.
    """
    def __init__(self):
        """Initialize fallback analytics with empty state"""
        self.activities = []
        self.users = set()

    def generate_activity_summary(self, days=7):
        """Generate a mock activity summary"""
        return {
            'total_activities': 0,
            'unique_users': 0,
            'success_rate': 100.0,
            'failed_activities': 0,
            'peak_activity_hour': 9
        }

    def generate_user_activity_report(self, user_id, days=30):
        """Generate a mock user activity report"""
        return f"Mock activity report for user {user_id} over {days} days"

    def create_activity_chart(self, chart_type, days, save_path):
        """Create a mock activity chart"""
        return save_path

class FallbackAlerts:
    """
    Fallback alerts manager

    Provides mock alert functionality when the full alerts module
    is unavailable. Returns empty alerts to maintain compatibility
    while preventing application crashes.
    """
    def __init__(self):
        """Initialize fallback alerts with empty state"""
        self.alerts = []
        self.alert_rules = []

    def run_alert_checks(self):
        """Run mock alert checks"""
        return []

class FallbackDatabase:
    """Fallback database manager"""
    def __init__(self, db_path):
        self.db_path = db_path

    def search_logs(self, filters=None, limit=100):
        """Search logs with filters"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = "SELECT * FROM activity_log"
            params = []

            if filters:
                conditions = []
                if filters.get('user_id'):
                    conditions.append("user_id = ?")
                    params.append(filters['user_id'])
                if filters.get('action'):
                    conditions.append("action = ?")
                    params.append(filters['action'])
                if filters.get('date_from'):
                    conditions.append("timestamp >= ?")
                    params.append(filters['date_from'])
                if filters.get('date_to'):
                    conditions.append("timestamp <= ?")
                    params.append(filters['date_to'])
                if filters.get('status'):
                    conditions.append("status = ?")
                    params.append(filters['status'])

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

            query += f" ORDER BY timestamp DESC LIMIT {limit}"

            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()

            return results
        except Exception as e:
            print(f"Database search error: {e}")
            return []

    def insert_log(self, log_data):
        """Insert a log entry"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO activity_log (timestamp, user_id, username, action, details, status, module, message, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_data.get('timestamp'),
                log_data.get('user_id'),
                log_data.get('username', ''),
                log_data.get('action'),
                log_data.get('details', ''),
                log_data.get('status', ''),
                log_data.get('module', ''),
                log_data.get('message', ''),
                log_data.get('ip_address', '127.0.0.1'),
                log_data.get('user_agent', '')
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Database insert error: {e}")

# Fallback Log Manager implementation
class FallbackLogManager:
    """Fallback log manager when the main one is not available"""

    def __init__(self):
        self.db_path = str(DEFAULT_DB_PATH)
        self.available = True
        self.config = FallbackConfig()
        self.db = FallbackDatabase(self.db_path)
        self.analytics = FallbackAnalytics()
        self.alerts = FallbackAlerts()

    def get_logs(self, limit=100, offset=0, filters=None):
        """Get logs from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = "SELECT * FROM activity_log"
            params = []

            if filters:
                conditions = []
                if filters.get('user_id'):
                    conditions.append("user_id = ?")
                    params.append(filters['user_id'])
                if filters.get('action'):
                    conditions.append("action = ?")
                    params.append(filters['action'])
                if filters.get('date_from'):
                    conditions.append("timestamp >= ?")
                    params.append(filters['date_from'])
                if filters.get('date_to'):
                    conditions.append("timestamp <= ?")
                    params.append(filters['date_to'])

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

            query += f" ORDER BY timestamp DESC LIMIT {limit} OFFSET {offset}"

            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()

            return results
        except Exception as e:
            print(f"Error getting logs: {e}")
            return []

    def get_alerts(self, limit=50):
        """Get alerts from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM alerts
                ORDER BY triggered_at DESC
                LIMIT ?
            """, (limit,))
            results = cursor.fetchall()
            conn.close()
            return results
        except Exception as e:
            print(f"Error getting alerts: {e}")
            return []

    def add_log(self, user_id, action, status, module, message, **kwargs):
        """Add a log entry"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO activity_log (user_id, username, action, status, module, message, ip_address, user_agent, timestamp, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                kwargs.get('username', user_id),
                action,
                status,
                module,
                message,
                kwargs.get('ip_address', '127.0.0.1'),
                kwargs.get('user_agent', ''),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                kwargs.get('details', '')
            ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error adding log: {e}")
            return False

# Import all original functionality
try:
    from university_system.utils.logging.log_management import get_log_manager
    STUDENT_SYSTEM_AVAILABLE = True  # set True on successful import
except ImportError:
    print("Warning: Original log_management module not found. Using fallback implementation.")
    STUDENT_SYSTEM_AVAILABLE = False  # keep False on failure

    def get_log_manager():
        """Fallback get_log_manager function"""
        return FallbackLogManager()

def get_student_db_connection():
    """Direct database connection without importing main.py"""
    if not STUDENT_SYSTEM_AVAILABLE:
        return None
    from university_system.infrastructure.database.db import sqlite3
    import os
    from university_system.infrastructure.database.db import DEFAULT_DB_PATH as DB_PATH

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def initialize_database():
    """Initialize database with required tables for log management"""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Create logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT,
                username TEXT,
                action TEXT,
                status TEXT,
                module TEXT,
                message TEXT,
                ip_address TEXT,
                user_agent TEXT
            )
        ''')

        # Create alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT,
                message TEXT,
                severity TEXT DEFAULT 'medium',
                triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                acknowledged BOOLEAN DEFAULT FALSE,
                resolved BOOLEAN DEFAULT FALSE,
                resolved_at DATETIME,
                user_id TEXT,
                metadata TEXT
            )
        ''')

        # Create saved_searches table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                user_id TEXT NOT NULL,
                search_params TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create students table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                email_address TEXT,
                first_name TEXT,
                last_name TEXT,
                course TEXT,
                enrollment_date DATE,
                status TEXT DEFAULT 'active'
            )
        ''')

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False
    
class LogManagementGUI:
    """Main GUI application for log management"""

    def __init__(self, root, auth=None, embedded: bool = False):
        self.root = root
        self.auth = auth
        self.log_manager = None
        self.embedded = embedded

        # Initialize database tables
        initialize_database()

        try:
            self.log_manager = get_log_manager()
            if not hasattr(self.log_manager, 'available'):
                self.log_manager.available = True
        except Exception as e:
            print(f"Error initializing log manager: {e}")
            self.log_manager = FallbackLogManager()

        self.setup_gui()
        
    def setup_gui(self):
        """Setup the main GUI"""
        if not self.embedded:
            self.root.title(_t("log_management.window_title"))
            self.root.geometry("1300x850")
            self.root.minsize(1100, 720)
            ttk.Button(
                self.root,
                text="🏠 " + _t("log_management.return_to_main"),
                command=self.return_to_main_menu
            ).place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        style = ttk.Style()
        style.theme_use('clam')

        if not self.embedded:
            self.setup_menu()

        # Main frame + notebook live fine in both modes
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.setup_dashboard_tab()
        self.setup_search_tab()
        self.setup_analytics_tab()
        self.setup_alerts_tab()
        self.setup_config_tab()
        self.setup_maintenance_tab()

        self.setup_status_bar()

        if not self.embedded:
            self.update_dashboard()

    def start_api_server(self):
        """Start the Flask API server - not available"""
        messagebox.showinfo(_t("log_management.api_server.title"), _t("log_management.api_server.removed"))

    def stop_api_server(self):
        """Stop the Flask API server - not available"""
        messagebox.showinfo(_t("log_management.api_server.title"), _t("log_management.api_server.removed"))
            
    def setup_menu(self):
        """Setup the main menu"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("log_management.menu.file"), menu=file_menu)
        file_menu.add_command(label=_t("log_management.menu.export_logs"), command=self.export_logs_dialog)
        file_menu.add_command(label=_t("log_management.menu.import_logs"), command=self.import_logs_dialog)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("log_management.menu.view"), menu=view_menu)
        view_menu.add_command(label=_t("log_management.menu.refresh_dashboard"), command=self.update_dashboard)
        view_menu.add_command(label=_t("log_management.menu.realtime_monitor"), command=self.open_realtime_monitor)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("log_management.menu.tools"), menu=tools_menu)
        tools_menu.add_command(label=_t("log_management.menu.generate_chart"), command=self.generate_chart_dialog)
        tools_menu.add_command(label=_t("log_management.menu.integrity_check"), command=self.run_integrity_check)
        tools_menu.add_command(label=_t("log_management.menu.db_optimization"), command=self.optimize_database)
        tools_menu.add_separator()
        tools_menu.add_command(label=_t("log_management.menu.send_email_report"), command=self.email_report_dialog)
        tools_menu.add_command(label=_t("log_management.menu.test_email"), command=self.send_test_email)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("log_management.menu.help"), menu=help_menu)
        help_menu.add_command(label=_t("log_management.menu.api_docs"), command=self.show_api_docs)
        help_menu.add_command(label=_t("log_management.menu.about"), command=self.show_about)
        self.setup_integration_menu()

    def create_student_integration_tab(self):
        """Create tab for student system integration"""
        if not STUDENT_SYSTEM_AVAILABLE:
            return

        self.student_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.student_frame, text=_t("log_management.tabs.student_system"))

        # Integration controls
        controls_frame = ttk.LabelFrame(self.student_frame, text=_t("log_management.student_system.integration"))
        controls_frame.pack(fill=tk.X, padx=10, pady=5)

        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(padx=10, pady=10)

        ttk.Button(button_frame, text=_t("log_management.student_system.view_logs"),
                   command=self.view_student_logs).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text=_t("log_management.student_system.sync_data"),
                   command=self.sync_student_data).pack(side=tk.LEFT)

        # Quick stats frame
        stats_frame = ttk.LabelFrame(self.student_frame, text=_t("log_management.student_system.quick_stats"))
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.student_stats_text = scrolledtext.ScrolledText(stats_frame, wrap=tk.WORD, height=20,
                                                             fg="#000000", bg="#FFFFFF")
        self.student_stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Load initial stats
        self.load_student_stats()

    def setup_dashboard_tab(self):
        """Setup the dashboard tab"""
        self.dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_frame, text="📊 " + _t("log_management.tabs.dashboard"))

        # Title
        title_label = ttk.Label(self.dashboard_frame, text=_t("log_management.dashboard.title"),
                                font=("Arial", 16, "bold"))
        title_label.pack(pady=10)

        # Stats frame
        stats_frame = ttk.LabelFrame(self.dashboard_frame, text=_t("log_management.dashboard.quick_stats"))
        stats_frame.pack(fill=tk.X, padx=10, pady=5)

        # Create stats labels
        self.stats_labels = {}
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(padx=10, pady=10)

        stats_items = [
            (_t("log_management.dashboard.total_activities"), "total_activities"),
            (_t("log_management.dashboard.unique_users"), "unique_users"),
            (_t("log_management.dashboard.success_rate"), "success_rate"),
            (_t("log_management.dashboard.failed_activities"), "failed_activities"),
            (_t("log_management.dashboard.peak_hour"), "peak_hour"),
            (_t("log_management.dashboard.last_24h"), "last_24h")
        ]

        for i, (label, key) in enumerate(stats_items):
            row, col = divmod(i, 3)

            stat_frame = ttk.Frame(stats_grid)
            stat_frame.grid(row=row, column=col, padx=20, pady=5, sticky="w")

            ttk.Label(stat_frame, text=f"{label}:", font=("Arial", 10, "bold")).pack(anchor="w")
            self.stats_labels[key] = ttk.Label(stat_frame, text=_t("log_management.dashboard.loading"),
                                                font=("Arial", 12))
            self.stats_labels[key].pack(anchor="w")

        # Recent activity and controls wrapper
        content_wrapper = ttk.Frame(self.dashboard_frame)
        content_wrapper.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        content_wrapper.rowconfigure(0, weight=1)
        content_wrapper.columnconfigure(0, weight=1)

        recent_frame = ttk.LabelFrame(content_wrapper, text=_t("log_management.dashboard.recent_activity"))
        recent_frame.grid(row=0, column=0, sticky="nsew")

        # Recent activity treeview
        columns = ("Time", "User", "Action", "Module", "Status")
        column_texts = [
            _t("log_management.dashboard.columns.time"),
            _t("log_management.dashboard.columns.user"),
            _t("log_management.dashboard.columns.action"),
            _t("log_management.dashboard.columns.module"),
            _t("log_management.dashboard.columns.status")
        ]
        self.recent_tree = ttk.Treeview(recent_frame, columns=columns, show="headings", height=15)

        for col, col_text in zip(columns, column_texts):
            self.recent_tree.heading(col, text=col_text)
            self.recent_tree.column(col, width=120)

        if STUDENT_SYSTEM_AVAILABLE:
            self.create_student_integration_tab()

        # Scrollbars
        recent_v_scroll = ttk.Scrollbar(recent_frame, orient=tk.VERTICAL,
                                       command=self.recent_tree.yview)
        recent_h_scroll = ttk.Scrollbar(recent_frame, orient=tk.HORIZONTAL,
                                       command=self.recent_tree.xview)
        self.recent_tree.configure(yscrollcommand=recent_v_scroll.set,
                                  xscrollcommand=recent_h_scroll.set)

        # Pack treeview and scrollbars
        self.recent_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        recent_v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        recent_h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Refresh / navigation buttons
        refresh_container = ttk.Frame(content_wrapper)
        refresh_container.grid(row=1, column=0, sticky="w", pady=8)

        ttk.Button(
            refresh_container,
            text="🔄 " + _t("log_management.dashboard.refresh"),
            command=self.update_dashboard
        ).pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(
            refresh_container,
            text="🏠 " + _t("log_management.return_to_homescreen"),
            command=self.return_to_main_menu
        ).pack(side=tk.LEFT)

    def setup_search_tab(self):
        """Setup the search tab"""
        self.search_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.search_frame, text="🔍 " + _t("log_management.tabs.search"))

        # Search controls frame
        search_controls = ttk.LabelFrame(self.search_frame, text=_t("log_management.search.title"))
        search_controls.pack(fill=tk.X, padx=10, pady=5)

        # Create search form
        form_frame = ttk.Frame(search_controls)
        form_frame.pack(padx=10, pady=10)

        # Row 1
        row1 = ttk.Frame(form_frame)
        row1.pack(fill=tk.X, pady=2)

        ttk.Label(row1, text=_t("log_management.search.from_date")).pack(side=tk.LEFT, padx=(0, 5))
        self.date_from_var = tk.StringVar()
        self.date_from_entry = ttk.Entry(row1, textvariable=self.date_from_var, width=12)
        self.date_from_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row1, text=_t("log_management.search.to_date")).pack(side=tk.LEFT, padx=(0, 5))
        self.date_to_var = tk.StringVar()
        self.date_to_entry = ttk.Entry(row1, textvariable=self.date_to_var, width=12)
        self.date_to_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row1, text=_t("log_management.search.user_id")).pack(side=tk.LEFT, padx=(0, 5))
        self.user_id_var = tk.StringVar()
        self.user_id_entry = ttk.Entry(row1, textvariable=self.user_id_var, width=15)
        self.user_id_entry.pack(side=tk.LEFT)

        # Row 2
        row2 = ttk.Frame(form_frame)
        row2.pack(fill=tk.X, pady=2)

        ttk.Label(row2, text=_t("log_management.search.username")).pack(side=tk.LEFT, padx=(0, 5))
        self.username_var = tk.StringVar()
        self.username_entry = ttk.Entry(row2, textvariable=self.username_var, width=15)
        self.username_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row2, text=_t("log_management.search.action")).pack(side=tk.LEFT, padx=(0, 5))
        self.action_var = tk.StringVar()
        self.action_combo = ttk.Combobox(row2, textvariable=self.action_var, width=12,
                                        values=["", "login", "logout", "create", "read", "update", "delete"])
        self.action_combo.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row2, text=_t("log_management.search.module")).pack(side=tk.LEFT, padx=(0, 5))
        self.module_var = tk.StringVar()
        self.module_entry = ttk.Entry(row2, textvariable=self.module_var, width=15)
        self.module_entry.pack(side=tk.LEFT)

        # Row 3
        row3 = ttk.Frame(form_frame)
        row3.pack(fill=tk.X, pady=2)

        ttk.Label(row3, text=_t("log_management.search.status")).pack(side=tk.LEFT, padx=(0, 5))
        self.status_var = tk.StringVar()
        self.status_combo = ttk.Combobox(row3, textvariable=self.status_var, width=12,
                                        values=["", "success", "failure"])
        self.status_combo.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row3, text=_t("log_management.search.search_text")).pack(side=tk.LEFT, padx=(0, 5))
        self.search_text_var = tk.StringVar()
        self.search_text_entry = ttk.Entry(row3, textvariable=self.search_text_var, width=25)
        self.search_text_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row3, text=_t("log_management.search.limit")).pack(side=tk.LEFT, padx=(0, 5))
        self.limit_var = tk.StringVar(value="100")
        self.limit_entry = ttk.Entry(row3, textvariable=self.limit_var, width=8)
        self.limit_entry.pack(side=tk.LEFT)

        # Search buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="🔍 " + _t("log_management.search.buttons.search"), command=self.perform_search).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🗑️ " + _t("log_management.search.buttons.clear"), command=self.clear_search).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="💾 " + _t("log_management.search.buttons.save_search"), command=self.save_search).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="📁 " + _t("log_management.search.buttons.load_search"), command=self.load_search).pack(side=tk.LEFT)

        # Results frame
        results_frame = ttk.LabelFrame(self.search_frame, text=_t("log_management.search.results"))
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Results treeview
        result_columns = ("ID", "Time", "User", "Action", "Module", "Status", "Details")
        result_column_texts = [
            _t("log_management.search.columns.id"),
            _t("log_management.search.columns.time"),
            _t("log_management.search.columns.user"),
            _t("log_management.search.columns.action"),
            _t("log_management.search.columns.module"),
            _t("log_management.search.columns.status"),
            _t("log_management.search.columns.details")
        ]
        self.search_tree = ttk.Treeview(results_frame, columns=result_columns, show="headings")

        for col, col_text in zip(result_columns, result_column_texts):
            self.search_tree.heading(col, text=col_text)
            self.search_tree.column(col, width=100)

        # Results scrollbars
        search_v_scroll = ttk.Scrollbar(results_frame, orient=tk.VERTICAL,
                                       command=self.search_tree.yview)
        search_h_scroll = ttk.Scrollbar(results_frame, orient=tk.HORIZONTAL,
                                       command=self.search_tree.xview)
        self.search_tree.configure(yscrollcommand=search_v_scroll.set,
                                  xscrollcommand=search_h_scroll.set)

        # Pack results components
        self.search_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        search_v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        search_h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Results info
        self.search_info_label = ttk.Label(results_frame, text=_t("log_management.search.no_search"))
        self.search_info_label.pack(pady=5)
        
        # Double-click to view details
        self.search_tree.bind("<Double-1>", self.view_log_details)

    def setup_integration_menu(self):
        """Add integration menu items if student system is available"""
        if self.embedded:
            return
        if STUDENT_SYSTEM_AVAILABLE:
            tools_menu = self.root.nametowidget(self.root['menu']).children['!menu2']
            tools_menu.add_separator()
            tools_menu.add_command(label=_t("log_management.student_logs.title"), command=self.view_student_logs)
    
    def setup_analytics_tab(self):
        """Setup the analytics tab"""
        self.analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.analytics_frame, text="📈 " + _t("log_management.tabs.analytics"))

        # Analytics controls
        controls_frame = ttk.LabelFrame(self.analytics_frame, text=_t("log_management.analytics.title"))
        controls_frame.pack(fill=tk.X, padx=10, pady=5)

        controls_grid = ttk.Frame(controls_frame)
        controls_grid.pack(padx=10, pady=10)

        # Days selection
        ttk.Label(controls_grid, text=_t("log_management.analytics.analysis_period")).grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.analytics_days_var = tk.StringVar(value="7")
        days_combo = ttk.Combobox(controls_grid, textvariable=self.analytics_days_var, width=10,
                                 values=["1", "7", "14", "30", "90"])
        days_combo.grid(row=0, column=1, padx=(0, 10))
        ttk.Label(controls_grid, text=_t("log_management.analytics.days")).grid(row=0, column=2, sticky="w")

        # User selection for user-specific analytics
        ttk.Label(controls_grid, text=_t("log_management.analytics.user_id_optional")).grid(row=1, column=0, sticky="w", padx=(0, 5))
        self.analytics_user_var = tk.StringVar()
        user_entry = ttk.Entry(controls_grid, textvariable=self.analytics_user_var, width=20)
        user_entry.grid(row=1, column=1, columnspan=2, sticky="w")

        # Buttons
        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="📊 " + _t("log_management.analytics.buttons.generate_summary"),
                  command=self.generate_analytics_summary).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="👤 " + _t("log_management.analytics.buttons.user_report"),
                  command=self.generate_user_report).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="📈 " + _t("log_management.analytics.buttons.create_chart"),
                  command=self.generate_chart_dialog).pack(side=tk.LEFT)

        # Results display
        results_frame = ttk.LabelFrame(self.analytics_frame, text=_t("log_management.analytics.results"))
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Text widget for results
        self.analytics_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD,
                                                       font=("Courier", 10),
                                                       fg="#000000", bg="#FFFFFF")
        self.analytics_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def setup_alerts_tab(self):
        """Setup the alerts tab"""
        self.alerts_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.alerts_frame, text="🚨 " + _t("log_management.tabs.alerts"))

        # Alert controls
        controls_frame = ttk.LabelFrame(self.alerts_frame, text=_t("log_management.alerts.title"))
        controls_frame.pack(fill=tk.X, padx=10, pady=5)

        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(padx=10, pady=10)

        ttk.Button(button_frame, text="🔍 " + _t("log_management.alerts.buttons.check_alerts"),
                  command=self.check_alerts).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🔄 " + _t("log_management.alerts.buttons.refresh"),
                  command=self.refresh_alerts).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="✅ " + _t("log_management.alerts.buttons.mark_all_read"),
                  command=self.mark_alerts_read).pack(side=tk.LEFT)

        # Alerts display
        alerts_display_frame = ttk.LabelFrame(self.alerts_frame, text=_t("log_management.alerts.recent_alerts"))
        alerts_display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Alerts treeview
        alert_columns = ("Time", "Type", "Severity", "Message", "Status")
        alert_column_texts = [
            _t("log_management.alerts.columns.time"),
            _t("log_management.alerts.columns.type"),
            _t("log_management.alerts.columns.severity"),
            _t("log_management.alerts.columns.message"),
            _t("log_management.alerts.columns.status")
        ]
        self.alerts_tree = ttk.Treeview(alerts_display_frame, columns=alert_columns, show="headings")

        for col, col_text in zip(alert_columns, alert_column_texts):
            self.alerts_tree.heading(col, text=col_text)
            self.alerts_tree.column(col, width=120)

        # Alerts scrollbar
        alerts_scroll = ttk.Scrollbar(alerts_display_frame, orient=tk.VERTICAL,
                                     command=self.alerts_tree.yview)
        self.alerts_tree.configure(yscrollcommand=alerts_scroll.set)

        self.alerts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        alerts_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Load alerts on startup
        self.refresh_alerts()
    
    def setup_config_tab(self):
        """Setup the configuration tab"""
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="⚙️ " + _t("log_management.tabs.config"))

        # Main config frame with scrollbar
        canvas = tk.Canvas(self.config_frame)
        scrollbar = ttk.Scrollbar(self.config_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # General Settings
        general_frame = ttk.LabelFrame(scrollable_frame, text=_t("log_management.config.general_settings"))
        general_frame.pack(fill=tk.X, padx=10, pady=5)

        # Retention settings
        ttk.Label(general_frame, text=_t("log_management.config.log_retention")).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.retention_var = tk.StringVar()
        ttk.Entry(general_frame, textvariable=self.retention_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(general_frame, text=_t("log_management.config.auto_archive")).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.archive_var = tk.StringVar()
        ttk.Entry(general_frame, textvariable=self.archive_var, width=10).grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(general_frame, text=_t("log_management.config.max_log_size")).grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.max_size_var = tk.StringVar()
        ttk.Entry(general_frame, textvariable=self.max_size_var, width=10).grid(row=2, column=1, padx=5, pady=2)

        # Feature toggles
        features_frame = ttk.LabelFrame(scrollable_frame, text=_t("log_management.config.feature_settings"))
        features_frame.pack(fill=tk.X, padx=10, pady=5)

        self.realtime_var = tk.BooleanVar()
        ttk.Checkbutton(features_frame, text=_t("log_management.config.enable_realtime"),
                       variable=self.realtime_var).pack(anchor="w", padx=5, pady=2)

        self.alerts_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(features_frame, text=_t("log_management.config.enable_alerts"),
                       variable=self.alerts_enabled_var).pack(anchor="w", padx=5, pady=2)

        self.analytics_var = tk.BooleanVar()
        ttk.Checkbutton(features_frame, text=_t("log_management.config.enable_analytics"),
                       variable=self.analytics_var).pack(anchor="w", padx=5, pady=2)

        self.encryption_var = tk.BooleanVar()
        ttk.Checkbutton(features_frame, text=_t("log_management.config.enable_encryption"),
                       variable=self.encryption_var).pack(anchor="w", padx=5, pady=2)

        # Email Settings
        email_frame = ttk.LabelFrame(scrollable_frame, text=_t("log_management.config.email_notifications"))
        email_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(email_frame, text=_t("log_management.config.alert_email")).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.alert_email_var = tk.StringVar()
        ttk.Entry(email_frame, textvariable=self.alert_email_var, width=30).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(email_frame, text=_t("log_management.config.smtp_server")).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.smtp_server_var = tk.StringVar()
        ttk.Entry(email_frame, textvariable=self.smtp_server_var, width=30).grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(email_frame, text=_t("log_management.config.smtp_port")).grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.smtp_port_var = tk.StringVar()
        ttk.Entry(email_frame, textvariable=self.smtp_port_var, width=10).grid(row=2, column=1, padx=5, pady=2)

        # SMTP Configuration
        smtp_frame = ttk.LabelFrame(scrollable_frame, text=_t("log_management.config.smtp_config"))
        smtp_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(smtp_frame, text=_t("log_management.config.smtp_username")).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.smtp_username_var = tk.StringVar()
        ttk.Entry(smtp_frame, textvariable=self.smtp_username_var, width=30).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(smtp_frame, text=_t("log_management.config.smtp_password")).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.smtp_password_var = tk.StringVar()
        ttk.Entry(smtp_frame, textvariable=self.smtp_password_var, width=30, show="*").grid(row=1, column=1, padx=5, pady=2)

        # Webhook Configuration
        webhook_frame = ttk.LabelFrame(scrollable_frame, text=_t("log_management.config.webhook_config"))
        webhook_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(webhook_frame, text=_t("log_management.config.webhook_secret")).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.webhook_secret_var = tk.StringVar()
        ttk.Entry(webhook_frame, textvariable=self.webhook_secret_var, width=30, show="*").grid(row=0, column=1, padx=5, pady=2)

        # API Settings
        api_frame = ttk.LabelFrame(scrollable_frame, text=_t("log_management.config.api_settings"))
        api_frame.pack(fill=tk.X, padx=10, pady=5)

        self.api_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(api_frame, text=_t("log_management.config.enable_api"),
                       variable=self.api_enabled_var).pack(anchor="w", padx=5, pady=2)

        ttk.Label(api_frame, text=_t("log_management.config.api_secret_key")).pack(anchor="w", padx=5)
        self.api_key_var = tk.StringVar()
        api_key_frame = ttk.Frame(api_frame)
        api_key_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Entry(api_key_frame, textvariable=self.api_key_var, width=40, show="*").pack(side=tk.LEFT)
        ttk.Button(api_key_frame, text=_t("log_management.config.generate"), command=self.generate_api_key).pack(side=tk.LEFT, padx=(5, 0))

        api_control_frame = ttk.Frame(api_frame)
        api_control_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Button(api_control_frame, text=_t("log_management.config.start_api_server"),
                  command=self.start_api_server).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(api_control_frame, text=_t("log_management.config.view_api_stats"),
                  command=lambda: self.view_api_stats(self.log_manager)).pack(side=tk.LEFT)

        # Config buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="💾 " + _t("log_management.config.buttons.save"),
                  command=self.save_configuration).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🔄 " + _t("log_management.config.buttons.load"),
                  command=self.load_configuration).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🔄 " + _t("log_management.config.buttons.reset"),
                  command=self.reset_configuration).pack(side=tk.LEFT)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Load current configuration
        self.load_configuration()

    def setup_maintenance_tab(self):
        """Setup the maintenance tab"""
        self.maintenance_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.maintenance_frame, text="🔧 " + _t("log_management.tabs.maintenance"))

        # Database section
        db_frame = ttk.LabelFrame(self.maintenance_frame, text=_t("log_management.maintenance.db_maintenance"))
        db_frame.pack(fill=tk.X, padx=10, pady=5)
        
        db_button_frame = ttk.Frame(db_frame)
        db_button_frame.pack(padx=10, pady=10)

        ttk.Button(db_button_frame, text="📊 " + _t("log_management.maintenance.buttons.db_info"),
                  command=self.show_database_info).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(db_button_frame, text="⚡ " + _t("log_management.maintenance.buttons.optimize"),
                  command=self.optimize_database).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(db_button_frame, text="🧹 " + _t("log_management.maintenance.buttons.vacuum"),
                  command=self.vacuum_database).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(db_button_frame, text="🔍 " + _t("log_management.maintenance.buttons.integrity_check"),
                  command=self.run_integrity_check).pack(side=tk.LEFT)

        # Archive section
        archive_frame = ttk.LabelFrame(self.maintenance_frame, text=_t("log_management.maintenance.archive_management"))
        archive_frame.pack(fill=tk.X, padx=10, pady=5)

        archive_button_frame = ttk.Frame(archive_frame)
        archive_button_frame.pack(padx=10, pady=10)

        ttk.Button(archive_button_frame, text="📦 " + _t("log_management.maintenance.archive_buttons.archive_old"),
                  command=self.archive_old_logs).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(archive_button_frame, text="🗑️ " + _t("log_management.maintenance.archive_buttons.cleanup_old"),
                  command=self.cleanup_old_logs).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(archive_button_frame, text="📁 " + _t("log_management.maintenance.archive_buttons.view_archives"),
                  command=self.view_archives).pack(side=tk.LEFT)

        # Performance section
        perf_frame = ttk.LabelFrame(self.maintenance_frame, text=_t("log_management.maintenance.performance_testing"))
        perf_frame.pack(fill=tk.X, padx=10, pady=5)

        perf_button_frame = ttk.Frame(perf_frame)
        perf_button_frame.pack(padx=10, pady=10)

        ttk.Button(perf_button_frame, text="🏃 " + _t("log_management.maintenance.perf_buttons.query_perf"),
                  command=self.test_query_performance).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(perf_button_frame, text="💾 " + _t("log_management.maintenance.perf_buttons.insert_perf"),
                  command=self.test_insert_performance).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(perf_button_frame, text="📊 " + _t("log_management.maintenance.perf_buttons.system_resources"),
                  command=self.show_system_resources).pack(side=tk.LEFT)

        # Results display
        results_frame = ttk.LabelFrame(self.maintenance_frame, text=_t("log_management.maintenance.results"))
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.maintenance_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD,
                                                         font=("Courier", 10),
                                                         fg="#000000", bg="#FFFFFF")
        self.maintenance_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def setup_status_bar(self):
        """Setup the status bar"""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(self.status_bar, text=_t("log_management.status_bar.ready"))
        self.status_label.pack(side=tk.LEFT, padx=5)

        # Add connection status
        db_status = self._check_database_connection()
        self.connection_label = ttk.Label(self.status_bar, text=_t("log_management.status_bar.database", status=db_status))
        self.connection_label.pack(side=tk.RIGHT, padx=5)

        # Language change button
        if I18N_AVAILABLE:
            lang_button = ttk.Button(
                self.status_bar,
                text="🌐 " + _t("log_management.language.button"),
                command=self._on_language_change
            )
            lang_button.pack(side=tk.RIGHT, padx=5)

        # Consistent navigation back to the main menu
        exit_button = ttk.Button(
            self.status_bar,
            text="🏠 " + _t("log_management.return_to_main"),
            command=self.return_to_main_menu
        )
        exit_button.pack(side=tk.RIGHT, padx=5)

    def _on_language_change(self):
        """Handle language change request"""
        current_lang = get_current_language()
        show_gui_language_selector(self.root)
        new_lang = get_current_language()

        if new_lang != current_lang:
            messagebox.showinfo(
                _t("log_management.language.changed_title"),
                _t("log_management.language.changed_message")
            )
            self._refresh_ui_language()

    def _refresh_ui_language(self):
        """Refresh the UI after language change"""
        # Re-initialize i18n with new language
        init_i18n(get_current_language())

        # Update window title
        if not self.embedded:
            self.root.title(_t("log_management.window_title"))

        # Rebuild the UI by destroying and recreating all widgets
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        if hasattr(self, 'status_bar'):
            self.status_bar.destroy()

        # Recreate notebook and tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.setup_dashboard_tab()
        self.setup_search_tab()
        self.setup_analytics_tab()
        self.setup_alerts_tab()
        self.setup_config_tab()
        self.setup_maintenance_tab()

        self.setup_status_bar()

        if not self.embedded:
            self.update_dashboard()

    def _check_database_connection(self):
        """Check if database connection is working"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            conn.close()

            # Check if required tables exist
            required_tables = {'logs', 'alerts', 'saved_searches', 'students'}
            existing_tables = {table[0] for table in tables}

            if required_tables.issubset(existing_tables):
                return _t("log_management.status_bar.connected")
            else:
                return _t("log_management.status_bar.missing_tables")
        except Exception:
            return _t("log_management.status_bar.disconnected")

    def update_status(self, message):
        """Update status bar message (safe if status bar not yet built)"""
        if not hasattr(self, "status_label"):
            # build it on first use to avoid AttributeError
            self.setup_status_bar()
        self.status_label.config(text=message)
        self.root.update_idletasks()

    def refresh_connection_status(self):
        """Refresh database connection status in status bar"""
        if hasattr(self, "connection_label"):
            db_status = self._check_database_connection()
            self.connection_label.config(text=_t("log_management.status_bar.database", status=db_status))

    def update_dashboard(self):
        """Update dashboard with current statistics"""
        if not self.log_manager:
            self.update_status(_t("log_management.messages.log_manager_not_available"))
            return

        self.update_status(_t("log_management.messages.updating_dashboard"))
        
        try:
            # Get summary data
            summary = self.log_manager.analytics.generate_activity_summary(7)
            
            if "error" not in summary:
                # Update stats labels
                self.stats_labels["total_activities"].config(text=f"{summary['total_activities']:,}")
                self.stats_labels["unique_users"].config(text=str(summary['unique_users']))
                self.stats_labels["success_rate"].config(text=f"{summary['success_rate']:.1f}%")
                self.stats_labels["failed_activities"].config(text=str(summary['failed_activities']))
                self.stats_labels["peak_hour"].config(text=f"{summary['peak_activity_hour']}:00")
                
                # Get last 24h count
                filters_24h = {
                    'date_from': (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d')
                }
                recent_results = self.log_manager.db.search_logs(filters_24h, limit=10000)
                recent_count = len(recent_results) if recent_results else 0
                self.stats_labels["last_24h"].config(text=str(recent_count))
            
            # Update recent activity
            self.update_recent_activity()
            
            self.update_status(_t("log_management.messages.dashboard_updated"))

        except Exception as e:
            self.update_status(_t("log_management.errors.update_dashboard", error=str(e)))
    
    def update_recent_activity(self):
        """Update recent activity display"""
        if not self.log_manager:
            return
            
        try:
            # Clear existing items
            for item in self.recent_tree.get_children():
                self.recent_tree.delete(item)
            
            # Get recent logs
            filters = {
                'date_from': (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d')
            }
            recent_logs = self.log_manager.db.search_logs(filters, limit=50)

            # Add to tree
            if recent_logs:
                for log in recent_logs:
                    timestamp = log.get('timestamp', '')[:19]
                    user = log.get('username', '')
                    action = log.get('action', '')
                    module = log.get('module', '')
                    status = log.get('status', '')

                    # Add status icon
                    status_display = f"✅ {status}" if status == "success" else f"❌ {status}"

                    self.recent_tree.insert("", 0, values=(timestamp, user, action, module, status_display))
                
        except Exception as e:
            print(f"Error updating recent activity: {e}")
    
    def perform_search(self):
        """Perform log search based on form inputs"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        self.update_status(_t("log_management.messages.searching_logs"))
        
        try:
            # Build filters from form
            filters = {}
            
            if self.date_from_var.get():
                filters['date_from'] = self.date_from_var.get()
            if self.date_to_var.get():
                filters['date_to'] = self.date_to_var.get()
            if self.user_id_var.get():
                filters['user_id'] = self.user_id_var.get()
            if self.username_var.get():
                filters['username'] = self.username_var.get()
            if self.action_var.get():
                filters['action'] = self.action_var.get()
            if self.module_var.get():
                filters['module'] = self.module_var.get()
            if self.status_var.get():
                filters['status'] = self.status_var.get()
            if self.search_text_var.get():
                filters['search_text'] = self.search_text_var.get()
            
            # Get limit
            try:
                limit = int(self.limit_var.get())
            except ValueError:
                limit = 100
            
            # Perform search
            results = self.log_manager.db.search_logs(filters, limit=limit)

            # Ensure results is a list
            if results is None:
                results = []

            # Clear existing results
            for item in self.search_tree.get_children():
                self.search_tree.delete(item)

            # Add results to tree
            for i, log in enumerate(results, 1):
                timestamp = log.get('timestamp', '')[:19] if log.get('timestamp') else ''
                user = log.get('username', '')
                action = log.get('action', '')
                module = log.get('module', '')
                status = log.get('status', '')
                details = log.get('details', '') or ''

                # Truncate details if too long
                if details and len(details) > 50:
                    details = details[:47] + "..."

                self.search_tree.insert("", "end", values=(
                    i, timestamp, user, action, module, status, details
                ))

            # Update info label
            self.search_info_label.config(text=_t("log_management.search.found_results", count=len(results)))
            self.update_status(_t("log_management.messages.search_completed", count=len(results)))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.search", error=str(e)))
            self.update_status(_t("log_management.messages.search_failed"))
    
    def clear_search(self):
        """Clear search form"""
        self.date_from_var.set("")
        self.date_to_var.set("")
        self.user_id_var.set("")
        self.username_var.set("")
        self.action_var.set("")
        self.module_var.set("")
        self.status_var.set("")
        self.search_text_var.set("")
        self.limit_var.set("100")
        
        # Clear results
        for item in self.search_tree.get_children():
            self.search_tree.delete(item)
        self.search_info_label.config(text=_t("log_management.search.search_cleared"))

    def save_search(self):
        """Save current search filters"""
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.auth_required"))
            return

        name = tk.simpledialog.askstring(_t("log_management.dialogs.save_search.title"), _t("log_management.dialogs.save_search.prompt"))
        if not name:
            return

        try:
            filters = {}
            if self.date_from_var.get(): filters['date_from'] = self.date_from_var.get()
            if self.date_to_var.get(): filters['date_to'] = self.date_to_var.get()
            if self.user_id_var.get(): filters['user_id'] = self.user_id_var.get()
            if self.username_var.get(): filters['username'] = self.username_var.get()
            if self.action_var.get(): filters['action'] = self.action_var.get()
            if self.module_var.get(): filters['module'] = self.module_var.get()
            if self.status_var.get(): filters['status'] = self.status_var.get()
            if self.search_text_var.get(): filters['search_text'] = self.search_text_var.get()
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO saved_searches (name, user_id, search_params)
                VALUES (?, ?, ?)
            ''', (name, self.auth.current_user['id'], json.dumps(filters)))
            
            conn.commit()
            conn.close()

            messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.dialogs.save_search.saved", name=name))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.save_search", error=str(e)))

    def load_search(self):
        """Load a saved search"""
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.auth_required"))
            return
            
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM saved_searches 
                WHERE user_id = ? 
                ORDER BY created_at DESC
            ''', (self.auth.current_user['id'],))
            
            searches = cursor.fetchall()
            conn.close()

            if not searches:
                messagebox.showinfo(_t("log_management.messages.info"), _t("log_management.dialogs.load_search.no_searches"))
                return

            # Create selection dialog
            search_window = tk.Toplevel(self.root)
            search_window.title(_t("log_management.dialogs.load_search.title"))
            search_window.geometry("400x300")

            ttk.Label(search_window, text=_t("log_management.dialogs.load_search.select")).pack(pady=10)
            
            # Listbox for searches
            search_listbox = tk.Listbox(search_window)
            search_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            
            for search in searches:
                search_listbox.insert(tk.END, f"{search['name']} ({search['created_at'][:19]})")
            
            def load_selected():
                selection = search_listbox.curselection()
                if not selection:
                    return
                    
                selected_search = searches[selection[0]]
                filters = json.loads(selected_search['search_params'])
                
                # Load filters into form
                self.date_from_var.set(filters.get('date_from', ''))
                self.date_to_var.set(filters.get('date_to', ''))
                self.user_id_var.set(filters.get('user_id', ''))
                self.username_var.set(filters.get('username', ''))
                self.action_var.set(filters.get('action', ''))
                self.module_var.set(filters.get('module', ''))
                self.status_var.set(filters.get('status', ''))
                self.search_text_var.set(filters.get('search_text', ''))
                
                search_window.destroy()
                messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.dialogs.load_search.loaded", name=selected_search['name']))

            ttk.Button(search_window, text=_t("log_management.dialogs.load_search.load"), command=load_selected).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.load_search", error=str(e)))
    
    def view_log_details(self, event):
        """View detailed log information"""
        selection = self.search_tree.selection()
        if not selection:
            return
            
        item = self.search_tree.item(selection[0])
        values = item['values']
        
        if not values:
            return
            
        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title(_t("log_management.dialogs.log_details.title"))
        details_window.geometry("600x400")
        
        # Get full log data
        try:
            log_id = values[0]
            # For simplicity, we'll recreate the search to get full details
            # In a real implementation, you'd store the full log data
            
            details_text = scrolledtext.ScrolledText(details_window, wrap=tk.WORD)
            details_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            details_content = f"""Log Entry Details
====================

ID: {values[0]}
Timestamp: {values[1]}
User: {values[2]}
Action: {values[3]}
Module: {values[4]}
Status: {values[5]}
Details: {values[6]}

This is a simplified view. In a full implementation,
you would display all available log fields including
IP address, user agent, session ID, etc.
"""
            
            details_text.insert("1.0", details_content)
            details_text.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.view_details", error=str(e)))

    def generate_analytics_summary(self):
        """Generate analytics summary"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        self.update_status(_t("log_management.messages.generating_summary"))
        
        try:
            days = int(self.analytics_days_var.get())
            summary = self.log_manager.analytics.generate_activity_summary(days)
            
            if "error" in summary:
                self.analytics_text.delete("1.0", tk.END)
                self.analytics_text.insert("1.0", summary["error"])
                return
            
            # Format summary for display
            output = f"""Activity Summary - Last {days} Days
{'='*50}

Period: {summary['period']}
Total Activities: {summary['total_activities']:,}
Unique Users: {summary['unique_users']}
Success Rate: {summary['success_rate']:.2f}%
Failed Activities: {summary['failed_activities']}
Peak Activity Hour: {summary['peak_activity_hour']}:00

Most Active Users:
{'-'*30}
"""
            
            for user, count in list(summary['most_active_users'].items())[:10]:
                output += f"{user:<20} {count:>8}\n"
            
            output += f"\nActivity by Action:\n{'-'*30}\n"
            for action, count in summary['activity_by_action'].items():
                output += f"{action:<20} {count:>8}\n"
            
            output += f"\nActivity by Module:\n{'-'*30}\n"
            for module, count in summary['activity_by_module'].items():
                output += f"{module:<20} {count:>8}\n"
            
            self.analytics_text.delete("1.0", tk.END)
            self.analytics_text.insert("1.0", output)

            self.update_status(_t("log_management.messages.summary_generated"))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.analytics", error=str(e)))
            self.update_status(_t("log_management.messages.analytics_failed"))

    def generate_user_report(self):
        """Generate user-specific report"""
        user_id = self.analytics_user_var.get()
        if not user_id:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.enter_user_id"))
            return

        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        self.update_status(_t("log_management.messages.generating_report", user_id=user_id))
        
        try:
            days = int(self.analytics_days_var.get())
            report = self.log_manager.analytics.generate_user_activity_report(user_id, days)
            
            if "error" in report:
                self.analytics_text.delete("1.0", tk.END)
                self.analytics_text.insert("1.0", report["error"])
                return
            
            # Format report for display
            output = f"""User Activity Report: {report['username']} ({report['user_id']})
{'='*60}

Period: {report['period']}
Total Activities: {report['total_activities']:,}
Success Rate: {report['success_rate']:.2f}%

Modules Used:
{'-'*30}
"""
            
            for module, count in list(report['modules_used'].items())[:10]:
                output += f"{module:<25} {count:>8}\n"
            
            output += f"\nActions Performed:\n{'-'*30}\n"
            for action, count in report['actions_performed'].items():
                output += f"{action:<25} {count:>8}\n"
            
            output += f"\nMost Active Hours:\n{'-'*30}\n"
            sorted_hours = sorted(report['activity_hours'].items(), key=lambda x: x[1], reverse=True)
            for hour, count in sorted_hours[:10]:
                output += f"{hour:02d}:00{'':<20} {count:>8}\n"
            
            self.analytics_text.delete("1.0", tk.END)
            self.analytics_text.insert("1.0", output)

            self.update_status(_t("log_management.messages.report_generated", user_id=user_id))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.user_report", error=str(e)))
            self.update_status(_t("log_management.messages.report_failed"))
    
    def generate_chart_dialog(self):
        """Show chart generation dialog"""
        chart_window = tk.Toplevel(self.root)
        chart_window.title(_t("log_management.dialogs.chart_generation.title"))
        chart_window.geometry("400x300")

        ttk.Label(chart_window, text=_t("log_management.dialogs.chart_generation.options"),
                 font=("Arial", 12, "bold")).pack(pady=10)

        # Days selection
        days_frame = ttk.Frame(chart_window)
        days_frame.pack(pady=10)

        ttk.Label(days_frame, text=_t("log_management.dialogs.chart_generation.period")).pack(side=tk.LEFT)
        days_var = tk.StringVar(value="7")
        ttk.Entry(days_frame, textvariable=days_var, width=10).pack(side=tk.LEFT, padx=5)
        
        # Save path
        path_frame = ttk.Frame(chart_window)
        path_frame.pack(pady=10, fill=tk.X, padx=20)

        ttk.Label(path_frame, text=_t("log_management.dialogs.chart_generation.save_path")).pack(anchor="w")
        path_var = tk.StringVar()
        path_entry = ttk.Entry(path_frame, textvariable=path_var)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def browse_path():
            filename = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
            )
            if filename:
                path_var.set(filename)

        ttk.Button(path_frame, text=_t("log_management.dialogs.chart_generation.browse"), command=browse_path).pack(side=tk.RIGHT, padx=(5, 0))

        # Generate button
        def generate_chart():
            try:
                days = int(days_var.get())
                save_path = path_var.get()

                if not save_path:
                    charts_dir = LOG_DIR / "charts"
                    charts_dir.mkdir(parents=True, exist_ok=True)
                    save_path = str(charts_dir / f"activity_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")

                result_path = self.log_manager.analytics.create_activity_chart("daily", days, save_path)

                if result_path:
                    messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.dialogs.chart_generation.saved", path=result_path))
                else:
                    messagebox.showinfo(_t("log_management.messages.info"), _t("log_management.dialogs.chart_generation.displayed"))

                chart_window.destroy()

            except Exception as e:
                messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.chart", error=str(e)))

        ttk.Button(chart_window, text=_t("log_management.dialogs.chart_generation.generate"), command=generate_chart).pack(pady=20)
    
    def check_alerts(self):
        """Check for alerts"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        self.update_status(_t("log_management.messages.checking_alerts"))

        try:
            alerts = self.log_manager.alerts.run_alert_checks()

            if not alerts:
                messagebox.showinfo(_t("log_management.alerts.title"), _t("log_management.messages.no_alerts"))
            else:
                messagebox.showinfo(_t("log_management.alerts.title"), _t("log_management.messages.alerts_found", count=len(alerts)))

            self.refresh_alerts()
            self.update_status(_t("log_management.alerts.alerts_checked"))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.alerts", error=str(e)))
            self.update_status(_t("log_management.messages.alert_check_failed"))
    
    def refresh_alerts(self):
        """Refresh alerts display"""
        if not self.log_manager:
            return
            
        try:
            # Clear existing alerts
            for item in self.alerts_tree.get_children():
                self.alerts_tree.delete(item)
            
            # Get recent alerts from database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM alerts 
                WHERE triggered_at > datetime('now', '-24 hours')
                ORDER BY triggered_at DESC
                LIMIT 50
            ''')
            
            alerts = cursor.fetchall()
            conn.close()
            
            # Add alerts to tree
            for alert in alerts:
                time_str = alert['triggered_at'][:19]
                alert_type = alert['alert_type']
                severity = alert['severity']
                message = alert['message']
                status = _t("log_management.alert_status.resolved") if alert['resolved'] else _t("log_management.alert_status.active")
                
                # Add severity icon
                severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
                severity_display = f"{severity_icon} {severity}"
                
                self.alerts_tree.insert("", "end", values=(
                    time_str, alert_type, severity_display, message, status
                ))
                
        except Exception as e:
            print(f"Error refreshing alerts: {e}")
    
    def mark_alerts_read(self):
        """Mark all alerts as read/resolved"""
        if not self.log_manager:
            return
            
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE alerts 
                SET resolved = TRUE, resolved_at = CURRENT_TIMESTAMP
                WHERE resolved = FALSE
            ''')
            
            updated_count = cursor.rowcount
            conn.commit()
            conn.close()

            messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.messages.alerts_marked_read", count=updated_count))
            self.refresh_alerts()

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.mark_alerts", error=str(e)))
    
    def load_configuration(self):
        """Load current configuration into form"""
        if not self.log_manager:
            return
            
        try:
            config = self.log_manager.config.config
            
            self.retention_var.set(str(config.get('retention_days', 90)))
            self.archive_var.set(str(config.get('auto_archive_days', 30)))
            self.max_size_var.set(str(config.get('max_log_size_mb', 100)))
            
            self.realtime_var.set(config.get('enable_real_time', True))
            self.alerts_enabled_var.set(config.get('enable_alerts', True))
            self.analytics_var.set(config.get('enable_analytics', True))
            self.encryption_var.set(config.get('enable_encryption', True))
            self.smtp_username_var.set(config.get('smtp_username', ''))
            self.smtp_password_var.set(config.get('smtp_password', ''))
            self.webhook_secret_var.set(config.get('webhook_secret', ''))
            self.alert_email_var.set(config.get('alert_email', ''))
            self.smtp_server_var.set(config.get('smtp_server', ''))
            self.smtp_port_var.set(str(config.get('smtp_port', 587)))
            
            self.api_enabled_var.set(config.get('api_enabled', False))
            self.api_key_var.set(config.get('api_secret_key', ''))
            
        except Exception as e:
            print(f"Error loading configuration: {e}")
    
    def save_configuration(self):
        """Save configuration changes"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return
            
        try:
            # Validate and save each setting
            try:
                retention_days = int(self.retention_var.get())
                self.log_manager.config.set('retention_days', retention_days)
            except ValueError as e:
                logger.warning(f"Invalid retention_days value: {e}")
            
            try:
                archive_days = int(self.archive_var.get())
                self.log_manager.config.set('auto_archive_days', archive_days)
            except ValueError as e:
                logger.warning(f"Invalid auto_archive_days value: {e}")
            
            try:
                max_size = int(self.max_size_var.get())
                self.log_manager.config.set('max_log_size_mb', max_size)
            except ValueError as e:
                logger.warning(f"Invalid max_log_size_mb value: {e}")
            
            self.log_manager.config.set('enable_real_time', self.realtime_var.get())
            self.log_manager.config.set('enable_alerts', self.alerts_enabled_var.get())
            self.log_manager.config.set('enable_analytics', self.analytics_var.get())
            self.log_manager.config.set('enable_encryption', self.encryption_var.get())
            self.log_manager.config.set('smtp_username', self.smtp_username_var.get())
            self.log_manager.config.set('smtp_password', self.smtp_password_var.get())
            self.log_manager.config.set('webhook_secret', self.webhook_secret_var.get())
            self.log_manager.config.set('alert_email', self.alert_email_var.get())
            self.log_manager.config.set('smtp_server', self.smtp_server_var.get())
            
            try:
                smtp_port = int(self.smtp_port_var.get())
                self.log_manager.config.set('smtp_port', smtp_port)
            except ValueError as e:
                logger.warning(f"Invalid smtp_port value: {e}")
            
            self.log_manager.config.set('api_enabled', self.api_enabled_var.get())
            self.log_manager.config.set('api_secret_key', self.api_key_var.get())

            messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.config.messages.saved"))
            self.update_status(_t("log_management.messages.config_saved"))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.config_save", error=str(e)))

    def reset_configuration(self):
        """Reset configuration to defaults"""
        if messagebox.askyesno(_t("log_management.messages.confirm"), _t("log_management.config.messages.reset_confirm")):
            try:
                self.log_manager.config.config = self.log_manager.config.default_config.copy()
                self.log_manager.config.save_config()
                self.load_configuration()
                messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.config.messages.reset_done"))
            except Exception as e:
                messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.config_load", error=str(e)))

    def generate_api_key(self):
        """Generate new API key"""
        import secrets
        new_key = secrets.token_urlsafe(32)
        self.api_key_var.set(new_key)
        messagebox.showinfo(_t("log_management.config.api_key_generated"), _t("log_management.config.api_key_message"))

    def export_logs_dialog(self):
        """Show export logs dialog"""
        export_window = tk.Toplevel(self.root)
        export_window.title(_t("log_management.dialogs.export.title"))
        export_window.geometry("500x400")

        ttk.Label(export_window, text=_t("log_management.dialogs.export.title"), font=("Arial", 14, "bold")).pack(pady=10)
        
        # Export options frame
        options_frame = ttk.LabelFrame(export_window, text=_t("log_management.export_options.title"))
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        # Format selection
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(format_frame, text=_t("log_management.export_options.format")).pack(side=tk.LEFT)
        format_var = tk.StringVar(value="json")
        format_combo = ttk.Combobox(format_frame, textvariable=format_var, 
                                   values=["json", "csv", "excel"], state="readonly")
        format_combo.pack(side=tk.LEFT, padx=5)
        
        # Date range
        date_frame = ttk.Frame(options_frame)
        date_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(date_frame, text=_t("log_management.export_options.last")).pack(side=tk.LEFT)
        days_var = tk.StringVar(value="7")
        ttk.Entry(date_frame, textvariable=days_var, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Label(date_frame, text=_t("log_management.export_options.days")).pack(side=tk.LEFT)
        
        # Export function
        def perform_export():
            try:
                days = int(days_var.get())
                file_format = format_var.get()
                
                # Get export file path
                if file_format == "csv":
                    file_path = filedialog.asksaveasfilename(
                        defaultextension=".csv",
                        filetypes=[("CSV files", "*.csv")]
                    )
                elif file_format == "excel":
                    file_path = filedialog.asksaveasfilename(
                        defaultextension=".xlsx",
                        filetypes=[("Excel files", "*.xlsx")]
                    )
                else:
                    file_path = filedialog.asksaveasfilename(
                        defaultextension=".json",
                        filetypes=[("JSON files", "*.json")]
                    )
                
                if not file_path:
                    return
                
                # Get logs for export
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                filters = {
                    'date_from': start_date.strftime('%Y-%m-%d'),
                    'date_to': end_date.strftime('%Y-%m-%d')
                }
                
                results = self.log_manager.db.search_logs(filters, limit=10000)

                if not results:
                    messagebox.showwarning(_t("log_management.export_options.no_data"), _t("log_management.export_options.no_logs_for_export"))
                    return

                # Export based on format
                if file_format == "csv":
                    import pandas as pd
                    df = pd.DataFrame(results)
                    df.to_csv(file_path, index=False)
                elif file_format == "excel":
                    import pandas as pd
                    df = pd.DataFrame(results)
                    df.to_excel(file_path, index=False)
                else:  # JSON
                    export_data = {
                        "export_info": {
                            "timestamp": datetime.now().isoformat(),
                            "filters": filters,
                            "record_count": len(results)
                        },
                        "logs": results
                    }
                    with open(file_path, 'w') as f:
                        json.dump(export_data, f, indent=2)
                
                messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.export_options.success", count=len(results), path=file_path))
                export_window.destroy()

            except Exception as e:
                messagebox.showerror(_t("log_management.messages.error"), _t("log_management.export_options.error", error=str(e)))

        ttk.Button(options_frame, text=_t("log_management.dialogs.export.export"), command=perform_export).pack(pady=10)
    
    def import_logs_dialog(self):
        """Show import logs dialog"""
        file_path = filedialog.askopenfilename(
            title=_t("log_management.import_dialog.select_file"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            logs = data.get('logs', [])
            if not logs:
                messagebox.showwarning(_t("log_management.import_dialog.no_data"), _t("log_management.import_dialog.no_logs_in_file"))
                return

            if messagebox.askyesno(_t("log_management.import_dialog.confirm_title"), _t("log_management.import_dialog.confirm_message", count=len(logs))):
                imported_count = 0
                for log in logs:
                    try:
                        self.log_manager.db.insert_log(log)
                        imported_count += 1
                    except Exception as e:
                        print(f"Error importing log: {e}")

                messagebox.showinfo(_t("log_management.import_dialog.complete"), _t("log_management.import_dialog.success", count=imported_count, total=len(logs)))
                self.update_dashboard()

        except Exception as e:
            messagebox.showerror(_t("log_management.import_dialog.error"), _t("log_management.import_dialog.error_message", error=str(e)))

    def scheduled_reports_menu_gui(self):
        """GUI version of scheduled reports menu"""
        reports_window = tk.Toplevel(self.root)
        reports_window.title(_t("log_management.scheduled_reports.title"))
        reports_window.geometry("600x500")

        ttk.Label(reports_window, text=_t("log_management.scheduled_reports.config_title"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Daily Email Reports
        daily_frame = ttk.LabelFrame(reports_window, text=_t("log_management.scheduled_reports.daily_reports"))
        daily_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(daily_frame, text=_t("log_management.scheduled_reports.email_address")).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        daily_email_var = tk.StringVar(value=self.log_manager.config.get('alert_email', ''))
        ttk.Entry(daily_frame, textvariable=daily_email_var, width=30).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(daily_frame, text=_t("log_management.scheduled_reports.send_time")).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        time_var = tk.StringVar(value="08:00")
        ttk.Entry(daily_frame, textvariable=time_var, width=10).grid(row=1, column=1, sticky="w", padx=5, pady=2)

        def save_daily_reports():
            self.log_manager.config.set('alert_email', daily_email_var.get())
            self.log_manager.config.set('daily_report_time', time_var.get())
            messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.scheduled_reports.saved"))

        ttk.Button(daily_frame, text=_t("log_management.scheduled_reports.save_daily"), command=save_daily_reports).grid(row=2, column=0, columnspan=2, pady=10)

        # Weekly Reports
        weekly_frame = ttk.LabelFrame(reports_window, text=_t("log_management.scheduled_reports.weekly_reports"))
        weekly_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(weekly_frame, text=_t("log_management.scheduled_reports.email_address")).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        weekly_email_var = tk.StringVar(value=self.log_manager.config.get('weekly_report_email', ''))
        ttk.Entry(weekly_frame, textvariable=weekly_email_var, width=30).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(weekly_frame, text=_t("log_management.scheduled_reports.day_of_week")).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        day_var = tk.StringVar(value="Monday")
        day_combo = ttk.Combobox(weekly_frame, textvariable=day_var,
                                values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        day_combo.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        def save_weekly_reports():
            day_map = {"Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
                      "Friday": 5, "Saturday": 6, "Sunday": 7}
            self.log_manager.config.set('weekly_report_email', weekly_email_var.get())
            self.log_manager.config.set('weekly_report_day', day_map[day_var.get()])
            messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.reports.weekly_saved"))

        ttk.Button(weekly_frame, text=_t("log_management.scheduled_reports.save_weekly"), command=save_weekly_reports).grid(row=2, column=0, columnspan=2, pady=10)

    def test_database_response_times_gui(self):
        """GUI version of database response time testing"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        self.update_status(_t("log_management.messages.testing_response"))
        
        try:
            import time
            from university_system.infrastructure.database.db import sqlite3
            # Test different operations
            tests = [
                ("Connection", self._test_db_connection),
                ("Simple Query", self._test_simple_query),
                ("Complex Query", self._test_complex_query),
            ]
            
            output = "Database Response Time Test Results\n"
            output += "="*40 + "\n\n"
            output += f"{'Test':<20} {'Avg (ms)':<10} {'Min (ms)':<10} {'Max (ms)':<10}\n"
            output += "-" * 55 + "\n"
            
            for test_name, test_func in tests:
                times = []
                
                # Run each test 5 times
                for _ in range(5):
                    start_time = time.time()
                    try:
                        test_func()
                        end_time = time.time()
                        times.append((end_time - start_time) * 1000)  # Convert to ms
                    except Exception as e:
                        print(f"Error in {test_name}: {e}")
                        times.append(float('inf'))
                
                # Calculate statistics
                if times and all(t != float('inf') for t in times):
                    avg_time = sum(times) / len(times)
                    min_time = min(times)
                    max_time = max(times)
                    
                    output += f"{test_name:<20} {avg_time:<9.2f} {min_time:<9.2f} {max_time:<9.2f}\n"
            
            self.maintenance_text.delete("1.0", tk.END)
            self.maintenance_text.insert("1.0", output)

            self.update_status(_t("log_management.messages.response_test_completed"))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.response_time", error=str(e)))
            self.update_status(_t("log_management.messages.response_test_failed"))

    def _test_db_connection(self):
        """Helper for connection test"""
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.close()

    def _test_simple_query(self):
        """Helper for simple query test"""
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        # First check if logs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='logs'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM activity_log LIMIT 1")
            cursor.fetchone()
        else:
            # Initialize database if tables don't exist
            initialize_database()
        conn.close()

    def _test_complex_query(self):
        """Helper for complex query test"""
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT username, COUNT(*) as count 
            FROM activity_log 
            WHERE date(timestamp) >= date('now', '-7 days')
            GROUP BY username 
            ORDER BY count DESC 
            LIMIT 10
        """)
        cursor.fetchall()
        conn.close()

    def _test_insert_operation(self):
        """Helper for insert operation test"""
        from datetime import datetime
        test_log = {
            'timestamp': datetime.now().isoformat(),
            'user_id': 'perf_test',
            'username': 'performance_test',
            'action': 'test',
            'module': 'test',
            'details': 'Performance test entry',
            'status': 'success'
        }

        self.log_manager.db.insert_log(test_log)
        
        # Clean up immediately
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM activity_log WHERE username = 'performance_test'")
        conn.commit()
        conn.close()

    def security_analysis_menu_gui(self):
        """GUI version of security analysis menu"""
        security_window = tk.Toplevel(self.root)
        security_window.title(_t("log_management.security_analysis.title"))
        security_window.geometry("800x600")

        ttk.Label(security_window, text=_t("log_management.security_analysis.tools_title"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Analysis buttons
        button_frame = ttk.Frame(security_window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(button_frame, text=_t("log_management.security_analysis.failed_logins"),
                  command=lambda: self.analyze_failed_logins_gui(security_window)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("log_management.security_analysis.unusual_activity"),
                  command=lambda: self.detect_unusual_activity_gui(security_window)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("log_management.security_analysis.admin_audit"),
                  command=lambda: self.audit_admin_actions_gui(security_window)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("log_management.security_analysis.user_behavior"),
                  command=lambda: self.analyze_user_behavior_gui(security_window)).pack(side=tk.LEFT, padx=5)

        # Results display
        results_frame = ttk.LabelFrame(security_window, text=_t("log_management.security_analysis.results"))
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.security_results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD,
                                                              font=("Courier", 10),
                                                              fg="#000000", bg="#FFFFFF")
        self.security_results_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def analyze_failed_logins_gui(self, parent_window):
        """GUI version of failed login analysis"""
        try:
            from collections import defaultdict
            from datetime import datetime, timedelta
            
            # Get failed logins from last 24 hours
            filters = {
                'date_from': (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d'),
                'action': 'login',
                'status': 'failure'
            }
            
            failed_logins = self.log_manager.db.search_logs(filters, limit=1000)
            
            if not failed_logins:
                output = _t("log_management.security_analysis.no_failed_logins")
            else:
                # Analyze by user
                user_failures = defaultdict(int)
                for login in failed_logins:
                    user_failures[login['username']] += 1
                
                output = f"""Failed Login Analysis - Last 24 Hours
{'='*45}

Total failed logins: {len(failed_logins)}
Unique users with failures: {len(user_failures)}

Top users with failed logins:
{'-'*35}
"""
                
                sorted_failures = sorted(user_failures.items(), key=lambda x: x[1], reverse=True)
                for user, count in sorted_failures[:10]:
                    output += f"{user:<25} {count:>8}\n"
                
                # Users with excessive failures
                suspicious_users = [user for user, count in user_failures.items() if count >= 5]
                if suspicious_users:
                    output += f"\n⚠️ Users with 5+ failed logins (potential brute force):\n"
                    for user in suspicious_users:
                        output += f"  {user}: {user_failures[user]} failures\n"
            
            self.security_results_text.delete("1.0", tk.END)
            self.security_results_text.insert("1.0", output)
            
        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.security_analysis.error_failed_logins", error=str(e)))

    def detect_unusual_activity_gui(self, parent_window):
        """GUI version of unusual activity detection"""
        try:
            from collections import defaultdict
            from datetime import datetime, timedelta
            
            # Get activities from last 7 days
            filters = {
                'date_from': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            }
            
            activities = self.log_manager.db.search_logs(filters, limit=5000)
            
            if not activities:
                output = _t("log_management.security_analysis.no_activities")
            else:
                # Analyze by hour
                hour_activity = defaultdict(int)
                unusual_hours = []
                
                for activity in activities:
                    try:
                        hour = datetime.fromisoformat(activity['timestamp']).hour
                        hour_activity[hour] += 1

                        # Flag activities between 2-6 AM as unusual
                        if 2 <= hour <= 6:
                            unusual_hours.append(activity)
                    except (ValueError, KeyError, TypeError):
                        continue
                
                output = "Unusual Activity Detection - Last 7 Days\n"
                output += "="*42 + "\n\n"
                output += "Activity by hour of day:\n"
                output += f"{'Hour':<6} {'Count':<8} {'Chart'}\n"
                output += "-" * 30 + "\n"
                
                for hour in range(24):
                    count = hour_activity.get(hour, 0)
                    bar = "█" * min(count // 10, 50)  # Limit bar length
                    output += f"{hour:02d}:00  {count:<8} {bar}\n"
                
                if unusual_hours:
                    output += f"\n⚠️ Activities during unusual hours (2-6 AM): {len(unusual_hours)}\n"
                    output += "Recent unusual activities:\n"
                    recent_unusual = unusual_hours[-5:]  # Show last 5
                    for activity in recent_unusual:
                        timestamp = activity['timestamp'][:19]
                        user = activity['username']
                        action = activity['action']
                        output += f"  {timestamp} - {user}: {action}\n"
            
            self.security_results_text.delete("1.0", tk.END)
            self.security_results_text.insert("1.0", output)
            
        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.security_analysis.error_unusual_activity", error=str(e)))

    def audit_admin_actions_gui(self, parent_window):
        """GUI version of admin action audit"""
        try:
            from collections import defaultdict
            from datetime import datetime, timedelta
            
            # Get admin actions from last 30 days
            filters = {
                'date_from': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            }

            admin_actions = self.log_manager.db.search_logs(filters, limit=1000)
            
            if not admin_actions:
                output = _t("log_management.security_analysis.no_admin_actions")
            else:
                # Categorize actions
                sensitive_actions = ['delete', 'user_management', 'system_config']
                
                sensitive_count = 0
                regular_count = 0
                action_breakdown = defaultdict(int)
                admin_breakdown = defaultdict(int)
                
                for action in admin_actions:
                    action_type = action['action']
                    admin_user = action['username']
                    
                    action_breakdown[action_type] += 1
                    admin_breakdown[admin_user] += 1
                    
                    if action_type in sensitive_actions:
                        sensitive_count += 1
                    else:
                        regular_count += 1
                
                output = f"""Admin Action Audit - Last 30 Days
{'='*38}

Total admin actions: {len(admin_actions)}
Sensitive actions: {sensitive_count}
Regular actions: {regular_count}

Actions by type:
{'-'*20}
"""
                
                for action_type, count in sorted(action_breakdown.items(), key=lambda x: x[1], reverse=True):
                    sensitivity = "⚠️" if action_type in sensitive_actions else "✅"
                    output += f"{sensitivity} {action_type:<20} {count:>8}\n"
                
                output += f"\nActions by admin:\n{'-'*20}\n"
                for admin, count in sorted(admin_breakdown.items(), key=lambda x: x[1], reverse=True):
                    output += f"{admin:<25} {count:>8}\n"
                
                # Show recent sensitive actions
                recent_sensitive = [a for a in admin_actions if a['action'] in sensitive_actions][-10:]
                if recent_sensitive:
                    output += f"\nRecent sensitive admin actions:\n{'-'*35}\n"
                    for action in recent_sensitive:
                        timestamp = action['timestamp'][:19]
                        user = action['username']
                        action_type = action['action']
                        module = action['module']
                        output += f"{timestamp} - {user}: {action_type} on {module}\n"
            
            self.security_results_text.delete("1.0", tk.END)
            self.security_results_text.insert("1.0", output)
            
        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.security_analysis.error_admin_audit", error=str(e)))

    def analyze_user_behavior_gui(self, parent_window):
        """GUI version of user behavior analysis"""
        try:
            from collections import defaultdict
            from datetime import datetime, timedelta
            
            # Get activities from last 7 days
            filters = {
                'date_from': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            }
            
            activities = self.log_manager.db.search_logs(filters, limit=5000)
            
            if not activities:
                output = _t("log_management.security_analysis.no_activities")
            else:
                # Analyze user patterns
                user_stats = defaultdict(lambda: {
                    'total_actions': 0,
                    'unique_modules': set(),
                    'actions_by_hour': defaultdict(int),
                    'success_rate': 0,
                    'failures': 0
                })
                
                for activity in activities:
                    user = activity['username']
                    stats = user_stats[user]
                    
                    stats['total_actions'] += 1
                    stats['unique_modules'].add(activity['module'])
                    
                    try:
                        hour = datetime.fromisoformat(activity['timestamp']).hour
                        stats['actions_by_hour'][hour] += 1
                    except Exception as e:
                        logger.debug(f"Failed to parse activity timestamp: {e}")
                    
                    if activity['status'] == 'failure':
                        stats['failures'] += 1
                
                # Calculate success rates
                for user, stats in user_stats.items():
                    if stats['total_actions'] > 0:
                        stats['success_rate'] = ((stats['total_actions'] - stats['failures']) / stats['total_actions']) * 100
                    stats['unique_modules'] = len(stats['unique_modules'])
                
                # Sort by activity level
                sorted_users = sorted(user_stats.items(), key=lambda x: x[1]['total_actions'], reverse=True)
                
                output = f"""User Behavior Analysis - Last 7 Days
{'='*40}

Analysis for {len(sorted_users)} users:

{'User':<15} {'Actions':<8} {'Modules':<8} {'Success%':<8} {'Failures':<8}
{'-'*60}
"""
                
                for user, stats in sorted_users[:15]:  # Top 15 users
                    output += f"{user:<15} {stats['total_actions']:<8} {stats['unique_modules']:<8} "
                    output += f"{stats['success_rate']:<7.1f}% {stats['failures']:<8}\n"
                
                # Identify unusual patterns
                output += f"\nUnusual patterns detected:\n{'-'*30}\n"
                
                # Users with low success rates
                low_success_users = [(user, stats) for user, stats in user_stats.items() 
                                    if stats['success_rate'] < 80 and stats['total_actions'] > 10]
                
                if low_success_users:
                    output += "Users with low success rates (<80%):\n"
                    for user, stats in low_success_users:
                        output += f"  {user}: {stats['success_rate']:.1f}% success rate ({stats['failures']} failures)\n"
                
                # Users with very high activity
                high_activity_users = [(user, stats) for user, stats in user_stats.items() 
                                      if stats['total_actions'] > 100]
                
                if high_activity_users:
                    output += "\nUsers with very high activity (>100 actions):\n"
                    for user, stats in high_activity_users:
                        output += f"  {user}: {stats['total_actions']} actions\n"
            
            self.security_results_text.delete("1.0", tk.END)
            self.security_results_text.insert("1.0", output)
            
        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.security_analysis.error_user_behavior", error=str(e)))

    def bulk_export_by_date(self, log_manager, auth):
        """Bulk export by date range"""
        export_window = tk.Toplevel(self.root)
        export_window.title(_t("log_management.bulk_export.title"))
        export_window.geometry("400x300")

        ttk.Label(export_window, text=_t("log_management.bulk_export.title_header"),
                 font=("Arial", 12, "bold")).pack(pady=10)

        # Date range inputs
        date_frame = ttk.Frame(export_window)
        date_frame.pack(pady=10)

        ttk.Label(date_frame, text=_t("log_management.bulk_export.from_date")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        from_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=from_var, width=15).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(date_frame, text=_t("log_management.bulk_export.to_date")).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        to_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=to_var, width=15).grid(row=1, column=1, padx=5, pady=5)

        # Format selection
        format_frame = ttk.Frame(export_window)
        format_frame.pack(pady=10)

        ttk.Label(format_frame, text=_t("log_management.bulk_export.export_format")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        format_var = tk.StringVar(value="json")
        format_combo = ttk.Combobox(format_frame, textvariable=format_var, values=["json", "csv", "excel"])
        format_combo.grid(row=0, column=1, padx=5, pady=5)
        
        def perform_bulk_export():
            try:
                filters = {}
                if from_var.get():
                    filters['date_from'] = from_var.get()
                if to_var.get():
                    filters['date_to'] = to_var.get()
                
                results = log_manager.db.search_logs(filters, limit=10000)
                
                if results:
                    # Get save location
                    filename = filedialog.asksaveasfilename(
                        defaultextension=f".{format_var.get()}",
                        filetypes=[(f"{format_var.get().upper()} files", f"*.{format_var.get()}"), ("All files", "*.*")]
                    )
                    
                    if filename:
                        if format_var.get() == "csv":
                            import pandas as pd
                            df = pd.DataFrame(results)
                            df.to_csv(filename, index=False)
                        elif format_var.get() == "excel":
                            import pandas as pd
                            df = pd.DataFrame(results)
                            df.to_excel(filename, index=False)
                        else:  # JSON
                            import json
                            with open(filename, 'w') as f:
                                json.dump({"results": results, "filters": filters}, f, indent=2)

                        messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.bulk_export.success", count=len(results), path=filename))
                        export_window.destroy()
                else:
                    messagebox.showwarning(_t("log_management.bulk_export.no_data"), _t("log_management.bulk_export.no_logs_in_range"))

            except Exception as e:
                messagebox.showerror(_t("log_management.messages.error"), _t("log_management.bulk_export.error", error=str(e)))

        ttk.Button(export_window, text=_t("log_management.bulk_export.export"), command=perform_bulk_export).pack(pady=20)

    def custom_format_export(self, log_manager, auth):
        """Custom format export dialog"""
        format_window = tk.Toplevel(self.root)
        format_window.title(_t("log_management.custom_format_export.title"))
        format_window.geometry("600x500")

        ttk.Label(format_window, text=_t("log_management.custom_format_export.title"),
                 font=("Arial", 12, "bold")).pack(pady=10)

        # Template selection
        template_frame = ttk.LabelFrame(format_window, text=_t("log_management.custom_format_export.templates"))
        template_frame.pack(fill=tk.X, padx=10, pady=5)
        
        template_var = tk.StringVar(value="detailed_csv")
        templates = [
            ("Detailed CSV", "detailed_csv"),
            ("Summary Report", "summary_report"),
            ("Security Audit", "security_audit"),
            ("Custom XML", "custom_xml")
        ]
        
        for text, value in templates:
            ttk.Radiobutton(template_frame, text=text, variable=template_var, value=value).pack(anchor="w", padx=10, pady=2)
        
        # Custom fields selection
        fields_frame = ttk.LabelFrame(format_window, text="Include Fields")
        fields_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create checkboxes for fields
        field_vars = {}
        fields = ["timestamp", "user_id", "username", "action", "module", "details", "status", "ip_address"]
        
        for i, field in enumerate(fields):
            var = tk.BooleanVar(value=True)
            field_vars[field] = var
            ttk.Checkbutton(fields_frame, text=field.replace("_", " ").title(), variable=var).grid(
                row=i//3, column=i%3, sticky="w", padx=10, pady=2)
        
        # Preview area
        preview_frame = ttk.LabelFrame(format_window, text="Format Preview")
        preview_frame.pack(fill=tk.X, padx=10, pady=5)
        
        preview_text = tk.Text(preview_frame, height=6, width=70)
        preview_text.pack(padx=5, pady=5)
        
        def update_preview():
            template = template_var.get()
            selected_fields = [field for field, var in field_vars.items() if var.get()]
            
            if template == "detailed_csv":
                preview_content = "CSV Format with columns:\n" + ", ".join(selected_fields)
            elif template == "summary_report":
                preview_content = "Summary Report Format:\n- Activity counts by user\n- Time period analysis\n- Status breakdown"
            elif template == "security_audit":
                preview_content = "Security Audit Format:\n- Failed login attempts\n- Admin actions\n- Unusual activity patterns"
            else:
                preview_content = "Custom XML Format:\n<logs>\n  <log>\n    " + "\n    ".join(f"<{field}></{field}>" for field in selected_fields) + "\n  </log>\n</logs>"
            
            preview_text.delete("1.0", tk.END)
            preview_text.insert("1.0", preview_content)
        
        # Update preview when template changes
        template_var.trace("w", lambda *args: update_preview())
        update_preview()
        
        def generate_custom_export():
            try:
                # Get date range
                days = tk.simpledialog.askinteger("Date Range", "Export last how many days?", initialvalue=7)
                if not days:
                    return
                
                from datetime import datetime, timedelta
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                
                filters = {
                    'date_from': start_date.strftime('%Y-%m-%d'),
                    'date_to': end_date.strftime('%Y-%m-%d')
                }
                
                results = log_manager.db.search_logs(filters, limit=10000)
                
                if not results:
                    messagebox.showwarning("No Data", "No logs found for export")
                    return
                
                # Get save location
                filename = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
                )
                
                if filename:
                    selected_fields = [field for field, var in field_vars.items() if var.get()]
                    
                    with open(filename, 'w') as f:
                        if template_var.get() == "custom_xml":
                            f.write("<logs>\n")
                            for log in results:
                                f.write("  <log>\n")
                                for field in selected_fields:
                                    value = log.get(field, '')
                                    f.write(f"    <{field}>{value}</{field}>\n")
                                f.write("  </log>\n")
                            f.write("</logs>\n")
                        else:
                            # Write as formatted text
                            for log in results:
                                for field in selected_fields:
                                    f.write(f"{field}: {log.get(field, '')}\n")
                                f.write("-" * 40 + "\n")
                    
                    messagebox.showinfo("Success", f"Custom export saved to {filename}")
                    format_window.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {str(e)}")
        
        ttk.Button(format_window, text=_t("log_management.custom_format.buttons.export"), command=generate_custom_export).pack(pady=10)

    def view_api_stats(self, log_manager):
        """View API usage statistics - enhanced version"""
        stats_window = tk.Toplevel(self.root)
        stats_window.title(_t("log_management.dialogs.api_stats"))
        stats_window.geometry("700x500")
        
        ttk.Label(stats_window, text=_t("log_management.api_stats.title"), 
                 font=("Arial", 14, "bold")).pack(pady=10)
        
        # API Status frame
        status_frame = ttk.LabelFrame(stats_window, text="API Configuration")
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        api_enabled = log_manager.config.get('api_enabled', False)
        status_text = f"Status: {'Enabled' if api_enabled else 'Disabled'}"
        ttk.Label(status_frame, text=status_text, font=("Arial", 12)).pack(pady=5)
        
        endpoint_text = "API Endpoint: Not available (API removed)"
        ttk.Label(status_frame, text=endpoint_text).pack(pady=2)
        
        key_configured = "Yes" if log_manager.config.get('api_secret_key') else "No"
        ttk.Label(status_frame, text=f"Secret Key Configured: {key_configured}").pack(pady=2)
        
        # Usage statistics frame
        usage_frame = ttk.LabelFrame(stats_window, text="Endpoint Statistics")
        usage_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create stats display
        stats_text = scrolledtext.ScrolledText(usage_frame, wrap=tk.WORD, height=15)
        stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Mock API stats (in real implementation, track API calls)
        api_stats = f"""API Usage Statistics (Last 24h)
{'='*40}

Endpoint Statistics:
/api/health: 0 requests
/api/auth/login: 0 requests  
/api/logs/search: 0 requests
/api/analytics/summary: 0 requests
/api/export/logs: 0 requests

Authentication:
Valid tokens issued: 0
Failed authentication attempts: 0

Performance Metrics:
Average response time: N/A
Error rate: 0%

API Usage Tracking:
- Real-time metrics are collected when API is running
- Metrics include request count, response times, error rates
- Authentication success/failure tracking
- Endpoint usage statistics
- Performance monitoring and alerting

Current API Status: {'Running' if api_enabled else 'Stopped'}
"""
        
        stats_text.insert("1.0", api_stats)
        stats_text.config(state=tk.DISABLED)
        
        # Control buttons
        button_frame = ttk.Frame(stats_window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        if api_enabled:
            ttk.Button(button_frame, text=_t("log_management.api_server.stop"), 
                      command=lambda: self.stop_api_server()).pack(side=tk.LEFT, padx=5)
        else:
            ttk.Button(button_frame, text=_t("log_management.api_server.start"), 
                      command=lambda: self.start_api_server()).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text=_t("log_management.buttons.refresh"), 
                  command=lambda: self.refresh_api_stats(stats_text, log_manager)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("log_management.buttons.close"), command=stats_window.destroy).pack(side=tk.RIGHT, padx=5)

    def refresh_api_stats(self, stats_text, log_manager):
        """Refresh API statistics display with actual data from activity logs"""
        stats_text.config(state=tk.NORMAL)
        stats_text.delete("1.0", tk.END)

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            # Try to get API stats from activity logs
            from university_system.infrastructure.database.db import get_connection

            with get_connection() as conn:
                # Create API tracking table if not exists
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS api_request_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        endpoint TEXT,
                        method TEXT,
                        status_code INTEGER,
                        response_time_ms REAL,
                        user_id INTEGER,
                        ip_address TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Get endpoint statistics
                endpoint_stats = conn.execute("""
                    SELECT endpoint, COUNT(*) as count,
                           AVG(response_time_ms) as avg_time,
                           SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as errors
                    FROM api_request_log
                    WHERE timestamp >= datetime('now', '-24 hours')
                    GROUP BY endpoint
                    ORDER BY count DESC
                    LIMIT 10
                """).fetchall()

                # Get total stats
                total_stats = conn.execute("""
                    SELECT COUNT(*) as total,
                           AVG(response_time_ms) as avg_time,
                           SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as errors,
                           SUM(CASE WHEN status_code >= 200 AND status_code < 300 THEN 1 ELSE 0 END) as success
                    FROM api_request_log
                    WHERE timestamp >= datetime('now', '-24 hours')
                """).fetchone()

                # Get hourly breakdown
                hourly_stats = conn.execute("""
                    SELECT strftime('%H:00', timestamp) as hour, COUNT(*) as count
                    FROM api_request_log
                    WHERE timestamp >= datetime('now', '-24 hours')
                    GROUP BY hour
                    ORDER BY hour
                """).fetchall()

                # Get top users
                user_stats = conn.execute("""
                    SELECT user_id, COUNT(*) as count
                    FROM api_request_log
                    WHERE timestamp >= datetime('now', '-24 hours') AND user_id IS NOT NULL
                    GROUP BY user_id
                    ORDER BY count DESC
                    LIMIT 5
                """).fetchall()

            # Build stats display
            stats = [f"API Usage Statistics (Refreshed: {current_time})", "=" * 60, ""]

            # Summary
            if total_stats and total_stats[0]:
                total, avg_time, errors, success = total_stats
                error_rate = (errors / total * 100) if total > 0 else 0
                stats.append("SUMMARY (Last 24 Hours)")
                stats.append("-" * 40)
                stats.append(f"  Total Requests:    {total or 0:,}")
                stats.append(f"  Successful (2xx):  {success or 0:,}")
                stats.append(f"  Errors (4xx/5xx):  {errors or 0:,}")
                stats.append(f"  Error Rate:        {error_rate:.1f}%")
                stats.append(f"  Avg Response Time: {avg_time or 0:.1f}ms")
            else:
                stats.append("SUMMARY (Last 24 Hours)")
                stats.append("-" * 40)
                stats.append("  No API requests recorded yet")

            stats.append("")
            stats.append("ENDPOINT BREAKDOWN")
            stats.append("-" * 40)

            if endpoint_stats:
                stats.append(f"{'Endpoint':<30} {'Count':>8} {'Avg(ms)':>10} {'Errors':>8}")
                stats.append("-" * 60)
                for row in endpoint_stats:
                    endpoint, count, avg_time, errors = row
                    stats.append(f"{endpoint:<30} {count:>8} {avg_time or 0:>10.1f} {errors or 0:>8}")
            else:
                stats.append("  No endpoint data available")

            stats.append("")
            stats.append("HOURLY TRAFFIC")
            stats.append("-" * 40)

            if hourly_stats:
                for hour, count in hourly_stats:
                    bar = "█" * min(count // 10, 30)
                    stats.append(f"  {hour}: {bar} ({count})")
            else:
                stats.append("  No hourly data available")

            stats.append("")
            stats.append("TOP USERS BY REQUEST COUNT")
            stats.append("-" * 40)

            if user_stats:
                for user_id, count in user_stats:
                    stats.append(f"  User {user_id}: {count} requests")
            else:
                stats.append("  No user data available")

            stats.append("")
            stats.append("Status: API tracking active")

            refreshed_stats = "\n".join(stats)

        except Exception as e:
            refreshed_stats = f"""API Usage Statistics (Refreshed: {current_time})
{'='*60}

Error loading API statistics: {e}

To enable API tracking, ensure the api_request_log table exists
and your API endpoints log requests to it.

Example logging code for Flask:
    @app.after_request
    def log_request(response):
        # Log to api_request_log table
        return response
"""

        stats_text.insert("1.0", refreshed_stats)
        stats_text.config(state=tk.DISABLED)

    def bulk_import_logs_gui(self):
        """GUI version of bulk log import"""
        import_window = tk.Toplevel(self.root)
        import_window.title(_t("log_management.dialogs.bulk_import"))
        import_window.geometry("500x400")
        
        ttk.Label(import_window, text=_t("log_management.bulk_import.title"), 
                 font=("Arial", 14, "bold")).pack(pady=10)
        
        # File selection frame
        file_frame = ttk.LabelFrame(import_window, text="File Selection")
        file_frame.pack(fill=tk.X, padx=10, pady=5)
        
        file_path_var = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=file_path_var, width=50)
        file_entry.pack(side=tk.LEFT, padx=5, pady=10, fill=tk.X, expand=True)
        
        def browse_file():
            filename = filedialog.askopenfilename(
                title="Select log file to import",
                filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if filename:
                file_path_var.set(filename)
        
        ttk.Button(file_frame, text=_t("log_management.buttons.browse"), command=browse_file).pack(side=tk.RIGHT, padx=5, pady=10)
        
        # Import options frame
        options_frame = ttk.LabelFrame(import_window, text="Import Options")
        options_frame.pack(fill=tk.X, padx=10, pady=5)
        
        validate_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Validate data before import", 
                       variable=validate_var).pack(anchor="w", padx=10, pady=5)
        
        backup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Create backup before import", 
                       variable=backup_var).pack(anchor="w", padx=10, pady=5)
        
        # Progress frame
        progress_frame = ttk.LabelFrame(import_window, text="Import Progress")
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        progress_text = scrolledtext.ScrolledText(progress_frame, height=10)
        progress_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        progress_bar.pack(fill=tk.X, padx=5, pady=5)
        
        def perform_import():
            file_path = file_path_var.get()
            if not file_path:
                messagebox.showerror("Error", "Please select a file to import")
                return
            
            if not os.path.exists(file_path):
                messagebox.showerror("Error", "File not found")
                return
            
            try:
                progress_text.insert(tk.END, f"Starting import from {file_path}\n")
                progress_text.see(tk.END)
                
                # Read file
                if file_path.endswith('.json'):
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    logs = data.get('logs', []) if isinstance(data, dict) else data
                else:
                    messagebox.showerror("Error", "Only JSON files are currently supported")
                    return
                
                if not logs:
                    progress_text.insert(tk.END, "No logs found in file\n")
                    return
                
                progress_text.insert(tk.END, f"Found {len(logs)} logs to import\n")
                progress_bar['maximum'] = len(logs)
                
                imported_count = 0
                error_count = 0
                
                for i, log in enumerate(logs):
                    try:
                        if validate_var.get():
                            # Basic validation
                            required_fields = ['timestamp', 'user_id', 'username', 'action', 'module']
                            if not all(field in log for field in required_fields):
                                error_count += 1
                                continue
                        
                        self.log_manager.db.insert_log(log)
                        imported_count += 1
                        
                        if (i + 1) % 100 == 0:
                            progress_text.insert(tk.END, f"Imported {imported_count} logs...\n")
                            progress_text.see(tk.END)
                            progress_bar['value'] = i + 1
                            import_window.update()
                        
                    except Exception as e:
                        error_count += 1
                        if error_count <= 10:  # Only show first 10 errors
                            progress_text.insert(tk.END, f"Error importing log {i+1}: {str(e)}\n")
                
                progress_bar['value'] = len(logs)
                progress_text.insert(tk.END, f"\nImport completed!\n")
                progress_text.insert(tk.END, f"Successfully imported: {imported_count}\n")
                progress_text.insert(tk.END, f"Errors: {error_count}\n")
                
                messagebox.showinfo("Import Complete", 
                                   f"Successfully imported {imported_count}/{len(logs)} logs")
                
            except Exception as e:
                progress_text.insert(tk.END, f"Import failed: {str(e)}\n")
                messagebox.showerror("Import Error", f"Error importing logs: {str(e)}")
        
        # Buttons
        button_frame = ttk.Frame(import_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text=_t("log_management.bulk_import.import"), command=perform_import).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("log_management.buttons.close"), command=import_window.destroy).pack(side=tk.RIGHT, padx=5)

    def bulk_cleanup_data_gui(self):
        """GUI version of bulk data cleanup"""
        cleanup_window = tk.Toplevel(self.root)
        cleanup_window.title(_t("log_management.dialogs.bulk_cleanup"))
        cleanup_window.geometry("500x400")
        
        ttk.Label(cleanup_window, text=_t("log_management.bulk_cleanup.title"), 
                 font=("Arial", 14, "bold")).pack(pady=10)
        
        # Warning
        warning_frame = ttk.Frame(cleanup_window)
        warning_frame.pack(fill=tk.X, padx=10, pady=5)
        
        warning_text = "⚠️ WARNING: This will permanently delete data!\nThis action cannot be undone!"
        ttk.Label(warning_frame, text=warning_text, foreground="red", 
                 font=("Arial", 10, "bold")).pack()
        
        # Cleanup options frame
        options_frame = ttk.LabelFrame(cleanup_window, text="Cleanup Options")
        options_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Date threshold
        date_frame = ttk.Frame(options_frame)
        date_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(date_frame, text=_t("log_management.bulk_cleanup.delete_older_than")).pack(side=tk.LEFT)
        days_var = tk.StringVar(value="90")
        days_spinbox = ttk.Spinbox(date_frame, from_=1, to=365, textvariable=days_var, width=10)
        days_spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Label(date_frame, text=_t("log_management.bulk_cleanup.days")).pack(side=tk.LEFT)
        
        # Status filter
        status_frame = ttk.Frame(options_frame)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        status_var = tk.StringVar(value="all")
        ttk.Label(status_frame, text=_t("log_management.bulk_cleanup.delete_by_status")).pack(side=tk.LEFT)
        status_combo = ttk.Combobox(status_frame, textvariable=status_var, 
                                   values=["all", "success", "failure"], width=15)
        status_combo.pack(side=tk.LEFT, padx=5)
        
        # Preview frame
        preview_frame = ttk.LabelFrame(cleanup_window, text="Cleanup Preview")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        preview_text = scrolledtext.ScrolledText(preview_frame, height=8)
        preview_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        def preview_cleanup():
            try:
                days = int(days_var.get())
                cutoff_date = datetime.now() - timedelta(days=days)
                
                filters = {'date_to': cutoff_date.strftime('%Y-%m-%d')}
                if status_var.get() != "all":
                    filters['status'] = status_var.get()
                
                logs_to_delete = self.log_manager.db.search_logs(filters, limit=50000)
                
                preview_content = f"""Cleanup Preview
================

Date threshold: {cutoff_date.strftime('%Y-%m-%d')}
Status filter: {status_var.get()}

Logs that would be deleted: {len(logs_to_delete):,}

Sample logs to be deleted:
"""
                
                for log in logs_to_delete[:10]:  # Show first 10 as sample
                    timestamp = log.get('timestamp', '')[:19]
                    user = log.get('username', '')
                    action = log.get('action', '')
                    status = log.get('status', '')
                    preview_content += f"  {timestamp} - {user}: {action} ({status})\n"
                
                if len(logs_to_delete) > 10:
                    preview_content += f"  ... and {len(logs_to_delete) - 10:,} more logs\n"
                
                preview_text.delete("1.0", tk.END)
                preview_text.insert("1.0", preview_content)
                
            except Exception as e:
                preview_text.delete("1.0", tk.END)
                preview_text.insert("1.0", f"Error generating preview: {str(e)}")
        
        def perform_cleanup():
            try:
                days = int(days_var.get())
                cutoff_date = datetime.now() - timedelta(days=days)
                
                # Double confirmation
                if not messagebox.askyesno("Confirm Cleanup", 
                                          f"Delete logs older than {days} days?\n"
                                          f"This action cannot be undone!"):
                    return
                
                if not messagebox.askyesno("Final Confirmation", 
                                          "Are you absolutely sure?\n"
                                          "Type 'DELETE' in the next dialog to confirm."):
                    return
                
                confirmation = tk.simpledialog.askstring("Type DELETE", 
                                                        "Type 'DELETE' to confirm:",
                                                        show='*')
                
                if confirmation != "DELETE":
                    messagebox.showinfo("Cancelled", "Cleanup cancelled - confirmation failed")
                    return
                
                # Perform cleanup (for demo, we'll just show what would happen)
                filters = {'date_to': cutoff_date.strftime('%Y-%m-%d')}
                if status_var.get() != "all":
                    filters['status'] = status_var.get()
                
                logs_to_delete = self.log_manager.db.search_logs(filters, limit=50000)
                
                # In real implementation, perform actual deletion here
                # For safety, this is commented out:
                # self.log_manager.retention.cleanup_old_logs()
                
                preview_text.insert(tk.END, f"\n--- CLEANUP SIMULATION ---\n")
                preview_text.insert(tk.END, f"Would delete {len(logs_to_delete):,} logs\n")
                preview_text.insert(tk.END, "Actual deletion not performed for safety\n")
                
                messagebox.showinfo("Cleanup Complete", 
                                   f"Cleanup simulation complete.\n"
                                   f"Would have deleted {len(logs_to_delete):,} logs.")
                
            except Exception as e:
                messagebox.showerror("Error", f"Cleanup failed: {str(e)}")
        
        # Buttons
        button_frame = ttk.Frame(cleanup_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Preview Cleanup", command=preview_cleanup).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Perform Cleanup", command=perform_cleanup).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("log_management.buttons.close"), command=cleanup_window.destroy).pack(side=tk.RIGHT, padx=5)

    def toggle_api_gui(self):
        """GUI version of API toggle"""
        if not self.log_manager:
            messagebox.showerror("Error", "Log manager not available")
            return
        
        current_status = self.log_manager.config.get('api_enabled', False)
        new_status = not current_status
        
        action = "enable" if new_status else "disable"
        if messagebox.askyesno("Confirm", f"Are you sure you want to {action} the API?"):
            self.log_manager.config.set('api_enabled', new_status)
            
            status_text = "enabled" if new_status else "disabled"
            message = f"API has been {status_text}"
            
            if new_status:
                message += "\n\nNote: API has been removed from the system"
            
            messagebox.showinfo("API Status", message)

    def generate_api_key_gui(self):
        """GUI version of API key generation"""
        if not self.log_manager:
            messagebox.showerror("Error", "Log manager not available")
            return
        
        if messagebox.askyesno("Generate API Key", 
                              "Generate a new API key?\n"
                              "This will invalidate the current key."):
            
            import secrets
            new_key = secrets.token_urlsafe(32)
            
            self.log_manager.config.set('api_secret_key', new_key)
            
            # Show key in a dialog
            key_window = tk.Toplevel(self.root)
            key_window.title(_t("log_management.dialogs.api_key_generated"))
            key_window.geometry("600x200")
            
            ttk.Label(key_window, text=_t("log_management.config.api_key_generated"), 
                     font=("Arial", 14, "bold")).pack(pady=10)
            
            ttk.Label(key_window, text=_t("log_management.config.api_key_message"),
                     foreground="red").pack(pady=5)
            
            key_frame = ttk.Frame(key_window)
            key_frame.pack(fill=tk.X, padx=10, pady=10)
            
            key_entry = ttk.Entry(key_frame, width=60)
            key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            key_entry.insert(0, new_key)
            key_entry.config(state='readonly')
            
            def copy_key():
                key_window.clipboard_clear()
                key_window.clipboard_append(new_key)
                messagebox.showinfo("Copied", "API key copied to clipboard")
            
            ttk.Button(key_frame, text="Copy", command=copy_key).pack(side=tk.RIGHT, padx=(5, 0))
            
            ttk.Button(key_window, text=_t("log_management.buttons.close"), command=key_window.destroy).pack(pady=10)

    def show_api_docs_gui(self):
        """GUI version of API documentation"""
        docs_window = tk.Toplevel(self.root)
        docs_window.title(_t("log_management.dialogs.api_docs"))
        docs_window.geometry("900x700")
        
        ttk.Label(docs_window, text=_t("log_management.dialogs.api_docs"), 
                 font=("Arial", 14, "bold")).pack(pady=10)
        
        # Create notebook for different sections
        docs_notebook = ttk.Notebook(docs_window)
        docs_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Overview tab
        overview_frame = ttk.Frame(docs_notebook)
        docs_notebook.add(overview_frame, text="Overview")
        
        overview_text = scrolledtext.ScrolledText(overview_frame, wrap=tk.WORD, font=("Courier", 10))
        overview_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        overview_content = """Log Management API Overview
============================

Note: The API has been removed from this system.
Log management is available through the GUI and CLI interfaces only.
"""
        
        overview_text.insert("1.0", overview_content)
        overview_text.config(state=tk.DISABLED)
        
        # Endpoints tab
        endpoints_frame = ttk.Frame(docs_notebook)
        docs_notebook.add(endpoints_frame, text="Endpoints")
        
        endpoints_text = scrolledtext.ScrolledText(endpoints_frame, wrap=tk.WORD, font=("Courier", 9))
        endpoints_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        endpoints_content = """API Endpoints Reference
========================

Authentication:
POST /api/auth/login
  Body: {"username": "user", "password": "pass"}
  Returns: {"token": "jwt_token", "expires_in": 86400}

Log Operations:
POST /api/logs/search
  Headers: Authorization: Bearer <token>
  Body: {"date_from": "2024-01-01", "user_id": "admin", "limit": 100}
  
GET /api/logs/recent?hours=24&limit=50
  Headers: Authorization: Bearer <token>
  
GET /api/logs/user/{user_id}?days=7&limit=100
  Headers: Authorization: Bearer <token>

Analytics:
GET /api/analytics/summary?days=7
  Headers: Authorization: Bearer <token>
  
GET /api/analytics/user/{user_id}?days=30
  Headers: Authorization: Bearer <token>
  
POST /api/analytics/chart
  Headers: Authorization: Bearer <token>
  Body: {"days": 7, "type": "daily"}

Alerts:
GET /api/alerts?hours=24
  Headers: Authorization: Bearer <token>
  
POST /api/alerts/check
  Headers: Authorization: Bearer <token>

Export:
POST /api/export/logs
  Headers: Authorization: Bearer <token>
  Body: {"filters": {...}, "format": "json|csv|excel"}

System:
GET /api/system/status
  Headers: Authorization: Bearer <token>
  
GET /api/config
  Headers: Authorization: Bearer <token>
  
PUT /api/config
  Headers: Authorization: Bearer <token>
  Body: {"retention_days": 90, "enable_alerts": true}

Health:
GET /api/health
  No authentication required
  Returns: {"status": "healthy", "timestamp": "..."}
"""
        
        endpoints_text.insert("1.0", endpoints_content)
        endpoints_text.config(state=tk.DISABLED)
        
        # Examples tab
        examples_frame = ttk.Frame(docs_notebook)
        docs_notebook.add(examples_frame, text="Examples")
        
        examples_text = scrolledtext.ScrolledText(examples_frame, wrap=tk.WORD, font=("Courier", 9))
        examples_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        examples_content = """API Usage Examples
===================

Note: The API has been removed from this system.
Log management is available through the GUI and CLI interfaces only.
"""
        
        examples_text.insert("1.0", examples_content)
        examples_text.config(state=tk.DISABLED)
        
        ttk.Button(docs_window, text=_t("log_management.buttons.close"), command=docs_window.destroy).pack(pady=10)

    def view_scheduled_tasks_gui(self):
        """GUI version of viewing scheduled tasks"""
        tasks_window = tk.Toplevel(self.root)
        tasks_window.title(_t("log_management.dialogs.scheduled_tasks"))
        tasks_window.geometry("600x400")
        
        ttk.Label(tasks_window, text=_t("log_management.scheduled_tasks.title"), 
                 font=("Arial", 14, "bold")).pack(pady=10)
        
        # Tasks display
        tasks_frame = ttk.LabelFrame(tasks_window, text="Current Scheduled Tasks")
        tasks_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        tasks_text = scrolledtext.ScrolledText(tasks_frame, wrap=tk.WORD, height=15)
        tasks_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Build tasks overview
        tasks_overview = """Scheduled Tasks Status
=======================

System Tasks:
- Daily log archival at 02:00
- Daily log cleanup at 03:00  
- Hourly alert checks

Email Notifications:
"""
        
        if self.log_manager.config.get('alert_email'):
            tasks_overview += f"- Daily email reports to: {self.log_manager.config.get('alert_email')}\n"
        
        if self.log_manager.config.get('weekly_report_email'):
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_index = self.log_manager.config.get('weekly_report_day', 1) - 1
            tasks_overview += f"- Weekly analytics reports to: {self.log_manager.config.get('weekly_report_email')} ({day_names[day_index]})\n"
        
        if self.log_manager.config.get('security_alert_email'):
            threshold = self.log_manager.config.get('failed_login_threshold', 5)
            tasks_overview += f"- Security alerts to: {self.log_manager.config.get('security_alert_email')} (threshold: {threshold})\n"
        
        if not any([self.log_manager.config.get('alert_email'), 
                   self.log_manager.config.get('weekly_report_email'),
                   self.log_manager.config.get('security_alert_email')]):
            tasks_overview += "- No email notifications configured\n"
        
        tasks_overview += f"""
API Status:
- API Server: {'Running' if self.log_manager.config.get('api_enabled') else 'Stopped'}

Real-time Monitoring:
- Status: {'Active' if self.log_manager.monitor.running else 'Inactive'}
- Subscribers: {len(self.log_manager.monitor.subscribers)}

Configuration:
- Log retention: {self.log_manager.config.get('retention_days', 90)} days
- Auto archive: {self.log_manager.config.get('auto_archive_days', 30)} days
- Alerts enabled: {self.log_manager.config.get('enable_alerts', True)}
"""
        
        tasks_text.insert("1.0", tasks_overview)
        tasks_text.config(state=tk.DISABLED)
        
        ttk.Button(tasks_window, text=_t("log_management.buttons.close"), command=tasks_window.destroy).pack(pady=10)

    def setup_security_alerts_gui(self):
        """GUI version of security alerts setup"""
        alerts_window = tk.Toplevel(self.root)
        alerts_window.title(_t("log_management.dialogs.security_alerts_config"))
        alerts_window.geometry("500x400")
        
        ttk.Label(alerts_window, text=_t("log_management.security_alerts_config.title"), 
                 font=("Arial", 14, "bold")).pack(pady=10)
        
        # Email configuration
        email_frame = ttk.LabelFrame(alerts_window, text="Alert Email Settings")
        email_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(email_frame, text=_t("log_management.security_alerts_config.email_address")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        email_var = tk.StringVar(value=self.log_manager.config.get('security_alert_email', ''))
        ttk.Entry(email_frame, textvariable=email_var, width=30).grid(row=0, column=1, padx=5, pady=5)
        
        # Threshold settings
        threshold_frame = ttk.LabelFrame(alerts_window, text="Alert Thresholds")
        threshold_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(threshold_frame, text=_t("log_management.security_alerts_config.failed_login_threshold")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        login_threshold_var = tk.StringVar(value=str(self.log_manager.config.get('failed_login_threshold', 5)))
        ttk.Spinbox(threshold_frame, from_=1, to=50, textvariable=login_threshold_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(threshold_frame, text=_t("log_management.security_alerts_config.rapid_actions_threshold")).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        rapid_threshold_var = tk.StringVar(value=str(self.log_manager.config.get('rapid_actions_threshold', 20)))
        ttk.Spinbox(threshold_frame, from_=5, to=100, textvariable=rapid_threshold_var, width=10).grid(row=1, column=1, padx=5, pady=5)
        
        # Alert types
        types_frame = ttk.LabelFrame(alerts_window, text="Alert Types")
        types_frame.pack(fill=tk.X, padx=10, pady=5)
        
        failed_logins_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(types_frame, text="Failed Login Attempts", variable=failed_logins_var).pack(anchor="w", padx=10, pady=2)
        
        unusual_hours_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(types_frame, text="Unusual Activity Hours", variable=unusual_hours_var).pack(anchor="w", padx=10, pady=2)
        
        rapid_actions_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(types_frame, text="Rapid Fire Actions", variable=rapid_actions_var).pack(anchor="w", padx=10, pady=2)
        
        admin_actions_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(types_frame, text="Admin Actions", variable=admin_actions_var).pack(anchor="w", padx=10, pady=2)
        
        def save_security_settings():
            try:
                self.log_manager.config.set('security_alert_email', email_var.get())
                self.log_manager.config.set('failed_login_threshold', int(login_threshold_var.get()))
                self.log_manager.config.set('rapid_actions_threshold', int(rapid_threshold_var.get()))
                self.log_manager.config.set('alert_failed_logins', failed_logins_var.get())
                self.log_manager.config.set('alert_unusual_hours', unusual_hours_var.get())
                self.log_manager.config.set('alert_rapid_actions', rapid_actions_var.get())
                self.log_manager.config.set('alert_admin_actions', admin_actions_var.get())
                
                messagebox.showinfo("Success", "Security alert settings saved successfully!")
                
            except ValueError:
                messagebox.showerror("Error", "Please enter valid threshold values")
            except Exception as e:
                messagebox.showerror("Error", f"Error saving settings: {str(e)}")
        
        def test_security_alerts():
            try:
                alerts = self.log_manager.alerts.run_alert_checks()
                if alerts:
                    messagebox.showinfo("Test Results", f"Found {len(alerts)} alerts")
                else:
                    messagebox.showinfo("Test Results", "No alerts found")
            except Exception as e:
                messagebox.showerror("Error", f"Error testing alerts: {str(e)}")
        
        # Buttons
        button_frame = ttk.Frame(alerts_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Save Settings", command=save_security_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Test Alerts", command=test_security_alerts).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("log_management.buttons.close"), command=alerts_window.destroy).pack(side=tk.RIGHT, padx=5)

    def rebuild_indexes_gui(self):
        """GUI version of rebuild indexes"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        if not messagebox.askyesno(_t("log_management.messages.confirm"), _t("log_management.maintenance.confirm_rebuild_indexes")):
            return

        self.update_status(_t("log_management.messages.rebuilding_indexes"))
        
        try:
            from university_system.infrastructure.database.db import sqlite3
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            output = "Rebuilding Database Indexes\n"
            output += "="*30 + "\n\n"
            
            # Drop and recreate indexes
            indexes = [
                ("idx_logs_timestamp", "DROP INDEX IF EXISTS idx_logs_timestamp"),
                ("idx_logs_user_id", "DROP INDEX IF EXISTS idx_logs_user_id"), 
                ("idx_logs_action", "DROP INDEX IF EXISTS idx_logs_action"),
                ("idx_logs_module", "DROP INDEX IF EXISTS idx_logs_module"),
                ("idx_logs_timestamp", "CREATE INDEX idx_logs_timestamp ON logs(timestamp)"),
                ("idx_logs_user_id", "CREATE INDEX idx_logs_user_id ON logs(user_id)"),
                ("idx_logs_action", "CREATE INDEX idx_logs_action ON logs(action)"),
                ("idx_logs_module", "CREATE INDEX idx_logs_module ON logs(module)")
            ]
            
            for index_name, index_sql in indexes:
                cursor.execute(index_sql)
                if "DROP" in index_sql:
                    output += f"Dropped index: {index_name}\n"
                else:
                    output += f"Created index: {index_name}\n"
            
            conn.commit()
            conn.close()
            
            output += "\nIndexes rebuilt successfully!"
            
            self.maintenance_text.delete("1.0", tk.END)
            self.maintenance_text.insert("1.0", output)

            self.update_status(_t("log_management.messages.index_rebuild_completed"))
            messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.maintenance.indexes_rebuilt"))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.rebuild_index", error=str(e)))
            self.update_status(_t("log_management.messages.index_rebuild_failed"))

    def setup_weekly_report_gui(self):
        """GUI version of weekly report setup"""
        weekly_window = tk.Toplevel(self.root)
        weekly_window.title(_t("log_management.dialogs.weekly_report_setup"))
        weekly_window.geometry("400x300")
        
        ttk.Label(weekly_window, text=_t("log_management.weekly_report.title"), 
                 font=("Arial", 12, "bold")).pack(pady=10)
        
        # Email settings
        email_frame = ttk.LabelFrame(weekly_window, text="Email Configuration")
        email_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(email_frame, text=_t("log_management.security_alerts_config.email_address")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        email_var = tk.StringVar(value=self.log_manager.config.get('weekly_report_email', ''))
        ttk.Entry(email_frame, textvariable=email_var, width=30).grid(row=0, column=1, padx=5, pady=5)
        
        # Schedule settings
        schedule_frame = ttk.LabelFrame(weekly_window, text="Schedule Configuration")
        schedule_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(schedule_frame, text=_t("log_management.weekly_report.day_of_week")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        day_var = tk.StringVar(value="Monday")
        day_combo = ttk.Combobox(schedule_frame, textvariable=day_var, 
                                values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        day_combo.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(schedule_frame, text=_t("log_management.weekly_report.time")).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        time_var = tk.StringVar(value="09:00")
        ttk.Entry(schedule_frame, textvariable=time_var, width=10).grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        # Report content
        content_frame = ttk.LabelFrame(weekly_window, text="Report Content")
        content_frame.pack(fill=tk.X, padx=10, pady=5)
        
        include_summary_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(content_frame, text="Activity Summary", variable=include_summary_var).pack(anchor="w", padx=10, pady=2)
        
        include_charts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(content_frame, text="Activity Charts", variable=include_charts_var).pack(anchor="w", padx=10, pady=2)
        
        include_alerts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(content_frame, text="Security Alerts", variable=include_alerts_var).pack(anchor="w", padx=10, pady=2)
        
        def save_weekly_settings():
            try:
                day_map = {"Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4, 
                          "Friday": 5, "Saturday": 6, "Sunday": 7}
                
                self.log_manager.config.set('weekly_report_email', email_var.get())
                self.log_manager.config.set('weekly_report_day', day_map[day_var.get()])
                self.log_manager.config.set('weekly_report_time', time_var.get())
                self.log_manager.config.set('weekly_include_summary', include_summary_var.get())
                self.log_manager.config.set('weekly_include_charts', include_charts_var.get())
                self.log_manager.config.set('weekly_include_alerts', include_alerts_var.get())
                
                messagebox.showinfo("Success", f"Weekly reports configured!\nReports will be sent every {day_var.get()} at {time_var.get()}")
                weekly_window.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Error saving settings: {str(e)}")
        
        # Buttons
        button_frame = ttk.Frame(weekly_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Save Settings", command=save_weekly_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=weekly_window.destroy).pack(side=tk.RIGHT, padx=5)

    def setup_daily_email_report_gui(self):
        """GUI version of daily email report setup"""
        daily_window = tk.Toplevel(self.root)
        daily_window.title(_t("log_management.dialogs.daily_report_setup"))
        daily_window.geometry("400x250")
        
        ttk.Label(daily_window, text=_t("log_management.daily_report.title"), 
                 font=("Arial", 12, "bold")).pack(pady=10)
        
        # Email settings
        email_frame = ttk.LabelFrame(daily_window, text="Email Configuration")
        email_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(email_frame, text=_t("log_management.security_alerts_config.email_address")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        email_var = tk.StringVar(value=self.log_manager.config.get('alert_email', ''))
        ttk.Entry(email_frame, textvariable=email_var, width=30).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(email_frame, text=_t("log_management.daily_report.send_time")).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        time_var = tk.StringVar(value="08:00")
        ttk.Entry(email_frame, textvariable=time_var, width=10).grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        # SMTP settings
        smtp_frame = ttk.LabelFrame(daily_window, text="SMTP Configuration")
        smtp_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(smtp_frame, text=_t("log_management.daily_report.smtp_server")).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        smtp_server_var = tk.StringVar(value=self.log_manager.config.get('smtp_server', ''))
        ttk.Entry(smtp_frame, textvariable=smtp_server_var, width=25).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(smtp_frame, text=_t("log_management.daily_report.smtp_port")).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        smtp_port_var = tk.StringVar(value=str(self.log_manager.config.get('smtp_port', 587)))
        ttk.Entry(smtp_frame, textvariable=smtp_port_var, width=10).grid(row=1, column=1, sticky="w", padx=5, pady=2)
        
        def save_daily_settings():
            try:
                self.log_manager.config.set('alert_email', email_var.get())
                self.log_manager.config.set('daily_report_time', time_var.get())
                self.log_manager.config.set('smtp_server', smtp_server_var.get())
                self.log_manager.config.set('smtp_port', int(smtp_port_var.get()))
                
                messagebox.showinfo("Success", f"Daily email reports configured!\nReports will be sent at {time_var.get()} daily")
                daily_window.destroy()
                
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid port number")
            except Exception as e:
                messagebox.showerror("Error", f"Error saving settings: {str(e)}")
        
        # Buttons
        button_frame = ttk.Frame(daily_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Save Settings", command=save_daily_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=daily_window.destroy).pack(side=tk.RIGHT, padx=5)

    def send_test_email(self):
        """Send test email to verify SMTP configuration"""
        try:
            from university_system.infrastructure.email.smtp import send_email_via_smtp
            from datetime import datetime

            alert_email = self.log_manager.config.get('alert_email')

            if not alert_email:
                messagebox.showerror("Configuration Error", "Alert email not configured")
                return

            body = "This is a test email from Log Management System"
            subject = "Log Management System - Test Email"

            current_time = datetime.now().isoformat()
            success = send_email_via_smtp(
                recipient_email=alert_email,
                subject=subject,
                body=body,
                cc=None,
                bcc=None,
                attachments=None,
                current_time=current_time
            )

            if success:
                messagebox.showinfo("Success", f"Test email sent to {alert_email}")
            else:
                messagebox.showerror("Email Error", "Failed to send test email")

        except Exception as e:
            messagebox.showerror("Email Error", f"Failed to send test email: {str(e)}")

    def email_report_dialog(self):
        """Dialog for sending email reports"""
        email_window = tk.Toplevel(self.root)
        email_window.title(_t("log_management.dialogs.email_report"))
        email_window.geometry("400x300")
        
        ttk.Label(email_window, text=_t("log_management.email_report.title"), 
                 font=("Arial", 12, "bold")).pack(pady=10)
        
        # Report type selection
        type_frame = ttk.Frame(email_window)
        type_frame.pack(pady=10)
        
        ttk.Label(type_frame, text=_t("log_management.email_report.report_type")).pack(anchor="w")
        report_type = tk.StringVar(value="daily")
        ttk.Radiobutton(type_frame, text="Daily Summary", 
                       variable=report_type, value="daily").pack(anchor="w")
        ttk.Radiobutton(type_frame, text="Weekly Analytics", 
                       variable=report_type, value="weekly").pack(anchor="w")
        ttk.Radiobutton(type_frame, text="Security Alert", 
                       variable=report_type, value="security").pack(anchor="w")
        
        # Email address - get admin email from database
        email_frame = ttk.Frame(email_window)
        email_frame.pack(pady=10, fill=tk.X, padx=20)

        ttk.Label(email_frame, text=_t("log_management.security_alerts_config.email_address")).pack(anchor="w")

        # Get admin email from database
        admin_email = self.log_manager.config.get('alert_email', '')
        try:
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("""
                    SELECT email FROM users
                    WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                    LIMIT 1
                """)
                admin_row = cursor.fetchone()
                if admin_row and admin_row[0]:
                    admin_email = admin_row[0]
        except Exception:
            pass

        email_var = tk.StringVar(value=admin_email)
        ttk.Entry(email_frame, textvariable=email_var).pack(fill=tk.X)

        def send_report():
            try:
                from university_system.infrastructure.email.email_service import send_email

                email_addr = email_var.get().strip()
                if not email_addr:
                    messagebox.showerror("Error", "Email address required")
                    return

                # Generate report based on type
                report_content = self.generate_email_report_content(report_type.get())

                # Build email subject and body
                report_type_name = report_type.get().replace('_', ' ').title()
                subject = f"Log Management {report_type_name} Report - {datetime.now().strftime('%Y-%m-%d')}"

                body = f"""Log Management Report

Report Type: {report_type_name}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'=' * 60}

{report_content}

{'=' * 60}

This report was automatically generated by the Log Management System.
"""

                # Send the email
                result = send_email(
                    recipient_email=email_addr,
                    subject=subject,
                    body=body
                )

                if result:
                    messagebox.showinfo("Success", f"Report sent successfully to {email_addr}")
                else:
                    messagebox.showinfo("Queued", f"Report queued for delivery to {email_addr}")
                email_window.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to send report: {str(e)}")
        
        button_frame = ttk.Frame(email_window)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Send Report", command=send_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Test Email", command=self.send_test_email).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=email_window.destroy).pack(side=tk.LEFT, padx=5)

    def generate_email_report_content(self, report_type):
        """Generate content for email reports"""
        if report_type == "daily":
            summary = self.log_manager.analytics.generate_activity_summary(1)
            return f"Daily Summary: {summary.get('total_activities', 0)} activities today"
        elif report_type == "weekly":
            summary = self.log_manager.analytics.generate_activity_summary(7)
            return f"Weekly Summary: {summary.get('total_activities', 0)} activities this week"
        else:
            return "Security Alert: No recent alerts found"

    def open_student_system(self):
        """Open student management system in new window"""
        if not STUDENT_SYSTEM_AVAILABLE:
            messagebox.showerror("Error", "Student management system not available")
            return
        
        try:
            # Create new window for student system
            student_window = tk.Toplevel(self.root)
            student_window.title(_t("log_management.dialogs.student_system"))
            student_window.geometry("1200x800")
            
            # Initialize student system (you'll need to adapt this based on student system's auth)
            from university_system.infrastructure.auth import UserAuth
            from university_system.infrastructure.shared_context import get_auth
            student_auth = get_auth()
            if student_auth is None:
                student_auth = UserAuth()
            
            # Create student GUI instance
            student_app = UnifiedManagementGUI(student_auth)
            student_app.root = student_window
            student_app.setup_main_layout()
            
            if not student_auth.current_user:
                student_app.show_login_screen()
            else:
                student_app.show_main_interface()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open student system: {str(e)}")

    def view_api_stats(self, log_manager):
        """View API usage statistics"""
        stats_window = tk.Toplevel(self.root)
        stats_window.title(_t("log_management.dialogs.api_stats"))
        stats_window.geometry("600x400")
        
        ttk.Label(stats_window, text=_t("log_management.api_stats.title"), 
                 font=("Arial", 14, "bold")).pack(pady=10)
        
        # Create stats display
        stats_text = scrolledtext.ScrolledText(stats_window, wrap=tk.WORD)
        stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # API has been removed from the system
        api_stats = """API Configuration Status
    ========================================

    Note: The API has been removed from this system.
    Log management is available through the GUI and CLI interfaces only.
    """
        
        stats_text.insert("1.0", api_stats)
        stats_text.config(state=tk.DISABLED)
        
        ttk.Button(stats_window, text=_t("log_management.buttons.close"), command=stats_window.destroy).pack(pady=10)

    def schedule_export(log_manager, auth):
        """Schedule automatic exports"""
        schedule_window = tk.Toplevel(self.root)
        schedule_window.title(_t("log_management.dialogs.schedule_export"))
        schedule_window.geometry("500x450")

        ttk.Label(schedule_window, text=_t("log_management.schedule_export.title"),
                 font=("Arial", 12, "bold")).pack(pady=10)

        # Form frame
        form_frame = ttk.Frame(schedule_window, padding="20")
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Frequency selection
        ttk.Label(form_frame, text=_t("log_management.schedule_export.frequency")).grid(row=0, column=0, sticky="w", pady=5)
        frequency_var = tk.StringVar(value="daily")
        frequency_combo = ttk.Combobox(form_frame, textvariable=frequency_var,
                                       values=["hourly", "daily", "weekly", "monthly"], state="readonly")
        frequency_combo.grid(row=0, column=1, sticky="ew", pady=5, padx=(10,0))

        # Time selection
        ttk.Label(form_frame, text=_t("log_management.schedule_export.time")).grid(row=1, column=0, sticky="w", pady=5)
        time_frame = ttk.Frame(form_frame)
        time_frame.grid(row=1, column=1, sticky="ew", pady=5, padx=(10,0))

        hour_var = tk.StringVar(value="00")
        minute_var = tk.StringVar(value="00")
        ttk.Spinbox(time_frame, from_=0, to=23, width=5, textvariable=hour_var, format="%02.0f").pack(side=tk.LEFT)
        ttk.Label(time_frame, text=":").pack(side=tk.LEFT, padx=2)
        ttk.Spinbox(time_frame, from_=0, to=59, width=5, textvariable=minute_var, format="%02.0f").pack(side=tk.LEFT)

        # Export format
        ttk.Label(form_frame, text="Export Format:").grid(row=2, column=0, sticky="w", pady=5)
        format_var = tk.StringVar(value="json")
        format_combo = ttk.Combobox(form_frame, textvariable=format_var,
                                    values=["json", "csv", "txt"], state="readonly")
        format_combo.grid(row=2, column=1, sticky="ew", pady=5, padx=(10,0))

        # Export directory
        ttk.Label(form_frame, text="Export Directory:").grid(row=3, column=0, sticky="w", pady=5)
        dir_var = tk.StringVar(value=os.path.join(os.getcwd(), "exports"))
        dir_frame = ttk.Frame(form_frame)
        dir_frame.grid(row=3, column=1, sticky="ew", pady=5, padx=(10,0))
        ttk.Entry(dir_frame, textvariable=dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(dir_frame, text=_t("log_management.buttons.browse"), command=lambda: dir_var.set(
            filedialog.askdirectory(initialdir=dir_var.get()))).pack(side=tk.LEFT, padx=(5,0))

        # Filters
        ttk.Label(form_frame, text="Level Filter:").grid(row=4, column=0, sticky="w", pady=5)
        level_var = tk.StringVar(value="all")
        level_combo = ttk.Combobox(form_frame, textvariable=level_var,
                                   values=["all", "info", "warning", "error", "critical"], state="readonly")
        level_combo.grid(row=4, column=1, sticky="ew", pady=5, padx=(10,0))

        # Enable/disable
        enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Enable scheduled export",
                       variable=enabled_var).grid(row=5, column=0, columnspan=2, pady=15)

        form_frame.columnconfigure(1, weight=1)

        def save_schedule():
            try:
                schedule_config = {
                    'enabled': enabled_var.get(),
                    'frequency': frequency_var.get(),
                    'time': f"{hour_var.get()}:{minute_var.get()}",
                    'format': format_var.get(),
                    'directory': dir_var.get(),
                    'level_filter': level_var.get()
                }

                # Create export directory if it doesn't exist
                os.makedirs(dir_var.get(), exist_ok=True)

                # Save configuration
                config_file = os.path.join(os.getcwd(), "scheduled_export_config.json")
                with open(config_file, 'w') as f:
                    json.dump(schedule_config, f, indent=2)

                messagebox.showinfo("Success",
                    f"Export scheduled {frequency_var.get()} at {hour_var.get()}:{minute_var.get()}\n" +
                    f"Exports will be saved to: {dir_var.get()}")
                schedule_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to schedule export: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(schedule_window)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Save Schedule", command=save_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=schedule_window.destroy).pack(side=tk.LEFT, padx=5)

    def custom_format_export(log_manager, auth):
        """Custom format export"""
        format_window = tk.Toplevel(self.root)
        format_window.title(_t("log_management.dialogs.custom_format_export"))
        format_window.geometry("700x600")

        ttk.Label(format_window, text="Custom Format Export",
                 font=("Arial", 12, "bold")).pack(pady=10)

        # Create notebook for different formats
        notebook = ttk.Notebook(format_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # XML Export Tab
        xml_frame = ttk.Frame(notebook, padding="10")
        notebook.add(xml_frame, text="XML Export")

        ttk.Label(xml_frame, text="Export logs in XML format", font=("Arial", 10, "bold")).pack(anchor="w", pady=5)

        xml_options_frame = ttk.LabelFrame(xml_frame, text="XML Options", padding="10")
        xml_options_frame.pack(fill=tk.X, pady=10)

        xml_include_attrs = tk.BooleanVar(value=True)
        xml_pretty_print = tk.BooleanVar(value=True)
        ttk.Checkbutton(xml_options_frame, text="Include attributes", variable=xml_include_attrs).pack(anchor="w")
        ttk.Checkbutton(xml_options_frame, text="Pretty print (formatted)", variable=xml_pretty_print).pack(anchor="w")

        def export_xml():
            try:
                logs = log_manager.db.search_logs({}, limit=1000)
                filename = filedialog.asksaveasfilename(
                    defaultextension=".xml",
                    filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
                )
                if filename:
                    with open(filename, 'w') as f:
                        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                        f.write('<logs>\n')
                        for log in logs:
                            f.write('  <log>\n')
                            for key, value in log.items():
                                f.write(f'    <{key}>{value}</{key}>\n')
                            f.write('  </log>\n')
                        f.write('</logs>\n')
                    messagebox.showinfo("Success", f"Exported {len(logs)} logs to XML")
            except Exception as e:
                messagebox.showerror("Error", f"XML export failed: {str(e)}")

        ttk.Button(xml_frame, text="Export to XML", command=export_xml).pack(pady=10)

        # Custom CSV Tab
        csv_frame = ttk.Frame(notebook, padding="10")
        notebook.add(csv_frame, text="Custom CSV")

        ttk.Label(csv_frame, text="Select columns to include in CSV export",
                 font=("Arial", 10, "bold")).pack(anchor="w", pady=5)

        # Column selection
        columns_frame = ttk.LabelFrame(csv_frame, text="Columns", padding="10")
        columns_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        column_vars = {}
        default_columns = ['timestamp', 'user_id', 'username', 'action',
                          'module', 'details', 'ip_address', 'status']

        for i, col in enumerate(default_columns):
            var = tk.BooleanVar(value=True)
            column_vars[col] = var
            ttk.Checkbutton(columns_frame, text=col.replace('_', ' ').title(),
                          variable=var).grid(row=i//3, column=i%3, sticky="w", padx=5, pady=2)

        csv_delimiter_var = tk.StringVar(value=",")
        delimiter_frame = ttk.Frame(csv_frame)
        delimiter_frame.pack(fill=tk.X, pady=5)
        ttk.Label(delimiter_frame, text="Delimiter:").pack(side=tk.LEFT)
        ttk.Entry(delimiter_frame, textvariable=csv_delimiter_var, width=5).pack(side=tk.LEFT, padx=5)

        def export_custom_csv():
            try:
                selected_cols = [col for col, var in column_vars.items() if var.get()]
                if not selected_cols:
                    messagebox.showwarning("Warning", "Please select at least one column")
                    return

                logs = log_manager.db.search_logs({}, limit=1000)
                filename = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
                )
                if filename:
                    delimiter = csv_delimiter_var.get() or ","
                    with open(filename, 'w', newline='') as f:
                        import csv
                        writer = csv.DictWriter(f, fieldnames=selected_cols, delimiter=delimiter,
                                              extrasaction='ignore')
                        writer.writeheader()
                        writer.writerows(logs)
                    messagebox.showinfo("Success", f"Exported {len(logs)} logs to CSV")
            except Exception as e:
                messagebox.showerror("Error", f"CSV export failed: {str(e)}")

        ttk.Button(csv_frame, text="Export to CSV", command=export_custom_csv).pack(pady=10)

        # Formatted Report Tab
        report_frame = ttk.Frame(notebook, padding="10")
        notebook.add(report_frame, text="Formatted Report")

        ttk.Label(report_frame, text="Generate a formatted text report",
                 font=("Arial", 10, "bold")).pack(anchor="w", pady=5)

        report_options_frame = ttk.LabelFrame(report_frame, text="Report Options", padding="10")
        report_options_frame.pack(fill=tk.X, pady=10)

        report_include_summary = tk.BooleanVar(value=True)
        report_group_by_user = tk.BooleanVar(value=False)
        report_group_by_module = tk.BooleanVar(value=False)

        ttk.Checkbutton(report_options_frame, text="Include summary statistics",
                       variable=report_include_summary).pack(anchor="w")
        ttk.Checkbutton(report_options_frame, text="Group by user",
                       variable=report_group_by_user).pack(anchor="w")
        ttk.Checkbutton(report_options_frame, text="Group by module",
                       variable=report_group_by_module).pack(anchor="w")

        def export_formatted_report():
            try:
                logs = log_manager.db.search_logs({}, limit=1000)
                filename = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
                )
                if filename:
                    with open(filename, 'w') as f:
                        f.write("="*80 + "\n")
                        f.write("ACTIVITY LOG REPORT\n")
                        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write("="*80 + "\n\n")

                        if report_include_summary.get():
                            f.write(f"Total Records: {len(logs)}\n")
                            f.write(f"Date Range: {logs[0].get('timestamp', 'N/A')} to {logs[-1].get('timestamp', 'N/A')}\n\n")

                        f.write("-"*80 + "\n")
                        f.write("LOG ENTRIES\n")
                        f.write("-"*80 + "\n\n")

                        for log in logs:
                            f.write(f"Timestamp: {log.get('timestamp', 'N/A')}\n")
                            f.write(f"User: {log.get('username', 'N/A')} (ID: {log.get('user_id', 'N/A')})\n")
                            f.write(f"Action: {log.get('action', 'N/A')}\n")
                            f.write(f"Module: {log.get('module', 'N/A')}\n")
                            f.write(f"Details: {log.get('details', 'N/A')}\n")
                            f.write("-"*80 + "\n")

                    messagebox.showinfo("Success", f"Generated formatted report with {len(logs)} entries")
            except Exception as e:
                messagebox.showerror("Error", f"Report generation failed: {str(e)}")

        ttk.Button(report_frame, text="Generate Report", command=export_formatted_report).pack(pady=10)

        # Close button
        ttk.Button(format_window, text=_t("log_management.buttons.close"), command=format_window.destroy).pack(pady=10)

    def bulk_export_by_date(log_manager, auth):
        """Bulk export by date range"""
        export_window = tk.Toplevel(self.root)
        export_window.title(_t("log_management.dialogs.bulk_date_export"))
        export_window.geometry("400x250")
        
        ttk.Label(export_window, text="Bulk Export by Date Range", 
                 font=("Arial", 12, "bold")).pack(pady=10)
        
        # Date range inputs
        date_frame = ttk.Frame(export_window)
        date_frame.pack(pady=10)
        
        ttk.Label(date_frame, text="From Date:").grid(row=0, column=0, padx=5)
        from_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=from_var).grid(row=0, column=1, padx=5)
        
        ttk.Label(date_frame, text="To Date:").grid(row=1, column=0, padx=5)
        to_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=to_var).grid(row=1, column=1, padx=5)
        
        def perform_bulk_export():
            try:
                filters = {}
                if from_var.get():
                    filters['date_from'] = from_var.get()
                if to_var.get():
                    filters['date_to'] = to_var.get()
                
                results = log_manager.db.search_logs(filters, limit=10000)
                
                if results:
                    # Save to file
                    filename = filedialog.asksaveasfilename(
                        defaultextension=".json",
                        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
                    )
                    
                    if filename:
                        with open(filename, 'w') as f:
                            json.dump({"results": results, "filters": filters}, f, indent=2)
                        messagebox.showinfo("Success", f"Exported {len(results)} logs to {filename}")
                        export_window.destroy()
                else:
                    messagebox.showwarning("No Data", "No logs found for the specified date range")
                    
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {str(e)}")
        
        ttk.Button(export_window, text="Export", command=perform_bulk_export).pack(pady=20)

    def sync_student_data(self):
        """Sync data between student system and log system"""
        try:
            if not STUDENT_SYSTEM_AVAILABLE:
                messagebox.showerror("Error", "Student management system not available")
                return
            
            # Get student data
            conn = get_student_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('SELECT student_id, email_address, first_name, last_name FROM students')
                students = cursor.fetchall()
                conn.close()
                
                # Log the sync operation
                if self.log_manager:
                    sync_log = {
                        'timestamp': datetime.now().isoformat(),
                        'user_id': 'system',
                        'username': 'log_system',
                        'action': 'sync',
                        'module': 'student_integration',
                        'details': f'Synced {len(students)} student records',
                        'status': 'success'
                    }
                    self.log_manager.db.insert_log(sync_log)
                
                messagebox.showinfo("Success", f"Synced {len(students)} student records")
                self.load_student_stats()
                
        except Exception as e:
            messagebox.showerror("Error", f"Sync failed: {str(e)}")

    def load_student_stats(self):
        """Load student system statistics"""
        try:
            if not STUDENT_SYSTEM_AVAILABLE:
                self.student_stats_text.delete("1.0", tk.END)
                self.student_stats_text.insert("1.0", "Student management system not available")
                return
                
            conn = get_student_db_connection()
            if not conn:  # Check if connection is None
                self.student_stats_text.delete("1.0", tk.END)
                self.student_stats_text.insert("1.0", "Unable to connect to student database")
                return
                
            cursor = conn.cursor()
            
            # Get basic stats with proper error handling
            try:
                cursor.execute('SELECT COUNT(*) FROM students')
                result = cursor.fetchone()
                total_students = result[0] if result else 0
            except Exception:
                total_students = 0
            
            try:
                cursor.execute('SELECT COUNT(*) FROM students WHERE course = "CS"')
                result = cursor.fetchone()
                cs_students = result[0] if result else 0
            except Exception:
                cs_students = 0
            
            try:
                cursor.execute('SELECT COUNT(*) FROM students WHERE course = "DS"')
                result = cursor.fetchone()
                ds_students = result[0] if result else 0
            except Exception:
                ds_students = 0
            
            conn.close()
            
            stats_text = f"""Student System Integration Status
    {'='*40}

    Connection Status: Active
    Total Students: {total_students}
    CS Students: {cs_students}
    DS Students: {ds_students}

    Recent Student Activities:
    {'='*40}
    """
            
            # Get recent student-related logs with error handling
            if self.log_manager:
                try:
                    filters = {
                        'module': 'student_management',
                        'date_from': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                    }
                    recent_logs = self.log_manager.db.search_logs(filters, limit=10)
                    
                    if recent_logs:
                        for log in recent_logs:
                            timestamp = log.get('timestamp', '')[:16]
                            action = log.get('action', '')
                            user = log.get('username', '')
                            stats_text += f"{timestamp} - {user}: {action}\n"
                    else:
                        stats_text += "No recent student activities found\n"
                except Exception as e:
                    stats_text += f"Error loading recent activities: {str(e)}\n"
            
            self.student_stats_text.delete("1.0", tk.END)
            self.student_stats_text.insert("1.0", stats_text)
            
        except Exception as e:
            error_text = f"Error loading student stats: {str(e)}"
            if hasattr(self, 'student_stats_text'):
                self.student_stats_text.delete("1.0", tk.END)
                self.student_stats_text.insert("1.0", error_text)
            else:
                print(error_text)

    def view_student_logs(self):
        """View logs related to student activities"""
        if not self.log_manager:
            messagebox.showerror("Error", "Log manager not available")
            return
        
        # Create filter for student-related activities
        student_filters = {
            'module': 'student_management',
            'date_from': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        }
        
        try:
            results = self.log_manager.db.search_logs(student_filters, limit=500)
            
            # Create new window to display results
            log_window = tk.Toplevel(self.root)
            log_window.title(_t("log_management.dialogs.student_logs"))
            log_window.geometry("800x600")
            
            # Create treeview for results
            columns = ("Time", "User", "Action", "Details", "Status")
            tree = ttk.Treeview(log_window, columns=columns, show="headings")
            
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=120)
            
            # Populate with results
            for log in results:
                timestamp = log.get('timestamp', '')[:19]
                user = log.get('username', '')
                action = log.get('action', '')
                details = log.get('details', '')[:50] + "..." if len(log.get('details', '')) > 50 else log.get('details', '')
                status = log.get('status', '')
                
                tree.insert("", "end", values=(timestamp, user, action, details, status))
            
            tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Add info label
            info_label = ttk.Label(log_window, text=f"Found {len(results)} student-related log entries")
            info_label.pack(pady=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load student logs: {str(e)}")
    
    def open_realtime_monitor(self):
        """Open real-time monitoring window"""
        monitor_window = tk.Toplevel(self.root)
        monitor_window.title(_t("log_management.dialogs.realtime_monitor"))
        monitor_window.geometry("800x600")
        
        ttk.Label(monitor_window, text="Real-time Activity Monitor", 
                 font=("Arial", 14, "bold")).pack(pady=10)
        
        # Control frame
        control_frame = ttk.Frame(monitor_window)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Status labels
        self.monitor_status_label = ttk.Label(control_frame, text="Status: Stopped")
        self.monitor_status_label.pack(side=tk.LEFT)
        
        self.monitor_count_label = ttk.Label(control_frame, text="Events: 0")
        self.monitor_count_label.pack(side=tk.RIGHT)
        
        # Log display
        log_frame = ttk.LabelFrame(monitor_window, text="Live Activity Feed")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.monitor_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD,
                                                     font=("Courier", 9),
                                                     fg="#000000", bg="#FFFFFF")
        self.monitor_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Control buttons
        button_frame = ttk.Frame(monitor_window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.monitor_running = False
        self.monitor_event_count = 0
        
        def start_monitoring():
            if not self.log_manager:
                messagebox.showerror("Error", "Log manager not available")
                return
                
            self.monitor_running = True
            self.monitor_status_label.config(text="Status: Running")
            start_btn.config(state=tk.DISABLED)
            stop_btn.config(state=tk.NORMAL)
            
            # Start monitoring in background thread
            def monitor_thread():
                def log_callback(log_entry):
                    if self.monitor_running:
                        timestamp = log_entry.get('timestamp', '')[:19]
                        user = log_entry.get('username', '')
                        action = log_entry.get('action', '')
                        module = log_entry.get('module', '')
                        status = log_entry.get('status', '')
                        
                        status_symbol = "✅" if status == "success" else "❌"
                        log_line = f"{timestamp} | {status_symbol} {user} - {action} on {module}\n"
                        
                        # Update UI in main thread
                        monitor_window.after(0, lambda: self.update_monitor_display(log_line))
                
                # Subscribe to real-time updates
                self.log_manager.monitor.subscribe(log_callback)
                
                # Show recent activity
                try:
                    recent_filters = {
                        'date_from': (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d')
                    }
                    recent_logs = self.log_manager.db.search_logs(recent_filters, limit=20)
                    
                    for log in reversed(recent_logs):  # Show oldest first
                        if self.monitor_running:
                            log_callback(log)
                            
                except Exception as e:
                    print(f"Error loading recent logs: {e}")
            
            threading.Thread(target=monitor_thread, daemon=True).start()
        
        def stop_monitoring():
            self.monitor_running = False
            self.monitor_status_label.config(text="Status: Stopped")
            start_btn.config(state=tk.NORMAL)
            stop_btn.config(state=tk.DISABLED)
        
        def clear_monitor():
            self.monitor_text.delete("1.0", tk.END)
            self.monitor_event_count = 0
            self.monitor_count_label.config(text="Events: 0")
        
        start_btn = ttk.Button(button_frame, text="▶️ Start", command=start_monitoring)
        start_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        stop_btn = ttk.Button(button_frame, text="⏹️ Stop", command=stop_monitoring, state=tk.DISABLED)
        stop_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(button_frame, text="🗑️ Clear", command=clear_monitor).pack(side=tk.LEFT)
        
        # Auto-start if real-time monitoring is enabled
        if self.log_manager and self.log_manager.monitor.running:
            start_monitoring()
    
    def update_monitor_display(self, log_line):
        """Update the monitor display with new log entry"""
        try:
            self.monitor_text.insert(tk.END, log_line)
            self.monitor_text.see(tk.END)
            
            # Keep only last 1000 lines
            lines = self.monitor_text.get("1.0", tk.END).split('\n')
            if len(lines) > 1000:
                self.monitor_text.delete("1.0", f"{len(lines)-1000}.0")
            
            self.monitor_event_count += 1
            self.monitor_count_label.config(text=f"Events: {self.monitor_event_count}")

        except tk.TclError as e:
            # Window was closed
            logger.debug(f"Monitor update failed (window likely closed): {e}")
    
    def show_database_info(self):
        """Show database information"""
        if not self.log_manager:
            messagebox.showerror("Error", "Log manager not available")
            return
            
        try:
            db_path = self.log_manager.db.db_path
            
            if os.path.exists(db_path):
                size_bytes = os.path.getsize(db_path)
                size_mb = size_bytes / (1024 * 1024)
                
                # Get record counts
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM activity_log")
                log_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM alerts")
                alert_count = cursor.fetchone()[0]
                
                conn.close()
                
                info_text = f"""Database Information
====================

File Path: {db_path}
Size: {size_bytes:,} bytes ({size_mb:.2f} MB)

Record Counts:
- Logs: {log_count:,}
- Alerts: {alert_count:,}

Average log size: {size_bytes / max(log_count, 1):.0f} bytes
"""
            else:
                info_text = "Database file not found."
            
            self.maintenance_text.delete("1.0", tk.END)
            self.maintenance_text.insert("1.0", info_text)
            
        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.db_info", error=str(e)))

    def optimize_database(self):
        """Optimize database"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        if messagebox.askyesno(_t("log_management.messages.confirm"), _t("log_management.maintenance.confirm_optimize")):
            self.update_status(_t("log_management.messages.optimizing_db"))
            
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                
                output = "Database Optimization Results\n"
                output += "="*35 + "\n\n"
                
                # Analyze tables
                cursor.execute("ANALYZE")
                output += "✅ Table analysis completed\n"
                
                # Update statistics
                cursor.execute("PRAGMA optimize")
                output += "✅ Statistics updated\n"
                
                conn.commit()
                conn.close()
                
                output += "\nDatabase optimization completed successfully!"
                
                self.maintenance_text.delete("1.0", tk.END)
                self.maintenance_text.insert("1.0", output)

                self.update_status(_t("log_management.messages.optimize_completed"))
                messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.messages.optimize_completed"))

            except Exception as e:
                messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.optimize", error=str(e)))
                self.update_status(_t("log_management.messages.optimize_failed"))

    def vacuum_database(self):
        """Vacuum database to reclaim space"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        if messagebox.askyesno(_t("log_management.messages.confirm"), _t("log_management.maintenance.confirm_vacuum")):
            self.update_status(_t("log_management.messages.vacuuming_db"))
            
            try:
                # Get size before
                size_before = os.path.getsize(self.log_manager.db.db_path)
                
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                
                cursor.execute("VACUUM")
                conn.close()
                
                # Get size after
                size_after = os.path.getsize(self.log_manager.db.db_path)
                space_saved = size_before - size_after
                
                output = f"""Database Vacuum Results
=======================

Size before: {size_before:,} bytes ({size_before/(1024*1024):.2f} MB)
Size after: {size_after:,} bytes ({size_after/(1024*1024):.2f} MB)
Space reclaimed: {space_saved:,} bytes ({space_saved/(1024*1024):.2f} MB)

VACUUM completed successfully!
"""
                
                self.maintenance_text.delete("1.0", tk.END)
                self.maintenance_text.insert("1.0", output)

                self.update_status(_t("log_management.messages.vacuum_completed"))
                messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.maintenance.vacuum_success", mb=f"{space_saved/(1024*1024):.2f}"))

            except Exception as e:
                messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.vacuum", error=str(e)))
                self.update_status(_t("log_management.messages.vacuum_failed"))

    def run_integrity_check(self):
        """Run log integrity check"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        self.update_status(_t("log_management.messages.integrity_check"))
        
        try:
            # Sample check of recent logs
            filters = {
                'date_from': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            }
            
            recent_logs = self.log_manager.db.search_logs(filters, limit=1000)
            
            if not recent_logs:
                output = "No recent logs to check."
            else:
                corrupted_count = 0
                checked_count = 0
                
                for log in recent_logs:
                    if log.get('hash'):
                        # Verify hash
                        log_data = {k: v for k, v in log.items() if k != 'hash'}
                        calculated_hash = LogSecurity.generate_hash(log_data)
                        
                        if calculated_hash != log['hash']:
                            corrupted_count += 1
                        
                        checked_count += 1
                
                output = f"""Log Integrity Check Results
============================

Logs checked: {checked_count:,}
Corrupted logs: {corrupted_count:,}
Success rate: {((checked_count - corrupted_count) / max(checked_count, 1)) * 100:.2f}%

"""
                
                if corrupted_count > 0:
                    output += "⚠️ Warning: Some logs may have been tampered with!\n"
                else:
                    output += "✅ All checked logs passed integrity verification\n"
            
            self.maintenance_text.delete("1.0", tk.END)
            self.maintenance_text.insert("1.0", output)

            self.update_status(_t("log_management.messages.integrity_completed"))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.integrity", error=str(e)))
            self.update_status(_t("log_management.messages.integrity_failed"))

    def archive_old_logs(self):
        """Archive old logs"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        if messagebox.askyesno(_t("log_management.messages.confirm"), _t("log_management.maintenance.confirm_archive")):
            self.update_status(_t("log_management.messages.archiving_logs"))
            
            try:
                self.log_manager.retention.archive_old_logs()
                
                output = "Archive operation completed!\nCheck the logs/archives directory for archived files."
                
                self.maintenance_text.delete("1.0", tk.END)
                self.maintenance_text.insert("1.0", output)

                self.update_status(_t("log_management.messages.archive_completed"))
                messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.maintenance.archive_success"))

            except Exception as e:
                messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.archive", error=str(e)))
                self.update_status(_t("log_management.messages.archive_failed"))

    def cleanup_old_logs(self):
        """Cleanup old logs"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        retention_days = self.log_manager.config.get('retention_days', 90)

        if messagebox.askyesno(_t("log_management.messages.confirm"),
                              _t("log_management.maintenance.confirm_cleanup", days=retention_days)):

            if messagebox.askyesno(_t("log_management.maintenance.final_confirm"),
                                  _t("log_management.maintenance.cleanup_warning")):

                self.update_status(_t("log_management.messages.cleanup_logs"))
                
                try:
                    self.log_manager.retention.cleanup_old_logs()
                    
                    output = f"Cleanup operation completed!\nLogs older than {retention_days} days have been deleted."

                    self.maintenance_text.delete("1.0", tk.END)
                    self.maintenance_text.insert("1.0", output)

                    self.update_status(_t("log_management.messages.cleanup_completed"))
                    messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.maintenance.cleanup_success"))
                    self.update_dashboard()

                except Exception as e:
                    messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.cleanup", error=str(e)))
                    self.update_status(_t("log_management.messages.cleanup_failed"))

    def view_archives(self):
        """View archived log files"""
        archive_dir = str(LOG_DIR / "archives")

        if not os.path.exists(archive_dir):
            messagebox.showinfo(_t("log_management.messages.info"), _t("log_management.maintenance.no_archive_dir"))
            return

        archives = [f for f in os.listdir(archive_dir) if f.endswith('.zip')]

        if not archives:
            messagebox.showinfo(_t("log_management.messages.info"), _t("log_management.maintenance.no_archives"))
            return
            
        # Create archive viewer window
        archive_window = tk.Toplevel(self.root)
        archive_window.title(_t("log_management.dialogs.archive_files"))
        archive_window.geometry("600x400")
        
        ttk.Label(archive_window, text="Archive Files", font=("Arial", 14, "bold")).pack(pady=10)
        
        # Archive list
        archive_frame = ttk.LabelFrame(archive_window, text="Available Archives")
        archive_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ("Filename", "Size", "Modified")
        archive_tree = ttk.Treeview(archive_frame, columns=columns, show="headings")
        
        for col in columns:
            archive_tree.heading(col, text=col)
            archive_tree.column(col, width=150)
        
        # Populate archive list
        for archive in sorted(archives, reverse=True):
            file_path = os.path.join(archive_dir, archive)
            file_size = os.path.getsize(file_path)
            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M')
            
            archive_tree.insert("", "end", values=(archive, f"{file_size:,} bytes", file_mtime))
        
        archive_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(archive_window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        def open_archive_location():
            import subprocess
            import platform
            
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer "{os.path.abspath(archive_dir)}"')
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", archive_dir])
            else:  # Linux
                subprocess.Popen(["xdg-open", archive_dir])
        
        ttk.Button(button_frame, text="Open Archive Folder", command=open_archive_location).pack(side=tk.LEFT)
    
    def test_query_performance(self):
        """Test database query performance"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        self.update_status(_t("log_management.messages.query_perf_test"))
        
        try:
            queries = [
                ("Simple count", "SELECT COUNT(*) FROM activity_log"),
                ("Date filter", "SELECT COUNT(*) FROM activity_log WHERE date(timestamp) >= date('now', '-7 days')"),
                ("User filter", "SELECT COUNT(*) FROM activity_log WHERE user_id = 'admin'"),
                ("Complex filter", "SELECT COUNT(*) FROM activity_log WHERE action = 'login' AND status = 'success'")
            ]
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            
            output = "Query Performance Test Results\n"
            output += "="*40 + "\n\n"
            output += f"{'Query':<20} {'Time (ms)':<12} {'Result':<10}\n"
            output += "-" * 45 + "\n"
            
            for name, query in queries:
                start_time = time.time()
                
                try:
                    cursor = conn.cursor()
                    cursor.execute(query)
                    result = cursor.fetchone()[0]
                    
                    end_time = time.time()
                    duration_ms = (end_time - start_time) * 1000
                    
                    output += f"{name:<20} {duration_ms:<11.2f} {result:<10}\n"
                    
                except Exception as e:
                    output += f"{name:<20} ERROR: {str(e)}\n"
            
            conn.close()

            self.maintenance_text.delete("1.0", tk.END)
            self.maintenance_text.insert("1.0", output)

            self.update_status(_t("log_management.messages.query_perf_completed"))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.query_perf", error=str(e)))
            self.update_status(_t("log_management.messages.query_perf_failed"))

    def test_insert_performance(self):
        """Test database insert performance"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return
            
        test_count = tk.simpledialog.askinteger(_t("log_management.maintenance.insert_perf_title"),
                                              _t("log_management.maintenance.insert_count_prompt"),
                                              initialvalue=100, minvalue=10, maxvalue=1000)
        if not test_count:
            return

        if messagebox.askyesno(_t("log_management.messages.confirm"), _t("log_management.maintenance.confirm_insert_test", count=test_count)):
            self.update_status(f"Running insert performance test with {test_count} entries...")
            
            try:
                start_time = time.time()
                
                for i in range(test_count):
                    test_log = {
                        'timestamp': datetime.now().isoformat(),
                        'user_id': f'test_user_{i}',
                        'username': f'testuser{i}',
                        'action': 'test_action',
                        'module': 'performance_test',
                        'details': f'Test entry {i}',
                        'status': 'success'
                    }

                    self.log_manager.db.insert_log(test_log)
                
                end_time = time.time()
                duration = end_time - start_time
                
                output = f"""Insert Performance Test Results
===================================

Test entries: {test_count:,}
Total time: {duration:.2f} seconds
Average per insert: {(duration/test_count)*1000:.2f} ms
Inserts per second: {test_count/duration:.1f}

Test completed successfully!
"""
                
                # Cleanup test entries
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute("DELETE FROM activity_log WHERE action = 'performance_test'")
                deleted = cursor.rowcount
                conn.commit()
                conn.close()
                
                output += f"\nCleaned up {deleted} test entries."
                
                self.maintenance_text.delete("1.0", tk.END)
                self.maintenance_text.insert("1.0", output)

                self.update_status(_t("log_management.messages.insert_perf_completed"))

            except Exception as e:
                messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.insert_perf", error=str(e)))
                self.update_status(_t("log_management.messages.insert_perf_failed"))
    
    def show_system_resources(self):
        """Show system resource usage"""
        try:
            import psutil
            
            # Get system info
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Get process info
            process = psutil.Process()
            
            output = f"""System Resource Usage
======================

CPU Usage: {cpu_percent}%
Memory Usage: {memory.percent}%
Available Memory: {memory.available / (1024**3):.2f} GB
Total Memory: {memory.total / (1024**3):.2f} GB

Disk Usage: {(disk.used / disk.total) * 100:.1f}%
Free Disk Space: {disk.free / (1024**3):.2f} GB
Total Disk Space: {disk.total / (1024**3):.2f} GB

Current Process:
Memory Usage: {process.memory_info().rss / (1024**2):.2f} MB
CPU Usage: {process.cpu_percent()}%
"""
            
        except ImportError:
            output = """System Resource Usage
======================

psutil library not available.
Install with: pip install psutil

Basic system information not available.
"""
        except Exception as e:
            output = f"Error retrieving system information: {str(e)}"
        
        self.maintenance_text.delete("1.0", tk.END)
        self.maintenance_text.insert("1.0", output)
    
    def show_api_docs(self):
        """Show API documentation"""
        docs_window = tk.Toplevel(self.root)
        docs_window.title(_t("log_management.dialogs.api_docs"))
        docs_window.geometry("800x600")
        
        ttk.Label(docs_window, text=_t("log_management.dialogs.api_docs"), 
                 font=("Arial", 14, "bold")).pack(pady=10)
        
        docs_text = scrolledtext.ScrolledText(docs_window, wrap=tk.WORD, font=("Courier", 10))
        docs_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        api_docs = """
Log Management API Endpoints
============================

Authentication:
POST /api/auth/login - Get authentication token
  Body: {"username": "user", "password": "pass"}
  Returns: {"token": "jwt_token", "expires_in": 86400}

Log Operations:
POST /api/logs/search - Search logs with filters
  Headers: Authorization: Bearer <token>
  Body: {"date_from": "2024-01-01", "user_id": "admin", "limit": 100}
  
GET /api/logs/recent?hours=24&limit=50 - Get recent logs
  Headers: Authorization: Bearer <token>
  
GET /api/logs/user/{user_id}?days=7&limit=100 - Get logs for specific user
  Headers: Authorization: Bearer <token>

Analytics:
GET /api/analytics/summary?days=7 - Get activity summary
  Headers: Authorization: Bearer <token>
  
GET /api/analytics/user/{user_id}?days=30 - Get user analytics
  Headers: Authorization: Bearer <token>
  
POST /api/analytics/chart - Generate activity chart
  Headers: Authorization: Bearer <token>
  Body: {"days": 7, "type": "daily"}

Alerts:
GET /api/alerts?hours=24 - Get recent alerts
  Headers: Authorization: Bearer <token>
  
POST /api/alerts/check - Trigger alert checks
  Headers: Authorization: Bearer <token>

Export:
POST /api/export/logs - Export logs with filters
  Headers: Authorization: Bearer <token>
  Body: {"filters": {...}, "format": "json|csv|excel"}

System:
GET /api/system/status - Get system status
  Headers: Authorization: Bearer <token>
  
GET /api/config - Get configuration
  Headers: Authorization: Bearer <token>
  
PUT /api/config - Update configuration
  Headers: Authorization: Bearer <token>
  Body: {"retention_days": 90, "enable_alerts": true}

Webhooks:
POST /api/webhooks/log - Receive external log entries
  Headers: X-Webhook-Key: <webhook_secret>
  Body: {log_entry_data}

Health:
GET /api/health - Health check (no auth required)
  Returns: {"status": "healthy", "timestamp": "..."}

Error Responses:
All endpoints return appropriate HTTP status codes:
- 200: Success
- 400: Bad Request
- 401: Unauthorized
- 404: Not Found
- 500: Internal Server Error

Response format:
{
  "success": true/false,
  "data": {...},
  "error": "error message if applicable"
}
"""
        
        docs_text.insert("1.0", api_docs)
        docs_text.config(state=tk.DISABLED)
    
    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            root_widget = self.root if hasattr(self, 'root') else self.master
            if isinstance(root_widget, tk.Toplevel):
                # Just close the child window
                root_widget.destroy()
            else:
                # Running standalone, need to create main GUI
                root_widget.destroy()
                from university_system.modules.shared.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def show_about(self):
        """Show about dialog"""
        about_text = """Enhanced Log Management System
Version 1.0.0

A comprehensive logging and audit system with:
• Real-time monitoring
• Advanced search and filtering
• Analytics and reporting
• Security alerts
• API integration
• Database management tools

Built with Python and tkinter
Compatible with the original CLI interface

For support and documentation, visit:
https://github.com/yourproject/log-management"""
        
        messagebox.showinfo("About", about_text)


# GUI Launcher Functions (maintains backwards compatibility)
def launch_log_management_gui(auth=None):
    """Launch the GUI version of log management"""
    root = tk.Tk()
    app = LogManagementGUI(root, auth)
    root.mainloop()

def display_log_management_menu_gui(auth):
    """GUI version of the original menu function"""
    launch_log_management_gui(auth)

if __name__ == "__main__":
    # Test the GUI
    try:
        # Try to import the original module for full functionality
        from university_system.infrastructure.logging.log_management import (
            log_manager, LogSecurity, generate_api_key, generate_chart,
            get_alerts, get_log_manager, login, optimize_database, save_search,
            search_logs, show_api_docs, show_system_resources,
            test_insert_performance, test_query_performance, vacuum_database
        )
        print("Full log management system loaded")
    except ImportError:
        print("Running in standalone GUI mode")
    
    # Add tkinter import for the dialog
    import tkinter.simpledialog
    tk.simpledialog = tkinter.simpledialog
    
    # Launch GUI
    launch_log_management_gui()
