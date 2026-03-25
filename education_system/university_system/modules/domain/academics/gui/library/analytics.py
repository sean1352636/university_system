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

def show_advanced_analytics_gui(self):
    """Show advanced analytics dashboard"""
    analytics_window = tk.Toplevel(self.master)
    analytics_window.title("Library Analytics Dashboard")
    analytics_window.geometry("1200x800")

    # Title
    ttk.Label(analytics_window, text="Library Analytics Dashboard",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Notebook for different analytics
    notebook = ttk.Notebook(analytics_window)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Tab 1: Collection Overview
    overview_tab = ttk.Frame(notebook)
    notebook.add(overview_tab, text="Collection Overview")
    self._create_collection_overview(overview_tab)

    # Tab 2: Circulation Stats
    circulation_tab = ttk.Frame(notebook)
    notebook.add(circulation_tab, text="Circulation")
    self._create_circulation_stats(circulation_tab)

    # Tab 3: User Activity
    activity_tab = ttk.Frame(notebook)
    notebook.add(activity_tab, text="User Activity")
    self._create_user_activity(activity_tab)

    # Tab 4: Category Analysis
    category_tab = ttk.Frame(notebook)
    notebook.add(category_tab, text="Categories")
    self._create_category_analysis(category_tab)

    # Export button
    ttk.Button(analytics_window, text="Export Full Report",
              command=self.export_analytics_report).pack(pady=10)

def _create_collection_overview(self, parent):
    """Create collection overview tab"""
    # Store reference for refresh
    self.collection_overview_parent = parent

    # Add refresh button at top
    btn_frame = ttk.Frame(parent)
    btn_frame.pack(fill=tk.X, padx=20, pady=10)
    ttk.Button(btn_frame, text="🔄 Refresh Overview",
               command=self._refresh_collection_overview).pack(side=tk.RIGHT)

    # Create content frame that can be refreshed
    self.collection_overview_content = ttk.Frame(parent)
    self.collection_overview_content.pack(fill=tk.BOTH, expand=True)

    self._load_collection_overview_data()

def _refresh_collection_overview(self):
    """Refresh the collection overview data"""
    # Clear existing content
    for widget in self.collection_overview_content.winfo_children():
        widget.destroy()
    # Reload data
    self._load_collection_overview_data()

def _load_collection_overview_data(self):
    """Load collection overview data"""
    parent = self.collection_overview_content
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get stats
        cursor.execute('''
        SELECT
            COUNT(*) as total_books,
            SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
            SUM(CASE WHEN status = 'checked_out' THEN 1 ELSE 0 END) as checked_out,
            SUM(CASE WHEN status = 'reserved' THEN 1 ELSE 0 END) as reserved,
            SUM(CASE WHEN status IN ('lost', 'damaged') THEN 1 ELSE 0 END) as unavailable
        FROM books
        ''')

        stats = cursor.fetchone()
        total, available, checked_out, reserved, unavailable = stats

        # Get fine stats
        cursor.execute('''
        SELECT COUNT(*) as fine_count, COALESCE(SUM(fine_amount), 0) as total_fines
        FROM book_loans WHERE fine_amount > 0 AND status != 'returned'
        ''')
        fine_stats = cursor.fetchone()
        fine_count, total_fines = fine_stats

        # Display stats
        stats_frame = ttk.Frame(parent)
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Grid layout for stats cards
        cards = [
            ("Total Books", total, "#3498db"),
            ("Available", available, "#2ecc71"),
            ("Checked Out", checked_out, "#e74c3c"),
            ("Reserved", reserved, "#f39c12"),
            ("Unavailable", unavailable, "#95a5a6"),
            (f"Outstanding Fines", f"£{total_fines:.2f}", "#9b59b6")
        ]

        for idx, (label, value, color) in enumerate(cards):
            card = tk.Frame(stats_frame, bg=color, relief=tk.RAISED, borderwidth=2)
            card.grid(row=0, column=idx, padx=10, pady=10, sticky='nsew')

            tk.Label(card, text=str(value), font=('Arial', 24, 'bold'),
                    bg=color, fg='white').pack(pady=(20, 5))
            tk.Label(card, text=label, font=('Arial', 12),
                    bg=color, fg='white').pack(pady=(0, 20))

            stats_frame.grid_columnconfigure(idx, weight=1)

        # Recent additions
        cursor.execute('''
        SELECT title, author, added_date
        FROM books
        ORDER BY added_date DESC
        LIMIT 10
        ''')

        recent_frame = ttk.LabelFrame(parent, text="Recently Added Books", padding=10)
        recent_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        recent_tree = ttk.Treeview(recent_frame, columns=('Title', 'Author', 'Date'),
                                   show='headings', height=8)
        recent_tree.pack(fill=tk.BOTH, expand=True)

        for col in ('Title', 'Author', 'Date'):
            recent_tree.heading(col, text=col)
            recent_tree.column(col, width=200)

        for row in cursor.fetchall():
            recent_tree.insert('', 'end', values=row)

        conn.close()

    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        ttk.Label(parent, text=f"Error loading collection overview: {str(e)}").pack(pady=20)

def _create_circulation_stats(self, parent):
    """Create circulation statistics tab"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get circulation stats
        cursor.execute('''
        SELECT
            COUNT(*) as total_loans,
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_loans,
            SUM(CASE WHEN status = 'returned' THEN 1 ELSE 0 END) as returned_loans,
            SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) as overdue_loans,
            SUM(COALESCE(fine_amount, 0)) as total_fines
        FROM book_loans
        ''')

        stats = cursor.fetchone()

        # Display stats
        stats_text = f"""
Circulation Statistics:
━━━━━━━━━━━━━━━━━━━━━━
Total Loans: {stats[0]:,}
Active Loans: {stats[1]:,}
Returned Loans: {stats[2]:,}
Overdue Loans: {stats[3]:,}
Total Fines: ${stats[4]:.2f}
"""

        text_widget = ScrolledText(parent, height=30, width=80, font=('Courier', 11))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        text_widget.insert('1.0', stats_text)
        text_widget.config(state=tk.DISABLED)

        # Most checked out books
        cursor.execute('''
        SELECT b.title, b.author, COUNT(l.loan_id) as loan_count
        FROM books b
        JOIN book_loans l ON b.book_id = l.book_id
        GROUP BY b.book_id
        ORDER BY loan_count DESC
        LIMIT 10
        ''')

        popular_text = "\n\nMost Popular Books:\n" + "━" * 60 + "\n"
        for idx, (title, author, count) in enumerate(cursor.fetchall(), 1):
            popular_text += f"{idx}. {title} by {author} ({count} loans)\n"

        text_widget.config(state=tk.NORMAL)
        text_widget.insert(tk.END, popular_text)
        text_widget.config(state=tk.DISABLED)

        conn.close()

    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        ttk.Label(parent, text=f"Error loading circulation stats: {str(e)}").pack(pady=20)

def _create_user_activity(self, parent):
    """Create user activity tab"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Most active users
        cursor.execute('''
        SELECT user_id, COUNT(loan_id) as loan_count
        FROM book_loans
        GROUP BY user_id
        ORDER BY loan_count DESC
        LIMIT 20
        ''')

        activity_frame = ttk.LabelFrame(parent, text="Most Active Users", padding=10)
        activity_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tree = ttk.Treeview(activity_frame, columns=('User ID', 'Loan Count'),
                           show='headings', height=15)
        tree.pack(fill=tk.BOTH, expand=True)

        tree.heading('User ID', text='User ID')
        tree.heading('Loan Count', text='Total Loans')
        tree.column('User ID', width=300)
        tree.column('Loan Count', width=150)

        for row in cursor.fetchall():
            tree.insert('', 'end', values=row)

        conn.close()

    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        ttk.Label(parent, text=f"Error loading user activity: {str(e)}").pack(pady=20)

def _create_category_analysis(self, parent):
    """Create category analysis tab"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Books by category
        cursor.execute('''
        SELECT category, COUNT(*) as book_count,
               SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available_count
        FROM books
        GROUP BY category
        ORDER BY book_count DESC
        ''')

        category_frame = ttk.LabelFrame(parent, text="Books by Category", padding=10)
        category_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tree = ttk.Treeview(category_frame, columns=('Category', 'Total', 'Available'),
                           show='headings', height=20)
        tree.pack(fill=tk.BOTH, expand=True)

        for col in ('Category', 'Total', 'Available'):
            tree.heading(col, text=col)
            tree.column(col, width=200)

        for row in cursor.fetchall():
            tree.insert('', 'end', values=row)

        conn.close()

    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        ttk.Label(parent, text=f"Error loading category analysis: {str(e)}").pack(pady=20)

def export_analytics_report(self):
    """Export comprehensive analytics report"""
    try:
        import pandas as pd

        # Ask for save location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )

        if not file_path:
            return

        conn = get_db_connection()

        # Create Excel writer
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # Collection overview
            df_books = pd.read_sql_query("SELECT * FROM books", conn)
            df_books.to_excel(writer, sheet_name='All Books', index=False)

            # Loans
            df_loans = pd.read_sql_query("SELECT * FROM book_loans", conn)
            df_loans.to_excel(writer, sheet_name='Loans', index=False)

            # Statistics
            stats_data = {
                'Metric': ['Total Books', 'Available', 'Checked Out', 'Overdue'],
                'Count': [len(df_books),
                         len(df_books[df_books['status'] == 'available']),
                         len(df_books[df_books['status'] == 'checked_out']),
                         len(df_loans[df_loans['status'] == 'overdue'])]
            }
            df_stats = pd.DataFrame(stats_data)
            df_stats.to_excel(writer, sheet_name='Statistics', index=False)

        conn.close()
        messagebox.showinfo(_("common.success"), f"Analytics report exported to:\n{file_path}")

    except ImportError:
        messagebox.showerror(_("common.error"), "pandas and openpyxl are required for export.")
    except (OSError, IOError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Export failed: {str(e)}")

