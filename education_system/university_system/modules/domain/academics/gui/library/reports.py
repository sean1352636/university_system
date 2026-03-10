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

from .base import LibraryGUI

def show_reports(self):
    """Show reports interface"""
    if not self.check_permission('view_reports'):
        return

    self.clear_content_area()

    reports_frame = ttk.Frame(self.notebook)
    self.notebook.add(reports_frame, text="Reports")

    title_label = ttk.Label(reports_frame, text="Library Reports", style='Title.TLabel')
    title_label.pack(pady=10)

    # Report types
    report_types = [
        ("Collection Overview", self.generate_collection_report),
        ("Circulation Summary", self.generate_circulation_report),
        ("Overdue Books", self.generate_overdue_report),
        ("User Activity", self.generate_user_activity_report),
        ("Popular Books", self.generate_popular_books_report),
        ("Statistics Dashboard", self.show_statistics_dashboard),
        ("Fine Collection Report", self.generate_fine_report),
        ("Library Card Usage Report", self.generate_card_usage_report), 
        ("System Health Report", self.generate_health_report),
        ("Maintenance Activity Report", self.generate_maintenance_report)
    ]

    # Create report buttons
    buttons_frame = ttk.Frame(reports_frame)
    buttons_frame.pack(pady=20)

    for i, (report_name, command) in enumerate(report_types):
        row = i // 2
        col = i % 2

        btn = ttk.Button(buttons_frame, text=report_name, command=command, width=25)
        btn.grid(row=row, column=col, padx=10, pady=5)

    # Report display area
    display_frame = ttk.LabelFrame(reports_frame, text=_("library.frames.report_output"))
    display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    self.report_text = ScrolledText(display_frame, wrap=tk.WORD)
    self.report_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Report action buttons
    action_button_frame = ttk.Frame(display_frame)
    action_button_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Button(action_button_frame, text="🔍 Open in New Window",
              command=self.open_current_report_window).pack(side=tk.LEFT, padx=5)
    ttk.Button(action_button_frame, text="📧 Email Report to Admin",
              command=self.email_report_to_admin).pack(side=tk.LEFT, padx=5)
    ttk.Button(action_button_frame, text="💾 Save Report to File",
              command=self.save_report_to_file).pack(side=tk.LEFT, padx=5)

def generate_collection_report(self):
    """Generate collection overview report"""
    self.report_text.delete("1.0", tk.END)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            report_data = self.get_collection_report_data()
        else:
            report_data = "DEMO COLLECTION REPORT\n" + "="*50 + "\nTotal Books: 150\nAvailable: 120\nChecked Out: 25\nDamaged: 5"

        self.report_text.insert(tk.END, report_data)

    except (OSError, IOError, tk.TclError) as e:
        self.report_text.insert(tk.END, f"Error generating report: {str(e)}")

def _show_report_message(self, title: str, body: str):
    """Utility to display a formatted report message."""
    self.report_text.delete("1.0", tk.END)
    self.report_text.insert(tk.END, f"{title}\n{'=' * len(title)}\n\n{body}")

def _show_report_not_available(self, title: str):
    """Notify users that a requested report is not yet implemented."""
    self._show_report_message(
        title,
        "This report is not yet available in the GUI. Please use the CLI workflow or check back after the next release."
    )

def get_collection_report_data(self):
    """Get collection report data"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Database connection unavailable"

        cursor = conn.cursor()

        # Collection statistics
        cursor.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
            SUM(CASE WHEN status = 'checked_out' THEN 1 ELSE 0 END) as checked_out,
            SUM(CASE WHEN status = 'reserved' THEN 1 ELSE 0 END) as reserved,
            SUM(CASE WHEN status = 'damaged' THEN 1 ELSE 0 END) as damaged,
            SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END) as lost
        FROM books
        ''')

        stats = cursor.fetchone()

        # Category breakdown
        cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM books
        GROUP BY category
        ORDER BY count DESC
        ''')

        categories = cursor.fetchall()

        conn.close()

        # Format report
        report = "LIBRARY COLLECTION REPORT\n"
        report += "="*50 + "\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        report += "OVERALL STATISTICS:\n"
        report += f"Total Books: {stats[0]:,}\n"
        report += f"Available: {stats[1]:,}\n"
        report += f"Checked Out: {stats[2]:,}\n"
        report += f"Reserved: {stats[3]:,}\n"
        report += f"Damaged: {stats[4]:,}\n"
        report += f"Lost: {stats[5]:,}\n\n"

        report += "CATEGORY BREAKDOWN:\n"
        report += "-"*30 + "\n"
        for category, count in categories:
            report += f"{category}: {count:,}\n"

        return report

    except (sqlite3.Error, DatabaseError) as e:
        return f"Error generating collection report: {str(e)}"

def generate_circulation_report(self):
    """Generate circulation report"""
    self.report_text.delete("1.0", tk.END)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            report_data = self.get_circulation_report_data()
        else:
            report_data = "DEMO CIRCULATION REPORT\n" + "="*50 + "\nActive Loans: 25\nReturns Today: 8\nOverdue: 3"

        self.report_text.insert(tk.END, report_data)

    except (tk.TclError, ValueError, TypeError) as e:
        self.report_text.insert(tk.END, f"Error generating report: {str(e)}")

def get_circulation_report_data(self):
    """Get circulation report data"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Database connection unavailable"

        cursor = conn.cursor()

        # Current circulation
        cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status IN ("active", "overdue")')
        active_loans = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status = "overdue"')
        overdue_loans = cursor.fetchone()[0]

        # Today's activity
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('SELECT COUNT(*) FROM book_loans WHERE date(checkout_date) = ?', (today,))
        today_checkouts = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM book_loans WHERE date(return_date) = ?', (today,))
        today_returns = cursor.fetchone()[0]

        # Monthly stats
        cursor.execute('''
        SELECT COUNT(*) FROM book_loans 
        WHERE checkout_date >= date('now', '-30 days')
        ''', )
        monthly_checkouts = cursor.fetchone()[0]

        conn.close()

        report = "CIRCULATION REPORT\n"
        report += "="*50 + "\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        report += "CURRENT STATUS:\n"
        report += f"Active Loans: {active_loans:,}\n"
        report += f"Overdue Items: {overdue_loans:,}\n"

        report += f"\nTODAY'S ACTIVITY:\n"
        report += f"Checkouts: {today_checkouts:,}\n"
        report += f"Returns: {today_returns:,}\n"

        report += f"\nMONTHLY SUMMARY:\n"
        report += f"Checkouts (30 days): {monthly_checkouts:,}\n"

        return report

    except (sqlite3.Error, DatabaseError) as e:
        return f"Error generating circulation report: {str(e)}"

def generate_overdue_report(self):
    """Generate overdue books report"""
    self.report_text.delete("1.0", tk.END)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            report_data = self.get_overdue_report_data()
        else:
            report_data = "DEMO OVERDUE REPORT\n" + "="*50 + "\nNo overdue books in demo mode"

        self.report_text.insert(tk.END, report_data)

    except (tk.TclError, ValueError, TypeError) as e:
        self.report_text.insert(tk.END, f"Error generating report: {str(e)}")

def get_overdue_report_data(self):
    """Get overdue books report data"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Database connection unavailable"

        cursor = conn.cursor()

        cursor.execute('''
        SELECT bl.user_id, bl.book_id, b.title, bl.due_date,
               julianday('now') - julianday(bl.due_date) as days_overdue,
               bl.fine_amount
        FROM book_loans bl
        JOIN books b ON bl.book_id = b.book_id
        WHERE bl.status = 'overdue'
        ORDER BY days_overdue DESC
        ''')

        overdue_books = cursor.fetchall()
        conn.close()

        report = "OVERDUE BOOKS REPORT\n"
        report += "="*50 + "\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        if not overdue_books:
            report += "No overdue books found.\n"
        else:
            report += f"Total Overdue Items: {len(overdue_books)}\n\n"
            report += f"{'User ID':<12} {'Book ID':<10} {'Days':<5} {'Fine':<8} {'Title':<30}\n"
            report += "-"*70 + "\n"

            total_fines = 0
            for book in overdue_books:
                user_id, book_id, title, due_date, days_overdue, fine = book
                fine_amount = fine if fine else 0
                total_fines += fine_amount
                title_display = title[:27] + "..." if len(title) > 30 else title

                report += f"{user_id:<12} {book_id:<10} {int(days_overdue):<5} ${fine_amount:<7.2f} {title_display:<30}\n"

            report += "-"*70 + "\n"
            report += f"Total Outstanding Fines: ${total_fines:.2f}\n"

        return report

    except (ValueError, TypeError) as e:
        return f"Error generating overdue report: {str(e)}"

def generate_user_activity_report(self):
    """Generate user activity report"""
    self._show_report_message(
        "User Activity Report",
        "This report will highlight active borrowers, engagement trends, and reservation patterns."
    )

def generate_popular_books_report(self):
    """Generate popular books report"""
    self._show_report_message(
        "Popular Books Report",
        "This report will list the most borrowed titles, trending categories, and recommendations once analytics is enabled."
    )

def generate_fine_report(self):
    """Generate outstanding fines report."""
    if not ORIGINAL_LIBRARY_AVAILABLE:
        self._show_report_message(
            "Fine Collection Report",
            "Demo mode: fines reporting is available only when the library database is connected."
        )
        return

    try:
        conn = get_db_connection()
        if not conn:
            raise RuntimeError("Database connection unavailable")

        cursor = conn.cursor()
        student_columns = self._get_student_columns()
        grade_sql = ', s.grade_level' if 'grade_level' in student_columns else ''
        cursor.execute('''
            SELECT bl.user_id,
                   COALESCE(s.first_name || ' ' || s.last_name, 'Unknown') AS full_name,
                   SUM(COALESCE(bl.fine_amount, 0)) AS total_fines,
                   COUNT(*) AS fine_items,
                   MAX(bl.due_date) AS latest_due,
                   s.email_address''' + grade_sql + '''
            FROM book_loans bl
            LEFT JOIN students s ON bl.user_id = s.student_id
            WHERE bl.fine_amount > 0 AND bl.status != 'returned'
            GROUP BY bl.user_id
            ORDER BY total_fines DESC
        ''')

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            self._show_report_message("Fine Collection Report", "No outstanding fines were found.")
            return

        title = "Fine Collection Report"
        lines = [title, "=" * len(title), ""]
        grand_total = 0.0

        for row in rows:
            user_id, full_name, total_fines, item_count, latest_due = row[:5]
            email = row[5] if len(row) > 5 else None
            grade_value = row[6] if len(row) > 6 else None

            amount = total_fines or 0.0
            grand_total += amount

            lines.append(f"User: {user_id} ({full_name})")
            if grade_value:
                lines.append(f"Grade: {grade_value}")
            if email:
                lines.append(f"Contact: {email}")
            lines.append(f"Outstanding Items: {item_count}")
            lines.append(f"Total Due: ${amount:.2f}")
            lines.append(f"Most Recent Due Date: {latest_due or 'N/A'}")
            lines.append("-")

        lines.append("")
        lines.append(f"Grand Total Outstanding Fines: ${grand_total:.2f}")

        self.report_text.delete("1.0", tk.END)
        self.report_text.insert(tk.END, "\n".join(lines))

    except tk.TclError as e:
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert(tk.END, f"Error generating fine report: {str(e)}")

def generate_card_usage_report(self):
    """Generate library card usage report showing borrowing patterns."""
    if not ORIGINAL_LIBRARY_AVAILABLE:
        self._show_report_message(
            "Library Card Usage Report",
            "Demo mode: card usage reporting is available only when the library database is connected."
        )
        return

    try:
        conn = get_db_connection()
        if not conn:
            raise RuntimeError("Database connection unavailable")

        cursor = conn.cursor()

        # Get top active borrowers
        cursor.execute('''
            SELECT bl.user_id,
                   COUNT(*) as total_loans,
                   SUM(CASE WHEN bl.status = 'active' THEN 1 ELSE 0 END) as active_loans,
                   SUM(CASE WHEN bl.status = 'returned' THEN 1 ELSE 0 END) as returned_loans,
                   SUM(CASE WHEN bl.status = 'overdue' THEN 1 ELSE 0 END) as overdue_loans,
                   MAX(bl.checkout_date) as last_checkout
            FROM book_loans bl
            GROUP BY bl.user_id
            ORDER BY total_loans DESC
            LIMIT 20
        ''')

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            self._show_report_message("Library Card Usage Report", "No card usage data found.")
            return

        title = "Library Card Usage Report"
        lines = [title, "=" * len(title), ""]
        lines.append("Top 20 Active Library Card Holders")
        lines.append("-" * 60)

        for row in rows:
            user_id, total, active, returned, overdue, last_checkout = row
            lines.append(f"\nUser ID: {user_id}")
            lines.append(f"  Total Loans: {total}")
            lines.append(f"  Active: {active} | Returned: {returned} | Overdue: {overdue}")
            lines.append(f"  Last Checkout: {last_checkout[:10] if last_checkout else 'N/A'}")

        lines.append("\n" + "=" * 60)
        lines.append(f"Total Unique Users: {len(rows)}")

        self.report_text.delete("1.0", tk.END)
        self.report_text.insert(tk.END, "\n".join(lines))

    except tk.TclError as e:
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert(tk.END, f"Error generating card usage report: {str(e)}")

def generate_health_report(self):
    """Generate library system health report showing overall status."""
    if not ORIGINAL_LIBRARY_AVAILABLE:
        self._show_report_message(
            "System Health Report",
            "Demo mode: health reporting is available only when the library database is connected."
        )
        return

    try:
        conn = get_db_connection()
        if not conn:
            raise RuntimeError("Database connection unavailable")

        cursor = conn.cursor()

        # Get overall statistics
        cursor.execute('SELECT COUNT(*) FROM books')
        total_books = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM books WHERE status = 'available'")
        available_books = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM books WHERE status = 'checked_out'")
        checked_out = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM books WHERE status = 'damaged'")
        damaged = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM book_loans WHERE status = 'active'")
        active_loans = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM book_loans WHERE status = 'overdue'")
        overdue_loans = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM book_reservations WHERE status = 'active'")
        active_reservations = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(fine_amount) FROM book_loans WHERE status != 'returned' AND fine_amount > 0")
        outstanding_fines = cursor.fetchone()[0] or 0.0

        conn.close()

        # Calculate health metrics
        availability_rate = (available_books / total_books * 100) if total_books > 0 else 0
        damage_rate = (damaged / total_books * 100) if total_books > 0 else 0
        overdue_rate = (overdue_loans / active_loans * 100) if active_loans > 0 else 0

        # Determine system health status
        if availability_rate > 70 and damage_rate < 5 and overdue_rate < 10:
            health_status = "EXCELLENT"
            status_symbol = "✓"
        elif availability_rate > 50 and damage_rate < 10 and overdue_rate < 20:
            health_status = "GOOD"
            status_symbol = "○"
        elif availability_rate > 30:
            health_status = "FAIR"
            status_symbol = "△"
        else:
            health_status = "NEEDS ATTENTION"
            status_symbol = "⚠"

        title = "Library System Health Report"
        lines = [title, "=" * len(title), ""]
        lines.append(f"System Status: {status_symbol} {health_status}")
        lines.append("")
        lines.append("=" * 60)
        lines.append("COLLECTION HEALTH")
        lines.append("-" * 60)
        lines.append(f"Total Books: {total_books}")
        lines.append(f"Available: {available_books} ({availability_rate:.1f}%)")
        lines.append(f"Checked Out: {checked_out}")
        lines.append(f"Damaged: {damaged} ({damage_rate:.1f}%)")
        lines.append("")
        lines.append("=" * 60)
        lines.append("CIRCULATION HEALTH")
        lines.append("-" * 60)
        lines.append(f"Active Loans: {active_loans}")
        lines.append(f"Overdue Loans: {overdue_loans} ({overdue_rate:.1f}%)")
        lines.append(f"Active Reservations: {active_reservations}")
        lines.append(f"Outstanding Fines: ${outstanding_fines:.2f}")
        lines.append("")
        lines.append("=" * 60)
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 60)

        if damage_rate > 5:
            lines.append("⚠ High damage rate - Review book handling procedures")
        if overdue_rate > 15:
            lines.append("⚠ High overdue rate - Consider sending reminder emails")
        if availability_rate < 50:
            lines.append("⚠ Low availability - Consider acquiring more copies of popular titles")
        if outstanding_fines > 500:
            lines.append("⚠ High outstanding fines - Follow up with borrowers")

        if not any("⚠" in line for line in lines[-4:]):
            lines.append("✓ All metrics are within healthy ranges")

        self.report_text.delete("1.0", tk.END)
        self.report_text.insert(tk.END, "\n".join(lines))

    except tk.TclError as e:
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert(tk.END, f"Error generating health report: {str(e)}")

def generate_maintenance_report(self):
    """Generate maintenance report showing books needing attention."""
    if not ORIGINAL_LIBRARY_AVAILABLE:
        self._show_report_message(
            "Maintenance Activity Report",
            "Demo mode: maintenance reporting is available only when the library database is connected."
        )
        return

    try:
        conn = get_db_connection()
        if not conn:
            raise RuntimeError("Database connection unavailable")

        cursor = conn.cursor()

        # Get damaged books
        cursor.execute('''
            SELECT book_id, title, author, status, condition_notes
            FROM books
            WHERE status = 'damaged' OR condition_notes IS NOT NULL
            ORDER BY last_updated DESC
        ''')
        damaged_books = cursor.fetchall()

        # Get frequently loaned books (high wear candidates)
        cursor.execute('''
            SELECT b.book_id, b.title, b.author, COUNT(*) as loan_count
            FROM books b
            JOIN book_loans bl ON b.book_id = bl.book_id
            GROUP BY b.book_id
            HAVING loan_count > 10
            ORDER BY loan_count DESC
            LIMIT 15
        ''')
        high_usage_books = cursor.fetchall()

        # Get books with missing information
        cursor.execute('''
            SELECT book_id, title, author,
                   CASE
                       WHEN isbn IS NULL OR isbn = '' THEN 'Missing ISBN; '
                       ELSE ''
                   END ||
                   CASE
                       WHEN location IS NULL OR location = '' THEN 'Missing Location; '
                       ELSE ''
                   END ||
                   CASE
                       WHEN category IS NULL OR category = '' THEN 'Missing Category; '
                       ELSE ''
                   END as issues
            FROM books
            WHERE (isbn IS NULL OR isbn = '')
               OR (location IS NULL OR location = '')
               OR (category IS NULL OR category = '')
            LIMIT 20
        ''')
        incomplete_records = cursor.fetchall()

        conn.close()

        title = "Library Maintenance Report"
        lines = [title, "=" * len(title), ""]

        # Damaged Books Section
        lines.append("=" * 60)
        lines.append("DAMAGED BOOKS REQUIRING ATTENTION")
        lines.append("-" * 60)

        if damaged_books:
            for book_id, title_text, author, status, notes in damaged_books:
                lines.append(f"\n⚠ Book ID: {book_id}")
                lines.append(f"  Title: {title_text}")
                lines.append(f"  Author: {author}")
                lines.append(f"  Status: {status}")
                if notes:
                    lines.append(f"  Notes: {notes}")
        else:
            lines.append("✓ No damaged books found")

        # High Usage Books Section
        lines.append("\n" + "=" * 60)
        lines.append("HIGH USAGE BOOKS (Inspection Recommended)")
        lines.append("-" * 60)

        if high_usage_books:
            for book_id, title_text, author, loan_count in high_usage_books:
                lines.append(f"\n○ Book ID: {book_id}")
                lines.append(f"  Title: {title_text}")
                lines.append(f"  Author: {author}")
                lines.append(f"  Total Loans: {loan_count}")
        else:
            lines.append("✓ No high usage books to report")

        # Incomplete Records Section
        lines.append("\n" + "=" * 60)
        lines.append("INCOMPLETE BOOK RECORDS")
        lines.append("-" * 60)

        if incomplete_records:
            for book_id, title_text, author, issues in incomplete_records:
                lines.append(f"\n△ Book ID: {book_id}")
                lines.append(f"  Title: {title_text}")
                lines.append(f"  Author: {author}")
                lines.append(f"  Issues: {issues.strip()}")
        else:
            lines.append("✓ All book records are complete")

        # Summary
        lines.append("\n" + "=" * 60)
        lines.append("MAINTENANCE SUMMARY")
        lines.append("-" * 60)
        lines.append(f"Damaged Books: {len(damaged_books)}")
        lines.append(f"High Usage Books: {len(high_usage_books)}")
        lines.append(f"Incomplete Records: {len(incomplete_records)}")
        lines.append(f"Total Items Requiring Attention: {len(damaged_books) + len(incomplete_records)}")

        self.report_text.delete("1.0", tk.END)
        self.report_text.insert(tk.END, "\n".join(lines))

    except tk.TclError as e:
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert(tk.END, f"Error generating maintenance report: {str(e)}")

def email_report_to_admin(self):
    """Email current report to administrator."""
    report_content = self.report_text.get("1.0", tk.END).strip()

    if not report_content or report_content == "":
        messagebox.showwarning("No Report", "Please generate a report first before emailing.")
        return

    try:
        # Get admin email from database
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_("common.error"), "Database connection unavailable")
            return

        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE role = 'admin' LIMIT 1")
        admin = cursor.fetchone()
        conn.close()

        if not admin or not admin[0]:
            messagebox.showerror(_("common.error"), "No admin email address found in database")
            return

        admin_email = admin[0]

        # Create email dialog
        dialog = tk.Toplevel(self.master)
        dialog.title("Email Report")
        dialog.geometry("500x350")
        dialog.transient(self.master)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Email Library Report", font=('Arial', 12, 'bold')).pack(pady=10)

        # Recipient
        recipient_frame = ttk.Frame(main_frame)
        recipient_frame.pack(fill=tk.X, pady=5)
        ttk.Label(recipient_frame, text="To:").pack(side=tk.LEFT, padx=5)
        recipient_entry = ttk.Entry(recipient_frame, width=40)
        recipient_entry.insert(0, admin_email)
        recipient_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Subject
        subject_frame = ttk.Frame(main_frame)
        subject_frame.pack(fill=tk.X, pady=5)
        ttk.Label(subject_frame, text="Subject:").pack(side=tk.LEFT, padx=5)
        subject_entry = ttk.Entry(subject_frame, width=40)
        subject_entry.insert(0, "Library Report - " + datetime.now().strftime('%Y-%m-%d'))
        subject_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Message
        ttk.Label(main_frame, text="Additional Message:").pack(anchor='w', padx=5, pady=(10, 0))
        message_text = ScrolledText(main_frame, height=8, wrap=tk.WORD)
        message_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        message_text.insert(tk.END, "Please find the library report below:\n\n")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        def send_email():
            try:
                recipient = recipient_entry.get().strip()
                subject = subject_entry.get().strip()
                message = message_text.get("1.0", tk.END).strip()

                if not recipient or not subject:
                    messagebox.showwarning("Missing Information", "Please provide recipient and subject")
                    return

                # Render email from template
                from education_system.university_system.infrastructure.email.template_utils import render_template
                from education_system.university_system.infrastructure.email.email_service import send_email as send_email_service

                template_subject, template_body = render_template('library/custom_report', {
                    'report_date': datetime.now().strftime('%Y-%m-%d'),
                    'custom_message': message,
                    'separator': '='*60,
                    'report_content': report_content
                })

                # Use template if available, otherwise use direct format
                if template_subject and template_body:
                    final_subject = subject  # Use user-provided subject
                    final_body = template_body
                else:
                    final_subject = subject
                    final_body = f"{message}\n\n{'='*60}\n{report_content}\n{'='*60}"

                send_email_service(
                    recipient_email=recipient,
                    subject=final_subject,
                    body=final_body
                )

                messagebox.showinfo(_("common.success"), f"Report emailed successfully to {recipient}")
                dialog.destroy()

            except tk.TclError as e:
                messagebox.showerror("Email Error", f"Failed to send email: {str(e)}")

        ttk.Button(button_frame, text="Send Email", command=send_email).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    except (tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Failed to prepare email: {str(e)}")

def save_report_to_file(self):
    """Save current report to a file."""
    report_content = self.report_text.get("1.0", tk.END).strip()

    if not report_content or report_content == "":
        messagebox.showwarning("No Report", "Please generate a report first before saving.")
        return

    try:
        from tkinter import filedialog
        from education_system.university_system.modules.shared.constants import paths

        # Create reports directory if it doesn't exist
        reports_dir = paths.REPORTS_DIR
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Default filename with timestamp
        default_filename = f"library_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        # Ask user where to save
        file_path = filedialog.asksaveasfilename(
            initialdir=reports_dir,
            initialfile=default_filename,
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )

        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report_content)

            messagebox.showinfo(_("common.success"), f"Report saved to:\n{file_path}")

    except (OSError, IOError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Failed to save report: {str(e)}")

def show_report_in_window(self, title: str = "Library Report", report_content: str = None):
    """Display report in a new window with export and email options."""
    # Get report content from report_text if not provided
    if report_content is None:
        report_content = self.report_text.get("1.0", tk.END).strip()

    if not report_content:
        messagebox.showwarning("No Report", "No report content to display.")
        return

    # Create report window
    report_window = tk.Toplevel(self.master)
    report_window.title(f"Report: {title}")
    report_window.geometry("800x600")
    report_window.transient(self.master)

    # Main frame
    main_frame = ttk.Frame(report_window, padding=10)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Title
    title_label = ttk.Label(main_frame, text=title, font=('Arial', 14, 'bold'))
    title_label.pack(pady=(0, 10))

    # Report content area
    content_frame = ttk.Frame(main_frame)
    content_frame.pack(fill=tk.BOTH, expand=True)

    report_text_widget = ScrolledText(content_frame, wrap=tk.WORD, font=('Courier', 10))
    report_text_widget.pack(fill=tk.BOTH, expand=True)
    report_text_widget.insert(tk.END, report_content)
    report_text_widget.config(state=tk.DISABLED)

    # Button frame
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=(10, 0))

    # Export functions
    def export_to_txt():
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile=f"library_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            messagebox.showinfo(_("common.success"), f"Report exported to:\n{file_path}")

    def export_to_json():
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile=f"library_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        if file_path:
            # Parse report content into structured data
            report_data = {
                "title": title,
                "generated_at": datetime.now().isoformat(),
                "content": report_content,
                "sections": []
            }
            # Try to parse sections from report
            lines = report_content.split('\n')
            current_section = {"name": "Overview", "data": []}
            for line in lines:
                if line.strip() and (line.startswith('=') or line.startswith('-')):
                    continue
                elif line.strip().endswith(':') and line.isupper():
                    if current_section["data"]:
                        report_data["sections"].append(current_section)
                    current_section = {"name": line.strip().rstrip(':'), "data": []}
                elif line.strip():
                    current_section["data"].append(line.strip())
            if current_section["data"]:
                report_data["sections"].append(current_section)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2)
            messagebox.showinfo(_("common.success"), f"Report exported to:\n{file_path}")

    def export_to_csv():
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"library_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        if file_path:
            import csv
            lines = report_content.split('\n')
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Report: " + title])
                writer.writerow(["Generated: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
                writer.writerow([])
                for line in lines:
                    if line.strip():
                        # Try to split on colon for key-value pairs
                        if ':' in line and not line.startswith('='):
                            parts = line.split(':', 1)
                            writer.writerow([parts[0].strip(), parts[1].strip() if len(parts) > 1 else ''])
                        else:
                            writer.writerow([line.strip()])
            messagebox.showinfo(_("common.success"), f"Report exported to:\n{file_path}")

    def email_to_admin():
        """Email report to administrator"""
        try:
            # Get admin email from database
            conn = get_db_connection()
            if not conn:
                messagebox.showerror(_("common.error"), "Database connection unavailable")
                return

            cursor = conn.cursor()
            # Try multiple sources for admin email
            admin_email = None
            admin_name = "Administrator"

            # Try users table first
            cursor.execute("""
                SELECT email, username FROM users
                WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                LIMIT 1
            """)
            result = cursor.fetchone()
            if result:
                admin_email = result[0]
                admin_name = result[1]
            else:
                # Try user_accounts table
                cursor.execute("""
                    SELECT email, username FROM user_accounts
                    WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                    LIMIT 1
                """)
                result = cursor.fetchone()
                if result:
                    admin_email = result[0]
                    admin_name = result[1]

            conn.close()

            if not admin_email:
                # Ask user to input email manually
                admin_email = simpledialog.askstring(
                    "Admin Email",
                    "No admin email found in database.\nPlease enter administrator email:",
                    parent=report_window
                )
                if not admin_email or '@' not in admin_email:
                    return

            # Confirm sending
            if not messagebox.askyesno(
                "Confirm Email",
                f"Send report to {admin_name}?\n\nEmail: {admin_email}",
                parent=report_window
            ):
                return

            # Render email from template
            from education_system.university_system.infrastructure.email.email_service import send_email
            from education_system.university_system.infrastructure.email.template_utils import render_template

            subject, body = render_template('library/library_report', {
                'report_title': title,
                'report_date': datetime.now().strftime('%Y-%m-%d'),
                'separator': '='*50,
                'report_content': report_content
            })

            # Fallback if template not found
            if not subject or not body:
                subject = f"Library Report: {title} - {datetime.now().strftime('%Y-%m-%d')}"
                body = f"Library Report\n{'='*50}\n\n{report_content}"

            success = send_email(
                recipient_email=admin_email,
                subject=subject,
                body=body
            )

            if success:
                messagebox.showinfo(_("common.success"), f"Report emailed to {admin_email}", parent=report_window)
            else:
                messagebox.showerror(_("common.error"), "Failed to send email. Check email configuration.", parent=report_window)

        except ImportError as e:
            messagebox.showerror(_("common.error"), f"Email service not available: {e}", parent=report_window)
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to email report: {e}", parent=report_window)

    # Export buttons
    export_frame = ttk.LabelFrame(button_frame, text="Export Options", padding=5)
    export_frame.pack(side=tk.LEFT, padx=5)

    ttk.Button(export_frame, text="📄 Export TXT", command=export_to_txt).pack(side=tk.LEFT, padx=2)
    ttk.Button(export_frame, text="📋 Export JSON", command=export_to_json).pack(side=tk.LEFT, padx=2)
    ttk.Button(export_frame, text="📊 Export CSV", command=export_to_csv).pack(side=tk.LEFT, padx=2)

    # Email button
    ttk.Button(button_frame, text="📧 Email to Admin", command=email_to_admin).pack(side=tk.LEFT, padx=10)

    # Close button
    ttk.Button(button_frame, text=_("common.close"), command=report_window.destroy).pack(side=tk.RIGHT, padx=5)

def open_current_report_window(self):
    """Open the current report (from report_text) in a new window."""
    report_content = self.report_text.get("1.0", tk.END).strip()
    if not report_content:
        messagebox.showwarning("No Report", "Please generate a report first.")
        return
    # Extract title from first line
    lines = report_content.split('\n')
    title = lines[0].strip() if lines else "Library Report"
    self.show_report_in_window(title, report_content)

def generate_circulation_report_gui(self):
    """Generate circulation report"""
    report_window = tk.Toplevel(self.master)
    report_window.title("Circulation Report")
    report_window.geometry("900x700")

    ttk.Label(report_window, text="Circulation Report",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Date range selection
    date_frame = ttk.LabelFrame(report_window, text="Date Range", padding=10)
    date_frame.pack(fill=tk.X, padx=10, pady=10)

    start_date_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))

    ttk.Label(date_frame, text="Start Date:").grid(row=0, column=0, padx=5, pady=5)
    ttk.Entry(date_frame, textvariable=start_date_var, width=15).grid(row=0, column=1, padx=5, pady=5)

    ttk.Label(date_frame, text="End Date:").grid(row=0, column=2, padx=5, pady=5)
    ttk.Entry(date_frame, textvariable=end_date_var, width=15).grid(row=0, column=3, padx=5, pady=5)

    # Report display
    report_frame = ttk.LabelFrame(report_window, text="Report", padding=10)
    report_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    report_text = ScrolledText(report_frame, height=30, width=100, font=('Courier', 10))
    report_text.pack(fill=tk.BOTH, expand=True)

    def generate_report():
        report_text.delete('1.0', tk.END)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            start = start_date_var.get()
            end = end_date_var.get()

            # Get circulation stats
            cursor.execute('''
            SELECT
                COUNT(*) as total_loans,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN status = 'returned' THEN 1 ELSE 0 END) as returned,
                SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) as overdue,
                SUM(COALESCE(fine_amount, 0)) as total_fines
            FROM book_loans
            WHERE checkout_date BETWEEN ? AND ?
            ''', (start, end))

            stats = cursor.fetchone()

            report = f"""
╔══════════════════════════════════════════════════════════════╗
║           LIBRARY CIRCULATION REPORT                         ║
╚══════════════════════════════════════════════════════════════╝

Period: {start} to {end}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

CIRCULATION SUMMARY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Loans:        {stats[0]:,}
Active Loans:       {stats[1]:,}
Returned Loans:     {stats[2]:,}
Overdue Loans:      {stats[3]:,}
Total Fines:        ${stats[4]:,.2f}

"""

            # Most checked out books
            cursor.execute('''
            SELECT b.title, b.author, COUNT(l.loan_id) as loan_count
            FROM book_loans l
            JOIN books b ON l.book_id = b.book_id
            WHERE l.checkout_date BETWEEN ? AND ?
            GROUP BY b.book_id
            ORDER BY loan_count DESC
            LIMIT 10
            ''', (start, end))

            report += "\nTOP 10 MOST CHECKED OUT BOOKS:\n"
            report += "━" * 60 + "\n"
            for idx, (title, author, count) in enumerate(cursor.fetchall(), 1):
                report += f"{idx:2}. {title[:40]:40} by {author[:20]:20} ({count:2} loans)\n"

            # Busiest days
            cursor.execute('''
            SELECT DATE(checkout_date) as day, COUNT(*) as count
            FROM book_loans
            WHERE checkout_date BETWEEN ? AND ?
            GROUP BY day
            ORDER BY count DESC
            LIMIT 5
            ''', (start, end))

            report += "\n\nBUSIEST CHECKOUT DAYS:\n"
            report += "━" * 60 + "\n"
            for day, count in cursor.fetchall():
                report += f"{day}: {count} checkouts\n"

            conn.close()

            report_text.insert('1.0', report)

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to generate report: {str(e)}")

    def export_report():
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(report_text.get('1.0', tk.END))
                messagebox.showinfo(_("common.success"), f"Report exported to:\n{file_path}")
            except (OSError, IOError, tk.TclError, ValueError, TypeError) as e:
                messagebox.showerror(_("common.error"), f"Export failed: {str(e)}")

    # Button frame
    button_frame = ttk.Frame(report_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Generate Report", command=generate_report).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Export Report", command=export_report).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=report_window.destroy).pack(side=tk.RIGHT, padx=5)

    # Auto-generate on open
    generate_report()

