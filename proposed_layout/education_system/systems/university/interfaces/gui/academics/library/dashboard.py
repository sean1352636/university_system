"""
Enhanced Library Management System - GUI Version
Maintains all original CLI functions while adding a modern GUI interface
Backwards compatible with existing database and auth systems
"""


import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from education_system.systems.university.infrastructure.i18n import get_text as _, init_i18n
init_i18n()
from tkinter.scrolledtext import ScrolledText
import threading
import queue
import os
import sys
from datetime import datetime, timedelta
import json
from education_system.systems.university.infrastructure.database.db import sqlite3
from typing import Dict, List, Optional, Any
import logging
import urllib.request
import urllib.parse
import urllib.error

# Import custom exceptions for better error handling
from education_system.systems.university.infrastructure.exceptions import (
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
    from education_system.systems.university.domain.academics.services.library.settings import (
        auth, get_current_user_id, set_auth, get_library_settings, update_library_setting
    )
    from education_system.systems.university.domain.academics.services.library.menu import display_library_menu
    from education_system.systems.university.domain.academics.services.library.barcode import (
        generate_barcode, generate_qr_code, process_scanned_barcode
    )
    from education_system.systems.university.domain.academics.services.library.reports import (
        generate_circulation_report, generate_library_statistics_export, generate_user_activity_report
    )
    from education_system.systems.university.domain.academics.services.library.database import (
        get_db_connection, init_library_db, log_audit_event
    )
    from education_system.systems.university.domain.academics.services.library.backup import (
        quick_system_health_check, restore_from_backup
    )
    from education_system.systems.university.domain.academics.services.library.reading_lists import view_reading_list_details
    ORIGINAL_LIBRARY_AVAILABLE = True
except ImportError:
    print("Warning: Original library module not found. GUI will use standalone functions.")
    ORIGINAL_LIBRARY_AVAILABLE = False

# Import shared authentication system
try:
    from education_system.systems.university.infrastructure.auth import UserAuth
    from education_system.systems.university.infrastructure.shared_context import get_auth, get_current_user
    SHARED_AUTH_AVAILABLE = True
except ImportError:
    print("Warning: Shared authentication system not found.")
    SHARED_AUTH_AVAILABLE = False
    # Provide fallback functions
    def get_auth():
        return None
    def get_current_user():
        return None

from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.infrastructure.utils.finance_integration import (
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
    from education_system.systems.university.infrastructure.email.email_service import send_email_as_system
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    def send_email_as_system(*args, **kwargs):
        return False
    print("Warning: Email service not available for library finance")

_AUDIT_LOG_COLUMNS_CACHE: Optional[List[str]] = None
_STUDENT_COLUMNS_CACHE: Optional[List[str]] = None

from education_system.systems.university.interfaces.gui.academics.library.base import LibraryGUI

def show_dashboard(self):
    """Show the main dashboard"""
    # Dashboard is always available - auth checks happen at action level

    self.clear_content_area()

    dashboard_frame = ttk.Frame(self.notebook)
    self.notebook.add(dashboard_frame, text=_("library.tabs.dashboard"))

    # Create dashboard content
    title_label = ttk.Label(dashboard_frame, text=_("library.dashboard.title"), style='Title.TLabel')
    title_label.pack(pady=10)

    # Statistics frame
    stats_frame = ttk.LabelFrame(dashboard_frame, text=_("library.dashboard.statistics"))
    stats_frame.pack(fill=tk.X, padx=10, pady=5)

    # Create statistics display
    self.create_statistics_display(stats_frame)

    # Quick actions frame
    actions_frame = ttk.LabelFrame(dashboard_frame, text=_("library.dashboard.quick_actions"))
    actions_frame.pack(fill=tk.X, padx=10, pady=5)

    # Quick action buttons
    quick_actions = [
        (_("library.buttons.add_new_book"), self.show_add_book),
        (_("library.buttons.search_books"), self.show_search_books),
        (_("library.buttons.checkout_book"), self.show_checkout),
        (_("library.buttons.return_book"), self.show_return),
        (_("library.buttons.library_finance"), self.open_library_finance),
        (_("library.buttons.view_loan_history"), self.view_loan_history_gui),
        (_("library.buttons.generate_barcodes"), self.show_barcode_generator),
        (_("library.buttons.system_maintenance"), self.library_maintenance_gui),
        (_("library.buttons.system_health_check"), self.quick_system_health_check),
        (_("library.buttons.view_reports"), self.show_reports),
        (_("library.buttons.system_settings"), self.show_settings)
    ]

    button_frame = ttk.Frame(actions_frame)
    button_frame.pack(pady=10)

    for i, (text, command) in enumerate(quick_actions):
        btn = ttk.Button(button_frame, text=text, command=command, width=20)
        btn.grid(row=i//3, column=i%3, padx=5, pady=5)

    # Recent activity frame
    activity_frame = ttk.LabelFrame(dashboard_frame, text=_("library.dashboard.recent_activity"))
    activity_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    self.create_activity_display(activity_frame)

def create_statistics_display(self, parent):
    """Create the statistics display"""
    # This would integrate with your existing analytics functions
    stats_text = ScrolledText(parent, height=6, wrap=tk.WORD)
    stats_text.pack(fill=tk.BOTH, padx=10, pady=10)

    # Get statistics data
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            # Use existing statistics functions
            stats_data = self.get_library_statistics()
            stats_text.insert(tk.END, stats_data)
        else:
            stats_text.insert(tk.END, _("library.messages.stats_placeholder"))
    except tk.TclError as e:
        stats_text.insert(tk.END, _("library.messages.error_loading_statistics").format(error=str(e)))

    stats_text.config(state=tk.DISABLED)

def get_library_statistics(self):
    """Get library statistics data"""
    try:
        conn = get_db_connection()
        if not conn:
            return _("library.messages.db_connection_unavailable")

        cursor = conn.cursor()

        # Get basic statistics
        cursor.execute('SELECT COUNT(*) FROM books')
        total_books = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM books WHERE status = "available"')
        available_books = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status IN ("active", "overdue")')
        active_loans = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status = "overdue"')
        overdue_books = cursor.fetchone()[0]

        conn.close()

        availability_pct = (available_books / total_books * 100) if total_books else 0.0
        overdue_pct = (overdue_books / active_loans * 100) if active_loans else 0.0

        stats = _("library.stats.collection_overview").format(
            total_books=f"{total_books:,}",
            available=f"{available_books:,}",
            checked_out=f"{active_loans:,}",
            overdue=f"{overdue_books:,}",
            availability_pct=f"{availability_pct:.1f}",
            overdue_pct=f"{overdue_pct:.1f}"
        )

        return stats

    except (sqlite3.Error, DatabaseError) as e:
        return _("library.messages.error_retrieving_statistics").format(error=str(e))

def create_activity_display(self, parent):
    """Create the recent activity display"""
    activity_text = ScrolledText(parent, height=8, wrap=tk.WORD)
    activity_text.pack(fill=tk.BOTH, padx=10, pady=10)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            activity_data = self.get_recent_activity()
            activity_text.insert(tk.END, activity_data)
        else:
            activity_text.insert(tk.END, _("library.messages.activity_placeholder"))
    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        activity_text.insert(tk.END, _("library.messages.error_loading_activity").format(error=str(e)))

    activity_text.config(state=tk.DISABLED)

def get_recent_activity(self):
    """Get recent activity data"""
    try:
        conn = get_db_connection()
        if not conn:
            return _("library.messages.db_connection_unavailable")

        cursor = conn.cursor()

        # Get recent audit log entries
        audit_columns = self._get_audit_log_columns(cursor)
        has_success = 'success' in audit_columns

        select_fields = "user_id, action, timestamp"
        if has_success:
            select_fields += ", success"

        cursor.execute('''
            SELECT ''' + select_fields + '''
            FROM audit_log
            WHERE timestamp >= datetime('now', '-24 hours')
            ORDER BY timestamp DESC
            LIMIT 10
        ''')

        raw_rows = cursor.fetchall()
        conn.close()

        if not raw_rows:
            return _("library.messages.no_recent_activity")

        activity_text = _("library.activity.header") + "\n\n"
        for row in raw_rows:
            user_id, action, timestamp = row[:3]
            success_val = row[3] if has_success and len(row) > 3 else None
            status = "✅" if success_val is None or bool(success_val) else "❌"
            activity_text += f"{status} {timestamp[:16]} - {user_id}: {action}\n"

        return activity_text

    except (sqlite3.Error, DatabaseError) as e:
        return _("library.messages.error_retrieving_activity").format(error=str(e))

def _get_audit_log_columns(self, cursor):
    """Return cached audit_log column names."""
    global _AUDIT_LOG_COLUMNS_CACHE
    if _AUDIT_LOG_COLUMNS_CACHE is None:
        cursor.execute("PRAGMA table_info(audit_log)")
        _AUDIT_LOG_COLUMNS_CACHE = [row[1] for row in cursor.fetchall()]
    return _AUDIT_LOG_COLUMNS_CACHE

def _get_student_columns(self):
    """Return cached student table column names."""
    global _STUDENT_COLUMNS_CACHE
    if _STUDENT_COLUMNS_CACHE is None:
        try:
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("PRAGMA table_info(students)")
                _STUDENT_COLUMNS_CACHE = [row[1] for row in cur.fetchall()]
                conn.close()
            else:
                _STUDENT_COLUMNS_CACHE = []
        except (sqlite3.Error, DatabaseError):
            _STUDENT_COLUMNS_CACHE = []
    return _STUDENT_COLUMNS_CACHE

def show_statistics_dashboard(self):
    """Show statistics dashboard"""
    self.report_text.delete("1.0", tk.END)

    try:
        stats_data = self.get_library_statistics()
        self.report_text.insert(tk.END, stats_data)
    except (tk.TclError, ValueError, TypeError) as e:
        self.report_text.insert(tk.END, f"Error loading statistics: {str(e)}")

