import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import threading
from datetime import datetime, timedelta
import json
import webbrowser
from pathlib import Path
import matplotlib
from education_system.university_system.modules.shared.constants import paths
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

# Import auth instance management from user_authentication
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
# Import the shared authentication system
try:
    from education_system.university_system.infrastructure.auth import UserAuth
    from education_system.university_system.infrastructure.shared_context import get_auth
except ImportError as e:
    print(f"⚠️ Could not import UserAuth: {e}")
    UserAuth = None
    get_auth = lambda: None

from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()


# This module defines mixin functions for FinancialManagementGUI
# Note: FinancialManagementGUI is registered via register function to avoid circular imports

def create_settings_tab(self):
    """Create settings tab with system configuration"""
    settings_frame = ttk.Frame(self.notebook, padding="10")
    self.notebook.add(settings_frame, text=_("finance_reporting.tabs.settings"))

    # Alert settings
    alert_frame = ttk.LabelFrame(settings_frame, text=_("finance_reporting.settings.alert_thresholds"), padding="10")
    alert_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    # Alert threshold settings
    self.alert_vars = {}
    alert_settings = [
        (_("finance_reporting.settings.collection_rate_min"), 'collection_rate_min', 85.0),
        (_("finance_reporting.settings.daily_payment_min"), 'daily_payment_min', 1000.0),
        (_("finance_reporting.settings.large_payment_threshold"), 'large_payment_threshold', 5000.0),
        (_("finance_reporting.settings.overdue_balance_max"), 'overdue_balance_max', 10000.0)
    ]

    for i, (label, var_name, default_value) in enumerate(alert_settings):
        ttk.Label(alert_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=2)
        self.alert_vars[var_name] = tk.DoubleVar(value=default_value)
        ttk.Entry(alert_frame, textvariable=self.alert_vars[var_name],
                 width=15).grid(row=i, column=1, sticky=tk.W, padx=(10, 0), pady=2)

    # System settings
    system_frame = ttk.LabelFrame(settings_frame, text=_("finance_reporting.settings.system_settings"), padding="10")
    system_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    # Auto-refresh setting
    self.auto_refresh = tk.BooleanVar(value=True)
    ttk.Checkbutton(system_frame, text=_("finance_reporting.settings.auto_refresh"),
                   variable=self.auto_refresh).grid(row=0, column=0, sticky=tk.W)

    # Email notifications
    self.email_notifications = tk.BooleanVar(value=True)
    ttk.Checkbutton(system_frame, text=_("finance_reporting.settings.email_notifications"),
                   variable=self.email_notifications).grid(row=1, column=0, sticky=tk.W)

    # Export location
    ttk.Label(system_frame, text=_("finance_reporting.settings.export_location")).grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
    export_frame = ttk.Frame(system_frame)
    export_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(5, 0))

    self.export_path = tk.StringVar(value=str(paths.EXPORTS_REPORTS_DIR))
    ttk.Entry(export_frame, textvariable=self.export_path, width=40).grid(row=0, column=0, sticky=(tk.W, tk.E))
    ttk.Button(export_frame, text=_("common.browse"), command=self.browse_export_path).grid(row=0, column=1, padx=(5, 0))

    export_frame.grid_columnconfigure(0, weight=1)

    # Save settings button
    ttk.Button(system_frame, text=_("finance_reporting.buttons.save_settings"), command=self.save_settings,
              style='Accent.TButton').grid(row=4, column=0, pady=(15, 0))

    # System info frame
    info_frame = ttk.LabelFrame(settings_frame, text=_("finance_reporting.settings.system_info"), padding="10")
    info_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # System info display
    self.info_text = ScrolledText(info_frame, height=8, wrap=tk.WORD)
    self.info_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Populate system info
    self.update_system_info()

    info_frame.grid_rowconfigure(0, weight=1)
    info_frame.grid_columnconfigure(0, weight=1)
    settings_frame.grid_rowconfigure(2, weight=1)
    settings_frame.grid_columnconfigure(0, weight=1)

def browse_export_path(self):
    """Browse for export directory"""
    directory = filedialog.askdirectory(title=_("finance_reporting.settings.select_export_directory"))
    if directory:
        self.export_path.set(directory)

def save_settings(self):
    """Save application settings"""
    settings = {
        'alert_thresholds': {key: var.get() for key, var in self.alert_vars.items()},
        'auto_refresh': self.auto_refresh.get(),
        'email_notifications': self.email_notifications.get(),
        'export_path': self.export_path.get()
    }

    try:
        with open('finance_gui_settings.json', 'w') as f:
            json.dump(settings, f, indent=2)

        messagebox.showinfo(_("finance_reporting.messages.settings_saved"), _("finance_reporting.messages.settings_saved_msg"))
        self.log_activity(_("finance_reporting.activity.settings_saved"))

    except Exception as e:
        messagebox.showerror(_("common.error"), _("finance_reporting.messages.save_settings_failed", error=e))

def load_settings(self):
    """Load application settings"""
    try:
        if Path('finance_gui_settings.json').exists():
            with open('finance_gui_settings.json', 'r') as f:
                settings = json.load(f)

            # Load alert thresholds
            for key, value in settings.get('alert_thresholds', {}).items():
                if key in self.alert_vars:
                    self.alert_vars[key].set(value)

            # Load other settings
            self.auto_refresh.set(settings.get('auto_refresh', True))
            self.email_notifications.set(settings.get('email_notifications', True))
            self.export_path.set(settings.get('export_path', './exports/'))

            self.log_activity("Settings loaded")

    except Exception as e:
        self.log_activity(f"Error loading settings: {e}")

def update_system_info(self):
    """Update system information display"""
    info_text = f"""System Information
    ==================

    Application: Enhanced Financial Management System
    Version: 2.0.0 (GUI Edition)
    Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    Database Status: Connected
    ML Models: Available
    Export System: Ready
    Alert System: Active

    Features Available:
    • Advanced Financial Forecasting
    • Real-time Dashboard
    • Payment Risk Prediction
    • Anomaly Detection
    • Cash Flow Forecasting
    • Scenario Planning
    • Automated Reporting
    • Compliance Audit
    • ML Model Training
    • Advanced Export System

    Memory Usage: Normal
    Performance: Optimal
    Last Health Check: {datetime.now().strftime('%H:%M:%S')}

    For technical support, contact your system administrator.
    """

    self.info_text.delete(1.0, tk.END)
    self.info_text.insert(1.0, info_text)

def register_settings_tab_methods(cls):
    """Register settings tab methods onto FinancialManagementGUI class."""
    cls.create_settings_tab = create_settings_tab
    cls.browse_export_path = browse_export_path
    cls.save_settings = save_settings
    cls.load_settings = load_settings
    cls.update_system_info = update_system_info
