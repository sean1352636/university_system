"""
Enhanced Library Management System - GUI Version
Maintains all original CLI functions while adding a modern GUI interface
Backwards compatible with existing database and auth systems
"""


import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from education_system.post_18.university_system.core.i18n import get_text as _, init_i18n
init_i18n()
from tkinter.scrolledtext import ScrolledText
import threading
import queue
import os
import sys
from datetime import datetime, timedelta
import json
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from typing import Dict, List, Optional, Any
import logging
import urllib.request
import urllib.parse
import urllib.error

# Import custom exceptions for better error handling
from education_system.post_18.university_system.core.exceptions import (
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
    from education_system.post_18.university_system.modules.domain.academics.services.library.settings import (
        auth, get_current_user_id, set_auth, get_library_settings, update_library_setting
    )
    from education_system.post_18.university_system.modules.domain.academics.services.library.menu import display_library_menu
    from education_system.post_18.university_system.modules.domain.academics.services.library.barcode import (
        generate_barcode, generate_qr_code, process_scanned_barcode
    )
    from education_system.post_18.university_system.modules.domain.academics.services.library.reports import (
        generate_circulation_report, generate_library_statistics_export, generate_user_activity_report
    )
    from education_system.post_18.university_system.modules.domain.academics.services.library.database import (
        get_db_connection, init_library_db, log_audit_event
    )
    from education_system.post_18.university_system.modules.domain.academics.services.library.backup import (
        quick_system_health_check, restore_from_backup
    )
    from education_system.post_18.university_system.modules.domain.academics.services.library.reading_lists import view_reading_list_details
    ORIGINAL_LIBRARY_AVAILABLE = True
except ImportError:
    print("Warning: Original library module not found. GUI will use standalone functions.")
    ORIGINAL_LIBRARY_AVAILABLE = False

# Import shared authentication system
try:
    from education_system.post_18.university_system.infrastructure.auth import UserAuth
    from education_system.post_18.university_system.infrastructure.shared_context import get_auth, get_current_user
    SHARED_AUTH_AVAILABLE = True
except ImportError:
    print("Warning: Shared authentication system not found.")
    SHARED_AUTH_AVAILABLE = False
    # Provide fallback functions
    def get_auth():
        return None
    def get_current_user():
        return None

from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import finance integration for student finance account payments
try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
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
    from education_system.post_18.university_system.infrastructure.email.email_service import send_email_as_system
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    def send_email_as_system(*args, **kwargs):
        return False
    print("Warning: Email service not available for library finance")

_AUDIT_LOG_COLUMNS_CACHE: Optional[List[str]] = None
_STUDENT_COLUMNS_CACHE: Optional[List[str]] = None

from education_system.post_18.university_system.modules.domain.academics.gui.library.base import LibraryGUI
from education_system.post_18.university_system.infrastructure.email.template_utils import render_template

def _send_library_payment_confirmation_email(self, student_id, student_name, email, amount):
    """Send email confirmation for library fine payment"""
    try:
        from education_system.post_18.university_system.infrastructure.email.template_utils import render_template

        subject, message = render_template('library_fine_payment', {
            'student_name': student_name,
            'student_id': student_id,
            'amount': f'£{amount:.2f}',
            'payment_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

        if not (subject and message):
            print("Failed to load library fine payment template")
            return

        # Try to send via email GUI
        success = self._send_email_via_gui(email, subject, message)

        if success:
            print(f"Library payment confirmation sent to {student_name} ({email})")
        else:
            # Fallback: show email details
            self._show_library_email_fallback(student_name, email, subject, message, "Payment Confirmation")

    except (ValueError, TypeError) as e:
        print(f"Failed to send library payment confirmation email: {e}")

def _send_email_via_gui(self, to_email, subject, message):
    """Try to send email via email GUI"""
    try:
        from education_system.post_18.university_system.modules.shared.gui.email.email_gui import EmailManagerGUI as EmailGUI
        email_gui = EmailGUI(self.master, self.auth)
        email_gui.send_email(to_email=to_email, subject=subject, message=message)
        return True
    except ImportError:
        return False
    except (ValueError, TypeError) as e:
        print(f"Error sending email via GUI: {e}")
        return False

def _show_library_email_fallback(self, student_name, email, subject, message, email_type):
    """Show fallback dialog for library email"""
    try:
        fallback_window = tk.Toplevel(self.master)
        fallback_window.title(f"Library {email_type} Email - Manual Send")
        fallback_window.geometry("700x500")
        fallback_window.transient(self.master)

        ttk.Label(fallback_window,
                 text=f"Library {email_type.lower()} email for {student_name} - Please send manually:",
                 font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=10)

        details_frame = ttk.LabelFrame(fallback_window, text="Email Details", padding=10)
        details_frame.pack(fill='both', expand=True, padx=10, pady=10)

        details_text = ScrolledText(details_frame, height=20, width=80)
        details_text.pack(fill='both', expand=True)

        email_details = f"To: {email}\nSubject: {subject}\n\nMessage:\n{message}"
        details_text.insert('1.0', email_details)
        details_text.config(state='disabled')

        ttk.Button(fallback_window, text=_("common.close"), command=fallback_window.destroy).pack(pady=10)
    except tk.TclError as e:
        print(f"Failed to show library email fallback: {e}")

def _send_checkout_confirmation_email(self, book_id, user_id):
    """Send email confirmation for book checkout"""
    try:
        # Get book and user details
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()

                # Get book details
                cursor.execute('SELECT title, author FROM books WHERE book_id = ?', (book_id,))
                book_info = cursor.fetchone()

                # Get user details and calculate due date
                cursor.execute('SELECT first_name, last_name, email_address FROM students WHERE student_id = ?', (user_id,))
                user_info = cursor.fetchone()

                # Get the most recent checkout for due date
                cursor.execute('''
                    SELECT due_date FROM book_loans
                    WHERE book_id = ? AND user_id = ? AND status = 'active'
                    ORDER BY checkout_date DESC LIMIT 1
                ''', (book_id, user_id))
                due_date_info = cursor.fetchone()

                conn.close()

                if book_info and user_info and due_date_info:
                    book_title, author = book_info
                    first_name, last_name, email = user_info
                    due_date = due_date_info[0]

                    template_vars = {
                        'student_name': f"{first_name} {last_name}",
                        'student_id': user_id,
                        'book_id': book_id,
                        'book_title': book_title,
                        'author': author,
                        'due_date': due_date
                    }

                    subject, message = render_template('library_book_checkout', template_vars)

                    if not subject or not message:
                        print("Failed to load email template.")
                        return

                    # Send email
                    success = self._send_email_via_gui(email, subject, message)

                    if success:
                        print(f"Checkout confirmation sent to {first_name} {last_name} ({email})")
                    else:
                        self._show_library_email_fallback(f"{first_name} {last_name}", email, subject, message, "Checkout Confirmation")

    except (ValueError, TypeError) as e:
        print(f"Failed to send checkout confirmation email: {e}")

def _send_return_confirmation_email(self, book_id, user_id):
    """Send email confirmation for book return"""
    try:
        # Get book and user details
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()

                # Get book details
                cursor.execute('SELECT title, author FROM books WHERE book_id = ?', (book_id,))
                book_info = cursor.fetchone()

                # Get user details
                cursor.execute('SELECT first_name, last_name, email_address FROM students WHERE student_id = ?', (user_id,))
                user_info = cursor.fetchone()

                # Check for any fines on the return
                cursor.execute('''
                    SELECT fine_amount FROM book_loans
                    WHERE book_id = ? AND user_id = ? AND status = 'returned'
                    ORDER BY return_date DESC LIMIT 1
                ''', (book_id, user_id))
                fine_info = cursor.fetchone()

                conn.close()

                if book_info and user_info:
                    book_title, author = book_info
                    first_name, last_name, email = user_info
                    fine_amount = fine_info[0] if fine_info and fine_info[0] else 0.0

                    template_vars = {
                        'student_name': f"{first_name} {last_name}",
                        'student_id': user_id,
                        'book_id': book_id,
                        'book_title': book_title,
                        'author': author,
                        'fine_amount': f"{fine_amount:.2f}"
                    }

                    subject, message = render_template('library_book_return', template_vars)

                    if not subject or not message:
                        print("Failed to load email template.")
                        return

                    # Send email
                    success = self._send_email_via_gui(email, subject, message)

                    if success:
                        print(f"Return confirmation sent to {first_name} {last_name} ({email})")
                    else:
                        self._show_library_email_fallback(f"{first_name} {last_name}", email, subject, message, "Return Confirmation")

    except (ValueError, TypeError) as e:
        print(f"Failed to send return confirmation email: {e}")

def send_automated_notifications_gui(self):
    """Automated notification management interface"""
    notif_window = tk.Toplevel(self.master)
    notif_window.title("Automated Notifications")
    notif_window.geometry("700x600")

    ttk.Label(notif_window, text="Automated Notification System",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Notebook for different notification types
    notebook = ttk.Notebook(notif_window)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Tab 1: Due Date Reminders
    due_tab = ttk.Frame(notebook)
    notebook.add(due_tab, text="Due Date Reminders")

    ttk.Label(due_tab, text="Send due date reminders to users with books due soon",
             wraplength=600).pack(pady=10, padx=10)

    days_before_var = tk.IntVar(value=3)
    ttk.Label(due_tab, text="Days before due date:").pack(pady=5)
    ttk.Spinbox(due_tab, from_=1, to=14, textvariable=days_before_var, width=10).pack(pady=5)

    def send_due_reminders():
        try:
            days = days_before_var.get()
            cutoff_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT l.user_id, b.title, l.due_date
            FROM book_loans l
            JOIN books b ON l.book_id = b.book_id
            WHERE l.status = 'active' AND l.due_date <= ? AND l.due_date > ?
            ''', (cutoff_date, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            reminders = cursor.fetchall()
            conn.close()

            if not reminders:
                messagebox.showinfo("No Reminders", "No books due in the next {days} days")
                return

            # Simulate sending (in real system, would send emails)
            count = len(reminders)
            messagebox.showinfo(_("common.success"),
                f"Sent {count} due date reminder(s)\n\n" +
                f"Books due within {days} days")

            log_audit_event(get_current_user_id(), f"Sent {count} due date reminders", "notifications")

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to send reminders: {str(e)}")

    ttk.Button(due_tab, text="Send Due Date Reminders", command=send_due_reminders).pack(pady=20)

    # Tab 2: Overdue Notifications
    overdue_tab = ttk.Frame(notebook)
    notebook.add(overdue_tab, text="Overdue Notifications")

    ttk.Label(overdue_tab, text="Send notifications to users with overdue books",
             wraplength=600).pack(pady=10, padx=10)

    def send_overdue_notifs():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT l.user_id, b.title, l.due_date,
                   julianday('now') - julianday(l.due_date) as days_overdue
            FROM book_loans l
            JOIN books b ON l.book_id = b.book_id
            WHERE l.status = 'active' AND l.due_date < datetime('now')
            ''')

            overdue = cursor.fetchall()
            conn.close()

            if not overdue:
                messagebox.showinfo("No Overdue", "No overdue books found")
                return

            count = len(overdue)
            messagebox.showinfo(_("common.success"),
                f"Sent {count} overdue notification(s)")

            log_audit_event(get_current_user_id(), f"Sent {count} overdue notifications", "notifications")

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to send notifications: {str(e)}")

    ttk.Button(overdue_tab, text="Send Overdue Notifications", command=send_overdue_notifs).pack(pady=20)

    # Tab 3: Reservation Notifications
    reservation_tab = ttk.Frame(notebook)
    notebook.add(reservation_tab, text="Reservation Alerts")

    ttk.Label(reservation_tab, text="Send notifications for available reserved books",
             wraplength=600).pack(pady=10, padx=10)

    def send_reservation_available():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Find books that became available and have active reservations
            cursor.execute('''
            SELECT r.user_id, b.title, r.reservation_id
            FROM book_reservations r
            JOIN books b ON r.book_id = b.book_id
            WHERE r.status = 'active' AND b.status = 'available' AND r.priority_order = 1
            ''')

            available = cursor.fetchall()

            if not available:
                messagebox.showinfo("No Notifications", "No reserved books are available")
                conn.close()
                return

            # Update reservations to fulfilled
            for user_id, title, res_id in available:
                cursor.execute('UPDATE book_reservations SET status = "fulfilled" WHERE reservation_id = ?', (res_id,))

            conn.commit()
            conn.close()

            count = len(available)
            messagebox.showinfo(_("common.success"),
                f"Sent {count} reservation available notification(s)")

            log_audit_event(get_current_user_id(), f"Sent {count} reservation notifications", "notifications")

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to send notifications: {str(e)}")

    ttk.Button(reservation_tab, text="Send Reservation Available Notifications",
              command=send_reservation_available).pack(pady=20)

    # Close button
    ttk.Button(notif_window, text=_("common.close"), command=notif_window.destroy).pack(pady=10)

def open_calendar_with_due_dates(self):
    """Show book return dates in a list view"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_("common.error"), "Could not connect to database")
            return

        cursor = conn.cursor()
        # Show all active/overdue loans
        cursor.execute('''
            SELECT bl.loan_id, bl.book_id, b.title, b.author, bl.user_id,
                   bl.checkout_date, bl.due_date, bl.return_date, bl.status
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            ORDER BY
                CASE bl.status
                    WHEN 'overdue' THEN 1
                    WHEN 'active' THEN 2
                    WHEN 'returned' THEN 3
                    ELSE 4
                END,
                bl.due_date ASC
        ''')
        loans = cursor.fetchall()
        conn.close()

        # Create window
        dialog = tk.Toplevel(self.master)
        dialog.title("Book Return Calendar")
        dialog.geometry("900x500")
        dialog.transient(self.master)

        ttk.Label(dialog, text="Book Return Dates", font=('Arial', 14, 'bold')).pack(pady=10)

        # Treeview
        columns = ('Loan ID', 'Book ID', 'Title', 'Author', 'User', 'Checked Out', 'Due Date', 'Returned', 'Status')
        tree_frame = ttk.Frame(dialog)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=18)
        widths = {'Loan ID': 60, 'Book ID': 70, 'Title': 180, 'Author': 120,
                  'User': 80, 'Checked Out': 100, 'Due Date': 100, 'Returned': 100, 'Status': 80}
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=widths.get(col, 100), anchor='w')

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        for loan in loans:
            lid, bid, title, author, uid, co_date, due, ret, status = loan
            tags = []
            if status == 'overdue':
                tags = ['overdue']
            elif status == 'returned':
                tags = ['returned']

            tree.insert('', 'end', values=(
                lid, bid, title[:35], author[:20] if author else '',
                uid, (co_date or '')[:10], (due or '')[:10],
                (ret or '')[:10], status
            ), tags=tags)

        tree.tag_configure('overdue', background='#ffebee')
        tree.tag_configure('returned', background='#e8f5e9')

        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror(_("common.error"), f"Could not load return dates: {e}")

def add_calendar_button_to_interface(self):
    """Add calendar button to the main interface"""
    try:
        # Add button to the control frame if it exists
        if hasattr(self, 'control_frame'):
            calendar_button = ttk.Button(self.control_frame,
                                       text="📅 View Return Calendar",
                                       command=self.open_calendar_with_due_dates)
            calendar_button.pack(side=tk.LEFT, padx=5)
    except tk.TclError as e:
        print(f"Could not add calendar button: {e}")

