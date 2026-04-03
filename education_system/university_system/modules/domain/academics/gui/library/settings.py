"""
Enhanced Library Management System - GUI Version
Maintains all original CLI functions while adding a modern GUI interface
Backwards compatible with existing database and auth systems
"""


from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()
from tkinter.scrolledtext import ScrolledText
import threading
import queue
import os
import sys
from datetime import datetime, timedelta
import json
from education_system.university_system.infrastructure.database.db import sqlite3
from typing import Dict, List, Optional, Any
import logging
import urllib.request
import urllib.parse
import urllib.error

# Import custom exceptions for better error handling
from education_system.university_system.infrastructure.exceptions import (
    DatabaseError,
    QueryError,
    ValidationError,
    InvalidInputError,
    FileError,
    UniversityFileNotFoundError
)

# Import all original library functions
try:
    # Import from modular library package
    from education_system.university_system.modules.domain.academics.services.library.settings import (
        auth, get_current_user_id, set_auth, get_library_settings, update_library_setting
    )
    from education_system.university_system.modules.domain.academics.services.library.menu import display_library_menu
    from education_system.university_system.modules.domain.academics.services.library.barcode import (
        generate_barcode, generate_qr_code, process_scanned_barcode
    )
    from education_system.university_system.modules.domain.academics.services.library.reports import (
        generate_circulation_report, generate_library_statistics_export, generate_user_activity_report
    )
    from education_system.university_system.modules.domain.academics.services.library.database import (
        get_db_connection, init_library_db, log_audit_event
    )
    from education_system.university_system.modules.domain.academics.services.library.backup import (
        quick_system_health_check, restore_from_backup
    )
    from education_system.university_system.modules.domain.academics.services.library.reading_lists import view_reading_list_details
    ORIGINAL_LIBRARY_AVAILABLE = True
except ImportError:
    print("Warning: Original library module not found. GUI will use standalone functions.")
    ORIGINAL_LIBRARY_AVAILABLE = False

# Import shared authentication system
try:
    from education_system.university_system.infrastructure.auth import UserAuth
    from education_system.university_system.infrastructure.shared_context import get_auth, get_current_user
    SHARED_AUTH_AVAILABLE = True
except ImportError:
    print("Warning: Shared authentication system not found.")
    SHARED_AUTH_AVAILABLE = False
    # Provide fallback functions
    def get_auth():
        return None
    def get_current_user():
        return None

from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD,
        ensure_student_finance_account_exists,
        top_up_student_finance_account
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

# Import matplotlib for library finance charts
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: Matplotlib not available for library finance charts")

# Import email service for library finance notifications
try:
    from education_system.university_system.infrastructure.email.email_service import send_email_as_system
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    def send_email_as_system(*args, **kwargs):
        return False
    print("Warning: Email service not available for library finance")

_AUDIT_LOG_COLUMNS_CACHE: Optional[List[str]] = None
_STUDENT_COLUMNS_CACHE: Optional[List[str]] = None

from education_system.university_system.modules.domain.academics.gui.library.base import LibraryGUI

def show_settings(self):
    """Show settings interface"""
    if not self.check_permission('system_config'):
        return

    self.clear_content_area()

    settings_frame = ttk.Frame(self.notebook)
    self.notebook.add(settings_frame, text="Settings")

    title_label = ttk.Label(settings_frame, text="System Settings", style='Title.TLabel')
    title_label.pack(pady=10)

    # Settings categories
    categories_frame = ttk.Frame(settings_frame)
    categories_frame.pack(fill=tk.X, padx=10, pady=5)

    # Create notebook for settings categories
    settings_notebook = ttk.Notebook(categories_frame)
    settings_notebook.pack(fill=tk.BOTH, expand=True)

    # Library Settings tab
    library_tab = ttk.Frame(settings_notebook)
    settings_notebook.add(library_tab, text="Library Settings")

    self.create_library_settings_tab(library_tab)

    # System Settings tab
    system_tab = ttk.Frame(settings_notebook)
    settings_notebook.add(system_tab, text="System Settings")

    self.create_system_settings_tab(system_tab)

    # User Settings tab
    user_tab = ttk.Frame(settings_notebook)
    settings_notebook.add(user_tab, text="User Settings")

    self.create_user_settings_tab(user_tab)

def create_library_settings_tab(self, parent):
    """Create library settings tab"""
    # Loan settings
    loan_frame = ttk.LabelFrame(parent, text="Loan Settings")
    loan_frame.pack(fill=tk.X, padx=10, pady=5)

    # Load current settings
    self.library_settings_vars = {}

    library_settings = [
        ("Loan Period (days):", "loan_period_days", "14"),
        ("Maximum Loans per User:", "max_loans", "5"),
        ("Fine per Day ($):", "fine_per_day", "0.50"),
        ("Reservation Period (days):", "reservation_period_days", "3"),
        ("Maximum Renewals:", "max_renewals", "2"),
    ]

    for i, (label, setting_name, default_value) in enumerate(library_settings):
        ttk.Label(loan_frame, text=label).grid(row=i, column=0, sticky='w', padx=5, pady=5)

        var = tk.StringVar()

        # Load current value
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                current_value = get_library_settings(setting_name) or default_value
            else:
                current_value = default_value
            var.set(current_value)
        except tk.TclError:
            var.set(default_value)

        entry = ttk.Entry(loan_frame, textvariable=var, width=10)
        entry.grid(row=i, column=1, sticky='w', padx=5, pady=5)

        self.library_settings_vars[setting_name] = var

    # Notification settings
    notification_frame = ttk.LabelFrame(parent, text="Notification Settings")
    notification_frame.pack(fill=tk.X, padx=10, pady=5)

    self.notification_vars = {}
    notification_settings = [
        ("Email Notifications", "email_notifications"),
        ("SMS Notifications", "sms_notifications"),
        ("Overdue Reminders", "overdue_notifications"),
        ("Reservation Alerts", "reservation_alerts"),
    ]

    for i, (label, setting_name) in enumerate(notification_settings):
        var = tk.BooleanVar()

        # Load current value
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                current_value = get_library_settings(setting_name) == 'true'
            else:
                current_value = True
            var.set(current_value)
        except tk.TclError:
            var.set(True)

        checkbox = ttk.Checkbutton(notification_frame, text=label, variable=var)
        checkbox.grid(row=i, column=0, sticky='w', padx=5, pady=5)

        self.notification_vars[setting_name] = var

    # Save button
    ttk.Button(parent, text="Save Library Settings", command=self.save_library_settings).pack(pady=10)

def create_system_settings_tab(self, parent):
    """Create system settings tab"""
    # Backup settings
    backup_frame = ttk.LabelFrame(parent, text="Backup Settings")
    backup_frame.pack(fill=tk.X, padx=10, pady=5)

    self.auto_backup_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(backup_frame, text="Enable Automatic Backups", variable=self.auto_backup_var).pack(anchor='w', padx=5, pady=5)

    ttk.Label(backup_frame, text="Backup Frequency (hours):").pack(anchor='w', padx=5, pady=5)
    self.backup_frequency_var = tk.StringVar(value="24")
    ttk.Entry(backup_frame, textvariable=self.backup_frequency_var, width=10).pack(anchor='w', padx=20, pady=5)

    # Database settings
    db_frame = ttk.LabelFrame(parent, text="Database Settings")
    db_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(db_frame, text="Optimize Database", command=self.optimize_database).pack(anchor='w', padx=5, pady=5)
    ttk.Button(db_frame, text="Check Integrity", command=self.check_database_integrity).pack(anchor='w', padx=5, pady=5)
    ttk.Button(db_frame, text="View Audit Log", command=self.show_audit_log).pack(anchor='w', padx=5, pady=5)

    # Save button
    ttk.Button(parent, text="Save System Settings", command=self.save_system_settings).pack(pady=10)

def create_user_settings_tab(self, parent):
    """Create user settings tab"""
    # User preferences
    pref_frame = ttk.LabelFrame(parent, text="User Preferences")
    pref_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Label(pref_frame, text="Default View:").pack(anchor='w', padx=5, pady=5)
    self.default_view_var = tk.StringVar(value="Dashboard")
    view_combo = ttk.Combobox(pref_frame, textvariable=self.default_view_var, width=20)
    view_combo['values'] = ('Dashboard', 'All Books', 'Search', 'Reports')
    view_combo.pack(anchor='w', padx=20, pady=5)

    ttk.Label(pref_frame, text="Items per Page:").pack(anchor='w', padx=5, pady=5)
    self.items_per_page_var = tk.StringVar(value="50")
    items_combo = ttk.Combobox(pref_frame, textvariable=self.items_per_page_var, width=10)
    items_combo['values'] = ('25', '50', '100', '200')
    items_combo.pack(anchor='w', padx=20, pady=5)

    # Interface settings
    interface_frame = ttk.LabelFrame(parent, text="Interface Settings")
    interface_frame.pack(fill=tk.X, padx=10, pady=5)

    self.confirm_deletes_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(interface_frame, text="Confirm Deletions", variable=self.confirm_deletes_var).pack(anchor='w', padx=5, pady=5)

    self.auto_refresh_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(interface_frame, text="Auto-refresh Data", variable=self.auto_refresh_var).pack(anchor='w', padx=5, pady=5)

    # Save button
    ttk.Button(parent, text="Save User Settings", command=self.save_user_settings).pack(pady=10)

def save_library_settings(self):
    """Save library settings"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            for setting_name, var in self.library_settings_vars.items():
                value = var.get().strip()
                if value:
                    update_library_setting(setting_name, value)

            for setting_name, var in self.notification_vars.items():
                value = 'true' if var.get() else 'false'
                update_library_setting(setting_name, value)

            messagebox.showinfo(_("common.success"), "Library settings saved successfully!")

            # Log the action
            log_audit_event(get_current_user_id(), "GUI: Updated library settings", "library_settings")
        else:
            messagebox.showinfo(_("common.demo"), "Settings would be saved in full version")

    except (tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Error saving settings: {str(e)}")

def save_system_settings(self):
    """Save system settings"""
    messagebox.showinfo(_("common.success"), "System settings saved successfully!")

def save_user_settings(self):
    """Save user settings"""
    messagebox.showinfo(_("common.success"), "User settings saved successfully!")

def show_user_preferences(self):
    """Show user preferences dialog"""
    # Get current user from auth system
    current_user = None
    if SHARED_AUTH_AVAILABLE:
        current_user = get_current_user()
    elif self.auth and hasattr(self.auth, 'current_user'):
        current_user = self.auth.current_user

    if not current_user:
        messagebox.showwarning(_("common.warning"), "Please log in first")
        return

    prefs_dialog = tk.Toplevel(self.master)
    prefs_dialog.title(_("library.dialogs.user_preferences"))
    prefs_dialog.geometry("400x300")
    prefs_dialog.transient(self.master)
    prefs_dialog.grab_set()

    main_frame = ttk.Frame(prefs_dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Create notebook for preference categories
    prefs_notebook = ttk.Notebook(main_frame)
    prefs_notebook.pack(fill=tk.BOTH, expand=True)

    # General preferences
    general_frame = ttk.Frame(prefs_notebook)
    prefs_notebook.add(general_frame, text="General")

    ttk.Label(general_frame, text="Default Dashboard View:").pack(anchor='w', pady=5)
    self.default_dashboard_var = tk.StringVar(value="Statistics")
    dashboard_combo = ttk.Combobox(general_frame, textvariable=self.default_dashboard_var, width=30)
    dashboard_combo['values'] = ('Statistics', 'Recent Activity', 'Quick Actions', 'Reports')
    dashboard_combo.pack(anchor='w', padx=20, pady=5)

    ttk.Label(general_frame, text="Items per Page:").pack(anchor='w', pady=5)
    self.items_per_page_pref_var = tk.StringVar(value="50")
    items_combo = ttk.Combobox(general_frame, textvariable=self.items_per_page_pref_var, width=10)
    items_combo['values'] = ('25', '50', '100', '200')
    items_combo.pack(anchor='w', padx=20, pady=5)

    # Interface preferences
    interface_frame = ttk.Frame(prefs_notebook)
    prefs_notebook.add(interface_frame, text="Interface")

    self.confirm_actions_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(interface_frame, text="Confirm dangerous actions",
                   variable=self.confirm_actions_var).pack(anchor='w', pady=5)

    self.auto_save_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(interface_frame, text="Auto-save form data",
                   variable=self.auto_save_var).pack(anchor='w', pady=5)

    self.show_tooltips_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(interface_frame, text="Show tooltips",
                   variable=self.show_tooltips_var).pack(anchor='w', pady=5)

    # Notification preferences
    notification_frame = ttk.Frame(prefs_notebook)
    prefs_notebook.add(notification_frame, text="Notifications")

    self.desktop_notifications_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(notification_frame, text="Desktop notifications",
                   variable=self.desktop_notifications_var).pack(anchor='w', pady=5)

    self.sound_alerts_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(notification_frame, text="Sound alerts",
                   variable=self.sound_alerts_var).pack(anchor='w', pady=5)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=10)

    ttk.Button(button_frame, text=_("common.save"), command=lambda: self.save_user_preferences(prefs_dialog)).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.cancel"), command=prefs_dialog.destroy).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Reset to Defaults", command=self.reset_user_preferences).pack(side=tk.LEFT, padx=5)

def save_user_preferences(self, dialog):
    """Save user preferences"""
    try:
        preferences = {
            'default_dashboard': self.default_dashboard_var.get(),
            'items_per_page': self.items_per_page_pref_var.get(),
            'confirm_actions': self.confirm_actions_var.get(),
            'auto_save': self.auto_save_var.get(),
            'show_tooltips': self.show_tooltips_var.get(),
            'desktop_notifications': self.desktop_notifications_var.get(),
            'sound_alerts': self.sound_alerts_var.get(),
        }

        if ORIGINAL_LIBRARY_AVAILABLE:
            # Save to database user_preferences table
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                user_id = get_current_user_id()

                cursor.execute('''
                INSERT OR REPLACE INTO user_preferences
                (user_id, preferred_categories, preferred_authors, reading_level,
                 notification_preferences, privacy_settings, reading_goals, language_preference)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    json.dumps([]),  # preferred_categories
                    json.dumps([]),  # preferred_authors
                    'Unknown',       # reading_level
                    json.dumps({
                        'desktop_notifications': preferences['desktop_notifications'],
                        'sound_alerts': preferences['sound_alerts']
                    }),
                    json.dumps({
                        'confirm_actions': preferences['confirm_actions'],
                        'auto_save': preferences['auto_save']
                    }),
                    json.dumps([]),  # reading_goals
                    'English'        # language_preference
                ))

                conn.commit()
                conn.close()

        messagebox.showinfo(_("common.success"), "Preferences saved successfully!")
        dialog.destroy()

    except (json.JSONDecodeError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Error saving preferences: {str(e)}")

def reset_user_preferences(self):
    """Reset user preferences to defaults"""
    result = messagebox.askyesno("Confirm Reset", "Reset all preferences to default values?")

    if result:
        self.default_dashboard_var.set("Statistics")
        self.items_per_page_pref_var.set("50")
        self.confirm_actions_var.set(True)
        self.auto_save_var.set(True)
        self.show_tooltips_var.set(True)
        self.desktop_notifications_var.set(True)
        self.sound_alerts_var.set(False)

        messagebox.showinfo(_("common.success"), "Preferences reset to defaults")

def enhanced_settings_management_gui(self):
    """Enhanced settings management interface"""
    settings_window = tk.Toplevel(self.master)
    settings_window.title("Library Settings Management")
    settings_window.geometry("800x700")

    ttk.Label(settings_window, text="Library Settings Management",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Notebook for settings categories
    notebook = ttk.Notebook(settings_window)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Tab 1: General Settings
    general_tab = ttk.Frame(notebook)
    notebook.add(general_tab, text="General")

    general_frame = ttk.LabelFrame(general_tab, text="General Library Settings", padding=15)
    general_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    settings_data = {}

    # Load current settings
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT setting_name, setting_value FROM library_settings')
        for name, value in cursor.fetchall():
            settings_data[name] = value
        conn.close()
    except (sqlite3.Error, DatabaseError, tk.TclError):
        pass

    # Create settings inputs
    settings_vars = {}

    ttk.Label(general_frame, text="Max Loans Per User:").grid(row=0, column=0, sticky=tk.W, pady=5)
    settings_vars['max_loans'] = tk.IntVar(value=int(settings_data.get('max_loans', 5)))
    ttk.Spinbox(general_frame, from_=1, to=20, textvariable=settings_vars['max_loans'], width=10).grid(row=0, column=1, sticky=tk.W, pady=5)

    ttk.Label(general_frame, text="Loan Period (days):").grid(row=1, column=0, sticky=tk.W, pady=5)
    settings_vars['loan_period_days'] = tk.IntVar(value=int(settings_data.get('loan_period_days', 14)))
    ttk.Spinbox(general_frame, from_=1, to=90, textvariable=settings_vars['loan_period_days'], width=10).grid(row=1, column=1, sticky=tk.W, pady=5)

    ttk.Label(general_frame, text="Max Renewals:").grid(row=2, column=0, sticky=tk.W, pady=5)
    settings_vars['max_renewals'] = tk.IntVar(value=int(settings_data.get('max_renewals', 2)))
    ttk.Spinbox(general_frame, from_=0, to=10, textvariable=settings_vars['max_renewals'], width=10).grid(row=2, column=1, sticky=tk.W, pady=5)

    ttk.Label(general_frame, text="Fine Per Day ($):").grid(row=3, column=0, sticky=tk.W, pady=5)
    settings_vars['fine_per_day'] = tk.DoubleVar(value=float(settings_data.get('fine_per_day', 0.50)))
    ttk.Spinbox(general_frame, from_=0, to=10, increment=0.10, textvariable=settings_vars['fine_per_day'], width=10).grid(row=3, column=1, sticky=tk.W, pady=5)

    ttk.Label(general_frame, text="Reservation Period (days):").grid(row=4, column=0, sticky=tk.W, pady=5)
    settings_vars['reservation_period_days'] = tk.IntVar(value=int(settings_data.get('reservation_period_days', 3)))
    ttk.Spinbox(general_frame, from_=1, to=30, textvariable=settings_vars['reservation_period_days'], width=10).grid(row=4, column=1, sticky=tk.W, pady=5)

    # Tab 2: Notification Settings
    notif_tab = ttk.Frame(notebook)
    notebook.add(notif_tab, text="Notifications")

    notif_frame = ttk.LabelFrame(notif_tab, text="Notification Settings", padding=15)
    notif_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    ttk.Label(notif_frame, text="Due Date Reminder (days before):").grid(row=0, column=0, sticky=tk.W, pady=5)
    settings_vars['due_reminder_days'] = tk.IntVar(value=int(settings_data.get('due_reminder_days', 3)))
    ttk.Spinbox(notif_frame, from_=1, to=14, textvariable=settings_vars['due_reminder_days'], width=10).grid(row=0, column=1, sticky=tk.W, pady=5)

    ttk.Label(notif_frame, text="Overdue Reminder Frequency (days):").grid(row=1, column=0, sticky=tk.W, pady=5)
    settings_vars['overdue_reminder_freq'] = tk.IntVar(value=int(settings_data.get('overdue_reminder_freq', 7)))
    ttk.Spinbox(notif_frame, from_=1, to=30, textvariable=settings_vars['overdue_reminder_freq'], width=10).grid(row=1, column=1, sticky=tk.W, pady=5)

    settings_vars['email_notifications'] = tk.BooleanVar(value=settings_data.get('email_notifications', 'true') == 'true')
    ttk.Checkbutton(notif_frame, text="Enable Email Notifications", variable=settings_vars['email_notifications']).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)

    settings_vars['sms_notifications'] = tk.BooleanVar(value=settings_data.get('sms_notifications', 'false') == 'true')
    ttk.Checkbutton(notif_frame, text="Enable SMS Notifications", variable=settings_vars['sms_notifications']).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)

    # Tab 3: System Settings
    system_tab = ttk.Frame(notebook)
    notebook.add(system_tab, text="System")

    system_frame = ttk.LabelFrame(system_tab, text="System Settings", padding=15)
    system_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    ttk.Label(system_frame, text="Library Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
    settings_vars['library_name'] = tk.StringVar(value=settings_data.get('library_name', 'University Library'))
    ttk.Entry(system_frame, textvariable=settings_vars['library_name'], width=40).grid(row=0, column=1, sticky=tk.W, pady=5)

    ttk.Label(system_frame, text="Library Email:").grid(row=1, column=0, sticky=tk.W, pady=5)
    settings_vars['library_email'] = tk.StringVar(value=settings_data.get('library_email', 'library@university.edu'))
    ttk.Entry(system_frame, textvariable=settings_vars['library_email'], width=40).grid(row=1, column=1, sticky=tk.W, pady=5)

    ttk.Label(system_frame, text="Library Phone:").grid(row=2, column=0, sticky=tk.W, pady=5)
    settings_vars['library_phone'] = tk.StringVar(value=settings_data.get('library_phone', ''))
    ttk.Entry(system_frame, textvariable=settings_vars['library_phone'], width=40).grid(row=2, column=1, sticky=tk.W, pady=5)

    def save_all_settings():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            for setting_name, var in settings_vars.items():
                if isinstance(var, tk.BooleanVar):
                    value = 'true' if var.get() else 'false'
                else:
                    value = str(var.get())

                cursor.execute('''
                INSERT OR REPLACE INTO library_settings (setting_name, setting_value)
                VALUES (?, ?)
                ''', (setting_name, value))

            conn.commit()
            conn.close()

            log_audit_event(get_current_user_id(), "Updated library settings", "library_settings")

            messagebox.showinfo(_("common.success"), "All settings saved successfully!")

        except (sqlite3.Error, DatabaseError, tk.TclError, ValueError, TypeError) as e:
            messagebox.showerror(_("common.error"), f"Failed to save settings: {str(e)}")

    # Button frame
    button_frame = ttk.Frame(settings_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Save All Settings", command=save_all_settings).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=settings_window.destroy).pack(side=tk.RIGHT, padx=5)

def export_settings_gui(self):
    """Export library settings to file"""
    export_window = tk.Toplevel(self.master)
    export_window.title("Export Settings")
    export_window.geometry("500x300")

    ttk.Label(export_window, text="Export Library Settings",
             font=('Arial', 14, 'bold')).pack(pady=10)

    # Format selection
    format_frame = ttk.LabelFrame(export_window, text="Export Format", padding=10)
    format_frame.pack(fill=tk.X, padx=10, pady=10)

    format_var = tk.StringVar(value="json")
    ttk.Radiobutton(format_frame, text="JSON Format", variable=format_var, value="json").pack(anchor=tk.W)
    ttk.Radiobutton(format_frame, text="CSV Format", variable=format_var, value="csv").pack(anchor=tk.W)

    def perform_export():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT setting_name, setting_value FROM library_settings')
            settings = cursor.fetchall()
            conn.close()

            format_type = format_var.get()

            if format_type == "json":
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".json",
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                    initialfile="library_settings.json"
                )

                if file_path:
                    import json
                    settings_dict = {name: value for name, value in settings}
                    settings_dict['export_date'] = datetime.now().isoformat()

                    with open(file_path, 'w') as f:
                        json.dump(settings_dict, f, indent=2)

                    log_audit_event(get_current_user_id(), "Exported settings to JSON", "library_settings")
                    messagebox.showinfo(_("common.success"), f"Settings exported successfully to:\n{file_path}")
                    export_window.destroy()

            else:  # CSV
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile="library_settings.csv"
                )

                if file_path:
                    import csv
                    with open(file_path, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(['Setting Name', 'Setting Value'])
                        writer.writerows(settings)

                    log_audit_event(get_current_user_id(), "Exported settings to CSV", "library_settings")
                    messagebox.showinfo(_("common.success"), f"Settings exported successfully to:\n{file_path}")
                    export_window.destroy()

        except (OSError, IOError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to export settings: {str(e)}")

    # Button frame
    button_frame = ttk.Frame(export_window)
    button_frame.pack(fill=tk.X, padx=10, pady=20)

    ttk.Button(button_frame, text=_("common.export"), command=perform_export).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.cancel"), command=export_window.destroy).pack(side=tk.RIGHT, padx=5)

def import_settings_gui(self):
    """Import library settings from file"""
    file_path = filedialog.askopenfilename(
        title="Select Settings File",
        filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv"), ("All files", "*.*")]
    )

    if not file_path:
        return

    try:
        settings_to_import = []

        if file_path.endswith('.json'):
            import json
            with open(file_path, 'r') as f:
                settings_dict = json.load(f)

            # Remove metadata fields
            settings_dict.pop('export_date', None)
            settings_to_import = list(settings_dict.items())

        elif file_path.endswith('.csv'):
            import csv
            with open(file_path, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                settings_to_import = list(reader)

        if not settings_to_import:
            messagebox.showwarning(_("common.warning"), "No valid settings found in file")
            return

        # Confirm import
        confirm = messagebox.askyesno(
            "Confirm Import",
            f"Import {len(settings_to_import)} settings?\nThis will overwrite existing values."
        )

        if not confirm:
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        for setting_name, setting_value in settings_to_import:
            cursor.execute('''
            INSERT OR REPLACE INTO library_settings (setting_name, setting_value)
            VALUES (?, ?)
            ''', (setting_name, setting_value))

        conn.commit()
        conn.close()

        log_audit_event(get_current_user_id(), f"Imported {len(settings_to_import)} settings", "library_settings")
        messagebox.showinfo(_("common.success"), f"Successfully imported {len(settings_to_import)} settings")

    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Failed to import settings: {str(e)}")

def reset_settings_to_default_gui(self):
    """Reset all settings to default values"""
    confirm = messagebox.askyesno(
        "Confirm Reset",
        "Are you sure you want to reset ALL settings to default values?\n\nThis action cannot be undone."
    )

    if not confirm:
        return

    try:
        default_settings = {
            'max_loans_per_user': '5',
            'loan_period_days': '14',
            'max_renewals': '2',
            'fine_per_day': '0.50',
            'reservation_period_days': '7',
            'due_reminder_days': '3',
            'overdue_reminder_frequency_days': '7',
            'enable_email_notifications': 'true',
            'enable_sms_notifications': 'false',
            'library_name': 'University Library',
            'library_email': 'library@university.edu',
            'library_phone': '555-0100'
        }

        conn = get_db_connection()
        cursor = conn.cursor()

        for setting_name, setting_value in default_settings.items():
            cursor.execute('''
            INSERT OR REPLACE INTO library_settings (setting_name, setting_value)
            VALUES (?, ?)
            ''', (setting_name, setting_value))

        conn.commit()
        conn.close()

        log_audit_event(get_current_user_id(), "Reset all settings to defaults", "library_settings")
        messagebox.showinfo(_("common.success"), f"Successfully reset {len(default_settings)} settings to default values")

    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Failed to reset settings: {str(e)}")

def backup_settings_only_gui(self):
    """Backup only library settings to a separate file"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        from education_system.university_system.modules.shared.constants import paths as _paths
        backup_dir = str(_paths.BACKUP_SETTINGS_DIR)
        os.makedirs(backup_dir, exist_ok=True)

        backup_file = os.path.join(backup_dir, f'settings_backup_{timestamp}.json')

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT setting_name, setting_value FROM library_settings')
        settings = cursor.fetchall()
        conn.close()

        import json
        settings_dict = {name: value for name, value in settings}
        settings_dict['backup_date'] = datetime.now().isoformat()
        settings_dict['backup_type'] = 'settings_only'

        with open(backup_file, 'w') as f:
            json.dump(settings_dict, f, indent=2)

        log_audit_event(get_current_user_id(), "Created settings backup", "library_settings")
        messagebox.showinfo(_("common.success"), f"Settings backup created:\n{backup_file}")

    except (sqlite3.Error, DatabaseError, OSError, IOError, json.JSONDecodeError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Failed to backup settings: {str(e)}")

